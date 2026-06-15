"""Integration tests for asher.commands using Textual's Pilot."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from asher.app import AsherApp


@pytest.fixture
def connected_app():
    """Create an AsherApp with mocked connected robot."""
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

    app = AsherApp()
    app._robot = robot
    app._account = MagicMock()
    app._account.disconnect = AsyncMock()
    app._pets = []
    return app


@pytest.mark.asyncio
async def test_clean_command_with_connected_robot(connected_app):
    """Test that 'clean' command works when robot is connected."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        # Type clean command
        await pilot.click("#cmd-input")
        await pilot.press("c", "l", "e", "a", "n")
        await pilot.press("enter")
        await pilot.pause()
        # Robot's start_cleaning should be called
        app._robot.start_cleaning.assert_called_once()


@pytest.mark.asyncio
async def test_lock_command_with_connected_robot(connected_app):
    """Test that 'lock' command works when robot is connected."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        # Type lock command
        await pilot.click("#cmd-input")
        await pilot.press("l", "o", "c", "k")
        await pilot.press("enter")
        await pilot.pause()
        # Robot's set_panel_lockout should be called with True
        app._robot.set_panel_lockout.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_unlock_command_with_connected_robot(connected_app):
    """Test that 'unlock' command works when robot is connected."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        # Type unlock command
        await pilot.click("#cmd-input")
        await pilot.press("u", "n", "l", "o", "c", "k")
        await pilot.press("enter")
        await pilot.pause()
        # Robot's set_panel_lockout should be called with False
        app._robot.set_panel_lockout.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_sleep_command_with_connected_robot(connected_app):
    """Test that 'sleep' command works when robot is connected."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        # Type sleep command
        await pilot.click("#cmd-input")
        await pilot.press("s", "l", "e", "e", "p")
        await pilot.press("enter")
        await pilot.pause()
        # Robot's set_sleep_mode should be called with True
        app._robot.set_sleep_mode.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_wake_command_with_connected_robot(connected_app):
    """Test that 'wake' command works when robot is connected."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        # Type wake command
        await pilot.click("#cmd-input")
        await pilot.press("w", "a", "k", "e")
        await pilot.press("enter")
        await pilot.pause()
        # Robot's set_sleep_mode should be called with False
        app._robot.set_sleep_mode.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_status_command_with_connected_robot(connected_app):
    """Test that 'status' command refreshes robot status."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        # Type status command
        await pilot.click("#cmd-input")
        await pilot.press("s", "t", "a", "t", "u", "s")
        await pilot.press("enter")
        await pilot.pause()
        # Robot's refresh should be called
        app._robot.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_history_command_with_connected_robot(connected_app):
    """Test that 'history' command fetches activity history."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        # Type history command
        await pilot.click("#cmd-input")
        await pilot.press("h", "i", "s", "t", "o", "r", "y")
        await pilot.press("enter")
        await pilot.pause()
        # Robot's get_activity_history should be called
        app._robot.get_activity_history.assert_called_once_with(limit=25)


@pytest.mark.asyncio
async def test_night_light_on_command(connected_app):
    """Test that 'night-light on' command works."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        # Type night-light on command
        await pilot.click("#cmd-input")
        await pilot.press("n", "i", "g", "h", "t", "-", "l", "i", "g", "h", "t", " ", "o", "n")
        await pilot.press("enter")
        await pilot.pause()


@pytest.mark.asyncio
async def test_command_shows_error_when_not_connected():
    """Test that commands show error when no robot is connected."""
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            log = app.query_one("#log")
            initial_content = str(log.lines)
            # Try clean command without connection
            await pilot.click("#cmd-input")
            await pilot.press("c", "l", "e", "a", "n")
            await pilot.press("enter")
            await pilot.pause()
            # Should show not connected error
            log_content = str(log.lines)
            assert "Not connected" in log_content or initial_content != log_content


@pytest.mark.asyncio
async def test_slash_login_command_starts_login_flow():
    """Test that '/login' command starts login flow."""
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Type /login command
            await pilot.click("#cmd-input")
            await pilot.press("/", "l", "o", "g", "i", "n")
            await pilot.press("enter")
            await pilot.pause()
            # Login state should be set
            assert app._login_state == "awaiting_email"


@pytest.mark.asyncio
async def test_slash_logout_command_clears_connection(connected_app):
    """Test that '/logout' command disconnects and clears state."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        # Type /logout command
        await pilot.click("#cmd-input")
        await pilot.press("/", "l", "o", "g", "o", "u", "t")
        await pilot.press("enter")
        await pilot.pause()
        # Account should be disconnected and cleared
        assert app._account is None
        assert app._robot is None


@pytest.mark.asyncio
async def test_unknown_command_shows_warning(connected_app):
    """Test that unknown commands show a warning."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        log = app.query_one("#log")
        # Type unknown command
        await pilot.click("#cmd-input")
        await pilot.press("x", "y", "z", "z", "y")
        await pilot.press("enter")
        await pilot.pause()
        # Log should contain warning about unknown command
        log_content = str(log.lines)
        assert "Unknown" in log_content or "unknown" in log_content.lower()


@pytest.mark.asyncio
async def test_slash_quit_exits_app():
    """Test that '/quit' command exits the app."""
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Type /quit command
            await pilot.click("#cmd-input")
            await pilot.press("/", "q", "u", "i", "t")
            await pilot.press("enter")
        # App should have exited
        assert app._exit
