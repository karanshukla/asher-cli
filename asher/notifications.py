"""Desktop toast notifications and audible alerts for fault/cycle events.

Thin façade over ``plyer`` so callers stay decoupled from the notification
backend and tests patch one path. Both functions are always-safe: a missing
plyer install, a headless session (SSH/container with no notification daemon),
or a flaky platform backend all degrade to a silent no-op rather than crashing
the app or blocking the refresh loop. The ``/notify`` slash command gates
whether these fire at all.
"""

from __future__ import annotations

import sys

_APP_NAME = "Asher CLI"


def fire(title: str, message: str) -> None:
    """Fire a toast notification. Silently no-ops if plyer is missing or errors.

    Plyer is imported lazily so ``import asher.notifications`` never fails even
    when the dependency is absent.
    """
    try:
        from plyer import notification  # noqa: PLC0415
    except ImportError:
        return
    try:
        notification.notify(title=title, message=message, app_name=_APP_NAME, timeout=8)
    except Exception:
        return  # noqa: BLE001 — platform backends are flaky; never crash on a toast


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
