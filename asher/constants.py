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

# Shortened LitterBoxStatus.text values for the cat panel only. #cat-status
# (asher/ui/style.tcss) is 26 columns wide with a 9-character key column,
# leaving 17 for the value — these .text values overflow that and wrap onto
# a second line. Only entries that would overflow are listed; everything
# else passes through status_text() unshortened. The status bar and the
# headless/`status` command still render the full text.
CAT_PANEL_STATUS_LABELS: dict[str, str] = {
    "Clean Cycle In Progress": "Cycling",
    "Clean Cycle Complete": "Cycle Complete",
    "Clean Cycle Paused": "Cycle Paused",
    "Cat Sensor Interrupted": "Sensor Interrupt",
    "Drawer Almost Full - 2 Cycles Left": "Almost Full (2)",
    "Drawer Almost Full - 1 Cycle Left": "Almost Full (1)",
    "Dump + Home Position Fault": "Dump+Home Fault",
    "Dump Position Fault": "Dump Pos Fault",
    "Home Position Fault": "Home Pos Fault",
    "Cat Sensor Fault At Startup": "Sensor (Startup)",
    "Drawer Full At Startup": "Drawer (Startup)",
    "Pinch Detect At Startup": "Pinch (Startup)",
}

ROBOT_MODELS: dict[str, str] = {
    "LitterRobot3": "LR3",
    "LitterRobot4": "LR4",
    "LitterRobot5": "LR5",
    "FeederRobot": "Feeder",
}
