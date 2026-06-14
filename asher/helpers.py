"""Pure helper functions — no Textual or pylitterbot imports."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text

STATUS_COLORS: dict[str, str] = {
    "Ready": "#3fb950",  # green
    "Cycling": "#58a6ff",  # blue
    "Cat Detected": "#d29922",  # amber
    "Drawer Full": "#f85149",  # red
    "Offline": "#f85149",  # red
    "Sleeping": "#484f58",  # muted
}


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
    color = "#f85149" if pct >= 85 else "#d29922" if pct >= 60 else "#3fb950"
    t = Text()
    t.append("[", style="#484f58")
    t.append(bar, style=color)
    t.append("]", style="#484f58")
    return t


def ts() -> Text:
    t = Text()
    t.append(f"[{datetime.now().strftime('%H:%M:%S')}] ", style="#484f58")
    return t
