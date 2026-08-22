"""Command dispatch and individual command handlers."""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import subprocess
import sys
from datetime import time
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from ..app import AsherApp
    from ..robot_protocol import RobotProtocol

from pylitterbot.enums import LitterBoxStatus
from pylitterbot.robot import EVENT_UPDATE
from rich.text import Text
from textual import work
from textual.css.query import NoMatches
from textual.widgets import Input, RichLog, Static

from .. import theme
from ..completion import enter_completes, render_completion, slash_matches
from ..export import ExportError, build_history_csv, resolve_dest
from ..helpers import fmt_ago, robot_model, status_text, ts
from ..history_view import HistoryScreen
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


def _persist(app: AsherApp, **changes: object) -> None:
    """Persist a runtime setting to ``~/.asher-cli/config.json``.

    A read-only filesystem (container, restricted environment) must not break
    the in-session command, so filesystem errors degrade to a warning log
    rather than raising.
    """
    from ..config import update  # noqa: PLC0415

    try:
        update(**changes)
    except OSError:
        app._log_warn("Could not save setting (filesystem read-only?)")


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
    description = "set night light mode"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "night-light on|off|auto"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._adapter is None:
            return
        arg = args[0].lower() if args else ""
        if arg not in ("on", "off", "auto"):
            app._log_warn("Usage: night-light on|off|auto")
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
    description = "[count|all]  show recent activity in a scrollable pager"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if app._robot is None:
            return
        raw = args[0].lower() if args else ""
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
        try:
            acts = await app._robot.get_activity_history(limit=limit)
        except Exception as exc:
            app._log_err(f"Failed to get history: {exc}")
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


_DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


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


class SleepScheduleCommand(Command):
    name = "sleep-schedule"
    aliases = ("sleepschedule",)
    description = "show the per-day sleep schedule (read-only)"
    requires_robot = True

    @property
    def display_name(self) -> str:
        return "sleep-schedule"

    async def run(self, app: AsherApp, args: list[str]) -> None:
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

            name = _DAY_NAMES[idx]
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
        if app._adapter is None:
            return
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
        if app._adapter is None:
            return
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
        if app._adapter is None:
            return
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
        if app._adapter is None:
            return
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
            t.append("  ● " if active else "    ", style=theme.OK if active else theme.MUTED)
            t.append(f"[{idx}] ", style=theme.MUTED)
            t.append(
                getattr(robot, "name", "-"),
                style=theme.FOREGROUND_BRIGHT if active else theme.FOREGROUND,
            )
            t.append(f"  {robot_model(robot)}", style=theme.MUTED)
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
            t.append("  ● " if active else "    ", style=theme.OK if active else theme.MUTED)
            t.append(f"[{idx}] ", style=theme.MUTED)
            t.append(
                getattr(pet, "name", "-"),
                style=theme.FOREGROUND_BRIGHT if active else theme.FOREGROUND,
            )
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
                _persist(app, active_pet_index=idx)
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
            _persist(app, active_pet_index=match)
            name = getattr(pets[match], "name", str(match))
            app._log_ok(f"Showing pet: {name}")
            await app._refresh_status()


class CatCommand(SlashCommand):
    name = "cat"
    description = "on|off|colour <hex>  configure the cat panel"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if not args:
            app._log_info("Usage: /cat on|off|colour <hex>")
            return

        sub = args[0].lower()
        if sub == "off":
            app.query_one("#cat-panel").display = False
            app._cat_panel_visible = False
            _persist(app, cat_panel_visible=False)
            app._log_ok("Cat panel hidden")
        elif sub == "on":
            app.query_one("#cat-panel").display = True
            app._cat_panel_visible = True
            _persist(app, cat_panel_visible=True)
            app._log_ok("Cat panel visible")
        elif sub in ("colour", "color"):
            if len(args) < 2:
                app._log_warn(f"Usage: /cat colour <hex>  e.g. /cat colour {theme.PINK}")
                return
            color = args[1]
            if not color.startswith("#"):
                color = f"#{color}"
            app._cat_color = color
            _persist(app, cat_panel_color=color)
            app._set_cat(app._cat_mode, getattr(app, "_cat_label", ""))
            app._log_ok(f"Cat colour set to {color}")
        elif sub == "reset":
            app._cat_color = None
            _persist(app, cat_panel_color=None)
            app._set_cat(app._cat_mode, getattr(app, "_cat_label", ""))
            app._log_ok("Cat colour reset to default")
        else:
            app._log_warn("Usage: /cat on|off|colour <hex>")


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
            _persist(app, poll_interval_seconds=0)
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
        _persist(app, poll_interval_seconds=seconds)
        app._log_ok(f"Auto-refresh set to every {seconds}s")


def _watcher_summary() -> str:
    from ..daemon import running_pid  # noqa: PLC0415

    pid = running_pid()
    return f"running (pid {pid})" if pid is not None else "not running"


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
        cat_color = getattr(app, "_cat_color", None) or f"{theme.ACCENT} (default)"

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
            (
                "notifications",
                "on" if getattr(app, "_notifications_enabled", True) else "off",
            ),
            (
                "notif. sound",
                "on" if getattr(app, "_notification_sound", False) else "off",
            ),
            ("watcher", _watcher_summary()),
        ]
        log.write("")
        for k, v in rows:
            t = Text()
            t.append(f"  {k:<14}", style=theme.MUTED)
            t.append(v, style=theme.FOREGROUND)
            log.write(t)
        log.write("")


class NotifyCommand(SlashCommand):
    name = "notify"
    description = "on|off|sound on|off|test  desktop toast settings"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        if not args:
            toasts = "on" if getattr(app, "_notifications_enabled", True) else "off"
            sound = "on" if getattr(app, "_notification_sound", False) else "off"
            app._log_info(
                f"Usage: /notify on|off|sound on|off|test  (toasts {toasts}, sound {sound})"
            )
            return

        sub = args[0].lower()
        if sub == "on":
            app._notifications_enabled = True
            _persist(app, notifications=True)
            app._log_ok("Desktop notifications enabled")
        elif sub == "off":
            app._notifications_enabled = False
            _persist(app, notifications=False)
            app._log_ok("Desktop notifications disabled")
        elif sub == "sound":
            if len(args) < 2 or args[1].lower() not in ("on", "off"):
                app._log_warn("Usage: /notify sound on|off")
                return
            enabled = args[1].lower() == "on"
            app._notification_sound = enabled
            _persist(app, notification_sound=enabled)
            app._log_ok(f"Notification sound {'enabled' if enabled else 'disabled'}")
        elif sub == "test":
            if not getattr(app, "_notifications_enabled", True):
                app._log_warn("Notifications are off — /notify on first")
                return
            from ..notifications import fire  # noqa: PLC0415

            name = getattr(getattr(app, "_robot", None), "name", "robot") or "robot"
            fire(f"Asher — {name}", "This is a test notification.")
            app._log_ok("Test notification fired")
        else:
            app._log_warn("Usage: /notify on|off|sound on|off|test")


class WatchCommand(SlashCommand):
    name = "watch"
    description = (
        "start|stop|status|enable|disable  background notifier that outlives this terminal"
    )

    async def run(self, app: AsherApp, args: list[str]) -> None:
        from ..autostart import disable as disable_autostart  # noqa: PLC0415
        from ..daemon import ACTIONS, enable_autostart, start, status, stop  # noqa: PLC0415

        action = args[0].lower() if args else "status"
        if action not in ACTIONS or action == "run":
            app._log_warn("Usage: /watch start|stop|status|enable|disable")
            return

        handlers = {
            "start": start,
            "stop": stop,
            "status": status,
            "enable": enable_autostart,
            "disable": disable_autostart,
        }
        # Each of these blocks on process signals and short sleeps, which would
        # otherwise stall the UI for the length of the daemon's shutdown grace.
        ok, message = await asyncio.to_thread(handlers[action])
        for line in message.splitlines():
            (app._log_ok if ok else app._log_warn)(line)
        if ok and action == "start":
            app._log_info("Dashboard toasts are suppressed while the watcher runs.")


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
            from ..connection import _env_credentials, _keyring_load  # noqa: PLC0415

            email, password = _keyring_load()
            has_keyring_creds = bool(email and password)
            has_env_creds = all(_env_credentials())
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
            from ..connection import (  # noqa: PLC0415
                _env_credentials,
                _keyring_load,
                _keyring_save,
            )

            email, password = _keyring_load()
            if not email or not password:
                env_email, env_password = _env_credentials()
                if env_email and env_password and _keyring_save(env_email, env_password):
                    app._log_info("Copied .env credentials into the OS keyring for MCP use.")
                    email, password = env_email, env_password

            if not email or not password:
                app._log_err("No credentials in the keyring - use /login first.")
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


class VersionCommand(SlashCommand):
    name = "version"
    description = "show version info (asher-cli, Python, pylitterbot, textual)"

    async def run(self, app: AsherApp, args: list[str]) -> None:  # noqa: ARG002
        def _v(pkg: str) -> str:
            try:
                return pkg_version(pkg)
            except PackageNotFoundError:
                return "?"

        app._log_info(f"Asher CLI v{_v('asher-cli')}")
        app._log_info(f"Python {sys.version.split()[0]}")
        app._log_info(f"pylitterbot {_v('pylitterbot')}")
        app._log_info(f"textual {_v('textual')}")

        from ..updates import check, releases_url  # noqa: PLC0415

        update = await asyncio.to_thread(check, force=True)
        if update is None:
            app._log_ok("You're on the latest release.")
        else:
            app._log_warn(update.notice)
            app._log_info(f"Changelog: {releases_url()}")


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
_registry.register(PanelBrightnessCommand())
_registry.register(HistoryCommand())
_registry.register(WaitTimeCommand())
_registry.register(PowerCommand())
_registry.register(RenameCommand())
_registry.register(InsightCommand())
_registry.register(SleepScheduleCommand())
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
_registry.register(NotifyCommand())
_registry.register(WatchCommand())
_registry.register(McpCommand())
_registry.register(VersionCommand())


# ── mixin ───────────────────────────────────────────────────────────────────


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
