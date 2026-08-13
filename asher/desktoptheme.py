"""Whether this desktop's tray sits on a dark or a light background.

The tray icon is a silhouette, so it has to be drawn in the opposite tone to
whatever it lands on — a dark glyph disappears into a dark panel and a light one
disappears into a light panel. Every desktop stores that preference somewhere
different, and none of them offer a portable change notification, so this polls
behind a short TTL rather than subscribing.

Every probe degrades to ``None`` (and the caller to :data:`_FALLBACK_IS_DARK`)
instead of raising: an icon drawn for the wrong tone is cosmetic, and the
watcher behind it must outlive any desktop-integration weirdness.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 # fixed argv from shutil.which, no shell
import sys
import time
from typing import Any

_FALLBACK_IS_DARK = True
"""Assumed tone when nothing on this machine will say — dark panels dominate."""

_CACHE_SECONDS = 30.0
_PROBE_TIMEOUT_SECONDS = 5

_WINDOWS_PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
_KDE_READERS = ("kreadconfig6", "kreadconfig5")

_cache: tuple[float, bool] | None = None


def panel_is_dark(*, refresh: bool = False) -> bool:
    """Whether the tray/menu-bar background is dark on this desktop.

    Cached for :data:`_CACHE_SECONDS` so a caller that asks once per status poll
    doesn't spawn a probe process every time.
    """
    global _cache  # noqa: PLW0603 — one process-wide TTL cache, not per-instance state
    now = time.monotonic()
    if not refresh and _cache is not None and now - _cache[0] < _CACHE_SECONDS:
        return _cache[1]
    detected = _detect()
    resolved = _FALLBACK_IS_DARK if detected is None else detected
    _cache = (now, resolved)
    return resolved


def _detect() -> bool | None:
    if sys.platform == "darwin":
        return _macos_is_dark()
    if sys.platform == "win32":
        return _windows_is_dark()
    if sys.platform.startswith("linux"):
        return _linux_is_dark()
    return None


# ── macOS ────────────────────────────────────────────────────────────────────


def _macos_is_dark() -> bool | None:
    """Read ``AppleInterfaceStyle``, which exists only while Dark Mode is on.

    In Light Mode the key is absent entirely, which ``defaults`` reports as a
    non-zero exit rather than as empty output — so a failed read is the answer
    "light", not the answer "don't know".
    """
    result = _run(["defaults", "read", "-g", "AppleInterfaceStyle"])
    if result is None:
        return None
    if result.returncode != 0:
        return False
    return "dark" in result.stdout.strip().lower()


# ── Windows ──────────────────────────────────────────────────────────────────


def _windows_is_dark() -> bool | None:
    """Read the Personalize keys, taskbar tone first.

    ``SystemUsesLightTheme`` is the one that governs the taskbar (and so the
    notification area); ``AppsUseLightTheme`` governs window chrome and is the
    only one present on builds before 1903, which makes it the fallback rather
    than the first choice.
    """
    import importlib  # noqa: PLC0415

    try:
        winreg: Any = importlib.import_module("winreg")
    except ImportError:
        return None
    for value_name in ("SystemUsesLightTheme", "AppsUseLightTheme"):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WINDOWS_PERSONALIZE_KEY) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
        except OSError:
            continue
        return not int(value)
    return None


# ── Linux ────────────────────────────────────────────────────────────────────


def _linux_is_dark() -> bool | None:
    for probe in (_kde_is_dark, _gnome_is_dark):
        answer = probe()
        if answer is not None:
            return answer
    return None


def _kde_is_dark() -> bool | None:
    """Judge Plasma by its window background colour rather than a theme name.

    Breeze ships light and dark variants under names that don't reliably say
    which is which, and third-party colour schemes are named anything at all,
    so the actual RGB is the only dependable signal.
    """
    for reader in _KDE_READERS:
        result = _run(
            [
                reader,
                "--file",
                "kdeglobals",
                "--group",
                "Colors:Window",
                "--key",
                "BackgroundNormal",
            ]
        )
        if result is None or result.returncode != 0:
            continue
        answer = _rgb_is_dark(result.stdout.strip())
        if answer is not None:
            return answer
    return None


def _gnome_is_dark() -> bool | None:
    """Prefer the explicit ``color-scheme`` setting, falling back to the theme name.

    ``color-scheme`` reports ``default`` when the user has expressed no
    preference, which is not the same as "light" — that case has to fall through
    to the GTK theme name instead of being read as an answer.
    """
    scheme = _gsettings("color-scheme")
    if scheme is not None and scheme != "default":
        return "dark" in scheme
    theme_name = _gsettings("gtk-theme")
    if theme_name is None:
        return None
    return "dark" in theme_name


def _gsettings(key: str) -> str | None:
    result = _run(["gsettings", "get", "org.gnome.desktop.interface", key])
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip().strip("'\"").lower() or None


def _rgb_is_dark(value: str) -> bool | None:
    """Whether a ``"r,g,b"`` string is a dark colour, by Rec. 601 luma."""
    parts = value.split(",")
    if len(parts) < 3:
        return None
    try:
        red, green, blue = (int(part) for part in parts[:3])
    except ValueError:
        return None
    return (0.299 * red + 0.587 * green + 0.114 * blue) < 128


def _run(argv: list[str]) -> subprocess.CompletedProcess[str] | None:
    """Run a desktop-settings probe, or return None if it can't be run at all."""
    executable = shutil.which(argv[0])
    if executable is None:
        return None
    try:
        return subprocess.run(  # nosec B603 # fixed argv from shutil.which, no shell
            [executable, *argv[1:]],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
