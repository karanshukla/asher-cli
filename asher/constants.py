"""Module-level constants shared across the app."""

from __future__ import annotations

from . import theme

STATUS_COLORS: dict[str, str] = {
    "Ready": theme.OK,
    "Clean Cycle In Progress": theme.ACCENT,
    "Empty Cycle": theme.ACCENT,
    "Cat Detected": theme.WARN,
    "Clean Cycle Paused": theme.WARN,
    "Drawer Almost Full - 2 Cycles Left": theme.WARN,
    "Drawer Almost Full - 1 Cycle Left": theme.WARN,
    "Drawer Full": theme.DANGER,
    "Off": theme.DANGER,
    "Offline": theme.DANGER,
    "Clean Cycle Complete": theme.OK,
}

ROBOT_MODELS: dict[str, str] = {
    "LitterRobot3": "LR3",
    "LitterRobot4": "LR4",
    "LitterRobot5": "LR5",
    "FeederRobot": "Feeder",
}
