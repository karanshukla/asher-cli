"""Command dispatch and individual command handlers."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timezone
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from ..app import AsherApp
    from ..robot_protocol import RobotProtocol

from pylitterbot.enums import LitterBoxStatus
from pylitterbot.robot import EVENT_UPDATE
from rich.text import Text
from textual import work
from textual.widgets import Input, RichLog, Static
from tzlocal import get_localzone

from ..helpers import robot_model, ts
from ..login_flow import LoginFlow, LoginState
from .base import Command, CommandRegistry, SlashCommand

_CYCLING_STATUSES = frozenset(
    {
        LitterBoxStatus.CLEAN_CYCLE,
        LitterBoxStatus.EMPTY_CYCLE,
        LitterBoxStatus.PAUSED,
        LitterBoxStatus.POWER_UP,
        LitterBoxStatus.POWER_DOWN,
    }
)

_HINT_DEFAULT = "help · clean · status · history · /login · /logout · quit"
_HINT_SIGNIN = "/login to sign in"


# ── robot commands ──────────────────────────────────────────────────────────


class CleanCommand(Command):
    name = "clean"
    description = "start a clean cycle"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._robot is not None
        app._set_cat("cleaning", "cleaning…")

        done: asyncio.Event = asyncio.Event()
        seen_cycling = False

        def _on_update() -> None:
            nonlocal seen_cycling
            status = getattr(app._robot, "status", None)
            if status in _CYCLING_STATUSES:
                seen_cycling = True
            elif seen_cycling or status is LitterBoxStatus.CLEAN_CYCLE_COMPLETE:
                done.set()

        unsubscribe = app._robot.on(EVENT_UPDATE, _on_update)
        try:
            await app._robot.start_cleaning()
        except Exception as exc:
            unsubscribe()
            app._log_err(f"Failed to start cleaning: {exc}")
            app._set_cat("error", "error")
            return

        app._log_ok("Clean cycle started")
        timed_out = False
        try:
            await asyncio.wait_for(done.wait(), timeout=300)
        except asyncio.TimeoutError:
            timed_out = True
        finally:
            unsubscribe()

        await app._robot.refresh()
        await app._refresh_status()
        if timed_out:
            app._log_warn("Clean cycle timed out - status may not reflect completion")
            app._set_cat("idle", "timed out")
        else:
            app._log_ok("Clean cycle complete")
            app._set_cat("happy", "all done!")


class StatusCommand(Command):
    name = "status"
    description = "refresh and display full status"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._robot is not None
        try:
            await app._robot.refresh()
            await app._refresh_status()
            r = app._robot
            rows = [
                ("Name", r.name),
                ("Status", str(r.status)),
                ("Drawer", f"{r.waste_drawer_level:.0f}%"),
                ("Sleeping", "yes" if r.sleep_mode_enabled else "no"),
                ("Locked", "yes" if r.panel_lock_enabled else "no"),
                ("Night light", "on" if r.night_light_mode_enabled else "off"),
                ("Online", "yes" if r.is_online else "no"),
                ("Serial", r.serial),
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
    description = "lock the panel"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "lock / unlock"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._adapter is not None
        ok, msg = await app._adapter.set_panel_lockout(True)
        if ok:
            app.query_one("#lock-lbl", Static).update(Text("⊘ Locked", style="bold #d29922"))
            app._log_ok(msg)
        else:
            app._log_err(msg)


class UnlockCommand(Command):
    name = "unlock"
    description = "unlock the panel"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "lock / unlock"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._adapter is not None
        ok, msg = await app._adapter.set_panel_lockout(False)
        if ok:
            app.query_one("#lock-lbl", Static).update(Text("□ Unlocked", style="#484f58"))
            app._log_ok(msg)
        else:
            app._log_err(msg)


class SleepCommand(Command):
    name = "sleep"
    description = "enable sleep mode"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "sleep / wake"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._adapter is not None
        ok, msg = await app._adapter.set_sleep(True)
        if ok:
            app._log_ok(msg)
            app._set_cat("sleeping", "sleeping...")
            await asyncio.sleep(2)
            await app._robot.refresh()  # type: ignore[union-attr]
            await app._refresh_status()
        else:
            app._log_warn(msg)


class WakeCommand(Command):
    name = "wake"
    description = "disable sleep mode"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "sleep / wake"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._adapter is not None
        ok, msg = await app._adapter.set_sleep(False)
        if ok:
            app._log_ok(msg)
            app._set_cat("happy", "awake!")
            await asyncio.sleep(2)
            await app._robot.refresh()  # type: ignore[union-attr]
            await app._refresh_status()
        else:
            app._log_warn(msg)


class NightLightCommand(Command):
    name = "night-light"
    aliases = ("nightlight", "nl")
    description = "set night light mode"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "night-light on|off|auto"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._adapter is not None
        arg = args[0].lower() if args else ""
        if arg not in ("on", "off", "auto"):
            app._log_warn("Usage: night-light on|off|auto")
            return
        ok, msg = await app._adapter.set_night_light(arg)
        if ok:
            app._log_ok(msg)
            if arg == "off":
                nl = Text("○", style="#484f58")
            elif arg == "auto":
                nl = Text("◐", style="#58a6ff")
            else:
                nl = Text("☀", style="#d29922")
            app.query_one("#nightlight-lbl", Static).update(nl)
        else:
            app._log_warn(msg)


class NightLightBrightnessCommand(Command):
    name = "night-light-brightness"
    aliases = ("nlb",)
    description = "<level> set night light brightness"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "night-light-brightness"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._adapter is not None
        if not args or not args[0].isdigit():
            app._log_warn("Usage: night-light-brightness <level>")
            return
        level = int(args[0])
        ok, msg = await app._adapter.set_night_light_brightness(level)
        if ok:
            app._log_ok(msg)
            r = app._robot
            nl_mode = getattr(r, "night_light_mode", None)
            nl_enabled = getattr(r, "night_light_mode_enabled", False)
            mode_str = (
                nl_mode.value.lower() if nl_mode is not None else ("on" if nl_enabled else "off")
            )
            if mode_str == "off":
                nl_emoji, nl_color = "○", "#484f58"
            elif mode_str == "auto":
                nl_emoji, nl_color = "◐", "#58a6ff"
            else:
                nl_emoji, nl_color = "☀", "#d29922"
            nl = Text()
            nl.append(nl_emoji, style=nl_color)
            if mode_str != "off":
                nl.append(f"  {level}%", style="#484f58")
            app.query_one("#nightlight-lbl", Static).update(nl)
        else:
            app._log_warn(msg)


class HistoryCommand(Command):
    name = "history"
    aliases = ("hist",)
    description = "show recent activity log"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._robot is not None
        try:
            acts = await app._robot.get_activity_history(limit=25)
            log = app.query_one("#log", RichLog)
            if not acts:
                app._log_info("No activity history available.")
                return
            app._log_info(f"Last {len(acts)} events:")
            for act in reversed(acts):
                ts_dt = getattr(act, "timestamp", None)
                if ts_dt:
                    if ts_dt.tzinfo is None:
                        ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                    ts_dt = ts_dt.astimezone(get_localzone())
                    ts_str = ts_dt.strftime("%m/%d %H:%M %Z")
                else:
                    ts_str = "?"
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
    aliases = ("commands",)
    description = "show this message"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        app._show_help()


class ClearCommand(Command):
    name = "clear"
    description = "clear the log"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        app.query_one("#log", RichLog).clear()


class QuitCommand(Command):
    name = "quit"
    aliases = ("exit", "q")
    description = "exit Asher CLI"

    @property
    def display_name(self) -> str:
        return "quit / exit"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        app.exit()


# ── slash commands ──────────────────────────────────────────────────────────


class LoginCommand(SlashCommand):
    name = "login"
    description = "sign in or switch accounts"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        app._start_login_flow()


class LogoutCommand(SlashCommand):
    name = "logout"
    description = "sign out and re-enter credentials"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        from ..connection import _keyring_delete  # noqa: PLC0415

        if not app._account:
            app._log_warn("Not signed in.")
            return

        if app._robot:
            with contextlib.suppress(Exception):
                await app._robot.unsubscribe()
        with contextlib.suppress(Exception):
            await app._account.disconnect()
        app._account = None
        app._robot = None
        app._adapter = None
        _keyring_delete()
        app._log_ok("Signed out.")
        app._log_info("Type /login to sign in.")
        app._set_cat("idle", "not signed in")
        app._show_signed_out_state()
        app.query_one("#hint-bar", Static).update(_HINT_SIGNIN)


class RobotsCommand(SlashCommand):
    name = "robots"
    description = "list all robots on the account"

    async def run(self, app: AsherApp, args: list[str]) -> None:  # noqa: ARG002
        robots = app._robots
        if not robots:
            app._log_warn("No robots loaded - use /login to connect first.")
            return
        log = app.query_one("#log", RichLog)
        for idx, robot in enumerate(robots):
            active = robot is app._robot
            t = ts()
            t.append("  ● " if active else "    ", style="#3fb950" if active else "#484f58")
            t.append(f"[{idx}] ", style="#484f58")
            t.append(getattr(robot, "name", "-"), style="#e6edf3" if active else "#c9d1d9")
            t.append(f"  {robot_model(robot)}", style="#484f58")
            log.write(t)


class RobotCommand(SlashCommand):
    name = "robot"
    description = "<index|name> switch active robot"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        robots = app._robots
        if not robots:
            app._log_warn("No robots loaded - use /login to connect first.")
            return

        if not args:
            app._log_info("Usage: /robot <index|name>  - use /robots to list")
            return

        target = " ".join(args)
        robot = None
        if target.isdigit():
            idx = int(target)
            if 0 <= idx < len(robots):
                robot = robots[idx]
            else:
                app._log_warn(f"No robot at index {idx} - use /robots to list")
                return
        else:
            tl = target.lower()
            robot = next((rb for rb in robots if tl in getattr(rb, "name", "").lower()), None)
            if robot is None:
                app._log_warn(f"No robot matching '{target}' - use /robots to list")
                return

        if robot is app._robot:
            app._log_info(f"Already using '{getattr(robot, 'name', '?')}'")
            return

        if app._robot is not None:
            with contextlib.suppress(Exception):
                await app._robot.unsubscribe()

        app._robot = robot
        from ..robot_adapters import make_adapter  # noqa: PLC0415

        app._adapter = make_adapter(robot)
        await app._start_monitoring()  # type: ignore[attr-defined]
        await app._update_last_cat_seen()  # type: ignore[attr-defined]
        await app._refresh_status()  # type: ignore[attr-defined]

        name = getattr(robot, "name", "?")
        app._log_ok(f"Switched to '{name}' ({robot_model(robot)})")
        app._set_cat("happy", "connected!")  # type: ignore[attr-defined]

        serial = getattr(robot, "serial", None)
        if serial:
            from ..connection import _keyring_save_robot  # noqa: PLC0415

            _keyring_save_robot(serial)


# ── registry ────────────────────────────────────────────────────────────────

_registry = CommandRegistry()
_registry.register(CleanCommand())
_registry.register(StatusCommand())
_registry.register(LockCommand())
_registry.register(UnlockCommand())
_registry.register(SleepCommand())
_registry.register(WakeCommand())
_registry.register(NightLightCommand())
_registry.register(NightLightBrightnessCommand())
_registry.register(HistoryCommand())
_registry.register(HelpCommand())
_registry.register(ClearCommand())
_registry.register(QuitCommand())
_registry.register(LoginCommand())
_registry.register(LogoutCommand())
_registry.register(RobotsCommand())
_registry.register(RobotCommand())


# ── mixin ───────────────────────────────────────────────────────────────────


class CommandsMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _robot: RobotProtocol | None
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

        # Normal command - add to history and echo
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
                self._log_warn(f"Unknown slash command: '{raw}'  - try /login, /logout, /exit")  # type: ignore[attr-defined]
            else:
                self._log_warn(f"Unknown command: '{cmd_name}'  - type 'help' for list")  # type: ignore[attr-defined]
            return

        if command.requires_robot and self._robot is None:
            self._log_err("Not connected - type '/login' to sign in.")  # type: ignore[attr-defined]
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
        self.query_one("#hint-bar", Static).update(_HINT_DEFAULT)  # type: ignore[attr-defined]
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
        log.write(Text.from_markup("[bold #58a6ff]Robot commands[/]"))
        seen: set[str] = set()
        for cmd in _registry.robot:
            if cmd.display_name in seen:
                continue
            seen.add(cmd.display_name)
            t = Text()
            t.append(f"  {cmd.help_name:<24}", style="#3fb950")
            t.append(cmd.description, style="#8b949e")
            log.write(t)
        log.write("")
        log.write(Text.from_markup("[bold #58a6ff]Slash commands[/]  [#484f58](app management)[/]"))
        for cmd in _registry.slash:
            t = Text()
            t.append(f"  {cmd.help_name:<24}", style="#d29922")
            t.append(cmd.description, style="#8b949e")
            log.write(t)
        log.write("")
