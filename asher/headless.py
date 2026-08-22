"""Headless command surface — the whole robot API without a TUI.

``asher --export`` proved the pattern: authenticate from the keyring, do one
thing, print, exit. This module generalises it into a scriptable wrapper over
pylitterbot, so every robot action the dashboard offers is also reachable from
cron, a shell pipeline, or an SSH session::

    asher status
    asher night-light auto --robot "Asher 2"
    asher history 20 --json | jq '.events[0]'

Design constraints that shape the code here:

* **No Textual.** Commands render plain strings and never touch a widget, so the
  module imports cleanly (and fast) in a scheduled task.
* **Model differences go through** :class:`~asher.robot_adapters.RobotAdapter`,
  exactly as the TUI commands do — LR3/LR4/LR5 quirks stay in one place.
* **Every command returns a** :class:`Result`, which carries both the
  human-readable lines and a JSON payload. ``--json`` picks the other rendering
  of the same data rather than taking a separate code path.
* **Exit codes are the contract** (see :mod:`asher.export`): a script checks
  ``$?`` rather than parsing text.
"""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import TYPE_CHECKING, Any

from .activity_labels import activity_raw_text, format_activity
from .export import (
    EXIT_COMMAND_REJECTED,
    EXIT_CONNECTION_FAILURE,
    EXIT_NO_ROBOT_MATCH,
    EXIT_OK,
    ExportError,
    build_history_csv,
    parse_days,
    resolve_dest,
    resolve_robot,
)
from .helpers import fmt_ago, robot_model, status_text

if TYPE_CHECKING:
    from .robot_adapters import RobotAdapter
    from .robot_protocol import RobotProtocol

_MAX_HISTORY = 500
_DEFAULT_HISTORY = 50
_LABEL_WIDTH = 16


class CommandError(Exception):
    """A headless command could not run as asked (bad argument, cloud refusal)."""

    def __init__(self, message: str, code: int = EXIT_COMMAND_REJECTED) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Result:
    """One command's output in both renderings.

    ``lines`` is what a human sees; ``data`` is the same information as a JSON
    object. Keeping them together means a command describes its result once and
    the caller decides how to print it.
    """

    data: dict[str, Any] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)
    code: int = EXIT_OK


@dataclass
class Session:
    """Everything a headless command needs: the account, the chosen robot, options."""

    account: Any
    robots: list[RobotProtocol]
    pets: list[Any]
    robot: RobotProtocol
    adapter: RobotAdapter
    output: str | None = None


def _rows(pairs: list[tuple[str, Any]]) -> Result:
    """Render ``(label, value)`` pairs as an aligned block plus a JSON object.

    JSON keys are the labels lowercased and underscored, so ``"Cat weight"``
    becomes ``cat_weight`` — stable enough to script against.
    """
    return Result(
        data={k.lower().replace(" ", "_").replace("-", "_"): v for k, v in pairs},
        lines=[f"  {k:<{_LABEL_WIDTH}}{v}" for k, v in pairs],
    )


def _outcome(ok: bool, message: str) -> Result:
    """Turn an adapter's ``(success, message)`` pair into a Result.

    A rejection is a non-zero exit, not an exception — the message is already
    user-facing, and the caller prints it to stderr.
    """
    if not ok:
        raise CommandError(message)
    return Result(data={"ok": True, "message": message}, lines=[message])


def _on_off(args: list[str], usage: str) -> bool:
    value = args[0].lower() if args else ""
    if value not in ("on", "off"):
        raise CommandError(f"Usage: {usage}")
    return value == "on"


def _int_arg(args: list[str], usage: str) -> int:
    if not args:
        raise CommandError(f"Usage: {usage}")
    try:
        return int(args[0])
    except ValueError:
        raise CommandError(f"Usage: {usage}") from None


# ── robot state ──────────────────────────────────────────────────────────────


_POWER_LABELS = {"AC": "AC (mains)", "DC": "Battery", "NC": "Off/unknown"}


def _percent(value: object) -> str:
    try:
        return f"{float(value):.0f}%"  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "—"


def _weight(robot: RobotProtocol) -> str:
    try:
        value = getattr(robot, "pet_weight", None)
        return f"{float(value):.1f} lb" if value and float(value) > 0 else "—"  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "—"


async def _status(session: Session, args: list[str]) -> Result:
    robot = session.robot
    await _refresh(robot)
    return _rows(
        [
            ("Name", getattr(robot, "name", "—")),
            ("Online", "yes" if getattr(robot, "is_online", False) else "no"),
            ("Status", status_text(getattr(robot, "status", None))),
            ("Drawer", _percent(getattr(robot, "waste_drawer_level", None))),
            ("Litter", _percent(getattr(robot, "litter_level", None))),
            ("Cat weight", _weight(robot)),
            ("Last seen", fmt_ago(getattr(robot, "last_seen", None))),
        ]
    )


async def _info(session: Session, args: list[str]) -> Result:
    robot = session.robot
    await _refresh(robot)

    def yes_no(flag: object) -> str:
        return "yes" if flag else "no"

    night_light_mode = getattr(robot, "night_light_mode", None)
    night_light = (
        night_light_mode.value.lower()
        if night_light_mode is not None
        else ("on" if getattr(robot, "night_light_mode_enabled", False) else "off")
    )
    brightness = getattr(robot, "panel_brightness", None)
    cycles = getattr(robot, "cycle_count", None)
    wait = getattr(robot, "clean_cycle_wait_time_minutes", None)
    return _rows(
        [
            ("Name", getattr(robot, "name", "—")),
            ("Model", robot_model(robot)),
            ("Serial", getattr(robot, "serial", "—")),
            ("Firmware", getattr(robot, "firmware", "—") or "—"),
            ("Power", _POWER_LABELS.get(str(getattr(robot, "power_type", "")), "—")),
            ("Wait time", f"{int(wait)} min" if wait is not None else "—"),
            ("Sleeping", yes_no(getattr(robot, "sleep_mode_enabled", False))),
            ("Panel locked", yes_no(getattr(robot, "panel_lock_enabled", False))),
            ("Panel bright", str(brightness).split(".")[-1].lower() if brightness else "—"),
            ("Night light", night_light),
            ("Drawer", _percent(getattr(robot, "waste_drawer_level", None))),
            ("Litter", _percent(getattr(robot, "litter_level", None))),
            ("Cycles", str(cycles) if cycles is not None else "—"),
            ("Online", yes_no(getattr(robot, "is_online", False))),
            ("Last seen", fmt_ago(getattr(robot, "last_seen", None))),
        ]
    )


async def _refresh(robot: RobotProtocol) -> None:
    try:
        await robot.refresh()
    except Exception as exc:
        raise CommandError(f"Refresh failed: {exc}", EXIT_CONNECTION_FAILURE) from exc


# ── account listings ─────────────────────────────────────────────────────────


async def _robots(session: Session, args: list[str]) -> Result:
    entries = [
        {
            "index": index,
            "name": getattr(robot, "name", "—"),
            "model": robot_model(robot),
            "serial": getattr(robot, "serial", "—"),
            "active": robot is session.robot,
        }
        for index, robot in enumerate(session.robots)
    ]
    lines = [
        f"  {'●' if entry['active'] else ' '} [{entry['index']}] "
        f"{entry['name']}  {entry['model']}  {entry['serial']}"
        for entry in entries
    ]
    return Result(data={"robots": entries}, lines=lines)


async def _pets(session: Session, args: list[str]) -> Result:
    if not session.pets:
        return Result(data={"pets": []}, lines=["No pets registered on this account."])
    entries = [
        {
            "index": index,
            "name": getattr(pet, "name", "—"),
            "weight_lb": getattr(pet, "weight", None),
        }
        for index, pet in enumerate(session.pets)
    ]
    lines = [
        f"  [{entry['index']}] {entry['name']}"
        + (f"  {float(entry['weight_lb']):.1f} lb" if entry["weight_lb"] else "")
        for entry in entries
    ]
    return Result(data={"pets": entries}, lines=lines)


# ── activity ─────────────────────────────────────────────────────────────────


def _parse_count(args: list[str]) -> int:
    raw = args[0].lower() if args else ""
    if raw in ("all", "max"):
        return _MAX_HISTORY
    if not raw:
        return _DEFAULT_HISTORY
    try:
        return max(1, min(_MAX_HISTORY, int(raw)))
    except ValueError:
        raise CommandError(f"Unknown count '{raw}' — use a number of events or 'all'") from None


async def _history(session: Session, args: list[str]) -> Result:
    count = _parse_count(args)
    try:
        acts = await session.robot.get_activity_history(limit=count)
    except Exception as exc:
        raise CommandError(f"Failed to fetch history: {exc}", EXIT_CONNECTION_FAILURE) from exc

    events: list[dict[str, Any]] = []
    lines: list[str] = []
    for act in acts:
        timestamp = getattr(act, "timestamp", None)
        label, _ = format_activity(act, session.pets)
        stamp = timestamp.isoformat() if isinstance(timestamp, datetime) else None
        events.append(
            {
                "timestamp": stamp,
                "event": label,
                "raw_event": activity_raw_text(act),
                "weight_lb": getattr(act, "weight", None),
            }
        )
        when = timestamp.strftime("%m/%d %H:%M") if isinstance(timestamp, datetime) else "?"
        lines.append(f"  {when:<12}{label}")
    if not events:
        lines = ["No activity history available for this robot."]
    return Result(data={"events": events}, lines=lines)


async def _insight(session: Session, args: list[str]) -> Result:
    days = parse_days(args[0] if args else None)
    try:
        insight = await session.robot.get_insight(days=days)
    except Exception as exc:
        raise CommandError(f"Failed to fetch insight: {exc}", EXIT_CONNECTION_FAILURE) from exc

    total = getattr(insight, "total_cycles", 0)
    average = float(getattr(insight, "average_cycles", 0.0) or 0.0)
    history = getattr(insight, "cycle_history", []) or []
    result = _rows(
        [
            ("Cycles", f"{total} (last {len(history)} days)"),
            ("Avg/day", f"{average:.1f}"),
        ]
    )
    if history:
        peak_date, peak_count = max(history, key=lambda entry: entry[1])
        result.lines.append(
            f"  {'Peak day':<{_LABEL_WIDTH}}{peak_count} on {peak_date.isoformat()}"
        )
        result.data["peak_day"] = {"date": peak_date.isoformat(), "cycles": peak_count}
    result.data.update({"total_cycles": total, "average_cycles": average, "days": days})
    return result


_DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _sleep_time(value: object) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M") if isinstance(value, time) else str(value)


async def _sleep_schedule(session: Session, args: list[str]) -> Result:
    schedule = getattr(session.robot, "sleep_schedule", None)
    if schedule is None:
        return Result(
            data={"enabled": False, "days": []},
            lines=["No sleep schedule set — the unit is always awake."],
        )

    enabled = bool(getattr(schedule, "is_enabled", False))
    days: list[dict[str, Any]] = []
    for day in getattr(schedule, "days", []):
        try:
            # pylitterbot's DayOfWeek runs Sun=0..Sat=6; Python's weekday is Mon=0..Sun=6.
            index = (int(getattr(day, "day", 0)) - 1) % 7
        except (TypeError, ValueError):
            continue
        days.append(
            {
                "day": _DAY_NAMES[index],
                "enabled": bool(getattr(day, "is_enabled", False)),
                "sleep_time": _sleep_time(getattr(day, "sleep_time", None)),
                "wake_time": _sleep_time(getattr(day, "wake_time", None)),
            }
        )
    days.sort(key=lambda entry: _DAY_NAMES.index(entry["day"]))

    lines = [] if enabled else ["Sleep schedule is disabled. Configured windows:"]
    for entry in days:
        window = (
            f"{entry['sleep_time'] or '—'} → {entry['wake_time'] or '—'}"
            if entry["enabled"]
            else "off"
        )
        lines.append(f"  {entry['day']}  {window}")
    return Result(data={"enabled": enabled, "days": days}, lines=lines)


# ── actions ──────────────────────────────────────────────────────────────────


async def _clean(session: Session, args: list[str]) -> Result:
    try:
        await session.robot.start_cleaning()
    except Exception as exc:
        raise CommandError(f"Failed to start cleaning: {exc}") from exc
    # Unlike the TUI, nothing here waits for the cycle to finish: the cloud has
    # accepted the command and a scheduled job shouldn't block for five minutes.
    return _outcome(True, "Clean cycle started")


async def _lock(session: Session, args: list[str]) -> Result:
    return _outcome(*await session.adapter.set_panel_lockout(True))


async def _unlock(session: Session, args: list[str]) -> Result:
    return _outcome(*await session.adapter.set_panel_lockout(False))


async def _sleep(session: Session, args: list[str]) -> Result:
    return _outcome(*await session.adapter.set_sleep(True))


async def _wake(session: Session, args: list[str]) -> Result:
    return _outcome(*await session.adapter.set_sleep(False))


async def _night_light(session: Session, args: list[str]) -> Result:
    mode = args[0].lower() if args else ""
    if mode not in ("on", "off", "auto"):
        raise CommandError("Usage: night-light on|off|auto")
    return _outcome(*await session.adapter.set_night_light(mode))


async def _night_light_brightness(session: Session, args: list[str]) -> Result:
    level = _int_arg(args, "night-light-brightness <level>")
    return _outcome(*await session.adapter.set_night_light_brightness(level))


async def _panel_brightness(session: Session, args: list[str]) -> Result:
    level = args[0].lower() if args else ""
    if level not in ("low", "medium", "high"):
        raise CommandError("Usage: panel-brightness low|medium|high")
    return _outcome(*await session.adapter.set_panel_brightness(level))


async def _wait_time(session: Session, args: list[str]) -> Result:
    valid = sorted(getattr(session.robot, "VALID_WAIT_TIMES", []))
    usage = f"wait-time <{'|'.join(str(v) for v in valid)}>" if valid else "wait-time <minutes>"
    minutes = _int_arg(args, usage)
    if valid and minutes not in valid:
        raise CommandError(
            f"Invalid wait time {minutes} — use one of: {', '.join(map(str, valid))}"
        )
    try:
        ok = await session.robot.set_wait_time(minutes)
    except Exception as exc:
        raise CommandError(f"Wait-time change failed: {exc}") from exc
    return _outcome(bool(ok), f"Wait time set to {minutes} min")


async def _power(session: Session, args: list[str]) -> Result:
    on = _on_off(args, "power on|off")
    try:
        ok = await session.robot.set_power_status(on)
    except Exception as exc:
        raise CommandError(f"Power change failed: {exc}") from exc
    return _outcome(bool(ok), f"Power {'on' if on else 'off'}")


async def _rename(session: Session, args: list[str]) -> Result:
    new_name = " ".join(args).strip()
    if not new_name:
        raise CommandError("Usage: rename <new name>")
    try:
        ok = await session.robot.set_name(new_name)
    except Exception as exc:
        raise CommandError(f"Rename failed: {exc}") from exc
    return _outcome(bool(ok), f"Renamed to '{new_name}'")


async def _privacy(session: Session, args: list[str]) -> Result:
    return _outcome(*await session.adapter.set_privacy_mode(_on_off(args, "privacy on|off")))


async def _volume(session: Session, args: list[str]) -> Result:
    return _outcome(*await session.adapter.set_volume(_int_arg(args, "volume <0-100>")))


async def _camera_audio(session: Session, args: list[str]) -> Result:
    return _outcome(*await session.adapter.set_camera_audio(_on_off(args, "camera-audio on|off")))


async def _drawer_reset(session: Session, args: list[str]) -> Result:
    return _outcome(*await session.adapter.reset_waste_drawer())


async def _export(session: Session, args: list[str]) -> Result:
    days = parse_days(args[0] if args else None)
    destination = resolve_dest(session.robot, session.output)
    print(f"Fetching history (last {days} days)…", file=sys.stderr)
    count = await build_history_csv(session.robot, session.pets, days, destination)
    return Result(
        data={"events": count, "path": str(destination), "days": days},
        lines=[f"Wrote {count} events to {destination}"],
    )


# ── registry ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HeadlessCommand:
    """One scriptable command: how to invoke it, and what it does."""

    name: str
    usage: str
    summary: str
    handler: Callable[[Session, list[str]], Awaitable[Result]]


COMMANDS: tuple[HeadlessCommand, ...] = (
    HeadlessCommand("status", "status", "at-a-glance robot status", _status),
    HeadlessCommand("info", "info", "full robot details (model, serial, firmware, …)", _info),
    HeadlessCommand("robots", "robots", "list robots on the account", _robots),
    HeadlessCommand("pets", "pets", "list pets on the account", _pets),
    HeadlessCommand("history", "history [count|all]", "recent activity (default: 50)", _history),
    HeadlessCommand("insight", "insight [days]", "cycle-usage statistics", _insight),
    HeadlessCommand("sleep-schedule", "sleep-schedule", "per-day sleep windows", _sleep_schedule),
    HeadlessCommand("clean", "clean", "start a clean cycle", _clean),
    HeadlessCommand("lock", "lock", "lock the control panel", _lock),
    HeadlessCommand("unlock", "unlock", "unlock the control panel", _unlock),
    HeadlessCommand("sleep", "sleep", "enable sleep mode", _sleep),
    HeadlessCommand("wake", "wake", "disable sleep mode", _wake),
    HeadlessCommand("night-light", "night-light on|off|auto", "set night light mode", _night_light),
    HeadlessCommand(
        "night-light-brightness",
        "night-light-brightness <level>",
        "set night light brightness",
        _night_light_brightness,
    ),
    HeadlessCommand(
        "panel-brightness",
        "panel-brightness low|medium|high",
        "set control-panel brightness (LR4/LR5)",
        _panel_brightness,
    ),
    HeadlessCommand("wait-time", "wait-time <minutes>", "set clean-cycle wait time", _wait_time),
    HeadlessCommand("power", "power on|off", "hard-power the unit", _power),
    HeadlessCommand("rename", "rename <new name>", "rename the unit in the cloud", _rename),
    HeadlessCommand("privacy", "privacy on|off", "toggle privacy mode (LR5)", _privacy),
    HeadlessCommand("volume", "volume <0-100>", "set sound volume (LR5)", _volume),
    HeadlessCommand(
        "camera-audio", "camera-audio on|off", "toggle camera audio (LR5)", _camera_audio
    ),
    HeadlessCommand(
        "drawer-reset", "drawer-reset", "reset the waste drawer indicator (LR5)", _drawer_reset
    ),
    HeadlessCommand("export", "export [days|month]", "export activity history to CSV", _export),
)

COMMANDS_BY_NAME: dict[str, HeadlessCommand] = {cmd.name: cmd for cmd in COMMANDS}


async def open_session(robot_selector: str | None, output: str | None = None) -> Session:
    """Authenticate and pick the robot to act on.

    Raises :class:`~asher.connection.HeadlessAuthError` when credentials are
    missing or the cloud is unreachable, and :class:`CommandError` when the
    account has no robots or ``robot_selector`` matches none of them.
    """
    from .connection import _connect_headless, _keyring_load_robot  # noqa: PLC0415

    account = await _connect_headless()
    robots = list(getattr(account, "robots", []))
    pets = list(getattr(account, "pets", []))
    if not robots:
        raise CommandError("No Litter Robots found on this account.", EXIT_CONNECTION_FAILURE)

    robot = resolve_robot(robots, robot_selector, _keyring_load_robot())
    if robot is None:
        available = "\n".join(
            f"  [{index}] {getattr(rb, 'name', '?')}" for index, rb in enumerate(robots)
        )
        raise CommandError(
            f"No robot matching '{robot_selector}'. Available:\n{available}",
            EXIT_NO_ROBOT_MATCH,
        )

    from .robot_adapters import make_adapter  # noqa: PLC0415

    return Session(
        account=account,
        robots=robots,
        pets=pets,
        robot=robot,
        adapter=make_adapter(robot),
        output=output,
    )


def render(result: Result, as_json: bool) -> str:
    return json.dumps(result.data, indent=2, default=str) if as_json else "\n".join(result.lines)


async def run(
    name: str,
    args: list[str] | None = None,
    *,
    robot: str | None = None,
    output: str | None = None,
    as_json: bool = False,
) -> int:
    """Run one headless command end to end and return a process exit code.

    Prints the result to stdout and any failure message to stderr, so callers
    only have to propagate the return value.
    """
    from .connection import HeadlessAuthError  # noqa: PLC0415

    command = COMMANDS_BY_NAME.get(name)
    if command is None:
        print(f"Unknown command '{name}'.", file=sys.stderr)
        return EXIT_COMMAND_REJECTED

    session: Session | None = None
    try:
        session = await open_session(robot, output)
        result = await command.handler(session, args or [])
    except HeadlessAuthError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    except (CommandError, ExportError) as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    finally:
        if session is not None:
            await _disconnect(session)

    rendered = render(result, as_json)
    if rendered:
        print(rendered)
    return result.code


async def _disconnect(session: Session) -> None:
    """Close the cloud session so the process can exit promptly."""
    with contextlib.suppress(Exception):
        await session.account.disconnect()
