"""Tests for asher.desktoptheme — panel-tone detection on all three platforms.

Every backend is driven directly rather than via ``sys.platform`` dispatch, so
the macOS and Windows probes stay covered on the Linux CI runner. The probes
shell out, so the contract that matters most is the failure one: nothing here
may raise, because the watcher behind the icon has to survive a desktop that
answers strangely or not at all.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from asher import desktoptheme


@pytest.fixture(autouse=True)
def _clear_cache() -> Any:
    desktoptheme._cache = None
    yield
    desktoptheme._cache = None


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["probe"], returncode=returncode, stdout=stdout)


# ── luma ─────────────────────────────────────────────────────────────────────


class TestRgbIsDark:
    def test_reads_a_kde_triplet(self) -> None:
        assert desktoptheme._rgb_is_dark("30,30,46") is True
        assert desktoptheme._rgb_is_dark("239,240,241") is False

    def test_weights_green_over_blue(self) -> None:
        """Rec. 601 luma, not a naive average — a pure blue reads as dark."""
        assert desktoptheme._rgb_is_dark("0,0,255") is True
        assert desktoptheme._rgb_is_dark("0,255,0") is False

    @pytest.mark.parametrize("value", ["", "30,30", "a,b,c", "not a colour"])
    def test_declines_to_guess_at_junk(self, value: str) -> None:
        assert desktoptheme._rgb_is_dark(value) is None


# ── macOS ────────────────────────────────────────────────────────────────────


class TestMacos:
    def test_dark_when_the_key_is_present(self) -> None:
        with patch.object(desktoptheme, "_run", return_value=_completed("Dark\n")):
            assert desktoptheme._macos_is_dark() is True

    def test_a_missing_key_means_light_not_unknown(self) -> None:
        """`defaults` exits non-zero in Light Mode — that is an answer."""
        with patch.object(desktoptheme, "_run", return_value=_completed(returncode=1)):
            assert desktoptheme._macos_is_dark() is False

    def test_unknown_when_defaults_cannot_run(self) -> None:
        with patch.object(desktoptheme, "_run", return_value=None):
            assert desktoptheme._macos_is_dark() is None


# ── Windows ──────────────────────────────────────────────────────────────────


def _winreg_stub(values: dict[str, int]) -> Any:
    winreg = MagicMock()
    winreg.OpenKey.return_value.__enter__ = lambda _self: "key"
    winreg.OpenKey.return_value.__exit__ = lambda *_: False

    def query(_key: Any, name: str) -> tuple[int, int]:
        if name not in values:
            raise OSError(name)
        return values[name], 4

    winreg.QueryValueEx.side_effect = query
    return winreg


class TestWindows:
    def test_taskbar_tone_wins_over_app_tone(self) -> None:
        """Only SystemUsesLightTheme describes the tray's own background."""
        winreg = _winreg_stub({"SystemUsesLightTheme": 0, "AppsUseLightTheme": 1})
        with patch.dict(sys.modules, {"winreg": winreg}):
            assert desktoptheme._windows_is_dark() is True

    def test_falls_back_to_the_app_tone_on_older_builds(self) -> None:
        winreg = _winreg_stub({"AppsUseLightTheme": 0})
        with patch.dict(sys.modules, {"winreg": winreg}):
            assert desktoptheme._windows_is_dark() is True

    def test_light_taskbar(self) -> None:
        winreg = _winreg_stub({"SystemUsesLightTheme": 1})
        with patch.dict(sys.modules, {"winreg": winreg}):
            assert desktoptheme._windows_is_dark() is False

    def test_unknown_when_neither_value_exists(self) -> None:
        with patch.dict(sys.modules, {"winreg": _winreg_stub({})}):
            assert desktoptheme._windows_is_dark() is None


# ── Linux ────────────────────────────────────────────────────────────────────


class TestKde:
    def test_judges_plasma_by_its_background_colour(self) -> None:
        with patch.object(desktoptheme, "_run", return_value=_completed("30,30,46\n")):
            assert desktoptheme._kde_is_dark() is True

    def test_light_breeze(self) -> None:
        with patch.object(desktoptheme, "_run", return_value=_completed("239,240,241\n")):
            assert desktoptheme._kde_is_dark() is False

    def test_tries_kreadconfig5_when_6_is_absent(self) -> None:
        answers = {"kreadconfig6": None, "kreadconfig5": _completed("30,30,46\n")}
        with patch.object(desktoptheme, "_run", side_effect=lambda argv: answers[argv[0]]):
            assert desktoptheme._kde_is_dark() is True

    def test_unknown_without_any_reader(self) -> None:
        with patch.object(desktoptheme, "_run", return_value=None):
            assert desktoptheme._kde_is_dark() is None


class TestGnome:
    def test_reads_the_colour_scheme_preference(self) -> None:
        with patch.object(desktoptheme, "_gsettings", return_value="'prefer-dark'".strip("'")):
            assert desktoptheme._gnome_is_dark() is True

    def test_default_scheme_falls_through_to_the_theme_name(self) -> None:
        """`default` means no preference expressed, which is not `light`."""
        answers = {"color-scheme": "default", "gtk-theme": "adwaita-dark"}
        with patch.object(desktoptheme, "_gsettings", side_effect=answers.get):
            assert desktoptheme._gnome_is_dark() is True

    def test_light_theme_name(self) -> None:
        answers = {"color-scheme": "default", "gtk-theme": "adwaita"}
        with patch.object(desktoptheme, "_gsettings", side_effect=answers.get):
            assert desktoptheme._gnome_is_dark() is False

    def test_unknown_without_gsettings(self) -> None:
        with patch.object(desktoptheme, "_gsettings", return_value=None):
            assert desktoptheme._gnome_is_dark() is None


class TestLinuxDispatch:
    def test_gnome_answers_when_kde_cannot(self) -> None:
        with (
            patch.object(desktoptheme, "_kde_is_dark", return_value=None),
            patch.object(desktoptheme, "_gnome_is_dark", return_value=False),
        ):
            assert desktoptheme._linux_is_dark() is False

    def test_kde_wins_when_both_answer(self) -> None:
        with (
            patch.object(desktoptheme, "_kde_is_dark", return_value=True),
            patch.object(desktoptheme, "_gnome_is_dark", return_value=False),
        ):
            assert desktoptheme._linux_is_dark() is True


# ── the public entry point ───────────────────────────────────────────────────


class TestPanelIsDark:
    def test_falls_back_when_nothing_will_say(self) -> None:
        with patch.object(desktoptheme, "_detect", return_value=None):
            assert desktoptheme.panel_is_dark() is desktoptheme._FALLBACK_IS_DARK

    def test_passes_a_detected_answer_through(self) -> None:
        with patch.object(desktoptheme, "_detect", return_value=False):
            assert desktoptheme.panel_is_dark() is False

    def test_caches_so_a_poll_loop_does_not_spawn_a_probe_each_time(self) -> None:
        with patch.object(desktoptheme, "_detect", return_value=True) as detect:
            desktoptheme.panel_is_dark()
            desktoptheme.panel_is_dark()
        detect.assert_called_once()

    def test_refresh_bypasses_the_cache(self) -> None:
        with patch.object(desktoptheme, "_detect", return_value=True) as detect:
            desktoptheme.panel_is_dark()
            desktoptheme.panel_is_dark(refresh=True)
        assert detect.call_count == 2

    def test_the_cache_expires(self) -> None:
        with patch.object(desktoptheme, "_detect", return_value=True) as detect:
            with patch.object(desktoptheme.time, "monotonic", return_value=0.0):
                desktoptheme.panel_is_dark()
            later = desktoptheme._CACHE_SECONDS + 1
            with patch.object(desktoptheme.time, "monotonic", return_value=later):
                desktoptheme.panel_is_dark()
        assert detect.call_count == 2

    def test_an_unknown_platform_detects_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "sunos5")
        assert desktoptheme._detect() is None


class TestRun:
    def test_returns_none_for_a_missing_executable(self) -> None:
        with patch.object(desktoptheme.shutil, "which", return_value=None):
            assert desktoptheme._run(["nope"]) is None

    @pytest.mark.parametrize(
        "failure",
        [OSError("boom"), subprocess.TimeoutExpired(cmd="probe", timeout=5)],
    )
    def test_survives_a_probe_that_misbehaves(self, failure: Exception) -> None:
        with (
            patch.object(desktoptheme.shutil, "which", return_value="/usr/bin/probe"),
            patch.object(desktoptheme.subprocess, "run", side_effect=failure),
        ):
            assert desktoptheme._run(["probe"]) is None

    def test_never_uses_a_shell(self) -> None:
        with (
            patch.object(desktoptheme.shutil, "which", return_value="/usr/bin/probe"),
            patch.object(desktoptheme.subprocess, "run", return_value=_completed()) as run,
        ):
            desktoptheme._run(["probe", "--flag"])
        assert run.call_args.args[0] == ["/usr/bin/probe", "--flag"]
        assert "shell" not in run.call_args.kwargs
