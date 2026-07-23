"""Scrollable activity-history pager, pushed over the main UI by the ``history`` command.

Replaces the old behaviour of dumping rows into the main ``#log`` (where they
scroll off as new output arrives): events render in a dedicated full-screen
overlay the user scrolls through at their own pace and then dismisses with
``q`` / ``Esc`` / ``Enter``. The scroll container takes focus on mount, so the
arrow keys, ``Page Up`` / ``Page Down`` and ``Home`` / ``End`` page through long
histories natively.

Layout (top to bottom):

* title line  — robot name, event count, and the spanned date range
* summary line — a compact event-type breakdown (cleans, cat visits, …)
* column header — pinned ``TIME`` / ``EVENT`` row aligned with the data
* scroll area — one styled row per event, newest first, fixed-width timestamps
* footer — navigation + close hints

Timestamps are rendered at a fixed width so the event column lines up
vertically regardless of an event's age — every event shows its date.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Static
from tzlocal import get_localzone

from .activity_labels import format_activity

if TYPE_CHECKING:
    from pylitterbot.activity import Activity

# Fixed width of the timestamp column. ``MM/DD HH:MM`` (11) covers the common
# case; older-year dates (``YYYY-MM-DD``) and the ``?`` placeholder are padded
# to match so the event column always starts at the same offset.
_TS_WIDTH = 11

# Keywords used to bucket events into the summary line — kept loose so unknown
# raw strings still fall into "other" rather than mislabeling.
_ALERT_KEYWORDS = ("offline", "fault", "pinch", "power", "motor", "timing")


def _localize(ts: object) -> datetime | None:
    """Coerce an activity timestamp to a local-tz-aware datetime, or ``None``."""
    if not isinstance(ts, datetime):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(get_localzone())


def _ts_str(local_dt: datetime | None) -> str:
    """Fixed-width timestamp: ``MM/DD HH:MM`` this year, ``YYYY-MM-DD`` older."""
    if local_dt is None:
        return "?"
    if local_dt.year == datetime.now(tz=timezone.utc).year:
        return local_dt.strftime("%m/%d %H:%M")
    return local_dt.strftime("%Y-%m-%d")


def format_history_rows(acts: list[Activity], pets: list[Any] | None = None) -> list[Text]:
    """Translate activities into display rows, newest first.

    Each row is a styled ``Text`` of ``"  <timestamp>  <label>"`` — the timestamp
    (padded to ``_TS_WIDTH``) in muted grey followed by the translated label in
    its event colour. ``acts`` is assumed newest-first from the API, so the most
    recent event ends up at the top of the pager.
    """
    rows: list[Text] = []
    for act in acts:
        ts_str = _ts_str(_localize(getattr(act, "timestamp", None)))
        label, colour = format_activity(act, pets)
        row = Text()
        row.append(f"  {ts_str.ljust(_TS_WIDTH)}  ", style="#484f58")
        row.append(label, style=colour)
        rows.append(row)
    return rows


def _category(label: str) -> str:
    """Bucket a translated label into a short summary name."""
    low = label.lower()
    if "clean cycle complete" in low:
        return "clean"
    if "cleaning" in low:
        return "cleaning"
    if "cat" in low:
        return "cat visits"
    if "drawer" in low:
        return "drawer"
    if low == "ready":
        return "ready"
    if any(k in low for k in _ALERT_KEYWORDS):
        return "alerts"
    return "other"


def _summarize(acts: list[Activity], pets: list[Any] | None = None) -> str:
    """Compact event-type breakdown, e.g. ``5 clean · 3 cat visits · 6 ready``."""
    counts: Counter[str] = Counter()
    for act in acts:
        label, _ = format_activity(act, pets)
        counts[_category(label)] += 1
    # Stable display: by count desc, then category name so ties don't shuffle.
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return " · ".join(f"{n} {name}" for name, n in ranked)


def _date_range(acts: list[Activity]) -> str:
    """Render the span of event dates as ``MM/DD`` / ``MM/DD – MM/DD`` / ``—``."""
    days = sorted(d for a in acts if (d := _localize(getattr(a, "timestamp", None))) is not None)
    if not days:
        return "—"
    if len(days) == 1:
        return days[0].strftime("%m/%d")
    return f"{days[0].strftime('%m/%d')} – {days[-1].strftime('%m/%d')}"


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'s' if n != 1 else ''}"


class HistoryScreen(ModalScreen[None]):
    """Full-screen, scrollable view of recent activity history."""

    CSS = """
    HistoryScreen {
        background: #0d1117;
    }

    #history-title {
        dock: top;
        height: 1;
        background: #161b22;
        padding: 0 2;
        color: #58a6ff;
        text-style: bold;
    }

    #history-meta {
        dock: top;
        height: 1;
        background: #161b22;
        border-bottom: solid #30363d;
        padding: 0 2;
        color: #8b949e;
    }

    #history-colhead {
        dock: top;
        height: 1;
        background: #0d1117;
        padding: 0 2;
        color: #484f58;
        text-style: italic;
    }

    #history-footer {
        dock: bottom;
        height: 1;
        background: #161b22;
        border-top: solid #30363d;
        padding: 0 2;
        color: #484f58;
    }

    #history-scroll {
        height: 1fr;
        padding: 0 0 1 0;
        scrollbar-background: #161b22;
        scrollbar-color: #30363d;
        scrollbar-color-hover: #58a6ff;
    }

    #history-empty {
        color: #8b949e;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("escape,q,enter", "dismiss", "Close", show=False, priority=True),
    ]

    def __init__(self, acts: list[Activity], pets: list[Any] | None, robot_name: str) -> None:
        super().__init__()
        self._acts = acts
        self._pets = pets
        self._robot_name = robot_name

    def compose(self) -> ComposeResult:
        count = len(self._acts)
        yield Static(self._title_line(count), id="history-title")
        yield Static(self._meta_line(count), id="history-meta")
        if count:
            yield Static(self._column_header(), id="history-colhead")
        with ScrollableContainer(id="history-scroll"):
            if count:
                for row in format_history_rows(self._acts, self._pets):
                    yield Static(row)
            else:
                yield Static("No activity history available for this robot.", id="history-empty")
        yield Static(
            "  ↑/↓ scroll   PgUp/PgDn page   Home/End jump   q · Esc · Enter close",
            id="history-footer",
        )

    def on_mount(self) -> None:
        self.query_one("#history-scroll", ScrollableContainer).focus()

    def _title_line(self, count: int) -> str:
        return f"  Activity history — {self._robot_name}   {_plural(count, 'event')}   {_date_range(self._acts)}"

    def _meta_line(self, count: int) -> str:
        if not count:
            return "  Nothing to show — the robot has no recent activity."
        return f"  {_summarize(self._acts, self._pets)}"

    def _column_header(self) -> str:
        return f"  {'TIME'.ljust(_TS_WIDTH)}  EVENT"
