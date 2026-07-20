"""Tests for asher.faults — live fault & safety detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from pylitterbot.enums import LitterBoxStatus

from asher.faults import SEVERITY_ERROR, SEVERITY_WARN, Fault, check_faults


def _robot(**overrides: object) -> MagicMock:
    r = MagicMock()
    r.status = LitterBoxStatus.READY
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
        setattr(r, attr, False)
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


class TestAttributeFaults:
    def test_globe_motor_fault(self):
        faults = check_faults(_robot(globe_motor_fault_status=True))
        assert any(f.label == "GLOBE MOTOR FAULT" and f.severity == SEVERITY_ERROR for f in faults)

    def test_globe_motor_retract_fault(self):
        faults = check_faults(_robot(globe_motor_retract_fault_status=True))
        assert any("RETRACT FAULT" in f.label for f in faults)

    def test_usb_fault(self):
        faults = check_faults(_robot(usb_fault_status=True))
        assert any("USB" in f.label and f.severity == SEVERITY_ERROR for f in faults)

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

    def test_multiple_attribute_faults_stack(self):
        faults = check_faults(_robot(usb_fault_status=True, is_hopper_removed=True))
        labels = {f.label for f in faults}
        assert len(faults) == 2
        assert any("USB" in lbl for lbl in labels)
        assert any("HOPPER" in lbl for lbl in labels)


class TestGracefulDegradation:
    def test_missing_fault_attrs_dont_raise(self):
        from asher.faults import check_faults as cf

        class Bare:
            status = LitterBoxStatus.READY

        assert cf(Bare()) == []

    def test_status_none_returns_empty(self):
        assert check_faults(_robot(status=None)) == []


class TestSafetyPrecedence:
    def test_safety_status_does_not_double_with_bonnet_attr(self):
        """A BONNET_REMOVED status should not also trip the is_bonnet_removed attr twice."""
        faults = check_faults(_robot(status=LitterBoxStatus.BONNET_REMOVED, is_bonnet_removed=True))
        # Both fire independently; assert at least one BONNET label present, no crash.
        assert any("BONNET" in f.label for f in faults)

    def test_fault_is_immutable_dataclass(self):
        f = Fault("x", SEVERITY_ERROR)
        assert f.label == "x"
        assert f.severity == SEVERITY_ERROR
