"""Tests for asher.helpers pure functions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from asher.helpers import drawer_bar, fmt_ago, ts


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
        assert text._spans[1].style == "#f85149"

    def test_warning_is_amber(self):
        text = drawer_bar(70)
        assert text._spans[1].style == "#d29922"

    def test_ok_is_green(self):
        text = drawer_bar(30)
        assert text._spans[1].style == "#3fb950"

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
        assert result._spans[0].style == "#484f58"
