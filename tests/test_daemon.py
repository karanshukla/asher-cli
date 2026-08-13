"""Tests for asher.daemon — pid-file bookkeeping and watcher process control.

Real file I/O against ``tmp_path`` via patched module path constants, in the
style of ``tests/test_config.py``. Nothing here spawns a watcher: ``Popen`` and
``os.kill`` are mocked, so the tests assert the bookkeeping around the process
rather than the process itself.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from asher import daemon
from asher.export import EXIT_COMMAND_REJECTED, EXIT_OK


@pytest.fixture
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the pid/log files so tests never touch the real home dir.

    Credentials are forced present so ``start``'s pre-flight doesn't make these
    tests depend on whatever is in the runner's keyring; the pre-flight has its
    own tests below.
    """
    monkeypatch.setattr(daemon, "_PID_PATH", tmp_path / "watch.pid")
    monkeypatch.setattr(daemon, "_LOG_PATH", tmp_path / "watch.log")
    monkeypatch.setattr(daemon, "_STARTUP_GRACE_SECONDS", 0)
    monkeypatch.setattr("asher.connection.credentials_available", lambda: True)
    return tmp_path


# ── pid file ─────────────────────────────────────────────────────────────────


class TestPidFile:
    def test_missing_file_reads_as_none(self, runtime: Path) -> None:
        assert daemon.read_pid() is None

    def test_round_trips_a_pid(self, runtime: Path) -> None:
        daemon.write_pid(4242)
        assert daemon.read_pid() == 4242

    def test_garbage_reads_as_none(self, runtime: Path) -> None:
        daemon.pid_path().write_text("not-a-pid\n", encoding="utf-8")
        assert daemon.read_pid() is None

    def test_clear_is_idempotent(self, runtime: Path) -> None:
        daemon.clear_pid()
        daemon.write_pid(1)
        daemon.clear_pid()
        assert daemon.read_pid() is None


@pytest.fixture
def posix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the POSIX branch of ``pid_alive`` so its tests run on Windows too."""
    monkeypatch.setattr(daemon.sys, "platform", "linux")


class TestPidAlive:
    def test_this_process_is_alive(self) -> None:
        """Unpinned on purpose — exercises the real branch for the host platform."""
        assert daemon.pid_alive(os.getpid()) is True

    def test_pid_zero_is_never_alive(self) -> None:
        assert daemon.pid_alive(0) is False

    def test_missing_process_is_not_alive(self, posix: None) -> None:
        with patch.object(daemon.os, "kill", side_effect=ProcessLookupError):
            assert daemon.pid_alive(4242) is False

    def test_another_users_process_counts_as_alive(self, posix: None) -> None:
        with patch.object(daemon.os, "kill", side_effect=PermissionError):
            assert daemon.pid_alive(4242) is True

    def test_windows_never_signals_to_test_liveness(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``os.kill(pid, 0)`` terminates the target on Windows — it must not be reached."""
        monkeypatch.setattr(daemon.sys, "platform", "win32")
        with (
            patch.object(daemon, "_windows_pid_alive", return_value=True) as windows_check,
            patch.object(daemon.os, "kill") as kill,
        ):
            assert daemon.pid_alive(4242) is True
        windows_check.assert_called_once_with(4242)
        kill.assert_not_called()


class TestRunningPid:
    def test_reports_a_live_watcher(self, runtime: Path) -> None:
        daemon.write_pid(4242)
        with (
            patch.object(daemon, "pid_alive", return_value=True),
            patch.object(daemon, "_pid_is_watcher", return_value=True),
        ):
            assert daemon.running_pid() == 4242

    def test_stale_pid_file_is_cleared(self, runtime: Path) -> None:
        daemon.write_pid(4242)
        with patch.object(daemon, "pid_alive", return_value=False):
            assert daemon.running_pid() is None
        assert daemon.read_pid() is None

    def test_recycled_pid_is_rejected(self, runtime: Path) -> None:
        """A live PID that isn't ours means the OS handed the number to someone else."""
        daemon.write_pid(4242)
        with (
            patch.object(daemon, "pid_alive", return_value=True),
            patch.object(daemon, "_pid_is_watcher", return_value=False),
        ):
            assert daemon.running_pid() is None


# ── start ────────────────────────────────────────────────────────────────────


def _spawned(pid: int = 4242, exited: int | None = None) -> MagicMock:
    process = MagicMock()
    process.pid = pid
    process.poll.return_value = exited
    process.returncode = exited
    return process


class TestStart:
    def test_records_the_child_pid(self, runtime: Path) -> None:
        with patch.object(daemon.subprocess, "Popen", return_value=_spawned()) as popen:
            ok, message = daemon.start()
        assert ok is True
        assert daemon.read_pid() == 4242
        assert "4242" in message
        assert popen.call_args.args[0][:4] == [daemon.sys.executable, "-m", "asher", "watch"]

    def test_accepts_a_child_that_registers_itself(
        self, runtime: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The normal path: the watcher claims the pid file, start just confirms it."""
        monkeypatch.setattr(daemon, "_STARTUP_GRACE_SECONDS", 1.0)
        daemon.write_pid(4242)
        with (
            patch.object(daemon.subprocess, "Popen", return_value=_spawned()),
            patch.object(daemon, "running_pid", return_value=None),
            patch.object(daemon, "write_pid") as fallback_write,
        ):
            ok, _ = daemon.start()
        assert ok is True
        fallback_write.assert_not_called()

    def test_passes_robot_and_tray_choices_to_the_child(self, runtime: Path) -> None:
        with patch.object(daemon.subprocess, "Popen", return_value=_spawned()) as popen:
            daemon.start(robot="Asher 2", tray=False)
        argv = popen.call_args.args[0]
        assert argv[-3:] == ["--robot", "Asher 2", "--no-tray"]

    def test_detaches_the_child(self, runtime: Path) -> None:
        with patch.object(daemon.subprocess, "Popen", return_value=_spawned()) as popen:
            daemon.start()
        kwargs = popen.call_args.kwargs
        assert "start_new_session" in kwargs or "creationflags" in kwargs

    def test_refuses_when_one_is_already_running(self, runtime: Path) -> None:
        with (
            patch.object(daemon, "running_pid", return_value=99),
            patch.object(daemon.subprocess, "Popen") as popen,
        ):
            ok, message = daemon.start()
        assert ok is False
        assert "already running" in message
        popen.assert_not_called()

    def test_refuses_without_credentials(
        self, runtime: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The watcher claims the pid file before authenticating, so it would
        register, report a pid, and stop a moment later with the reason buried
        in the log."""
        monkeypatch.setattr("asher.connection.credentials_available", lambda: False)
        with patch.object(daemon.subprocess, "Popen") as popen:
            ok, message = daemon.start()
        assert ok is False
        assert "/login" in message
        popen.assert_not_called()
        assert daemon.read_pid() is None

    def test_credential_check_costs_no_network(
        self, runtime: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Starting offline must still work: the watcher retries until the cloud answers."""
        monkeypatch.undo()
        monkeypatch.setattr(daemon, "_PID_PATH", runtime / "watch.pid")
        monkeypatch.setattr(daemon, "_LOG_PATH", runtime / "watch.log")
        monkeypatch.setattr(daemon, "_STARTUP_GRACE_SECONDS", 0)
        monkeypatch.setattr("asher.connection._keyring_load_token", lambda: None)
        monkeypatch.setattr("asher.connection._keyring_available", lambda: True)
        monkeypatch.setattr("asher.connection._keyring_load", lambda: ("a@b.com", "pw"))
        with (
            patch.object(daemon.subprocess, "Popen", return_value=_spawned()),
            patch("pylitterbot.Account") as account,
        ):
            ok, _ = daemon.start()
        assert ok is True
        account.assert_not_called()

    def test_reports_a_child_that_dies_on_the_way_up(self, runtime: Path) -> None:
        with patch.object(daemon.subprocess, "Popen", return_value=_spawned(exited=1)):
            ok, message = daemon.start()
        assert ok is False
        assert "exited immediately" in message
        assert daemon.read_pid() is None

    def test_reports_a_spawn_failure(self, runtime: Path) -> None:
        with patch.object(daemon.subprocess, "Popen", side_effect=OSError("no exec")):
            ok, message = daemon.start()
        assert ok is False
        assert "Could not start watcher" in message


class TestWaitUntilRegistered:
    def test_returns_as_soon_as_the_child_claims_the_pid_file(
        self, runtime: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(daemon, "_STARTUP_GRACE_SECONDS", 1.0)
        daemon.write_pid(4242)
        with patch.object(daemon, "write_pid") as fallback_write:
            assert daemon._wait_until_registered(_spawned()) is True
        fallback_write.assert_not_called()

    def test_reports_a_child_that_died(self, runtime: Path) -> None:
        assert daemon._wait_until_registered(_spawned(exited=1)) is False

    def test_records_a_slow_child_itself(self, runtime: Path) -> None:
        """Alive but not registered in time still has to be stoppable."""
        assert daemon._wait_until_registered(_spawned()) is True
        assert daemon.read_pid() == 4242


class TestPidFileHeld:
    def test_claims_and_releases(self, runtime: Path) -> None:
        with daemon._pid_file_held():
            assert daemon.read_pid() == os.getpid()
        assert daemon.read_pid() is None

    def test_leaves_a_pid_file_that_is_not_ours(self, runtime: Path) -> None:
        """A watcher that took over mid-flight must not have its claim deleted."""
        with daemon._pid_file_held():
            daemon.write_pid(4242)
        assert daemon.read_pid() == 4242

    def test_releases_even_when_the_watcher_raises(self, runtime: Path) -> None:
        with pytest.raises(RuntimeError), daemon._pid_file_held():
            raise RuntimeError("watcher blew up")
        assert daemon.read_pid() is None


# ── stop ─────────────────────────────────────────────────────────────────────


class TestStop:
    def test_says_so_when_nothing_is_running(self, runtime: Path) -> None:
        ok, message = daemon.stop()
        assert ok is False
        assert message == "No watcher is running."

    def test_terminates_and_clears_the_pid_file(self, runtime: Path) -> None:
        daemon.write_pid(4242)
        with (
            patch.object(daemon, "running_pid", return_value=4242),
            patch.object(daemon.os, "kill") as kill,
            patch.object(daemon, "pid_alive", return_value=False),
        ):
            ok, message = daemon.stop()
        assert ok is True
        assert "4242" in message
        assert kill.call_args.args == (4242, daemon.signal.SIGTERM)
        assert daemon.read_pid() is None

    def test_escalates_when_sigterm_is_ignored(self, runtime: Path) -> None:
        """A tray-hosted watcher sits in a native GUI loop where SIGTERM may not land."""
        # Zero grace means one liveness check per signal: still up after
        # SIGTERM, gone after SIGKILL.
        with (
            patch.object(daemon, "running_pid", return_value=4242),
            patch.object(daemon, "_TERM_GRACE_SECONDS", 0),
            patch.object(daemon, "_KILL_GRACE_SECONDS", 0),
            patch.object(daemon.os, "kill") as kill,
            patch.object(daemon, "pid_alive", side_effect=[True, False]),
        ):
            ok, _ = daemon.stop()
        assert ok is True
        # Windows has no SIGKILL; there the escalation is a second
        # TerminateProcess, which is what stop() falls back to.
        assert [call.args[1] for call in kill.call_args_list] == [
            daemon.signal.SIGTERM,
            getattr(daemon.signal, "SIGKILL", daemon.signal.SIGTERM),
        ]

    def test_already_gone_counts_as_stopped(self, runtime: Path) -> None:
        with (
            patch.object(daemon, "running_pid", return_value=4242),
            patch.object(daemon.os, "kill", side_effect=ProcessLookupError),
        ):
            ok, _ = daemon.stop()
        assert ok is True


# ── status ───────────────────────────────────────────────────────────────────


class TestStatus:
    def test_not_running(self, runtime: Path) -> None:
        ok, message = daemon.status()
        assert ok is False
        assert "not running" in message

    def test_reports_autostart_state(self, runtime: Path) -> None:
        with patch("asher.autostart.describe", return_value="enabled (launchd)"):
            _, message = daemon.status()
        assert "autostart: enabled (launchd)" in message

    def test_running_includes_the_log_tail(self, runtime: Path) -> None:
        daemon.log_path().write_text("first\n\nsecond\nthird\nfourth\n", encoding="utf-8")
        with patch.object(daemon, "running_pid", return_value=4242):
            ok, message = daemon.status()
        assert ok is True
        assert "pid 4242" in message
        assert "| fourth" in message
        assert "first" not in message

    def test_survives_a_missing_log(self, runtime: Path) -> None:
        with patch.object(daemon, "running_pid", return_value=4242):
            ok, message = daemon.status()
        assert ok is True
        assert "pid 4242" in message


# ── dispatch ─────────────────────────────────────────────────────────────────


class TestDispatch:
    def test_unknown_action_is_rejected(self, runtime: Path) -> None:
        assert daemon.dispatch("frobnicate") == EXIT_COMMAND_REJECTED

    def test_successful_start_exits_zero(self, runtime: Path) -> None:
        with patch.object(daemon, "start", return_value=(True, "started")):
            assert daemon.dispatch("start") == EXIT_OK

    def test_status_exits_non_zero_when_not_running(self, runtime: Path) -> None:
        """Truthful, but scripts want to branch on it."""
        assert daemon.dispatch("status") == EXIT_COMMAND_REJECTED

    def test_enable_registers_autostart(self, runtime: Path) -> None:
        with (
            patch("asher.autostart.enable", return_value=(True, "enabled")) as enable,
            patch.object(daemon, "running_pid", return_value=99),
        ):
            assert daemon.dispatch("enable") == EXIT_OK
        enable.assert_called_once()

    def test_enable_also_starts_watching_now(self, runtime: Path) -> None:
        """`systemctl enable --now` semantics: don't make the user wait for a login."""
        with (
            patch("asher.autostart.enable", return_value=(True, "enabled")),
            patch.object(daemon, "start", return_value=(True, "started")) as start,
        ):
            assert daemon.dispatch("enable") == EXIT_OK
        start.assert_called_once()

    def test_enable_does_not_start_a_duplicate(self, runtime: Path) -> None:
        with (
            patch("asher.autostart.enable", return_value=(True, "enabled")),
            patch.object(daemon, "running_pid", return_value=99),
            patch.object(daemon, "start") as start,
        ):
            daemon.dispatch("enable")
        start.assert_not_called()

    def test_disable_removes_autostart(self, runtime: Path) -> None:
        with patch("asher.autostart.disable", return_value=(True, "disabled")) as disable:
            assert daemon.dispatch("disable") == EXIT_OK
        disable.assert_called_once()

    def test_run_hands_off_to_the_foreground_watcher(self, runtime: Path) -> None:
        with patch.object(daemon, "run_foreground", return_value=EXIT_OK) as run:
            assert daemon.dispatch("run", robot="Asher", tray=False) == EXIT_OK
        run.assert_called_once_with(robot="Asher", tray=False)


# ── run_foreground ───────────────────────────────────────────────────────────


class TestRunForeground:
    def test_refuses_to_start_a_second_watcher(self, runtime: Path) -> None:
        """Autostart plus a manual start would otherwise notify twice."""
        with (
            patch.object(daemon, "running_pid", return_value=99),
            patch("asher.watcher.watch") as watch,
        ):
            assert daemon.run_foreground() == EXIT_COMMAND_REJECTED
        watch.assert_not_called()

    def test_owns_the_pid_file_while_watching(self, runtime: Path) -> None:
        seen: list[int | None] = []
        with (
            patch("asher.tray.is_available", return_value=False),
            patch("asher.watcher.watch", side_effect=lambda **_: seen.append(daemon.read_pid())),
        ):
            daemon.run_foreground()
        assert seen == [os.getpid()]
        assert daemon.read_pid() is None

    def test_skips_the_tray_when_unavailable(self, runtime: Path) -> None:
        with (
            patch("asher.tray.is_available", return_value=False),
            patch("asher.watcher.watch", return_value=EXIT_OK) as watch,
        ):
            assert daemon.run_foreground() == EXIT_OK
        assert watch.call_args.kwargs["poll_seconds"] > 0

    def test_uses_the_tray_when_available(self, runtime: Path) -> None:
        with (
            patch("asher.tray.is_available", return_value=True),
            patch("asher.tray.run", return_value=EXIT_OK) as tray_run,
        ):
            assert daemon.run_foreground(robot="Asher 2") == EXIT_OK
        assert tray_run.call_args.kwargs["robot_selector"] == "Asher 2"

    def test_no_tray_flag_wins(self, runtime: Path) -> None:
        with (
            patch("asher.tray.is_available", return_value=True) as available,
            patch("asher.watcher.watch", return_value=EXIT_OK),
        ):
            daemon.run_foreground(tray=False)
        available.assert_not_called()

    def test_config_can_disable_the_tray(self, runtime: Path) -> None:
        with (
            patch("asher.config.load", return_value={"watch_tray": False}),
            patch("asher.tray.is_available", return_value=True) as available,
            patch("asher.watcher.watch", return_value=EXIT_OK),
        ):
            daemon.run_foreground()
        available.assert_not_called()
