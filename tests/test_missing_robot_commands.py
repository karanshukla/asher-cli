"""Pilot tests for the wait-time, power, rename, and insight robot commands (§3)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from asher.app import AsherApp
from asher.robot_adapters import LR3Adapter


def _make_insight() -> MagicMock:
    """Build a fake Insight with the same dataclass shape pylitterbot exposes."""
    insight = MagicMock()
    insight.total_cycles = 42
    insight.average_cycles = 1.4
    insight.cycle_history = [
        (date(2026, 7, 18), 2),
        (date(2026, 7, 19), 1),
        (date(2026, 7, 20), 3),
    ]
    insight.total_days = 3
    return insight


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
    robot.power_status = "on"
    robot.clean_cycle_wait_time_minutes = 7
    robot.firmware = "ESP: 1.1.50 / PIC: 1.0.11"
    robot.VALID_WAIT_TIMES = [3, 7, 15, 25, 30]
    robot.refresh = AsyncMock()
    robot.get_activity_history = AsyncMock(return_value=[])
    robot.set_wait_time = AsyncMock(return_value=True)
    robot.set_power_status = AsyncMock(return_value=True)
    robot.set_name = AsyncMock(return_value=True)
    robot.get_insight = AsyncMock(return_value=_make_insight())

    app = AsherApp()
    app._robot = robot
    app._adapter = LR3Adapter(robot)
    app._account = MagicMock()
    app._account.disconnect = AsyncMock()
    app._pets = []
    app._connect_worker = lambda **kwargs: None  # type: ignore[method-assign]
    return app


def _log_text(app: AsherApp) -> str:
    return str(app.query_one("#log").lines)


async def _type(pilot, text: str) -> None:
    for ch in text:
        await pilot.press(ch)
    await pilot.press("enter")


# ── wait-time ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wait_time_sets_value(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "wait-time 15")
        await pilot.pause()
        await pilot.pause()

    connected_app._robot.set_wait_time.assert_called_once_with(15)


@pytest.mark.asyncio
async def test_wait_time_rejects_invalid_value(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "wait-time 99")
        await pilot.pause()

        log = _log_text(connected_app)

    connected_app._robot.set_wait_time.assert_not_called()
    assert "99" in log


@pytest.mark.asyncio
async def test_wait_time_no_arg_shows_usage_and_current(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "wait-time")
        await pilot.pause()

        log = _log_text(connected_app)

    connected_app._robot.set_wait_time.assert_not_called()
    assert "Usage" in log
    assert "7" in log  # current wait time from the fixture


@pytest.mark.asyncio
async def test_wait_time_handles_rejection(connected_app):
    connected_app._robot.set_wait_time.return_value = False
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "wait-time 7")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(connected_app)

    assert "rejected" in log.lower()


# ── power ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_power_on(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "power on")
        await pilot.pause()
        await pilot.pause()

    connected_app._robot.set_power_status.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_power_off(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "power off")
        await pilot.pause()
        await pilot.pause()

    connected_app._robot.set_power_status.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_power_invalid_shows_usage(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "power standby")
        await pilot.pause()

        log = _log_text(connected_app)

    connected_app._robot.set_power_status.assert_not_called()
    assert "Usage" in log


# ── rename ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rename_single_word(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "rename Fluffy")
        await pilot.pause()
        await pilot.pause()

    connected_app._robot.set_name.assert_called_once_with("Fluffy")


@pytest.mark.asyncio
async def test_rename_multi_word_joins_args(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "rename Idiot Box 2")
        await pilot.pause()
        await pilot.pause()

    connected_app._robot.set_name.assert_called_once_with("Idiot Box 2")


@pytest.mark.asyncio
async def test_rename_no_arg_shows_usage(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "rename")
        await pilot.pause()

        log = _log_text(connected_app)

    connected_app._robot.set_name.assert_not_called()
    assert "Usage" in log
    assert "TestBot" in log  # shows current name in usage line


# ── insight ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insight_default_30_days(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "insight")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(connected_app)

    connected_app._robot.get_insight.assert_called_once_with(days=30)
    assert "42" in log  # total cycles
    assert "1.4" in log  # average per day


@pytest.mark.asyncio
async def test_insight_explicit_days(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "insight 7")
        await pilot.pause()
        await pilot.pause()

    connected_app._robot.get_insight.assert_called_once_with(days=7)


@pytest.mark.asyncio
async def test_insight_month_alias(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "insight month")
        await pilot.pause()
        await pilot.pause()

    connected_app._robot.get_insight.assert_called_once_with(days=30)


@pytest.mark.asyncio
async def test_insight_invalid_period_shows_warning(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "insight notdays")
        await pilot.pause()

        log = _log_text(connected_app)

    connected_app._robot.get_insight.assert_not_called()
    assert "notdays" in log


@pytest.mark.asyncio
async def test_insight_shows_peak_day(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "insight")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(connected_app)

    # Peak day in the fixture is 3 cycles on 2026-07-20.
    assert "2026-07-20" in log
    assert "3" in log


# ── status / info split (§3) ──────────────────────────────────────────────────
#
# `status` is the trimmed at-a-glance view; `info` is the full property dump.


@pytest.mark.asyncio
async def test_status_is_at_a_glance_view(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "status")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(connected_app)

    # status refreshes the robot and refreshes the status bar
    connected_app._robot.refresh.assert_called_once()
    # at-a-glance fields present
    assert "Online" in log
    assert "Drawer" in log and "50%" in log
    assert "Cat weight" in log and "10.5 lb" in log
    assert "Last seen" in log
    # status is the trimmed view — full-detail fields belong to `info`, not here
    assert "Serial" not in log
    assert "Firmware" not in log


@pytest.mark.asyncio
async def test_status_renders_readable_status_not_enum_repr(connected_app):
    """LitterBoxStatus is a plain Enum — str() yields 'LitterBoxStatus.READY'.
    The status command must render the human-readable .text ('Ready') instead."""
    from pylitterbot.enums import LitterBoxStatus

    connected_app._robot.status = LitterBoxStatus.READY
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "status")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(connected_app)

    assert "Ready" in log
    assert "LitterBoxStatus" not in log


@pytest.mark.asyncio
async def test_info_shows_full_property_dump(connected_app):
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "info")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(connected_app)

    connected_app._robot.refresh.assert_called_once()
    assert "Name" in log and "TestBot" in log
    assert "Serial" in log and "LR12345" in log
    assert "Firmware" in log and "1.1.50" in log
    assert "Wait time" in log and "7 min" in log
    assert "Panel locked" in log and "no" in log
    assert "Online" in log


@pytest.mark.asyncio
async def test_info_handles_missing_optional_props():
    """LR3 lacks firmware / clean_cycle_wait_time_minutes — info must degrade gracefully."""
    robot = MagicMock(
        spec=[
            "name",
            "serial",
            "is_online",
            "status",
            "waste_drawer_level",
            "sleep_mode_enabled",
            "panel_lock_enabled",
            "night_light_mode_enabled",
            "last_seen",
            "refresh",
        ]
    )
    robot.name = "OldBox"
    robot.serial = "LR3-001"
    robot.is_online = True
    robot.status = "Ready"
    robot.waste_drawer_level = 40.0
    robot.sleep_mode_enabled = False
    robot.panel_lock_enabled = False
    robot.night_light_mode_enabled = False
    robot.last_seen = datetime.now(timezone.utc)
    robot.refresh = AsyncMock()

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
        await _type(pilot, "info")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(app)

    # Absent optional props render as the em-dash placeholder, not a crash.
    assert "Firmware" in log and "—" in log
    assert "Wait time" in log and "—" in log
    assert "Name" in log and "OldBox" in log


# ── sleep-schedule (§8) — read-only viewer ─────────────────────────────────────


def _make_schedule(enabled_days: list[int] | None = None, disabled_days: list[int] | None = None):
    """Build a fake SleepSchedule-like object from the real pylitterbot dataclasses.

    `enabled_days`/`disabled_days` are weekday indices (Mon=0..Sun=6). The
    command reads `.days`, `.is_enabled`, and `.get_window()` defensively.
    """
    from datetime import time

    from pylitterbot.sleep_schedule import DayOfWeek, SleepSchedule, SleepScheduleDay

    days = []
    enabled_days = enabled_days or []
    disabled_days = disabled_days or []
    # Map Mon=0..Sun=6 (Python weekday) to DayOfWeek Sun=0..Sat=6.
    wd_to_dow = {
        0: DayOfWeek.MONDAY,
        1: DayOfWeek.TUESDAY,
        2: DayOfWeek.WEDNESDAY,
        3: DayOfWeek.THURSDAY,
        4: DayOfWeek.FRIDAY,
        5: DayOfWeek.SATURDAY,
        6: DayOfWeek.SUNDAY,
    }
    for wd in enabled_days:
        days.append(
            SleepScheduleDay(
                day=wd_to_dow[wd], sleep_time=time(22, 0), wake_time=time(7, 0), is_enabled=True
            )
        )
    for wd in disabled_days:
        days.append(
            SleepScheduleDay(
                day=wd_to_dow[wd], sleep_time=time(22, 0), wake_time=time(7, 0), is_enabled=False
            )
        )
    return SleepSchedule(days=days)


@pytest.mark.asyncio
async def test_sleep_schedule_shows_enabled_windows(connected_app):
    connected_app._robot.sleep_schedule = _make_schedule(
        enabled_days=[0, 1, 2],
        disabled_days=[3, 4],  # Mon-Wed on, Thu-Fri off
    )
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "sleep-schedule")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(connected_app)

    assert "22:00" in log
    assert "07:00" in log
    assert "Mon" in log and "Tue" in log and "Wed" in log
    # disabled days render "off"
    assert "off" in log


@pytest.mark.asyncio
async def test_sleep_schedule_handles_none(connected_app):
    """_sleep_schedule is None when no schedule is configured — must warn, not crash."""
    connected_app._robot.sleep_schedule = None
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "sleep-schedule")
        await pilot.pause()

        log = _log_text(connected_app)

    assert "No sleep schedule" in log or "always awake" in log.lower()


@pytest.mark.asyncio
async def test_sleep_schedule_reports_disabled_when_no_days_enabled(connected_app):
    connected_app._robot.sleep_schedule = _make_schedule(disabled_days=[0, 1])
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "sleep-schedule")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(connected_app)

    assert "disabled" in log.lower()


@pytest.mark.asyncio
async def test_sleep_schedule_requires_robot():
    """sleep-schedule should refuse when no robot is connected."""
    app = AsherApp()
    app._robot = None
    app._account = MagicMock()
    app._account.disconnect = AsyncMock()
    app._pets = []
    app._connect_worker = lambda **kwargs: None  # type: ignore[method-assign]

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "sleep-schedule")
        await pilot.pause()

        log = _log_text(app)

    assert "Not connected" in log or "connected" in log.lower()


@pytest.mark.asyncio
async def test_sleep_schedule_alias_works(connected_app):
    """The 'sleepschedule' alias should dispatch the same command."""
    connected_app._robot.sleep_schedule = _make_schedule(enabled_days=[0])
    async with connected_app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await _type(pilot, "sleepschedule")
        await pilot.pause()
        await pilot.pause()

        log = _log_text(connected_app)

    assert "22:00" in log
