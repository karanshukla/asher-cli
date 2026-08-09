"""Activity-history CSV export — shared by the TUI `export` command and the headless CLI.

`build_history_csv()` is the pure core: fetch, filter, write. No Textual, no
``_log_*`` helpers, no folder-open side effect. Both the interactive command path
(``asher/commands/__init__.py`` → ``_run_export``) and the headless path
(``asher --export`` → ``_run_headless_export``) call it, so the CSV content is
identical regardless of how it was invoked.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .activity_labels import ACTION_LABELS, activity_raw_text

if TYPE_CHECKING:
    from .robot_protocol import RobotProtocol

# Whisker caps activity history at 30 days; fetching with a high limit ensures
# full coverage up to that ceiling.
_FETCH_LIMIT = 500
_MAX_DAYS = 30

# Exit codes — the scripting contract for every headless command, not just export
# (see ROADMAP §25 and README § "Headless commands").
EXIT_OK = 0
EXIT_NO_CREDENTIALS = 1
EXIT_CONNECTION_FAILURE = 2
EXIT_WRITE_FAILURE = 3
EXIT_NO_ROBOT_MATCH = 4
EXIT_COMMAND_REJECTED = 5


class ExportError(Exception):
    """Base for headless export failures. ``code`` maps to a process exit code."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


def parse_days(raw: str | None) -> int:
    """Resolve a days argument the same way the ``export`` command does.

    Accepts a day count (clamped to 1–30), or ``"month"``/``"30"`` for the full
    Whisker ceiling. Raises :class:`ExportError` on garbage input.
    """
    value = raw or "month"
    if value in ("month", "30"):
        return _MAX_DAYS
    try:
        return max(1, min(_MAX_DAYS, int(value)))
    except ValueError:
        raise ExportError(
            f"Unknown period '{value}' — use a number of days (1-30) or 'month'.",
            EXIT_OK,  # arg errors don't get a failure exit code; the message is enough
        ) from None


def _filter_recent(acts: list[Any], days: int) -> list[tuple[Any, datetime]]:
    """Keep only events newer than ``days`` ago, returning ``(act, aware_ts)`` pairs."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    filtered: list[tuple[Any, datetime]] = []
    for act in acts:
        ts_dt = getattr(act, "timestamp", None)
        if ts_dt is None:
            continue
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        if ts_dt >= cutoff:
            filtered.append((act, ts_dt))
    filtered.sort(key=lambda x: x[1])
    return filtered


def resolve_dest(robot: RobotProtocol, output_override: str | None) -> Path:
    """Pick the output path: ``--output`` verbatim, else the standard cascade.

    ``~/Downloads`` is the standard export destination; if absent, fall back to
    ``~/Documents/asher-cli/`` (created), then ``~``. Matches the TUI path so the
    two write to the same place by default.
    """
    if output_override:
        return Path(output_override).expanduser()

    serial = getattr(robot, "serial", "unknown") or "unknown"
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"asher-{serial}-{date_str}.csv"

    downloads = Path.home() / "Downloads"
    if downloads.exists():
        return downloads / filename
    fallback = Path.home() / "Documents" / "asher-cli"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / filename


async def build_history_csv(robot: RobotProtocol, pets: list[Any], days: int, dest: Path) -> int:
    """Fetch activity history, filter to ``days``, and write a 7-column CSV.

    Returns the number of event rows written. Raises :class:`ExportError` on
    fetch or write failure so callers can map to a process exit code. Reuses
    ``ACTION_LABELS`` / ``activity_raw_text`` so events render identically to
    the ``history`` command output.
    """
    try:
        acts = await robot.get_activity_history(limit=_FETCH_LIMIT)
    except Exception as exc:  # noqa: BLE001 — surface any API failure as a clean exit
        raise ExportError(f"Failed to fetch history: {exc}", EXIT_CONNECTION_FAILURE) from exc

    filtered = _filter_recent(list(acts), days)

    serial = getattr(robot, "serial", "") or ""
    robot_name = getattr(robot, "name", "") or ""

    try:
        from tzlocal import get_localzone  # noqa: PLC0415

        local_tz: tzinfo = get_localzone()
    except Exception:  # noqa: BLE001 — tz discovery is best-effort; fall back to UTC
        local_tz = timezone.utc

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
            for act, ts_dt in filtered:
                local_dt = ts_dt.astimezone(local_tz)
                iso_ts = local_dt.isoformat()
                raw_str = activity_raw_text(act)
                label, _ = ACTION_LABELS.get(raw_str.lower(), (raw_str, ""))
                weight = getattr(act, "weight", None)
                weight_str = f"{float(weight):.1f}" if weight is not None else ""
                pet_id = getattr(act, "pet_id", None)
                pet_name = next(
                    (getattr(p, "name", "") for p in pets if getattr(p, "id", None) == pet_id),
                    "",
                )
                writer.writerow([iso_ts, label, raw_str, weight_str, pet_name, robot_name, serial])
    except Exception as exc:  # noqa: BLE001 — permissions, disk full, etc.
        raise ExportError(f"Failed to write CSV: {exc}", EXIT_WRITE_FAILURE) from exc

    return len(filtered)


def resolve_robot(
    robots: list[RobotProtocol], selector: str | None, preferred_serial: str
) -> RobotProtocol | None:
    """Pick the robot to export from, mirroring ``/robot`` and ``_finish_connect``.

    ``selector`` may be an index (``"1"``) or a partial case-insensitive name
    (``"Asher 2"``). When ``None``, the keyring-persisted preferred robot wins
    if it matches, otherwise ``robots[0]``. Returns ``None`` when a selector is
    given but matches nothing (caller maps to exit 4).
    """
    if not robots:
        return None
    if selector is None:
        return next(
            (rb for rb in robots if getattr(rb, "serial", None) == preferred_serial),
            robots[0],
        )
    if selector.isdigit():
        idx = int(selector)
        if 0 <= idx < len(robots):
            return robots[idx]
        return None
    target_lower = selector.lower()
    return next(
        (rb for rb in robots if target_lower in getattr(rb, "name", "").lower()),
        None,
    )


async def _run_headless_export(args: argparse.Namespace) -> int:
    """Legacy ``asher --export`` entry point — delegates to the headless runner.

    ``asher export 7`` and ``asher --export 7`` must produce byte-identical CSVs,
    so the flag form is a thin translation onto the ``export`` command rather
    than a second implementation. Imported locally because :mod:`asher.headless`
    imports this module for the CSV core.
    """
    from .headless import run  # noqa: PLC0415

    try:
        parse_days(args.export)
    except ExportError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code

    return await run(
        "export",
        [args.export] if args.export else [],
        robot=args.robot,
        output=args.output,
    )
