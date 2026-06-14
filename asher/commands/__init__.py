"""Command dispatch and individual command handlers."""
from __future__ import annotations

import asyncio

from rich.text import Text
from textual import work
from textual.widgets import Input, RichLog

from ..helpers import ts


class CommandsMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _robot:       object | None
    _cmd_history: list[str]
    _hist_idx:    int

    # ── input events ─────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        self.query_one("#cmd-input", Input).value = ""  # type: ignore[attr-defined]
        if not raw:
            return

        self._cmd_history.insert(0, raw)
        self._hist_idx = -1

        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]
        t = ts()
        t.append("> ", style="bold #3fb950")
        t.append(raw,  style="#e6edf3")
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

        self._run_cmd(raw)

    def on_key(self, event) -> None:  # type: ignore[override]
        cmd_input = self.query_one("#cmd-input", Input)  # type: ignore[attr-defined]
        if not cmd_input.has_focus:
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

    # ── dispatch ──────────────────────────────────────────────────────────────

    @work
    async def _run_cmd(self, raw: str) -> None:
        parts = raw.strip().split()
        cmd   = parts[0].lower() if parts else ""
        args  = parts[1:] if len(parts) > 1 else []

        if self._robot is None:
            self._log_err("Not connected. Check .env credentials and restart.")  # type: ignore[attr-defined]
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

    # ── individual handlers ───────────────────────────────────────────────────

    async def _cmd_clean(self) -> None:
        self._set_cat("cleaning", "cleaning…")  # type: ignore[attr-defined]
        try:
            await self._robot.start_cleaning()  # type: ignore[union-attr]
            self._log_ok("Clean cycle started")  # type: ignore[attr-defined]
            await asyncio.sleep(3)
            await self._robot.refresh()           # type: ignore[union-attr]
            await self._refresh_status()          # type: ignore[attr-defined]
            self._set_cat("happy", "all done!")   # type: ignore[attr-defined]
        except Exception as exc:
            self._log_err(f"Failed to start cleaning: {exc}")  # type: ignore[attr-defined]
            self._set_cat("error", "error")                    # type: ignore[attr-defined]

    async def _cmd_status(self) -> None:
        try:
            await self._robot.refresh()   # type: ignore[union-attr]
            await self._refresh_status()  # type: ignore[attr-defined]
            r = self._robot
            rows = [
                ("Name",        getattr(r, "name",              "—")),
                ("Status",      str(getattr(r, "status",        "—"))),
                ("Drawer",      f"{getattr(r, 'waste_drawer_level', 0):.0f}%"),
                ("Sleeping",    "yes" if getattr(r, "sleeping", False) else "no"),
                ("Locked",      "yes" if getattr(r, "panel_lockout", False) else "no"),
                ("Night light", "on"  if getattr(r, "night_light_mode_enabled", False) else "off"),
                ("Online",      "yes" if getattr(r, "is_online", False) else "no"),
                ("Serial",      getattr(r, "serial", "—")),
            ]
            log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]
            for k, v in rows:
                t = Text()
                t.append(f"  {k:<14}", style="#484f58")
                t.append(str(v),       style="#c9d1d9")
                log.write(t)
        except Exception as exc:
            self._log_err(f"Status refresh failed: {exc}")  # type: ignore[attr-defined]

    async def _cmd_lock(self, lock: bool) -> None:
        action = "locked" if lock else "unlocked"
        try:
            await self._robot.set_panel_lockout(lock)  # type: ignore[union-attr]
            self._log_ok(f"Panel {action}")            # type: ignore[attr-defined]
        except Exception as exc:
            self._log_err(f"Failed: {exc}")            # type: ignore[attr-defined]

    async def _cmd_sleep(self, sleep: bool) -> None:
        try:
            await self._robot.set_sleep_mode(sleep)  # type: ignore[union-attr]
            if sleep:
                self._log_ok("Sleep mode enabled")          # type: ignore[attr-defined]
                self._set_cat("sleeping", "sleeping…")      # type: ignore[attr-defined]
            else:
                self._log_ok("Robot woken up")              # type: ignore[attr-defined]
                self._set_cat("happy", "awake!")            # type: ignore[attr-defined]
        except Exception as exc:
            self._log_err(f"Failed: {exc}")                 # type: ignore[attr-defined]

    async def _cmd_nightlight(self, args: list[str]) -> None:
        arg = args[0].lower() if args else ""
        if arg not in ("on", "off"):
            self._log_warn("Usage: night-light on|off")  # type: ignore[attr-defined]
            return
        try:
            if hasattr(self._robot, "set_night_light_brightness"):
                await self._robot.set_night_light_brightness(100 if arg == "on" else 0)  # type: ignore[union-attr]
            elif hasattr(self._robot, "set_night_light_mode"):
                from pylitterbot.enums import NightLightMode  # noqa: PLC0415
                mode = NightLightMode.ON if arg == "on" else NightLightMode.OFF
                await self._robot.set_night_light_mode(mode)  # type: ignore[union-attr]
            else:
                self._log_warn("Night light control not supported by this robot version.")  # type: ignore[attr-defined]
                return
            self._log_ok(f"Night light {arg}")  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_err(f"Failed: {exc}")     # type: ignore[attr-defined]

    async def _cmd_history_list(self) -> None:
        try:
            acts = await self._robot.get_activity_history(limit=25)  # type: ignore[union-attr]
            log  = self.query_one("#log", RichLog)                   # type: ignore[attr-defined]
            if not acts:
                self._log_info("No activity history available.")     # type: ignore[attr-defined]
                return
            self._log_info(f"Last {len(acts)} events:")              # type: ignore[attr-defined]
            for act in reversed(acts):
                ts_dt     = getattr(act, "timestamp", None)
                ts_str    = ts_dt.strftime("%m/%d %H:%M") if ts_dt else "?"
                action    = getattr(act, "action", "?")
                action_str = action.text if hasattr(action, "text") else str(action)
                t = Text()
                t.append(f"  {ts_str}  ", style="#484f58")
                t.append(action_str,       style="#8b949e")
                log.write(t)
        except Exception as exc:
            self._log_err(f"Failed to get history: {exc}")  # type: ignore[attr-defined]

    def _show_help(self) -> None:
        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]
        log.write("")
        log.write(Text.from_markup("[bold #58a6ff]Commands[/]"))
        cmds = [
            ("clean",              "start a clean cycle"),
            ("status",             "refresh and display full status"),
            ("lock",               "enable panel lockout"),
            ("unlock",             "disable panel lockout"),
            ("sleep",              "enable sleep mode"),
            ("wake",               "wake from sleep"),
            ("night-light on|off", "toggle night light"),
            ("history",            "show recent activity log"),
            ("clear",              "clear the log"),
            ("help",               "show this message"),
            ("quit",               "exit Asher CLI"),
        ]
        for name, desc in cmds:
            t = Text()
            t.append(f"  {name:<22}", style="#3fb950")
            t.append(desc,            style="#8b949e")
            log.write(t)
        log.write("")
