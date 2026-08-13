"""Optional system-tray icon for the background watcher.

``pystray`` and Pillow are an extra (``pip install "asher-cli[tray]"``): a tray
is a nicety, and on a server, an SSH session, or a Linux desktop with no
AppIndicator host there is nothing to attach to. Every entry point here
degrades to "no tray" rather than failing, so :mod:`asher.daemon` can always
fall back to a headless watcher.

The threading split is forced by the toolkits pystray wraps — AppKit on macOS
and the Win32 message loop both insist on running from the main thread — so the
icon owns the main thread and :class:`~asher.watcher.WatcherRunner` takes the
asyncio side off it.
"""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from . import config, theme

if TYPE_CHECKING:
    from .watcher import Snapshot

_ICON_SIZE = 64


def is_available() -> bool:
    """Whether a tray icon can plausibly be shown on this machine.

    A cheap pre-flight, not a guarantee: pystray only discovers that its backend
    is unusable when the loop starts, which is why :func:`run` also survives
    failing outright.
    """
    try:
        import PIL  # noqa: F401, PLC0415
        import pystray  # noqa: F401, PLC0415
    except ImportError:
        return False
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def run(
    *,
    robot_selector: str | None = None,
    poll_seconds: int = 300,
    drawer_threshold: float = 85.0,
    log: Callable[[str], None] = print,
) -> int:
    """Run the watcher under a tray icon. Returns the watcher's exit code.

    Falls back to a plain headless watcher if the tray can't actually start —
    losing the icon is a far better outcome than losing the notifications.
    """
    watch_kwargs: dict[str, Any] = {
        "robot_selector": robot_selector,
        "poll_seconds": poll_seconds,
        "drawer_threshold": drawer_threshold,
        "log": log,
    }
    try:
        import pystray  # noqa: PLC0415
    except ImportError:
        return _headless(watch_kwargs)

    from .watcher import WatcherRunner  # noqa: PLC0415

    state = _TrayState()
    runner = WatcherRunner(on_status=state.update, **watch_kwargs)
    icon = pystray.Icon(
        "asher",
        icon=_icon_image(theme.MUTED),
        title="Asher — connecting…",
        menu=_build_menu(pystray, state, runner, log),
    )
    state.bind(icon)
    watching = threading.Event()

    def setup(tray_icon: Any) -> None:
        tray_icon.visible = True
        watching.set()
        runner.start()
        threading.Thread(
            target=_stop_icon_when_watcher_exits,
            args=(runner, tray_icon),
            name="asher-tray-exit",
            daemon=True,
        ).start()

    try:
        icon.run(setup=setup)
    except Exception as exc:  # noqa: BLE001 — an unusable backend must not cost us the watcher
        log(f"Tray unavailable ({exc}) — watching without one.")
        if not watching.is_set():
            return _headless(watch_kwargs)

    runner.request_stop()
    runner.join(timeout=10)
    return runner.exit_code


def _headless(watch_kwargs: dict[str, Any]) -> int:
    import asyncio  # noqa: PLC0415

    from .watcher import watch  # noqa: PLC0415

    return asyncio.run(watch(**watch_kwargs))


def _stop_icon_when_watcher_exits(runner: Any, icon: Any) -> None:
    """Close the tray when the watcher gives up, so the icon can't outlive it."""
    runner.finished.wait()
    with contextlib.suppress(Exception):
        icon.stop()


class _TrayState:
    """The latest robot snapshot, and the icon it drives.

    Updates arrive on the watcher thread and are pushed straight onto the icon;
    every backend pystray supports accepts attribute writes from any thread.
    Redundant redraws are dropped because a status poll fires far more often
    than the rendered state actually changes.
    """

    def __init__(self) -> None:
        self._icon: Any = None
        self.snapshot: Snapshot | None = None
        self._rendered: tuple[str, str] | None = None

    def bind(self, icon: Any) -> None:
        self._icon = icon

    def update(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot
        rendered = (self.title(), self._colour())
        if rendered == self._rendered or self._icon is None:
            return
        self._rendered = rendered
        with contextlib.suppress(Exception):
            self._icon.icon = _icon_image(rendered[1])
            self._icon.title = rendered[0]
            self._icon.update_menu()

    def title(self) -> str:
        snapshot = self.snapshot
        if snapshot is None:
            return "Asher — connecting…"
        if not snapshot.online:
            return f"Asher — {snapshot.name} (offline)"
        return f"Asher — {snapshot.name}: {snapshot.status}, drawer {snapshot.drawer}"

    def detail(self) -> str:
        snapshot = self.snapshot
        if snapshot is None:
            return "Connecting…"
        return f"{snapshot.status}  ·  drawer {snapshot.drawer}"

    def _colour(self) -> str:
        snapshot = self.snapshot
        if snapshot is None or not snapshot.online:
            return theme.MUTED
        return theme.DANGER if snapshot.faulted else theme.OK


def _build_menu(pystray: Any, state: _TrayState, runner: Any, log: Callable[[str], None]) -> Any:
    """Assemble the tray menu — a live status readout plus the two useful verbs."""

    def inert(item: Any) -> None:
        """Menu rows that are readouts, not buttons."""

    def clean(icon: Any, item: Any) -> None:
        if runner.call(lambda session: session.robot.start_cleaning()):
            log("Clean cycle requested from the tray.")
        else:
            log("Not connected — clean cycle not sent.")

    def toggle_notifications(icon: Any, item: Any) -> None:
        settings = config.update(notifications=not config.load().get("notifications", True))
        log(f"Notifications {'enabled' if settings['notifications'] else 'disabled'}.")

    def quit_watcher(icon: Any, item: Any) -> None:
        runner.request_stop()
        icon.stop()

    return pystray.Menu(
        pystray.MenuItem(lambda item: state.title().removeprefix("Asher — "), inert, enabled=False),
        pystray.MenuItem(lambda item: state.detail(), inert, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Clean now", clean),
        pystray.MenuItem(
            "Notifications",
            toggle_notifications,
            checked=lambda item: bool(config.load().get("notifications", True)),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_watcher),
    )


def _icon_image(colour: str) -> Any:
    """Draw the tray glyph — a cat head in ``colour``, no asset files needed.

    Kept to one flat silhouette because a tray icon is rendered at 16-22px on
    most desktops, where anything finer turns to mush.
    """
    from PIL import Image, ImageDraw  # noqa: PLC0415

    image = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.polygon([(12, 26), (16, 4), (32, 18)], fill=colour)
    draw.polygon([(52, 26), (48, 4), (32, 18)], fill=colour)
    draw.ellipse((8, 16, 56, 58), fill=colour)
    return image
