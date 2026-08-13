"""Tests for asher.autostart — login items on launchd, systemd, and the registry.

Each backend is driven directly rather than through the platform dispatch, so
all three are covered on every CI runner. External commands (``launchctl``,
``systemctl``) and ``winreg`` are mocked: what's asserted is the unit content
and the sequence of commands, not the OS accepting them.
"""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from asher import autostart
from asher.autostart import (
    AutostartError,
    LaunchdAutostart,
    RegistryAutostart,
    SystemdAutostart,
    watcher_argv,
)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every backend's on-disk location at tmp_path."""
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    return tmp_path


def _ok_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


# ── the command every backend registers ──────────────────────────────────────


class TestWatcherArgv:
    def test_runs_the_same_entry_point_as_start(self) -> None:
        """`watch run` claims the pid file, so a login watcher is stoppable too."""
        assert watcher_argv()[1:] == ["-m", "asher", "watch", "run"]

    def test_uses_this_interpreter_by_default(self) -> None:
        assert watcher_argv()[0] == autostart.sys.executable

    def test_honours_an_explicit_interpreter(self) -> None:
        assert watcher_argv(executable="/opt/py")[0] == "/opt/py"


# ── macOS ────────────────────────────────────────────────────────────────────


class TestLaunchd:
    def test_writes_a_plist_the_system_can_parse(self, home: Path) -> None:
        with patch.object(autostart, "_run", side_effect=_ok_run):
            LaunchdAutostart().enable()
        parsed = plistlib.loads(LaunchdAutostart().plist_path().read_bytes())
        assert parsed["Label"] == "com.asher-cli.watcher"
        assert parsed["ProgramArguments"] == watcher_argv()
        assert parsed["RunAtLoad"] is True

    def test_restarts_only_after_an_abnormal_exit(self, home: Path) -> None:
        """Blanket KeepAlive would have launchd undo `asher watch stop`."""
        with patch.object(autostart, "_run", side_effect=_ok_run):
            LaunchdAutostart().enable()
        parsed = plistlib.loads(LaunchdAutostart().plist_path().read_bytes())
        assert parsed["KeepAlive"] == {"SuccessfulExit": False}

    def test_escapes_a_path_that_would_break_the_xml(self, home: Path) -> None:
        with (
            patch.object(autostart, "watcher_argv", return_value=["/opt/a&b/py", "-m", "asher"]),
            patch.object(autostart, "_run", side_effect=_ok_run),
        ):
            LaunchdAutostart().enable()
        parsed = plistlib.loads(LaunchdAutostart().plist_path().read_bytes())
        assert parsed["ProgramArguments"][0] == "/opt/a&b/py"

    def test_loads_the_agent(self, home: Path) -> None:
        with patch.object(autostart, "_run", side_effect=_ok_run) as run:
            LaunchdAutostart().enable()
        assert run.call_args.args[0][:2] == ["launchctl", "load"]

    def test_disable_unloads_and_removes(self, home: Path) -> None:
        with patch.object(autostart, "_run", side_effect=_ok_run) as run:
            LaunchdAutostart().enable()
            assert LaunchdAutostart().is_enabled() is True
            LaunchdAutostart().disable()
        assert LaunchdAutostart().is_enabled() is False
        assert run.call_args.args[0][:2] == ["launchctl", "unload"]

    def test_disable_is_safe_when_nothing_is_installed(self, home: Path) -> None:
        with patch.object(autostart, "_run", side_effect=_ok_run) as run:
            LaunchdAutostart().disable()
        run.assert_not_called()


# ── Linux ────────────────────────────────────────────────────────────────────


class TestSystemd:
    def test_writes_a_user_unit(self, home: Path) -> None:
        with patch.object(autostart, "_run", side_effect=_ok_run):
            SystemdAutostart().enable()
        unit = SystemdAutostart().unit_path().read_text(encoding="utf-8")
        assert "ExecStart=" in unit
        assert "-m asher watch run" in unit
        assert "WantedBy=default.target" in unit

    def test_restarts_only_on_failure(self, home: Path) -> None:
        with patch.object(autostart, "_run", side_effect=_ok_run):
            SystemdAutostart().enable()
        assert "Restart=on-failure" in SystemdAutostart().unit_path().read_text(encoding="utf-8")

    def test_quotes_an_interpreter_path_containing_a_space(self, home: Path) -> None:
        """systemd splits ExecStart on whitespace."""
        with patch.object(
            autostart, "watcher_argv", return_value=["/opt/My Tools/py", "-m", "asher"]
        ):
            assert autostart._exec_start() == '"/opt/My Tools/py" -m asher'

    def test_enables_the_unit(self, home: Path) -> None:
        with patch.object(autostart, "_run", side_effect=_ok_run) as run:
            SystemdAutostart().enable()
        commands = [call.args[0] for call in run.call_args_list]
        assert ["systemctl", "--user", "daemon-reload"] in commands
        assert ["systemctl", "--user", "enable", "asher-watch.service"] in commands

    def test_disable_removes_the_unit(self, home: Path) -> None:
        with patch.object(autostart, "_run", side_effect=_ok_run):
            SystemdAutostart().enable()
            assert SystemdAutostart().is_enabled() is True
            SystemdAutostart().disable()
        assert SystemdAutostart().is_enabled() is False

    def test_unavailable_without_systemctl(self, home: Path) -> None:
        with patch.object(autostart.shutil, "which", return_value=None):
            reason = SystemdAutostart().unavailable_reason()
        assert reason is not None
        assert "systemd" in reason

    def test_unavailable_when_the_user_manager_is_dead(self, home: Path) -> None:
        dead = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        with (
            patch.object(autostart.shutil, "which", return_value="/bin/systemctl"),
            patch.object(autostart, "_run", return_value=dead),
        ):
            assert SystemdAutostart().unavailable_reason() is not None

    def test_available_when_the_user_manager_answers(self, home: Path) -> None:
        with (
            patch.object(autostart.shutil, "which", return_value="/bin/systemctl"),
            patch.object(autostart, "_run", side_effect=_ok_run),
        ):
            assert SystemdAutostart().unavailable_reason() is None


# ── Windows ──────────────────────────────────────────────────────────────────


class TestRegistry:
    def test_registers_a_per_user_run_value(self) -> None:
        winreg = MagicMock()
        with patch.object(autostart, "_winreg", return_value=winreg):
            RegistryAutostart().enable()
        winreg.SetValueEx.assert_called_once()
        assert winreg.SetValueEx.call_args.args[1] == "AsherWatch"

    def test_quotes_arguments_containing_spaces(self) -> None:
        # Compared against the Path-normalised form: the backend routes the
        # interpreter through Path to find pythonw.exe beside it, which rewrites
        # separators on Windows. What matters here is the quoting, not the slash.
        executable = str(Path("/opt/My Tools/python.exe"))
        with patch.object(autostart.sys, "executable", executable):
            command = RegistryAutostart()._command()
        assert command.startswith(f'"{executable}"')
        assert command.endswith("-m asher watch run")

    def test_location_names_the_value(self) -> None:
        assert RegistryAutostart().location().endswith(r"\Run\AsherWatch")

    def test_missing_value_reads_as_disabled(self) -> None:
        winreg = MagicMock()
        winreg.QueryValueEx.side_effect = OSError
        with patch.object(autostart, "_winreg", return_value=winreg):
            assert RegistryAutostart().is_enabled() is False

    def test_disable_tolerates_an_absent_value(self) -> None:
        winreg = MagicMock()
        winreg.OpenKey.side_effect = FileNotFoundError
        with patch.object(autostart, "_winreg", return_value=winreg):
            RegistryAutostart().disable()  # must not raise

    def test_reports_a_registry_write_failure(self) -> None:
        winreg = MagicMock()
        winreg.CreateKey.side_effect = OSError("access denied")
        with (
            patch.object(autostart, "_winreg", return_value=winreg),
            pytest.raises(AutostartError),
        ):
            RegistryAutostart().enable()


# ── dispatch ─────────────────────────────────────────────────────────────────


class TestBackendSelection:
    @pytest.mark.parametrize(
        ("platform", "expected"),
        [
            ("darwin", LaunchdAutostart),
            ("win32", RegistryAutostart),
            ("linux", SystemdAutostart),
        ],
    )
    def test_picks_the_platform_backend(
        self, monkeypatch: pytest.MonkeyPatch, platform: str, expected: type
    ) -> None:
        monkeypatch.setattr(autostart.sys, "platform", platform)
        assert isinstance(autostart.backend(), expected)

    def test_no_backend_on_an_unknown_platform(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(autostart.sys, "platform", "aix")
        assert autostart.backend() is None


class TestEnableDisable:
    def test_enable_reports_where_the_item_lives(self) -> None:
        target = MagicMock(name="backend")
        target.name = "launchd"
        target.unavailable_reason.return_value = None
        target.location.return_value = "/somewhere/asher.plist"
        with patch.object(autostart, "backend", return_value=target):
            ok, message = autostart.enable()
        assert ok is True
        assert "/somewhere/asher.plist" in message
        target.enable.assert_called_once()

    def test_enable_explains_an_unusable_backend(self) -> None:
        target = MagicMock()
        target.unavailable_reason.return_value = "no systemd here"
        with patch.object(autostart, "backend", return_value=target):
            ok, message = autostart.enable()
        assert ok is False
        assert "no systemd here" in message
        assert "asher watch start" in message
        target.enable.assert_not_called()

    def test_enable_surfaces_a_backend_failure(self) -> None:
        target = MagicMock()
        target.unavailable_reason.return_value = None
        target.enable.side_effect = AutostartError("launchctl said no")
        with patch.object(autostart, "backend", return_value=target):
            ok, message = autostart.enable()
        assert ok is False
        assert "launchctl said no" in message

    def test_enable_refuses_on_an_unsupported_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(autostart.sys, "platform", "aix")
        ok, _ = autostart.enable()
        assert ok is False

    def test_disable_says_so_when_nothing_is_registered(self) -> None:
        target = MagicMock()
        target.is_enabled.return_value = False
        with patch.object(autostart, "backend", return_value=target):
            ok, message = autostart.disable()
        assert ok is False
        assert message == "Autostart is not enabled."
        target.disable.assert_not_called()

    def test_disable_removes_the_item(self) -> None:
        target = MagicMock()
        target.name = "launchd"
        target.is_enabled.return_value = True
        with patch.object(autostart, "backend", return_value=target):
            ok, _ = autostart.disable()
        assert ok is True
        target.disable.assert_called_once()


class TestDescribe:
    def test_enabled(self) -> None:
        target = MagicMock()
        target.name = "launchd"
        target.unavailable_reason.return_value = None
        target.is_enabled.return_value = True
        with patch.object(autostart, "backend", return_value=target):
            assert autostart.describe() == "enabled (launchd)"

    def test_not_enabled(self) -> None:
        target = MagicMock()
        target.unavailable_reason.return_value = None
        target.is_enabled.return_value = False
        with patch.object(autostart, "backend", return_value=target):
            assert autostart.describe() == "not enabled"

    def test_unsupported_platform(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(autostart.sys, "platform", "aix")
        assert autostart.describe() == "unsupported on this platform"


class TestRunHelper:
    def test_missing_command_becomes_an_autostart_error(self) -> None:
        with (
            patch.object(autostart.shutil, "which", return_value=None),
            pytest.raises(AutostartError, match="not found"),
        ):
            autostart._run(["launchctl", "load"])

    def test_non_zero_exit_reports_stderr(self) -> None:
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")
        with (
            patch.object(autostart.shutil, "which", return_value="/bin/launchctl"),
            patch.object(autostart.subprocess, "run", return_value=failed),
            pytest.raises(AutostartError, match="boom"),
        ):
            autostart._run(["launchctl", "load"])

    def test_check_false_returns_the_failure(self) -> None:
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")
        with (
            patch.object(autostart.shutil, "which", return_value="/bin/systemctl"),
            patch.object(autostart.subprocess, "run", return_value=failed),
        ):
            assert autostart._run(["systemctl", "x"], check=False).returncode == 1

    def test_never_uses_a_shell(self) -> None:
        with (
            patch.object(autostart.shutil, "which", return_value="/bin/launchctl"),
            patch.object(autostart.subprocess, "run", side_effect=_ok_run) as run,
        ):
            autostart._run(["launchctl", "list"])
        assert run.call_args.kwargs.get("shell", False) is False
        assert run.call_args.args[0][0] == "/bin/launchctl"
