"""Model-specific command adapters for Litter Robot models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .robot_protocol import RobotProtocol


class RobotAdapter(ABC):
    """Translates Asher commands into model-specific robot API calls."""

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


class LR4Adapter(RobotAdapter):
    async def set_sleep(self, enable: bool) -> tuple[bool, str]:
        return False, "LR4 sleep requires a per-day schedule - not yet supported"

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


class LR5Adapter(RobotAdapter):
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


_ADAPTER_MAP: dict[str, type[RobotAdapter]] = {
    "LitterRobot3": LR3Adapter,
    "LitterRobot4": LR4Adapter,
    "LitterRobot5": LR5Adapter,
}


def make_adapter(robot: RobotProtocol) -> RobotAdapter:
    """Return the right adapter for the given robot model, defaulting to LR4."""
    cls = _ADAPTER_MAP.get(type(robot).__name__, LR4Adapter)
    return cls(robot)
