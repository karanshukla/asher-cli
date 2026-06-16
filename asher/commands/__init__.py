"""Command dispatch and individual command handlers."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from rich.text import Text
from textual import work
from textual.widgets import Input, RichLog, Static

from ..helpers import ts
from ..login_flow import LoginFlow, LoginState
from .base import Command, CommandRegistry, SlashCommand

_HINT_DEFAULT = "help · clean · status · history · /login · /logout · quit"
_HINT_SIGNIN = "/login to sign in"


# ── robot commands ──────────────────────────────────────────────────────────


class CleanCommand(Command):
    name = "clean"
    description = "start a clean cycle"
    requires_robot = True

    async def run(self, app: Any, args: list[str]) -> None:
        app._set_cat("cleaning", "cleaning…")
        try:
            await app._robot.start_cleaning()
            app._log_ok("Clean cycle started")
            await asyncio.sleep(3)
            await app._robot.refresh()
            await app._refresh_status()
            app._set_cat("happy", "all done!")
        except Exception as exc:
            app._log_err(f"Failed to start cleaning: {exc}")
            app._set_cat("error", "error")


class StatusCommand(Command):
    name = "status"
    description = "refresh and display full status"
    requires_robot = True

    async def run(self, app: Any, args: list[str]) -> None:
        try:
            await app._robot.refresh()
            await app._refresh_status()
            r = app._robot
            rows = [
                ("Name", getattr(r, "name", "—")),
                ("Status", str(getattr(r, "status", "—"))),
                ("Drawer", f"{getattr(r, 'waste_drawer_level', 0):.0f}%"),
                ("Sleeping", "yes" if getattr(r, "sleeping", False) else "no"),
                ("Locked", "yes" if getattr(r, "panel_lockout", False) else "no"),
                ("Night light", "on" if getattr(r, "night_light_mode_enabled", False) else "off"),
                ("Online", "yes" if getattr(r, "is_online", False) else "no"),
                ("Serial", getattr(r, "serial", "—")),
            ]
            log = app.query_one("#log", RichLog)
            for k, v in rows:
                t = Text()
                t.append(f"  {k:<14}", style="#484f58")
                t.append(str(v), style="#c9d1d9")
                log.write(t)
        except Exception as exc:
            app._log_err(f"Status refresh failed: {exc}")


class LockCommand(Command):
    name = "lock"
    description = "toggle panel lockout"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "lock / unlock"

    async def run(self, app: Any, args: list[str]) -> None:
        try:
            await app._robot.set_panel_lockout(True)
            app._log_ok("Panel locked")
        except Exception as exc:
            app._log_err(f"Failed: {exc}")


class UnlockCommand(Command):
    name = "unlock"
    description = "toggle panel lockout"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "lock / unlock"

    async def run(self, app: Any, args: list[str]) -> None:
        try:
            await app._robot.set_panel_lockout(False)
            app._log_ok("Panel unlocked")
        except Exception as exc:
            app._log_err(f"Failed: {exc}")


class SleepCommand(Command):
    name = "sleep"
    description = "toggle sleep mode"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "sleep / wake"

    async def run(self, app: Any, args: list[str]) -> None:
        try:
            await app._robot.set_sleep_mode(True)
            app._log_ok("Sleep mode enabled")
            app._set_cat("sleeping", "sleeping…")
        except Exception as exc:
            app._log_err(f"Failed: {exc}")


class WakeCommand(Command):
    name = "wake"
    description = "toggle sleep mode"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "sleep / wake"

    async def run(self, app: Any, args: list[str]) -> None:
        try:
            await app._robot.set_sleep_mode(False)
            app._log_ok("Robot woken up")
            app._set_cat("happy", "awake!")
        except Exception as exc:
            app._log_err(f"Failed: {exc}")


class NightLightCommand(Command):
    name = "night-light"
    aliases = ("nightlight", "nl")
    description = "toggle night light"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "night-light on|off"

    async def run(self, app: Any, args: list[str]) -> None:
        arg = args[0].lower() if args else ""
        if arg not in ("on", "off"):
            app._log_warn("Usage: night-light on|off")
            return
        try:
            if hasattr(app._robot, "set_night_light_brightness"):
                await app._robot.set_night_light_brightness(100 if arg == "on" else 0)
            elif hasattr(app._robot, "set_night_light_mode"):
                from pylitterbot.enums import NightLightMode  # noqa: PLC0415

                mode = NightLightMode.ON if arg == "on" else NightLightMode.OFF
                await app._robot.set_night_light_mode(mode)
            else:
                app._log_warn("Night light control not supported by this robot version.")
                return
            app._log_ok(f"Night light {arg}")
        except Exception as exc:
            app._log_err(f"Failed: {exc}")


class HistoryCommand(Command):
    name = "history"
    aliases = ("hist",)
    description = "show recent activity log"
    requires_robot = True

    async def run(self, app: Any, args: list[str]) -> None:
        try:
            acts = await app._robot.get_activity_history(limit=25)
            log = app.query_one("#log", RichLog)
            if not acts:
                app._log_info("No activity history available.")
                return
            app._log_info(f"Last {len(acts)} events:")
            for act in reversed(acts):
                ts_dt = getattr(act, "timestamp", None)
                ts_str = ts_dt.strftime("%m/%d %H:%M") if ts_dt else "?"
                action = getattr(act, "action", "?")
                action_str = action.text if hasattr(action, "text") else str(action)
                t = Text()
                t.append(f"  {ts_str}  ", style="#484f58")
                t.append(action_str, style="#8b949e")
                log.write(t)
        except Exception as exc:
            app._log_err(f"Failed to get history: {exc}")


# ── app commands (no robot required) ────────────────────────────────────────


class HelpCommand(Command):
    name = "help"
    description = "show this message"

    async def run(self, app: Any, args: list[str]) -> None:
        app._show_help()


class ClearCommand(Command):
    name = "clear"
    description = "clear the log"

    async def run(self, app: Any, args: list[str]) -> None:
        app.query_one("#log", RichLog).clear()


class QuitCommand(Command):
    name = "quit"
    aliases = ("exit", "q")
    description = "exit Asher CLI"

    @property
    def display_name(self) -> str:
        return "quit / exit"

    async def run(self, app: Any, args: list[str]) -> None:
        app.exit()


# ── slash commands ──────────────────────────────────────────────────────────


class LoginCommand(SlashCommand):
    name = "login"
    description = "sign in or switch accounts"

    async def run(self, app: Any, args: list[str]) -> None:
        app._start_login_flow()


class LogoutCommand(SlashCommand):
    name = "logout"
    description = "sign out and re-enter credentials"

    async def run(self, app: Any, args: list[str]) -> None:
        from ..connection import _keyring_delete  # noqa: PLC0415

        if not app._account:
            app._log_warn("Not signed in.")
            return

        with contextlib.suppress(Exception):
            await app._account.disconnect()
        app._account = None
        app._robot = None
        _keyring_delete()
        app._log_ok("Signed out.")
        app._log_info("Type /login to sign in.")
        app._set_cat("idle", "not signed in")
        app._show_signed_out_state()
        app.query_one("#hint-bar", Static).update(_HINT_SIGNIN)


# ── registry ────────────────────────────────────────────────────────────────

_registry = CommandRegistry()
_registry.register(CleanCommand())
_registry.register(StatusCommand())
_registry.register(LockCommand())
_registry.register(UnlockCommand())
_registry.register(SleepCommand())
_registry.register(WakeCommand())
_registry.register(NightLightCommand())
_registry.register(HistoryCommand())
_registry.register(HelpCommand())
_registry.register(ClearCommand())
_registry.register(QuitCommand())
_registry.register(LoginCommand())
_registry.register(LogoutCommand())


# ── mixin ───────────────────────────────────────────────────────────────────


class CommandsMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _robot: Any
    _account: Any
    _cmd_history: list[str]
    _hist_idx: int
    _login: LoginFlow

    # ── input events ─────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        self.query_one("#cmd-input", Input).value = ""  # type: ignore[attr-defined]
        if not raw:
            return

        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]

        # Login flow intercepts before history/echo
        if self._login.state is LoginState.AWAITING_EMAIL:
            t = ts()
            t.append(f"  {raw}", style="#e6edf3")
            log.write(t)
            self._handle_login_email(raw)
            return

        if self._login.state is LoginState.AWAITING_PASSWORD:
            t = ts()
            t.append("  ••••••••", style="#484f58")
            log.write(t)
            self._handle_login_password(raw)
            return

        # Normal command — add to history and echo
        self._cmd_history.insert(0, raw)
        self._hist_idx = -1

        t = ts()
        t.append("> ", style="bold #3fb950")
        t.append(raw, style="#e6edf3")
        log.write(t)

        parts = raw.strip().split()
        raw_cmd = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []

        # Strip known prefixes (currently only "/")
        cmd_name = raw_cmd.lstrip("/")

        command = _registry.get(cmd_name)
        if command is None:
            if raw_cmd.startswith("/"):
                self._log_warn(f"Unknown slash command: '{raw}'  — try /login, /logout, /exit")  # type: ignore[attr-defined]
            else:
                self._log_warn(f"Unknown command: '{cmd_name}'  — type 'help' for list")  # type: ignore[attr-defined]
            return

        if command.requires_robot and self._robot is None:
            self._log_err("Not connected — type '/login' to sign in.")  # type: ignore[attr-defined]
            return

        self._dispatch_command(command, args)

    def on_key(self, event) -> None:  # type: ignore[override]
        cmd_input = self.query_one("#cmd-input", Input)  # type: ignore[attr-defined]
        if not cmd_input.has_focus:
            return
        if self._login.is_active:
            return  # disable history nav during login

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
        """Enter interactive login mode — prompts for email then password in the command bar."""
        if self._account:
            self._log_warn("Already signed in — use /logout to sign out first.")  # type: ignore[attr-defined]
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
        self.query_one("#hint-bar", Static).update(_HINT_DEFAULT)  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).password = False  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).placeholder = "type a command  (help for list)…"  # type: ignore[attr-defined]

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
        await command.run(self, args)

    # ── help ────────────────────────────────────────────────────────────────────

    def _show_help(self) -> None:
        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]
        log.write("")
        log.write(Text.from_markup("[bold #58a6ff]Robot commands[/]"))
        for cmd in _registry.robot:
            t = Text()
            t.append(f"  {cmd.help_name:<22}", style="#3fb950")
            t.append(cmd.description, style="#8b949e")
            log.write(t)
        log.write("")
        log.write(Text.from_markup("[bold #58a6ff]Slash commands[/]  [#484f58](app management)[/]"))
        for cmd in _registry.slash:
            t = Text()
            t.append(f"  {cmd.help_name:<22}", style="#d29922")
            t.append(cmd.description, style="#8b949e")
            log.write(t)
        log.write("")
