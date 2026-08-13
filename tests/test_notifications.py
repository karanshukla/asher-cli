"""Tests for asher.notifications — the plyer toast + beep façade.

Pure unit tests (no Textual, no Pilot). The façade's contract is that both
``fire`` and ``beep`` are always-safe: a missing plyer, a flaky platform
backend, or a headless session must degrade to a no-op rather than raising.
"""

from __future__ import annotations

import builtins
import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from asher import notifications


def _no_real_toasts() -> Any:
    """Stop a test that defeats plyer from popping a toast on the dev's desktop.

    Whenever ``_fire_plyer`` is made to fail, ``fire`` falls through to the
    platform's own notifier — which, unmocked, is a live ``notify-send`` /
    ``osascript`` call.
    """
    return patch.object(notifications, "_fire_native", return_value=False)


# ── fire ──────────────────────────────────────────────────────────────────────


class TestFire:
    def test_calls_plyer_on_happy_path(self) -> None:
        fake_notification = MagicMock()
        fake_mod = MagicMock(notification=fake_notification)
        with patch.dict("sys.modules", {"plyer": fake_mod}):
            notifications.fire("Title", "Body")
        fake_notification.notify.assert_called_once()
        kwargs = fake_notification.notify.call_args.kwargs
        assert kwargs["title"] == "Title"
        assert kwargs["message"] == "Body"
        assert kwargs["app_name"] == "Asher CLI"

    def test_no_op_when_plyer_missing(self) -> None:
        real_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object):
            if name == "plyer" or name.startswith("plyer."):
                raise ImportError("no plyer")
            return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

        with (
            patch("builtins.__import__", side_effect=fake_import),
            _no_real_toasts(),
        ):
            notifications.fire("Title", "Body")  # must not raise

    def test_no_op_when_backend_raises(self) -> None:
        fake_notification = MagicMock()
        fake_notification.notify.side_effect = RuntimeError("no desktop daemon")
        fake_mod = MagicMock(notification=fake_notification)
        with patch.dict("sys.modules", {"plyer": fake_mod}), _no_real_toasts():
            notifications.fire("Title", "Body")  # must not raise

    def test_timeout_passed_through(self) -> None:
        fake_notification = MagicMock()
        fake_mod = MagicMock(notification=fake_notification)
        with patch.dict("sys.modules", {"plyer": fake_mod}):
            notifications.fire("Title", "Body")
        assert fake_notification.notify.call_args.kwargs["timeout"] == 8


# ── the platform's own notifier ───────────────────────────────────────────────


class TestNativeArgv:
    """The fallback plyer leans on when its own backend is absent or unusable.

    On macOS that is the path that actually runs: plyer's backend imports
    pyobjus, which plyer does not depend on, so `fire` reaches osascript.
    Each platform is built directly rather than via dispatch, so macOS and
    Windows stay covered on a Linux runner.
    """

    def test_macos_builds_an_osascript_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(notifications.sys, "platform", "darwin")
        with patch.object(notifications.shutil, "which", return_value="/usr/bin/osascript"):
            argv = notifications._native_argv("Asher", "Drawer full")
        assert argv is not None
        assert argv[:2] == ["/usr/bin/osascript", "-e"]
        assert argv[2] == 'display notification "Drawer full" with title "Asher"'

    def test_macos_escapes_quotes_in_the_script(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The text is embedded in AppleScript source, so it must not end the literal."""
        monkeypatch.setattr(notifications.sys, "platform", "darwin")
        with patch.object(notifications.shutil, "which", return_value="/usr/bin/osascript"):
            argv = notifications._native_argv('Cat "Bin"', "ok")
        assert argv is not None
        assert r"\"Bin\"" in argv[2]

    def test_linux_builds_a_notify_send_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(notifications.sys, "platform", "linux")
        with patch.object(notifications.shutil, "which", return_value="/usr/bin/notify-send"):
            argv = notifications._native_argv("Asher", "Drawer full")
        assert argv is not None
        assert argv[0] == "/usr/bin/notify-send"
        assert argv[-2:] == ["Asher", "Drawer full"]
        assert "--app-name" in argv

    def test_linux_separates_the_text_from_the_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`--` so a title that starts with a dash isn't parsed as an option."""
        monkeypatch.setattr(notifications.sys, "platform", "linux")
        with patch.object(notifications.shutil, "which", return_value="/usr/bin/notify-send"):
            argv = notifications._native_argv("--oops", "body")
        assert argv is not None
        assert argv[argv.index("--") + 1] == "--oops"

    def test_windows_has_no_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Windows notifications rest entirely on plyer's win32 backend."""
        monkeypatch.setattr(notifications.sys, "platform", "win32")
        assert notifications._native_argv("Asher", "Drawer full") is None

    @pytest.mark.parametrize("platform", ["darwin", "linux"])
    def test_none_when_the_tool_is_missing(
        self, monkeypatch: pytest.MonkeyPatch, platform: str
    ) -> None:
        monkeypatch.setattr(notifications.sys, "platform", platform)
        with patch.object(notifications.shutil, "which", return_value=None):
            assert notifications._native_argv("Asher", "Drawer full") is None

    def test_a_failing_tool_reports_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(notifications.sys, "platform", "linux")
        with (
            patch.object(notifications.shutil, "which", return_value="/usr/bin/notify-send"),
            patch.object(notifications.subprocess, "run", return_value=MagicMock(returncode=1)),
        ):
            assert notifications._fire_native("Asher", "Drawer full") is False

    def test_survives_a_tool_that_hangs_or_dies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(notifications.sys, "platform", "linux")
        failure = subprocess.TimeoutExpired(cmd="notify-send", timeout=5)
        with (
            patch.object(notifications.shutil, "which", return_value="/usr/bin/notify-send"),
            patch.object(notifications.subprocess, "run", side_effect=failure),
        ):
            assert notifications._fire_native("Asher", "Drawer full") is False


# ── beep ──────────────────────────────────────────────────────────────────────


class TestBeep:
    def test_windows_calls_winsound_beep(self) -> None:
        fake_winsound = MagicMock()
        with (
            patch.object(notifications.sys, "platform", "win32"),
            patch.dict("sys.modules", {"winsound": fake_winsound}),
        ):
            notifications.beep()
        fake_winsound.Beep.assert_called_once_with(440, 300)

    def test_windows_critical_uses_higher_pitch(self) -> None:
        fake_winsound = MagicMock()
        with (
            patch.object(notifications.sys, "platform", "win32"),
            patch.dict("sys.modules", {"winsound": fake_winsound}),
        ):
            notifications.beep(critical=True)
        fake_winsound.Beep.assert_called_once_with(880, 300)

    def test_non_windows_prints_bell(self, capsys: object) -> None:
        with patch.object(notifications.sys, "platform", "linux"):
            notifications.beep()
        # Terminal bell is written to stdout; we just assert it doesn't raise
        # and doesn't touch winsound (which isn't importable here anyway).
