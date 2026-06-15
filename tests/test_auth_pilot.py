"""Integration tests for asher.auth using Textual's Pilot."""

from __future__ import annotations

import pytest
from textual.app import App

from asher.auth import LoginScreen


class TestApp(App):
    """Minimal app for testing LoginScreen."""
    CSS = ""

    def on_mount(self) -> None:
        self.push_screen(LoginScreen(), self._on_login)

    def _on_login(self, result: tuple[str, str] | None) -> None:
        self.exit(result)


@pytest.mark.asyncio
async def test_login_screen_composes():
    """Test that LoginScreen mounts all expected widgets."""
    app = TestApp()
    async with app.run_test() as pilot:
        # Wait for mount
        await pilot.pause()
        # Get the active screen and query within it
        screen = app.screen
        assert screen.query_one("#login-box")
        assert screen.query_one("#email-input")
        assert screen.query_one("#password-input")
        assert screen.query_one("#login-btn")


@pytest.mark.asyncio
async def test_email_input_focus_on_mount():
    """Test that email input is focused on mount."""
    app = TestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        email_input = screen.query_one("#email-input")
        assert email_input.has_focus


@pytest.mark.asyncio
async def test_password_input_is_password_field():
    """Test that password input has password flag set."""
    app = TestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        password_input = screen.query_one("#password-input")
        assert password_input.password is True


@pytest.mark.asyncio
async def test_submit_with_credentials_exits_app():
    """Test that submitting credentials dismisses screen and exits app."""
    app = TestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        # Enter email and password
        await pilot.click("#email-input")
        await pilot.press("t", "e", "s", "t", "@", "e", "x", "a", "m", "p", "l", "e", ".", "c", "o", "m")

        await pilot.click("#password-input")
        await pilot.press("s", "e", "c", "r", "e", "t", "1", "2", "3")

        # Click the login button
        await pilot.click("#login-btn")

    # After the async context, app should have exited with credentials
    assert app.return_value == ("test@example.com", "secret123")


@pytest.mark.asyncio
async def test_empty_credentials_shows_error():
    """Test that empty email/password shows error message."""
    app = TestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        # Leave inputs empty and click login
        await pilot.click("#login-btn")

        error_label = screen.query_one("#login-error")
        # Static widget content is accessible via its content or rendered
        error_text = str(error_label.render())
        assert "required" in error_text.lower()
