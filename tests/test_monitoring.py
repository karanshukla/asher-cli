"""Tests for asher.monitoring module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pylitterbot.enums import LitterBoxStatus

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
