"""Tests for asher.activity_labels — pure translation layer.

No Textual / event-loop dependency. ``Activity`` is a plain dataclass so we
build real instances rather than mocking, which keeps the assertions honest
about how ``action`` (``str | LitterBoxStatus``) is read.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from pylitterbot.enums import LitterBoxStatus

from asher.activity_labels import (
    ACTION_LABELS,
    UNKNOWN_COLOUR,
    activity_raw_text,
    format_activity,
)


def _act(action, *, weight=None, pet_id=None, timestamp=None):
    """Build a duck-typed Activity-like object with optional weight/pet_id.

    pylitterbot's ``Activity`` dataclass only has ``timestamp`` and ``action``
    fields — ``weight`` and ``pet_id`` come from the LR5-rich activity subtype.
    Using ``SimpleNamespace`` lets us attach them without subclassing.
    """
    return SimpleNamespace(
        timestamp=timestamp or datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc),
        action=action,
        weight=weight,
        pet_id=pet_id,
    )


# ── activity_raw_text ────────────────────────────────────────────────────────


class TestActivityRawText:
    def test_plain_string_action(self):
        assert activity_raw_text(_act("Clean Cycle Complete")) == "Clean Cycle Complete"

    def test_strips_whitespace(self):
        assert activity_raw_text(_act("  Ready  ")) == "Ready"

    def test_litterbox_status_action_uses_text_property(self):
        # LitterBoxStatus exposes a .text property ("Ready", "Cat Detected", …)
        assert activity_raw_text(_act(LitterBoxStatus.CAT_DETECTED)) == "Cat Detected"

    def test_missing_action_attribute_falls_back_to_str_none(self):
        # Defensive: a malformed object with no .action attr should not raise.
        assert activity_raw_text(SimpleNamespace(timestamp=datetime.now(timezone.utc))) == "None"


# ── format_activity ──────────────────────────────────────────────────────────


class TestFormatActivityKnownEvents:
    def test_clean_cycle_complete_is_green(self):
        label, colour = format_activity(_act("Clean Cycle Complete"))
        assert label == "Clean cycle complete"
        assert colour == "#3fb950"

    def test_cat_detected_is_amber(self):
        label, colour = format_activity(_act("Cat Detected"))
        assert label == "Cat detected"
        assert colour == "#d29922"

    def test_drawer_full_is_red(self):
        label, colour = format_activity(_act("Drawer Full"))
        assert label == "Drawer full — empty now"
        assert colour == "#f85149"

    def test_ready_is_muted(self):
        label, colour = format_activity(_act("Ready"))
        assert label == "Ready"
        assert colour == "#484f58"

    def test_case_insensitive_lookup(self):
        label, _ = format_activity(_act("CLEAN CYCLE COMPLETE"))
        assert label == "Clean cycle complete"

    def test_litterbox_status_enum_action(self):
        # Status enum members carry the same text strings the API returns.
        label, colour = format_activity(_act(LitterBoxStatus.CLEAN_CYCLE))
        assert label == "Cleaning…"
        assert colour == "#58a6ff"


class TestFormatActivityCatSuffix:
    def test_appends_weight_and_pet_name(self):
        pets = [SimpleNamespace(id="pet-1", name="Asher")]
        act = _act("Cat Detected", weight=9.1, pet_id="pet-1")
        label, _ = format_activity(act, pets)
        assert label == "Cat detected  Asher  9.1 lb"

    def test_weight_only_when_pet_unknown(self):
        act = _act("Cat Detected", weight=8.4, pet_id="nope")
        label, _ = format_activity(act, [])
        assert label == "Cat detected  8.4 lb"

    def test_no_suffix_without_weight(self):
        act = _act("Cat Detected")
        label, _ = format_activity(act)
        assert label == "Cat detected"

    def test_non_cat_event_ignores_weight(self):
        # Clean cycles carry no pet attribution — the suffix must not appear.
        act = _act("Clean Cycle Complete", weight=9.1, pet_id="pet-1")
        label, _ = format_activity(act)
        assert label == "Clean cycle complete"


class TestFormatActivityUnknownEvents:
    def test_unknown_event_falls_back_to_raw_in_muted_grey(self):
        label, colour = format_activity(_act("Some New Whisker Event"))
        assert label == "Some New Whisker Event"
        assert colour == UNKNOWN_COLOUR

    def test_empty_pets_does_not_crash(self):
        # pets=None default path
        label, _ = format_activity(_act("Ready"))
        assert label == "Ready"


class TestActionLabelsIntegrity:
    def test_every_value_has_label_and_colour(self):
        for raw_str, (label, colour) in ACTION_LABELS.items():
            assert isinstance(raw_str, str) and raw_str
            assert label  # non-empty display label
            assert colour.startswith("#") and len(colour) == 7
