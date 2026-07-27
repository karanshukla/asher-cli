"""Tests for asher.export — shared CSV core + headless export path.

No Textual ``Pilot`` is needed: ``build_history_csv`` and ``_run_headless_export``
are plain async functions, testable the same way as ``asher.mcp_bridge``.
Mirrors the style of ``tests/test_mcp_bridge.py``.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from asher import export
from asher.export import (
    EXIT_CONNECTION_FAILURE,
    EXIT_NO_CREDENTIALS,
    EXIT_NO_ROBOT_MATCH,
    EXIT_OK,
    EXIT_WRITE_FAILURE,
    ExportError,
    build_history_csv,
    parse_days,
    resolve_dest,
    resolve_robot,
)

# ── parse_days ────────────────────────────────────────────────────────────────


class TestParseDays:
    def test_month_alias(self):
        assert parse_days("month") == 30

    def test_30_alias(self):
        assert parse_days("30") == 30

    def test_none_defaults_to_month(self):
        assert parse_days(None) == 30

    def test_explicit_count(self):
        assert parse_days("7") == 7

    def test_clamped_to_min(self):
        assert parse_days("0") == 1

    def test_clamped_to_max(self):
        assert parse_days("100") == 30

    def test_garbage_raises(self):
        with pytest.raises(ExportError) as exc:
            parse_days("notadays")
        assert "notadays" in str(exc.value)


# ── resolve_dest ──────────────────────────────────────────────────────────────


class TestResolveDest:
    def test_output_override_used_verbatim(self, tmp_path):
        robot = MagicMock(serial="LR4C001")
        override = tmp_path / "custom.csv"
        assert resolve_dest(robot, str(override)) == override

    def test_output_override_expands_user(self):
        robot = MagicMock(serial="LR4C001")
        with patch.object(export.Path, "expanduser") as mock_expand:
            resolve_dest(robot, "~/some/path.csv")
        mock_expand.assert_called_once()

    def test_downloads_when_present(self, tmp_path):
        robot = MagicMock(serial="LR4C001")
        downloads = tmp_path / "Downloads"
        downloads.mkdir()
        with patch.object(export.Path, "home", return_value=tmp_path):
            dest = resolve_dest(robot, None)
        assert dest.parent == downloads
        assert "asher-LR4C001-" in dest.name
        assert dest.suffix == ".csv"
        assert datetime.now().strftime("%Y-%m-%d") in dest.name

    def test_documents_fallback_when_no_downloads(self, tmp_path):
        robot = MagicMock(serial="ABC")
        with patch.object(export.Path, "home", return_value=tmp_path):
            dest = resolve_dest(robot, None)
        assert dest.parent == tmp_path / "Documents" / "asher-cli"
        assert dest.parent.exists()

    def test_unknown_serial_handled(self, tmp_path):
        robot = MagicMock(serial=None)
        downloads = tmp_path / "Downloads"
        downloads.mkdir()
        with patch.object(export.Path, "home", return_value=tmp_path):
            dest = resolve_dest(robot, None)
        assert "asher-unknown-" in dest.name


# ── resolve_robot ─────────────────────────────────────────────────────────────


def _robots(*names: str) -> list[MagicMock]:
    robots = []
    for i, n in enumerate(names):
        rb = MagicMock(serial=f"S{i}")
        rb.name = n  # name= on MagicMock sets the mock id, not a .name attribute
        robots.append(rb)
    return robots


class TestResolveRobot:
    def test_empty_list_returns_none(self):
        assert resolve_robot([], None, "") is None

    def test_no_selector_returns_first(self):
        robots = _robots("Asher", "Luna")
        assert resolve_robot(robots, None, "") is robots[0]

    def test_no_selector_prefers_keyring_serial(self):
        robots = _robots("Asher", "Luna")
        assert resolve_robot(robots, None, "S1") is robots[1]

    def test_no_selector_falls_back_to_first_when_serial_missing(self):
        robots = _robots("Asher", "Luna")
        assert resolve_robot(robots, None, "ZZZ") is robots[0]

    def test_index_selector(self):
        robots = _robots("Asher", "Luna", "Milo")
        assert resolve_robot(robots, "2", "") is robots[2]

    def test_index_out_of_range_returns_none(self):
        robots = _robots("Asher")
        assert resolve_robot(robots, "5", "") is None

    def test_name_partial_case_insensitive(self):
        robots = _robots("Asher 2", "Luna")
        assert resolve_robot(robots, "asher", "") is robots[0]

    def test_name_no_match_returns_none(self):
        robots = _robots("Asher")
        assert resolve_robot(robots, "zzz", "") is None


# ── build_history_csv ─────────────────────────────────────────────────────────


def _act(
    *,
    days_ago: float = 1,
    action_text: str = "Clean Cycle Complete",
    weight: float | None = 9.1,
    pet_id: str | None = None,
) -> MagicMock:
    act = MagicMock()
    act.timestamp = datetime.now(timezone.utc) - timedelta(days=days_ago)
    act.action = MagicMock(text=action_text)
    act.weight = weight
    act.pet_id = pet_id
    return act


def _robot(
    *,
    serial: str = "S1",
    name: str = "R",
    acts: list[MagicMock] | None = None,
) -> MagicMock:
    """Build a mock robot. ``name=`` can't go through MagicMock kwargs (sets id, not attr)."""
    rb = MagicMock(
        serial=serial,
        get_activity_history=AsyncMock(return_value=acts if acts is not None else []),
    )
    rb.name = name
    return rb


class TestBuildHistoryCsv:
    async def test_writes_header_and_rows(self, tmp_path):
        robot = _robot(serial="LR4C001", name="Idiot Box", acts=[_act(days_ago=1)])
        dest = tmp_path / "out.csv"
        count = await build_history_csv(robot, [], 30, dest)
        assert count == 1
        rows = list(csv.reader(dest.read_text().splitlines()))
        assert rows[0] == [
            "timestamp",
            "event",
            "raw_event",
            "weight_lb",
            "pet_name",
            "robot_name",
            "robot_serial",
        ]
        assert len(rows) == 2
        assert rows[1][1] == "Clean cycle complete"
        assert rows[1][2] == "Clean Cycle Complete"
        assert rows[1][3] == "9.1"
        assert rows[1][4] == ""
        assert rows[1][5] == "Idiot Box"
        assert rows[1][6] == "LR4C001"

    async def test_filters_out_events_older_than_window(self, tmp_path):
        robot = _robot(acts=[_act(days_ago=1), _act(days_ago=20)])
        dest = tmp_path / "out.csv"
        count = await build_history_csv(robot, [], 7, dest)
        assert count == 1

    async def test_sorts_ascending_by_timestamp(self, tmp_path):
        newer = _act(days_ago=1)
        older = _act(days_ago=5)
        robot = _robot(acts=[newer, older])
        dest = tmp_path / "out.csv"
        await build_history_csv(robot, [], 30, dest)
        rows = list(csv.reader(dest.read_text().splitlines()))
        # older event first (ascending)
        assert rows[1][2] == older.action.text
        assert rows[2][2] == newer.action.text

    async def test_resolves_pet_name_by_pet_id(self, tmp_path):
        pet = MagicMock(id="pet-42")
        pet.name = "Asher"
        robot = _robot(acts=[_act(days_ago=1, pet_id="pet-42")])
        dest = tmp_path / "out.csv"
        await build_history_csv(robot, [pet], 30, dest)
        rows = list(csv.reader(dest.read_text().splitlines()))
        assert rows[1][4] == "Asher"

    async def test_empty_history_writes_header_only(self, tmp_path):
        robot = _robot(acts=[])
        dest = tmp_path / "out.csv"
        count = await build_history_csv(robot, [], 30, dest)
        assert count == 0
        rows = list(csv.reader(dest.read_text().splitlines()))
        assert len(rows) == 1  # header only

    async def test_fetch_failure_raises_connection_error(self, tmp_path):
        robot = _robot(acts=None)
        robot.get_activity_history = AsyncMock(side_effect=RuntimeError("boom"))
        dest = tmp_path / "out.csv"
        with pytest.raises(ExportError) as exc:
            await build_history_csv(robot, [], 30, dest)
        assert exc.value.code == EXIT_CONNECTION_FAILURE
        assert "boom" in str(exc.value)

    async def test_write_failure_raises_write_error(self, tmp_path):
        robot = _robot(acts=[_act(days_ago=1)])
        # A path whose parent doesn't exist and can't be created (file in the way).
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        dest = blocker / "out.csv"
        with pytest.raises(ExportError) as exc:
            await build_history_csv(robot, [], 30, dest)
        assert exc.value.code == EXIT_WRITE_FAILURE

    async def test_naive_timestamp_treated_as_utc(self, tmp_path):
        act = MagicMock()
        act.timestamp = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        act.action = MagicMock(text="Ready")
        act.weight = None
        act.pet_id = None
        robot = _robot(acts=[act])
        dest = tmp_path / "out.csv"
        count = await build_history_csv(robot, [], 30, dest)
        assert count == 1

    async def test_none_weight_leaves_cell_blank(self, tmp_path):
        robot = _robot(acts=[_act(days_ago=1, weight=None)])
        dest = tmp_path / "out.csv"
        await build_history_csv(robot, [], 30, dest)
        rows = list(csv.reader(dest.read_text().splitlines()))
        assert rows[1][3] == ""


# ── _run_headless_export ──────────────────────────────────────────────────────


def _export_args(
    *, export: str | None = "month", output: str | None = None, robot: str | None = None
) -> argparse.Namespace:
    return argparse.Namespace(export=export, output=output, robot=robot)


def _account(robots: list[MagicMock] | None = None, pets: list | None = None) -> MagicMock:
    acc = MagicMock()
    acc.robots = robots if robots is not None else []
    acc.pets = pets if pets is not None else []
    return acc


class TestRunHeadlessExport:
    async def test_happy_path_writes_csv_and_exits_zero(self, tmp_path, capsys):
        act = _act(days_ago=1)
        account = _account(robots=[_robot(serial="LR4C001", name="Idiot Box", acts=[act])])
        dest = tmp_path / "out.csv"
        with (
            patch("asher.connection._connect_headless", AsyncMock(return_value=account)),
            patch("asher.connection._keyring_load_robot", return_value=""),
        ):
            code = await export._run_headless_export(_export_args(export="7", output=str(dest)))
        assert code == EXIT_OK
        assert dest.exists()
        rows = list(csv.reader(dest.read_text().splitlines()))
        assert len(rows) == 2
        captured = capsys.readouterr()
        assert "Fetching history" in captured.err
        assert "1 events" in captured.out

    async def test_no_credentials_exits_one(self, capsys):
        from asher.connection import HeadlessAuthError

        with patch(
            "asher.connection._connect_headless",
            AsyncMock(side_effect=HeadlessAuthError("no creds", EXIT_NO_CREDENTIALS)),
        ):
            code = await export._run_headless_export(_export_args())
        assert code == EXIT_NO_CREDENTIALS
        assert "no creds" in capsys.readouterr().err

    async def test_connection_failure_exits_two(self, capsys):
        from asher.connection import HeadlessAuthError

        with patch(
            "asher.connection._connect_headless",
            AsyncMock(side_effect=HeadlessAuthError("down", EXIT_CONNECTION_FAILURE)),
        ):
            code = await export._run_headless_export(_export_args())
        assert code == EXIT_CONNECTION_FAILURE
        assert "down" in capsys.readouterr().err

    async def test_no_robots_on_account_exits_two(self, capsys):
        account = _account(robots=[])
        with (
            patch("asher.connection._connect_headless", AsyncMock(return_value=account)),
            patch("asher.connection._keyring_load_robot", return_value=""),
        ):
            code = await export._run_headless_export(_export_args())
        assert code == EXIT_CONNECTION_FAILURE
        assert "No Litter Robots" in capsys.readouterr().err

    async def test_robot_selector_no_match_exits_four(self, capsys):
        account = _account(robots=[_robot(serial="S0", name="Asher")])
        with (
            patch("asher.connection._connect_headless", AsyncMock(return_value=account)),
            patch("asher.connection._keyring_load_robot", return_value=""),
        ):
            code = await export._run_headless_export(_export_args(robot="zzz"))
        assert code == EXIT_NO_ROBOT_MATCH
        err = capsys.readouterr().err
        assert "zzz" in err
        assert "Asher" in err

    async def test_fetch_failure_during_export_exits_two(self, tmp_path, capsys):
        robot = _robot(serial="S0", name="Asher", acts=None)
        robot.get_activity_history = AsyncMock(side_effect=RuntimeError("api down"))
        account = _account(robots=[robot])
        dest = tmp_path / "out.csv"
        with (
            patch("asher.connection._connect_headless", AsyncMock(return_value=account)),
            patch("asher.connection._keyring_load_robot", return_value=""),
        ):
            code = await export._run_headless_export(_export_args(output=str(dest)))
        assert code == EXIT_CONNECTION_FAILURE
        assert "api down" in capsys.readouterr().err

    async def test_invalid_period_prints_message(self, capsys):
        code = await export._run_headless_export(_export_args(export="garbage"))
        assert code == EXIT_OK
        assert "garbage" in capsys.readouterr().err

    async def test_month_default_uses_thirty_days(self, tmp_path):
        robot = _robot(serial="S0", name="Asher", acts=[])
        account = _account(robots=[robot])
        dest = tmp_path / "out.csv"
        with (
            patch("asher.connection._connect_headless", AsyncMock(return_value=account)),
            patch("asher.connection._keyring_load_robot", return_value=""),
        ):
            code = await export._run_headless_export(_export_args(export="month", output=str(dest)))
        assert code == EXIT_OK
        robot.get_activity_history.assert_called_once_with(limit=500)


# ── __main__ parser ───────────────────────────────────────────────────────────


class TestBuildParser:
    def test_export_flag_parsed(self):
        from asher.__main__ import _build_parser

        args = _build_parser().parse_args(["--export", "7"])
        assert args.export == "7"
        assert args.output is None
        assert args.robot is None

    def test_bare_export_defaults_to_month(self):
        from asher.__main__ import _build_parser

        args = _build_parser().parse_args(["--export"])
        assert args.export == "month"

    def test_no_export_flag_is_none(self):
        from asher.__main__ import _build_parser

        args = _build_parser().parse_args([])
        assert args.export is None

    def test_output_and_robot_flags(self):
        from asher.__main__ import _build_parser

        args = _build_parser().parse_args(
            ["--export", "month", "--output", "/tmp/x.csv", "--robot", "Asher"]
        )
        assert args.export == "month"
        assert args.output == "/tmp/x.csv"
        assert args.robot == "Asher"
