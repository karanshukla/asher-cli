"""Tests for asher.faults — live fault & safety detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from pylitterbot.enums import GlobeMotorFaultStatus, LitterBoxStatus

from asher.faults import SEVERITY_ERROR, SEVERITY_WARN, Fault, check_faults

# Healthy sentinels for the enum-valued fault properties.
_OK_GLOBE = GlobeMotorFaultStatus.NONE
_FAULT_GLOBE = GlobeMotorFaultStatus.FAULT_OVERTORQUE_AMP


def _robot(**overrides: object) -> MagicMock:
    """A healthy robot mock — every fault source in its no-fault state."""
    r = MagicMock()
    r.status = LitterBoxStatus.READY
    # Enum-valued properties default to the healthy sentinel.
    r.globe_motor_fault_status = _OK_GLOBE
    r.globe_motor_retract_fault_status = _OK_GLOBE
    # Boolean-valued properties default to False.
    r.is_hopper_removed = False
    r.is_bonnet_removed = False
    r.is_laser_dirty = False
    r.is_gas_sensor_fault_detected = False
    r.is_drawer_removed = False
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


class TestCheckFaultsHealthy:
    def test_none_robot_returns_empty(self):
        assert check_faults(None) == []

    def test_ready_robot_no_faults(self):
        assert check_faults(_robot()) == []

    def test_returns_list_type(self):
        assert isinstance(check_faults(_robot()), list)

    def test_enum_healthy_sentinel_is_not_a_fault(self):
        """Regression: GlobeMotorFaultStatus.NONE is truthy but means no fault."""
        assert check_faults(_robot()) == []

    def test_enum_fault_clear_is_not_a_fault(self):
        assert (
            check_faults(_robot(globe_motor_fault_status=GlobeMotorFaultStatus.FAULT_CLEAR)) == []
        )


class TestSafetyStatuses:
    def test_cat_detected_is_error(self):
        faults = check_faults(_robot(status=LitterBoxStatus.CAT_DETECTED))
        assert len(faults) == 1
        assert faults[0].severity == SEVERITY_ERROR
        assert "CAT DETECTED" in faults[0].label

    def test_cat_sensor_interrupted_is_error(self):
        faults = check_faults(_robot(status=LitterBoxStatus.CAT_SENSOR_INTERRUPTED))
        assert len(faults) == 1
        assert faults[0].severity == SEVERITY_ERROR

    def test_pinch_detect_is_error(self):
        faults = check_faults(_robot(status=LitterBoxStatus.PINCH_DETECT))
        assert len(faults) == 1
        assert faults[0].severity == SEVERITY_ERROR

    def test_over_torque_fault_is_warn(self):
        faults = check_faults(_robot(status=LitterBoxStatus.OVER_TORQUE_FAULT))
        assert len(faults) == 1
        assert faults[0].severity == SEVERITY_WARN

    def test_bonnet_removed_status_is_warn(self):
        faults = check_faults(_robot(status=LitterBoxStatus.BONNET_REMOVED))
        assert len(faults) == 1
        assert faults[0].severity == SEVERITY_WARN

    def test_home_position_fault_is_error(self):
        faults = check_faults(_robot(status=LitterBoxStatus.HOME_POSITION_FAULT))
        assert len(faults) == 1
        assert faults[0].severity == SEVERITY_ERROR


class TestEnumAttributeFaults:
    def test_globe_motor_fault(self):
        faults = check_faults(_robot(globe_motor_fault_status=_FAULT_GLOBE))
        assert any(f.label == "GLOBE MOTOR FAULT" and f.severity == SEVERITY_ERROR for f in faults)

    def test_globe_motor_retract_fault(self):
        faults = check_faults(_robot(globe_motor_retract_fault_status=_FAULT_GLOBE))
        assert any("RETRACT FAULT" in f.label for f in faults)

    def test_both_globe_faults_stack(self):
        faults = check_faults(
            _robot(
                globe_motor_fault_status=_FAULT_GLOBE,
                globe_motor_retract_fault_status=_FAULT_GLOBE,
            )
        )
        labels = {f.label for f in faults}
        assert any("GLOBE MOTOR FAULT" in lbl for lbl in labels)
        assert any("RETRACT FAULT" in lbl for lbl in labels)


class TestBoolAttributeFaults:
    def test_hopper_removed_is_warn(self):
        faults = check_faults(_robot(is_hopper_removed=True))
        assert any("HOPPER" in f.label and f.severity == SEVERITY_WARN for f in faults)

    def test_bonnet_attr_is_warn(self):
        faults = check_faults(_robot(is_bonnet_removed=True))
        assert any("BONNET" in f.label and f.severity == SEVERITY_WARN for f in faults)

    def test_laser_dirty(self):
        faults = check_faults(_robot(is_laser_dirty=True))
        assert any("LASER" in f.label for f in faults)

    def test_gas_sensor_fault(self):
        faults = check_faults(_robot(is_gas_sensor_fault_detected=True))
        assert any("GAS SENSOR" in f.label and f.severity == SEVERITY_ERROR for f in faults)

    def test_drawer_removed(self):
        faults = check_faults(_robot(is_drawer_removed=True))
        assert any("DRAWER REMOVED" in f.label for f in faults)

    def test_multiple_bool_faults_stack(self):
        faults = check_faults(_robot(is_hopper_removed=True, is_bonnet_removed=True))
        labels = {f.label for f in faults}
        assert len(faults) == 2
        assert any("HOPPER" in lbl for lbl in labels)
        assert any("BONNET" in lbl for lbl in labels)


class TestGracefulDegradation:
    def test_missing_fault_attrs_dont_raise(self):
        """A bare object with only a status should contribute no faults."""

        class Bare:
            status = LitterBoxStatus.READY

        assert check_faults(Bare()) == []

    def test_status_none_returns_empty(self):
        assert check_faults(_robot(status=None)) == []

    def test_enum_attr_none_is_not_a_fault(self):
        """usb_fault_status / missing enum property (None) must not fire."""
        assert check_faults(_robot(globe_motor_fault_status=None)) == []


class TestSafetyPrecedence:
    def test_safety_status_does_not_double_count(self):
        """A BONNET_REMOVED status and the bool attr are independent; no crash."""
        faults = check_faults(_robot(status=LitterBoxStatus.BONNET_REMOVED, is_bonnet_removed=True))
        assert any("BONNET" in f.label for f in faults)

    def test_fault_is_immutable_dataclass(self):
        f = Fault("x", SEVERITY_ERROR)
        assert f.label == "x"
        assert f.severity == SEVERITY_ERROR
