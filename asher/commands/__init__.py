"""Command dispatch and individual command handlers."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from rich.text import Text
from textual import work
from textual.widgets import Input, RichLog, Static

from ..helpers import ts

_HINT_DEFAULT = "help · clean · status · history · /login · /logout · quit"
_HINT_SIGNIN = "/login to sign in"


class CommandsMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _robot: Any
    _account: Any
    _cmd_history: list[str]
    _hist_idx: int
    _login_state: str
    _login_email: str

    # ── input events ─────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        self.query_one("#cmd-input", Input).value = ""  # type: ignore[attr-defined]
        if not raw:
            return

        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]

        # Login flow intercepts before history/echo
        if self._login_state == "awaiting_email":
            t = ts()
            t.append(f"  {raw}", style="#e6edf3")
            log.write(t)
            self._handle_login_email(raw)
            return

        if self._login_state == "awaiting_password":
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

        cmd = raw.split()[0].lower()

        if cmd in ("quit", "exit", "q"):
            self.exit()  # type: ignore[attr-defined]
            return
        if cmd == "help":
            self._show_help()
            return
        if cmd == "clear":
            log.clear()
            return

        if raw.startswith("/"):
            self._run_slash_cmd(raw)
        else:
            self._run_cmd(raw)

    def on_key(self, event) -> None:  # type: ignore[override]
        cmd_input = self.query_one("#cmd-input", Input)  # type: ignore[attr-defined]
        if not cmd_input.has_focus:
            return
        if self._login_state:
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
        self._login_state = "awaiting_email"
        self._login_email = ""
        self._set_cat("idle", "sign in")  # type: ignore[attr-defined]
        self.query_one("#prompt", Static).update("email ›")  # type: ignore[attr-defined]
        self.query_one("#hint-bar", Static).update("enter your Whisker account email")  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).placeholder = "your@email.com"  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).password = False  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).focus()  # type: ignore[attr-defined]
        self._log_info("Enter your Whisker account email:")  # type: ignore[attr-defined]

    def _handle_login_email(self, email: str) -> None:
        self._login_email = email
        self._login_state = "awaiting_password"
        self.query_one("#prompt", Static).update("password ›")  # type: ignore[attr-defined]
        self.query_one("#hint-bar", Static).update("password will not be shown")  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).placeholder = "password"  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).password = True  # type: ignore[attr-defined]
        self._log_info("Enter your password:")  # type: ignore[attr-defined]

    @work
    async def _handle_login_password(self, password: str) -> None:
        from ..connection import _keyring_save  # noqa: PLC0415

        email = self._login_email
        self._login_state = ""
        self._login_email = ""

        # Restore prompt and input to normal
        self.query_one("#prompt", Static).update(">")  # type: ignore[attr-defined]
        self.query_one("#hint-bar", Static).update(_HINT_DEFAULT)  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).password = False  # type: ignore[attr-defined]
        self.query_one("#cmd-input", Input).placeholder = "type a command  (help for list)…"  # type: ignore[attr-defined]

        saved = _keyring_save(email, password)
        if saved:
            self._log_info("Credentials saved to keyring.")  # type: ignore[attr-defined]
        else:
            self._log_warn("Keyring unavailable - signed in for this session only.")  # type: ignore[attr-defined]

        if self._account:
            with contextlib.suppress(Exception):
                await self._account.disconnect()
        self._account = None
        self._robot = None
        self._set_cat("idle", "connecting…")  # type: ignore[attr-defined]
        kwargs = {} if saved else {"email": email, "password": password}
        self._connect_worker(**kwargs)  # type: ignore[attr-defined]

    # ── slash-command dispatch (app management) ───────────────────────────────

    @work
    async def _run_slash_cmd(self, raw: str) -> None:
        parts = raw.strip().split()
        cmd = parts[0].lstrip("/").lower() if parts else ""

        if cmd in ("exit", "quit", "q"):
            self.exit()  # type: ignore[attr-defined]
        elif cmd == "login":
            self._start_login_flow()
        elif cmd == "logout":
            await self._cmd_logout()
        elif cmd == "help":
            self._show_help()
        else:
            self._log_warn(  # type: ignore[attr-defined]
                f"Unknown slash command: '{raw}'  — try /login, /logout, /exit"
            )

    # ── robot-command dispatch ────────────────────────────────────────────────

    @work
    async def _run_cmd(self, raw: str) -> None:
        parts = raw.strip().split()
        cmd = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []

        if self._robot is None:
            self._log_err("Not connected — type '/login' to sign in.")  # type: ignore[attr-defined]
            return

        if cmd == "clean":
            await self._cmd_clean()
        elif cmd == "status":
            await self._cmd_status()
        elif cmd == "lock":
            await self._cmd_lock(True)
        elif cmd == "unlock":
            await self._cmd_lock(False)
        elif cmd == "sleep":
            await self._cmd_sleep(True)
        elif cmd == "wake":
            await self._cmd_sleep(False)
        elif cmd in ("night-light", "nightlight", "nl"):
            await self._cmd_nightlight(args)
        elif cmd in ("history", "hist"):
            await self._cmd_history_list()
        else:
            self._log_warn(f"Unknown command: '{cmd}'  — type 'help' for list")  # type: ignore[attr-defined]

    # ── slash-command handlers ────────────────────────────────────────────────

    async def _cmd_logout(self) -> None:
        from ..connection import _keyring_delete  # noqa: PLC0415

        if not self._account:
            self._log_warn("Not signed in.")  # type: ignore[attr-defined]
            return

        with contextlib.suppress(Exception):
            await self._account.disconnect()
        self._account = None
        self._robot = None
        _keyring_delete()
        self._log_ok("Signed out.")  # type: ignore[attr-defined]
        self._log_info("Type /login to sign in.")  # type: ignore[attr-defined]
        self._set_cat("idle", "not signed in")  # type: ignore[attr-defined]
        self.query_one("#hint-bar", Static).update(_HINT_SIGNIN)  # type: ignore[attr-defined]

    # ── robot-command handlers ────────────────────────────────────────────────

    async def _cmd_clean(self) -> None:
        self._set_cat("cleaning", "cleaning…")  # type: ignore[attr-defined]
        try:
            await self._robot.start_cleaning()
            self._log_ok("Clean cycle started")  # type: ignore[attr-defined]
            await asyncio.sleep(3)
            await self._robot.refresh()
            await self._refresh_status()  # type: ignore[attr-defined]
            self._set_cat("happy", "all done!")  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_err(f"Failed to start cleaning: {exc}")  # type: ignore[attr-defined]
            self._set_cat("error", "error")  # type: ignore[attr-defined]

    async def _cmd_status(self) -> None:
        try:
            await self._robot.refresh()
            await self._refresh_status()  # type: ignore[attr-defined]
            r = self._robot
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
            log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]
            for k, v in rows:
                t = Text()
                t.append(f"  {k:<14}", style="#484f58")
                t.append(str(v), style="#c9d1d9")
                log.write(t)
        except Exception as exc:
            self._log_err(f"Status refresh failed: {exc}")  # type: ignore[attr-defined]

    async def _cmd_lock(self, lock: bool) -> None:
        action = "locked" if lock else "unlocked"
        try:
            await self._robot.set_panel_lockout(lock)
            self._log_ok(f"Panel {action}")  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_err(f"Failed: {exc}")  # type: ignore[attr-defined]

    async def _cmd_sleep(self, sleep: bool) -> None:
        try:
            await self._robot.set_sleep_mode(sleep)
            if sleep:
                self._log_ok("Sleep mode enabled")  # type: ignore[attr-defined]
                self._set_cat("sleeping", "sleeping…")  # type: ignore[attr-defined]
            else:
                self._log_ok("Robot woken up")  # type: ignore[attr-defined]
                self._set_cat("happy", "awake!")  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_err(f"Failed: {exc}")  # type: ignore[attr-defined]

    async def _cmd_nightlight(self, args: list[str]) -> None:
        arg = args[0].lower() if args else ""
        if arg not in ("on", "off"):
            self._log_warn("Usage: night-light on|off")  # type: ignore[attr-defined]
            return
        try:
            if hasattr(self._robot, "set_night_light_brightness"):
                await self._robot.set_night_light_brightness(100 if arg == "on" else 0)
            elif hasattr(self._robot, "set_night_light_mode"):
                from pylitterbot.enums import NightLightMode  # noqa: PLC0415

                mode = NightLightMode.ON if arg == "on" else NightLightMode.OFF
                await self._robot.set_night_light_mode(mode)
            else:
                self._log_warn("Night light control not supported by this robot version.")  # type: ignore[attr-defined]
                return
            self._log_ok(f"Night light {arg}")  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_err(f"Failed: {exc}")  # type: ignore[attr-defined]

    async def _cmd_history_list(self) -> None:
        try:
            acts = await self._robot.get_activity_history(limit=25)
            log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]
            if not acts:
                self._log_info("No activity history available.")  # type: ignore[attr-defined]
                return
            self._log_info(f"Last {len(acts)} events:")  # type: ignore[attr-defined]
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
            self._log_err(f"Failed to get history: {exc}")  # type: ignore[attr-defined]

    def _show_help(self) -> None:
        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]
        log.write("")
        log.write(Text.from_markup("[bold #58a6ff]Robot commands[/]"))
        robot_cmds = [
            ("clean", "start a clean cycle"),
            ("status", "refresh and display full status"),
            ("lock / unlock", "toggle panel lockout"),
            ("sleep / wake", "toggle sleep mode"),
            ("night-light on|off", "toggle night light"),
            ("history", "show recent activity log"),
            ("clear", "clear the log"),
            ("help", "show this message"),
            ("quit / exit", "exit Asher CLI"),
        ]
        for name, desc in robot_cmds:
            t = Text()
            t.append(f"  {name:<22}", style="#3fb950")
            t.append(desc, style="#8b949e")
            log.write(t)
        log.write("")
        log.write(Text.from_markup("[bold #58a6ff]Slash commands[/]  [#484f58](app management)[/]"))
        slash_cmds = [
            ("/login", "sign in or switch accounts"),
            ("/logout", "sign out and re-enter credentials"),
            ("/exit", "exit Asher CLI"),
        ]
        for name, desc in slash_cmds:
            t = Text()
            t.append(f"  {name:<22}", style="#d29922")
            t.append(desc, style="#8b949e")
            log.write(t)
        log.write("")
