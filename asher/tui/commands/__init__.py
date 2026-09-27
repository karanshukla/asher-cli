"""Command dispatch — the CommandsMixin that routes input to the registry."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from ...robot.protocol import RobotProtocol
    from ..app import AsherApp

from rich.text import Text
from textual import work
from textual.css.query import NoMatches
from textual.widgets import Input, RichLog, Static

from ...core import theme
from ...core.helpers import ts
from ..completion import enter_completes, render_completion, slash_matches
from ..loginflow import LoginFlow, LoginState
from .base import HINT_DEFAULT, Command
from .registry import _registry


class CommandsMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _robot: RobotProtocol | None
    _account: Any
    _cmd_history: list[str]
    _hist_idx: int
    _login: LoginFlow
    _completion_matches: list[Command]
    _completion_idx: int

    # ── input events ─────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd_input = self.query_one("#cmd-input", Input)  # type: ignore[attr-defined]
        raw = event.value.strip()
        completed = enter_completes(self._completion_matches, self._completion_idx, raw)
        if completed is not None:
            # Fill the completion but don't submit — Enter confirms the pick,
            # a second Enter runs it. Cursor sits after a space ready for args.
            cmd_input.value = f"{completed.full_name} "
            cmd_input.cursor_position = len(cmd_input.value)
            self._hide_completion()
            return

        cmd_input.value = ""
        self._hide_completion()
        if not raw:
            return

        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]

        # Login flow intercepts before history/echo
        if self._login.state is LoginState.AWAITING_EMAIL:
            t = ts()
            t.append(f"  {raw}", style=theme.FOREGROUND_BRIGHT)
            log.write(t)
            self._handle_login_email(raw)
            return

        if self._login.state is LoginState.AWAITING_PASSWORD:
            t = ts()
            t.append("  ••••••••", style=theme.MUTED)
            log.write(t)
            self._handle_login_password(raw)
            return

        # Normal command - add to history and echo
        self._cmd_history.insert(0, raw)
        self._hist_idx = -1

        t = ts()
        t.append("> ", style=f"bold {theme.OK}")
        t.append(raw, style=theme.FOREGROUND_BRIGHT)
        log.write(t)

        parts = raw.strip().split()
        raw_cmd = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []

        # Strip known prefixes (currently only "/")
        cmd_name = raw_cmd.lstrip("/")

        command = _registry.get(cmd_name)
        if command is None:
            if raw_cmd.startswith("/"):
                self._log_warn(f"Unknown slash command: '{raw}'  - try /login, /logout, /exit")  # type: ignore[attr-defined]
            else:
                self._log_warn(f"Unknown command: '{cmd_name}'  - type 'help' for list")  # type: ignore[attr-defined]
            return

        if command.requires_robot and self._robot is None:
            self._log_err("Not connected - type '/login' to sign in.")  # type: ignore[attr-defined]
            return

        self._dispatch_command(command, args)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Live-filter the slash popup and clear ghost text as the user types."""
        if self._login.is_active:
            # Suppress both completions during the email/password prompts —
            # the suggester fires on every keystroke, so wipe its result too.
            self._hide_completion()
            with contextlib.suppress(NoMatches):
                app_input = self.query_one("#cmd-input", Input)  # type: ignore[attr-defined]
                app_input._suggestion = ""  # type: ignore[attr-defined]
            return
        text = event.value
        # Only the first token is a command name; once a space is present the
        # user is typing arguments, so the overlay should not stay open.
        if " " in text or "\t" in text:
            self._hide_completion()
            return
        matches = slash_matches(_registry.slash, text)
        if matches:
            self._completion_matches = matches
            self._completion_idx = 0
            self._show_completion()
        else:
            self._hide_completion()

    def _render_completion(self) -> None:
        """Refresh the overlay widget's content from the current match list."""
        with contextlib.suppress(NoMatches):
            self.query_one("#completion-overlay", Static).update(  # type: ignore[attr-defined]
                render_completion(self._completion_matches, self._completion_idx)
            )

    def _show_completion(self) -> None:
        with contextlib.suppress(NoMatches):
            overlay = self.query_one("#completion-overlay", Static)  # type: ignore[attr-defined]
            overlay.update(render_completion(self._completion_matches, self._completion_idx))
            overlay.display = True

    def _hide_completion(self) -> None:
        self._completion_matches = []
        self._completion_idx = 0
        with contextlib.suppress(NoMatches):
            overlay = self.query_one("#completion-overlay", Static)  # type: ignore[attr-defined]
            overlay.display = False
            overlay.update("")

    def _accept_completion(self, *, append_space: bool) -> bool:
        """Fill the input with the selected completion. Returns True if handled."""
        if not self._completion_matches:
            return False
        idx = min(self._completion_idx, len(self._completion_matches) - 1)
        cmd = self._completion_matches[idx]
        cmd_input = self.query_one("#cmd-input", Input)  # type: ignore[attr-defined]
        value = f"{cmd.full_name} " if append_space else cmd.full_name
        cmd_input.value = value
        cmd_input.cursor_position = len(cmd_input.value)
        self._hide_completion()
        return True

    def _accept_ghost(self) -> bool:
        """Accept the inline ghost-text suggestion in the command bar.

        Returns True if a suggestion was accepted (so the caller can swallow
        the keypress). Mirrors the CmdInput's own Right-arrow acceptance: only
        fires at cursor-end when a suggestion is showing.
        """
        cmd_input = self.query_one("#cmd-input", Input)  # type: ignore[attr-defined]
        suggestion = getattr(cmd_input, "_suggestion", "") or ""
        if suggestion and getattr(cmd_input, "cursor_at_end", False):
            cmd_input.value = suggestion
            cmd_input.cursor_position = len(cmd_input.value)
            return True
        return False

    def on_key(self, event) -> None:  # type: ignore[override]
        # A pushed modal (history pager, login modal, …) owns its keys. The base
        # screen's `focused` still points at #cmd-input under a modal, so
        # has_focus alone would let us hijack arrows/special keys from the overlay.
        if len(self.screen_stack) > 1:  # type: ignore[attr-defined]
            return
        cmd_input = self.query_one("#cmd-input", Input)  # type: ignore[attr-defined]
        if not cmd_input.has_focus:
            return
        if self._login.is_active:
            return  # disable history nav + completion during login

        # Completion navigation takes precedence over history while the overlay
        # is open — mirrors the Claude Code behaviour where ↑/↓ move through
        # suggestions rather than recycling prior commands.
        if self._completion_matches:
            if event.key == "up":
                event.prevent_default()
                if self._completion_idx > 0:
                    self._completion_idx -= 1
                    self._render_completion()
                return
            if event.key == "down":
                event.prevent_default()
                if self._completion_idx < len(self._completion_matches) - 1:
                    self._completion_idx += 1
                    self._render_completion()
                return
            if event.key == "escape":
                event.prevent_default()
                self._hide_completion()
                return
            if event.key == "tab":
                event.prevent_default()
                self._accept_completion(append_space=True)
                return

        # Tab accepts the inline ghost-text suggestion when the slash popup is
        # closed — same role as Right-arrow, but matching IDE muscle memory.
        if event.key == "tab":
            if self._accept_ghost():
                event.prevent_default()
            return

        if event.key == "up":
            event.prevent_default()
            if self._cmd_history and self._hist_idx < len(self._cmd_history) - 1:
                self._hist_idx += 1
                cmd_input.value = self._cmd_history[self._hist_idx]
                cmd_input.cursor_position = len(cmd_input.value)
        elif event.key == "down":
            event.prevent_default()
            if self._hist_idx > 0:
                self._hist_idx -= 1
                cmd_input.value = self._cmd_history[self._hist_idx]
                cmd_input.cursor_position = len(cmd_input.value)
            elif self._hist_idx == 0:
                self._hist_idx = -1
                cmd_input.value = ""

    # ── inline login flow ─────────────────────────────────────────────────────

    def _start_login_flow(self) -> None:
        """Enter interactive login mode - prompts for email then password in the command bar."""
        if self._account:
            self._log_warn("Already signed in - use /logout to sign out first.")  # type: ignore[attr-defined]
            return
        self._login.start()
        self._set_cat("idle", "sign in")  # type: ignore[attr-defined]
        self.query_one("#prompt", Static).update("email ›")  # type: ignore[attr-defined]
        self.query_one("#hint-bar", Static).update("enter your Whisker account email")  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).placeholder = "your@email.com"  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).password = False  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).focus()  # type: ignore[attr-defined]
        self._log_info("Enter your Whisker account email:")  # type: ignore[attr-defined]

    def _handle_login_email(self, email: str) -> None:
        self._login.set_email(email)
        self.query_one("#prompt", Static).update("password ›")  # type: ignore[attr-defined]
        self.query_one("#hint-bar", Static).update("password will not be shown")  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).placeholder = "password"  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).password = True  # type: ignore[attr-defined]
        self._log_info("Enter your password:")  # type: ignore[attr-defined]

    @work
    async def _handle_login_password(self, password: str) -> None:
        email = self._login.complete()

        # Restore prompt and input to normal
        self.query_one("#prompt", Static).update(">")  # type: ignore[attr-defined]
        self.query_one("#hint-bar", Static).update(HINT_DEFAULT)  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).password = False  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).placeholder = "type a command  (help for list)…"  # type: ignore[attr-defined]

        if self._robot:
            with contextlib.suppress(Exception):
                await self._robot.unsubscribe()  # type: ignore[attr-defined]
        if self._account:
            with contextlib.suppress(Exception):
                await self._account.disconnect()
        self._account = None
        self._robot = None
        self._set_cat("idle", "connecting…")  # type: ignore[attr-defined]
        self._connect_worker(  # type: ignore[attr-defined]
            email=email, password=password, save_to_keyring=True
        )

    # ── command dispatch ────────────────────────────────────────────────────────

    @work
    async def _dispatch_command(self, command: Command, args: list[str]) -> None:
        await command.run(cast("AsherApp", self), args)

    # ── help ────────────────────────────────────────────────────────────────────

    def _show_help(self) -> None:
        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]
        log.write("")
        log.write(Text("Robot commands", style=f"bold {theme.ACCENT}"))
        seen: set[str] = set()
        for cmd in _registry.robot:
            if cmd.display_name in seen:
                continue
            seen.add(cmd.display_name)
            t = Text()
            t.append(f"  {cmd.help_name:<24}", style=theme.OK)
            t.append(cmd.description, style=theme.SUBTLE)
            log.write(t)
        log.write("")
        heading = Text("Slash commands", style=f"bold {theme.ACCENT}")
        heading.append("  (app management)", style=theme.MUTED)
        log.write(heading)
        for cmd in _registry.slash:
            t = Text()
            t.append(f"  {cmd.help_name:<24}", style=theme.WARN)
            t.append(cmd.description, style=theme.SUBTLE)
            log.write(t)
        log.write("")
