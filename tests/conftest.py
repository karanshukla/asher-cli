"""Shared pytest fixtures."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_robot():
    r = MagicMock()
    r.name = "Test Box"
    r.is_online = True
    r.waste_drawer_level = 42.0
    r.pet_weight = 9.1
    r.status.value = "Ready"
    r.sleeping = False
    r.panel_lockout = False
    r.night_light_mode_enabled = False
    r.serial = "ABC123"
    r.last_seen = datetime.now(timezone.utc)
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
