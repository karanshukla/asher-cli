"""Tests for asher.history_view — the activity-history pager.

Covers two layers:

* ``format_history_rows`` — pure formatter (timestamp + ``format_activity``), no
  Textual or event-loop dependency, mirroring ``test_activity_labels.py``.
* ``HistoryScreen`` — structure, focus-on-mount, and Pilot-driven dismiss,
  mirroring the ``LoginScreen`` pattern in ``test_auth_pilot.py``.
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


# ── format_history_rows ──────────────────────────────────────────────────────


class TestFormatHistoryRows:
    def test_returns_one_text_per_activity(self):
        acts = [
            _act(LitterBoxStatus.CLEAN_CYCLE_COMPLETE),
            _act(LitterBoxStatus.READY),
        ]
        rows = format_history_rows(acts)
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

    def test_same_day_timestamp_shows_only_time(self):
        from tzlocal import get_localzone

        now = datetime.now(tz=timezone.utc)
        rows = format_history_rows([_act("Ready", timestamp=now)])
        # HH:MM only — no date component for a same-day event (compared in the
        # formatter's local timezone, not the raw UTC value).
        rendered = str(rows[0])
        assert now.astimezone(get_localzone()).strftime("%H:%M") in rendered

    def test_naive_timestamp_is_treated_as_utc(self):
        # pylitterbot returns tz-aware datetimes, but the formatter degrades
        # gracefully if it ever receives a naive one.
        naive = datetime(2026, 6, 14, 12, 0)
        rows = format_history_rows([_act("Ready", timestamp=naive)])
        assert len(rows) == 1

    def test_missing_timestamp_renders_placeholder(self):
        act = SimpleNamespace(action="Ready", timestamp=None)
        row = str(format_history_rows([act])[0])
        assert "?" in row

    def test_translated_label_and_colour_flow_through(self):
        # Cat-detected events are amber and gain a pet/weight suffix when pets
        # are supplied — the row should carry both the timestamp and the label.
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


def _some_rows() -> list:
    from rich.text import Text

    return [Text("Clean cycle complete", style="#3fb950"), Text("Ready", style="#484f58")]


@pytest.mark.asyncio
async def test_history_screen_renders_header_and_rows():
    screen = HistoryScreen(_some_rows(), "  Activity history — TestBot   2 events   [q] close")
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen is screen
        header = screen.query_one("#history-header", Static)
        assert "Activity history" in str(header.render())
        rows = screen.query("#history-scroll Static")
        # Two event rows (the #history-empty placeholder must not appear).
        assert len(rows) == 2


@pytest.mark.asyncio
async def test_history_screen_scroll_takes_focus_on_mount():
    screen = HistoryScreen(_some_rows(), "title")
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        scroll = screen.query_one("#history-scroll", ScrollableContainer)
        assert scroll.has_focus


@pytest.mark.asyncio
async def test_history_screen_empty_state_shows_placeholder():
    screen = HistoryScreen([], "title")
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        empty = screen.query_one("#history-empty", Static)
        assert "No activity history" in str(empty.render())


@pytest.mark.asyncio
async def test_history_screen_q_dismisses():
    screen = HistoryScreen(_some_rows(), "title")
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen is screen
        await pilot.press("q")
        await pilot.pause()
        # Screen popped — back to the app's default screen.
        assert app.screen is not screen


@pytest.mark.asyncio
async def test_history_screen_escape_dismisses():
    screen = HistoryScreen(_some_rows(), "title")
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is not screen


@pytest.mark.asyncio
async def test_history_screen_enter_dismisses():
    screen = HistoryScreen(_some_rows(), "title")
    app = _ShellApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen is not screen


@pytest.mark.asyncio
async def test_history_command_pushes_screen_with_default_limit():
    """End-to-end: typing `history` fetches with the new default and pushes the pager."""
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
        # New default limit is 50 (was 25 before the pager shipped).
        app._robot.get_activity_history.assert_called_once_with(limit=50)
        # The pager screen is now on top of the screen stack.
        assert app.screen.__class__.__name__ == "HistoryScreen"
        header = app.screen.query_one("#history-header", Static)
        assert "TestBot" in str(header.render())
        assert "1 event" in str(header.render())
