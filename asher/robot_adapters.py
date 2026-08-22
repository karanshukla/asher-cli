"""Model-specific command adapters for Litter Robot models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from .helpers import DAY_NAMES

if TYPE_CHECKING:
    from datetime import time

    from pylitterbot.activity import Activity

    from .robot_protocol import RobotProtocol

# The LR3's sleep length is fixed in firmware (pylitterbot's
# litterrobot3.SLEEP_DURATION_HOURS), so only the start time is settable.
LR3_SLEEP_HOURS = 8

# The LR4 exposes no schedule setter at all — the app is the only way to change
# one, and saying so beats a cloud rejection the user can't act on.
LR4_SCHEDULE_NOTE = (
    "LR4 sleep schedules can only be changed in the Whisker app — "
    "'sleep-schedule' shows the one it's running"
)

# Only the LR5's activity endpoint takes a type parameter; the LR3/LR4 history
# call returns whatever the cloud feels like sending.
HISTORY_FILTER_NOTE = "Filtering history by type is only available on the LR5"


class RobotAdapter(ABC):
    """Translates Asher commands into model-specific robot API calls."""

    supports_history_filter = False

    def __init__(self, robot: RobotProtocol) -> None:
        self.robot = robot

    @abstractmethod
    async def set_sleep(self, enable: bool) -> tuple[bool, str]:
        """Enable or disable sleep mode. Returns (success, message)."""

    @abstractmethod
    async def set_night_light(self, mode: str) -> tuple[bool, str]:
        """Set night light mode ('on', 'off', or 'auto'). Returns (success, message)."""

    @abstractmethod
    async def set_night_light_brightness(self, level: int) -> tuple[bool, str]:
        """Set night light brightness level. Returns (success, message)."""

    async def set_panel_lockout(self, enable: bool) -> tuple[bool, str]:
        """Enable or disable panel lockout. Uniform API across all models."""
        try:
            ok = await self.robot.set_panel_lockout(enable)
        except Exception as exc:
            return False, f"Panel lock command failed: {exc}"
        if not ok:
            return False, "Panel lock command rejected by cloud"
        return True, "Panel locked" if enable else "Panel unlocked"

    async def set_panel_brightness(self, level: str) -> tuple[bool, str]:
        """Set the control-panel brightness ('low', 'medium', 'high'). LR4/LR5 only."""
        return False, "Panel brightness is only available on the LR4/LR5"

    # ── sleep schedule ────────────────────────────────────────────────────────

    async def set_sleep_window(
        self, weekday: int | None, sleep: time, wake: time
    ) -> tuple[bool, str]:
        """Set the sleep → wake window, for one weekday or (``None``) every day."""
        return False, "Setting a sleep schedule is not supported on this model"

    async def disable_sleep_schedule(self) -> tuple[bool, str]:
        """Turn every scheduled sleep window off.

        Disabling is the same cloud call as waking the robot on every model that
        has one, so this rides on ``set_sleep`` rather than repeating the
        per-model dispatch — including the LR4's "use the app" refusal.
        """
        ok, msg = await self.set_sleep(False)
        return (True, "Sleep schedule disabled for every day") if ok else (False, msg)

    # ── activity history ──────────────────────────────────────────────────────

    async def get_history(
        self, limit: int, activity_type: str | None = None
    ) -> tuple[list[Activity] | None, str]:
        """Fetch recent activity. Returns ``(events, "")`` or ``(None, reason)``."""
        if activity_type is not None:
            return None, HISTORY_FILTER_NOTE
        try:
            return list(await self.robot.get_activity_history(limit=limit)), ""
        except Exception as exc:
            return None, f"Failed to get history: {exc}"

    # ── LR5-only capabilities ─────────────────────────────────────────────────
    # The base implementations return "not supported"; LR5Adapter overrides them.
    # Commands detect model via the adapter and surface these messages gracefully.

    async def set_privacy_mode(self, enable: bool) -> tuple[bool, str]:
        """Toggle privacy mode. LR5 only."""
        return False, "Privacy mode is only available on the LR5"

    async def set_volume(self, volume: int) -> tuple[bool, str]:
        """Set sound volume (0-100). LR5 only."""
        return False, "Volume control is only available on the LR5"

    async def set_camera_audio(self, enable: bool) -> tuple[bool, str]:
        """Toggle camera audio. LR5 only."""
        return False, "Camera audio is only available on the LR5"

    async def set_night_light_color(self, colour: str) -> tuple[bool, str]:
        """Set the night light colour from a ``#RRGGBB`` string. LR5 only."""
        return False, "Night light colour is only available on the LR5"

    async def reset_waste_drawer(self) -> tuple[bool, str]:
        """Reset the waste drawer level indicator. LR5 only."""
        return False, "Drawer reset is only available on the LR5"


class LR3Adapter(RobotAdapter):
    async def set_sleep(self, enable: bool) -> tuple[bool, str]:
        try:
            ok = await self.robot.set_sleep_mode(enable)
        except Exception as exc:
            return False, f"Sleep mode change failed: {exc}"
        if not ok:
            return False, "Sleep mode command rejected"
        return True, "Sleep mode enabled" if enable else "Robot woken up"

    async def set_night_light(self, mode: str) -> tuple[bool, str]:
        if mode == "auto":
            return False, "LR3 does not support auto night light mode - use on or off"
        try:
            ok = await self.robot.set_night_light(mode == "on")  # type: ignore[attr-defined]
        except Exception as exc:
            return False, f"Night light command failed: {exc}"
        if not ok:
            return False, "Night light command rejected"
        return True, f"Night light {mode}"

    async def set_night_light_brightness(self, level: int) -> tuple[bool, str]:
        return False, "Night light brightness control not supported on LR3"

    async def set_sleep_window(
        self, weekday: int | None, sleep: time, wake: time
    ) -> tuple[bool, str]:
        if weekday is not None:
            return (
                False,
                f"The LR3 runs one schedule every day — use "
                f"'sleep-schedule set all {sleep:%H:%M} {wake:%H:%M}'",
            )
        try:
            ok = await self.robot.set_sleep_mode(True, sleep)  # type: ignore[call-arg]
        except Exception as exc:
            return False, f"Sleep schedule change failed: {exc}"
        if not ok:
            return False, "Sleep schedule command rejected"
        return True, (
            f"Sleeping from {sleep:%H:%M} every day "
            f"(the LR3 always wakes {LR3_SLEEP_HOURS}h later, so the wake time was ignored)"
        )


class LR4Adapter(RobotAdapter):
    async def set_sleep(self, enable: bool) -> tuple[bool, str]:
        return False, LR4_SCHEDULE_NOTE

    async def set_sleep_window(
        self, weekday: int | None, sleep: time, wake: time
    ) -> tuple[bool, str]:
        return False, LR4_SCHEDULE_NOTE

    async def set_night_light(self, mode: str) -> tuple[bool, str]:
        from pylitterbot.enums import NightLightMode  # noqa: PLC0415

        mode_map = {
            "on": NightLightMode.ON,
            "off": NightLightMode.OFF,
            "auto": NightLightMode.AUTO,
        }
        nl_mode = mode_map.get(mode)
        if nl_mode is None:
            return False, f"Unknown night light mode '{mode}'"
        try:
            ok = await self.robot.set_night_light_mode(nl_mode)
        except Exception as exc:
            return False, f"Night light command failed: {exc}"
        if not ok:
            return False, "Night light command rejected"
        return True, f"Night light {mode}"

    async def set_night_light_brightness(self, level: int) -> tuple[bool, str]:
        if level not in (25, 50, 100):
            return False, f"Invalid brightness {level} - LR4 accepts 25, 50, or 100"
        try:
            ok = await self.robot.set_night_light_brightness(level)
        except Exception as exc:
            return False, f"Night light brightness command failed: {exc}"
        if not ok:
            return False, "Night light brightness command rejected"
        return True, f"Night light brightness set to {level}%"

    async def set_panel_brightness(self, level: str) -> tuple[bool, str]:
        from pylitterbot.enums import BrightnessLevel  # noqa: PLC0415

        level_map = {
            "low": BrightnessLevel.LOW,
            "medium": BrightnessLevel.MEDIUM,
            "high": BrightnessLevel.HIGH,
        }
        bl = level_map.get(level)
        if bl is None:
            return False, f"Unknown brightness '{level}' - use low, medium, or high"
        try:
            ok = await self.robot.set_panel_brightness(bl)
        except Exception as exc:
            return False, f"Panel brightness command failed: {exc}"
        if not ok:
            return False, "Panel brightness command rejected"
        return True, f"Panel brightness set to {level}"


class LR5Adapter(RobotAdapter):
    supports_history_filter = True

    async def set_sleep(self, enable: bool) -> tuple[bool, str]:
        try:
            ok = await self.robot.set_sleep_mode(enable)
        except Exception as exc:
            return False, f"Sleep mode change failed: {exc}"
        if not ok:
            return False, "Sleep mode command rejected"
        return True, "Sleep mode enabled" if enable else "Robot woken up"

    async def set_night_light(self, mode: str) -> tuple[bool, str]:
        from pylitterbot.enums import NightLightMode  # noqa: PLC0415

        mode_map = {
            "on": NightLightMode.ON,
            "off": NightLightMode.OFF,
            "auto": NightLightMode.AUTO,
        }
        nl_mode = mode_map.get(mode)
        if nl_mode is None:
            return False, f"Unknown night light mode '{mode}'"
        try:
            ok = await self.robot.set_night_light_mode(nl_mode)
        except Exception as exc:
            return False, f"Night light command failed: {exc}"
        if not ok:
            return False, "Night light command rejected"
        return True, f"Night light {mode}"

    async def set_night_light_brightness(self, level: int) -> tuple[bool, str]:
        if not 0 <= level <= 100:
            return False, f"Invalid brightness {level} - must be 0-100"
        try:
            ok = await self.robot.set_night_light_brightness(level)
        except Exception as exc:
            return False, f"Night light brightness command failed: {exc}"
        if not ok:
            return False, "Night light brightness command rejected"
        return True, f"Night light brightness set to {level}%"

    async def set_panel_brightness(self, level: str) -> tuple[bool, str]:
        from pylitterbot.enums import BrightnessLevel  # noqa: PLC0415

        level_map = {
            "low": BrightnessLevel.LOW,
            "medium": BrightnessLevel.MEDIUM,
            "high": BrightnessLevel.HIGH,
        }
        bl = level_map.get(level)
        if bl is None:
            return False, f"Unknown brightness '{level}' - use low, medium, or high"
        try:
            ok = await self.robot.set_panel_brightness(bl)
        except Exception as exc:
            return False, f"Panel brightness command failed: {exc}"
        if not ok:
            return False, "Panel brightness command rejected"
        return True, f"Panel brightness set to {level}"

    # ── LR5-only capabilities ─────────────────────────────────────────────────

    async def set_privacy_mode(self, enable: bool) -> tuple[bool, str]:
        try:
            ok = await self.robot.set_privacy_mode(enable)
        except Exception as exc:
            return False, f"Privacy mode command failed: {exc}"
        if not ok:
            return False, "Privacy mode command rejected"
        return True, f"Privacy mode {'on' if enable else 'off'}"

    async def set_volume(self, volume: int) -> tuple[bool, str]:
        if not 0 <= volume <= 100:
            return False, f"Invalid volume {volume} - must be 0-100"
        try:
            ok = await self.robot.set_volume(volume)
        except Exception as exc:
            return False, f"Volume command failed: {exc}"
        if not ok:
            return False, "Volume command rejected"
        return True, f"Volume set to {volume}"

    async def set_camera_audio(self, enable: bool) -> tuple[bool, str]:
        try:
            ok = await self.robot.set_camera_audio(enable)
        except Exception as exc:
            return False, f"Camera audio command failed: {exc}"
        if not ok:
            return False, "Camera audio command rejected"
        return True, f"Camera audio {'on' if enable else 'off'}"

    async def reset_waste_drawer(self) -> tuple[bool, str]:
        try:
            ok = await self.robot.reset_waste_drawer()
        except Exception as exc:
            return False, f"Drawer reset command failed: {exc}"
        if not ok:
            return False, "Drawer reset command rejected"
        return True, "Waste drawer level reset"

    async def set_night_light_color(self, colour: str) -> tuple[bool, str]:
        robot: Any = self.robot
        try:
            ok = await robot.set_night_light_settings(color=colour)
        except Exception as exc:
            return False, f"Night light colour command failed: {exc}"
        if not ok:
            return False, "Night light colour command rejected"
        return True, f"Night light colour set to {colour}"

    async def set_sleep_window(
        self, weekday: int | None, sleep: time, wake: time
    ) -> tuple[bool, str]:
        robot: Any = self.robot
        try:
            ok = await robot.set_sleep_mode(
                True,
                sleep.hour * 60 + sleep.minute,
                wake_time=wake.hour * 60 + wake.minute,
                day_of_week=_to_day_of_week(weekday),
            )
        except Exception as exc:
            return False, f"Sleep schedule change failed: {exc}"
        if not ok:
            return False, "Sleep schedule command rejected"
        when = "every day" if weekday is None else DAY_NAMES[weekday]
        return True, f"Sleeping {sleep:%H:%M} → {wake:%H:%M} on {when}"

    async def get_history(
        self, limit: int, activity_type: str | None = None
    ) -> tuple[list[Activity] | None, str]:
        if activity_type is None:
            return await super().get_history(limit)

        from pylitterbot.activity import Activity  # noqa: PLC0415
        from pylitterbot.utils import to_timestamp  # noqa: PLC0415

        robot: Any = self.robot
        try:
            raw = await robot.get_activities(limit=limit, activity_type=activity_type)
        except Exception as exc:
            return None, f"Failed to get history: {exc}"
        # get_activities() returns the raw endpoint dicts; the same (timestamp,
        # type) reduction pylitterbot applies in its own get_activity_history()
        # is what keeps a filtered list renderable by the shared formatter.
        return [
            Activity(timestamp, event.get("type", ""))
            for event in raw
            if (timestamp := to_timestamp(event.get("timestamp"))) is not None
        ], ""


def _to_day_of_week(weekday: int | None) -> int | None:
    """Convert a Python weekday (Mon=0…Sun=6) to pylitterbot's DayOfWeek (Sun=0…Sat=6).

    ``set_sleep_mode``'s own docstring claims 0=Monday, but it matches the value
    against the ``dayOfWeek`` field of the schedule the cloud sent back, and
    those follow the ``DayOfWeek`` enum — so the enum's numbering is the one
    that actually selects a day.
    """
    return None if weekday is None else (weekday + 1) % 7


_ADAPTER_MAP: dict[str, type[RobotAdapter]] = {
    "LitterRobot3": LR3Adapter,
    "LitterRobot4": LR4Adapter,
    "LitterRobot5": LR5Adapter,
}


def make_adapter(robot: RobotProtocol) -> RobotAdapter:
    """Return the right adapter for the given robot model, defaulting to LR4."""
    cls = _ADAPTER_MAP.get(type(robot).__name__, LR4Adapter)
    return cls(robot)
