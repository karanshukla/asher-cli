"""Start the watcher at login, using each platform's own supervisor.

``asher watch start`` survives closing the terminal, but not logging out or
rebooting. This registers the watcher with whatever already runs things at
login on this machine — launchd, systemd's user manager, or the Windows
registry's Run key — so notifications resume without anyone typing a command.

One backend per platform, behind :class:`AutostartBackend`, mirroring the
adapter pattern in :mod:`asher.robot_adapters`. Each writes a unit that runs
``python -m asher watch run``: the same entry point ``start`` spawns, which
claims the pid file itself, so a login-started watcher is visible to ``asher
watch status`` and stoppable with ``asher watch stop`` exactly like a manual
one.

Deliberately *not* a package installer. Nothing here writes outside the user's
own login-item locations, nothing needs administrator rights, and ``disable``
removes exactly what ``enable`` created.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess  # nosec B404 # fixed argv from shutil.which, no shell
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

_LABEL = "com.asher-cli.watcher"
_SERVICE_NAME = "asher-watch"
_REGISTRY_VALUE = "AsherWatch"
_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_COMMAND_TIMEOUT_SECONDS = 20


class AutostartError(Exception):
    """Registering or removing the login item failed."""


def watcher_argv(*, executable: str | None = None) -> list[str]:
    """The command a login supervisor should run.

    ``sys.executable`` rather than the ``asher`` console script: under pipx and
    ``uv tool`` the interpreter path is the stable one, and going through
    ``-m asher`` avoids depending on the user's PATH, which login supervisors
    frequently don't share with an interactive shell.
    """
    return [executable or sys.executable, "-m", "asher", "watch", "run"]


class AutostartBackend(ABC):
    """One platform's way of running something at login."""

    name: str = ""

    @abstractmethod
    def location(self) -> str:
        """Where the login item lives, for humans to inspect or delete."""

    @abstractmethod
    def is_enabled(self) -> bool: ...

    @abstractmethod
    def enable(self) -> None: ...

    @abstractmethod
    def disable(self) -> None: ...

    def unavailable_reason(self) -> str | None:
        """Why this backend can't be used here, or None when it can."""
        return None


# ── macOS ────────────────────────────────────────────────────────────────────


_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
{arguments}
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
</dict>
</plist>
"""


class LaunchdAutostart(AutostartBackend):
    """macOS launchd user agent in ``~/Library/LaunchAgents``.

    ``KeepAlive`` is scoped to ``SuccessfulExit=false`` rather than set outright:
    a crashed watcher should come back, but ``asher watch stop`` exits cleanly
    and must stay stopped. Blanket ``KeepAlive`` would have launchd fight the
    stop command.
    """

    name = "launchd"

    def plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{_LABEL}.plist"

    def location(self) -> str:
        return str(self.plist_path())

    def is_enabled(self) -> bool:
        return self.plist_path().exists()

    def enable(self) -> None:
        from .daemon import log_path  # noqa: PLC0415

        path = self.plist_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        arguments = "\n".join(f"    <string>{_xml_escape(arg)}</string>" for arg in watcher_argv())
        log = log_path()
        log.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _PLIST_TEMPLATE.format(label=_LABEL, arguments=arguments, log=_xml_escape(str(log))),
            encoding="utf-8",
        )
        _run(["launchctl", "unload", str(path)], check=False)
        _run(["launchctl", "load", "-w", str(path)])

    def disable(self) -> None:
        path = self.plist_path()
        if path.exists():
            _run(["launchctl", "unload", "-w", str(path)], check=False)
        with contextlib.suppress(OSError):
            path.unlink()


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── Linux ────────────────────────────────────────────────────────────────────


_UNIT_TEMPLATE = """[Unit]
Description=Asher CLI Litter Robot watcher
After=graphical-session.target

[Service]
Type=simple
ExecStart={command}
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
"""


def _exec_start() -> str:
    """Render ``ExecStart``, quoting any argument containing a space.

    systemd splits the line on whitespace, so an interpreter living under a
    path with a space in it would otherwise be read as two arguments.
    """
    return " ".join(f'"{arg}"' if " " in arg else arg for arg in watcher_argv())


class SystemdAutostart(AutostartBackend):
    """Linux systemd user unit in ``~/.config/systemd/user``.

    ``Restart=on-failure`` for the same reason launchd gets a scoped
    ``KeepAlive``: bring a crashed watcher back, leave a stopped one stopped.
    """

    name = "systemd --user"

    def unit_path(self) -> Path:
        config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        return Path(config_home) / "systemd" / "user" / f"{_SERVICE_NAME}.service"

    def location(self) -> str:
        return str(self.unit_path())

    def unavailable_reason(self) -> str | None:
        if shutil.which("systemctl") is None:
            return "systemctl not found — this system doesn't use systemd."
        try:
            result = _run(["systemctl", "--user", "show-environment"], check=False)
        except AutostartError:
            return "systemd's user manager is not reachable from this session."
        if result.returncode != 0:
            return "systemd's user manager is not running for this user."
        return None

    def is_enabled(self) -> bool:
        return self.unit_path().exists()

    def enable(self) -> None:
        path = self.unit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_UNIT_TEMPLATE.format(command=_exec_start()), encoding="utf-8")
        _run(["systemctl", "--user", "daemon-reload"])
        _run(["systemctl", "--user", "enable", f"{_SERVICE_NAME}.service"])

    def disable(self) -> None:
        _run(["systemctl", "--user", "disable", f"{_SERVICE_NAME}.service"], check=False)
        with contextlib.suppress(OSError):
            self.unit_path().unlink()
        _run(["systemctl", "--user", "daemon-reload"], check=False)


# ── Windows ──────────────────────────────────────────────────────────────────


def _winreg() -> Any:
    """The stdlib ``winreg``, loaded dynamically.

    typeshed gates ``winreg`` behind ``sys.platform == "win32"``, so a plain
    import is an error on every non-Windows machine mypy runs on — which is
    also every machine where it would have checked these calls. Importing by
    name costs nothing real and keeps the module import-safe off Windows.
    """
    import importlib  # noqa: PLC0415

    return importlib.import_module("winreg")


class RegistryAutostart(AutostartBackend):
    """Windows ``HKCU\\...\\CurrentVersion\\Run`` value.

    Per-user, so it needs no administrator rights, and it's a single value to
    delete if this ever needs undoing by hand.
    """

    name = "the Windows registry"

    def location(self) -> str:
        return f"HKCU\\{_REGISTRY_KEY}\\{_REGISTRY_VALUE}"

    def _command(self) -> str:
        # pythonw.exe runs without a console, so login doesn't flash a black
        # window. It sits next to python.exe in every CPython layout.
        executable = Path(sys.executable)
        windowless = executable.with_name("pythonw.exe")
        argv = watcher_argv(executable=str(windowless if windowless.exists() else executable))
        return " ".join(f'"{arg}"' if " " in arg else arg for arg in argv)

    def is_enabled(self) -> bool:
        winreg = _winreg()
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REGISTRY_KEY) as key:
                winreg.QueryValueEx(key, _REGISTRY_VALUE)
        except OSError:
            return False
        return True

    def enable(self) -> None:
        winreg = _winreg()
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REGISTRY_KEY) as key:
                winreg.SetValueEx(key, _REGISTRY_VALUE, 0, winreg.REG_SZ, self._command())
        except OSError as exc:
            raise AutostartError(f"Could not write the registry Run value: {exc}") from exc

    def disable(self) -> None:
        winreg = _winreg()
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _REGISTRY_KEY, 0, winreg.KEY_WRITE
            ) as key:
                winreg.DeleteValue(key, _REGISTRY_VALUE)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise AutostartError(f"Could not remove the registry Run value: {exc}") from exc


# ── dispatch ─────────────────────────────────────────────────────────────────


def backend() -> AutostartBackend | None:
    """The login-item backend for this platform, or None if there isn't one."""
    if sys.platform == "darwin":
        return LaunchdAutostart()
    if sys.platform == "win32":
        return RegistryAutostart()
    if sys.platform.startswith("linux"):
        return SystemdAutostart()
    return None


def _run(argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a login-supervisor command, translating failure into AutostartError."""
    executable = shutil.which(argv[0])
    if executable is None:
        raise AutostartError(f"{argv[0]} not found on PATH.")
    try:
        result = subprocess.run(  # nosec B603 # fixed argv from shutil.which, no shell
            [executable, *argv[1:]],
            capture_output=True,
            text=True,
            timeout=_COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AutostartError(f"{argv[0]} failed: {exc}") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise AutostartError(f"{' '.join(argv)} failed: {detail or result.returncode}")
    return result


def enable() -> tuple[bool, str]:
    """Register the watcher to start at login. Returns ``(ok, message)``."""
    target = backend()
    if target is None:
        return False, f"No login-item support for this platform ({sys.platform})."
    reason = target.unavailable_reason()
    if reason is not None:
        return False, f"{reason}\n{_manual_hint()}"
    try:
        target.enable()
    except AutostartError as exc:
        return False, f"Could not enable autostart: {exc}"
    return True, "\n".join(
        [
            f"Autostart enabled via {target.name} — the watcher will start when you log in.",
            f"  item: {target.location()}",
            "  off:  asher watch disable",
        ]
    )


def disable() -> tuple[bool, str]:
    """Remove the login item. Returns ``(ok, message)``."""
    target = backend()
    if target is None:
        return False, f"No login-item support for this platform ({sys.platform})."
    if not target.is_enabled():
        return False, "Autostart is not enabled."
    try:
        target.disable()
    except AutostartError as exc:
        return False, f"Could not disable autostart: {exc}"
    return True, f"Autostart disabled — removed the {target.name} login item."


def describe() -> str:
    """One line on the current autostart state, for ``watch status``."""
    target = backend()
    if target is None:
        return "unsupported on this platform"
    if target.unavailable_reason() is not None:
        return "unavailable"
    return f"enabled ({target.name})" if target.is_enabled() else "not enabled"


def _manual_hint() -> str:
    return "Run `asher watch start` from your shell profile or session autostart instead."
