"""Live robot fault & safety detection.

Pure functions over a robot object — no UI imports, so this is fully
unit-testable. Robust to per-model API differences via ``getattr`` with
defaults: older robots (LR3) and missing attributes simply contribute no
faults rather than raising.

Note that several pylitterbot fault properties return enums (not booleans)
where the "no fault" state is a sentinel member like ``NONE`` / ``CLEAR`` /
``FAULT_CLEAR``. Such enums are truthy even when healthy, so each must be
checked against its known-healthy members rather than via truthiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pylitterbot.enums import GlobeMotorFaultStatus, LitterBoxStatus

if TYPE_CHECKING:
    from .robot_protocol import RobotProtocol

SEVERITY_ERROR = "error"
SEVERITY_WARN = "warn"


@dataclass(frozen=True)
class Fault:
    label: str
    severity: str


# Status-enum-driven safety states (cycle halted or refused to run).
# Checked first — they take precedence over attribute-driven faults.
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

# Enum-valued component fault properties. Each maps (property name) ->
# (label, severity, set-of-healthy-members). A fault is reported only when
# the current value is not one of the healthy members.
# Healthy sentinels are members of the actual pylitterbot enums so they stay
# correct across versions (e.g. NONE / FAULT_CLEAR / CLEAR).
_ENUM_FAULTS: tuple[tuple[str, str, str, frozenset[object]], ...] = (
    (
        "globe_motor_fault_status",
        "GLOBE MOTOR FAULT",
        SEVERITY_ERROR,
        frozenset({GlobeMotorFaultStatus.NONE, GlobeMotorFaultStatus.FAULT_CLEAR}),
    ),
    (
        "globe_motor_retract_fault_status",
        "GLOBE RETRACT FAULT",
        SEVERITY_ERROR,
        frozenset({GlobeMotorFaultStatus.NONE, GlobeMotorFaultStatus.FAULT_CLEAR}),
    ),
)

# Boolean-valued component faults (won't self-resolve). ``getattr(..., False)``
# is safe here because these properties genuinely return bool. LR5-only attrs
# degrade to False on LR3/LR4 via getattr. Drawer-full is intentionally
# excluded — it's already surfaced via the DRAWER_FULL status enum and the
# drawer-% cat mode, so including it here would double-report.
_BOOL_FAULTS: tuple[tuple[str, str, str], ...] = (
    ("is_hopper_removed", "HOPPER REMOVED", SEVERITY_WARN),
    ("is_bonnet_removed", "BONNET OPEN", SEVERITY_WARN),
    ("is_laser_dirty", "LASER SENSOR DIRTY — clean globe", SEVERITY_WARN),
    ("is_gas_sensor_fault_detected", "GAS SENSOR FAULT", SEVERITY_ERROR),
    ("is_drawer_removed", "DRAWER REMOVED", SEVERITY_WARN),
)


def _enum_is_faulty(value: object, healthy: frozenset[object]) -> bool:
    """A fault is active when the enum value is present and not a healthy sentinel."""
    if value is None:
        return False
    return value not in healthy


def check_faults(robot: RobotProtocol | None) -> list[Fault]:
    """Return active faults on ``robot``, safety states first then component faults.

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

    for attr, label, severity, healthy in _ENUM_FAULTS:
        value = getattr(robot, attr, None)
        if _enum_is_faulty(value, healthy):
            faults.append(Fault(label, severity))

    for attr, label, severity in _BOOL_FAULTS:
        if getattr(robot, attr, False):
            faults.append(Fault(label, severity))

    return faults
