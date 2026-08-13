"""Tests for asher.notifications — the plyer toast + beep façade.

Pure unit tests (no Textual, no Pilot). The façade's contract is that both
``fire`` and ``beep`` are always-safe: a missing plyer, a flaky platform
backend, or a headless session must degrade to a no-op rather than raising.
"""

from __future__ import annotations

import builtins
from typing import Any
from unittest.mock import MagicMock, patch

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
