"""Tests for asher.cats ASCII art definitions."""

from __future__ import annotations

from asher.cats import CATS


class TestCatsStructure:
    def test_cats_is_dict(self):
        assert isinstance(CATS, dict)

    def test_has_expected_modes(self):
        expected_modes = {"idle", "happy", "sleeping", "cleaning", "error", "full"}
        assert set(CATS.keys()) == expected_modes

    def test_all_modes_are_lists(self):
        for mode, art in CATS.items():
            assert isinstance(art, list), f"Mode '{mode}' should be a list of frames"
            assert len(art) > 0, f"Mode '{mode}' should have at least one frame"

    def test_all_frames_are_strings(self):
        for mode, frames in CATS.items():
            for i, frame in enumerate(frames):
                assert isinstance(frame, str), f"Mode '{mode}' frame {i} should be a string"
                assert len(frame) > 0, f"Mode '{mode}' frame {i} should not be empty"

    def test_all_art_contains_cat_features(self):
        for mode, art in CATS.items():
            if isinstance(art, list):
                art = art[0]
            assert (
                "o" in art
                or "^" in art
                or "-" in art
                or "@" in art
                or "x" in art
                or "!" in art
                or "*" in art
            ), f"Mode '{mode}' should contain cat face features"

    def test_happy_has_eyes(self):
        assert "^ ^" in CATS["happy"][0]

    def test_idle_has_eyes(self):
        assert "o o" in CATS["idle"][0]

    def test_sleeping_has_eyes(self):
        assert "- -" in CATS["sleeping"][0]

    def test_error_has_x_eyes(self):
        assert "x x" in CATS["error"][0]

    def test_full_has_exclamation_eyes(self):
        assert "! !" in CATS["full"][0]

    def test_all_animations_have_at_least_two_frames(self):
        for mode, frames in CATS.items():
            assert len(frames) >= 2, f"Mode '{mode}' should have at least 2 frames"

    def test_idle_and_cleaning_have_frame_variation(self):
        for mode in ("idle", "cleaning"):
            frames = CATS[mode]
            unique = set(frames)
            assert len(unique) > 1, f"Mode '{mode}' should have varying frames"
