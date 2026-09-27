"""Pure helper functions — no Textual or pylitterbot imports."""

from __future__ import annotations

import os
import re
from datetime import datetime, time, timezone

from rich.text import Text

from . import theme
from .constants import ACTIVITY_TYPES, ROBOT_MODELS

_DEV_MODE_VAR = "ASHER_CLI_DEV_MODE"

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


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


def fmt_until(dt: datetime | None) -> str:
    """Render a future date as ``2026-09-14 (in 23d)``; a past one reads ``overdue``."""
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    seconds = (dt - datetime.now(timezone.utc)).total_seconds()
    stamp = dt.date().isoformat()
    # Counted away from now in whole days, so 3 days and an hour ago reads as
    # "3d" in either direction — timedelta.days alone floors that to 4.
    days = int(abs(seconds) // 86400)
    if seconds < 0:
        return f"{stamp} (overdue by {days}d)" if days else f"{stamp} (today)"
    return f"{stamp} (in {days}d)" if days else f"{stamp} (today)"


def hex_colour(value: str) -> str | None:
    """Normalise a user-typed colour to ``#RRGGBB``, or None when it isn't one.

    Accepts a leading ``#`` or not, and the 3-digit shorthand. Validating here
    rather than at the cloud keeps a typo a local error message instead of a
    round trip that comes back as a generic rejection.
    """
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(component * 2 for component in text)
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", text):
        return None
    return f"#{text.upper()}"


def parse_clock(value: str) -> time | None:
    """Parse a 24-hour ``HH:MM`` wall-clock time, or None when unreadable."""
    hours, separator, minutes = value.strip().partition(":")
    if not separator:
        return None
    try:
        hour, minute = int(hours), int(minutes)
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return time(hour=hour, minute=minute)


def split_type_flag(args: list[str]) -> tuple[list[str], str | None]:
    """Split ``--type X`` / ``--type=X`` out of an argument list.

    Returns the remaining positional arguments and the requested type, which is
    an empty string when the flag was given without a value — the caller can
    tell "no filter" (``None``) from "filter, but unreadable".
    """
    rest: list[str] = []
    wanted: str | None = None
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--type":
            wanted = args[index + 1] if index + 1 < len(args) else ""
            index += 2
            continue
        if arg.startswith("--type="):
            wanted = arg.split("=", 1)[1]
            index += 1
            continue
        rest.append(arg)
        index += 1
    return rest, wanted


def activity_type(value: str | None) -> str | None:
    """Map a friendly ``--type`` argument onto the cloud's activity type name.

    An unknown word is passed through uppercased rather than rejected, so a type
    the app doesn't know yet is still reachable; only a missing value is None.
    """
    if value is None or not value.strip():
        return None
    text = value.strip()
    return ACTIVITY_TYPES.get(text.lower(), text.upper())


def parse_day(value: str) -> int | None:
    """Parse a weekday name into a Python weekday index (Mon=0…Sun=6), or None."""
    text = value.strip().lower()[:3]
    for index, name in enumerate(DAY_NAMES):
        if name.lower() == text:
            return index
    return None


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


def status_text(status: object) -> str:
    """Render a robot status as human-readable text.

    ``LitterBoxStatus`` is a plain ``Enum`` (not ``StrEnum``), so ``str()`` yields
    the verbose ``"LitterBoxStatus.READY"`` — or, via ``.value``, the raw
    3-letter cloud code (``"RDY"``). The readable form ("Ready") lives in its
    ``text`` property. Falls back to ``str()`` for plain strings, and to an em
    dash when status is missing.
    """
    if status is None:
        return "—"
    text = getattr(status, "text", None)
    if isinstance(text, str):
        return text
    return str(status)
