"""Pilot tests for the LR5-only commands: privacy, volume, camera-audio, drawer-reset (§4)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from asher.app import AsherApp
from asher.robot_adapters import LR4Adapter, LR5Adapter


@pytest.fixture
def lr5_app():
    """A connected app whose active robot is an LR5 (LR5Adapter)."""
    robot = MagicMock()
    robot.name = "EvoBot"
    robot.is_online = True
    robot.waste_drawer_level = 50.0
    robot.status = MagicMock()
    robot.status.value = "Ready"
    robot.sleep_mode_enabled = False
    robot.panel_lock_enabled = False
    robot.night_light_mode_enabled = False
    robot.serial = "LR5C001"
    robot.last_seen = datetime.now(timezone.utc)
    robot.pet_weight = 9.1
    robot.sound_volume = 50
    robot.refresh = AsyncMock()
    robot.get_activity_history = AsyncMock(return_value=[])
    robot.set_privacy_mode = AsyncMock(return_value=True)
    robot.set_volume = AsyncMock(return_value=True)
    robot.set_camera_audio = AsyncMock(return_value=True)
    robot.reset_waste_drawer = AsyncMock(return_value=True)

    app = AsherApp()
    app._robot = robot
    app._adapter = LR5Adapter(robot)
    app._account = MagicMock()
    app._account.disconnect = AsyncMock()
    app._pets = []
    app._connect_worker = lambda **kwargs: None  # type: ignore[method-assign]
    return app


@pytest.fixture
def lr4_app(lr5_app):
    """Same robot, but fronted by an LR4Adapter — commands should report 'not supported'."""
    lr5_app._adapter = LR4Adapter(lr5_app._robot)
    return lr5_app


def _log_text(app: AsherApp) -> str:
    return str(app.query_one("#log").lines)


async def _type(pilot, text: str) -> None:
    for ch in text:
        await pilot.press(ch)
    await pilot.press("enter")


# ── privacy ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_privacy_on_lr5(lr5_app):
    async with lr5_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "privacy on")
        await pilot.pause()
        await pilot.pause()

    lr5_app._robot.set_privacy_mode.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_privacy_off_lr5(lr5_app):
    async with lr5_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "privacy off")
        await pilot.pause()
        await pilot.pause()

    lr5_app._robot.set_privacy_mode.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_privacy_invalid_arg_shows_usage(lr5_app):
    async with lr5_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "privacy maybe")
        await pilot.pause()

        log = _log_text(lr5_app)

    lr5_app._robot.set_privacy_mode.assert_not_called()
    assert "Usage" in log


@pytest.mark.asyncio
async def test_privacy_not_supported_on_lr4(lr4_app):
    async with lr4_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "privacy on")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(lr4_app)

    lr4_app._robot.set_privacy_mode.assert_not_called()
    assert "LR5" in log


# ── volume ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_volume_set_lr5(lr5_app):
    async with lr5_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "volume 75")
        await pilot.pause()
        await pilot.pause()

    lr5_app._robot.set_volume.assert_called_once_with(75)


@pytest.mark.asyncio
async def test_volume_no_arg_shows_usage_and_current(lr5_app):
    async with lr5_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "volume")
        await pilot.pause()

        log = _log_text(lr5_app)

    lr5_app._robot.set_volume.assert_not_called()
    assert "Usage" in log
    assert "50" in log  # current volume from the fixture


@pytest.mark.asyncio
async def test_volume_out_of_range_lr5(lr5_app):
    async with lr5_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "volume 150")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(lr5_app)

    # Adapter rejects before hitting the robot.
    lr5_app._robot.set_volume.assert_not_called()
    assert "150" in log


@pytest.mark.asyncio
async def test_volume_not_supported_on_lr4(lr4_app):
    async with lr4_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "volume 50")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(lr4_app)

    lr4_app._robot.set_volume.assert_not_called()
    assert "LR5" in log


# ── camera-audio ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_camera_audio_on_lr5(lr5_app):
    async with lr5_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "camera-audio on")
        await pilot.pause()
        await pilot.pause()

    lr5_app._robot.set_camera_audio.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_camera_audio_off_lr5(lr5_app):
    async with lr5_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "camera-audio off")
        await pilot.pause()
        await pilot.pause()

    lr5_app._robot.set_camera_audio.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_camera_audio_invalid_arg_shows_usage(lr5_app):
    async with lr5_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "camera-audio loud")
        await pilot.pause()

        log = _log_text(lr5_app)

    lr5_app._robot.set_camera_audio.assert_not_called()
    assert "Usage" in log


@pytest.mark.asyncio
async def test_camera_audio_not_supported_on_lr4(lr4_app):
    async with lr4_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "camera-audio on")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(lr4_app)

    lr4_app._robot.set_camera_audio.assert_not_called()
    assert "LR5" in log


# ── drawer-reset ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_drawer_reset_lr5(lr5_app):
    async with lr5_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "drawer-reset")
        await pilot.pause()
        await pilot.pause()

    lr5_app._robot.reset_waste_drawer.assert_called_once_with()


@pytest.mark.asyncio
async def test_drawer_reset_not_supported_on_lr4(lr4_app):
    async with lr4_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "drawer-reset")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(lr4_app)

    lr4_app._robot.reset_waste_drawer.assert_not_called()
    assert "LR5" in log
