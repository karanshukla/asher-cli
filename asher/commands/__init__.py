"""Command dispatch and individual command handlers."""

from __future__ import annotations

import asyncio
import contextlib
import csv
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
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

from ..activity_labels import ACTION_LABELS, activity_raw_text, format_activity
from ..helpers import fmt_ago, robot_model, ts
from ..login_flow import LoginFlow, LoginState
from .base import Command, CommandRegistry, SlashCommand


def _fmt_wait_time(minutes: object) -> str:
    """Render a clean-cycle wait time, tolerating a missing/None value."""
    if minutes is None:
        return "—"
    try:
        return f"{int(float(str(minutes)))} min"
    except (TypeError, ValueError):
        return "—"


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
    description = "refresh and show at-a-glance status"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._robot is not None
        try:
            await app._robot.refresh()
            await app._refresh_status()
        except Exception as exc:
            app._log_err(f"Status refresh failed: {exc}")
            return
        r = app._robot
        weight = "—"
        try:
            w = getattr(r, "pet_weight", None)
            if w is not None and float(w) > 0:
                weight = f"{float(w):.1f} lb"
        except Exception:
            pass
        last_seen = getattr(app, "_last_cat_seen", None) or getattr(r, "last_seen", None)
        rows = [
            ("Online", "yes" if getattr(r, "is_online", False) else "no"),
            ("Status", str(getattr(r, "status", "—"))),
            ("Drawer", f"{float(getattr(r, 'waste_drawer_level', 0) or 0):.0f}%"),
            ("Last seen", fmt_ago(last_seen)),
            ("Cat weight", weight),
        ]
        log = app.query_one("#log", RichLog)
        for k, v in rows:
            t = Text()
            t.append(f"  {k:<14}", style="#484f58")
            t.append(str(v), style="#c9d1d9")
            log.write(t)


class InfoCommand(Command):
    name = "info"
    description = "show full robot details (model, serial, firmware, …)"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._robot is not None
        try:
            await app._robot.refresh()
        except Exception as exc:
            app._log_err(f"Info refresh failed: {exc}")
            return
        r = app._robot

        def _yn(flag: object) -> str:
            return "yes" if flag else "no"

        # Properties marked optional are LR4/LR5-specific and absent on LR3 —
        # read via getattr so the command degrades gracefully across models.
        nl_mode = getattr(r, "night_light_mode", None)
        nl_enabled = getattr(r, "night_light_mode_enabled", False)
        night_str = (
            nl_mode.value.lower() if nl_mode is not None else ("on" if nl_enabled else "off")
        )
        last_seen = getattr(app, "_last_cat_seen", None) or getattr(r, "last_seen", None)
        rows = [
            ("Name", getattr(r, "name", "—")),
            ("Model", robot_model(r)),
            ("Serial", getattr(r, "serial", "—")),
            ("Firmware", getattr(r, "firmware", "—") or "—"),
            ("Wait time", _fmt_wait_time(getattr(r, "clean_cycle_wait_time_minutes", None))),
            ("Sleeping", _yn(getattr(r, "sleep_mode_enabled", False))),
            ("Panel locked", _yn(getattr(r, "panel_lock_enabled", False))),
            ("Night light", night_str),
            ("Drawer", f"{float(getattr(r, 'waste_drawer_level', 0) or 0):.0f}%"),
            ("Online", _yn(getattr(r, "is_online", False))),
            ("Last seen", fmt_ago(last_seen)),
        ]
        log = app.query_one("#log", RichLog)
        for k, v in rows:
            t = Text()
            t.append(f"  {k:<14}", style="#484f58")
            t.append(str(v), style="#c9d1d9")
            log.write(t)


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
            today = datetime.now(tz=timezone.utc).date()
            for act in reversed(acts):
                ts_dt = getattr(act, "timestamp", None)
                if ts_dt:
                    if ts_dt.tzinfo is None:
                        ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                    local_dt = ts_dt.astimezone(get_localzone())
                    # Show the year only for events older than today, to match
                    # the §11 "timestamps in activity history" note.
                    if local_dt.date() == today:
                        ts_str = local_dt.strftime("%H:%M")
                    elif local_dt.year == today.year:
                        ts_str = local_dt.strftime("%m/%d %H:%M")
                    else:
                        ts_str = local_dt.strftime("%Y-%m-%d %H:%M")
                else:
                    ts_str = "?"
                label, colour = format_activity(act, app._pets)
                t = Text()
                t.append(f"  {ts_str}  ", style="#484f58")
                t.append(label, style=colour)
                log.write(t)
        except Exception as exc:
            app._log_err(f"Failed to get history: {exc}")


class WaitTimeCommand(Command):
    name = "wait-time"
    aliases = ("waittime", "wait")
    description = "<minutes>  set clean-cycle wait time"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "wait-time <minutes>"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._robot is not None
        valid = sorted(getattr(app._robot, "VALID_WAIT_TIMES", []))
        if not args or not args[0].isdigit():
            current = getattr(app._robot, "clean_cycle_wait_time_minutes", "?")
            if valid:
                app._log_warn(f"Usage: wait-time <{'|'.join(str(v) for v in valid)}>")
                app._log_info(f"Current wait time: {current} min")
            else:
                app._log_warn("Usage: wait-time <minutes>")
            return

        minutes = int(args[0])
        if valid and minutes not in valid:
            app._log_warn(
                f"Invalid wait time {minutes} - use one of: {', '.join(str(v) for v in valid)}"
            )
            return

        try:
            ok = await app._robot.set_wait_time(minutes)
        except Exception as exc:
            app._log_err(f"Wait-time change failed: {exc}")
            return
        if ok:
            app._log_ok(f"Wait time set to {minutes} min")
            await app._robot.refresh()
            await app._refresh_status()
        else:
            app._log_warn("Wait-time command rejected by cloud")


class PowerCommand(Command):
    name = "power"
    description = "on|off  hard-power the unit"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "power on|off"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._robot is not None
        arg = args[0].lower() if args else ""
        if arg not in ("on", "off"):
            app._log_warn("Usage: power on|off")
            return
        try:
            ok = await app._robot.set_power_status(arg == "on")
        except Exception as exc:
            app._log_err(f"Power change failed: {exc}")
            return
        if ok:
            app._log_ok(f"Power {'on' if arg == 'on' else 'off'}")
            await app._robot.refresh()
            await app._refresh_status()
        else:
            app._log_warn("Power command rejected by cloud")


class RenameCommand(Command):
    name = "rename"
    description = "<new name>  rename the unit in the Whisker cloud"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "rename <name>"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._robot is not None
        if not args:
            app._log_warn(f"Usage: rename <new name>  (current: {app._robot.name})")
            return
        new_name = " ".join(args).strip()
        if not new_name:
            app._log_warn("Usage: rename <new name>")
            return
        try:
            ok = await app._robot.set_name(new_name)
        except Exception as exc:
            app._log_err(f"Rename failed: {exc}")
            return
        if ok:
            app._log_ok(f"Renamed to '{new_name}'")
            await app._robot.refresh()
            await app._refresh_status()
        else:
            app._log_warn("Rename command rejected by cloud")


class InsightCommand(Command):
    name = "insight"
    description = "[days]  show cycle-usage statistics (default: 30 days)"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._robot is not None
        raw = args[0].lower() if args else "30"
        if raw == "month":
            days = 30
        else:
            try:
                days = max(1, min(30, int(raw)))
            except ValueError:
                app._log_warn(f"Unknown period '{raw}' - use a number of days or 'month'")
                return

        app._log_info(f"Fetching insight (last {days} days)…")
        try:
            insight = await app._robot.get_insight(days=days)
        except Exception as exc:
            app._log_err(f"Failed to fetch insight: {exc}")
            return

        total = getattr(insight, "total_cycles", 0)
        avg = getattr(insight, "average_cycles", 0.0)
        history = getattr(insight, "cycle_history", []) or []

        log = app.query_one("#log", RichLog)
        rows = [
            ("Cycles", f"{total} (last {len(history)} days)"),
            ("Avg/day", f"{float(avg):.1f}"),
        ]
        # Peak day, if any history is present
        if history:
            peak_date, peak_count = max(history, key=lambda x: x[1])
            rows.append(("Peak day", f"{peak_count} on {peak_date.isoformat()}"))

        for k, v in rows:
            t = Text()
            t.append(f"  {k:<14}", style="#484f58")
            t.append(str(v), style="#c9d1d9")
            log.write(t)


# ── LR5-only commands ─────────────────────────────────────────────────────────
# These route through the adapter, which returns a "not supported" message on
# LR3/LR4 rather than crashing — so the commands are safe to type on any model.


class PrivacyCommand(Command):
    name = "privacy"
    description = "on|off  toggle LR5 privacy mode"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "privacy on|off"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._adapter is not None
        arg = args[0].lower() if args else ""
        if arg not in ("on", "off"):
            app._log_warn("Usage: privacy on|off")
            return
        ok, msg = await app._adapter.set_privacy_mode(arg == "on")
        if ok:
            app._log_ok(msg)
            await app._refresh_status()
        else:
            app._log_warn(msg)


class VolumeCommand(Command):
    name = "volume"
    description = "<0-100>  set LR5 sound volume"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "volume <0-100>"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._adapter is not None
        if not args or not args[0].lstrip("-").isdigit():
            current = getattr(app._robot, "sound_volume", None)
            extra = f"  (current: {current})" if current is not None else ""
            app._log_warn(f"Usage: volume <0-100>{extra}")
            return
        ok, msg = await app._adapter.set_volume(int(args[0]))
        if ok:
            app._log_ok(msg)
            await app._refresh_status()
        else:
            app._log_warn(msg)


class CameraAudioCommand(Command):
    name = "camera-audio"
    aliases = ("cameraaudio",)
    description = "on|off  toggle LR5 camera audio"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "camera-audio on|off"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._adapter is not None
        arg = args[0].lower() if args else ""
        if arg not in ("on", "off"):
            app._log_warn("Usage: camera-audio on|off")
            return
        ok, msg = await app._adapter.set_camera_audio(arg == "on")
        if ok:
            app._log_ok(msg)
            await app._refresh_status()
        else:
            app._log_warn(msg)


class DrawerResetCommand(Command):
    name = "drawer-reset"
    aliases = ("drawerreset",)
    description = "reset the LR5 waste drawer level indicator"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "drawer-reset"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        assert app._adapter is not None
        ok, msg = await app._adapter.reset_waste_drawer()
        if ok:
            app._log_ok(msg)
            await app._refresh_status()
        else:
            app._log_warn(msg)


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


class PetsCommand(SlashCommand):
    name = "pets"
    description = "list all pets on the account"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        pets = app._pets
        if not pets:
            app._log_warn("No pets found on this account.")
            return
        log = app.query_one("#log", RichLog)
        active_idx = getattr(app, "_active_pet_idx", 0)
        for idx, pet in enumerate(pets):
            active = idx == active_idx
            t = ts()
            t.append("  ● " if active else "    ", style="#3fb950" if active else "#484f58")
            t.append(f"[{idx}] ", style="#484f58")
            t.append(getattr(pet, "name", "-"), style="#e6edf3" if active else "#c9d1d9")
            log.write(t)


class PetCommand(SlashCommand):
    name = "pet"
    description = "<index|name> switch active pet in status bar"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        pets = app._pets
        if not pets:
            app._log_warn("No pets found on this account.")
            return

        if not args:
            app._log_info("Usage: /pet <index|name>  - use /pets to list")
            return

        target = args[0]
        if target.isdigit():
            idx = int(target)
            if 0 <= idx < len(pets):
                app._active_pet_idx = idx
                name = getattr(pets[idx], "name", str(idx))
                app._log_ok(f"Showing pet: {name}")
                await app._refresh_status()
            else:
                app._log_warn(f"No pet at index {idx} - use /pet to list")
        else:
            tl = target.lower()
            match = next(
                (i for i, p in enumerate(pets) if tl in getattr(p, "name", "").lower()), None
            )
            if match is None:
                app._log_warn(f"No pet matching '{target}' - use /pet to list")
                return
            app._active_pet_idx = match
            name = getattr(pets[match], "name", str(match))
            app._log_ok(f"Showing pet: {name}")
            await app._refresh_status()


class CatCommand(SlashCommand):
    name = "cat"
    description = "on|off|color <hex>  configure the cat panel"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if not args:
            app._log_info("Usage: /cat on|off|color <hex>")
            return

        sub = args[0].lower()
        if sub == "off":
            app.query_one("#cat-panel").display = False
            app._cat_panel_visible = False
            app._log_ok("Cat panel hidden")
        elif sub == "on":
            app.query_one("#cat-panel").display = True
            app._cat_panel_visible = True
            app._log_ok("Cat panel visible")
        elif sub == "color":
            if len(args) < 2:
                app._log_warn("Usage: /cat color <hex>  e.g. /cat color #ff79c6")
                return
            color = args[1]
            if not color.startswith("#"):
                color = f"#{color}"
            app._cat_color = color
            app._set_cat(app._cat_mode, getattr(app, "_cat_label", ""))
            app._log_ok(f"Cat color set to {color}")
        elif sub == "reset":
            app._cat_color = None
            app._set_cat(app._cat_mode, getattr(app, "_cat_label", ""))
            app._log_ok("Cat color reset to default")
        else:
            app._log_warn("Usage: /cat on|off|color <hex>")


class RefreshCommand(SlashCommand):
    name = "refresh"
    description = "<seconds|off>  change auto-refresh interval"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        poll_timer = getattr(app, "_poll_timer", None)

        if not args:
            interval = getattr(app, "_poll_interval", 300)
            if interval == 0:
                app._log_info("Auto-refresh is off")
            else:
                app._log_info(f"Auto-refresh interval: {interval}s")
            return

        raw = args[0].lower()
        if raw == "off":
            if poll_timer is not None:
                poll_timer.stop()
                app._poll_timer = None
            app._poll_interval = 0
            app._log_ok("Auto-refresh disabled")
            return

        try:
            seconds = max(10, int(raw))
        except ValueError:
            app._log_warn("Usage: /refresh <seconds|off>  (minimum 10s)")
            return

        if poll_timer is not None:
            poll_timer.stop()
        app._poll_timer = app.set_interval(seconds, app._poll_status_interval)
        app._poll_interval = seconds
        app._log_ok(f"Auto-refresh set to every {seconds}s")


class ConfigCommand(SlashCommand):
    name = "config"
    description = "show current runtime configuration"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        log = app.query_one("#log", RichLog)

        robot = app._robot
        robot_name = getattr(robot, "name", "—") if robot else "not connected"
        robot_info = f"{robot_name} ({robot_model(robot)})" if robot else robot_name

        interval = getattr(app, "_poll_interval", 300)
        refresh_str = f"{interval}s" if interval else "off"

        cat_visible = getattr(app, "_cat_panel_visible", True)
        cat_color = getattr(app, "_cat_color", None) or "#58a6ff (default)"

        pets = app._pets
        active_pet_idx = getattr(app, "_active_pet_idx", 0)
        if pets and active_pet_idx < len(pets):
            pet_str = f"{getattr(pets[active_pet_idx], 'name', '?')} (index {active_pet_idx})"
        elif pets:
            pet_str = f"{getattr(pets[0], 'name', '?')} (index 0)"
        else:
            pet_str = "none"

        rows = [
            ("robot", robot_info),
            ("refresh", refresh_str),
            ("cat panel", f"{'on' if cat_visible else 'off'}  {cat_color}"),
            ("active pet", pet_str),
        ]
        log.write("")
        for k, v in rows:
            t = Text()
            t.append(f"  {k:<14}", style="#484f58")
            t.append(v, style="#c9d1d9")
            log.write(t)
        log.write("")


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


async def _ensure_mcp_extra(app: AsherApp) -> bool:
    """Install pylitterbot's mcp extra if it isn't already available. Returns success."""
    from importlib.metadata import version as pkg_version  # noqa: PLC0415

    from ..mcp_config import mcp_extra_installed  # noqa: PLC0415

    if mcp_extra_installed():
        return True

    pin = f"pylitterbot[mcp]=={pkg_version('pylitterbot')}"
    app._log_info(f"Installing {pin}…")
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pip",
        "install",
        pin,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output = (await proc.communicate())[0].decode(errors="replace")
    if proc.returncode == 0:
        app._log_ok("Installed pylitterbot[mcp].")
        return True

    app._log_err("Failed to install pylitterbot[mcp]:")
    for line in output.splitlines()[-10:]:
        app._log_err(f"  {line}")
    app._log_info(f"Try manually: {sys.executable} -m pip install '{pin}'")
    return False


class McpCommand(SlashCommand):
    name = "mcp"
    description = "on|off|status  Litter-Robot MCP server for Claude Desktop"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        from ..mcp_config import mcp_status, set_mcp_enabled  # noqa: PLC0415

        sub = args[0].lower() if args else "status"
        if sub not in ("on", "off", "status"):
            app._log_warn("Usage: /mcp on|off|status")
            return

        if sub == "status":
            from ..connection import _keyring_load  # noqa: PLC0415

            email, password = _keyring_load()
            has_keyring_creds = bool(email and password)
            has_env_creds = bool(
                os.getenv("LITTER_ROBOT_USER") and os.getenv("LITTER_ROBOT_PASSWORD")
            )
            if has_keyring_creds:
                app._log_info("Credentials: present in keyring")
            elif has_env_creds:
                app._log_info("Credentials: present in .env (will be copied to keyring on /mcp on)")
            else:
                app._log_info("Credentials: missing - use /login first")
            for path, enabled in mcp_status():
                state = "enabled " if enabled else "disabled"
                found = "found" if path.exists() else "not found"
                app._log_info(f"  [{state}, {found}]  {path}")
            return

        if sub == "on":
            from ..connection import _keyring_load, _keyring_save  # noqa: PLC0415

            email, password = _keyring_load()
            if not email or not password:
                env_email = os.getenv("LITTER_ROBOT_USER") or ""
                env_password = os.getenv("LITTER_ROBOT_PASSWORD") or ""
                if env_email and env_password and _keyring_save(env_email, env_password):
                    app._log_info("Copied .env credentials into the OS keyring for MCP use.")
                    email, password = env_email, env_password

            if not email or not password:
                app._log_err(
                    "No credentials in keyring or .env - use /login first, "
                    "or set LITTER_ROBOT_USER/LITTER_ROBOT_PASSWORD."
                )
                return
            if not await _ensure_mcp_extra(app):
                return
            touched = set_mcp_enabled(True)
        else:
            touched = set_mcp_enabled(False)

        verb = "enabled" if sub == "on" else "disabled"
        if touched:
            for path in touched:
                app._log_ok(f"MCP server '{verb}' in {path}")
            app._log_info("Restart Claude Desktop to apply this change.")
        else:
            app._log_info(f"MCP server was already {verb}")


def _open_folder(path: Path) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


async def _run_export(app: AsherApp, days: int) -> None:
    assert app._robot is not None
    app._log_info(f"Fetching history (last {days} days)…")
    try:
        acts = await app._robot.get_activity_history(limit=500)
    except Exception as exc:
        app._log_err(f"Failed to fetch history: {exc}")
        return

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    filtered = []
    for act in acts:
        ts_dt = getattr(act, "timestamp", None)
        if ts_dt is None:
            continue
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        if ts_dt >= cutoff:
            filtered.append((act, ts_dt))
    filtered.sort(key=lambda x: x[1])

    serial = getattr(app._robot, "serial", "unknown")
    robot_name = getattr(app._robot, "name", "—")
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"asher-{serial}-{date_str}.csv"

    downloads = Path.home() / "Downloads"
    if downloads.exists():
        dest = downloads / filename
    else:
        fallback = Path.home() / "Documents" / "asher-cli"
        fallback.mkdir(parents=True, exist_ok=True)
        dest = fallback / filename

    app._log_info(f"Writing {filename}… {len(filtered)} events")
    try:
        with dest.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "event",
                    "raw_event",
                    "weight_lb",
                    "pet_name",
                    "robot_name",
                    "robot_serial",
                ]
            )
            from tzlocal import get_localzone  # noqa: PLC0415

            local_tz = get_localzone()
            for act, ts_dt in filtered:
                local_dt = ts_dt.astimezone(local_tz)
                iso_ts = local_dt.isoformat()
                raw_str = activity_raw_text(act)
                label, _ = ACTION_LABELS.get(raw_str.lower(), (raw_str, ""))
                weight = getattr(act, "weight", None)
                weight_str = f"{float(weight):.1f}" if weight is not None else ""
                pet_id = getattr(act, "pet_id", None)
                pet_name = next(
                    (getattr(p, "name", "") for p in app._pets if getattr(p, "id", None) == pet_id),
                    "",
                )
                writer.writerow([iso_ts, label, raw_str, weight_str, pet_name, robot_name, serial])
    except Exception as exc:
        app._log_err(f"Failed to write CSV: {exc}")
        app._log_info(f"Try: {Path.home() / filename}")
        return

    app._log_ok(f"Saved → {dest}")
    app._log_info("Opening folder…")
    _open_folder(dest)


class ExportCommand(Command):
    name = "export"
    description = "[days|month]  export activity history to CSV (default: 30 days)"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        raw = args[0].lower() if args else "month"
        if raw in ("month", "30"):
            days = 30
        else:
            try:
                days = max(1, min(30, int(raw)))
            except ValueError:
                app._log_warn(f"Unknown period '{raw}' — use a number of days or 'month'")
                return
        await _run_export(app, days)


# ── registry ────────────────────────────────────────────────────────────────

_registry = CommandRegistry()
_registry.register(CleanCommand())
_registry.register(StatusCommand())
_registry.register(InfoCommand())
_registry.register(LockCommand())
_registry.register(UnlockCommand())
_registry.register(SleepCommand())
_registry.register(WakeCommand())
_registry.register(NightLightCommand())
_registry.register(NightLightBrightnessCommand())
_registry.register(HistoryCommand())
_registry.register(WaitTimeCommand())
_registry.register(PowerCommand())
_registry.register(RenameCommand())
_registry.register(InsightCommand())
_registry.register(PrivacyCommand())
_registry.register(VolumeCommand())
_registry.register(CameraAudioCommand())
_registry.register(DrawerResetCommand())
_registry.register(ExportCommand())
_registry.register(HelpCommand())
_registry.register(ClearCommand())
_registry.register(QuitCommand())
_registry.register(LoginCommand())
_registry.register(LogoutCommand())
_registry.register(RobotsCommand())
_registry.register(RobotCommand())
_registry.register(PetsCommand())
_registry.register(PetCommand())
_registry.register(CatCommand())
_registry.register(RefreshCommand())
_registry.register(ConfigCommand())
_registry.register(McpCommand())


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
