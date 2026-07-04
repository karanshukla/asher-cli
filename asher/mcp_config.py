"""Manage the Litter-Robot MCP server entry in Claude Desktop's config file(s)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

_SERVER_NAME = "Asher CLI MCP Bridge"


def mcp_extra_installed() -> bool:
    """Whether pylitterbot's mcp extra (the third-party `mcp` SDK) is importable."""
    return importlib.util.find_spec("mcp") is not None


def config_paths() -> list[Path]:
    """Return every claude_desktop_config.json path this OS's Claude Desktop might read.

    On Windows, a standard installer and an MSIX/Microsoft Store install use different,
    unrelated directories (the Store version is redirected by Windows to a virtualized
    per-package path) - write to both so the entry is picked up regardless of install type.

    On Linux, Anthropic's official apt package (beta as of mid-2026) is expected to use
    ~/.config/Claude/, matching macOS/Windows naming, but older community-built wrappers
    used ~/.config/claude-desktop/ - include that one too if it's already present.
    """
    if sys.platform == "win32":
        paths = []
        appdata = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        paths.append(appdata / "Claude" / "claude_desktop_config.json")

        local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        packages_dir = local_appdata / "Packages"
        if packages_dir.is_dir():
            for entry in sorted(packages_dir.glob("Claude_*")):
                paths.append(
                    entry / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json"
                )
        return paths
    if sys.platform == "darwin":
        return [
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        ]

    paths = [Path.home() / ".config" / "Claude" / "claude_desktop_config.json"]
    alt_dir = Path.home() / ".config" / "claude-desktop"
    if alt_dir.is_dir():
        paths.append(alt_dir / "claude_desktop_config.json")
    return paths


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data: dict = json.loads(path.read_text(encoding="utf-8"))
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def set_mcp_enabled(enabled: bool) -> list[Path]:
    """Add or remove the MCP server entry in every known config location.

    Returns the list of config paths actually written.
    """
    touched: list[Path] = []

    for path in config_paths():
        data = _load(path)
        servers = data.setdefault("mcpServers", {})

        if enabled:
            servers[_SERVER_NAME] = {
                "command": sys.executable,
                "args": ["-m", "asher.mcp_bridge"],
            }
            _save(path, data)
            touched.append(path)
        elif _SERVER_NAME in servers:
            del servers[_SERVER_NAME]
            _save(path, data)
            touched.append(path)

    return touched


def mcp_status() -> list[tuple[Path, bool]]:
    """Return (path, enabled) for every known Claude Desktop config location."""
    result = []
    for path in config_paths():
        data = _load(path)
        enabled = _SERVER_NAME in data.get("mcpServers", {})
        result.append((path, enabled))
    return result
