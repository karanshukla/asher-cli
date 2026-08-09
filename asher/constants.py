"""Module-level constants shared across the app."""

from __future__ import annotations

from . import theme

STATUS_COLORS: dict[str, str] = {
    "Ready": theme.OK,
    "Cycling": theme.ACCENT,
    "Cat Detected": theme.WARN,
    "Drawer Full": theme.DANGER,
    "Offline": theme.DANGER,
    "Sleeping": theme.MUTED,
    "Empty Cycle": theme.ACCENT,
    "Paused": theme.WARN,
    "Clean Cycle Complete": theme.OK,
}

ROBOT_MODELS: dict[str, str] = {
    "LitterRobot3": "LR3",
    "LitterRobot4": "LR4",
    "LitterRobot5": "LR5",
    "FeederRobot": "Feeder",
}
