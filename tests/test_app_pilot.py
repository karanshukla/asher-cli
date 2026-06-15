"""Integration tests for asher.app using Textual's Pilot."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from asher.app import AsherApp


@pytest.fixture
def mock_robot():
    """Create a mock Litter Robot."""
    robot = MagicMock()
    robot.name = "TestBot"
    robot.is_online = True
    robot.waste_drawer_level = 50.0
    robot.status = MagicMock()
    robot.status.value = "Ready"
    robot.sleeping = False
    robot.panel_lockout = False
    robot.night_light_mode_enabled = False
    robot.serial = "LR12345"
    robot.last_seen = datetime.now(timezone.utc)
    robot.pet_weight = 10.5
    robot.refresh = AsyncMock()
    robot.start_cleaning = AsyncMock(return_value=True)
    robot.set_panel_lockout = AsyncMock(return_value=True)
    robot.set_sleep_mode = AsyncMock(return_value=True)
    robot.set_night_light_brightness = AsyncMock()
    robot.get_activity_history = AsyncMock(return_value=[])
    return robot


@pytest.fixture
def mock_account(mock_robot):
    """Create a mock Whisker Account."""
    account = MagicMock()
    account.robots = [mock_robot]
    account.pets = []
    account.connect = AsyncMock()
    account.disconnect = AsyncMock()
    return account


@pytest.mark.asyncio
async def test_app_initial_state():
    """Test that AsherApp initializes with correct default state."""
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        # Check initial state before running
        assert app._account is None
        assert app._robot is None
        assert app._is_loading is True
        assert app._cat_mode == "idle"
        assert app._cat_frame == 0
        from asher.login_flow import LoginState

        assert app._login.state is LoginState.IDLE


@pytest.mark.asyncio
async def test_app_shows_login_prompt_without_credentials():
    """Test that app shows login prompt when no credentials exist."""
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # App should show not signed in state
            assert app._account is None
            assert app._robot is None


@pytest.mark.asyncio
async def test_app_bindings_exist():
    """Test that app has expected key bindings."""
    app = AsherApp()
    bindings = {b.key for b in app.BINDINGS}
    assert "ctrl+c" in bindings
    assert "ctrl+l" in bindings
    assert "escape" in bindings


@pytest.mark.asyncio
async def test_app_composes_ui():
    """Test that app composes all expected UI widgets."""
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Check UI widgets exist
            assert app.query_one("#status-bar")
            assert app.query_one("#main-area")
            assert app.query_one("#log")
            assert app.query_one("#cat-panel")
            assert app.query_one("#cat-art")
            assert app.query_one("#cat-label")
            assert app.query_one("#bottom-dock")
            assert app.query_one("#input-bar")
            assert app.query_one("#cmd-input")
            assert app.query_one("#hint-bar")


@pytest.mark.asyncio
async def test_status_bar_widgets_exist():
    """Test that status bar has all expected labels."""
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#title-lbl")
            assert app.query_one("#robot-lbl")
            assert app.query_one("#online-lbl")
            assert app.query_one("#status-lbl")
            assert app.query_one("#drawer-lbl")
            assert app.query_one("#weight-lbl")
            assert app.query_one("#clean-lbl")


@pytest.mark.asyncio
async def test_quit_command_exits_app():
    """Test that typing 'quit' exits the app."""
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Type quit command
            await pilot.click("#cmd-input")
            await pilot.press("q", "u", "i", "t")
            await pilot.press("enter")
            # App should exit
        assert app._exit


@pytest.mark.asyncio
async def test_clear_command_clears_log():
    """Test that 'clear' command clears the log."""
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            log = app.query_one("#log")
            # Add some content to log
            log.write("Test message")
            assert len(log.lines) > 0
            # Type clear command
            await pilot.click("#cmd-input")
            await pilot.press("c", "l", "e", "a", "r")
            await pilot.press("enter")
            # Log should be cleared
            assert len(log.lines) == 0


@pytest.mark.asyncio
async def test_help_command_shows_help():
    """Test that 'help' command displays help text."""
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            log = app.query_one("#log")
            initial_lines = len(log.lines)
            # Type help command
            await pilot.click("#cmd-input")
            await pilot.press("h", "e", "l", "p")
            await pilot.press("enter")
            await pilot.pause()
            # Log should have more content
            assert len(log.lines) > initial_lines


@pytest.mark.asyncio
async def test_ctrl_l_clears_log():
    """Test that Ctrl+L key binding clears the log."""
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            log = app.query_one("#log")
            log.write("Test message")
            assert len(log.lines) > 0
            # Press Ctrl+L
            await pilot.press("ctrl+l")
            # Log should be cleared
            assert len(log.lines) == 0
