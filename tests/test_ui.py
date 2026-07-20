"""Tests for asher.ui module."""

from __future__ import annotations

from pathlib import Path

from asher.ui import _SPINNER, VERSION, UIMixin

_CSS_PATH = Path(__file__).parent.parent / "asher" / "ui" / "style.tcss"
_CSS = _CSS_PATH.read_text()


class TestVersion:
    def test_version_is_defined(self):
        assert VERSION is not None
        assert isinstance(VERSION, str)

    def test_version_is_not_empty(self):
        assert len(VERSION) > 0


class TestSpinner:
    def test_spinner_is_list(self):
        assert isinstance(_SPINNER, list)

    def test_spinner_has_expected_frames(self):
        expected_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        assert expected_frames == _SPINNER

    def test_spinner_has_ten_frames(self):
        assert len(_SPINNER) == 10

    def test_spinner_frames_are_single_characters(self):
        for frame in _SPINNER:
            assert len(frame) == 1


class TestCSS:
    def test_css_is_string(self):
        assert isinstance(_CSS, str)

    def test_css_is_not_empty(self):
        assert len(_CSS) > 0

    def test_css_contains_screen_selector(self):
        assert "Screen {" in _CSS

    def test_css_contains_status_bar(self):
        assert "#status-bar" in _CSS

    def test_css_contains_main_area(self):
        assert "#main-area" in _CSS

    def test_css_contains_log(self):
        assert "#log" in _CSS

    def test_css_contains_cat_panel(self):
        assert "#cat-panel" in _CSS

    def test_css_contains_cat_art(self):
        assert "#cat-art" in _CSS

    def test_css_contains_cat_fx(self):
        assert "#cat-fx" in _CSS

    def test_css_contains_cat_label(self):
        assert "#cat-label" in _CSS

    def test_css_contains_cat_status(self):
        assert "#cat-status" in _CSS

    def test_css_contains_fault_banner(self):
        assert "#fault-banner" in _CSS

    def test_css_contains_bottom_dock(self):
        assert "#bottom-dock" in _CSS

    def test_css_contains_input_bar(self):
        assert "#input-bar" in _CSS

    def test_css_contains_prompt(self):
        assert "#prompt" in _CSS

    def test_css_contains_hint_bar(self):
        assert "#hint-bar" in _CSS

    def test_css_contains_cmd_input(self):
        assert "#cmd-input" in _CSS

    def test_css_uses_expected_background_color(self):
        assert "#0d1117" in _CSS

    def test_css_uses_expected_foreground_color(self):
        assert "#c9d1d9" in _CSS

    def test_css_has_srow_class(self):
        assert ".srow" in _CSS

    def test_css_has_sep_class(self):
        assert ".sep" in _CSS

    def test_css_has_chunk_class(self):
        assert ".chunk" in _CSS


class TestAppCSS:
    def test_app_has_css_path(self):
        from asher.app import AsherApp

        assert hasattr(AsherApp, "CSS_PATH")

    def test_css_path_points_to_existing_file(self):
        from asher.app import AsherApp

        css_path = Path(__file__).parent.parent / "asher" / AsherApp.CSS_PATH
        assert css_path.exists()


class TestUIMixinLoggingHelpers:
    def test_log_ok_exists(self):
        assert hasattr(UIMixin, "_log_ok")

    def test_log_err_exists(self):
        assert hasattr(UIMixin, "_log_err")

    def test_log_warn_exists(self):
        assert hasattr(UIMixin, "_log_warn")

    def test_log_info_exists(self):
        assert hasattr(UIMixin, "_log_info")


class TestUIMixinCatHelpers:
    def test_set_cat_exists(self):
        assert hasattr(UIMixin, "_set_cat")

    def test_tick_cat_exists(self):
        assert hasattr(UIMixin, "_tick_cat")

    def test_show_welcome_exists(self):
        assert hasattr(UIMixin, "_show_welcome")

    def test_show_loading_state_exists(self):
        assert hasattr(UIMixin, "_show_loading_state")

    def test_refresh_title_exists(self):
        assert hasattr(UIMixin, "_refresh_title")


class TestUIMixinActions:
    def test_action_clear_log_exists(self):
        assert hasattr(UIMixin, "action_clear_log")

    def test_action_blur_input_exists(self):
        assert hasattr(UIMixin, "action_blur_input")

    def test_action_dismiss_fault_exists(self):
        assert hasattr(UIMixin, "action_dismiss_fault")
