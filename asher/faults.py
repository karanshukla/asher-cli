"""Live robot fault & safety detection.

Pure functions over a robot object — no UI imports, so this is fully
unit-testable.

Fault detection is **model-scoped**: a fault attribute is only checked on
models for which it is a genuine fault indicator. This mirrors the per-model
adapter pattern in ``robot_adapters.py``. The key reason: several properties
that look like fault flags are actually accessory *state*. The LR4 reports
``is_hopper_removed = True`` when no hopper accessory is fitted — that's a
hardware configuration, not a fault, so reporting it would cry wolf on every
LR4 without the hopper. The same attribute on the LR5 (where the hopper is
standard) would be meaningful, but Whisker exposes it as a state there too,
so it's excluded model-wide rather than risk false positives.

A few pylitterbot fault properties return enums whose healthy sentinels
(``NONE`` / ``FAULT_CLEAR``) are truthy; those are checked against their
known-healthy members rather than via truthiness. Older robots (LR3) and
missing attributes contribute no faults rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pylitterbot.enums import GlobeMotorFaultStatus, LitterBoxStatus

if TYPE_CHECKING:
    from .robot_protocol import RobotProtocol

SEVERITY_ERROR = "error"
SEVERITY_WARN = "warn"

_GLOBE_HEALTHY = frozenset({GlobeMotorFaultStatus.NONE, GlobeMotorFaultStatus.FAULT_CLEAR})


@dataclass(frozen=True)
class Fault:
    label: str
    severity: str


# Status-enum-driven safety states (cycle halted or refused to run). These are
# universal across models, so they're checked first regardless of model.
_SAFETY_STATUSES: dict[LitterBoxStatus, tuple[str, str]] = {
    LitterBoxStatus.CAT_DETECTED: ("CAT DETECTED — cycle halted", SEVERITY_ERROR),
    LitterBoxStatus.CAT_SENSOR_INTERRUPTED: ("CAT SENSOR INTERRUPTED", SEVERITY_ERROR),
    LitterBoxStatus.PINCH_DETECT: ("PINCH DETECT — possible obstruction", SEVERITY_ERROR),
    LitterBoxStatus.STARTUP_PINCH_DETECT: ("PINCH DETECT — possible obstruction", SEVERITY_ERROR),
    LitterBoxStatus.OVER_TORQUE_FAULT: ("OVER-TORQUE — globe blocked or jammed", SEVERITY_WARN),
    LitterBoxStatus.HOME_POSITION_FAULT: ("HOME POSITION FAULT", SEVERITY_ERROR),
    LitterBoxStatus.DUMP_POSITION_FAULT: ("DUMP POSITION FAULT", SEVERITY_ERROR),
    LitterBoxStatus.DUMP_HOME_POSITION_FAULT: ("DUMP POSITION FAULT", SEVERITY_ERROR),
    LitterBoxStatus.BONNET_REMOVED: ("BONNET OPEN", SEVERITY_WARN),
}


@dataclass(frozen=True)
class _EnumCheck:
    attr: str
    label: str
    severity: str
    healthy: frozenset[object]


@dataclass(frozen=True)
class _BoolCheck:
    attr: str
    label: str
    severity: str


# Per-model component-fault allowlists. Only attributes that are genuine fault
# indicators for that model are listed. ``is_hopper_removed`` is deliberately
# absent everywhere — it's accessory state on the LR4 and standard hardware
# state on the LR5, never a fault.
_MODEL_ENUM_FAULTS: dict[str, tuple[_EnumCheck, ...]] = {
    "LitterRobot4": (
        _EnumCheck("globe_motor_fault_status", "GLOBE MOTOR FAULT", SEVERITY_ERROR, _GLOBE_HEALTHY),
        _EnumCheck(
            "globe_motor_retract_fault_status",
            "GLOBE RETRACT FAULT",
            SEVERITY_ERROR,
            _GLOBE_HEALTHY,
        ),
    ),
    "LitterRobot5": (
        _EnumCheck("globe_motor_fault_status", "GLOBE MOTOR FAULT", SEVERITY_ERROR, _GLOBE_HEALTHY),
        _EnumCheck(
            "globe_motor_retract_fault_status",
            "GLOBE RETRACT FAULT",
            SEVERITY_ERROR,
            _GLOBE_HEALTHY,
        ),
    ),
}

_MODEL_BOOL_FAULTS: dict[str, tuple[_BoolCheck, ...]] = {
    # LR3 has no component-fault attributes exposed by pylitterbot.
    "LitterRobot5": (
        _BoolCheck("is_bonnet_removed", "BONNET OPEN", SEVERITY_WARN),
        _BoolCheck("is_laser_dirty", "LASER SENSOR DIRTY — clean globe", SEVERITY_WARN),
        _BoolCheck("is_gas_sensor_fault_detected", "GAS SENSOR FAULT", SEVERITY_ERROR),
        _BoolCheck("is_drawer_removed", "DRAWER REMOVED", SEVERITY_WARN),
    ),
}


def _enum_is_faulty(value: object, healthy: frozenset[object]) -> bool:
    """A fault is active when the enum value is present and not a healthy sentinel."""
    if value is None:
        return False
    return value not in healthy


def check_faults(robot: RobotProtocol | None) -> list[Fault]:
    """Return active faults on ``robot``, safety states first then component faults.

    Component faults are scoped to the robot's model so accessory/state
    attributes (e.g. ``is_hopper_removed`` on the LR4) can't fire as faults.
    Returns an empty list when ``robot`` is ``None``, has no ``status``, or
    none of the fault conditions are met.
    """
    if robot is None:
        return []

    faults: list[Fault] = []

    status = getattr(robot, "status", None)
    safety = _SAFETY_STATUSES.get(status) if status is not None else None
    if safety is not None:
        label, severity = safety
        faults.append(Fault(label, severity))

    model = type(robot).__name__
    for check in _MODEL_ENUM_FAULTS.get(model, ()):
        value = getattr(robot, check.attr, None)
        if _enum_is_faulty(value, check.healthy):
            faults.append(Fault(check.label, check.severity))

    for bool_check in _MODEL_BOOL_FAULTS.get(model, ()):
        if getattr(robot, bool_check.attr, False):
            faults.append(Fault(bool_check.label, bool_check.severity))

    return faults
