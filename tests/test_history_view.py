"""Tests for asher.history_view — the activity-history pager.

Covers two layers:

* ``format_history_rows`` — pure formatter (timestamp + ``format_activity``), no
  Textual or event-loop dependency, mirroring ``test_activity_labels.py``.
* ``HistoryScreen`` — structure, focus-on-mount, layout widgets, and
  Pilot-driven dismiss, mirroring the ``LoginScreen`` pattern in
  ``test_auth_pilot.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from pylitterbot.enums import LitterBoxStatus
from textual.app import App
from textual.containers import ScrollableContainer
from textual.widgets import Static

from asher.history_view import HistoryScreen, format_history_rows


def _act(action: Any, *, timestamp: datetime | None = None) -> SimpleNamespace:
    """A duck-typed Activity — only ``timestamp`` and ``action`` are read here."""
    return SimpleNamespace(
        timestamp=timestamp or datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc),
        action=action,
    )


def _some_acts() -> list:
    """A couple of newish activities for screen-structure tests."""
    return [
        _act(
            LitterBoxStatus.CLEAN_CYCLE_COMPLETE,
            timestamp=datetime(2026, 6, 14, 14, 0, tzinfo=timezone.utc),
        ),
        _act(LitterBoxStatus.READY, timestamp=datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)),
    ]


# ── format_history_rows ──────────────────────────────────────────────────────


class TestFormatHistoryRows:
    def test_returns_one_text_per_activity(self):
        rows = format_history_rows(
            [_act(LitterBoxStatus.CLEAN_CYCLE_COMPLETE), _act(LitterBoxStatus.READY)]
        )
        assert len(rows) == 2

    def test_preserves_input_order_newest_first(self):
        # The formatter renders in the local timezone, so compare against the
        # local-converted strings rather than the raw UTC literals.
        from tzlocal import get_localzone

        newer = datetime(2026, 6, 14, 14, 0, tzinfo=timezone.utc)
        older = datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)
        acts = [
            _act(LitterBoxStatus.READY, timestamp=newer),
            _act("Clean Cycle Complete", timestamp=older),
        ]
        rows = format_history_rows(acts)
        # Input order is retained verbatim — the caller passes newest-first.
        assert newer.astimezone(get_localzone()).strftime("%H:%M") in str(rows[0])
        assert older.astimezone(get_localzone()).strftime("%H:%M") in str(rows[1])

    def test_timestamps_are_fixed_width_so_labels_align(self):
        # Today's events used to show only HH:MM while older ones showed the
        # date, leaving ragged indentation. Every timestamp must now be padded
        # to the same width so the event column lines up vertically.
        from tzlocal import get_localzone

        today = datetime.now(tz=timezone.utc)
        older = datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc)
        rows = format_history_rows([_act("Ready", timestamp=today), _act("Ready", timestamp=older)])
        first_ts = str(rows[0]).split("Ready")[0]
        second_ts = str(rows[1]).split("Ready")[0]
        # Both timestamp prefixes are the same length → labels start aligned.
        assert len(first_ts) == len(second_ts)
        # The today-event carries a date (MM/DD), not bare time.
        assert today.astimezone(get_localzone()).strftime("%m/%d") in first_ts

    def test_naive_timestamp_is_treated_as_utc(self):
        # pylitterbot returns tz-aware datetimes, but the formatter degrades
        # gracefully if it ever receives a naive one.
        naive = datetime(2026, 6, 14, 12, 0)
        assert len(format_history_rows([_act("Ready", timestamp=naive)])) == 1

    def test_missing_timestamp_renders_placeholder(self):
        act = SimpleNamespace(action="Ready", timestamp=None)
        assert "?" in str(format_history_rows([act])[0])

    def test_translated_label_and_colour_flow_through(self):
        pets = [SimpleNamespace(id="pet-1", name="Asher")]
        act = SimpleNamespace(
            timestamp=datetime.now(tz=timezone.utc),
            action="Cat Detected",
            weight=9.1,
            pet_id="pet-1",
        )
        row = str(format_history_rows([act], pets)[0])
        assert "Cat detected" in row
        assert "Asher" in row
        assert "9.1 lb" in row

    def test_empty_input_returns_empty_list(self):
        assert format_history_rows([]) == []


# ── HistoryScreen ────────────────────────────────────────────────────────────


class _ShellApp(App):
    """Minimal app that pushes a HistoryScreen on mount, for Pilot tests.

    Named without a leading ``Test`` so pytest doesn't collect it (same guard
    as ``LoginTestApp`` in ``test_auth_pilot.py``).
    """

    def __init__(self, screen: HistoryScreen) -> None:
        super().__init__()
        self._screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._screen)


def _screen(acts: list | None = None) -> HistoryScreen:
    return HistoryScreen(acts if acts is not None else _some_acts(), None, "TestBot")


@pytest.mark.asyncio
async def test_history_screen_renders_title_meta_and_rows():
    screen = _screen()
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen is screen
        title = screen.query_one("#history-title", Static)
        assert "Activity history" in str(title.render())
        assert "TestBot" in str(title.render())
        assert "2 events" in str(title.render())
        # Summary (event-type breakdown) line is present.
        meta = screen.query_one("#history-meta", Static)
        assert str(meta.render()).strip() != ""
        # Column header is pinned above the scroll area.
        colhead = screen.query_one("#history-colhead", Static)
        assert "TIME" in str(colhead.render())
        assert "EVENT" in str(colhead.render())
        # Two event rows inside the scroll area.
        rows = screen.query("#history-scroll Static")
        assert len(rows) == 2


@pytest.mark.asyncio
async def test_history_screen_footer_shows_navigation_and_close_hints():
    screen = _screen()
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        footer = str(screen.query_one("#history-footer", Static).render())
        # Close hints for all three dismiss keys.
        assert "q" in footer
        assert "Esc" in footer
        assert "Enter" in footer
        # Navigation hints.
        assert "PgUp" in footer or "Page" in footer


@pytest.mark.asyncio
async def test_history_screen_title_singular_event():
    screen = _screen([_act(LitterBoxStatus.CLEAN_CYCLE_COMPLETE)])
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "1 event" in str(screen.query_one("#history-title", Static).render())


@pytest.mark.asyncio
async def test_history_screen_scroll_takes_focus_on_mount():
    screen = _screen()
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert screen.query_one("#history-scroll", ScrollableContainer).has_focus


@pytest.mark.asyncio
async def test_history_screen_empty_state_shows_placeholder():
    screen = _screen([])
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        title = str(screen.query_one("#history-title", Static).render())
        assert "0 events" in title
        empty = screen.query_one("#history-empty", Static)
        assert "No activity history" in str(empty.render())


@pytest.mark.asyncio
async def test_history_screen_q_dismisses():
    screen = _screen()
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen is screen
        await pilot.press("q")
        await pilot.pause()
        assert app.screen is not screen


@pytest.mark.asyncio
async def test_history_screen_escape_dismisses():
    screen = _screen()
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is not screen


@pytest.mark.asyncio
async def test_history_screen_enter_dismisses():
    screen = _screen()
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen is not screen


@pytest.mark.asyncio
async def test_history_command_pushes_screen_with_default_limit():
    """End-to-end: typing `history` fetches with the default and pushes the pager."""
    from unittest.mock import AsyncMock, MagicMock

    from asher.app import AsherApp
    from asher.robot_adapters import LR3Adapter

    robot = MagicMock()
    robot.name = "TestBot"
    robot.is_online = True
    robot.status = MagicMock(value="Ready")
    robot.last_seen = datetime.now(timezone.utc)
    robot.get_activity_history = AsyncMock(
        return_value=[_act(LitterBoxStatus.CLEAN_CYCLE_COMPLETE)]
    )

    app = AsherApp()
    app._robot = robot
    app._adapter = LR3Adapter(robot)
    app._account = MagicMock()
    app._account.disconnect = AsyncMock()
    app._pets = []
    app._connect_worker = lambda **kwargs: None  # type: ignore[method-assign]

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("h", "i", "s", "t", "o", "r", "y")
        await pilot.press("enter")
        await pilot.pause()
        # Default limit is 50 (was 25 before the pager shipped).
        app._robot.get_activity_history.assert_called_once_with(limit=50)
        # The pager screen is now on top of the screen stack.
        assert app.screen.__class__.__name__ == "HistoryScreen"
        title = app.screen.query_one("#history-title", Static)
        assert "TestBot" in str(title.render())
        assert "1 event" in str(title.render())
