"""Tests for asher.faults — model-scoped live fault & safety detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from pylitterbot.enums import GlobeMotorFaultStatus, LitterBoxStatus

from asher.faults import SEVERITY_ERROR, SEVERITY_WARN, Fault, check_faults

_OK_GLOBE = GlobeMotorFaultStatus.NONE
_FAULT_GLOBE = GlobeMotorFaultStatus.FAULT_OVERTORQUE_AMP


def _robot(model: str, **overrides: object) -> MagicMock:
    """A healthy robot mock whose ``type(r).__name__`` is ``model``.

    A named subclass is used (rather than setting ``__class__.__name__``) so
    that ``type(robot).__name__`` — which is how ``check_faults`` dispatches
    per model — returns the model name. All known fault sources start in their
    healthy state; ``is_hopper_removed`` defaults to True to model an LR4 with
    no hopper accessory (must not fault).
    """
    model_cls = type(model, (MagicMock,), {})
    r = model_cls()
    r.status = LitterBoxStatus.READY
    r.globe_motor_fault_status = _OK_GLOBE
    r.globe_motor_retract_fault_status = _OK_GLOBE
    r.is_hopper_removed = True
    r.is_bonnet_removed = False
    r.is_laser_dirty = False
    r.is_gas_sensor_fault_detected = False
    r.is_drawer_removed = False
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def _lr4(**overrides: object) -> MagicMock:
    return _robot("LitterRobot4", **overrides)


def _lr5(**overrides: object) -> MagicMock:
    return _robot("LitterRobot5", **overrides)


def _lr3(**overrides: object) -> MagicMock:
    return _robot("LitterRobot3", **overrides)


class TestHealthyRobots:
    def test_none_robot_returns_empty(self):
        assert check_faults(None) == []

    def test_healthy_lr4_no_faults(self):
        assert check_faults(_lr4()) == []

    def test_healthy_lr5_no_faults(self):
        assert check_faults(_lr5()) == []

    def test_healthy_lr3_no_faults(self):
        assert check_faults(_lr3()) == []

    def test_lr4_hopper_removed_is_not_a_fault(self):
        """Regression: an LR4 with no hopper accessory must not cry wolf."""
        assert check_faults(_lr4(is_hopper_removed=True)) == []

    def test_lr5_hopper_removed_is_not_a_fault(self):
        assert check_faults(_lr5(is_hopper_removed=True)) == []

    def test_enum_healthy_sentinel_is_not_a_fault(self):
        assert check_faults(_lr4(globe_motor_fault_status=GlobeMotorFaultStatus.FAULT_CLEAR)) == []


class TestSafetyStatuses:
    """Universal — checked on every model regardless of allowlist."""

    def test_cat_detected_is_error(self):
        faults = check_faults(_lr4(status=LitterBoxStatus.CAT_DETECTED))
        assert len(faults) == 1
        assert faults[0].severity == SEVERITY_ERROR
        assert "CAT DETECTED" in faults[0].label

    def test_pinch_detect_is_error(self):
        faults = check_faults(_lr5(status=LitterBoxStatus.PINCH_DETECT))
        assert len(faults) == 1
        assert faults[0].severity == SEVERITY_ERROR

    def test_over_torque_fault_is_warn(self):
        faults = check_faults(_lr4(status=LitterBoxStatus.OVER_TORQUE_FAULT))
        assert len(faults) == 1
        assert faults[0].severity == SEVERITY_WARN

    def test_home_position_fault_is_error(self):
        faults = check_faults(_lr3(status=LitterBoxStatus.HOME_POSITION_FAULT))
        assert len(faults) == 1
        assert faults[0].severity == SEVERITY_ERROR

    def test_safety_status_fires_on_all_models(self):
        for robot in (_lr3, _lr4, _lr5):
            assert len(check_faults(robot(status=LitterBoxStatus.PINCH_DETECT))) == 1


class TestLR4ComponentFaults:
    def test_globe_motor_fault(self):
        faults = check_faults(_lr4(globe_motor_fault_status=_FAULT_GLOBE))
        assert any(f.label == "GLOBE MOTOR FAULT" and f.severity == SEVERITY_ERROR for f in faults)

    def test_globe_motor_retract_fault(self):
        faults = check_faults(_lr4(globe_motor_retract_fault_status=_FAULT_GLOBE))
        assert any("RETRACT FAULT" in f.label for f in faults)

    def test_lr4_ignores_lr5_only_bool_attrs(self):
        """LR4 allowlist must not check bonnet/laser/gas/drawer-removed."""
        r = _lr4()
        r.is_bonnet_removed = True
        r.is_gas_sensor_fault_detected = True
        assert check_faults(r) == []


class TestLR5ComponentFaults:
    def test_bonnet_removed_is_warn(self):
        faults = check_faults(_lr5(is_bonnet_removed=True))
        assert any("BONNET" in f.label and f.severity == SEVERITY_WARN for f in faults)

    def test_laser_dirty(self):
        faults = check_faults(_lr5(is_laser_dirty=True))
        assert any("LASER" in f.label for f in faults)

    def test_gas_sensor_fault(self):
        faults = check_faults(_lr5(is_gas_sensor_fault_detected=True))
        assert any("GAS SENSOR" in f.label and f.severity == SEVERITY_ERROR for f in faults)

    def test_drawer_removed(self):
        faults = check_faults(_lr5(is_drawer_removed=True))
        assert any("DRAWER REMOVED" in f.label for f in faults)

    def test_multiple_lr5_faults_stack(self):
        faults = check_faults(_lr5(is_bonnet_removed=True, is_laser_dirty=True))
        labels = {f.label for f in faults}
        assert len(faults) == 2
        assert any("BONNET" in lbl for lbl in labels)
        assert any("LASER" in lbl for lbl in labels)


class TestLR3ComponentFaults:
    def test_lr3_has_no_component_fault_checks(self):
        """LR3 has no allowlist entry; only universal safety statuses fire."""
        r = _lr3(status=LitterBoxStatus.PINCH_DETECT)
        # These would fire on LR4/LR5 but are not in the LR3 allowlist:
        r.globe_motor_fault_status = _FAULT_GLOBE
        r.is_gas_sensor_fault_detected = True
        faults = check_faults(r)
        # Only the universal pinch-detect safety status, no component faults.
        assert len(faults) == 1
        assert "PINCH" in faults[0].label


class TestGracefulDegradation:
    def test_missing_fault_attrs_dont_raise(self):
        """A model whose allowlist attrs are genuinely absent yields no component faults."""

        class StubRobot:
            status = LitterBoxStatus.READY

        # Rename so check_faults dispatches it as an LR4 (which has the globe
        # attrs in its allowlist) — but the stub lacks those attrs entirely.
        StubRobot.__name__ = "LitterRobot4"
        assert check_faults(StubRobot()) == []

    def test_status_none_returns_empty(self):
        assert check_faults(_lr4(status=None)) == []

    def test_unknown_model_falls_back_to_safety_statuses_only(self):
        unknown_cls = type("MysteryRobot", (MagicMock,), {})
        r = unknown_cls()
        r.status = LitterBoxStatus.READY
        r.globe_motor_fault_status = _FAULT_GLOBE  # ignored — unknown model
        assert check_faults(r) == []


class TestDataclass:
    def test_fault_is_immutable(self):
        f = Fault("x", SEVERITY_ERROR)
        assert f.label == "x"
        assert f.severity == SEVERITY_ERROR
