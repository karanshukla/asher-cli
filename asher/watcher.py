"""Background robot watcher — the notification loop without the dashboard.

The TUI only notifies while it is on screen: ``MonitoringMixin._notify_fault``
runs inside the Textual refresh loop, so closing the terminal ends the alerts.
This module is that loop lifted out — plain asyncio, no Textual — so it can run
in a detached process (:mod:`asher.daemon`) or under a tray icon
(:mod:`asher.tray`) and keep notifying with no terminal at all.

Two halves, split so the interesting one is testable without a network:

* :class:`WatchState` — pure. Successive robot snapshots in, :class:`Alert`
  objects out. It owns the "is this worth interrupting the user for?" decision.
* :func:`watch` — the plumbing: authenticate, subscribe to the WebSocket, poll
  as a fallback, reconnect when the cloud drops, hand each alert to a notifier.

A watcher is expected to outlive laptop sleeps, Wi-Fi drops and expiring
tokens, so :func:`watch` supervises its own session and rebuilds it rather than
exiting. The only unrecoverable case is missing credentials — nothing about
waiting makes those appear, whereas an unreachable cloud is the normal state of
a machine that has only just finished booting.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pylitterbot.enums import LitterBoxStatus

from . import config
from .export import EXIT_NO_CREDENTIALS, EXIT_OK
from .faults import SEVERITY_ERROR, check_faults

if TYPE_CHECKING:
    from .headless import Session
    from .robot_protocol import RobotProtocol

_DRAWER_FULL_STATUSES = frozenset(
    {
        LitterBoxStatus.DRAWER_FULL,
        LitterBoxStatus.DRAWER_FULL_1,
        LitterBoxStatus.DRAWER_FULL_2,
    }
)

_REFRESH_FAILURES_BEFORE_RECONNECT = 3
_INITIAL_BACKOFF_SECONDS = 5.0
_MAX_BACKOFF_SECONDS = 300.0
_MIN_POLL_SECONDS = 30


@dataclass(frozen=True)
class Alert:
    """One notification-worthy change in robot state."""

    title: str
    message: str
    critical: bool = False


@dataclass(frozen=True)
class Snapshot:
    """Robot state as the tray needs it — display strings, already resolved."""

    name: str
    status: str
    drawer: str
    online: bool
    faulted: bool


class SessionLost(Exception):
    """The cloud session stopped answering and needs rebuilding."""


class WatchState:
    """Successive robot snapshots in, alerts worth interrupting for out.

    Conditions fall into two kinds, deliberately treated differently on the very
    first evaluation:

    * **Problems** — faults and a filling drawer — alert as soon as they are
      seen, so a watcher started next to an already-faulted robot says so
      immediately instead of staying quiet until the fault happens to clear.
    * **Transitions** — online ⇄ offline — alert only on a change, so startup
      doesn't announce a robot that was never away.

    The instance survives reconnects, which is what stops a Wi-Fi blip from
    re-announcing every fault that was already showing before it.
    """

    def __init__(self, drawer_threshold: float = 85.0) -> None:
        self._drawer_threshold = drawer_threshold
        self._faults: set[str] = set()
        self._drawer_full = False
        self._online: bool | None = None

    def evaluate(self, robot: RobotProtocol) -> list[Alert]:
        """Return the alerts caused by whatever changed since the last call."""
        title = f"Asher — {getattr(robot, 'name', 'robot') or 'robot'}"
        return [
            *self._fault_alerts(robot, title),
            *self._drawer_alerts(robot, title),
            *self._connectivity_alerts(robot, title),
        ]

    def _fault_alerts(self, robot: RobotProtocol, title: str) -> list[Alert]:
        by_label = {fault.label: fault for fault in check_faults(robot)}
        active = set(by_label)
        alerts = [
            Alert(title, label, critical=by_label[label].severity == SEVERITY_ERROR)
            for label in sorted(active - self._faults)
        ]
        alerts += [Alert(title, f"Cleared: {label}") for label in sorted(self._faults - active)]
        self._faults = active
        return alerts

    def _drawer_alerts(self, robot: RobotProtocol, title: str) -> list[Alert]:
        """Early warning before the robot itself reports DRAWER FULL and stops.

        Suppressed once that status is up: the fault path already alerted, and
        two toasts for one drawer is one too many.
        """
        level = _to_float(getattr(robot, "waste_drawer_level", None))
        full = level is not None and level >= self._drawer_threshold
        already_reported = getattr(robot, "status", None) in _DRAWER_FULL_STATUSES
        alerts = (
            [Alert(title, f"Waste drawer {level:.0f}% full")]
            if full and not self._drawer_full and not already_reported and level is not None
            else []
        )
        self._drawer_full = full
        return alerts

    def _connectivity_alerts(self, robot: RobotProtocol, title: str) -> list[Alert]:
        online = bool(getattr(robot, "is_online", False))
        was_online = self._online
        self._online = online
        if was_online is None or online == was_online:
            return []
        return [Alert(title, "Back online" if online else "Went offline", critical=not online)]


def _to_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def snapshot(robot: RobotProtocol) -> Snapshot:
    """Render the tray-facing view of a robot's current state."""
    status = getattr(robot, "status", None)
    status_text = getattr(status, "text", None) if status is not None else None
    level = _to_float(getattr(robot, "waste_drawer_level", None))
    return Snapshot(
        name=str(getattr(robot, "name", "robot") or "robot"),
        status=status_text if isinstance(status_text, str) else "—",
        drawer=f"{level:.0f}%" if level is not None else "—",
        online=bool(getattr(robot, "is_online", False)),
        faulted=bool(check_faults(robot)),
    )


def deliver(alert: Alert) -> None:
    """Fire a toast (plus optional beep) for one alert, honouring ``/notify``.

    Settings are re-read per alert rather than cached at startup so toggling
    notifications — from the tray menu, or from a TUI running alongside — takes
    effect on a watcher that has been up for days.
    """
    settings = config.load()
    if not settings.get("notifications", True):
        return
    from .notifications import beep, fire  # noqa: PLC0415

    fire(alert.title, alert.message)
    if settings.get("notification_sound", False):
        beep(critical=alert.critical)


async def watch(
    *,
    robot_selector: str | None = None,
    poll_seconds: int = 300,
    drawer_threshold: float = 85.0,
    on_alert: Callable[[Alert], None] = deliver,
    on_status: Callable[[Snapshot], None] | None = None,
    on_session: Callable[[Session], None] | None = None,
    stop_event: asyncio.Event | None = None,
    log: Callable[[str], None] = print,
) -> int:
    """Watch one robot and notify on every change worth knowing about.

    Returns a process exit code: ``EXIT_OK`` once ``stop_event`` is set, or the
    authentication failure code when there are no usable credentials. Every
    other failure is treated as transient and retried with backoff.
    """
    from .connection import HeadlessAuthError  # noqa: PLC0415

    stop = stop_event or asyncio.Event()
    state = WatchState(drawer_threshold)
    backoff = _INITIAL_BACKOFF_SECONDS

    while not stop.is_set():
        try:
            await _watch_session(
                robot_selector=robot_selector,
                poll_seconds=max(_MIN_POLL_SECONDS, poll_seconds),
                state=state,
                on_alert=on_alert,
                on_status=on_status,
                on_session=on_session,
                stop=stop,
                log=log,
            )
            backoff = _INITIAL_BACKOFF_SECONDS
        except HeadlessAuthError as exc:
            # Code 1 is "no credentials anywhere", which no amount of waiting
            # fixes. Code 2 is the cloud refusing or unreachable — routine for a
            # watcher that starts at login, before the network is up.
            if exc.code == EXIT_NO_CREDENTIALS:
                log(f"{exc} Watcher stopping.")
                return exc.code
            log(f"{exc} — retrying in {backoff:.0f}s")
            if await _sleep_unless_stopped(stop, backoff):
                break
            backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — any cloud failure is retryable
            log(f"Connection lost ({exc}) — retrying in {backoff:.0f}s")
            if await _sleep_unless_stopped(stop, backoff):
                break
            backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)

    log("Watcher stopped.")
    return EXIT_OK


async def _watch_session(
    *,
    robot_selector: str | None,
    poll_seconds: int,
    state: WatchState,
    on_alert: Callable[[Alert], None],
    on_status: Callable[[Snapshot], None] | None,
    on_session: Callable[[Session], None] | None,
    stop: asyncio.Event,
    log: Callable[[str], None],
) -> None:
    """Hold one cloud session open, alerting until it stops or dies."""
    from .headless import open_session  # noqa: PLC0415

    session = await open_session(robot_selector)
    robot = session.robot
    log(f"Watching {getattr(robot, 'name', 'robot')} (poll every {poll_seconds}s)")
    if on_session is not None:
        on_session(session)

    updated = asyncio.Event()
    with contextlib.suppress(Exception):
        from pylitterbot.robot import EVENT_UPDATE  # noqa: PLC0415

        robot.on(EVENT_UPDATE, updated.set)
        await robot.subscribe()

    failures = 0
    try:
        while not stop.is_set():
            for alert in state.evaluate(robot):
                log(alert.message)
                await asyncio.get_running_loop().run_in_executor(None, on_alert, alert)
            if on_status is not None:
                on_status(snapshot(robot))

            updated.clear()
            if await _wait_for_change(updated, stop, poll_seconds):
                continue
            try:
                await robot.refresh()
                failures = 0
            except Exception as exc:  # noqa: BLE001 — surfaced via SessionLost below
                failures += 1
                if failures >= _REFRESH_FAILURES_BEFORE_RECONNECT:
                    raise SessionLost(str(exc)) from exc
    finally:
        await _close(session)


async def _wait_for_change(updated: asyncio.Event, stop: asyncio.Event, timeout: float) -> bool:
    """Block until the robot pushes an update or we're told to stop.

    Returns True if one of the events fired, False when the timeout expired and
    the caller should poll instead. The WebSocket is the primary signal; the
    timeout is what keeps the watcher honest when the socket goes quiet.
    """
    waiters = [asyncio.ensure_future(event.wait()) for event in (updated, stop)]
    try:
        done, _ = await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for waiter in waiters:
            waiter.cancel()
        await asyncio.gather(*waiters, return_exceptions=True)
    return bool(done)


async def _sleep_unless_stopped(stop: asyncio.Event, seconds: float) -> bool:
    """Sleep, returning True if we were asked to stop before the time was up."""
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)
        return True
    return stop.is_set()


async def _close(session: Session) -> None:
    with contextlib.suppress(Exception):
        await session.robot.unsubscribe()
    with contextlib.suppress(Exception):
        await session.account.disconnect()


class WatcherRunner:
    """Runs :func:`watch` on its own event loop in a background thread.

    Exists for the tray: pystray's AppKit and Win32 backends both insist on the
    main thread, so the asyncio side has to move off it. Everything public here
    is safe to call from the thread hosting the tray.
    """

    def __init__(self, **watch_kwargs: Any) -> None:
        self._kwargs = watch_kwargs
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._started = threading.Event()
        self.session: Session | None = None
        self.exit_code: int = EXIT_OK
        self.finished = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="asher-watcher", daemon=True)
        self._thread.start()
        self._started.wait(timeout=10)

    def _run(self) -> None:
        try:
            asyncio.run(self._main())
        finally:
            self.finished.set()

    async def _main(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        self._started.set()
        on_session = self._kwargs.pop("on_session", None)

        def remember(session: Session) -> None:
            self.session = session
            if on_session is not None:
                on_session(session)

        self.exit_code = await watch(stop_event=self._stop, on_session=remember, **self._kwargs)

    def request_stop(self) -> None:
        """Ask the watcher to shut down; safe from any thread."""
        loop, stop = self._loop, self._stop
        if loop is None or stop is None:
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(stop.set)

    def call(self, action: Callable[[Session], Coroutine[Any, Any, Any]]) -> bool:
        """Run a coroutine against the live session from another thread.

        Returns False when there is no session yet (still connecting, or the
        cloud is down) so the caller can say so rather than failing silently.
        """
        loop, session = self._loop, self.session
        if loop is None or session is None:
            return False
        with contextlib.suppress(RuntimeError):
            asyncio.run_coroutine_threadsafe(action(session), loop)
            return True
        return False

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)
