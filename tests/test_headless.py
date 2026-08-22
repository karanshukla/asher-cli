"""Tests for the headless command surface (``asher <command>``).

Two layers, mirroring how the module is built:

* the pure parts — ``Result`` rendering, argument parsing, the registry — which
  need no event loop and no mocks;
* ``run()`` end to end with ``_connect_headless`` patched out, which is where
  the exit-code contract lives.

No Pilot and no Textual: the point of the module is that it works without them.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from asher.export import (
    EXIT_COMMAND_REJECTED,
    EXIT_CONNECTION_FAILURE,
    EXIT_NO_CREDENTIALS,
    EXIT_NO_ROBOT_MATCH,
    EXIT_OK,
)
from asher.headless import (
    COMMANDS,
    COMMANDS_BY_NAME,
    CommandError,
    Result,
    Session,
    render,
    run,
)


def _robot(*, serial: str = "S1", name: str = "Asher", model: str = "LitterRobot4", **attrs):
    """Mock robot whose class name drives ``make_adapter``/``robot_model`` dispatch."""
    cls = type(model, (MagicMock,), {})
    robot = cls()
    robot.name = name
    robot.serial = serial
    robot.refresh = AsyncMock()
    robot.is_online = True
    robot.waste_drawer_level = 42.0
    robot.litter_level = 71.0
    robot.pet_weight = 9.1
    robot.last_seen = datetime.now(timezone.utc)
    robot.night_light_mode = None
    robot.night_light_mode_enabled = False
    robot.panel_brightness = None
    robot.cycle_count = 12
    robot.clean_cycle_wait_time_minutes = 7
    robot.sleep_mode_enabled = False
    robot.panel_lock_enabled = False
    robot.sleep_schedule = None
    robot.firmware = "1.0"
    robot.power_type = "AC"
    robot.status = SimpleNamespace(text="Ready")
    robot.get_activity_history = AsyncMock(return_value=[])
    for key, value in attrs.items():
        setattr(robot, key, value)
    return robot


def _account(robots=None, pets=None):
    account = MagicMock()
    account.robots = robots if robots is not None else [_robot()]
    account.pets = pets if pets is not None else []
    account.disconnect = AsyncMock()
    return account


def _session(robot=None, pets=None, output=None) -> Session:
    from asher.robot_adapters import make_adapter

    robot = robot or _robot()
    return Session(
        account=_account([robot]),
        robots=[robot],
        pets=pets or [],
        robot=robot,
        adapter=make_adapter(robot),
        output=output,
    )


def _act(*, days_ago: float = 1, action_text: str = "Clean Cycle Complete", weight=9.1):
    act = MagicMock()
    act.timestamp = datetime.now(timezone.utc) - timedelta(days=days_ago)
    act.action = MagicMock(text=action_text)
    act.weight = weight
    act.pet_id = None
    return act


def _connected(account):
    """Patch the credential/connection layer so ``run()`` reaches a command."""
    return (
        patch("asher.connection._connect_headless", AsyncMock(return_value=account)),
        patch("asher.connection._keyring_load_robot", return_value=""),
    )


async def _run(name, args=None, *, account=None, **kwargs):
    connect, keyring = _connected(account or _account())
    with connect, keyring:
        return await run(name, args or [], **kwargs)


# ── registry ─────────────────────────────────────────────────────────────────


class TestRegistry:
    def test_names_are_unique(self):
        names = [command.name for command in COMMANDS]
        assert len(names) == len(set(names))

    def test_lookup_matches_the_tuple(self):
        assert set(COMMANDS_BY_NAME) == {command.name for command in COMMANDS}

    def test_every_command_documents_usage_and_summary(self):
        for command in COMMANDS:
            assert command.usage.startswith(command.name)
            assert command.summary

    @pytest.mark.parametrize(
        "name",
        ["status", "info", "robots", "pets", "history", "insight", "clean", "export"],
    )
    def test_core_commands_are_registered(self, name):
        assert name in COMMANDS_BY_NAME


# ── rendering ────────────────────────────────────────────────────────────────


class TestRender:
    def test_text_rendering_joins_lines(self):
        assert render(Result(lines=["a", "b"]), as_json=False) == "a\nb"

    def test_json_rendering_emits_the_data_payload(self):
        out = json.loads(render(Result(data={"ok": True, "message": "done"}), as_json=True))
        assert out == {"ok": True, "message": "done"}

    def test_json_rendering_coerces_unserialisable_values(self):
        out = json.loads(render(Result(data={"when": datetime(2026, 1, 1)}), as_json=True))
        assert out["when"].startswith("2026-01-01")

    def test_empty_result_renders_empty_text(self):
        assert render(Result(), as_json=False) == ""


# ── read commands ────────────────────────────────────────────────────────────


class TestStatusAndInfo:
    async def test_status_refreshes_before_reading(self):
        session = _session()
        await COMMANDS_BY_NAME["status"].handler(session, [])
        session.robot.refresh.assert_awaited_once()

    async def test_status_reports_the_readable_state(self):
        result = await COMMANDS_BY_NAME["status"].handler(_session(), [])
        assert result.data["online"] == "yes"
        assert result.data["status"] == "Ready"
        assert result.data["drawer"] == "42%"
        assert result.data["cat_weight"] == "9.1 lb"

    async def test_status_refresh_failure_is_a_connection_failure(self):
        robot = _robot()
        robot.refresh = AsyncMock(side_effect=RuntimeError("api down"))
        with pytest.raises(CommandError) as excinfo:
            await COMMANDS_BY_NAME["status"].handler(_session(robot), [])
        assert excinfo.value.code == EXIT_CONNECTION_FAILURE

    async def test_info_includes_identity_and_settings(self):
        result = await COMMANDS_BY_NAME["info"].handler(_session(), [])
        assert result.data["model"] == "LR4"
        assert result.data["serial"] == "S1"
        assert result.data["wait_time"] == "7 min"
        assert result.data["night_light"] == "off"

    async def test_missing_values_degrade_to_em_dashes(self):
        robot = _robot(litter_level=None, clean_cycle_wait_time_minutes=None, cycle_count=None)
        result = await COMMANDS_BY_NAME["info"].handler(_session(robot), [])
        assert result.data["litter"] == "—"
        assert result.data["wait_time"] == "—"
        assert result.data["cycles"] == "—"


class TestListings:
    async def test_robots_marks_the_active_one(self):
        first, second = _robot(serial="A", name="One"), _robot(serial="B", name="Two")
        session = _session(first)
        session.robots = [first, second]
        result = await COMMANDS_BY_NAME["robots"].handler(session, [])
        assert [entry["active"] for entry in result.data["robots"]] == [True, False]
        assert result.data["robots"][1]["name"] == "Two"

    async def test_pets_lists_names_and_weights(self):
        pets = [SimpleNamespace(name="Asher", weight=9.1)]
        result = await COMMANDS_BY_NAME["pets"].handler(_session(pets=pets), [])
        assert result.data["pets"][0]["name"] == "Asher"
        assert "9.1 lb" in result.lines[0]

    async def test_no_pets_says_so_rather_than_printing_nothing(self):
        result = await COMMANDS_BY_NAME["pets"].handler(_session(), [])
        assert result.data["pets"] == []
        assert "No pets" in result.lines[0]


class TestHistory:
    async def test_default_limit_is_fifty(self):
        session = _session()
        await COMMANDS_BY_NAME["history"].handler(session, [])
        session.robot.get_activity_history.assert_awaited_once_with(limit=50)

    async def test_all_requests_the_ceiling(self):
        session = _session()
        await COMMANDS_BY_NAME["history"].handler(session, ["all"])
        session.robot.get_activity_history.assert_awaited_once_with(limit=500)

    async def test_explicit_count_is_clamped(self):
        session = _session()
        await COMMANDS_BY_NAME["history"].handler(session, ["9999"])
        session.robot.get_activity_history.assert_awaited_once_with(limit=500)

    async def test_garbage_count_is_rejected(self):
        with pytest.raises(CommandError, match="banana"):
            await COMMANDS_BY_NAME["history"].handler(_session(), ["banana"])

    async def test_events_carry_label_raw_text_and_timestamp(self):
        robot = _robot()
        robot.get_activity_history = AsyncMock(return_value=[_act()])
        result = await COMMANDS_BY_NAME["history"].handler(_session(robot), [])
        event = result.data["events"][0]
        assert event["event"] == "Clean cycle complete"
        assert event["raw_event"] == "Clean Cycle Complete"
        assert event["timestamp"] is not None

    async def test_empty_history_explains_itself(self):
        result = await COMMANDS_BY_NAME["history"].handler(_session(), [])
        assert result.data["events"] == []
        assert "No activity history" in result.lines[0]

    async def test_fetch_failure_is_a_connection_failure(self):
        robot = _robot()
        robot.get_activity_history = AsyncMock(side_effect=RuntimeError("api down"))
        with pytest.raises(CommandError) as excinfo:
            await COMMANDS_BY_NAME["history"].handler(_session(robot), [])
        assert excinfo.value.code == EXIT_CONNECTION_FAILURE


class TestInsight:
    async def test_totals_and_peak_day(self):
        robot = _robot()
        robot.get_insight = AsyncMock(
            return_value=SimpleNamespace(
                total_cycles=42,
                average_cycles=1.4,
                cycle_history=[(datetime(2026, 1, 1).date(), 2), (datetime(2026, 1, 2).date(), 9)],
            )
        )
        result = await COMMANDS_BY_NAME["insight"].handler(_session(robot), ["7"])
        assert result.data["total_cycles"] == 42
        assert result.data["days"] == 7
        assert result.data["peak_day"]["cycles"] == 9

    async def test_default_window_is_the_whisker_ceiling(self):
        robot = _robot()
        robot.get_insight = AsyncMock(
            return_value=SimpleNamespace(total_cycles=0, average_cycles=0.0, cycle_history=[])
        )
        await COMMANDS_BY_NAME["insight"].handler(_session(robot), [])
        robot.get_insight.assert_awaited_once_with(days=30)


class TestSleepSchedule:
    async def test_absent_schedule_is_reported_not_crashed(self):
        result = await COMMANDS_BY_NAME["sleep-schedule"].handler(_session(), [])
        assert result.data == {"enabled": False, "days": []}

    async def test_days_are_translated_and_ordered(self):
        # pylitterbot's DayOfWeek is Sun=0..Sat=6.
        robot = _robot(
            sleep_schedule=SimpleNamespace(
                is_enabled=True,
                days=[
                    SimpleNamespace(
                        day=2, is_enabled=True, sleep_time=time(22, 0), wake_time=time(6, 0)
                    ),
                    SimpleNamespace(day=1, is_enabled=False, sleep_time=None, wake_time=None),
                ],
            )
        )
        result = await COMMANDS_BY_NAME["sleep-schedule"].handler(_session(robot), [])
        assert [entry["day"] for entry in result.data["days"]] == ["Mon", "Tue"]
        assert result.data["days"][1]["sleep_time"] == "22:00"
        assert result.data["days"][0]["enabled"] is False


# ── action commands ──────────────────────────────────────────────────────────


class TestActions:
    async def test_clean_returns_immediately_without_waiting_for_the_cycle(self):
        session = _session()
        session.robot.start_cleaning = AsyncMock(return_value=True)
        result = await COMMANDS_BY_NAME["clean"].handler(session, [])
        assert result.data["ok"] is True
        session.robot.start_cleaning.assert_awaited_once()

    async def test_clean_failure_is_reported(self):
        session = _session()
        session.robot.start_cleaning = AsyncMock(side_effect=RuntimeError("nope"))
        with pytest.raises(CommandError, match="nope"):
            await COMMANDS_BY_NAME["clean"].handler(session, [])

    async def test_lock_and_unlock_go_through_the_adapter(self):
        session = _session()
        session.robot.set_panel_lockout = AsyncMock(return_value=True)
        assert (await COMMANDS_BY_NAME["lock"].handler(session, [])).data["message"] == (
            "Panel locked"
        )
        assert (await COMMANDS_BY_NAME["unlock"].handler(session, [])).data["message"] == (
            "Panel unlocked"
        )

    async def test_a_cloud_rejection_is_a_command_error(self):
        session = _session()
        session.robot.set_panel_lockout = AsyncMock(return_value=False)
        with pytest.raises(CommandError) as excinfo:
            await COMMANDS_BY_NAME["lock"].handler(session, [])
        assert excinfo.value.code == EXIT_COMMAND_REJECTED

    async def test_night_light_rejects_an_unknown_mode(self):
        with pytest.raises(CommandError, match="Usage: night-light"):
            await COMMANDS_BY_NAME["night-light"].handler(_session(), ["purple"])

    async def test_night_light_accepts_auto_on_lr4(self):
        session = _session()
        session.robot.set_night_light_mode = AsyncMock(return_value=True)
        result = await COMMANDS_BY_NAME["night-light"].handler(session, ["auto"])
        assert result.data["message"] == "Night light auto"

    async def test_lr3_reports_that_auto_is_unsupported(self):
        session = _session(_robot(model="LitterRobot3"))
        with pytest.raises(CommandError, match="does not support auto"):
            await COMMANDS_BY_NAME["night-light"].handler(session, ["auto"])

    async def test_lr5_only_command_explains_itself_on_lr4(self):
        with pytest.raises(CommandError, match="only available on the LR5"):
            await COMMANDS_BY_NAME["privacy"].handler(_session(), ["on"])

    async def test_power_requires_on_or_off(self):
        with pytest.raises(CommandError, match="Usage: power on\\|off"):
            await COMMANDS_BY_NAME["power"].handler(_session(), ["maybe"])

    async def test_power_sets_the_requested_state(self):
        session = _session()
        session.robot.set_power_status = AsyncMock(return_value=True)
        result = await COMMANDS_BY_NAME["power"].handler(session, ["off"])
        session.robot.set_power_status.assert_awaited_once_with(False)
        assert result.data["message"] == "Power off"

    async def test_wait_time_validates_against_the_model_whitelist(self):
        session = _session(_robot(VALID_WAIT_TIMES=[3, 7, 15]))
        with pytest.raises(CommandError, match="Invalid wait time 4"):
            await COMMANDS_BY_NAME["wait-time"].handler(session, ["4"])

    async def test_wait_time_accepts_a_valid_value(self):
        session = _session(_robot(VALID_WAIT_TIMES=[3, 7, 15]))
        session.robot.set_wait_time = AsyncMock(return_value=True)
        result = await COMMANDS_BY_NAME["wait-time"].handler(session, ["7"])
        assert result.data["message"] == "Wait time set to 7 min"

    async def test_wait_time_requires_a_number(self):
        with pytest.raises(CommandError, match="Usage: wait-time"):
            await COMMANDS_BY_NAME["wait-time"].handler(_session(), ["soon"])

    async def test_rename_joins_multi_word_names(self):
        session = _session()
        session.robot.set_name = AsyncMock(return_value=True)
        await COMMANDS_BY_NAME["rename"].handler(session, ["The", "Idiot", "Box"])
        session.robot.set_name.assert_awaited_once_with("The Idiot Box")

    async def test_rename_requires_a_name(self):
        with pytest.raises(CommandError, match="Usage: rename"):
            await COMMANDS_BY_NAME["rename"].handler(_session(), [])


# ── export ───────────────────────────────────────────────────────────────────


class TestExportCommand:
    async def test_writes_the_csv_to_the_requested_path(self, tmp_path, capsys):
        robot = _robot()
        robot.get_activity_history = AsyncMock(return_value=[_act()])
        dest = tmp_path / "out.csv"
        result = await COMMANDS_BY_NAME["export"].handler(_session(robot, output=str(dest)), ["7"])
        assert result.data["events"] == 1
        assert result.data["days"] == 7
        rows = list(csv.reader(dest.read_text().splitlines()))
        assert len(rows) == 2
        assert "Fetching history (last 7 days)" in capsys.readouterr().err


# ── run() ────────────────────────────────────────────────────────────────────


class TestRun:
    async def test_unknown_command_exits_rejected(self, capsys):
        assert await run("frobnicate") == EXIT_COMMAND_REJECTED
        assert "frobnicate" in capsys.readouterr().err

    async def test_happy_path_prints_and_exits_zero(self, capsys):
        assert await _run("status") == EXIT_OK
        assert "Ready" in capsys.readouterr().out

    async def test_json_flag_switches_the_rendering(self, capsys):
        assert await _run("status", as_json=True) == EXIT_OK
        assert json.loads(capsys.readouterr().out)["status"] == "Ready"

    async def test_missing_credentials_exit_one(self, capsys):
        from asher.connection import HeadlessAuthError

        with patch(
            "asher.connection._connect_headless",
            AsyncMock(side_effect=HeadlessAuthError("no creds", EXIT_NO_CREDENTIALS)),
        ):
            assert await run("status") == EXIT_NO_CREDENTIALS
        assert "no creds" in capsys.readouterr().err

    async def test_no_robots_on_the_account_exits_two(self, capsys):
        assert await _run("status", account=_account(robots=[])) == EXIT_CONNECTION_FAILURE
        assert "No Litter Robots" in capsys.readouterr().err

    async def test_unmatched_robot_selector_lists_the_alternatives(self, capsys):
        code = await _run("status", account=_account([_robot(name="Asher")]), robot="zzz")
        assert code == EXIT_NO_ROBOT_MATCH
        err = capsys.readouterr().err
        assert "zzz" in err
        assert "Asher" in err

    async def test_robot_selector_picks_by_partial_name(self, capsys):
        account = _account([_robot(name="Upstairs"), _robot(name="Downstairs Box")])
        assert await _run("status", account=account, robot="Downstairs") == EXIT_OK
        assert "Downstairs Box" in capsys.readouterr().out

    async def test_a_rejected_command_exits_five(self, capsys):
        robot = _robot()
        robot.set_panel_lockout = AsyncMock(return_value=False)
        assert await _run("lock", account=_account([robot])) == EXIT_COMMAND_REJECTED
        assert "rejected" in capsys.readouterr().err

    async def test_the_cloud_session_is_closed_afterwards(self):
        account = _account()
        await _run("status", account=account)
        account.disconnect.assert_awaited_once()

    async def test_the_session_is_closed_even_when_the_command_fails(self):
        robot = _robot()
        robot.refresh = AsyncMock(side_effect=RuntimeError("boom"))
        account = _account([robot])
        assert await _run("status", account=account) == EXIT_CONNECTION_FAILURE
        account.disconnect.assert_awaited_once()


# ── argument parsing ─────────────────────────────────────────────────────────


class TestParser:
    def _parse(self, argv):
        from asher.__main__ import _build_parser

        return _build_parser().parse_args(argv)

    def test_no_arguments_selects_the_tui(self):
        args = self._parse([])
        assert args.command is None
        assert args.export is None

    def test_subcommand_is_captured(self):
        args = self._parse(["status"])
        assert args.command == "status"
        assert args.args == []

    def test_subcommand_arguments_are_collected(self):
        args = self._parse(["night-light", "auto"])
        assert args.command == "night-light"
        assert args.args == ["auto"]

    def test_multi_word_arguments_survive(self):
        args = self._parse(["rename", "The", "Idiot", "Box"])
        assert args.args == ["The", "Idiot", "Box"]

    def test_json_flag_defaults_off(self):
        assert self._parse(["status"]).json is False

    def test_json_flag_is_accepted(self):
        assert self._parse(["status", "--json"]).json is True

    def test_robot_flag_after_the_subcommand(self):
        assert self._parse(["status", "--robot", "Asher"]).robot == "Asher"

    def test_robot_flag_before_the_subcommand_is_not_clobbered(self):
        args = self._parse(["--robot", "Asher", "status"])
        assert args.robot == "Asher"

    def test_export_subcommand_takes_an_output_path(self):
        args = self._parse(["export", "7", "--output", "/tmp/x.csv"])
        assert args.command == "export"
        assert args.args == ["7"]
        assert args.output == "/tmp/x.csv"

    def test_legacy_export_flag_still_parses(self):
        args = self._parse(["--export", "7", "--output", "/tmp/x.csv"])
        assert args.command is None
        assert args.export == "7"
        assert args.output == "/tmp/x.csv"

    def test_history_takes_a_type_flag(self):
        args = self._parse(["history", "20", "--type", "cat"])
        assert args.args == ["20"]
        assert args.type == "cat"

    def test_the_type_flag_is_folded_back_into_the_handler_arguments(self):
        from asher.__main__ import _handler_args

        assert _handler_args(self._parse(["history", "20", "--type", "cat"])) == [
            "20",
            "--type",
            "cat",
        ]

    def test_handler_arguments_are_untouched_without_the_flag(self):
        from asher.__main__ import _handler_args

        assert _handler_args(self._parse(["history", "20"])) == ["20"]

    def test_sleep_schedule_takes_a_set_form(self):
        args = self._parse(["sleep-schedule", "set", "mon", "22:00", "07:00"])
        assert args.args == ["set", "mon", "22:00", "07:00"]

    def test_every_registered_command_has_a_subparser(self):
        for command in COMMANDS:
            assert self._parse([command.name]).command == command.name


# ── roadmap gaps: filters, colour, schedule writes ───────────────────────────


class TestHistoryFiltering:
    async def test_type_flag_reaches_the_lr5_endpoint(self):
        robot = _robot(model="LitterRobot5")
        robot.get_activities = AsyncMock(
            return_value=[{"timestamp": "2026-08-20T10:00:00Z", "type": "PET_VISIT"}]
        )
        result = await COMMANDS_BY_NAME["history"].handler(_session(robot), ["10", "--type", "cat"])
        robot.get_activities.assert_awaited_once_with(limit=10, activity_type="PET_VISIT")
        assert result.data["events"][0]["event"] == "Cat visit"

    async def test_equals_form_is_accepted(self):
        robot = _robot(model="LitterRobot5")
        robot.get_activities = AsyncMock(return_value=[])
        await COMMANDS_BY_NAME["history"].handler(_session(robot), ["--type=clean"])
        assert robot.get_activities.await_args.kwargs["activity_type"] == "CYCLE_COMPLETED"

    async def test_filtering_is_refused_on_an_lr4(self):
        with pytest.raises(CommandError) as excinfo:
            await COMMANDS_BY_NAME["history"].handler(_session(), ["--type", "cat"])
        assert "LR5" in str(excinfo.value)
        assert excinfo.value.code == EXIT_COMMAND_REJECTED

    async def test_type_without_a_value_is_a_usage_error(self):
        with pytest.raises(CommandError) as excinfo:
            await COMMANDS_BY_NAME["history"].handler(_session(), ["--type"])
        assert "Usage" in str(excinfo.value)

    async def test_count_still_parses_alongside_the_flag(self):
        robot = _robot(model="LitterRobot5")
        robot.get_activities = AsyncMock(return_value=[])
        await COMMANDS_BY_NAME["history"].handler(_session(robot), ["all", "--type", "cat"])
        assert robot.get_activities.await_args.kwargs["limit"] == 500


class TestNightLightColour:
    async def test_colour_is_normalised_before_it_is_sent(self):
        robot = _robot(model="LitterRobot5")
        robot.set_night_light_settings = AsyncMock(return_value=True)
        result = await COMMANDS_BY_NAME["night-light"].handler(_session(robot), ["color", "ff9e64"])
        assert result.data["ok"] is True
        robot.set_night_light_settings.assert_awaited_once_with(color="#FF9E64")

    async def test_british_spelling_works_too(self):
        robot = _robot(model="LitterRobot5")
        robot.set_night_light_settings = AsyncMock(return_value=True)
        await COMMANDS_BY_NAME["night-light"].handler(_session(robot), ["colour", "#f0a"])
        robot.set_night_light_settings.assert_awaited_once_with(color="#FF00AA")

    async def test_a_bad_colour_never_reaches_the_cloud(self):
        robot = _robot(model="LitterRobot5")
        robot.set_night_light_settings = AsyncMock(return_value=True)
        with pytest.raises(CommandError):
            await COMMANDS_BY_NAME["night-light"].handler(_session(robot), ["color", "burgundy"])
        robot.set_night_light_settings.assert_not_called()

    async def test_colour_on_an_lr4_reports_the_model_limit(self):
        with pytest.raises(CommandError) as excinfo:
            await COMMANDS_BY_NAME["night-light"].handler(_session(), ["color", "#FF9E64"])
        assert "LR5" in str(excinfo.value)

    async def test_the_mode_form_still_works(self):
        session = _session()
        session.robot.set_night_light_mode = AsyncMock(return_value=True)
        result = await COMMANDS_BY_NAME["night-light"].handler(session, ["auto"])
        assert result.data["ok"] is True


class TestSleepScheduleWrites:
    async def test_set_sends_the_window_for_one_day(self):
        robot = _robot(model="LitterRobot5")
        robot.set_sleep_mode = AsyncMock(return_value=True)
        result = await COMMANDS_BY_NAME["sleep-schedule"].handler(
            _session(robot), ["set", "tue", "22:00", "07:00"]
        )
        assert result.data["ok"] is True
        robot.set_sleep_mode.assert_awaited_once_with(True, 1320, wake_time=420, day_of_week=2)

    async def test_set_all_days(self):
        robot = _robot(model="LitterRobot5")
        robot.set_sleep_mode = AsyncMock(return_value=True)
        await COMMANDS_BY_NAME["sleep-schedule"].handler(
            _session(robot), ["set", "all", "22:00", "07:00"]
        )
        assert robot.set_sleep_mode.await_args.kwargs["day_of_week"] is None

    async def test_missing_arguments_are_a_usage_error(self):
        with pytest.raises(CommandError) as excinfo:
            await COMMANDS_BY_NAME["sleep-schedule"].handler(_session(), ["set", "mon"])
        assert "Usage" in str(excinfo.value)

    async def test_an_unreadable_time_is_rejected_locally(self):
        robot = _robot(model="LitterRobot5")
        robot.set_sleep_mode = AsyncMock(return_value=True)
        with pytest.raises(CommandError) as excinfo:
            await COMMANDS_BY_NAME["sleep-schedule"].handler(
                _session(robot), ["set", "all", "bedtime", "07:00"]
            )
        assert "HH:MM" in str(excinfo.value)
        robot.set_sleep_mode.assert_not_called()

    async def test_an_unknown_day_is_rejected_locally(self):
        robot = _robot(model="LitterRobot5")
        robot.set_sleep_mode = AsyncMock(return_value=True)
        with pytest.raises(CommandError) as excinfo:
            await COMMANDS_BY_NAME["sleep-schedule"].handler(
                _session(robot), ["set", "caturday", "22:00", "07:00"]
            )
        assert "Unknown day" in str(excinfo.value)
        robot.set_sleep_mode.assert_not_called()

    async def test_disable_turns_every_day_off(self):
        robot = _robot(model="LitterRobot5")
        robot.set_sleep_mode = AsyncMock(return_value=True)
        result = await COMMANDS_BY_NAME["sleep-schedule"].handler(_session(robot), ["disable"])
        assert "disabled" in result.lines[0]
        robot.set_sleep_mode.assert_awaited_once_with(False)

    async def test_an_unknown_subcommand_explains_the_grammar(self):
        with pytest.raises(CommandError) as excinfo:
            await COMMANDS_BY_NAME["sleep-schedule"].handler(_session(), ["reticulate"])
        assert "Usage" in str(excinfo.value)

    async def test_writing_a_schedule_on_an_lr4_points_at_the_app(self):
        with pytest.raises(CommandError) as excinfo:
            await COMMANDS_BY_NAME["sleep-schedule"].handler(
                _session(), ["set", "all", "22:00", "07:00"]
            )
        assert "Whisker app" in str(excinfo.value)


class TestFilterReminder:
    async def test_info_shows_the_next_filter_date_when_the_model_has_one(self):
        due = datetime.now(timezone.utc) + timedelta(days=23, hours=1)
        robot = _robot(model="LitterRobot5", next_filter_replacement_date=due)
        result = await COMMANDS_BY_NAME["info"].handler(_session(robot), [])
        assert result.data["filter_due"] == f"{due.date().isoformat()} (in 23d)"

    async def test_info_omits_the_row_on_a_model_without_one(self):
        robot = _robot(next_filter_replacement_date=None)
        result = await COMMANDS_BY_NAME["info"].handler(_session(robot), [])
        assert "filter_due" not in result.data
