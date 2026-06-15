"""Tests for asher.cats ASCII art definitions."""

from __future__ import annotations

import pytest

from asher.cats import CATS


class TestCatsStructure:
    def test_cats_is_dict(self):
        assert isinstance(CATS, dict)

    def test_has_expected_modes(self):
        expected_modes = {"idle", "happy", "sleeping", "cleaning", "error", "full"}
        assert set(CATS.keys()) == expected_modes

    def test_idle_is_string(self):
        assert isinstance(CATS["idle"], str)
        assert len(CATS["idle"]) > 0

    def test_happy_is_string(self):
        assert isinstance(CATS["happy"], str)
        assert len(CATS["happy"]) > 0

    def test_sleeping_is_string(self):
        assert isinstance(CATS["sleeping"], str)
        assert len(CATS["sleeping"]) > 0

    def test_error_is_string(self):
        assert isinstance(CATS["error"], str)
        assert len(CATS["error"]) > 0

    def test_full_is_string(self):
        assert isinstance(CATS["full"], str)
        assert len(CATS["full"]) > 0

    def test_cleaning_is_list(self):
        assert isinstance(CATS["cleaning"], list)
        assert len(CATS["cleaning"]) > 0

    def test_cleaning_frames_are_strings(self):
        for i, frame in enumerate(CATS["cleaning"]):
            assert isinstance(frame, str), f"Frame {i} should be a string"
            assert len(frame) > 0, f"Frame {i} should not be empty"

    def test_all_art_contains_cat_features(self):
        for mode, art in CATS.items():
            if isinstance(art, list):
                art = art[0]
            assert "o" in art or "^" in art or "-" in art or "@" in art or "x" in art or "!" in art or "*" in art, (
                f"Mode '{mode}' should contain cat face features"
            )

    def test_happy_has_eyes(self):
        assert "^ ^" in CATS["happy"]

    def test_idle_has_eyes(self):
        assert "o o" in CATS["idle"]

    def test_sleeping_has_eyes(self):
        assert "- -" in CATS["sleeping"]

    def test_error_has_x_eyes(self):
        assert "x x" in CATS["error"]

    def test_full_has_exclamation_eyes(self):
        assert "! !" in CATS["full"]

    def test_cleaning_animation_has_variation(self):
        frames = CATS["cleaning"]
        assert len(frames) >= 2
        assert frames[0] != frames[1]

    def test_sleeping_has_zZ_indicator(self):
        assert "z" in CATS["sleeping"].lower()
