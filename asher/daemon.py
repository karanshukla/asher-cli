"""Detached watcher process — notifications that outlive the terminal.

``asher watch start`` re-executes this interpreter as ``python -m asher watch
run`` in a new session (POSIX) or a detached process (Windows), with its output
redirected to a log file. The shell that launched it can then close without
taking the watcher — and the notifications — down with it.

A PID file in ``~/.asher-cli`` is how ``stop`` and ``status`` find the process
again. That is the same bet every pidfile-based daemon makes: a PID can in
principle be recycled by an unrelated process between runs, so liveness checks
are corroborated with the process's own command line wherever the platform
makes that cheap.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess  # nosec B404 # one call site, fixed argv on this interpreter, no shell
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from . import autostart, config
from .export import EXIT_COMMAND_REJECTED, EXIT_OK

_RUNTIME_DIR = Path.home() / ".asher-cli"
_PID_PATH = _RUNTIME_DIR / "watch.pid"
_LOG_PATH = _RUNTIME_DIR / "watch.log"

_LOG_SIZE_LIMIT_BYTES = 1_000_000
_STARTUP_GRACE_SECONDS = 5.0
_TERM_GRACE_SECONDS = 5.0
_KILL_GRACE_SECONDS = 3.0
_DEFAULT_POLL_SECONDS = 300

ACTIONS = ("start", "stop", "status", "run", "enable", "disable")


def pid_path() -> Path:
    return _PID_PATH


def log_path() -> Path:
    return _LOG_PATH


# ── pid file ─────────────────────────────────────────────────────────────────


def read_pid() -> int | None:
    """Return the PID recorded in the pid file, or None if absent/unreadable."""
    try:
        raw = _PID_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def write_pid(pid: int) -> None:
    _PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PID_PATH.write_text(f"{pid}\n", encoding="utf-8")


def clear_pid() -> None:
    with contextlib.suppress(OSError):
        _PID_PATH.unlink()


def running_pid() -> int | None:
    """Return the live watcher's PID, clearing the pid file if it's stale."""
    pid = read_pid()
    if pid is None:
        return None
    if pid_alive(pid) and _pid_is_watcher(pid):
        return pid
    clear_pid()
    return None


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _windows_pid_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _windows_pid_alive(pid: int) -> bool:
    """Ask the kernel, because ``os.kill(pid, 0)`` *terminates* the target here.

    Windows has no signals: CPython maps every ``os.kill`` signal other than the
    two console-control events onto ``TerminateProcess``, so the usual POSIX
    "signal 0 means are-you-there" idiom would kill the watcher it is checking.
    """
    import ctypes  # noqa: PLC0415

    still_active = 259
    query_limited_information = 0x1000

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(query_limited_information, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _pid_is_watcher(pid: int) -> bool:
    """Best-effort guard against a PID the OS has recycled.

    Only Linux exposes another process's argv cheaply; elsewhere an unreadable
    command line means "can't tell", which resolves in the pid file's favour.
    """
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return True
    return b"asher" in cmdline


# ── lifecycle ────────────────────────────────────────────────────────────────


def start(*, robot: str | None = None, tray: bool = True) -> tuple[bool, str]:
    """Spawn a detached watcher process. Returns ``(started, message)``."""
    from .connection import credentials_available  # noqa: PLC0415

    existing = running_pid()
    if existing is not None:
        return False, f"Watcher already running (pid {existing}) — `asher watch stop` to stop it."

    # The watcher claims the pid file before it authenticates, so it registers
    # successfully and *then* stops — which reported a pid for a process that
    # was already gone, tray and all. Refusing here keeps the failure in the
    # terminal the user is looking at.
    if not credentials_available():
        return False, "\n".join(
            [
                "No credentials found — the watcher would start and immediately stop.",
                "  fix: run `asher` and sign in with /login, then try again.",
            ]
        )

    log = log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    _truncate_oversized_log(log)

    argv = [sys.executable, "-m", "asher", "watch", "run"]
    if robot:
        argv += ["--robot", robot]
    if not tray:
        argv.append("--no-tray")

    try:
        with log.open("a", encoding="utf-8") as stream:
            process = subprocess.Popen(  # nosec B603 # fixed argv on this interpreter, no shell
                argv,
                stdout=stream,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                cwd=str(log.parent),
                **_detach_kwargs(),
            )
    except OSError as exc:
        return False, f"Could not start watcher: {exc}"

    if not _wait_until_registered(process):
        return False, f"Watcher exited immediately (code {process.returncode}). See {log}"

    return True, "\n".join(
        [
            f"Watcher started (pid {process.pid}) — notifications continue after this terminal closes.",
            f"  log:  {log}",
            "  stop: asher watch stop",
        ]
    )


def enable_autostart(*, robot: str | None = None, tray: bool = True) -> tuple[bool, str]:
    """Register the login item and start watching now.

    `systemctl enable --now` semantics: nobody asking for notifications at login
    wants to wait until the next one to get any.
    """
    ok, message = autostart.enable()
    if not ok:
        return ok, message
    if running_pid() is not None:
        return True, message
    _, start_message = start(robot=robot, tray=tray)
    return True, f"{message}\n{start_message}"


def _wait_until_registered(process: subprocess.Popen[bytes]) -> bool:
    """Wait for the child to claim the pid file, or report that it died trying.

    A watcher that falls over on the way up (bad install, unimportable
    dependency) would otherwise be reported as started. Waiting for the pid file
    rather than sleeping a fixed interval also means ``asher watch status`` run
    immediately after ``start`` sees a registered watcher.
    """
    deadline = time.monotonic() + _STARTUP_GRACE_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        if read_pid() == process.pid:
            return True
        time.sleep(0.05)
    if process.poll() is not None:
        return False
    # Alive but slow to register — record it so `stop` can still find it.
    write_pid(process.pid)
    return True


def _detach_kwargs() -> dict[str, Any]:
    """Popen flags that cut the child loose from this terminal."""
    if sys.platform == "win32":
        detached_process = 0x00000008
        create_new_process_group = 0x00000200
        return {"creationflags": detached_process | create_new_process_group}
    return {"start_new_session": True}


def stop() -> tuple[bool, str]:
    """Stop the running watcher. Returns ``(stopped, message)``.

    SIGTERM first so the watcher can unsubscribe and close its cloud session,
    then SIGKILL if it doesn't go. The escalation matters because a tray-hosted
    watcher parks the main thread inside a native GUI loop, where a Python
    signal handler may not get a chance to run — and a watcher has no state
    worth preserving anyway.
    """
    pid = running_pid()
    if pid is None:
        return False, "No watcher is running."

    if not _signal_and_wait(pid, signal.SIGTERM, _TERM_GRACE_SECONDS):
        kill = getattr(signal, "SIGKILL", signal.SIGTERM)
        if not _signal_and_wait(pid, kill, _KILL_GRACE_SECONDS):
            return False, f"Watcher (pid {pid}) is not responding."

    clear_pid()
    return True, f"Watcher stopped (pid {pid})."


def _signal_and_wait(pid: int, sig: int, timeout: float) -> bool:
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            return True
        time.sleep(0.1)
    return not pid_alive(pid)


def status() -> tuple[bool, str]:
    """Report whether a watcher is running, with the tail of its log."""
    pid = running_pid()
    if pid is None:
        return False, "\n".join(
            [
                "Watcher: not running  (start it with `asher watch start`)",
                f"  autostart: {autostart.describe()}",
            ]
        )

    lines = [
        f"Watcher: running (pid {pid})",
        f"  autostart: {autostart.describe()}",
        f"  log: {log_path()}",
    ]
    lines += [f"  | {entry}" for entry in _log_tail(3)]
    return True, "\n".join(lines)


def _log_tail(count: int) -> list[str]:
    try:
        entries = _LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [entry for entry in entries if entry.strip()][-count:]


def _truncate_oversized_log(log: Path) -> None:
    """Keep the log from growing without bound across many restarts."""
    with contextlib.suppress(OSError):
        if log.exists() and log.stat().st_size > _LOG_SIZE_LIMIT_BYTES:
            log.unlink()


# ── the watcher process itself ───────────────────────────────────────────────


def run_foreground(*, robot: str | None = None, tray: bool = True) -> int:
    """Run the watcher in this process — what the detached child executes.

    Also what launchd/systemd/the registry run at login, and the way to debug a
    watcher that isn't behaving: the same code path, with the log on your
    terminal instead of in a file.
    """
    existing = running_pid()
    if existing is not None:
        _log_line(f"A watcher is already running (pid {existing}) — not starting a second.")
        return EXIT_COMMAND_REJECTED
    with _pid_file_held():
        return _watch_here(robot=robot, tray=tray)


@contextlib.contextmanager
def _pid_file_held() -> Iterator[None]:
    """Own the pid file for this process's lifetime.

    The watcher writes its own pid rather than relying on whoever spawned it,
    because at login nobody did: launchd and systemd start it directly, and a
    watcher `stop` and `status` can't see is a watcher you can't turn off.
    """
    write_pid(os.getpid())
    try:
        yield
    finally:
        if read_pid() == os.getpid():
            clear_pid()


def _watch_here(*, robot: str | None, tray: bool) -> int:
    import asyncio  # noqa: PLC0415

    settings = config.load()
    poll = int(settings.get("poll_interval_seconds") or _DEFAULT_POLL_SECONDS)
    threshold = float(settings.get("watch_drawer_threshold", 85))
    poll_seconds = poll if poll > 0 else _DEFAULT_POLL_SECONDS

    if tray and settings.get("watch_tray", True):
        from . import tray as tray_module  # noqa: PLC0415

        if tray_module.is_available():
            return tray_module.run(
                robot_selector=robot,
                poll_seconds=poll_seconds,
                drawer_threshold=threshold,
                log=_log_line,
            )
        _log_line("No system tray available — watching without one.")

    return asyncio.run(
        _run_until_signalled(
            robot_selector=robot, poll_seconds=poll_seconds, drawer_threshold=threshold
        )
    )


async def _run_until_signalled(
    *, robot_selector: str | None, poll_seconds: int, drawer_threshold: float
) -> int:
    """Run the watcher, wiring SIGTERM/SIGINT to a clean shutdown."""
    import asyncio  # noqa: PLC0415

    from .watcher import watch  # noqa: PLC0415

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError, AttributeError, ValueError, OSError):
            loop.add_signal_handler(sig, stop.set)
    return await watch(
        robot_selector=robot_selector,
        poll_seconds=poll_seconds,
        drawer_threshold=drawer_threshold,
        stop_event=stop,
        log=_log_line,
    )


def _log_line(message: str) -> None:
    """Timestamped line on stdout — which the detached child has as its log."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


# ── CLI entry ────────────────────────────────────────────────────────────────


def dispatch(action: str, *, robot: str | None = None, tray: bool = True) -> int:
    """Run one ``asher watch <action>`` and return a process exit code."""
    if action == "run":
        return run_foreground(robot=robot, tray=tray)

    handlers = {
        "start": lambda: start(robot=robot, tray=tray),
        "stop": stop,
        "status": status,
        "enable": lambda: enable_autostart(robot=robot, tray=tray),
        "disable": autostart.disable,
    }
    handler = handlers.get(action)
    if handler is None:
        print(f"Unknown watch action '{action}' — use {', '.join(ACTIONS)}.", file=sys.stderr)
        return EXIT_COMMAND_REJECTED

    ok, message = handler()
    print(message, file=sys.stdout if ok else sys.stderr)
    # `status` reporting "not running" is a truthful answer, not a failed
    # command, but scripts want to branch on it — hence the non-zero exit.
    return EXIT_OK if ok else EXIT_COMMAND_REJECTED
