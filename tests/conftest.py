"""Shared pytest fixtures."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_robot():
    from pylitterbot.enums import GlobeMotorFaultStatus, LitterBoxStatus

    # Named subclass so type(r).__name__ == "LitterRobot4" (check_faults dispatch).
    lr4_cls = type("LitterRobot4", (MagicMock,), {})
    r = lr4_cls()
    r.name = "Test Box"
    r.is_online = True
    r.waste_drawer_level = 42.0
    r.pet_weight = 9.1
    r.status = LitterBoxStatus.READY
    r.sleep_mode_enabled = False
    r.panel_lock_enabled = False
    r.night_light_mode_enabled = False
    r.serial = "ABC123"
    r.last_seen = datetime.now(timezone.utc)
    # Fault sources in their healthy/no-fault state (enums are truthy even
    # when healthy, so they must be set explicitly to avoid false positives).
    r.globe_motor_fault_status = GlobeMotorFaultStatus.NONE
    r.globe_motor_retract_fault_status = GlobeMotorFaultStatus.NONE
    r.is_hopper_removed = False
    r.is_bonnet_removed = False
    r.is_laser_dirty = False
    r.is_gas_sensor_fault_detected = False
    r.is_drawer_removed = False
    r.refresh = AsyncMock()
    r.start_cleaning = AsyncMock(return_value=True)
    r.set_panel_lockout = AsyncMock(return_value=True)
    r.set_sleep_mode = AsyncMock(return_value=True)
    r.get_activity_history = AsyncMock(return_value=[])
    return r


@pytest.fixture
def mock_account(mock_robot):
    a = MagicMock()
    a.robots = [mock_robot]
    a.pets = []
    a.connect = AsyncMock()
    a.disconnect = AsyncMock()
    return a
