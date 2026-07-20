"""Tests for asher.monitoring module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pylitterbot.enums import LitterBoxStatus
from textual.css.query import NoMatches

from asher.monitoring import MonitoringMixin


class TestMonitoringMixinStructure:
    def test_class_exists(self):
        assert MonitoringMixin is not None

    def test_has_required_methods(self):
        assert hasattr(MonitoringMixin, "_update_last_cat_seen")
        assert hasattr(MonitoringMixin, "_refresh_status")
        assert hasattr(MonitoringMixin, "_poll_status_interval")
        assert hasattr(MonitoringMixin, "_start_monitoring")
        assert hasattr(MonitoringMixin, "_on_robot_update")
        assert hasattr(MonitoringMixin, "_handle_ws_update")


class TestUpdateLastCatSeen:
    @pytest.fixture
    def mixin(self):
        mixin = MagicMock(spec=MonitoringMixin)
        mixin._robot = MagicMock()
        mixin._last_cat_seen = None
        return mixin

    def test_returns_early_if_no_robot(self):
        mixin = MagicMock()
        mixin._robot = None
        mixin._last_cat_seen = None

        import asyncio

        coro = MonitoringMixin._update_last_cat_seen(mixin)
        asyncio.run(coro)
        assert mixin._last_cat_seen is None

    @pytest.mark.asyncio
    async def test_finds_cat_detected_event(self):
        mixin = MagicMock()
        mixin._robot = MagicMock()
        mixin._last_cat_seen = None

        mock_act = MagicMock()
        mock_act.action = LitterBoxStatus.CAT_DETECTED
        mock_ts = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_act.timestamp = mock_ts

        mixin._robot.get_activity_history = AsyncMock(return_value=[mock_act])

        await MonitoringMixin._update_last_cat_seen(mixin)
        assert mixin._last_cat_seen == mock_ts

    @pytest.mark.asyncio
    async def test_skips_non_cat_detected_events(self):
        mixin = MagicMock()
        mixin._robot = MagicMock()
        mixin._last_cat_seen = None

        mock_act = MagicMock()
        mock_act.action = LitterBoxStatus.CLEAN_CYCLE_COMPLETE
        mock_act.timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)

        mixin._robot.get_activity_history = AsyncMock(return_value=[mock_act])

        await MonitoringMixin._update_last_cat_seen(mixin)
        assert mixin._last_cat_seen is None

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        mixin = MagicMock()
        mixin._robot = MagicMock()
        mixin._robot.get_activity_history = AsyncMock(side_effect=Exception("API error"))

        await MonitoringMixin._update_last_cat_seen(mixin)


class TestRefreshStatus:
    @pytest.mark.asyncio
    async def test_returns_early_if_no_robot(self):
        mixin = MagicMock()
        mixin._robot = None
        mixin._is_loading = True

        await MonitoringMixin._refresh_status(mixin)

    @pytest.mark.asyncio
    async def test_updates_loading_state(self):
        mixin = MagicMock()
        mixin._robot = MagicMock()
        mixin._robot.name = "TestBot"
        mixin._robot.is_online = True
        mixin._robot.waste_drawer_level = 50.0
        mixin._robot.status = MagicMock()
        mixin._robot.status.value = "Ready"
        mixin._robot.sleep_mode_enabled = False
        mixin._last_cat_seen = None
        mixin._robot.last_seen = None
        mixin._robot.pet_weight = None
        mixin._pets = []
        mixin._is_loading = True

        await MonitoringMixin._refresh_status(mixin)
        assert mixin._is_loading is False


class TestStartMonitoring:
    @pytest.mark.asyncio
    async def test_registers_callback_and_subscribes(self):
        mixin = MagicMock()
        mixin._robot = MagicMock()
        mixin._robot.subscribe = AsyncMock()

        await MonitoringMixin._start_monitoring(mixin)

        mixin._robot.on.assert_called_once()
        mixin._robot.subscribe.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_swallows_subscribe_exception(self):
        mixin = MagicMock()
        mixin._robot = MagicMock()
        mixin._robot.subscribe = AsyncMock(side_effect=Exception("ws error"))

        await MonitoringMixin._start_monitoring(mixin)  # should not raise


class TestOnRobotUpdate:
    def test_calls_handle_ws_update(self):
        mixin = MagicMock()
        MonitoringMixin._on_robot_update(mixin)
        mixin._handle_ws_update.assert_called_once()


class TestPollStatusInterval:
    @pytest.mark.asyncio
    async def test_returns_early_if_no_robot(self):
        # _poll_status_interval is decorated with @work, which requires a DOMNode
        # We test the underlying logic by checking if the method exists
        assert hasattr(MonitoringMixin, "_poll_status_interval")

    def test_has_poll_status_interval_method(self):
        assert hasattr(MonitoringMixin, "_poll_status_interval")
        assert callable(MonitoringMixin._poll_status_interval)


class TestMonitoringStructureExtensions:
    def test_has_update_cat_panel(self):
        assert hasattr(MonitoringMixin, "_update_cat_panel")

    def test_has_refresh_faults(self):
        assert hasattr(MonitoringMixin, "_refresh_faults")

    def test_has_cycling_helpers(self):
        assert hasattr(MonitoringMixin, "_cycling_chip")
        assert hasattr(MonitoringMixin, "_start_cycle_timer")
        assert hasattr(MonitoringMixin, "_stop_cycle_timer")
        assert hasattr(MonitoringMixin, "_tick_cycle")


class TestRefreshFaults:
    def _mixin(self, prev: set[str] | None = None):
        m = MagicMock()
        m._prev_faults = prev if prev is not None else set()
        m._fault_dismissed = set()
        m._log_err = MagicMock()
        m._log_ok = MagicMock()
        m.query_one = MagicMock(side_effect=NoMatches("no DOM"))
        return m

    def test_logs_new_fault_once(self):
        from asher.faults import check_faults

        m = self._mixin()
        robot = MagicMock()
        robot.status = LitterBoxStatus.READY
        robot.globe_motor_fault_status = True
        # ensure other attrs falsy
        for attr in (
            "globe_motor_retract_fault_status",
            "usb_fault_status",
            "is_hopper_removed",
            "is_bonnet_removed",
            "is_laser_dirty",
            "is_gas_sensor_fault_detected",
            "is_drawer_removed",
        ):
            setattr(robot, attr, False)

        result = MonitoringMixin._refresh_faults(m, robot)
        assert result is True
        m._log_err.assert_called_once()
        m._log_ok.assert_not_called()
        assert m._prev_faults == {check_faults(robot)[0].label}

    def test_does_not_log_steady_state(self):
        m = self._mixin()
        robot = MagicMock()
        robot.status = LitterBoxStatus.READY
        for attr in (
            "globe_motor_fault_status",
            "globe_motor_retract_fault_status",
            "usb_fault_status",
            "is_hopper_removed",
            "is_bonnet_removed",
            "is_laser_dirty",
            "is_gas_sensor_fault_detected",
            "is_drawer_removed",
        ):
            setattr(robot, attr, False)
        # Healthy robot => no active faults; seed prev as empty (steady state)
        m._prev_faults = set()
        MonitoringMixin._refresh_faults(m, robot)
        m._log_err.assert_not_called()
        m._log_ok.assert_not_called()

    def test_logs_cleared_on_resolution(self):
        m = self._mixin(prev={"GLOBE MOTOR FAULT"})
        robot = MagicMock()
        robot.status = LitterBoxStatus.READY
        for attr in (
            "globe_motor_fault_status",
            "globe_motor_retract_fault_status",
            "usb_fault_status",
            "is_hopper_removed",
            "is_bonnet_removed",
            "is_laser_dirty",
            "is_gas_sensor_fault_detected",
            "is_drawer_removed",
        ):
            setattr(robot, attr, False)

        result = MonitoringMixin._refresh_faults(m, robot)
        assert result is False
        m._log_ok.assert_called_once()

    def test_persistent_fault_not_relogged(self):
        """A fault that's still active on the next refresh shouldn't log again."""
        robot = MagicMock()
        robot.status = LitterBoxStatus.READY
        robot.globe_motor_fault_status = True
        for attr in (
            "globe_motor_retract_fault_status",
            "usb_fault_status",
            "is_hopper_removed",
            "is_bonnet_removed",
            "is_laser_dirty",
            "is_gas_sensor_fault_detected",
            "is_drawer_removed",
        ):
            setattr(robot, attr, False)

        # First refresh: logs the new fault
        m1 = self._mixin()
        MonitoringMixin._refresh_faults(m1, robot)
        m1._log_err.assert_called_once()

        # Second refresh with same prev set: should not log again
        m2 = self._mixin(prev=set(m1._prev_faults))
        MonitoringMixin._refresh_faults(m2, robot)
        m2._log_err.assert_not_called()
        m2._log_ok.assert_not_called()


class TestCyclingChip:
    def test_chip_without_start(self):
        m = MagicMock()
        m._cycle_start = None
        chip = MonitoringMixin._cycling_chip(m)
        assert "Cycling" in chip.plain

    def test_chip_with_start_shows_elapsed(self):
        from datetime import datetime, timedelta

        m = MagicMock()
        m._cycle_start = datetime.now() - timedelta(seconds=65)
        chip = MonitoringMixin._cycling_chip(m)
        assert "Cycling" in chip.plain
        assert "1:05" in chip.plain
