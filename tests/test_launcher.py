"""Tests for asher.launcher — opening the TUI from the tray.

Each platform path is driven directly rather than through ``sys.platform``
dispatch, so the macOS and Windows branches stay covered on the Linux CI
runner. Nothing here may actually spawn a terminal, so ``Popen`` is always
mocked; the contract under test is the argv built and the ``(ok, message)``
pair reported back to the tray.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any
from unittest.mock import patch

import pytest

from asher import launcher


def _which(available: set[str]) -> Any:
    return lambda name: f"/usr/bin/{name}" if name in available else None


# ── the command ──────────────────────────────────────────────────────────────


class TestAppArgv:
    def test_runs_this_interpreter_as_a_module(self) -> None:
        """Not the `asher` console script — a tray process may not share PATH."""
        assert launcher.app_argv() == [sys.executable, "-m", "asher"]


# ── Linux ────────────────────────────────────────────────────────────────────


class TestLinux:
    def test_runs_the_tui_in_the_found_terminal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
        with (
            patch.object(launcher.shutil, "which", _which({"konsole"})),
            patch.object(launcher.subprocess, "Popen") as popen,
        ):
            ok, message = launcher._open_linux()
        assert ok is True
        assert "konsole" in message
        assert popen.call_args.args[0] == ["/usr/bin/konsole", "-e", *launcher.app_argv()]

    def test_detaches_so_closing_the_terminal_cannot_kill_the_watcher(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
        with (
            patch.object(launcher.shutil, "which", _which({"xterm"})),
            patch.object(launcher.subprocess, "Popen") as popen,
        ):
            launcher._open_linux()
        assert popen.call_args.kwargs["start_new_session"] is True

    def test_reports_when_no_terminal_is_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
        with patch.object(launcher.shutil, "which", _which(set())):
            ok, message = launcher._open_linux()
        assert ok is False
        assert "no terminal emulator" in message

    def test_moves_on_when_a_terminal_refuses_to_launch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A present-but-unusable emulator must not end the search."""
        monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
        attempts: list[str] = []

        def popen(argv: list[str], **_kwargs: Any) -> Any:
            attempts.append(argv[0])
            if argv[0].endswith("konsole"):
                raise OSError("broken")
            return object()

        with (
            patch.object(launcher.shutil, "which", _which({"konsole", "xterm"})),
            patch.object(launcher.subprocess, "Popen", side_effect=popen),
        ):
            ok, message = launcher._open_linux()
        assert ok is True
        assert "xterm" in message
        assert [a.split("/")[-1] for a in attempts] == ["konsole", "xterm"]

    @pytest.mark.parametrize(
        ("desktop", "expected"),
        [("KDE", "konsole"), ("GNOME", "ptyxis"), ("XFCE", "xfce4-terminal")],
    )
    def test_prefers_the_running_desktops_own_terminal(
        self, monkeypatch: pytest.MonkeyPatch, desktop: str, expected: str
    ) -> None:
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", desktop)
        installed = {"konsole", "ptyxis", "xfce4-terminal", "xterm"}
        with (
            patch.object(launcher.shutil, "which", _which(installed)),
            patch.object(launcher.subprocess, "Popen") as popen,
        ):
            launcher._open_linux()
        assert popen.call_args.args[0][0].endswith(expected)

    def test_desktop_string_may_be_compound(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """XDG_CURRENT_DESKTOP is colon-separated, e.g. `ubuntu:GNOME`."""
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
        with (
            patch.object(launcher.shutil, "which", _which({"konsole", "gnome-terminal"})),
            patch.object(launcher.subprocess, "Popen") as popen,
        ):
            launcher._open_linux()
        assert popen.call_args.args[0][0].endswith("gnome-terminal")

    def test_every_candidate_is_ranked_exactly_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
        ordered = launcher._ordered_terminals()
        assert sorted(ordered) == sorted(launcher._LINUX_TERMINALS)


# ── macOS ────────────────────────────────────────────────────────────────────


class TestMacos:
    def test_drives_terminal_app(self) -> None:
        with (
            patch.object(launcher.shutil, "which", return_value="/usr/bin/osascript"),
            patch.object(launcher.subprocess, "Popen") as popen,
        ):
            ok, message = launcher._open_macos()
        assert ok is True
        assert "Terminal" in message
        argv = popen.call_args.args[0]
        assert argv[0] == "/usr/bin/osascript"
        assert "do script" in argv[2]
        assert "activate" in argv[4]

    def test_quotes_an_interpreter_path_containing_spaces(self) -> None:
        """The command is embedded in AppleScript source, then run by a shell."""
        with (
            patch.object(launcher.shutil, "which", return_value="/usr/bin/osascript"),
            patch.object(launcher.subprocess, "Popen") as popen,
            patch.object(launcher.sys, "executable", "/Applications/My Python/bin/python"),
        ):
            launcher._open_macos()
        script = popen.call_args.args[0][2]
        assert "'/Applications/My Python/bin/python'" in script

    def test_reports_a_missing_osascript(self) -> None:
        with patch.object(launcher.shutil, "which", return_value=None):
            ok, message = launcher._open_macos()
        assert ok is False
        assert "osascript" in message


# ── Windows ──────────────────────────────────────────────────────────────────


class TestWindows:
    def test_asks_windows_for_a_console(self) -> None:
        with patch.object(launcher.subprocess, "Popen") as popen:
            ok, _ = launcher._open_windows()
        assert ok is True
        assert popen.call_args.args[0] == launcher.app_argv()
        assert popen.call_args.kwargs["creationflags"] == launcher._WINDOWS_NEW_CONSOLE

    def test_reports_a_failure_to_launch(self) -> None:
        with patch.object(launcher.subprocess, "Popen", side_effect=OSError("denied")):
            ok, message = launcher._open_windows()
        assert ok is False
        assert "denied" in message


# ── dispatch ─────────────────────────────────────────────────────────────────


class TestOpenApp:
    @pytest.mark.parametrize(
        ("platform", "expected"),
        [("win32", "_open_windows"), ("darwin", "_open_macos"), ("linux", "_open_linux")],
    )
    def test_routes_to_the_platform_path(
        self, monkeypatch: pytest.MonkeyPatch, platform: str, expected: str
    ) -> None:
        monkeypatch.setattr(sys, "platform", platform)
        with patch.object(launcher, expected, return_value=(True, "ok")) as target:
            assert launcher.open_app() == (True, "ok")
        target.assert_called_once()

    def test_never_raises_when_the_platform_call_fails(self) -> None:
        """The tray calls this from a menu handler — an exception there is fatal."""
        with patch.object(launcher.subprocess, "Popen", side_effect=OSError("nope")):
            ok, _ = launcher.open_app()
        assert ok is False


def test_module_spawns_nothing_at_import() -> None:
    """Importing must not touch the terminal — the tray imports this eagerly."""
    with patch.object(subprocess, "Popen", side_effect=AssertionError("spawned")):
        import importlib  # noqa: PLC0415

        importlib.reload(launcher)
