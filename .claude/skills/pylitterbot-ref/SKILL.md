---
name: pylitterbot-ref
description: Reference for the confirmed pylitterbot API surface as used in asher-cli. Load before making changes to robot command handling, monitoring, or adapter code. Prevents attribute-name guessing and eliminates runtime inspection commands.
user-invocable: false
---

# pylitterbot Confirmed API Surface

Load this skill whenever working on `asher/commands/`, `asher/monitoring/`, `asher/robot_adapters.py`, or anything that touches `robot.*`.

## Robot attributes (LR4 confirmed)

```python
robot.name                    # str
robot.serial                  # str
robot.is_online               # bool
robot.status                  # LitterBoxStatus enum
robot.waste_drawer_level      # int, 0–100
robot.sleep_mode_enabled      # bool — NOT "sleeping"
robot.panel_lock_enabled      # bool — NOT "panel_lockout"
robot.night_light_mode_enabled # bool
robot.last_seen               # datetime | None
```

## Robot methods (all async, await required)

```python
await robot.refresh()
await robot.start_cleaning()
await robot.set_sleep_mode(enabled: bool)
await robot.set_panel_lockout(enabled: bool)
await robot.set_night_light_brightness(brightness: int)   # or:
await robot.set_night_light_mode(mode: NightLightMode)
await robot.get_activity_history(limit: int)  # -> list[Activity]
```

## Activity objects

```python
activity.timestamp   # datetime
activity.action      # LitterBoxStatus enum (same as robot.status values)
```

## Model detection

```python
model_name = type(robot).__name__  # "LitterRobot4", "LitterRobot3", etc.
```

### Model-specific behaviour

| Feature | LR3 | LR4 | LR5 |
|---|---|---|---|
| `set_sleep_mode()` | Simple on/off | Per-weekday schedule | TBD |
| Night light | `set_night_light_brightness(int)` | `set_night_light_mode(NightLightMode)` | TBD |

Use `asher/robot_adapters.py` for all model-specific dispatch — do not branch on `type(robot).__name__` inline in command handlers.

## Timing / cloud queuing gotcha

`sendLitterRobot4Command` returns when the cloud **queues** the command, not when the robot applies it.
- Toggle commands (lock, unlock, night-light): use optimistic UI updates, not `refresh()` after the call.
- State-unknown commands (sleep, wake): use `asyncio.sleep(2)` + `refresh()` + `_refresh_status()` as best-effort.

## Safe attribute access pattern

```python
level = getattr(robot, "waste_drawer_level", None)
if level is not None:
    ...
```

Use `getattr(..., default)` or `try/except AttributeError` for any attribute not guaranteed on all models.
