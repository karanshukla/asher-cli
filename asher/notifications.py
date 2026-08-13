"""Desktop toast notifications and audible alerts for fault/cycle events.

Thin façade over ``plyer`` so callers stay decoupled from the notification
backend and tests patch one path. Both functions are always-safe: a missing
plyer install, a headless session (SSH/container with no notification daemon),
or a flaky platform backend all degrade to a silent no-op rather than crashing
the app or blocking the refresh loop. The ``/notify`` slash command gates
whether these fire at all.

``fire`` falls back to the platform's own notification tool when plyer can't
deliver. plyer picks its macOS/Linux backend at import time and silently has
none when the optional bindings are absent — survivable when a toast merely
decorates a dashboard you are already looking at, but not when the background
watcher (:mod:`asher.watcher`) has nowhere else to surface a fault.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 # each call site below is a fixed argv, no shell
import sys

from .helpers import applescript_string

_APP_NAME = "Asher CLI"
_TIMEOUT_SECONDS = 8
_BACKEND_TIMEOUT_SECONDS = 5


def fire(title: str, message: str) -> bool:
    """Fire a toast notification. Returns whether a backend accepted it.

    Never raises: a missing plyer, an unusable backend, or a machine with no
    notification daemon at all returns ``False`` instead.
    """
    return _fire_plyer(title, message) or _fire_native(title, message)


def _fire_plyer(title: str, message: str) -> bool:
    """Try plyer, the cross-platform backend.

    Imported lazily so ``import asher.notifications`` never fails when the
    dependency is absent.
    """
    try:
        from plyer import notification  # noqa: PLC0415
    except ImportError:
        return False
    try:
        notification.notify(
            title=title, message=message, app_name=_APP_NAME, timeout=_TIMEOUT_SECONDS
        )
    except Exception:
        return False  # noqa: BLE001 — platform backends are flaky; never crash on a toast
    return True


def _fire_native(title: str, message: str) -> bool:
    """Fall back to the OS's own notification command.

    ``osascript`` ships with every macOS install and ``notify-send`` with most
    Linux desktops, so this covers the common case where plyer imported fine but
    had no working backend behind it. Windows needs no fallback — plyer's win32
    backend has no optional dependencies.
    """
    argv = _native_argv(title, message)
    if argv is None:
        return False
    try:
        completed = subprocess.run(  # nosec B603 # fixed argv from shutil.which, no shell
            argv, capture_output=True, timeout=_BACKEND_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _native_argv(title: str, message: str) -> list[str] | None:
    """Build the platform notification command, or None when there isn't one."""
    if sys.platform == "darwin":
        osascript = shutil.which("osascript")
        if osascript is None:
            return None
        script = (
            f"display notification {applescript_string(message)} "
            f"with title {applescript_string(title)}"
        )
        return [osascript, "-e", script]
    if sys.platform.startswith("linux"):
        notify_send = shutil.which("notify-send")
        if notify_send is None:
            return None
        return [
            notify_send,
            "--app-name",
            _APP_NAME,
            "--expire-time",
            str(_TIMEOUT_SECONDS * 1000),
            "--",
            title,
            message,
        ]
    return None


def beep(critical: bool = False) -> None:
    """Audible alert — ``winsound.Beep`` on Windows, terminal bell elsewhere.

    ``critical`` raises the pitch (a safety event like cat-detected vs. a
    gentler nudge for drawer-full).
    """
    if sys.platform == "win32":
        try:
            import winsound  # noqa: PLC0415

            winsound.Beep(880 if critical else 440, 300)
        except Exception:
            print("\a", end="", flush=True)
    else:
        print("\a", end="", flush=True)
