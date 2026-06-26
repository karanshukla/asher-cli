"""Pilot tests for new slash commands and export command."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from asher.app import AsherApp
from asher.robot_adapters import LR3Adapter


@pytest.fixture
def connected_app():
    robot = MagicMock()
    robot.name = "TestBot"
    robot.is_online = True
    robot.waste_drawer_level = 50.0
    robot.status = MagicMock()
    robot.status.value = "Ready"
    robot.sleep_mode_enabled = False
    robot.panel_lock_enabled = False
    robot.night_light_mode_enabled = False
    robot.serial = "LR12345"
    robot.last_seen = datetime.now(timezone.utc)
    robot.pet_weight = 10.5
    robot.refresh = AsyncMock()
    robot.get_activity_history = AsyncMock(return_value=[])

    app = AsherApp()
    app._robot = robot
    app._adapter = LR3Adapter(robot)
    app._account = MagicMock()
    app._account.disconnect = AsyncMock()
    app._pets = []
    app._connect_worker = lambda **kwargs: None  # type: ignore[method-assign]
    return app


@pytest.fixture
def app_with_pets(connected_app):
    pet0 = MagicMock()
    pet0.name = "Asher"
    pet0.id = "pet-001"
    pet1 = MagicMock()
    pet1.name = "Luna"
    pet1.id = "pet-002"
    connected_app._pets = [pet0, pet1]
    return connected_app


# ── /cat ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cat_off_hides_panel(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        cat_panel = connected_app.query_one("#cat-panel")
        assert cat_panel.display is True

        await pilot.click("#cmd-input")
        await pilot.press("/", "c", "a", "t", " ", "o", "f", "f")
        await pilot.press("enter")
        await pilot.pause()

        assert cat_panel.display is False
        assert connected_app._cat_panel_visible is False


@pytest.mark.asyncio
async def test_cat_on_shows_panel(connected_app):
    connected_app._cat_panel_visible = False
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        cat_panel = connected_app.query_one("#cat-panel")
        cat_panel.display = False

        await pilot.click("#cmd-input")
        await pilot.press("/", "c", "a", "t", " ", "o", "n")
        await pilot.press("enter")
        await pilot.pause()

        assert cat_panel.display is True
        assert connected_app._cat_panel_visible is True


@pytest.mark.asyncio
async def test_cat_color_sets_override(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        # /cat color #ff79c6
        for ch in "/cat color #ff79c6":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert connected_app._cat_color == "#ff79c6"


@pytest.mark.asyncio
async def test_cat_reset_clears_color(connected_app):
    connected_app._cat_color = "#ff0000"
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/cat reset":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert connected_app._cat_color is None


@pytest.mark.asyncio
async def test_cat_no_args_shows_usage(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/cat":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        log_content = str(connected_app.query_one("#log").lines)
        assert "Usage" in log_content


# ── /refresh ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_sets_interval(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/refresh 60":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert connected_app._poll_interval == 60
        assert connected_app._poll_timer is not None


@pytest.mark.asyncio
async def test_refresh_off_stops_timer(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/refresh off":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert connected_app._poll_interval == 0
        assert connected_app._poll_timer is None


@pytest.mark.asyncio
async def test_refresh_no_args_shows_interval(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/refresh":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        log_content = str(connected_app.query_one("#log").lines)
        assert "300" in log_content


# ── /config ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_config_shows_robot_name(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/config":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        log_content = str(connected_app.query_one("#log").lines)
        assert "TestBot" in log_content


@pytest.mark.asyncio
async def test_config_shows_refresh_rate(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/config":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        log_content = str(connected_app.query_one("#log").lines)
        assert "300" in log_content


# ── /pet ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pets_command_lists_all_pets(app_with_pets):
    async with app_with_pets.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/pets":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        log_content = str(app_with_pets.query_one("#log").lines)
        assert "Asher" in log_content
        assert "Luna" in log_content


@pytest.mark.asyncio
async def test_pet_no_args_shows_usage(app_with_pets):
    async with app_with_pets.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/pet":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        log_content = str(app_with_pets.query_one("#log").lines)
        assert "Usage" in log_content


@pytest.mark.asyncio
async def test_pet_switch_by_index(app_with_pets):
    async with app_with_pets.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/pet 1":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert app_with_pets._active_pet_idx == 1


@pytest.mark.asyncio
async def test_pet_switch_by_name(app_with_pets):
    async with app_with_pets.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/pet luna":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert app_with_pets._active_pet_idx == 1


@pytest.mark.asyncio
async def test_pet_invalid_index_shows_warning(app_with_pets):
    async with app_with_pets.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/pet 99":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        log_content = str(app_with_pets.query_one("#log").lines)
        assert "99" in log_content


@pytest.mark.asyncio
async def test_pet_no_pets_shows_warning(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "/pet":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        log_content = str(connected_app.query_one("#log").lines)
        assert "No pets" in log_content


# ── export ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_calls_get_activity_history(connected_app, tmp_path):
    connected_app._robot.get_activity_history = AsyncMock(return_value=[])
    with patch("asher.commands._open_folder"), patch("pathlib.Path.home", return_value=tmp_path):
        async with connected_app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#cmd-input")
            for ch in "export":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()

        connected_app._robot.get_activity_history.assert_called_once_with(limit=500)


@pytest.mark.asyncio
async def test_export_7_days(connected_app, tmp_path):
    connected_app._robot.get_activity_history = AsyncMock(return_value=[])
    with patch("asher.commands._open_folder"), patch("pathlib.Path.home", return_value=tmp_path):
        async with connected_app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#cmd-input")
            for ch in "export 7":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()

        connected_app._robot.get_activity_history.assert_called_once_with(limit=500)


@pytest.mark.asyncio
async def test_export_writes_csv(connected_app, tmp_path):
    act = MagicMock()
    act.timestamp = datetime(2026, 6, 20, 14, 32, 0, tzinfo=timezone.utc)
    act.action = MagicMock()
    act.action.text = "Clean Cycle Complete"
    act.weight = 9.1
    act.pet_id = None

    connected_app._robot.get_activity_history = AsyncMock(return_value=[act])
    connected_app._robot.serial = "LR4C001"
    connected_app._robot.name = "Idiot Box"

    downloads = tmp_path / "Downloads"
    downloads.mkdir()

    with patch("asher.commands._open_folder"), patch("pathlib.Path.home", return_value=tmp_path):
        async with connected_app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#cmd-input")
            for ch in "export":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()

    csv_files = list(downloads.glob("asher-LR4C001-*.csv"))
    assert len(csv_files) == 1
    content = csv_files[0].read_text()
    assert "timestamp" in content
    assert "Clean cycle complete" in content
    assert "9.1" in content


@pytest.mark.asyncio
async def test_export_invalid_period_shows_warning(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        for ch in "export notaday":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        log_content = str(connected_app.query_one("#log").lines)
        assert "notaday" in log_content


@pytest.mark.asyncio
async def test_export_without_robot_shows_error():
    with (
        patch("asher.connection._keyring_available", return_value=False),
        patch("os.getenv", return_value=""),
    ):
        app = AsherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#cmd-input")
            for ch in "export":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            log_content = str(app.query_one("#log").lines)
            assert "Not connected" in log_content or "connected" in log_content.lower()
