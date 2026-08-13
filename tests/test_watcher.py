"""Tests for asher.watcher — alert detection and the supervising watch loop.

``WatchState`` is pure, so most of this file is plain synchronous assertions
over fake robots. The async tests drive :func:`asher.watcher.watch` with
``open_session`` patched out — no network, no pylitterbot session, no Textual.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pylitterbot.enums import LitterBoxStatus

from asher import config, watcher
from asher.export import EXIT_OK
from asher.watcher import Alert, WatchState, deliver, snapshot


class FakeRobot:
    """Minimal stand-in for a pylitterbot robot.

    Named ``FakeRobot`` deliberately: ``check_faults`` scopes component faults
    by ``type(robot).__name__``, so an unrecognised class name exercises the
    status-driven safety faults that every model shares.
    """

    def __init__(
        self,
        *,
        name: str = "Asher",
        status: Any = LitterBoxStatus.READY,
        waste_drawer_level: float | None = 10.0,
        is_online: bool = True,
    ) -> None:
        self.name = name
        self.status = status
        self.waste_drawer_level = waste_drawer_level
        self.is_online = is_online


# ── WatchState: faults ───────────────────────────────────────────────────────


class TestFaultAlerts:
    def test_alerts_on_a_fault_present_at_startup(self) -> None:
        state = WatchState()
        alerts = state.evaluate(FakeRobot(status=LitterBoxStatus.CAT_DETECTED))
        assert [alert.message for alert in alerts] == ["CAT DETECTED — cycle halted"]

    def test_does_not_repeat_a_standing_fault(self) -> None:
        state = WatchState()
        robot = FakeRobot(status=LitterBoxStatus.CAT_DETECTED)
        state.evaluate(robot)
        assert state.evaluate(robot) == []

    def test_alerts_when_a_fault_clears(self) -> None:
        state = WatchState()
        robot = FakeRobot(status=LitterBoxStatus.CAT_DETECTED)
        state.evaluate(robot)
        robot.status = LitterBoxStatus.READY
        assert [alert.message for alert in state.evaluate(robot)] == [
            "Cleared: CAT DETECTED — cycle halted"
        ]

    def test_error_severity_is_critical(self) -> None:
        alerts = WatchState().evaluate(FakeRobot(status=LitterBoxStatus.CAT_DETECTED))
        assert alerts[0].critical is True

    def test_warn_severity_is_not_critical(self) -> None:
        alerts = WatchState().evaluate(FakeRobot(status=LitterBoxStatus.BONNET_REMOVED))
        assert alerts[0].critical is False

    def test_title_carries_the_robot_name(self) -> None:
        alerts = WatchState().evaluate(
            FakeRobot(name="Litter Box", status=LitterBoxStatus.CAT_DETECTED)
        )
        assert alerts[0].title == "Asher — Litter Box"

    def test_healthy_robot_produces_nothing(self) -> None:
        assert WatchState().evaluate(FakeRobot()) == []


# ── WatchState: drawer ───────────────────────────────────────────────────────


class TestDrawerAlerts:
    def test_alerts_when_crossing_the_threshold(self) -> None:
        state = WatchState(drawer_threshold=85.0)
        state.evaluate(FakeRobot(waste_drawer_level=80.0))
        alerts = state.evaluate(FakeRobot(waste_drawer_level=90.0))
        assert [alert.message for alert in alerts] == ["Waste drawer 90% full"]

    def test_alerts_when_already_over_at_startup(self) -> None:
        alerts = WatchState(drawer_threshold=85.0).evaluate(FakeRobot(waste_drawer_level=95.0))
        assert [alert.message for alert in alerts] == ["Waste drawer 95% full"]

    def test_does_not_repeat_while_still_full(self) -> None:
        state = WatchState(drawer_threshold=85.0)
        state.evaluate(FakeRobot(waste_drawer_level=90.0))
        assert state.evaluate(FakeRobot(waste_drawer_level=92.0)) == []

    def test_re_alerts_after_the_drawer_is_emptied(self) -> None:
        state = WatchState(drawer_threshold=85.0)
        state.evaluate(FakeRobot(waste_drawer_level=90.0))
        state.evaluate(FakeRobot(waste_drawer_level=5.0))
        alerts = state.evaluate(FakeRobot(waste_drawer_level=88.0))
        assert [alert.message for alert in alerts] == ["Waste drawer 88% full"]

    def test_suppressed_once_the_robot_reports_drawer_full(self) -> None:
        """The fault path already alerts; two toasts for one drawer is one too many."""
        alerts = WatchState(drawer_threshold=85.0).evaluate(
            FakeRobot(waste_drawer_level=100.0, status=LitterBoxStatus.DRAWER_FULL)
        )
        assert [alert.message for alert in alerts] == ["DRAWER FULL — empty now"]

    def test_missing_level_is_not_an_alert(self) -> None:
        assert WatchState().evaluate(FakeRobot(waste_drawer_level=None)) == []


# ── WatchState: connectivity ─────────────────────────────────────────────────


class TestConnectivityAlerts:
    def test_first_evaluation_never_announces_connectivity(self) -> None:
        assert WatchState().evaluate(FakeRobot(is_online=False)) == []

    def test_going_offline_alerts(self) -> None:
        state = WatchState()
        state.evaluate(FakeRobot(is_online=True))
        alerts = state.evaluate(FakeRobot(is_online=False))
        assert [(alert.message, alert.critical) for alert in alerts] == [("Went offline", True)]

    def test_coming_back_alerts(self) -> None:
        state = WatchState()
        state.evaluate(FakeRobot(is_online=True))
        state.evaluate(FakeRobot(is_online=False))
        alerts = state.evaluate(FakeRobot(is_online=True))
        assert [(alert.message, alert.critical) for alert in alerts] == [("Back online", False)]

    def test_staying_online_is_silent(self) -> None:
        state = WatchState()
        state.evaluate(FakeRobot())
        assert state.evaluate(FakeRobot()) == []


# ── snapshot ─────────────────────────────────────────────────────────────────


class TestSnapshot:
    def test_renders_display_strings(self) -> None:
        result = snapshot(FakeRobot(name="Asher", waste_drawer_level=42.4))
        assert result.name == "Asher"
        assert result.drawer == "42%"
        assert result.online is True
        assert result.faulted is False

    def test_flags_a_faulted_robot(self) -> None:
        assert snapshot(FakeRobot(status=LitterBoxStatus.CAT_DETECTED)).faulted is True

    def test_missing_values_degrade(self) -> None:
        result = snapshot(FakeRobot(status=None, waste_drawer_level=None, is_online=False))
        assert (result.status, result.drawer, result.online) == ("—", "—", False)


# ── deliver ──────────────────────────────────────────────────────────────────


class TestDeliver:
    def test_fires_a_toast_when_enabled(self) -> None:
        with (
            patch.object(config, "load", return_value={"notifications": True}),
            patch("asher.notifications.fire") as fire,
        ):
            deliver(Alert("Asher — Cat", "DRAWER FULL"))
        fire.assert_called_once_with("Asher — Cat", "DRAWER FULL")

    def test_silent_when_notifications_are_off(self) -> None:
        with (
            patch.object(config, "load", return_value={"notifications": False}),
            patch("asher.notifications.fire") as fire,
        ):
            deliver(Alert("Asher — Cat", "DRAWER FULL"))
        fire.assert_not_called()

    def test_beeps_only_when_sound_is_on(self) -> None:
        settings = {"notifications": True, "notification_sound": True}
        with (
            patch.object(config, "load", return_value=settings),
            patch("asher.notifications.fire"),
            patch("asher.notifications.beep") as beep,
        ):
            deliver(Alert("Asher — Cat", "CAT DETECTED", critical=True))
        beep.assert_called_once_with(critical=True)


# ── _wait_for_change ─────────────────────────────────────────────────────────


class TestWaitForChange:
    async def test_returns_true_when_an_update_arrives(self) -> None:
        updated, stop = asyncio.Event(), asyncio.Event()
        updated.set()
        assert await watcher._wait_for_change(updated, stop, timeout=5) is True

    async def test_returns_false_on_timeout(self) -> None:
        updated, stop = asyncio.Event(), asyncio.Event()
        assert await watcher._wait_for_change(updated, stop, timeout=0.01) is False

    async def test_returns_true_when_asked_to_stop(self) -> None:
        updated, stop = asyncio.Event(), asyncio.Event()
        stop.set()
        assert await watcher._wait_for_change(updated, stop, timeout=5) is True


# ── watch ────────────────────────────────────────────────────────────────────


def _fake_session(robot: FakeRobot) -> MagicMock:
    session = MagicMock()
    session.robot = robot
    robot.on = MagicMock()  # type: ignore[attr-defined]
    robot.subscribe = AsyncMock()  # type: ignore[attr-defined]
    robot.unsubscribe = AsyncMock()  # type: ignore[attr-defined]
    robot.refresh = AsyncMock()  # type: ignore[attr-defined]
    session.account.disconnect = AsyncMock()
    return session


class TestWatch:
    async def test_stops_immediately_when_already_asked_to(self) -> None:
        stop = asyncio.Event()
        stop.set()
        with patch("asher.headless.open_session") as open_session:
            code = await watcher.watch(stop_event=stop, log=lambda _: None)
        assert code == EXIT_OK
        open_session.assert_not_called()

    async def test_delivers_alerts_from_the_first_evaluation(self) -> None:
        robot = FakeRobot(status=LitterBoxStatus.CAT_DETECTED)
        stop = asyncio.Event()
        alerts: list[Alert] = []

        with patch("asher.headless.open_session", AsyncMock(return_value=_fake_session(robot))):
            code = await watcher.watch(
                stop_event=stop,
                on_alert=alerts.append,
                on_status=lambda _: stop.set(),
                log=lambda _: None,
            )

        assert code == EXIT_OK
        assert [alert.message for alert in alerts] == ["CAT DETECTED — cycle halted"]

    async def test_reports_the_session_to_the_caller(self) -> None:
        robot = FakeRobot()
        session = _fake_session(robot)
        stop = asyncio.Event()
        seen: list[Any] = []

        with patch("asher.headless.open_session", AsyncMock(return_value=session)):
            await watcher.watch(
                stop_event=stop,
                on_session=seen.append,
                on_status=lambda _: stop.set(),
                log=lambda _: None,
            )

        assert seen == [session]

    async def test_closes_the_session_on_the_way_out(self) -> None:
        robot = FakeRobot()
        session = _fake_session(robot)
        stop = asyncio.Event()

        with patch("asher.headless.open_session", AsyncMock(return_value=session)):
            await watcher.watch(stop_event=stop, on_status=lambda _: stop.set(), log=lambda _: None)

        robot.unsubscribe.assert_awaited()  # type: ignore[attr-defined]
        session.account.disconnect.assert_awaited()

    async def test_missing_credentials_end_the_watcher(self) -> None:
        """Nothing about waiting makes credentials appear, so this must not retry."""
        from asher.connection import HeadlessAuthError

        with patch(
            "asher.headless.open_session", AsyncMock(side_effect=HeadlessAuthError("nope", 1))
        ):
            code = await watcher.watch(stop_event=asyncio.Event(), log=lambda _: None)
        assert code == 1

    async def test_an_unreachable_cloud_is_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A watcher started at login often beats the network there."""
        from asher.connection import HeadlessAuthError

        monkeypatch.setattr(watcher, "_INITIAL_BACKOFF_SECONDS", 0.01)
        stop = asyncio.Event()
        attempts: list[int] = []

        async def unreachable(_selector: str | None) -> MagicMock:
            attempts.append(1)
            if len(attempts) < 3:
                raise HeadlessAuthError("Connection failed: no route to host", 2)
            stop.set()
            return _fake_session(FakeRobot())

        with patch("asher.headless.open_session", unreachable):
            code = await watcher.watch(stop_event=stop, log=lambda _: None)

        assert code == EXIT_OK
        assert len(attempts) == 3

    async def test_a_cloud_failure_is_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(watcher, "_INITIAL_BACKOFF_SECONDS", 0.01)
        stop = asyncio.Event()
        attempts: list[int] = []

        async def flaky(_selector: str | None) -> MagicMock:
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("cloud down")
            stop.set()
            return _fake_session(FakeRobot())

        with patch("asher.headless.open_session", flaky):
            code = await watcher.watch(stop_event=stop, log=lambda _: None)

        assert code == EXIT_OK
        assert len(attempts) == 3

    async def test_state_survives_a_reconnect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A blip must not re-announce faults the user was already told about."""
        monkeypatch.setattr(watcher, "_INITIAL_BACKOFF_SECONDS", 0.01)
        robot = FakeRobot(status=LitterBoxStatus.CAT_DETECTED)
        stop = asyncio.Event()
        alerts: list[Alert] = []
        sessions = 0

        async def reconnecting(_selector: str | None) -> MagicMock:
            nonlocal sessions
            sessions += 1
            return _fake_session(robot)

        def on_status(_snapshot: Any) -> None:
            if sessions >= 2:
                stop.set()
                return
            raise RuntimeError("connection dropped")

        with patch("asher.headless.open_session", reconnecting):
            await watcher.watch(
                stop_event=stop, on_alert=alerts.append, on_status=on_status, log=lambda _: None
            )

        assert [alert.message for alert in alerts] == ["CAT DETECTED — cycle halted"]


# ── WatcherRunner ────────────────────────────────────────────────────────────


class TestWatcherRunner:
    def test_runs_and_stops_on_a_background_thread(self) -> None:
        robot = FakeRobot()
        with patch("asher.headless.open_session", AsyncMock(return_value=_fake_session(robot))):
            runner = watcher.WatcherRunner(log=lambda _: None)
            runner.start()
            runner.request_stop()
            runner.join(timeout=10)
        assert runner.finished.is_set()
        assert runner.exit_code == EXIT_OK

    def test_call_reports_when_there_is_no_session_yet(self) -> None:
        runner = watcher.WatcherRunner(log=lambda _: None)
        assert runner.call(lambda session: session.robot.start_cleaning()) is False

    def test_request_stop_is_safe_before_start(self) -> None:
        watcher.WatcherRunner(log=lambda _: None).request_stop()  # must not raise
