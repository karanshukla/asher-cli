"""Tests for slash-command tab completion.

Two layers:

1. Pure helpers in ``asher.completion`` — matching, enter-completion decision,
   and rendering are data-in/data-out, so they're tested directly without a
   Textual event loop.
2. Pilot-driven integration — the overlay appears/updates/hides as the user
   types into ``#cmd-input``, arrow keys move the selection, Tab/Esc behave,
   and Enter completes a partial command instead of erroring as unknown.

The Pilot tests share the ``connected_app`` fixture pattern from
``test_commands_pilot.py``: a mocked robot is injected before ``run_test``
so the command bar is live but no real cloud calls happen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from textual.widgets import Input, Static

from asher.app import AsherApp
from asher.commands import _registry
from asher.completion import enter_completes, render_completion, slash_matches

# ── fixtures ─────────────────────────────────────────────────────────────────


def _slash_cmd(name: str, description: str = ""):
    """Build a duck-typed SlashCommand-like object for pure-helper tests."""
    return SimpleNamespace(
        name=name,
        description=description or f"{name} description",
        full_name=f"/{name}",
    )


@pytest.fixture
def slash_cmds():
    """A small, deterministic slice of slash commands for pure-helper tests."""
    return [
        _slash_cmd("login", "sign in"),
        _slash_cmd("logout", "sign out"),
        _slash_cmd("robots", "list robots"),
        _slash_cmd("robot", "switch robot"),
        _slash_cmd("config", "show config"),
    ]


@pytest.fixture
def connected_app():
    """Create an AsherApp with mocked connected robot — mirrors test_commands_pilot."""
    robot = MagicMock()
    robot.name = "TestBot"
    robot.is_online = True
    robot.waste_drawer_level = 50.0
    robot.status = MagicMock()
    robot.status.value = "Ready"
    robot.sleep_mode_enabled = False
    robot.panel_lock_enabled = False
    robot.night_light_mode_enabled = False
    robot.serial = "LR12345"
    robot.last_seen = datetime.now(timezone.utc)
    robot.pet_weight = 10.5
    robot.refresh = AsyncMock()
    robot.start_cleaning = AsyncMock(return_value=True)
    robot.get_activity_history = AsyncMock(return_value=[])

    app = AsherApp()
    app._robot = robot
    app._account = MagicMock()
    app._pets = []
    app._connect_worker = lambda **kwargs: None  # type: ignore[method-assign]
    return app


# ── slash_matches ────────────────────────────────────────────────────────────


class TestSlashMatches:
    def test_bare_slash_returns_all_slash_commands(self, slash_cmds):
        result = slash_matches(slash_cmds, "/")
        assert result == slash_cmds

    def test_prefix_match_filters_case_insensitively(self, slash_cmds):
        result = slash_matches(slash_cmds, "/LO")
        assert [c.name for c in result] == ["login", "logout"]

    def test_single_char_prefix(self, slash_cmds):
        result = slash_matches(slash_cmds, "/r")
        assert [c.name for c in result] == ["robots", "robot"]

    def test_exact_name_still_matches(self, slash_cmds):
        result = slash_matches(slash_cmds, "/login")
        assert [c.name for c in result] == ["login"]

    def test_no_match_returns_empty(self, slash_cmds):
        assert slash_matches(slash_cmds, "/xyz") == []

    def test_non_slash_text_returns_empty(self, slash_cmds):
        # Bare commands are intentionally not completed.
        assert slash_matches(slash_cmds, "clean") == []
        assert slash_matches(slash_cmds, "") == []

    def test_preserves_registry_order(self):
        # Against the real registry, results keep registration order, not alpha.
        result = slash_matches(_registry.slash, "/")
        assert result == _registry.slash

    def test_real_registry_filters_multiple(self):
        # 'l' matches login, logout — both real slash commands.
        result = slash_matches(_registry.slash, "/l")
        names = [c.name for c in result]
        assert "login" in names
        assert "logout" in names
        assert all(n.startswith("l") for n in names)


# ── enter_completes ──────────────────────────────────────────────────────────


class TestEnterCompletes:
    def test_partial_match_completes(self, slash_cmds):
        # /log is ambiguous (login, logout) → Enter completes to the selected one.
        matches = slash_matches(slash_cmds, "/lo")
        assert enter_completes(matches, 0, "/lo") is matches[0]

    def test_exact_match_does_not_complete(self, slash_cmds):
        # /login exactly matches → Enter should submit, not re-complete.
        matches = slash_matches(slash_cmds, "/login")
        assert enter_completes(matches, 0, "/login") is None

    def test_no_matches_returns_none(self, slash_cmds):
        assert enter_completes([], 0, "/xyz") is None

    def test_non_slash_returns_none(self, slash_cmds):
        assert enter_completes(slash_cmds, 0, "clean") is None

    def test_args_present_does_not_complete(self, slash_cmds):
        # "/login foo" has args → completion phase is over; Enter submits.
        matches = slash_matches(slash_cmds, "/login")
        assert enter_completes(matches, 0, "/login foo") is None

    def test_selected_index_out_of_range_falls_back_to_first(self, slash_cmds):
        matches = slash_matches(slash_cmds, "/lo")
        # An out-of-range idx clamps to the first match rather than crashing.
        assert enter_completes(matches, 99, "/lo") is matches[0]

    def test_exact_match_submits_even_when_also_a_prefix(self, slash_cmds):
        # /robot is an exact command name but also a prefix of /robots.
        # Enter must submit /robot, not silently expand to /robots.
        matches = slash_matches(slash_cmds, "/robot")
        assert enter_completes(matches, 0, "/robot") is None


# ── render_completion ────────────────────────────────────────────────────────


class TestRenderCompletion:
    def test_empty_matches_renders_blank(self):
        assert str(render_completion([], 0)) == ""

    def test_renders_one_line_per_match(self, slash_cmds):
        text = render_completion(slash_cmds, 0)
        plain = text.plain
        # One row per match, joined by newlines.
        assert plain.count("\n") == len(slash_cmds) - 1

    def test_selected_index_appears_in_output(self, slash_cmds):
        text = render_completion(slash_cmds, 2)
        plain = text.plain
        # The third command ("robots") is the selected one.
        assert "/robots" in plain

    def test_negative_selected_idx_does_not_crash(self, slash_cmds):
        # Defensive: an index of -1 would wrap in Python; render should tolerate.
        text = render_completion(slash_cmds, -1)
        assert text.plain  # non-empty


# ── Pilot integration: overlay visibility ────────────────────────────────────


@pytest.mark.asyncio
async def test_typing_slash_shows_overlay(connected_app):
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("/")
        await pilot.pause()

        overlay = app.query_one("#completion-overlay", Static)
        assert overlay.display is True


@pytest.mark.asyncio
async def test_typing_bare_command_does_not_show_overlay(connected_app):
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("c", "l", "e", "a", "n")
        await pilot.pause()

        overlay = app.query_one("#completion-overlay", Static)
        assert overlay.display is False


@pytest.mark.asyncio
async def test_overlay_filters_as_user_types(connected_app):
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("/", "l", "o")
        await pilot.pause()

        overlay = app.query_one("#completion-overlay", Static)
        assert overlay.display is True
        # The overlay renders from _completion_matches; asserting on the
        # source-of-truth state is more robust than parsing rendered Content.
        names = [c.name for c in app._completion_matches]
        assert names == ["login", "logout"]


@pytest.mark.asyncio
async def test_no_match_hides_overlay(connected_app):
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("/", "l", "o")
        await pilot.pause()
        # Now type something that matches nothing.
        await pilot.press("q")
        await pilot.pause()

        overlay = app.query_one("#completion-overlay", Static)
        assert overlay.display is False


@pytest.mark.asyncio
async def test_space_dismisses_overlay(connected_app):
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("/", "l")
        await pilot.pause()
        assert app.query_one("#completion-overlay", Static).display is True

        await pilot.press("space")
        await pilot.pause()
        assert app.query_one("#completion-overlay", Static).display is False


# ── Pilot integration: navigation & completion ──────────────────────────────


@pytest.mark.asyncio
async def test_down_arrow_moves_selection(connected_app):
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("/", "l")
        await pilot.pause()
        assert app._completion_idx == 0

        await pilot.press("down")
        await pilot.pause()
        # Selection advanced from the first match to the second.
        assert app._completion_idx == 1

        # Up moves it back.
        await pilot.press("up")
        await pilot.pause()
        assert app._completion_idx == 0


@pytest.mark.asyncio
async def test_tab_accepts_completion_with_trailing_space(connected_app):
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("/", "l", "o", "g")
        await pilot.pause()

        await pilot.press("tab")
        await pilot.pause()

        cmd_input = app.query_one("#cmd-input", Input)
        # /log is ambiguous → Tab fills the first match (/login) + space.
        assert cmd_input.value == "/login "
        # Overlay hides after accepting.
        assert app.query_one("#completion-overlay", Static).display is False


@pytest.mark.asyncio
async def test_escape_dismisses_overlay(connected_app):
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("/", "l")
        await pilot.pause()
        assert app.query_one("#completion-overlay", Static).display is True

        await pilot.press("escape")
        await pilot.pause()
        assert app.query_one("#completion-overlay", Static).display is False


@pytest.mark.asyncio
async def test_enter_completes_partial_command_instead_of_erroring(connected_app):
    """The headline behaviour: /log + Enter completes to /login, not 'unknown'."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("/", "l", "o", "g")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        cmd_input = app.query_one("#cmd-input", Input)
        # Enter completed to /login (the first match) with a trailing space.
        assert cmd_input.value == "/login "


@pytest.mark.asyncio
async def test_enter_on_exact_match_submits_and_clears_input(connected_app):
    """Once the command name is complete, Enter submits normally."""
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        # /help is an exact match — no args needed.
        await pilot.press("/", "h", "e", "l", "p")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        cmd_input = app.query_one("#cmd-input", Input)
        # Input was cleared because the command actually dispatched.
        assert cmd_input.value == ""


@pytest.mark.asyncio
async def test_overlay_hidden_after_submit(connected_app):
    app = connected_app
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("/", "l", "o", "g")
        await pilot.pause()
        assert app.query_one("#completion-overlay", Static).display is True

        await pilot.press("enter")
        await pilot.pause()
        assert app.query_one("#completion-overlay", Static).display is False


@pytest.mark.asyncio
async def test_overlay_not_shown_during_login_flow(connected_app):
    """Completion must not interfere with the email/password prompt flow."""
    app = connected_app
    app._account = None  # signed-out so /login starts the flow
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cmd-input")
        await pilot.press("/", "l", "o", "g", "i", "n")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        # Login flow is active — typing / now should NOT open the overlay.
        await pilot.press("/")
        await pilot.pause()
        assert app.query_one("#completion-overlay", Static).display is False
