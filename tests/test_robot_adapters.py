"""Unit tests for model-specific RobotAdapter subclasses and the make_adapter factory."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from asher.robot_adapters import LR3Adapter, LR4Adapter, LR5Adapter, make_adapter


@pytest.fixture
def robot():
    r = MagicMock()
    r.set_panel_lockout = AsyncMock(return_value=True)
    r.set_sleep_mode = AsyncMock(return_value=True)
    r.set_night_light = AsyncMock(return_value=True)
    r.set_night_light_mode = AsyncMock(return_value=True)
    r.set_night_light_brightness = AsyncMock(return_value=True)
    # LR5-only setters (only invoked via LR5Adapter)
    r.set_privacy_mode = AsyncMock(return_value=True)
    r.set_volume = AsyncMock(return_value=True)
    r.set_camera_audio = AsyncMock(return_value=True)
    r.reset_waste_drawer = AsyncMock(return_value=True)
    return r


# ── make_adapter factory ──────────────────────────────────────────────────────
# make_adapter uses type(robot).__name__, so we need real class instances —
# MagicMock.__class__ assignment doesn't affect type().


def test_make_adapter_returns_lr3_for_lr3():
    class LitterRobot3:  # noqa: N801
        pass

    assert isinstance(make_adapter(LitterRobot3()), LR3Adapter)  # type: ignore[arg-type]


def test_make_adapter_returns_lr4_for_lr4():
    class LitterRobot4:  # noqa: N801
        pass

    assert isinstance(make_adapter(LitterRobot4()), LR4Adapter)  # type: ignore[arg-type]


def test_make_adapter_returns_lr5_for_lr5():
    class LitterRobot5:  # noqa: N801
        pass

    assert isinstance(make_adapter(LitterRobot5()), LR5Adapter)  # type: ignore[arg-type]


def test_make_adapter_unknown_defaults_to_lr4():
    class SomeOtherRobot:
        pass

    assert isinstance(make_adapter(SomeOtherRobot()), LR4Adapter)  # type: ignore[arg-type]


# ── base: set_panel_lockout (shared by all models) ───────────────────────────


@pytest.mark.asyncio
async def test_panel_lock_enable(robot):
    ok, msg = await LR3Adapter(robot).set_panel_lockout(True)
    assert ok
    assert "locked" in msg.lower()
    robot.set_panel_lockout.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_panel_lock_disable(robot):
    ok, msg = await LR3Adapter(robot).set_panel_lockout(False)
    assert ok
    assert "unlocked" in msg.lower()
    robot.set_panel_lockout.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_panel_lock_rejected(robot):
    robot.set_panel_lockout.return_value = False
    ok, _ = await LR3Adapter(robot).set_panel_lockout(True)
    assert not ok


@pytest.mark.asyncio
async def test_panel_lock_exception(robot):
    robot.set_panel_lockout.side_effect = RuntimeError("cloud error")
    ok, msg = await LR3Adapter(robot).set_panel_lockout(True)
    assert not ok
    assert "cloud error" in msg


# ── LR3Adapter ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lr3_sleep_enable(robot):
    ok, _ = await LR3Adapter(robot).set_sleep(True)
    assert ok
    robot.set_sleep_mode.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_lr3_sleep_disable(robot):
    ok, _ = await LR3Adapter(robot).set_sleep(False)
    assert ok
    robot.set_sleep_mode.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_lr3_sleep_rejected(robot):
    robot.set_sleep_mode.return_value = False
    ok, _ = await LR3Adapter(robot).set_sleep(True)
    assert not ok


@pytest.mark.asyncio
async def test_lr3_sleep_exception(robot):
    robot.set_sleep_mode.side_effect = Exception("timeout")
    ok, msg = await LR3Adapter(robot).set_sleep(True)
    assert not ok
    assert "timeout" in msg


@pytest.mark.asyncio
async def test_lr3_night_light_on(robot):
    ok, _ = await LR3Adapter(robot).set_night_light("on")
    assert ok
    robot.set_night_light.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_lr3_night_light_off(robot):
    ok, _ = await LR3Adapter(robot).set_night_light("off")
    assert ok
    robot.set_night_light.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_lr3_night_light_auto_unsupported(robot):
    ok, msg = await LR3Adapter(robot).set_night_light("auto")
    assert not ok
    assert "LR3" in msg


@pytest.mark.asyncio
async def test_lr3_night_light_rejected(robot):
    robot.set_night_light.return_value = False
    ok, _ = await LR3Adapter(robot).set_night_light("on")
    assert not ok


@pytest.mark.asyncio
async def test_lr3_night_light_exception(robot):
    robot.set_night_light.side_effect = Exception("api down")
    ok, msg = await LR3Adapter(robot).set_night_light("on")
    assert not ok
    assert "api down" in msg


@pytest.mark.asyncio
async def test_lr3_night_light_brightness_unsupported(robot):
    ok, msg = await LR3Adapter(robot).set_night_light_brightness(50)
    assert not ok
    assert "LR3" in msg


# ── LR4Adapter ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lr4_sleep_unsupported(robot):
    ok, msg = await LR4Adapter(robot).set_sleep(True)
    assert not ok
    assert "LR4" in msg


@pytest.mark.asyncio
async def test_lr4_wake_unsupported(robot):
    ok, msg = await LR4Adapter(robot).set_sleep(False)
    assert not ok
    assert "LR4" in msg


@pytest.mark.asyncio
async def test_lr4_night_light_on(robot):
    from pylitterbot.enums import NightLightMode

    ok, _ = await LR4Adapter(robot).set_night_light("on")
    assert ok
    robot.set_night_light_mode.assert_called_once_with(NightLightMode.ON)


@pytest.mark.asyncio
async def test_lr4_night_light_off(robot):
    from pylitterbot.enums import NightLightMode

    ok, _ = await LR4Adapter(robot).set_night_light("off")
    assert ok
    robot.set_night_light_mode.assert_called_once_with(NightLightMode.OFF)


@pytest.mark.asyncio
async def test_lr4_night_light_auto(robot):
    from pylitterbot.enums import NightLightMode

    ok, _ = await LR4Adapter(robot).set_night_light("auto")
    assert ok
    robot.set_night_light_mode.assert_called_once_with(NightLightMode.AUTO)


@pytest.mark.asyncio
async def test_lr4_night_light_invalid_mode(robot):
    ok, msg = await LR4Adapter(robot).set_night_light("disco")
    assert not ok
    assert "disco" in msg


@pytest.mark.asyncio
async def test_lr4_night_light_rejected(robot):
    robot.set_night_light_mode.return_value = False
    ok, _ = await LR4Adapter(robot).set_night_light("on")
    assert not ok


@pytest.mark.asyncio
async def test_lr4_night_light_exception(robot):
    robot.set_night_light_mode.side_effect = Exception("timeout")
    ok, msg = await LR4Adapter(robot).set_night_light("auto")
    assert not ok
    assert "timeout" in msg


@pytest.mark.asyncio
async def test_lr4_brightness_25(robot):
    ok, _ = await LR4Adapter(robot).set_night_light_brightness(25)
    assert ok
    robot.set_night_light_brightness.assert_called_once_with(25)


@pytest.mark.asyncio
async def test_lr4_brightness_50(robot):
    ok, _ = await LR4Adapter(robot).set_night_light_brightness(50)
    assert ok
    robot.set_night_light_brightness.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_lr4_brightness_100(robot):
    ok, _ = await LR4Adapter(robot).set_night_light_brightness(100)
    assert ok
    robot.set_night_light_brightness.assert_called_once_with(100)


@pytest.mark.asyncio
async def test_lr4_brightness_invalid(robot):
    ok, msg = await LR4Adapter(robot).set_night_light_brightness(75)
    assert not ok
    assert "75" in msg


@pytest.mark.asyncio
async def test_lr4_brightness_rejected(robot):
    robot.set_night_light_brightness.return_value = False
    ok, _ = await LR4Adapter(robot).set_night_light_brightness(50)
    assert not ok


@pytest.mark.asyncio
async def test_lr4_brightness_exception(robot):
    robot.set_night_light_brightness.side_effect = Exception("bad request")
    ok, msg = await LR4Adapter(robot).set_night_light_brightness(100)
    assert not ok
    assert "bad request" in msg


# ── LR5Adapter ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lr5_sleep_enable(robot):
    ok, _ = await LR5Adapter(robot).set_sleep(True)
    assert ok
    robot.set_sleep_mode.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_lr5_sleep_disable(robot):
    ok, _ = await LR5Adapter(robot).set_sleep(False)
    assert ok
    robot.set_sleep_mode.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_lr5_sleep_rejected(robot):
    robot.set_sleep_mode.return_value = False
    ok, _ = await LR5Adapter(robot).set_sleep(True)
    assert not ok


@pytest.mark.asyncio
async def test_lr5_sleep_exception(robot):
    robot.set_sleep_mode.side_effect = Exception("timeout")
    ok, msg = await LR5Adapter(robot).set_sleep(True)
    assert not ok
    assert "timeout" in msg


@pytest.mark.asyncio
async def test_lr5_night_light_on(robot):
    from pylitterbot.enums import NightLightMode

    ok, _ = await LR5Adapter(robot).set_night_light("on")
    assert ok
    robot.set_night_light_mode.assert_called_once_with(NightLightMode.ON)


@pytest.mark.asyncio
async def test_lr5_night_light_off(robot):
    from pylitterbot.enums import NightLightMode

    ok, _ = await LR5Adapter(robot).set_night_light("off")
    assert ok
    robot.set_night_light_mode.assert_called_once_with(NightLightMode.OFF)


@pytest.mark.asyncio
async def test_lr5_night_light_auto(robot):
    from pylitterbot.enums import NightLightMode

    ok, _ = await LR5Adapter(robot).set_night_light("auto")
    assert ok
    robot.set_night_light_mode.assert_called_once_with(NightLightMode.AUTO)


@pytest.mark.asyncio
async def test_lr5_night_light_invalid_mode(robot):
    ok, msg = await LR5Adapter(robot).set_night_light("strobe")
    assert not ok
    assert "strobe" in msg


@pytest.mark.asyncio
async def test_lr5_night_light_rejected(robot):
    robot.set_night_light_mode.return_value = False
    ok, _ = await LR5Adapter(robot).set_night_light("on")
    assert not ok


@pytest.mark.asyncio
async def test_lr5_brightness_zero(robot):
    ok, _ = await LR5Adapter(robot).set_night_light_brightness(0)
    assert ok
    robot.set_night_light_brightness.assert_called_once_with(0)


@pytest.mark.asyncio
async def test_lr5_brightness_midrange(robot):
    ok, _ = await LR5Adapter(robot).set_night_light_brightness(75)
    assert ok
    robot.set_night_light_brightness.assert_called_once_with(75)


@pytest.mark.asyncio
async def test_lr5_brightness_100(robot):
    ok, _ = await LR5Adapter(robot).set_night_light_brightness(100)
    assert ok


@pytest.mark.asyncio
async def test_lr5_brightness_above_100(robot):
    ok, msg = await LR5Adapter(robot).set_night_light_brightness(101)
    assert not ok
    assert "101" in msg


@pytest.mark.asyncio
async def test_lr5_brightness_negative(robot):
    ok, msg = await LR5Adapter(robot).set_night_light_brightness(-1)
    assert not ok
    assert "-1" in msg


@pytest.mark.asyncio
async def test_lr5_brightness_rejected(robot):
    robot.set_night_light_brightness.return_value = False
    ok, _ = await LR5Adapter(robot).set_night_light_brightness(50)
    assert not ok


@pytest.mark.asyncio
async def test_lr5_brightness_exception(robot):
    robot.set_night_light_brightness.side_effect = Exception("api error")
    ok, msg = await LR5Adapter(robot).set_night_light_brightness(50)
    assert not ok
    assert "api error" in msg


# ── LR5-only capabilities: base class "not supported" ─────────────────────────
# LR3/LR4 adapters should refuse these gracefully rather than calling the robot.


@pytest.mark.parametrize("adapter_cls", [LR3Adapter, LR4Adapter])
@pytest.mark.asyncio
async def test_base_privacy_not_supported(robot, adapter_cls):
    ok, msg = await adapter_cls(robot).set_privacy_mode(True)
    assert not ok
    assert "LR5" in msg
    robot.set_privacy_mode.assert_not_called()


@pytest.mark.parametrize("adapter_cls", [LR3Adapter, LR4Adapter])
@pytest.mark.asyncio
async def test_base_volume_not_supported(robot, adapter_cls):
    ok, msg = await adapter_cls(robot).set_volume(50)
    assert not ok
    assert "LR5" in msg
    robot.set_volume.assert_not_called()


@pytest.mark.parametrize("adapter_cls", [LR3Adapter, LR4Adapter])
@pytest.mark.asyncio
async def test_base_camera_audio_not_supported(robot, adapter_cls):
    ok, msg = await adapter_cls(robot).set_camera_audio(True)
    assert not ok
    assert "LR5" in msg
    robot.set_camera_audio.assert_not_called()


@pytest.mark.parametrize("adapter_cls", [LR3Adapter, LR4Adapter])
@pytest.mark.asyncio
async def test_base_drawer_reset_not_supported(robot, adapter_cls):
    ok, msg = await adapter_cls(robot).reset_waste_drawer()
    assert not ok
    assert "LR5" in msg
    robot.reset_waste_drawer.assert_not_called()


# ── LR5Adapter: privacy mode ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lr5_privacy_on(robot):
    ok, msg = await LR5Adapter(robot).set_privacy_mode(True)
    assert ok
    assert "on" in msg
    robot.set_privacy_mode.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_lr5_privacy_off(robot):
    ok, msg = await LR5Adapter(robot).set_privacy_mode(False)
    assert ok
    assert "off" in msg
    robot.set_privacy_mode.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_lr5_privacy_rejected(robot):
    robot.set_privacy_mode.return_value = False
    ok, _ = await LR5Adapter(robot).set_privacy_mode(True)
    assert not ok


@pytest.mark.asyncio
async def test_lr5_privacy_exception(robot):
    robot.set_privacy_mode.side_effect = Exception("timeout")
    ok, msg = await LR5Adapter(robot).set_privacy_mode(True)
    assert not ok
    assert "timeout" in msg


# ── LR5Adapter: volume ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lr5_volume_valid(robot):
    ok, msg = await LR5Adapter(robot).set_volume(50)
    assert ok
    assert "50" in msg
    robot.set_volume.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_lr5_volume_zero(robot):
    ok, _ = await LR5Adapter(robot).set_volume(0)
    assert ok
    robot.set_volume.assert_called_once_with(0)


@pytest.mark.asyncio
async def test_lr5_volume_above_100(robot):
    ok, msg = await LR5Adapter(robot).set_volume(101)
    assert not ok
    assert "101" in msg
    robot.set_volume.assert_not_called()


@pytest.mark.asyncio
async def test_lr5_volume_negative(robot):
    ok, msg = await LR5Adapter(robot).set_volume(-1)
    assert not ok
    assert "-1" in msg
    robot.set_volume.assert_not_called()


@pytest.mark.asyncio
async def test_lr5_volume_rejected(robot):
    robot.set_volume.return_value = False
    ok, _ = await LR5Adapter(robot).set_volume(50)
    assert not ok


@pytest.mark.asyncio
async def test_lr5_volume_exception(robot):
    robot.set_volume.side_effect = Exception("api error")
    ok, msg = await LR5Adapter(robot).set_volume(50)
    assert not ok
    assert "api error" in msg


# ── LR5Adapter: camera audio ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lr5_camera_audio_on(robot):
    ok, msg = await LR5Adapter(robot).set_camera_audio(True)
    assert ok
    assert "on" in msg
    robot.set_camera_audio.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_lr5_camera_audio_off(robot):
    ok, msg = await LR5Adapter(robot).set_camera_audio(False)
    assert ok
    assert "off" in msg
    robot.set_camera_audio.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_lr5_camera_audio_rejected(robot):
    robot.set_camera_audio.return_value = False
    ok, _ = await LR5Adapter(robot).set_camera_audio(True)
    assert not ok


@pytest.mark.asyncio
async def test_lr5_camera_audio_exception(robot):
    robot.set_camera_audio.side_effect = Exception("boom")
    ok, msg = await LR5Adapter(robot).set_camera_audio(True)
    assert not ok
    assert "boom" in msg


# ── LR5Adapter: drawer reset ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lr5_drawer_reset(robot):
    ok, msg = await LR5Adapter(robot).reset_waste_drawer()
    assert ok
    assert "reset" in msg.lower()
    robot.reset_waste_drawer.assert_called_once_with()


@pytest.mark.asyncio
async def test_lr5_drawer_reset_rejected(robot):
    robot.reset_waste_drawer.return_value = False
    ok, _ = await LR5Adapter(robot).reset_waste_drawer()
    assert not ok


@pytest.mark.asyncio
async def test_lr5_drawer_reset_exception(robot):
    robot.reset_waste_drawer.side_effect = Exception("nope")
    ok, msg = await LR5Adapter(robot).reset_waste_drawer()
    assert not ok
    assert "nope" in msg
