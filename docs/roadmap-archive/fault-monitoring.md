# §9 — Fault monitoring & alerts ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §9. The original section text, preserved verbatim.

Live fault detection lives in `asher/faults.py` (`check_faults(robot)`), called
from `MonitoringMixin._refresh_faults` on every status refresh (WebSocket push
+ poll). Detection is **model-scoped** — each model only checks the component
attributes that are genuine fault indicators for it (mirrors the adapter
pattern in `robot_adapters.py`):

- **LR4** — globe motor + retract faults only
- **LR5** — globe motor + retract + bonnet + laser + gas sensor + drawer-removed
- **LR3** — no component checks (pylitterbot exposes none)

`is_hopper_removed` is **never** treated as a fault: on the LR4 it's `True`
when no hopper accessory is fitted (a hardware configuration, not a fault),
and on the LR5 it's standard hardware state. Universal safety statuses (cat
detected, pinch, over-torque, position faults) are checked on every model.
Enum-valued properties (`GlobeMotorFaultStatus`) are checked against their
healthy sentinels (`NONE` / `FAULT_CLEAR`) since the enums are truthy even
when healthy. Faults surface via a `#fault-banner` widget inside the cat panel,
beneath the status badges — hidden by default, red for `error`, amber for
`warn`. Transitions are logged (`_log_err` new / `_log_ok` cleared) but
steady-state faults don't flood the log. While a fault is active the cat
panel switches to `error` mode. Press `d` to dismiss the banner until the set
of active faults changes.

### 9a. Safety events (highest priority — surface immediately)

These indicate the robot stopped mid-cycle or refused to run for a safety reason.
They're not hardware faults; they're expected protective states that the user
needs to act on.

| Property / Status | Meaning | Urgency |
|---|---|---|
| `LitterBoxStatus.CAT_DETECTED` | Cat entered globe during or before a cycle — robot halted | 🔴 red banner |
| `LitterBoxStatus.CAT_SENSOR_INTERRUPTED` | Cat sensor tripped mid-cycle (pinch risk) | 🔴 red banner |
| `LitterBoxStatus.PINCH_DETECT` | Motor detected resistance (possible obstruction or cat limb) | 🔴 red banner |
| `is_cat_detected` | Boolean shorthand for the cat-sensor trip state | same |
| `LitterBoxStatus.TIMING_FAULT` | Cycle took too long — globe may be stuck | 🟠 amber banner |
| `LitterBoxStatus.OVER_TORQUE_FAULT` | Motor drew too much current — globe blocked or jammed | 🟠 amber banner |

**Cat detected / pinch** should also trigger:
- Log entry: `⚠ Cat detected — cycle halted at HH:MM`
- Cat animation switched to `"alert"` mode (new state, blinking/urgent art)
- Auto-dismiss the banner once the robot returns to `READY` on the next refresh

### 9b. Hardware faults

These indicate a component failure that won't self-resolve. They persist until
the user physically intervenes.

| Property | Meaning | Model |
|---|---|---|
| `globe_motor_fault_status` | Globe motor stall / winding fault | LR4/LR5 |
| `globe_motor_retract_fault_status` | Globe failed to retract to home position | LR4/LR5 |
| `usb_fault_status` | USB power rail fault | LR4/LR5 |
| `is_hopper_removed` | Litter hopper physically removed | LR4 |
| `is_bonnet_removed` | Bonnet lid open or removed | LR5 |
| `is_laser_dirty` | Cat-detection laser sensor obscured by litter dust | LR5 |
| `is_gas_sensor_fault_detected` | Odor / gas sensor hardware fault | LR5 |
| `is_waste_drawer_full` | Drawer full (boolean complement of `waste_drawer_level`) | all |
| `is_drawer_removed` _(LR5)_ | Drawer physically removed mid-session | LR5 |

### 9c. Surfacing strategy

**Banner widget** — a `FaultBanner` widget docked between the status bar and the
main area. Hidden by default; appears when any fault is active.

```
┌──────────────────────────────────────────────────────┐
│ ⚠  CAT DETECTED — cycle halted 14:32  [dismiss: d]  │  ← amber
│ ✗  GLOBE MOTOR FAULT — check globe rotation          │  ← red
└──────────────────────────────────────────────────────┘
```

Multiple faults stack vertically. `d` key (or `dismiss` command) hides the
banner for the current fault until state changes.

```python
FAULT_CHECKS = [
    # (attr_or_status, label, severity)
    ("is_cat_detected",              "CAT DETECTED — cycle halted",        "warn"),
    ("LitterBoxStatus.PINCH_DETECT", "PINCH DETECT — possible obstruction","error"),
    ("globe_motor_fault_status",     "GLOBE MOTOR FAULT",                   "error"),
    ("globe_motor_retract_fault_status", "GLOBE RETRACT FAULT",            "error"),
    ("usb_fault_status",             "USB POWER FAULT",                     "error"),
    ("is_hopper_removed",            "HOPPER REMOVED",                      "warn"),
    ("is_bonnet_removed",            "BONNET OPEN",                         "warn"),
    ("is_laser_dirty",               "LASER SENSOR DIRTY — clean globe",   "warn"),
    ("is_gas_sensor_fault_detected", "GAS SENSOR FAULT",                   "error"),
    ("is_waste_drawer_full",         "DRAWER FULL — empty now",            "warn"),
]

def _check_faults(self, robot) -> list[tuple[str, str]]:
    active = []
    status = getattr(robot, "status", None)
    for attr, label, sev in FAULT_CHECKS:
        if attr.startswith("LitterBoxStatus."):
            enum_name = attr.split(".")[1]
            if status and status.name == enum_name:
                active.append((label, sev))
        elif getattr(robot, attr, False):
            active.append((label, sev))
    return active
```

**Cat animation modes** to add alongside `"error"`:
- `"alert"` — blinking/urgent art for cat-detected / pinch events (clears automatically)
- `"fault"` — static red-tinted art for persistent hardware faults (requires user action)

**Log entries on state change** — only log when fault state transitions (not on
every 30 s poll), to avoid flooding the log:

```python
prev_faults = set()

def _refresh_faults(self, robot) -> None:
    current = set(label for label, _ in self._check_faults(robot))
    new_faults = current - self.prev_faults
    cleared    = self.prev_faults - current
    for f in new_faults:
        self._log_err(f"FAULT: {f}")
    for f in cleared:
        self._log_ok(f"Cleared: {f}")
    self.prev_faults = current
```

**Desktop notification** (see §22) — cat detected and pinch faults are good
candidates for an OS-level `plyer` notification, since the user may not be
watching the terminal.
