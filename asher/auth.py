"""Login screen for first-time credential setup."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from . import theme


class LoginScreen(ModalScreen[tuple[str, str]]):
    """Prompts for Whisker account credentials and returns (email, password)."""

    CSS = theme.apply("""
    LoginScreen {
        align: center middle;
    }

    #login-box {
        background: $asher-panel;
        border: solid $asher-border;
        padding: 2 4;
        width: 52;
        height: auto;
    }

    #login-title {
        color: $asher-accent;
        text-style: bold;
        text-align: center;
        padding-bottom: 0;
        width: 100%;
    }

    #login-note {
        color: $asher-muted;
        text-align: center;
        width: 100%;
        padding-bottom: 1;
    }

    .field-label {
        color: $asher-subtle;
        padding: 1 0 0 0;
        height: 1;
    }

    #login-box Input {
        border: solid $asher-border;
        background: $asher-bg;
        padding: 0 1;
        margin-top: 0;
    }

    #login-box Input:focus {
        border: solid $asher-accent;
    }

    #login-btn {
        margin-top: 1;
        width: 100%;
    }

    #login-error {
        color: $asher-danger;
        text-align: center;
        height: 1;
        padding-top: 1;
    }
    """)

    def compose(self) -> ComposeResult:
        with Container(id="login-box"):
            yield Static("◆ Sign in to Whisker", id="login-title")
            yield Static("Stored securely in your OS keyring.", id="login-note")
            yield Label("Email", classes="field-label")
            yield Input(placeholder="you@example.com", id="email-input")
            yield Label("Password", classes="field-label")
            yield Input(placeholder="••••••••", password=True, id="password-input")
            yield Button("Connect", id="login-btn", variant="success")
            yield Static("", id="login-error")

    def on_mount(self) -> None:
        self.query_one("#email-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "login-btn":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        if event.input.id == "email-input":
            self.query_one("#password-input", Input).focus()
        elif event.input.id == "password-input":
            self._submit()

    def _submit(self) -> None:
        email = self.query_one("#email-input", Input).value.strip()
        password = self.query_one("#password-input", Input).value
        if not email or not password:
            self.query_one("#login-error", Static).update("Email and password are required.")
            return
        self.dismiss((email, password))
