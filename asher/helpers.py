"""Pure helper functions — no Textual or pylitterbot imports."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from rich.text import Text

from . import theme
from .constants import ROBOT_MODELS

_DEV_MODE_VAR = "ASHER_CLI_DEV_MODE"


def dev_mode() -> bool:
    """Whether this is a working copy rather than a real install.

    Set by ``ASHER_CLI_DEV_MODE`` in the repo's ``.env``. It gates the
    conveniences that only make sense while developing — the ``dev`` version
    string, and reading credentials out of the environment — so neither can
    take effect on a machine that merely installed the package.
    """
    return os.getenv(_DEV_MODE_VAR, "false").lower() == "true"


def applescript_string(value: str) -> str:
    """Quote a Python string as an AppleScript literal.

    ``osascript -e`` takes one argument, so text is embedded in source rather
    than passed as data — which makes escaping the caller's problem: a robot
    named ``Cat "Bin"`` would otherwise end the literal early.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def fmt_ago(dt: datetime | None) -> str:
    if dt is None:
        return "never"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    s = int((datetime.now(timezone.utc) - dt).total_seconds())
    if s < 60:
        return f"{s}s ago"
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


def drawer_bar(pct: float, width: int = 14) -> Text:
    filled = max(0, min(width, int(width * pct / 100)))
    bar = "█" * filled + "░" * (width - filled)
    color = theme.DANGER if pct >= 85 else theme.WARN if pct >= 60 else theme.OK
    t = Text()
    t.append("[", style=theme.MUTED)
    t.append(bar, style=color)
    t.append("]", style=theme.MUTED)
    return t


def ts() -> Text:
    t = Text()
    t.append(f"[{datetime.now().strftime('%H:%M:%S')}] ", style=theme.MUTED)
    return t


def robot_model(robot: object) -> str:
    return ROBOT_MODELS.get(type(robot).__name__, type(robot).__name__)
