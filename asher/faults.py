"""Live robot fault & safety detection.

Pure functions over a robot object — no UI imports, so this is fully
unit-testable. Robust to per-model API differences via ``getattr`` with
defaults: older robots (LR3) and missing attributes simply contribute no
faults rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pylitterbot.enums import LitterBoxStatus

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

# Attribute-driven component faults (won't self-resolve).
_FAULT_ATTRS: tuple[tuple[str, str, str], ...] = (
    ("globe_motor_fault_status", "GLOBE MOTOR FAULT", SEVERITY_ERROR),
    ("globe_motor_retract_fault_status", "GLOBE RETRACT FAULT", SEVERITY_ERROR),
    ("usb_fault_status", "USB POWER FAULT", SEVERITY_ERROR),
    ("is_hopper_removed", "HOPPER REMOVED", SEVERITY_WARN),
    ("is_bonnet_removed", "BONNET OPEN", SEVERITY_WARN),
    ("is_laser_dirty", "LASER SENSOR DIRTY — clean globe", SEVERITY_WARN),
    ("is_gas_sensor_fault_detected", "GAS SENSOR FAULT", SEVERITY_ERROR),
    ("is_drawer_removed", "DRAWER REMOVED", SEVERITY_WARN),
)


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

    for attr, label, severity in _FAULT_ATTRS:
        if getattr(robot, attr, False):
            faults.append(Fault(label, severity))

    return faults
