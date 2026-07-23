"""Scrollable activity-history pager, pushed over the main UI by the ``history`` command.

Replaces the old behaviour of dumping rows into the main ``#log`` (where they
scroll off as new output arrives): events render in a dedicated full-screen
overlay the user scrolls through at their own pace and then dismisses with
``q`` / ``Esc`` / ``Enter``. The scroll container takes focus on mount, so the
arrow keys, ``Page Up`` / ``Page Down`` and ``Home`` / ``End`` page through long
histories natively.
"""

from __future__ import annotations

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


def format_history_rows(acts: list[Activity], pets: list[Any] | None = None) -> list[Text]:
    """Translate activities into display rows, newest first.

    Each row is a styled ``Text`` of ``"  <timestamp>  <label>"`` — the timestamp
    in muted grey followed by the translated label in its event colour. Timestamps
    render in the local timezone; same-day events show ``HH:MM``, this-year events
    show ``mm/dd HH:MM`` and older events show the full date, mirroring the status
    bar's relative-time philosophy. ``acts`` is assumed newest-first from the API,
    so the most recent event ends up at the top of the pager.
    """
    today = datetime.now(tz=timezone.utc).date()
    rows: list[Text] = []
    for act in acts:
        ts_dt = getattr(act, "timestamp", None)
        if ts_dt is not None:
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)
            local_dt = ts_dt.astimezone(get_localzone())
            if local_dt.date() == today:
                ts_str = local_dt.strftime("%H:%M")
            elif local_dt.year == today.year:
                ts_str = local_dt.strftime("%m/%d %H:%M")
            else:
                ts_str = local_dt.strftime("%Y-%m-%d %H:%M")
        else:
            ts_str = "?"
        label, colour = format_activity(act, pets)
        row = Text()
        row.append(f"  {ts_str}  ", style="#484f58")
        row.append(label, style=colour)
        rows.append(row)
    return rows


class HistoryScreen(ModalScreen[None]):
    """Full-screen, scrollable view of recent activity history."""

    CSS = """
    HistoryScreen {
        background: #0d1117;
    }

    #history-header {
        dock: top;
        height: 1;
        background: #161b22;
        border-bottom: solid #30363d;
        color: #58a6ff;
        padding: 0 2;
        text-style: bold;
    }

    #history-scroll {
        height: 1fr;
        padding: 1 2;
        scrollbar-background: #161b22;
        scrollbar-color: #30363d;
        scrollbar-color-hover: #58a6ff;
    }

    #history-empty {
        color: #8b949e;
    }
    """

    BINDINGS = [
        Binding("escape,q,enter", "dismiss", "Close", show=False, priority=True),
    ]

    def __init__(self, rows: list[Text], title: str) -> None:
        super().__init__()
        self._rows = rows
        self._title = title

    def compose(self) -> ComposeResult:
        yield Static(self._title, id="history-header")
        with ScrollableContainer(id="history-scroll"):
            if self._rows:
                for row in self._rows:
                    yield Static(row)
            else:
                yield Static("No activity history available.", id="history-empty")

    def on_mount(self) -> None:
        self.query_one("#history-scroll", ScrollableContainer).focus()
