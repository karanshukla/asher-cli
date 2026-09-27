"""Robot commands — actions and reads against the active Litter-Robot."""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..app import AsherApp

from pylitterbot.enums import LitterBoxStatus
from pylitterbot.robot import EVENT_UPDATE
from rich.text import Text
from textual.widgets import RichLog, Static

from ...core import theme
from ...core.constants import ACTIVITY_TYPES
from ...core.export import ExportError, build_history_csv, resolve_dest
from ...core.helpers import (
    DAY_NAMES,
    activity_type,
    fmt_ago,
    fmt_until,
    hex_colour,
    parse_clock,
    parse_day,
    robot_model,
    split_type_flag,
    status_text,
)
from ..history import HistoryScreen
from .base import Command


def _fmt_wait_time(minutes: object) -> str:
    """Render a clean-cycle wait time, tolerating a missing/None value."""
    if minutes is None:
        return "—"
    try:
        return f"{int(float(str(minutes)))} min"
    except (TypeError, ValueError):
        return "—"


_POWER_LABELS = {"AC": "AC (mains)", "DC": "Battery", "NC": "Off/unknown"}


def _fmt_power(power_type: object) -> str:
    """Render a power source string ('AC'/'DC'/'NC') readably."""
    return _POWER_LABELS.get(str(power_type) if power_type else "", "—")


def _fmt_wifi(status: object) -> str:
    """Render an LR4 WifiModeStatus enum readably; '—' when absent/unknown."""
    name: str | None = getattr(status, "name", None)
    if not name or name == "NONE":
        return "—"
    suffix = name.split("_", 1)[-1].lower()
    if name == "OFF":
        return "off"
    if suffix == "connected":
        return "connected"
    if suffix == "waiting":
        return "connecting"
    if suffix == "fault":
        return "fault"
    return suffix


_CYCLING_STATUSES = frozenset(
    {
        LitterBoxStatus.CLEAN_CYCLE,
        LitterBoxStatus.EMPTY_CYCLE,
        LitterBoxStatus.PAUSED,
        LitterBoxStatus.POWER_UP,
        LitterBoxStatus.POWER_DOWN,
    }
)


# ── robot commands ──────────────────────────────────────────────────────────


class CleanCommand(Command):
    name = "clean"
    description = "start a clean cycle"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._robot is None:
            return
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
        if app._robot is None:
            return
        try:
            await app._robot.refresh()
            await app._refresh_status()
        except Exception as exc:
            app._log_err(f"Status refresh failed: {exc}")
            return
        r = app._robot
        weight = "—"
        with contextlib.suppress(Exception):
            w = getattr(r, "pet_weight", None)
            if w is not None and float(w) > 0:
                weight = f"{float(w):.1f} lb"
        last_seen = getattr(app, "_last_cat_seen", None) or getattr(r, "last_seen", None)
        rows = [
            ("Online", "yes" if getattr(r, "is_online", False) else "no"),
            ("Status", status_text(getattr(r, "status", None))),
            ("Drawer", f"{float(getattr(r, 'waste_drawer_level', 0) or 0):.0f}%"),
            ("Last seen", fmt_ago(last_seen)),
            ("Cat weight", weight),
        ]
        log = app.query_one("#log", RichLog)
        for k, v in rows:
            t = Text()
            t.append(f"  {k:<14}", style=theme.MUTED)
            t.append(str(v), style=theme.FOREGROUND)
            log.write(t)


class InfoCommand(Command):
    name = "info"
    description = "show full robot details (model, serial, firmware, …)"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._robot is None:
            return
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
        litter = getattr(r, "litter_level", None)
        litter_str = f"{float(litter):.0f}%" if litter is not None else "—"
        brightness = getattr(r, "panel_brightness", None)
        brightness_str = str(brightness).split(".")[-1].lower() if brightness else "—"
        cycles = getattr(r, "cycle_count", None)
        cycles_str = str(cycles) if cycles is not None else "—"
        rows = [
            ("Name", getattr(r, "name", "—")),
            ("Model", robot_model(r)),
            ("Serial", getattr(r, "serial", "—")),
            ("Firmware", getattr(r, "firmware", "—") or "—"),
            ("Power", _fmt_power(getattr(r, "power_type", None))),
            ("Wait time", _fmt_wait_time(getattr(r, "clean_cycle_wait_time_minutes", None))),
            ("Sleeping", _yn(getattr(r, "sleep_mode_enabled", False))),
            ("Panel locked", _yn(getattr(r, "panel_lock_enabled", False))),
            ("Panel bright", brightness_str),
            ("Night light", night_str),
            ("Drawer", f"{float(getattr(r, 'waste_drawer_level', 0) or 0):.0f}%"),
            ("Litter", litter_str),
            ("Cycles", cycles_str),
            ("Wi-Fi", _fmt_wifi(getattr(r, "wifi_mode_status", None))),
            ("Online", _yn(getattr(r, "is_online", False))),
            ("Last seen", fmt_ago(last_seen)),
        ]
        filter_due = getattr(r, "next_filter_replacement_date", None)
        if isinstance(filter_due, datetime):
            rows.insert(-2, ("Filter due", fmt_until(filter_due)))
        log = app.query_one("#log", RichLog)
        for k, v in rows:
            t = Text()
            t.append(f"  {k:<14}", style=theme.MUTED)
            t.append(str(v), style=theme.FOREGROUND)
            log.write(t)


class LockCommand(Command):
    name = "lock"
    description = "lock the panel"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "lock / unlock"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._adapter is None:
            return
        ok, msg = await app._adapter.set_panel_lockout(True)
        if ok:
            app.query_one("#lock-lbl", Static).update(Text("⊘ Locked", style=f"bold {theme.WARN}"))
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
        if app._adapter is None:
            return
        ok, msg = await app._adapter.set_panel_lockout(False)
        if ok:
            app.query_one("#lock-lbl", Static).update(Text("□ Unlocked", style=theme.MUTED))
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
        if app._adapter is None:
            return
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
        if app._adapter is None:
            return
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
    description = "on|off|auto|color <hex>  set night light mode"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "night-light"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._adapter is None:
            return
        arg = args[0].lower() if args else ""
        if arg in ("color", "colour"):
            await self._set_colour(app, args[1:])
            return
        if arg not in ("on", "off", "auto"):
            app._log_warn("Usage: night-light on|off|auto|color <hex>")
            return
        ok, msg = await app._adapter.set_night_light(arg)
        if ok:
            app._log_ok(msg)
            if arg == "off":
                nl = Text("○", style=theme.MUTED)
            elif arg == "auto":
                nl = Text("◐", style=theme.ACCENT)
            else:
                nl = Text("☀", style=theme.WARN)
            app.query_one("#nightlight-lbl", Static).update(nl)
        else:
            app._log_warn(msg)

    async def _set_colour(self, app: AsherApp, args: list[str]) -> None:
        if app._adapter is None:
            return
        colour = hex_colour(args[0]) if args else None
        if colour is None:
            app._log_warn("Usage: night-light color <hex>  e.g. night-light color #FF9E64")
            return
        ok, msg = await app._adapter.set_night_light_color(colour)
        if ok:
            app._log_ok(msg)
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
        if app._adapter is None:
            return
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
                nl_emoji, nl_color = "○", theme.MUTED
            elif mode_str == "auto":
                nl_emoji, nl_color = "◐", theme.ACCENT
            else:
                nl_emoji, nl_color = "☀", theme.WARN
            nl = Text()
            nl.append(nl_emoji, style=nl_color)
            if mode_str != "off":
                nl.append(f"  {level}%", style=theme.MUTED)
            app.query_one("#nightlight-lbl", Static).update(nl)
        else:
            app._log_warn(msg)


class PanelBrightnessCommand(Command):
    name = "panel-brightness"
    aliases = ("pb",)
    description = "<low|medium|high>  set control-panel brightness (LR4/LR5)"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._adapter is None:
            return
        if not args:
            current = getattr(app._robot, "panel_brightness", None)
            app._log_info(f"Usage: panel-brightness <low|medium|high>  (current: {current or '—'})")
            return
        ok, msg = await app._adapter.set_panel_brightness(args[0].lower())
        if ok:
            app._log_ok(msg)
        else:
            app._log_warn(msg)


class HistoryCommand(Command):
    name = "history"
    aliases = ("hist",)
    description = "[count|all] [--type <kind>]  recent activity in a scrollable pager"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._robot is None or app._adapter is None:
            return
        counts, wanted_type = split_type_flag(args)
        raw = counts[0].lower() if counts else ""
        if raw in ("all", "max"):
            limit = 500
        elif raw:
            try:
                limit = max(1, min(500, int(raw)))
            except ValueError:
                app._log_warn(f"Unknown count '{raw}' — use a number of events or 'all'")
                return
        else:
            limit = 50

        wanted = activity_type(wanted_type)
        if wanted_type is not None and wanted is None:
            app._log_warn(f"Usage: history [count|all] --type <{'|'.join(ACTIVITY_TYPES)}>")
            return

        acts, problem = await app._adapter.get_history(limit, wanted)
        if acts is None:
            app._log_err(problem)
            return
        robot_name = getattr(app._robot, "name", "robot")
        app.push_screen(HistoryScreen(acts, app._pets, robot_name))


class WaitTimeCommand(Command):
    name = "wait-time"
    aliases = ("waittime", "wait")
    description = "<minutes>  set clean-cycle wait time"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "wait-time <minutes>"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._robot is None:
            return
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
        if app._robot is None:
            return
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
        if app._robot is None:
            return
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
        if app._robot is None:
            return
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
            t.append(f"  {k:<14}", style=theme.MUTED)
            t.append(str(v), style=theme.FOREGROUND)
            log.write(t)


def _fmt_sleep_time(t: object) -> str:
    if t is None:
        return "—"
    if isinstance(t, time):
        return t.strftime("%H:%M")
    return str(t)


def _dow_to_weekday(day: int) -> int:
    """Convert a pylitterbot DayOfWeek (Sun=0..Sat=6) to Python weekday (Mon=0..Sun=6)."""
    return (day - 1) % 7


def _parse_sleep_day(day: Any) -> tuple[int, bool, object, object] | None:
    """Read one schedule day, or None when the API returns a shape we can't read."""
    try:
        return (
            _dow_to_weekday(int(getattr(day, "day", 0))),
            bool(getattr(day, "is_enabled", False)),
            getattr(day, "sleep_time", None),
            getattr(day, "wake_time", None),
        )
    except Exception:
        return None


_EVERY_DAY = ("all", "every", "daily", "everyday")
_SCHEDULE_USAGE = (
    "Usage: sleep-schedule · sleep-schedule set <day|all> <HH:MM> <HH:MM> · sleep-schedule disable"
)


class SleepScheduleCommand(Command):
    name = "sleep-schedule"
    aliases = ("sleepschedule",)
    description = "[set <day|all> <HH:MM> <HH:MM>|disable]  per-day sleep windows"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "sleep-schedule"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        action = args[0].lower() if args else ""
        if action == "set":
            await self._set_window(app, args[1:])
            return
        if action in ("disable", "off"):
            await self._disable(app)
            return
        if action:
            app._log_warn(_SCHEDULE_USAGE)
            return
        await self._show(app)

    async def _set_window(self, app: AsherApp, args: list[str]) -> None:
        if app._adapter is None:
            return
        if len(args) < 3:
            app._log_warn("Usage: sleep-schedule set <day|all> <HH:MM> <HH:MM>")
            return
        day_arg = args[0].lower()
        weekday = None if day_arg in _EVERY_DAY else parse_day(day_arg)
        if weekday is None and day_arg not in _EVERY_DAY:
            app._log_warn(f"Unknown day '{args[0]}' — use {'/'.join(DAY_NAMES)} or 'all'")
            return
        sleep, wake = parse_clock(args[1]), parse_clock(args[2])
        if sleep is None or wake is None:
            app._log_warn("Times must be 24-hour HH:MM — e.g. sleep-schedule set all 22:00 07:00")
            return

        ok, msg = await app._adapter.set_sleep_window(weekday, sleep, wake)
        if not ok:
            app._log_warn(msg)
            return
        app._log_ok(msg)
        await app._refresh_status()

    async def _disable(self, app: AsherApp) -> None:
        if app._adapter is None:
            return
        ok, msg = await app._adapter.disable_sleep_schedule()
        if not ok:
            app._log_warn(msg)
            return
        app._log_ok(msg)
        await app._refresh_status()

    async def _show(self, app: AsherApp) -> None:
        if app._robot is None:
            return
        try:
            schedule = getattr(app._robot, "sleep_schedule", None)
        except Exception as exc:
            app._log_err(f"Failed to read sleep schedule: {exc}")
            return

        if schedule is None:
            app._log_warn(
                "No sleep schedule set — the unit is always awake "
                "(or toggle sleep/wake for an immediate nap)."
            )
            return

        try:
            days = sorted(
                getattr(schedule, "days", []),
                key=lambda d: _dow_to_weekday(int(getattr(d, "day", 0))),
            )
            is_enabled = bool(getattr(schedule, "is_enabled", False))
            # Window covers [sleep_start, wake_end] as datetimes; None if disabled/expired.
            window = None
            with contextlib.suppress(Exception):
                window = schedule.get_window()
        except Exception as exc:
            app._log_err(f"Failed to parse sleep schedule: {exc}")
            return

        if not is_enabled:
            app._log_info("Sleep schedule is disabled. Configured windows:")

        log = app.query_one("#log", RichLog)
        active_day_indices = set()
        if window is not None:
            with contextlib.suppress(Exception):
                start_dt, end_dt = window
                # Sleep windows can wrap past midnight, so flag both the start
                # and end day as "active now" for the user-facing marker.
                active_day_indices.add(start_dt.weekday())
                active_day_indices.add(end_dt.weekday())

        for day in days:
            parsed = _parse_sleep_day(day)
            if parsed is None:
                continue
            idx, day_enabled, sleep_t, wake_t = parsed

            name = DAY_NAMES[idx]
            t = Text()
            t.append(f"  {name} ", style=theme.MUTED)
            if day_enabled:
                window_str = f"{_fmt_sleep_time(sleep_t)} → {_fmt_sleep_time(wake_t)}"
                t.append(window_str, style=theme.FOREGROUND)
                if idx in active_day_indices:
                    t.append("   ● now", style=f"bold {theme.WARN}")
            else:
                t.append("off", style=theme.MUTED)
            log.write(t)

        if is_enabled and not active_day_indices:
            app._log_info("Outside the active sleep window right now.")


def _open_folder(path: Path) -> None:
    if sys.platform == "win32":
        argv = ["explorer", "/select,", str(path)]
    elif sys.platform == "darwin":
        argv = ["open", "-R", str(path)]
    else:
        argv = ["xdg-open", str(path.parent)]

    argv[0] = shutil.which(argv[0]) or argv[0]
    subprocess.Popen(argv)  # nosec B603 # fixed argv, no shell, path is not user-controlled


async def _run_export(app: AsherApp, days: int) -> None:
    if app._robot is None:
        return
    dest = resolve_dest(app._robot, None)
    app._log_info(f"Fetching history (last {days} days)…")
    try:
        count = await build_history_csv(app._robot, app._pets, days, dest)
    except ExportError as exc:
        app._log_err(str(exc))
        return

    app._log_ok(f"Saved → {dest}")
    app._log_info(f"{count} events")
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
