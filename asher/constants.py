"""Module-level constants shared across the app."""

from __future__ import annotations

STATUS_COLORS: dict[str, str] = {
    "Ready": "#3fb950",
    "Cycling": "#58a6ff",
    "Cat Detected": "#d29922",
    "Drawer Full": "#f85149",
    "Offline": "#f85149",
    "Sleeping": "#484f58",
    "Empty Cycle": "#58a6ff",
    "Paused": "#d29922",
    "Clean Cycle Complete": "#3fb950",
}

ROBOT_MODELS: dict[str, str] = {
    "LitterRobot3": "LR3",
    "LitterRobot4": "LR4",
    "LitterRobot5": "LR5",
    "FeederRobot": "Feeder",
}
