"""Open the Asher TUI from the tray, in a terminal of its own.

The tray lives in a detached process with no terminal attached, so "Open Asher"
can't simply run the app — it has to find something to run it *in*. Each
platform gets there differently: Windows hands a fresh console to any child that
asks for one, macOS drives Terminal.app through AppleScript, and Linux has to go
looking for whichever emulator happens to be installed, since it has no single
answer to "the terminal".

Like :mod:`asher.autostart`, nothing here needs elevated rights and every
failure is reported rather than raised — a tray menu item that can't find a
terminal should say so, not take the watcher down with it.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess  # nosec B404 # fixed argv from shutil.which/sys.executable, no shell
import sys

from .helpers import applescript_string

_WINDOWS_NEW_CONSOLE = 0x00000010

# Each entry is the emulator and the flag that means "the rest is the command".
# Ordered generically; _ordered_terminals() promotes the running desktop's own.
_LINUX_TERMINALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("x-terminal-emulator", ("-e",)),
    ("konsole", ("-e",)),
    ("ptyxis", ("--",)),
    ("kgx", ("--",)),
    ("gnome-terminal", ("--",)),
    ("xfce4-terminal", ("-x",)),
    ("alacritty", ("-e",)),
    ("kitty", ()),
    ("foot", ()),
    ("wezterm", ("start", "--")),
    ("xterm", ("-e",)),
)

_DESKTOP_TERMINALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("KDE", ("konsole",)),
    ("GNOME", ("ptyxis", "kgx", "gnome-terminal")),
    ("XFCE", ("xfce4-terminal",)),
)


def app_argv() -> list[str]:
    """The command that starts the TUI.

    ``sys.executable -m asher`` for the same reason
    :func:`asher.autostart.watcher_argv` uses it: under pipx and ``uv tool`` the
    interpreter path is the stable one, and it avoids depending on a ``PATH``
    that a detached tray process may not share with an interactive shell.
    """
    return [sys.executable, "-m", "asher"]


def open_app() -> tuple[bool, str]:
    """Launch the TUI in a new terminal window. Returns ``(opened, message)``."""
    if sys.platform == "win32":
        return _open_windows()
    if sys.platform == "darwin":
        return _open_macos()
    return _open_linux()


def _open_windows() -> tuple[bool, str]:
    """Ask Windows for a console; console apps get a window with no emulator hunt."""
    try:
        subprocess.Popen(  # nosec B603 # fixed argv on this interpreter, no shell
            app_argv(),
            creationflags=_WINDOWS_NEW_CONSOLE,
            close_fds=True,
        )
    except OSError as exc:
        return False, f"Could not open Asher: {exc}"
    return True, "Opened Asher in a new window."


def _open_macos() -> tuple[bool, str]:
    """Hand the command to Terminal.app, which owns window creation on macOS."""
    osascript = shutil.which("osascript")
    if osascript is None:
        return False, "Could not open Asher: osascript is not available."
    command = shlex.join(app_argv())
    script = f'tell application "Terminal" to do script {applescript_string(command)}'
    try:
        subprocess.Popen(  # nosec B603 # fixed argv from shutil.which, no shell
            [osascript, "-e", script, "-e", 'tell application "Terminal" to activate'],
            close_fds=True,
        )
    except OSError as exc:
        return False, f"Could not open Asher: {exc}"
    return True, "Opened Asher in Terminal."


def _open_linux() -> tuple[bool, str]:
    """Try the installed emulators in turn, preferring the running desktop's own."""
    for name, prefix in _ordered_terminals():
        executable = shutil.which(name)
        if executable is None:
            continue
        try:
            subprocess.Popen(  # nosec B603 # fixed argv from shutil.which, no shell
                [executable, *prefix, *app_argv()],
                start_new_session=True,
                close_fds=True,
            )
        except OSError:
            continue
        return True, f"Opened Asher in {name}."
    return False, "Could not open Asher: no terminal emulator found."


def _ordered_terminals() -> list[tuple[str, tuple[str, ...]]]:
    """The candidate list with this desktop's own emulator moved to the front.

    Without this a KDE session that happens to have gnome-terminal installed
    would open a GNOME window, which works but looks foreign.
    """
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    preferred: tuple[str, ...] = ()
    for token, names in _DESKTOP_TERMINALS:
        if token in desktop:
            preferred = names
            break
    if not preferred:
        return list(_LINUX_TERMINALS)
    rank = {name: index for index, name in enumerate(preferred)}
    return sorted(_LINUX_TERMINALS, key=lambda entry: rank.get(entry[0], len(rank)))
