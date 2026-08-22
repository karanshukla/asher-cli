"""Tests for asher.helpers pure functions."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from asher import theme
from asher.helpers import (
    activity_type,
    dev_mode,
    drawer_bar,
    fmt_ago,
    fmt_until,
    hex_colour,
    parse_clock,
    parse_day,
    split_type_flag,
    status_text,
    ts,
)


class TestFmtAgo:
    def test_none_returns_never(self):
        assert fmt_ago(None) == "never"

    def test_seconds(self):
        dt = datetime.now(timezone.utc) - timedelta(seconds=30)
        assert fmt_ago(dt) == "30s ago"

    def test_minutes(self):
        dt = datetime.now(timezone.utc) - timedelta(minutes=5)
        assert fmt_ago(dt) == "5m ago"

    def test_hours(self):
        dt = datetime.now(timezone.utc) - timedelta(hours=3)
        assert fmt_ago(dt) == "3h ago"

    def test_days(self):
        dt = datetime.now(timezone.utc) - timedelta(days=7)
        assert fmt_ago(dt) == "7d ago"

    def test_naive_datetime_treated_as_utc(self):
        dt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        result = fmt_ago(dt)
        assert result.endswith("m ago")


class TestDrawerBar:
    def test_empty_bar(self):
        text = drawer_bar(0)
        rendered = str(text)
        assert "░" in rendered

    def test_half_bar(self):
        text = drawer_bar(50)
        rendered = str(text)
        assert "█" in rendered
        assert "░" in rendered

    def test_full_is_red(self):
        text = drawer_bar(90)
        # second span is the bar fill; should be red at 90%
        assert text._spans[1].style == theme.DANGER

    def test_warning_is_amber(self):
        text = drawer_bar(70)
        assert text._spans[1].style == theme.WARN

    def test_ok_is_green(self):
        text = drawer_bar(30)
        assert text._spans[1].style == theme.OK

    def test_brackets_present(self):
        text = drawer_bar(50)
        plain = text.plain
        assert plain.startswith("[") and plain.endswith("]")


class TestTs:
    def test_returns_text_object(self):
        result = ts()
        assert result.__class__.__name__ == "Text"

    def test_contains_timestamp(self):
        result = ts()
        plain = result.plain
        assert plain.startswith("[")
        assert "]" in plain

    def test_timestamp_format(self):
        result = ts()
        plain = result.plain
        import re

        pattern = r"\[\d{2}:\d{2}:\d{2}\] "
        assert re.search(pattern, plain) is not None

    def test_has_single_span(self):
        result = ts()
        assert len(result._spans) == 1

    def test_span_style_is_gray(self):
        result = ts()
        assert result._spans[0].style == theme.MUTED


class TestDevMode:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv("ASHER_CLI_DEV_MODE", raising=False)
        assert dev_mode() is False

    def test_on_when_set_true(self, monkeypatch):
        monkeypatch.setenv("ASHER_CLI_DEV_MODE", "true")
        assert dev_mode() is True

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("ASHER_CLI_DEV_MODE", "True")
        assert dev_mode() is True

    def test_any_other_value_is_off(self, monkeypatch):
        """Only an explicit `true` opts in — `1`/`yes` must not enable it silently."""
        for value in ("false", "1", "yes", ""):
            monkeypatch.setenv("ASHER_CLI_DEV_MODE", value)
            assert dev_mode() is False


class TestStatusText:
    def test_none_returns_em_dash(self):
        assert status_text(None) == "—"

    def test_uses_text_property_not_value(self):
        from pylitterbot.enums import LitterBoxStatus

        assert status_text(LitterBoxStatus.CLEAN_CYCLE) == "Clean Cycle In Progress"
        assert status_text(LitterBoxStatus.READY) == "Ready"
        assert status_text(LitterBoxStatus.DRAWER_FULL) == "Drawer Full"

    def test_plain_string_passthrough(self):
        assert status_text("Ready") == "Ready"

    def test_object_without_text_falls_back_to_str(self):
        assert status_text(42) == "42"


class TestFmtUntil:
    def test_none_returns_em_dash(self):
        assert fmt_until(None) == "—"

    def test_future_date_counts_down(self):
        dt = datetime.now(timezone.utc) + timedelta(days=23, hours=1)
        assert fmt_until(dt) == f"{dt.date().isoformat()} (in 23d)"

    def test_today_says_today(self):
        dt = datetime.now(timezone.utc) + timedelta(hours=2)
        assert "(today)" in fmt_until(dt)

    def test_past_date_is_overdue(self):
        dt = datetime.now(timezone.utc) - timedelta(days=3, hours=1)
        assert "(overdue by 3d)" in fmt_until(dt)

    def test_just_past_still_reads_as_today(self):
        dt = datetime.now(timezone.utc) - timedelta(hours=2)
        assert "(today)" in fmt_until(dt)

    def test_naive_datetime_is_read_as_utc(self):
        dt = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=5, hours=1)
        assert "(in 5d)" in fmt_until(dt)


class TestHexColour:
    def test_normalises_to_upper_six_digits(self):
        assert hex_colour("#ff9e64") == "#FF9E64"

    def test_accepts_a_missing_hash(self):
        assert hex_colour("ff9e64") == "#FF9E64"

    def test_expands_the_three_digit_shorthand(self):
        assert hex_colour("#f0a") == "#FF00AA"

    def test_tolerates_surrounding_whitespace(self):
        assert hex_colour("  #FF9E64 ") == "#FF9E64"

    def test_rejects_non_hex_characters(self):
        assert hex_colour("#zzzzzz") is None

    def test_rejects_a_wrong_length(self):
        assert hex_colour("#ff9e6") is None
        assert hex_colour("") is None


class TestParseClock:
    def test_parses_a_24_hour_time(self):
        assert parse_clock("22:00") == time(22, 0)
        assert parse_clock("7:05") == time(7, 5)

    def test_rejects_a_missing_separator(self):
        assert parse_clock("2200") is None

    def test_rejects_out_of_range_values(self):
        assert parse_clock("24:00") is None
        assert parse_clock("22:60") is None

    def test_rejects_words(self):
        assert parse_clock("bedtime") is None


class TestParseDay:
    def test_parses_short_and_long_names(self):
        assert parse_day("mon") == 0
        assert parse_day("Monday") == 0
        assert parse_day("SUN") == 6

    def test_unknown_day_is_none(self):
        assert parse_day("caturday") is None


class TestSplitTypeFlag:
    def test_no_flag_leaves_args_alone(self):
        assert split_type_flag(["50"]) == (["50"], None)

    def test_separate_value(self):
        assert split_type_flag(["50", "--type", "cat"]) == (["50"], "cat")

    def test_equals_form(self):
        assert split_type_flag(["--type=cat", "50"]) == (["50"], "cat")

    def test_flag_without_a_value_is_empty_not_missing(self):
        assert split_type_flag(["--type"]) == ([], "")


class TestActivityType:
    def test_friendly_names_map_to_cloud_types(self):
        assert activity_type("cat") == "PET_VISIT"
        assert activity_type("clean") == "CYCLE_COMPLETED"

    def test_lookup_is_case_insensitive(self):
        assert activity_type("Cat") == "PET_VISIT"

    def test_unknown_word_passes_through_uppercased(self):
        assert activity_type("weird_new_event") == "WEIRD_NEW_EVENT"

    def test_missing_or_blank_is_none(self):
        assert activity_type(None) is None
        assert activity_type("  ") is None
