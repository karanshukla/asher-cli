"""Persist a small set of runtime settings across restarts.

Settings written here mirror the rows the ``/config`` slash command displays:
poll interval, cat-panel visibility/colour, the active pet, and the desktop-
notification preferences. Credentials and the preferred-robot serial stay in
the OS keyring; this file holds only non-secret UI preferences, so a corrupt
or hand-edited file degrades to defaults rather than crashing the app.

It is also the only channel between the dashboard and a detached watcher
(:mod:`asher.watcher`), which is why the watcher re-reads it per alert rather
than caching at startup: toggling ``/notify`` in the TUI, or the tray's own
Notifications item, has to reach a process that may have been up for days.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path.home() / ".asher-cli"
_CONFIG_PATH = _CONFIG_DIR / "config.json"

_DEFAULTS: dict[str, Any] = {
    "poll_interval_seconds": 300,
    "cat_panel_visible": True,
    "cat_panel_color": None,
    "active_pet_index": 0,
    "notifications": True,
    "notification_sound": False,
    "watch_tray": True,
    "watch_drawer_threshold": 85,
}


def config_path() -> Path:
    """Return the resolved path of the config file."""
    return _CONFIG_PATH


def load() -> dict[str, Any]:
    """Load config merged over defaults; corrupt/missing file → defaults.

    Only keys present in ``_DEFAULTS`` are read from the file, so a stale
    key left behind by an older release is silently ignored and a future
    key absent from an older file falls back to its default.
    """
    data = dict(_DEFAULTS)
    if not _CONFIG_PATH.exists():
        return data
    try:
        file_data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return data
    if isinstance(file_data, dict):
        for key in _DEFAULTS:
            if key in file_data:
                data[key] = file_data[key]
    return data


def save(settings: dict[str, Any]) -> None:
    """Write settings, creating the parent directory if needed."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def update(**changes: Any) -> dict[str, Any]:
    """Load → merge ``changes`` → save → return the new full settings dict."""
    settings = load()
    settings.update(changes)
    save(settings)
    return settings
