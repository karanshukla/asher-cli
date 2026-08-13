"""Tests for asher.tray — availability probing, menu text, and the fallback.

pystray and Pillow are an optional extra, so the tray is exercised through
fakes: the point of these tests is that a missing or unusable tray costs the
user an icon, never the notifications behind it.
"""

from __future__ import annotations

import builtins
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from asher import theme, tray
from asher.export import EXIT_OK
from asher.watcher import Snapshot


def _blocking_import(*blocked: str):
    """An ``__import__`` that fails for the named top-level modules."""
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> Any:
        if name.split(".")[0] in blocked:
            raise ImportError(f"no {name}")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    return fake_import


# ── is_available ─────────────────────────────────────────────────────────────


class TestIsAvailable:
    def test_false_without_pystray(self) -> None:
        with patch("builtins.__import__", side_effect=_blocking_import("pystray")):
            assert tray.is_available() is False

    def test_false_without_pillow(self) -> None:
        with patch("builtins.__import__", side_effect=_blocking_import("PIL")):
            assert tray.is_available() is False

    def test_false_on_linux_with_no_display(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        with patch.dict("sys.modules", {"pystray": MagicMock(), "PIL": MagicMock()}):
            assert tray.is_available() is False

    def test_true_on_linux_with_a_display(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("DISPLAY", ":0")
        with patch.dict("sys.modules", {"pystray": MagicMock(), "PIL": MagicMock()}):
            assert tray.is_available() is True

    def test_true_on_macos_without_display_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.delenv("DISPLAY", raising=False)
        with patch.dict("sys.modules", {"pystray": MagicMock(), "PIL": MagicMock()}):
            assert tray.is_available() is True


# ── _TrayState ───────────────────────────────────────────────────────────────


def _snapshot(**overrides: Any) -> Snapshot:
    defaults: dict[str, Any] = {
        "name": "Asher",
        "status": "Ready",
        "drawer": "40%",
        "online": True,
        "faulted": False,
    }
    return Snapshot(**{**defaults, **overrides})


class TestTrayState:
    def test_reads_as_connecting_before_the_first_snapshot(self) -> None:
        state = tray._TrayState()
        assert "connecting" in state.title()
        assert state.detail() == "Connecting…"

    def test_title_summarises_a_healthy_robot(self) -> None:
        state = tray._TrayState()
        state.update(_snapshot())
        assert state.title() == "Asher — Asher: Ready, drawer 40%"

    def test_title_leads_with_offline(self) -> None:
        state = tray._TrayState()
        state.update(_snapshot(online=False))
        assert state.title() == "Asher — Asher (offline)"

    def test_detail_pairs_status_and_drawer(self) -> None:
        state = tray._TrayState()
        state.update(_snapshot())
        assert state.detail() == "Ready  ·  drawer 40%"

    def test_icon_colour_tracks_robot_health(self) -> None:
        state = tray._TrayState()
        state.update(_snapshot())
        assert state._colour() == theme.OK
        state.update(_snapshot(faulted=True))
        assert state._colour() == theme.DANGER
        state.update(_snapshot(online=False))
        assert state._colour() == theme.MUTED

    def test_pushes_changes_to_the_icon(self) -> None:
        state = tray._TrayState()
        icon = MagicMock()
        state.bind(icon)
        with patch.object(tray, "_icon_image", return_value="image"):
            state.update(_snapshot())
        assert icon.title == "Asher — Asher: Ready, drawer 40%"
        icon.update_menu.assert_called_once()

    def test_skips_redundant_redraws(self) -> None:
        """Status polls fire far more often than the rendered state changes."""
        state = tray._TrayState()
        icon = MagicMock()
        state.bind(icon)
        with patch.object(tray, "_icon_image", return_value="image"):
            state.update(_snapshot())
            state.update(_snapshot())
        icon.update_menu.assert_called_once()

    def test_survives_an_icon_that_rejects_updates(self) -> None:
        state = tray._TrayState()
        icon = MagicMock()
        type(icon).title = property(lambda _self: "", _raise)
        state.bind(icon)
        with patch.object(tray, "_icon_image", return_value="image"):
            state.update(_snapshot())  # must not raise


def _raise(_self: Any, _value: Any) -> None:
    raise RuntimeError("backend gone")


# ── run ──────────────────────────────────────────────────────────────────────


class TestRun:
    def test_falls_back_to_headless_without_pystray(self) -> None:
        with (
            patch("builtins.__import__", side_effect=_blocking_import("pystray")),
            patch("asher.watcher.watch", return_value=EXIT_OK) as watch,
        ):
            assert tray.run(robot_selector="Asher", poll_seconds=60) == EXIT_OK
        assert watch.call_args.kwargs["robot_selector"] == "Asher"
        assert watch.call_args.kwargs["poll_seconds"] == 60

    def test_falls_back_when_the_backend_refuses_to_start(self) -> None:
        """An unusable tray must not take the notifications down with it."""
        fake_pystray = MagicMock()
        fake_pystray.Icon.return_value.run.side_effect = RuntimeError("no AppIndicator host")
        with (
            patch.dict("sys.modules", {"pystray": fake_pystray}),
            patch.object(tray, "_icon_image", return_value="image"),
            patch("asher.watcher.watch", return_value=EXIT_OK) as watch,
        ):
            assert tray.run(log=lambda _: None) == EXIT_OK
        watch.assert_called_once()

    def test_stops_the_watcher_when_the_icon_closes(self) -> None:
        fake_pystray = MagicMock()
        runner = MagicMock()
        runner.exit_code = EXIT_OK
        with (
            patch.dict("sys.modules", {"pystray": fake_pystray}),
            patch.object(tray, "_icon_image", return_value="image"),
            patch("asher.watcher.WatcherRunner", return_value=runner),
        ):
            assert tray.run(log=lambda _: None) == EXIT_OK
        runner.request_stop.assert_called_once()
        runner.join.assert_called_once()


# ── icon ─────────────────────────────────────────────────────────────────────


class TestIconImage:
    def test_draws_a_square_rgba_image(self) -> None:
        pytest.importorskip("PIL")
        image = tray._icon_image(theme.OK)
        assert image.size == (tray._ICON_SIZE, tray._ICON_SIZE)
        assert image.mode == "RGBA"
