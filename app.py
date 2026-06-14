#!/usr/bin/env python3
"""Asher CLI — Litter Robot 4 terminal dashboard."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Input, RichLog, Static

load_dotenv()

EMAIL    = os.getenv("LITTER_ROBOT_USER") or os.getenv("LR4_EMAIL", "")
PASSWORD = os.getenv("LITTER_ROBOT_PASSWORD") or os.getenv("LR4_PASSWORD", "")
VERSION  = "1.0.0"

# ── ASCII cats ────────────────────────────────────────────────────────────────

CATS: dict[str, list[str] | str] = {
    "idle": (
        "  /\\_____/\\\n"
        " /  o   o  \\\n"
        "( ==  ^  == )\n"
        " )         (\n"
        "(           )\n"
        " \\  |___|  /\n"
        "  \\_______/"
    ),
    "happy": (
        "  /\\_____/\\\n"
        " /  ^   ^  \\\n"
        "( ==  ω  == )\n"
        " )   ~~~   (\n"
        "(  ♪  ♫  ♪  )\n"
        " \\  |___|  /\n"
        "  \\_______/"
    ),
    "sleeping": (
        "  /\\_____/\\\n"
        " /  -   -  \\\n"
        "( == zZ Z == )\n"
        " )  ~~~~~~ (\n"
        "(  ~~~~~~~~)\n"
        " \\  |___|  /\n"
        "  \\_______/"
    ),
    "cleaning": [
        (
            "  /\\_____/\\\n"
            " /  o   o  \\\n"
            "( = spin ⟳ = )\n"
            " ) ~ ~ ~ ~ (\n"
            "(  whirrrr )\n"
            " \\  |___|  /\n"
            "  \\_______/"
        ),
        (
            "  /\\_____/\\\n"
            " /  @   @  \\\n"
            "( = ⟳ spin = )\n"
            " ) ~ ~ ~ ~ (\n"
            "(  whirrrr )\n"
            " \\  |___|  /\n"
            "  \\_______/"
        ),
        (
            "  /\\_____/\\\n"
            " /  o   o  \\\n"
            "( == ⟳ ⟳ == )\n"
            " ) ~ ~ ~ ~ (\n"
            "( whirrrr~ )\n"
            " \\  |___|  /\n"
            "  \\_______/"
        ),
    ],
    "error": (
        "  /\\_____/\\\n"
        " /  x   x  \\\n"
        "( ==  !  == )\n"
        " )   ???   (\n"
        "(   !!!!   )\n"
        " \\  |___|  /\n"
        "  \\_______/"
    ),
    "full": (
        "  /\\_____/\\\n"
        " /  o   o  \\\n"
        "( == !!  == )\n"
        " )  FULL!  (\n"
        "(  ░░░░░░  )\n"
        " \\  |___|  /\n"
        "  \\_______/"
    ),
}

# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
Screen {
    background: #0d1117;
    color: #c9d1d9;
}

/* ── Status bar ── */
#status-bar {
    background: #161b22;
    height: 4;
    border-bottom: solid #30363d;
    dock: top;
    padding: 0 2;
    layout: vertical;
}

.srow {
    height: 2;
    layout: horizontal;
    align: left middle;
}

.chunk {
    width: auto;
    padding: 0 2 0 0;
    height: 1;
}

/* ── Main ── */
#main-area {
    layout: horizontal;
    height: 1fr;
}

#log {
    width: 1fr;
    height: 1fr;
    background: #0d1117;
    padding: 1 2;
    scrollbar-background: #161b22;
    scrollbar-color: #30363d;
    scrollbar-color-hover: #58a6ff;
}

/* ── Cat panel ── */
#cat-panel {
    width: 24;
    background: #0d1117;
    border-left: solid #21262d;
    align: center middle;
    padding: 1;
    height: 1fr;
    layout: vertical;
}

#cat-art {
    color: #58a6ff;
    text-align: center;
    width: 22;
    content-align: center middle;
}

#cat-label {
    color: #484f58;
    text-style: italic;
    text-align: center;
    width: 22;
    padding-top: 1;
    height: 3;
}

/* ── Input bar ── */
#input-bar {
    background: #161b22;
    height: 3;
    border-top: solid #30363d;
    dock: bottom;
    layout: horizontal;
    align: left middle;
    padding: 0 2;
}

#prompt {
    color: #3fb950;
    width: auto;
    text-style: bold;
    padding: 0 1 0 0;
}

#cmd-input {
    width: 1fr;
    background: #161b22;
    color: #e6edf3;
    border: none;
    height: 1;
    padding: 0;
}

Input {
    border: none;
    background: #161b22;
    padding: 0;
}

Input:focus {
    border: none;
    outline: none;
}
"""

# ── helpers ───────────────────────────────────────────────────────────────────

def fmt_ago(dt: Optional[datetime]) -> str:
    if dt is None:
        return "never"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    s = int((datetime.now(timezone.utc) - dt).total_seconds())
    if s < 60:
        return f"{s}s ago"
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


def drawer_bar(pct: float, width: int = 14) -> Text:
    filled = max(0, min(width, int(width * pct / 100)))
    bar = "█" * filled + "░" * (width - filled)
    color = "#f85149" if pct >= 85 else "#d29922" if pct >= 60 else "#3fb950"
    t = Text()
    t.append("[", style="#484f58")
    t.append(bar, style=color)
    t.append("]", style="#484f58")
    return t


def ts() -> Text:
    t = Text()
    t.append(f"[{datetime.now().strftime('%H:%M:%S')}] ", style="#484f58")
    return t


# ── app ───────────────────────────────────────────────────────────────────────

class AsherApp(App):
    CSS = CSS

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_log", "Clear log"),
        Binding("escape", "blur_input", "Focus log", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._account = None
        self._robot = None
        self._pets: list = []
        self._cat_mode: str = "idle"
        self._cat_frame: int = 0
        self._cmd_history: list[str] = []
        self._hist_idx: int = -1

    # ── layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Container(id="status-bar"):
            with Container(classes="srow"):
                yield Static("", id="title-lbl",   classes="chunk")
                yield Static("", id="robot-lbl",   classes="chunk")
                yield Static("", id="online-lbl",  classes="chunk")
                yield Static("", id="status-lbl",  classes="chunk")
            with Container(classes="srow"):
                yield Static("", id="drawer-lbl",  classes="chunk")
                yield Static("", id="clean-lbl",   classes="chunk")
                yield Static("", id="weight-lbl",  classes="chunk")

        with Container(id="main-area"):
            yield RichLog(id="log", highlight=True, markup=True, wrap=True)
            with Container(id="cat-panel"):
                yield Static(CATS["idle"], id="cat-art")
                yield Static("idle", id="cat-label")

        with Container(id="input-bar"):
            yield Static(">", id="prompt")
            yield Input(placeholder="type a command  (help for list)…", id="cmd-input")

    # ── mount ─────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._refresh_title()
        self._show_welcome()
        self._connect_worker()
        self.set_interval(30, self._poll_status_interval)
        self.set_interval(0.9, self._tick_cat)
        self.query_one("#cmd-input", Input).focus()

    def _refresh_title(self) -> None:
        t = Text()
        t.append("◆ ", style="bold #58a6ff")
        t.append("Asher CLI", style="bold #e6edf3")
        t.append(f" v{VERSION}", style="#484f58")
        self.query_one("#title-lbl", Static).update(t)

    def _show_welcome(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write("")
        log.write(Text.from_markup(
            " [bold #58a6ff]◆ Asher CLI[/] [#484f58]— Litter Robot 4 Dashboard[/]"
        ))
        log.write(Text.from_markup(
            " [#484f58]Connecting to Whisker cloud API…[/]"
        ))
        log.write(Text.from_markup(
            " [#484f58]Type [/][#3fb950]help[/][#484f58] to see available commands.[/]"
        ))
        log.write(Text.from_markup(" [#21262d]" + "─" * 52 + "[/]"))
        log.write("")

    # ── connection ────────────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _connect_worker(self) -> None:
        log = self.query_one("#log", RichLog)
        if not EMAIL or not PASSWORD:
            self._log_err("No credentials found.")
            self._log_err("Set LITTER_ROBOT_USER and LITTER_ROBOT_PASSWORD in .env")
            self._set_cat("error", "no creds")
            return

        try:
            from pylitterbot import Account  # noqa: PLC0415
            self._account = Account()
            await self._account.connect(
                username=EMAIL, password=PASSWORD, load_robots=True, load_pets=True
            )
            self._pets = list(self._account.pets)
            robots = list(self._account.robots)
            if not robots:
                self._log_err("No Litter Robots found on this account.")
                self._set_cat("error", "no robots")
                return

            # pick first robot; list all if multiple
            self._robot = robots[0]
            if len(robots) > 1:
                self._log_info(f"{len(robots)} robots found — using '{getattr(robots[0], 'name', 'robot #1')}'")
                for i, rb in enumerate(robots):
                    model = type(rb).__name__
                    self._log_info(f"  [{i}] {getattr(rb, 'name', '?')} ({model}  serial={getattr(rb, 'serial', '?')})")

            await self._refresh_status()

            t = ts()
            t.append("✓ Connected to ", style="#3fb950")
            name  = getattr(self._robot, "name",  "robot")
            model = type(self._robot).__name__
            t.append(name,            style="bold #e6edf3")
            t.append(f" ({model})",   style="#484f58")
            log.write(t)
            self._set_cat("happy", "connected!")

        except ImportError:
            self._log_err("pylitterbot not installed. Run: pip install pylitterbot")
            self._set_cat("error", "missing dep")
        except Exception as exc:
            self._log_err(f"Connection failed: {exc}")
            self._set_cat("error", "auth error")

    # ── status refresh ────────────────────────────────────────────────────────

    async def _refresh_status(self) -> None:
        r = self._robot
        if r is None:
            return

        name     = getattr(r, "name",              "—")
        online   = getattr(r, "is_online",         False)
        drawer   = float(getattr(r, "waste_drawer_level", 0) or 0)
        status   = getattr(r, "status",            None)
        sleeping = getattr(r, "sleeping",          False)
        last_seen = getattr(r, "last_seen",        None)

        status_str = status.value if status else ("Sleeping" if sleeping else "Ready")

        # cat weight — robot.pet_weight is the last scale reading
        weight_val = "—"
        try:
            w = getattr(r, "pet_weight", None)
            if w is not None and float(w) > 0:
                weight_val = f"{float(w):.1f} lb"
        except Exception:
            pass

        # pet name from account profile
        pet_name = self._pets[0].name if self._pets else None

        # update header widgets
        robot_lbl = self.query_one("#robot-lbl", Static)
        robot_lbl.update(Text(name, style="bold #e6edf3"))

        online_lbl = self.query_one("#online-lbl", Static)
        if online:
            online_lbl.update(Text("● ONLINE",  style="bold #3fb950"))
        else:
            online_lbl.update(Text("○ OFFLINE", style="bold #f85149"))

        status_lbl = self.query_one("#status-lbl", Static)
        status_lbl.update(Text(f"[{status_str}]", style="#8b949e"))

        drawer_lbl = self.query_one("#drawer-lbl", Static)
        bar = drawer_bar(drawer)
        dt = Text()
        dt.append("Drawer ", style="#484f58")
        dt.append_text(bar)
        dt.append(f" {drawer:.0f}%", style="#8b949e")
        drawer_lbl.update(dt)

        clean_lbl = self.query_one("#clean-lbl", Static)
        clean_lbl.update(Text(f"Last seen {fmt_ago(last_seen)}", style="#484f58"))

        wt = self.query_one("#weight-lbl", Static)
        wt_text = Text()
        if pet_name:
            wt_text.append(pet_name, style="#8b949e")
            wt_text.append(" 🐱 ",  style="#484f58")
        else:
            wt_text.append("cat ",  style="#484f58")
        wt_text.append(weight_val,  style="#8b949e")
        wt.update(wt_text)

        # warn if drawer nearly full
        if drawer >= 85 and self._cat_mode not in ("cleaning", "error"):
            self._set_cat("full", "drawer full!")

    @work(exclusive=True)
    async def _poll_status_interval(self) -> None:
        if self._robot is None:
            return
        try:
            await self._robot.refresh()
            await self._refresh_status()
        except Exception:
            pass

    # ── cat animation ─────────────────────────────────────────────────────────

    def _set_cat(self, mode: str, label: str = "") -> None:
        self._cat_mode  = mode
        self._cat_frame = 0
        cats = CATS.get(mode, CATS["idle"])
        frame = cats[0] if isinstance(cats, list) else cats
        color = "#f85149" if mode == "error" else "#d29922" if mode == "full" else "#58a6ff"
        self.query_one("#cat-art",   Static).update(Text(frame, style=color))
        self.query_one("#cat-label", Static).update(
            Text(label or mode, style="italic #484f58")
        )

    def _tick_cat(self) -> None:
        cats = CATS.get(self._cat_mode, CATS["idle"])
        if not isinstance(cats, list):
            return
        self._cat_frame = (self._cat_frame + 1) % len(cats)
        frame = cats[self._cat_frame]
        self.query_one("#cat-art", Static).update(Text(frame, style="#58a6ff"))

    # ── input handling ────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        self.query_one("#cmd-input", Input).value = ""
        if not raw:
            return

        self._cmd_history.insert(0, raw)
        self._hist_idx = -1

        log = self.query_one("#log", RichLog)
        t = ts()
        t.append("> ", style="bold #3fb950")
        t.append(raw, style="#e6edf3")
        log.write(t)

        self._run_cmd(raw)

    def on_key(self, event) -> None:
        cmd_input = self.query_one("#cmd-input", Input)
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

    # ── command dispatch ──────────────────────────────────────────────────────

    @work
    async def _run_cmd(self, raw: str) -> None:
        parts = raw.strip().split()
        cmd   = parts[0].lower() if parts else ""
        args  = parts[1:] if len(parts) > 1 else []

        if cmd in ("quit", "exit", "q"):
            self.exit()
            return

        if cmd == "help":
            self._show_help()
            return

        if cmd == "clear":
            self.query_one("#log", RichLog).clear()
            return

        if self._robot is None:
            self._log_err("Not connected. Check .env credentials and restart.")
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
            self._log_warn(f"Unknown command: '{cmd}'  — type 'help' for list")

    # ── individual commands ───────────────────────────────────────────────────

    async def _cmd_clean(self) -> None:
        self._set_cat("cleaning", "cleaning…")
        try:
            await self._robot.start_cleaning()
            self._log_ok("Clean cycle started")
            await asyncio.sleep(3)
            await self._robot.refresh()
            await self._refresh_status()
            self._set_cat("happy", "all done!")
        except Exception as exc:
            self._log_err(f"Failed to start cleaning: {exc}")
            self._set_cat("error", "error")

    async def _cmd_status(self) -> None:
        try:
            await self._robot.refresh()
            await self._refresh_status()
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
            log = self.query_one("#log", RichLog)
            for k, v in rows:
                t = Text()
                t.append(f"  {k:<14}", style="#484f58")
                t.append(str(v), style="#c9d1d9")
                log.write(t)
        except Exception as exc:
            self._log_err(f"Status refresh failed: {exc}")

    async def _cmd_lock(self, lock: bool) -> None:
        action = "locked" if lock else "unlocked"
        try:
            await self._robot.set_panel_lockout(lock)
            self._log_ok(f"Panel {action}")
        except Exception as exc:
            self._log_err(f"Failed: {exc}")

    async def _cmd_sleep(self, sleep: bool) -> None:
        try:
            await self._robot.set_sleep_mode(sleep)
            if sleep:
                self._log_ok("Sleep mode enabled")
                self._set_cat("sleeping", "sleeping…")
            else:
                self._log_ok("Robot woken up")
                self._set_cat("happy", "awake!")
        except Exception as exc:
            self._log_err(f"Failed: {exc}")

    async def _cmd_nightlight(self, args: list[str]) -> None:
        arg = args[0].lower() if args else ""
        if arg not in ("on", "off"):
            self._log_warn("Usage: night-light on|off")
            return
        try:
            # try brightness method first, fall back to mode setter
            if hasattr(self._robot, "set_night_light_brightness"):
                await self._robot.set_night_light_brightness(100 if arg == "on" else 0)
            elif hasattr(self._robot, "set_night_light_mode"):
                from pylitterbot.enums import NightLightMode  # noqa: PLC0415
                mode = NightLightMode.ON if arg == "on" else NightLightMode.OFF
                await self._robot.set_night_light_mode(mode)
            else:
                self._log_warn("Night light control not supported by this robot version.")
                return
            self._log_ok(f"Night light {arg}")
        except Exception as exc:
            self._log_err(f"Failed: {exc}")

    async def _cmd_history_list(self) -> None:
        try:
            acts = await self._robot.get_activity_history(limit=25)
            log  = self.query_one("#log", RichLog)
            if not acts:
                self._log_info("No activity history available.")
                return
            self._log_info(f"Last {len(acts)} events:")
            for act in acts:
                ts_dt  = getattr(act, "timestamp", None)
                ts_str = ts_dt.strftime("%m/%d %H:%M") if ts_dt else "?"
                action = getattr(act, "action", "?")
                # action is str or LitterBoxStatus
                action_str = action.text if hasattr(action, "text") else str(action)
                t = Text()
                t.append(f"  {ts_str}  ", style="#484f58")
                t.append(action_str,       style="#8b949e")
                log.write(t)
        except Exception as exc:
            self._log_err(f"Failed to get history: {exc}")

    def _show_help(self) -> None:
        log = self.query_one("#log", RichLog)
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

    # ── log helpers ───────────────────────────────────────────────────────────

    def _log_ok(self, msg: str) -> None:
        t = ts(); t.append(f"✓ {msg}", style="#3fb950")
        self.query_one("#log", RichLog).write(t)

    def _log_err(self, msg: str) -> None:
        t = ts(); t.append(f"✖ {msg}", style="#f85149")
        self.query_one("#log", RichLog).write(t)

    def _log_warn(self, msg: str) -> None:
        t = ts(); t.append(f"⚠ {msg}", style="#d29922")
        self.query_one("#log", RichLog).write(t)

    def _log_info(self, msg: str) -> None:
        t = ts(); t.append(f"  {msg}", style="#8b949e")
        self.query_one("#log", RichLog).write(t)

    # ── actions ───────────────────────────────────────────────────────────────

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()

    def action_blur_input(self) -> None:
        self.query_one("#cmd-input", Input).blur()

    async def on_unmount(self) -> None:
        if self._account:
            try:
                await self._account.disconnect()
            except Exception:
                pass


def main() -> None:
    AsherApp().run()


if __name__ == "__main__":
    main()
