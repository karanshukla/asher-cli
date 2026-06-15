"""Tests for asher.auth module."""

from __future__ import annotations

import pytest

from asher.auth import LoginScreen


class TestLoginScreenStructure:
    def test_login_screen_is_modal_screen(self):
        from textual.screen import ModalScreen
        assert issubclass(LoginScreen, ModalScreen)

    def test_has_css_defined(self):
        assert hasattr(LoginScreen, "CSS")
        assert isinstance(LoginScreen.CSS, str)
        assert len(LoginScreen.CSS) > 0

    def test_css_contains_login_box(self):
        assert "#login-box" in LoginScreen.CSS

    def test_css_contains_login_title(self):
        assert "#login-title" in LoginScreen.CSS

    def test_css_contains_login_note(self):
        assert "#login-note" in LoginScreen.CSS

    def test_css_contains_field_label(self):
        assert ".field-label" in LoginScreen.CSS

    def test_css_contains_login_btn(self):
        assert "#login-btn" in LoginScreen.CSS

    def test_css_contains_login_error(self):
        assert "#login-error" in LoginScreen.CSS


class TestLoginScreenCSS:
    def test_css_has_alignment(self):
        assert "align:" in LoginScreen.CSS

    def test_css_has_background_colors(self):
        assert "background:" in LoginScreen.CSS

    def test_css_has_border_styles(self):
        assert "border:" in LoginScreen.CSS or "border-bottom:" in LoginScreen.CSS

    def test_css_has_padding(self):
        assert "padding:" in LoginScreen.CSS

    def test_css_has_width_and_height(self):
        assert "width:" in LoginScreen.CSS
        assert "height:" in LoginScreen.CSS

    def test_css_has_focus_styles(self):
        assert ":focus" in LoginScreen.CSS

    def test_css_uses_expected_colors(self):
        expected_colors = ["#161b22", "#30363d", "#58a6ff", "#484f58", "#8b949e", "#0d1117"]
        for color in expected_colors:
            assert color in LoginScreen.CSS, f"Color {color} should be in CSS"
