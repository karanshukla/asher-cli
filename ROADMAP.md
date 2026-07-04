# Asher CLI — Roadmap & Feature Gaps

Current state, missing functionality, and suggested additions — grounded in what
`pylitterbot` actually exposes today.

---

## What's working now

| Area | Status |
|---|---|
| Auth — keyring (primary) → `.env` fallback → `/login` prompt | ✅ |
| Connect & load robots | ✅ |
| Status bar top row — name + model, contextual online label (Cycling/Paused/Cat inside/Cycle done/Drawer full/Offline), night light mode + brightness, panel lock indicator | ✅ |
| Status bar second row — drawer %, litter %, cat weight (with pet name), last visit | ✅ |
| Pet name from Whisker account profile | ✅ |
| Commands: clean, status, lock, unlock, sleep, wake, night-light on/off/auto, night-light-brightness, history, export [days\|month], help, clear, quit | ✅ |
| Slash commands: `/login`, `/logout`, `/exit`, `/help`, `/robots`, `/robot <index\|name>`, `/pets`, `/pet <index\|name>`, `/cat on\|off\|color <hex>`, `/refresh [seconds\|off]`, `/config`, `/mcp on\|off\|status` | ✅ |
| MCP bridge — keyring-backed `pylitterbot[mcp]` launcher, auto-installs the extra, writes/removes the Claude Desktop config entry (incl. Windows MSIX path) | ✅ |
| Inline login flow (email → password in command bar, no restart) | ✅ |
| `LoginScreen` modal (`auth.py`) — available for future use | ✅ |
| Activity history (`get_activity_history`) | ✅ |
| Cat animation panel with mode changes | ✅ |
| Command history (↑/↓) | ✅ |
| WebSocket real-time updates (LR4 primary; poll fallback every 5 min for activity history) | ✅ |
| LR4 / LR5 / LR3 polymorphic support via `RobotAdapter` pattern | ✅ |
| Preferred robot persisted to keyring; auto-restored on next launch | ✅ |
| PyPI release workflow (`release.yml` — `release/*` branches) | ✅ |

---

## 1. Slash commands — configuration at runtime

Everything below would be `/command` style, similar to Claude Code, so they're
visually distinct from robot-action commands.

### ~~`/robot` — switch active robot~~ ✅

Two separate commands are live:

```
/robots           list all robots on the account (with active indicator)
/robot 0          switch to robot by index
/robot "Asher 2"  switch to robot by (partial, case-insensitive) name
```

Switching unsubscribes WebSocket from the old robot, re-subscribes to the new
one, and refreshes the status bar. The chosen robot's serial is saved to keyring
and auto-restored on the next launch.

### ~~`/auth`~~ → `/login` ✅ — update credentials without restart

`/login` starts an inline credential entry flow directly in the command bar:
the prompt label changes to `email ›` then `password ›`, the password field
masks input as `••••••••`, and on submit the credentials are saved to the OS
keyring and the connection is re-established — no restart needed.

`/logout` disconnects, deletes credentials from keyring, and prompts
`/login` to sign back in.

### ~~`/cat` — configure the cat animation~~ ✅

```
/cat off              hide the cat panel entirely (more log space)
/cat on               show the cat panel
/cat color <hex>      change the cat art colour (#58a6ff default)
/cat reset            revert to default palette colours
```

Toggling sets `widget.display = False/True` directly. Colour override stored in
`_cat_color` and applied in `_set_cat` / `_tick_cat` instead of the per-mode
palette. `/cat style` (alternate art sets) is not yet implemented.

### ~~`/refresh` — change the poll interval~~ ✅

```
/refresh 10       poll every 10 s
/refresh 60       poll every 60 s (lighter on API)
/refresh off      disable auto-refresh (manual `status` only)
/refresh          show current interval
```

Timer ref stored as `_poll_timer` in `AsherApp.__init__`; on change, old timer
is stopped via `timer.stop()` and a new one created with `set_interval`.
`_poll_interval` stores the current value for `/config` display.

### ~~`/config` — show current runtime config~~ ✅

```
/config
  robot          Idiot Box (LR4, index 0)
  refresh        300s
  cat panel      on  #58a6ff (default)
  active pet     Asher (index 0)
```

Read-only dump of current runtime settings. No API call needed.

### ~~`/pet` — switch which pet's name/weight is shown~~ ✅

```
/pet              list pets on the account
/pet 0            show Whisker pet at index 0 in the status bar
/pet luna         switch by partial, case-insensitive name
```

`_active_pet_idx` stored on `AsherApp`; `_refresh_status` reads it instead of
hard-coding `pets[0]`. Supports both index and name lookup.

---

## ~~2. History export to CSV~~ ✅

Writes activity history to a CSV file and opens the containing folder in the OS file explorer.

### Command syntax

`export` is a bare robot command (no `/` prefix) — it queries the robot for history and produces a local file artifact.

```
export            export last 30 days (Whisker API maximum — good default)
export 7          export last 7 days
export 14         export last 14 days
export month      alias for 30 days — explicit "I want everything Whisker will give me"
```

Whisker caps history at 30 days regardless of what you request — this is the hard ceiling.

### CSV columns

| Column | Source | Example |
|---|---|---|
| `timestamp` | `act.timestamp`, converted to local timezone, ISO 8601 | `2026-06-20T14:32:00+10:00` |
| `event` | human label from `ACTION_LABELS` map (§11) | `Clean cycle complete` |
| `raw_event` | `act.action.text` or `str(act.action)` | `Clean Cycle Complete` |
| `weight_lb` | `act.weight` | `9.1` |
| `pet_name` | resolved from `account.pets` by `pet_id` | `Asher` |
| `robot_name` | `robot.name` | `Idiot Box` |
| `robot_serial` | `robot.serial` | `LR4C012345` |

Rows sorted ascending by timestamp (oldest first). Empty cells left blank — no `null` or `N/A`.

### Output path

Default: `~/Downloads/asher-<serial>-<YYYY-MM-DD>.csv`

Example: `~/Downloads/asher-LR4C012345-2026-06-20.csv`

`~/Downloads` is the standard export destination on Windows, macOS, and most Linux desktops. If it doesn't exist, fall back to `~/Documents/asher-cli/` (create if needed), then `~`.

### Open folder after export

After writing, open the containing directory in the OS file explorer:

```python
import subprocess, sys
from pathlib import Path

def _open_folder(path: Path) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])
```

`explorer /select,<file>` highlights the specific file in Windows Explorer rather than just opening the folder — gives instant visual confirmation. `open -R` does the same in macOS Finder. Linux falls back to opening the parent directory with the default file manager.

### Log output during export

```
  Fetching history (last 30 days)…
  Writing asher-LR4C012345-2026-06-20.csv… 128 events
  Saved → ~/Downloads/asher-LR4C012345-2026-06-20.csv
  Opening folder…
```

Error cases:
- No robot connected → `"No robot connected"` (same as other robot commands)
- API failure → `"Failed to fetch history: <message>"`
- Write failure → `"Failed to write CSV: <message>"` (e.g. permissions issue) + suggest fallback path

### Data fetching

`get_activity_history(limit=N)` doesn't accept a date range — it returns the most recent N events. To implement day-based filtering:

1. Fetch with a high limit (e.g. `limit=500`) to ensure full coverage up to 30 days
2. Filter client-side: keep only events where `act.timestamp >= now - timedelta(days=N)`

For LR5, the richer `get_activities(limit, offset, activity_type)` (see §4) could be used for paginated export, but `get_activity_history` works for all models.

### Implementation sketch

Add `ExportCommand` in `asher/commands/__init__.py` inheriting `Command`:

```python
class ExportCommand(Command):
    name = "export"
    description = "export activity history to CSV"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        # parse days arg
        raw = args[0].lower() if args else "month"
        if raw in ("month", "30"):
            days = 30
        else:
            try:
                days = max(1, min(30, int(raw)))
            except ValueError:
                app._log_warn(f"Unknown period '{raw}' — use a number of days or 'month'")
                return

        await _run_export(app, days)
```

`_run_export` is a module-level async function (not a method) to keep `ExportCommand.run` thin and the logic independently testable.

### Naming note

The `help` output should list `export` alongside other robot commands, with a note on accepted args:

```
  export [days|month]   export activity history to CSV (default: 30 days)
```

---

## 3. Missing robot commands

All of these are real `LitterRobot4` / `LitterRobot5` methods in pylitterbot
that aren't wired up yet.

### `status` vs `info` — split the current status command

`status` currently dumps every known property into the log. It should instead
surface only what the user actually needs at a glance — the same information
shown in the status bar, refreshed on demand:

```
  Online         yes
  Status         Ready
  Drawer         48%
  Last seen      4m ago
  Cat weight     9.1 lb
```

`info` handles the full property dump — serial number, firmware version, wait
time, all boolean flags, model type, etc. Useful for debugging or first-time
setup, not something you need every time you check in:

```
  Name           Idiot Box
  Model          LR4  (LitterRobot4)
  Serial         LR4C012345
  Firmware       ESP: 1.1.50  STM: 1.0.11
  Wait time      7 min
  Sleeping       no
  Panel locked   no
  Night light    off
  Drawer         48%
  Online         yes
  Last seen      4m ago
```

### `power on` / `power off`
```python
await robot.set_power_status(True / False)
```
Hard-power the unit on or off. Useful for scheduled restarts.

### `wait-time <minutes>`
```python
await robot.set_wait_time(minutes)   # VALID_WAIT_TIMES: 3, 7, 15, 25, 30
```
Sets how many minutes the robot waits after a cat visit before cleaning.
Show current value in `status` output (`robot.clean_cycle_wait_time_minutes`).

### `panel-brightness <low|medium|high>`
```python
from pylitterbot.enums import BrightnessLevel
await robot.set_panel_brightness(BrightnessLevel.LOW)
```

### `rename <new name>`
```python
await robot.set_name("new name")
```
Renames the unit in the Whisker cloud (persists across sessions).

### `reset` / `reset-settings`
```python
await robot.reset()          # full factory reset
await robot.reset_settings() # settings reset only
```
Should require a `--confirm` flag or an "are you sure?" prompt before running.

### `firmware`
```python
has_update = await robot.has_firmware_update()
details    = await robot.get_firmware_details()
```
Show current firmware version and whether an update is available. Add
`firmware update` to trigger `robot.update_firmware()` with a warning.

### `insight [days]` — usage statistics
```python
insight = await robot.get_insight(days=30)
```
`Insight` object contains cycle counts, averages, etc. Could render a small
summary table:
```
  Cycles last 30d    42
  Avg cycles/day     1.4
  Drawer emptied     2x
```

---

## 4. LR5-only features

LR5 exposes additional capabilities that don't exist on LR4. The app should
detect model type and show/hide these commands gracefully.

| Command | API | LR5 property |
|---|---|---|
| `privacy on/off` | `set_privacy_mode(bool)` | `privacy_mode` |
| `volume <0-10>` | `set_volume(int)` | `sound_volume` |
| `camera-audio on/off` | `set_camera_audio(bool)` | `camera_audio_enabled` |
| `night-light color <hex>` | `set_night_light_settings(color=...)` | `night_light_color` |
| `drawer reset` | `reset_waste_drawer()` | `is_drawer_removed` |
| `filter reminder` | _(read-only)_ | `next_filter_replacement_date` |

The LR5 also has `get_activities(limit, offset, activity_type)` (plural) which
is richer than `get_activity_history` and supports pagination and filtering by
type (e.g. only weight events).

---

## 5. Feeder Robot support

`pylitterbot` fully supports the Feeder Robot. `account.robots` already includes
it if one is on the account. Currently the app only acts on `robots[0]` which
might be the feeder, not the litter box.

Additions needed:
- Detect robot type (`type(robot).__name__`) and show model in status bar (already done for the connected log line, not the status bar)
- Filter `robots` list to offer a dedicated feeder sub-context
- Wire up feeder commands:

```
snack             → await robot.give_snack()
gravity on/off    → await robot.set_gravity_mode(bool)
meal-size <n>     → await robot.set_meal_insert_size(float)
```

---

## 6. Real-time WebSocket updates (replace polling)

pylitterbot has first-class WebSocket support:

```python
await robot.subscribe()    # opens WS connection, fires EVENT_UPDATE
await robot.unsubscribe()
```

On `EVENT_UPDATE` the robot's properties update automatically — no polling
needed. The `_poll_status_interval` timer could be replaced with:

```python
robot.on(EVENT_UPDATE, lambda: asyncio.create_task(self._refresh_status()))
await robot.subscribe()
```

**Why this matters:** the current 30 s polling means the UI is always up to 30 s
stale. WebSocket gives instant updates — the drawer fill jumps as soon as the
cloud sees it, and a cleaning cycle starting shows immediately in the status bar.

---

## 7. Pet features

The `Pet` model in pylitterbot is surprisingly rich.

### Weight history chart (ASCII sparkline)
```python
pet = account.pets[0]
history = await pet.fetch_weight_history(limit=60)
# → list[WeightMeasurement(timestamp, weight)]
```
Could render a small sparkline in the log panel:

```
  Asher weight — last 14 days
  9.1 ▁▂▂▁▂▂▃▂▂▁▁▂▂▂  8.8 lb avg
```

### `pets` command — full pet status table
```
/pet info
  Name      Asher
  Breed     Domestic Shorthair
  Age       4 yrs
  Weight    9.1 lb (last reading 2h ago)
  Visits    6 this week
```

### Multi-pet support
If the account has multiple pets, the status bar currently only shows `pets[0]`.
Options:
- Show all names: `Asher & Luna 🐱 9.1 lb`
- Cycle through pets every few seconds
- Use `/pet <n>` to pin one

### Visit reassignment (LR5 only)
```python
await robot.reassign_pet_visit(event_id, from_pet_id=..., to_pet_id=...)
```
If weight ID misidentifies a cat, this corrects the record.

---

## 8. Sleep schedule

`robot.sleep_schedule` returns a `SleepSchedule` with per-day `SleepScheduleDay`
objects (day, sleep_time, wake_time, is_enabled). This is more granular than the
current `sleep` / `wake` toggle.

```
sleep-schedule            show current schedule
sleep-schedule set        interactive wizard (or flags)
sleep-schedule Mon 22:00 07:00   set Monday sleep window
sleep-schedule disable    clear all days
```

### Contextual sleep/wake toggle

LR4 does not implement `set_sleep_mode` — calling it raises `NotImplementedError`.
LR3 and LR5 both support it but with different signatures:

- **LR3**: `set_sleep_mode(value: bool, sleep_time: time | None)`
- **LR5**: `set_sleep_mode(value: bool, sleep_time: int | time | None, *, wake_time, day_of_week)`

The `sleep` / `wake` commands should detect the robot model and dispatch accordingly:
- LR3 → `set_sleep_mode(True/False)` (uses current time as sleep start)
- LR5 → `set_sleep_mode(True/False)` (enables/disables all schedule days)
- LR4 → explain schedule-based sleep and point to `sleep-schedule` command

---

## 9. Fault monitoring & alerts

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

---

## 10. Config file persistence

Currently all settings are read-only from `.env` and nothing the user sets at
runtime persists across restarts (e.g. `/refresh 10`, `/cat color green`).

A simple `config.json` alongside `.env` could store:
```json
{
  "active_robot_index": 0,
  "active_pet_index": 0,
  "poll_interval_seconds": 30,
  "cat_panel_visible": true,
  "cat_panel_color": "#58a6ff"
}
```

Load on startup, write on any `/config set` or `/cat` change.

---

## 11. UI / UX gaps

### ~~Status bar: litter level~~ ✅
`robot.litter_level` is shown in the second row of the status bar as `Litter N%`.
`litter_level_state` (Low / Nominal / High) is not shown — numeric % is sufficient.

### Status bar: WiFi indicator

The Whisker API does not expose the WiFi network name (SSID) for any model, so
"connected to MyNetwork" is not possible. What is available varies by model:

| Model | Available | API |
|---|---|---|
| LR5 | `wifi_rssi` — integer RSSI in dBm (e.g. `-65`) | `robot.wifi_rssi` |
| LR4 | `wifi_mode_status` — connection mode enum | `robot.wifi_mode_status` |
| LR3 | nothing | — |

**LR5 signal strength** can be rendered as a bar indicator in the top row:

```
  -40 dBm  ▂▄▆█  excellent
  -65 dBm  ▂▄▆░  good
  -80 dBm  ▂▄░░  weak
  -90 dBm  ▂░░░  poor
```

Mapping: `>= -60` excellent, `>= -70` good, `>= -80` weak, `< -80` poor.

**LR4 connection mode** (`WifiModeStatus` enum values):
- `ROUTER_CONNECTED` — connected via home router
- `HOTSPOT_CONNECTED` — connected via LR4's own hotspot (setup mode)
- `ROUTER_WAITING` / `HOTSPOT_WAITING` — connecting
- `ROUTER_FAULT` / `HOTSPOT_FAULT` — connection failed
- `OFF` / `NONE` — WiFi disabled or unknown

A minimal indicator for LR4 could just show a coloured dot:
`● WiFi` (green for ROUTER_CONNECTED, amber for fault/waiting).

**Implementation note:** Both properties are only present on their respective
models — `wifi_rssi` via `LR5Adapter` (or `getattr(robot, "wifi_rssi", None)`),
`wifi_mode_status` via `LR4Adapter`. Since SSID is unavailable, a tooltip or
the `info` command output is the natural place to show full WiFi diagnostics.

---

### Status bar: cycle counter
`robot.cycle_count` and `robot.scoops_saved_count` (scoops saved vs. traditional
box) — nice vanity stats for the right-side cat panel caption area.

### Color-coded status
The `[RDY]` status token is always the same grey. Map `LitterBoxStatus` values to
colours:
- `READY` → green
- `CYCLING` → blue (animated)
- `DRAWER_FULL` → red
- `CAT_DETECTED` → amber
- `OFFLINE` → red

### Tabs / split view for multiple robots
If `account.robots` has more than one unit, a tab bar across the top (Textual's
`TabbedContent` widget) would let users switch without `/robot n`.

### Readable event labels (replace raw library strings)

The current `_cmd_history_list` renders `action.text` or `str(action)` directly,
which produces whatever pylitterbot happens to expose — enum names, internal
strings, or unprintable objects. It needs a translation layer.

**Current output:**
```
  06/14 14:22  Litter Robot is Ready.
  06/14 13:55  Clean Cycle Complete
  06/14 13:54  Cat Detected
  06/14 12:01  Drawer Full
```

**Target output:**
```
  06/14 14:22  Ready                          (muted grey)
  06/14 13:55  Clean cycle complete  1m 42s   (green, with duration)
  06/14 13:54  Cat detected  Asher  9.1 lb    (amber, with weight + pet)
  06/14 12:01  Drawer full — empty now        (red)
  06/14 11:30  Sleep mode on                  (muted)
```

**Implementation — event label map:**

```python
ACTION_LABELS: dict[str, tuple[str, str]] = {
    # lowercased raw text → (display label, colour)
    "ready":                      ("Ready",                   "#484f58"),
    "litter robot is ready.":     ("Ready",                   "#484f58"),
    "clean cycle complete":       ("Clean cycle complete",     "#3fb950"),
    "clean cycle in progress":    ("Cleaning…",               "#58a6ff"),
    "cat detected":               ("Cat detected",            "#d29922"),
    "cat sensor interrupted":     ("Cat sensor tripped",      "#d29922"),
    "drawer full":                ("Drawer full — empty now", "#f85149"),
    "drawer full cleared":        ("Drawer emptied",          "#3fb950"),
    "sleep mode on":              ("Sleep mode on",           "#484f58"),
    "sleep mode off":             ("Sleep mode off",          "#484f58"),
    "panel locked":               ("Panel locked",            "#484f58"),
    "panel unlocked":             ("Panel unlocked",          "#484f58"),
    "offline":                    ("Offline",                 "#f85149"),
    "power off":                  ("Powered off",             "#f85149"),
    "power on":                   ("Powered on",              "#3fb950"),
    "motor fault":                ("Motor fault",             "#f85149"),
    "pinch detect":               ("Pinch detected",          "#f85149"),
    "timing fault":               ("Timing fault",            "#d29922"),
}

def _fmt_action(act, pets: list) -> tuple[str, str]:
    raw     = getattr(act, "action", None)
    raw_str = (raw.text if hasattr(raw, "text") else str(raw)).strip()
    label, colour = ACTION_LABELS.get(raw_str.lower(), (raw_str, "#8b949e"))

    weight  = getattr(act, "weight", None)
    pet_id  = getattr(act, "pet_id", None)
    pet_name = next((p.name for p in pets if p.id == pet_id), None)

    if weight and "cat" in raw_str.lower():
        label += f"  {pet_name}  {weight:.1f} lb" if pet_name else f"  {weight:.1f} lb"

    return label, colour
```

**Fallback:** unknown event types fall through to the raw string in muted grey
rather than crashing — new pylitterbot event types shouldn't break the display.

### History as a scrollable sub-view (pager mode)

Currently `history` dumps rows into the main log, which then scrolls off.
The better pattern — like Claude Code's diff/file viewers — is a dedicated
screen pushed over the main UI that the user scrolls through and dismisses.

**Behaviour:**
- `history` command pushes a `HistoryScreen` over the main app
- Full-width, full-height overlay with its own scroll container
- Page Up / Page Down, arrow keys, Home / End all work naturally
- `q`, `Escape`, or `Enter` pops back to the main view instantly
- A header bar shows the robot name and event count

**Textual implementation:**

```python
from textual.screen import Screen
from textual.widgets import Static, Footer
from textual.containers import ScrollableContainer

class HistoryScreen(Screen):
    BINDINGS = [
        ("escape,q,enter", "app.pop_screen", "Close"),
        ("page_up",        "scroll_up",      "Page up"),
        ("page_down",      "scroll_down",    "Page down"),
    ]

    def __init__(self, rows: list[Text], title: str) -> None:
        super().__init__()
        self._rows  = rows
        self._title = title

    def compose(self):
        yield Static(self._title, id="history-header")
        with ScrollableContainer(id="history-scroll"):
            for row in self._rows:
                yield Static(row)
        yield Footer()

    def action_scroll_up(self):
        self.query_one("#history-scroll").scroll_page_up()

    def action_scroll_down(self):
        self.query_one("#history-scroll").scroll_page_down()
```

Invoke it from `_cmd_history_list`:

```python
rows = [_fmt_row(act, self._pets) for act in acts]
title = Text(f"  Activity history — {self._robot.name}  ({len(acts)} events)  [q] close",
             style="bold #58a6ff")
await self.app.push_screen(HistoryScreen(rows, title))
```

**CSS sketch:**

```css
HistoryScreen {
    background: #0d1117;
    border: solid #30363d;
}

#history-header {
    dock: top;
    height: 1;
    background: #161b22;
    padding: 0 2;
    color: #58a6ff;
}

#history-scroll {
    padding: 1 2;
}
```

This approach means `history 100` is just as usable as `history 10` — the
events don't pollute the log and the user can scroll at their own pace.

### Live cat presence indicator

`robot.is_cat_detected` is already polled in `_refresh_status`, but there's no
dedicated visual for "cat is inside right now" vs. "cat was detected in a fault".
The distinction matters: fault detection (§9) is a safety event that halted a
cycle; live presence is ambient state while a cat is using the box.

**Status bar** — add a `🐱 IN` badge in the second row that appears while
`is_cat_detected` is true and disappears when the cat leaves:

```
Drawer [████░░░░] 48%   Litter: Nominal   🐱 IN   Asher 9.1 lb   7m ago
```

**Cat panel** — switch the cat art to a `"present"` mode (new state, cat-in-box
ASCII art or a distinct label like `"visiting…"`). Switch back to `idle` once
`is_cat_detected` returns false.

WebSocket (§6) makes this responsive — with 30 s polling you'll likely miss the
entire visit. With real-time push the badge appears the moment the sensor trips.

---

### Real-time cycling indicator (requires WebSockets)

`LitterBoxStatus.CLEAN_CYCLE` is already caught by the `[RDY]` status chip,
but polling every 30 s means a full clean cycle (typically 2–4 min) can start
and finish between polls, showing only `Ready` to the user the whole time.

**What's needed:**
- WebSocket subscription (§6) — `robot.subscribe()` fires `EVENT_UPDATE`
  immediately when the status transitions to `CLEAN_CYCLE` or back to `READY`.
- Animated status chip — while `status == CLEAN_CYCLE`, pulse the `[RDY]` chip
  blue and add a spinner character (Textual's `LoadingIndicator` or a manual
  `_tick` frame cycle):
  ```
  ◆ Asher CLI   Idiot Box   ● ONLINE   [⠙ CYCLING]
  ```
- Cat animation — switch to `"cleaning"` mode (already defined) the moment the
  cycle starts; revert to `idle` on `READY`.
- Elapsed time — show how long the current cycle has been running:
  ```
  [⠙ CYCLING  0:42]
  ```
  Track `_cycle_start: datetime | None` on the transition to `CLEAN_CYCLE`;
  update the chip every second via a `set_interval(1, ...)` timer that's active
  only while cycling.

This is the primary reason to implement WebSocket (§6) — the cycling indicator
is meaningless without it.

---

### Timestamps in activity history
The history output currently shows `mm/dd HH:MM`. Adding the year for older
events and relative time (like the status bar's "7d ago") would be cleaner.

### `history` pagination
`get_activity_history(limit=25)` is hardcoded. Could support `history 50` or
`history --all` to page through more results.

### `history --type cat` filter (LR5)
`robot.get_activities(activity_type="cat_detection")` on LR5 lets you filter to
only cat visits, only cleans, etc.

---

## 12. Stretch / nice-to-have

| Idea | Notes |
|---|---|
| Desktop notifications | `plyer` / `winotify` toasts + `winsound` bell — see §22 |
| **Export to CSV** | `export [days\|month]` command — writes to `~/Downloads`, opens folder in OS explorer — see §2 |
| Weight sparkline in cat panel | Replace idle cat with a 7-day weight chart |
| Dark / light theme toggle | `/theme light` swaps colour palette |
| Startup robot selection | If multiple robots, prompt on launch instead of defaulting to `[0]` |
| `.env` wizard | First-run prompt if no `.env` found, writes creds interactively |
| Reconnect on network drop | Currently a failed poll is silently swallowed; should show a banner and retry |

---

## 13. Account management

### Credential persistence ✅ — OS keyring

Credentials (email + password) are stored in the OS keyring after the first
`/login`. On subsequent runs `_keyring_load()` retrieves them — no re-entry
needed. `.env` is still supported as a fallback for CI and existing users.

Helper functions in `asher/connection/__init__.py`:
- `_keyring_load() → tuple[str, str]` — returns `(email, password)` or `("", "")`
- `_keyring_save(email, password) → bool`
- `_keyring_delete()` — called by `/logout`

Keyring service name: `asher-cli`, keys `email` and `password`.

### Token persistence (stretch — avoid API re-auth on every run)

`Account.connect()` accepts a pre-existing `token` dict and exposes a
`token_update_callback`. If we save the session token alongside credentials
after first login, subsequent runs skip the username/password API call entirely
— faster startup and more resilient to rate-limiting.

```python
def save_token(token: dict | None) -> None:
    if token:
        keyring.set_password("asher-cli", "token", json.dumps(token))

account = Account(
    token=json.loads(keyring.get_password("asher-cli", "token") or "null"),
    token_update_callback=save_token,
)
```

The token is automatically refreshed by pylitterbot when it expires. This
would mean users only re-enter their password when the refresh token itself
expires (typically months).

### `subscribe_for_updates` — let pylitterbot manage WebSocket per robot

`account.connect(subscribe_for_updates=True)` calls `robot.subscribe()` for
every loaded robot automatically. Combined with `account.load_robots(subscribe_for_updates=True)`,
this means the app never needs its own polling timer. The `EVENT_UPDATE` event
fires on each robot instance when the cloud pushes new state.

```python
from pylitterbot.event import EVENT_UPDATE

robot.on(EVENT_UPDATE, lambda: self.call_soon(self._refresh_status))
await account.connect(..., load_robots=True, subscribe_for_updates=True)
```

### `/account` command — account-level info

```
/account              show logged-in email and user_id
/account logout       delete saved token, force re-login next run
/account refresh      re-fetch all robots and pets from the API
```

### Multi-account support (stretch)

The `Account` class is stateless enough to support multiple instances. A power
user with separate Whisker accounts could switch with `/account switch 1`. Would
require storing a list of token files rather than one.

---

## 14. Slash commands — full design spec

Slash commands (`/foo`) are distinguished from robot-action commands (`clean`,
`status`) by the leading `/`. They configure the app rather than send commands
to the robot.

### Parsing ✅

Dispatch is live in `on_input_submitted` in `asher/commands/__init__.py`:

```python
if raw.startswith("/"):
    self._run_slash_cmd(raw)
else:
    self._run_cmd(raw)
```

### Full slash command table

| Command | Description | Implementation note |
|---|---|---|
| `/login` ✅ | Enter credentials inline, save to keyring, reconnect | Inline flow in command bar |
| `/logout` ✅ | Delete keyring credentials, disconnect | `_keyring_delete()` + disconnect |
| `/exit` ✅ | Exit the app | `self.exit()` |
| `/help` ✅ | Show all commands | Two-section output: robot cmds + slash cmds |
| `/robot [index\|name]` | List or switch active robot | `self._robot = robots[n]` + status refresh |
| `/pets` | List all pets with index and active indicator | mirrors `/robots` |
| `/pet <index\|name>` | Switch which pet shows in status bar | `self._active_pet_idx = n` |
| `/account` | Show account info | `account.user_id`, email from keyring |
| `/refresh [seconds\|off]` | Change poll interval | Cancel + recreate `set_interval` timer |
| `/cat [on\|off]` | Show/hide cat panel | `add_class` / `remove_class` on `#cat-panel` |
| `/cat color <hex>` | Change cat art colour | Update `_cat_color` attr, redraw |
| `/cat style <n>` | Switch ASCII art set | Swap `CATS` dict at runtime |
| `/config` | Show all current settings | Read-only dump |
| `/config set <key> <val>` | Change a setting | Write to `config.json` |
| `/theme [dark\|light]` | Swap colour scheme | Swap Textual CSS variables |
| `/log [n]` | Set max log lines to keep | `RichLog(max_lines=n)` |
| `export [days\|month]` | Export activity history to CSV | See §2 for full spec |
| `/notify [on\|off\|test]` | Desktop notification settings | See §22 |

### Tab-completion

Textual's `Input` widget doesn't ship with completion, but it can be extended.
A `CompletionList` overlay above the input bar (like a dropdown) that appears
when the user types `/` would make the slash system discoverable:

```
/r[ob...]
  /robot       switch active robot
  /refresh     change poll interval
```

This could be built with a `ListView` widget overlaid at the bottom of the
`#main-area` that hides/shows based on input content.

---

## 15. PyPI publishing — `pip install asher-cli`

The goal: any Python user can run `pip install asher-cli` (or `pipx install asher-cli`)
and immediately type `asher` in any terminal, with no manual venv or clone required.

### What's already in place

`pyproject.toml` now has everything needed:
- `[project]` metadata (name, version, description, classifiers)
- `dependencies` pinned to minimum versions
- `[project.scripts]` entry point: `asher = "asher.__main__:main"`
- `[build-system]` using `hatchling`

### Publishing to PyPI

```bash
# 1. Build the distribution
pip install hatch
hatch build
# → dist/asher-1.0.0-py3-none-any.whl
# → dist/asher-cli-1.0.0.tar.gz

# 2. Test in a clean environment first
pipx install asher-cli --index-url https://test.pypi.org/simple/

# 3. Upload to PyPI
pip install twine
twine upload dist/*

# then anywhere:
pip install asher-cli
asher
```

### Automate publishing on release branch push (release.yml) ✅

`.github/workflows/release.yml` is live. Triggered by pushing to any
`release/*` branch (not tags — tags are for git history only, not CI triggers):

```yaml
name: Release
on:
  push:
    branches:
      - "release/*"

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write   # OIDC trusted publishing — no API token needed
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

**Trusted publishing**: PyPI is configured to trust the OIDC token for
`karanshukla/asher-cli` → `release.yml` → `pypi` environment. No stored API
token needed.

**Hotfix flow** — branch from the last release branch directly, don't touch
`main`:

```bash
git checkout release/1.0.0
git checkout -b release/1.0.1
# cherry-pick fix, bump version in pyproject.toml
git push origin release/1.0.1   # → triggers publish
git tag v1.0.1                  # optional, for git history only
```

### Package release checklist

- [ ] `hatch version minor` — bump version in `pyproject.toml`
- [ ] `CHANGELOG.md` updated
- [ ] `README.md` has `pip install asher-cli` install instructions
- [ ] Tested in a clean venv: `pip install .` then `asher`
- [ ] `git checkout -b release/X.Y.Z && git push origin release/X.Y.Z`

---

## 16. Standalone binary — no Python required

### Option A — `pipx` (simplest — wraps the PyPI package)

```bash
pipx install asher-cli
asher   # works anywhere
```

### Option B — PyInstaller (true standalone `.exe` / binary)

```bash
pip install pyinstaller
pyinstaller --onefile --name asher app.py
# dist/asher.exe (Windows) or dist/asher (macOS/Linux)
```

**Known friction points:**
- `textual` ships CSS and static assets that PyInstaller needs to bundle via
  `--collect-data textual`
- `pylitterbot` uses `aiohttp` which has C extensions — ensure the correct
  platform wheels are bundled
- Resulting binary is ~30–60 MB but needs no Python installed

Recommended spec file additions:
```python
# asher.spec
a = Analysis(
    ['app.py'],
    hiddenimports=['pylitterbot', 'textual'],
    datas=[
        ('.venv/Lib/site-packages/textual', 'textual'),
    ],
)
```

### Option C — Nuitka (compiled, faster startup)

```bash
pip install nuitka
python -m nuitka --standalone --onefile app.py
```

Slower to build but produces a smaller, faster binary than PyInstaller because
it compiles Python to C. Good for a final release artifact.

### Option D — `uv` script header (zero-install, modern)

For a developer-facing tool, `uv` inline dependencies are the newest approach:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pylitterbot>=3.0", "textual>=0.47", "python-dotenv"]
# ///
```

Run with `uv run app.py` — no venv setup needed, `uv` handles it.

### Distribution checklist

- [ ] `pyproject.toml` with version, dependencies, entry point
- [ ] `CHANGELOG.md`
- [ ] GitHub Release with attached `.exe` / binary built by CI
- [ ] GitHub Actions workflow: `build.yml` running PyInstaller on
  ubuntu-latest, windows-latest, macos-latest

---

## 17. Testing

### Unit tests ✅

Pure function tests with no Textual or API dependency. Already in place:

```
tests/
  conftest.py       shared fixtures (mock_robot, mock_account)
  testhelpers.py    fmt_ago, drawer_bar — 12 tests, all passing
```

Run: `uv run pytest`

CI matrix: Python 3.10 / 3.11 / 3.12 × Ubuntu / Windows / macOS.

### Integration tests — pylitterbot mocking ✅ (fixtures ready, handlers not yet covered)

`tests/conftest.py` already provides `mock_robot` and `mock_account` fixtures
using `AsyncMock`. The next step is wiring them into command handler tests:

```python
# tests/testcommands.py
async def test_clean_calls_start_cleaning(mock_robot):
    app = AsherApp()
    app._robot = mock_robot
    await app._cmd_clean()
    mock_robot.start_cleaning.assert_called_once()

async def test_unknown_command_logs_warning(mock_robot):
    app = AsherApp()
    app._robot = mock_robot
    # assert _log_warn was called with "Unknown command"
```

Slash command tests follow the same pattern — inject state, call `_run_slash_cmd`,
assert on side effects (keyring calls, cat mode, log output).

### E2E — Textual Pilot harness

Textual ships a `Pilot` test harness that drives the full TUI — keypresses,
widget queries, and assertions — without a real terminal. No extra install
needed; it's part of `textual` itself.

```python
# tests/teste2e.py
import pytest
from asher.app import AsherApp

@pytest.mark.asyncio
async def test_help_renders():
    async with AsherApp().run_test() as pilot:
        await pilot.press("h", "e", "l", "p", "enter")
        log = pilot.app.query_one("#log")
        content = str(log.renderable)
        assert "clean" in content
        assert "/login" in content

@pytest.mark.asyncio
async def test_quit_exits():
    async with AsherApp().run_test() as pilot:
        await pilot.press("q", "enter")
        assert pilot.app._exit  # app exited cleanly

@pytest.mark.asyncio
async def test_clear_empties_log():
    async with AsherApp().run_test() as pilot:
        await pilot.press("c", "l", "e", "a", "r", "enter")
        log = pilot.app.query_one("#log")
        assert str(log.renderable).strip() == ""
```

The key `run_test()` context manager boots the full app headlessly, fires the
compose/mount lifecycle, and lets tests assert on real widget state. No mocking
of Textual internals required — only the pylitterbot layer needs mocking.

**Mocking the connection in E2E tests:**

```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_status_bar_updates_on_connect(mock_robot, mock_account):
    with patch("asher.connection.Account", return_value=mock_account):
        async with AsherApp().run_test() as pilot:
            await pilot.pause(0.1)   # let _connect_worker finish
            lbl = pilot.app.query_one("#online-lbl").renderable
            assert "ONLINE" in str(lbl)
```

### Code coverage

Add `pytest-cov` to dev dependencies:

```toml
[dependency-groups]
dev = [
    ...
    "pytest-cov>=5.0",
]
```

Run with terminal report:

```bash
uv run pytest --cov=asher --cov-report=term-missing
```

Target coverage by layer:

| Layer | Target | Notes |
|---|---|---|
| `helpers.py` | 100% | Pure functions, trivially testable |
| `commands/` | ≥ 80% | Mock robot; cover each command branch |
| `connection/` | ≥ 70% | Mock keyring + pylitterbot Account |
| `monitoring/` | ≥ 70% | Mock robot; test drawer full threshold |
| `ui/` | ≥ 50% | E2E pilot covers compose/log helpers |

Add to CI once a baseline is established — fail the build if coverage drops
below the agreed floor.

### Suggested test structure (target)

```
tests/
  conftest.py         ✅ shared fixtures (mock_robot, mock_account)
  testhelpers.py      ✅ fmt_ago, drawer_bar (12 tests)
  testcommands.py        robot command handler integration tests
  testslash.py           /login, /logout, /exit slash command tests
  teste2e.py             Textual Pilot end-to-end tests
  snapshots/             baseline TUI screenshots (textual-snapshot)
```

---

## 18. Cat panel — robot status badges underneath the art

Currently the cat panel only shows the ASCII art and a single italic label
(`connected`, `cleaning…`, etc.). The panel has room to show a compact set of
status indicators beneath the art without touching the status bar or log.

### Proposed layout

```
  /\_____/\
 /  o   o  \          ← ASCII art (existing)
( ==  ^  == )
 )         (
(           )
 \  |___|  /
  \_______/

  connected            ← mode label (existing)

  ● RDY                ← status line
  🔓 unlocked
  ☀ night light off
  💤 awake
  ⏱ wait: 7 min
```

### Implementation

Add a new `Static` widget (`#cat-status`) below `#cat-label` inside `#cat-panel`.
Update it in `_refresh_status` alongside the header bar:

```python
def _update_cat_status(self, r) -> None:
    status    = getattr(r, "status",              None)
    locked    = getattr(r, "panel_lock_enabled",  False)
    sleeping  = getattr(r, "is_sleeping",         False)
    night     = getattr(r, "night_light_mode_enabled", False)
    wait      = getattr(r, "clean_cycle_wait_time_minutes", None)

    lines = Text()
    # status chip
    status_str = status.value if status else "—"
    status_color = STATUS_COLORS.get(status_str, "#8b949e")
    lines.append(f"● {status_str}\n", style=status_color)
    # lock
    lines.append("🔒 locked\n"   if locked   else "🔓 unlocked\n", style="#8b949e")
    # sleep
    lines.append("💤 sleeping\n" if sleeping  else "  awake\n",    style="#8b949e")
    # night light
    lines.append("☀ light on\n"  if night    else "☾ light off\n",style="#8b949e")
    # wait time
    if wait:
        lines.append(f"⏱ wait {wait}m\n", style="#484f58")

    self.query_one("#cat-status", Static).update(lines)
```

Status → colour mapping (`STATUS_COLORS`):

| Status value | Colour |
|---|---|
| `Ready` | `#3fb950` (green) |
| `Cycling` | `#58a6ff` (blue) |
| `Cat Detected` | `#d29922` (amber) |
| `Drawer Full` | `#f85149` (red) |
| `Offline` | `#f85149` (red) |
| `Sleeping` | `#484f58` (muted) |

### CSS additions

```css
#cat-status {
    width: 22;
    height: auto;
    text-align: center;
    padding-top: 1;
    color: #8b949e;
    font-size: 0.85em;
}
```

The cat panel would also benefit from a **minimum height** so the status badges
don't get squashed when the terminal is short. Consider making the panel
collapsible (the `/cat off` slash command from §14) so users on small terminals
can reclaim the space.

---

## 19. Architecture refactor — modular structure

`app.py` is currently a single ~560-line file. That works for now, but adding
the features in this roadmap would push it past 1 000 lines quickly. A clean
module split makes it easier to test, extend, and read.

### Proposed package layout

```
asher/
  __init__.py
  app.py            AsherApp class only — compose, mount, bindings
  commands.py       _run_cmd, _run_slash, all _cmd_* methods (mixin or module)
  status.py         _refresh_status, _update_cat_status, header widget logic
  config.py         Config dataclass, load_config(), save_config()
  cats.py           CATS dict, _set_cat(), _tick_cat(), cat art definitions
  helpers.py        fmt_ago(), drawer_bar(), ts(), STATUS_COLORS
  widgets/
    __init__.py
    statusbar.py    StatusBar(Widget) — self-contained header widget
    catpanel.py     CatPanel(Widget) — art + label + status badges
    logpanel.py     LogPanel(Widget) — RichLog wrapper with helpers
    inputbar.py     InputBar(Widget) — prompt + Input + completion
  __main__.py       if __name__ == "__main__": main()
```

### Key refactoring moves

**1. Extract `StatusBar` as a proper Widget**

Currently the header is a raw `Container` with individually-queried `Static`
children updated from `AsherApp`. A `StatusBar` widget owns its own children
and exposes a single `update(robot, pets)` method. The app calls
`self.query_one(StatusBar).update(...)` — no more `query_one("#drawer-lbl")` 
scattered across methods.

**2. Extract `CatPanel` as a Widget**

`CatPanel` owns the art, label, and status badges. Exposes:
- `set_mode(mode, label)` — replaces `_set_cat()`
- `tick()` — advances animation frame
- `update_status(robot)` — refreshes badge row

**3. Commands as a mixin or module**

`_run_cmd`, `_run_slash`, and all `_cmd_*` methods are pure async logic with no
Textual widget dependencies beyond `_log_*` helpers. They can live in a
`CommandHandler` class that receives the app's log and robot reference:

```python
class CommandHandler:
    def __init__(self, log_fn, robot_fn, app):
        self._log = log_fn    # callable → RichLog.write
        self._robot = robot_fn  # callable → current robot
        self._app = app

    async def handle(self, raw: str) -> None: ...
    async def _cmd_clean(self) -> None: ...
```

This makes command methods unit-testable with no Textual dependency at all.

**4. `Config` dataclass**

```python
@dataclass
class Config:
    active_robot_index: int = 0
    active_pet_index: int = 0
    poll_interval: int = 30
    cat_visible: bool = True
    cat_color: str = "#58a6ff"
    token_path: Path = Path("~/.asher_token.json")

    @classmethod
    def load(cls) -> Config: ...
    def save(self) -> None: ...
```

Loaded once at startup, passed into `AsherApp.__init__`, mutated by `/config set`
slash commands, and saved on change.

**5. `helpers.py` — pure functions only**

`fmt_ago`, `drawer_bar`, `ts`, `STATUS_COLORS` — no imports from Textual or
pylitterbot. Makes them trivially unit-testable.

### Migration path

1. Create `asher/` package, move `app.py` → `asher/app.py`
2. Extract `helpers.py` first (zero dependencies, easy test wins)
3. Extract `cats.py` (pure data)
4. Extract `config.py` (no Textual dependency)
5. Extract `StatusBar` widget (isolate header from app logic)
6. Extract `CatPanel` widget
7. Extract `CommandHandler` (biggest win for testability)
8. Update `pyproject.toml` entry point: `asher = "asher.__main__:main"`

Each step is independently mergeable — no big-bang rewrite needed.

---

## 20. Versioning

### Single source of truth

Version lives in exactly one place — `pyproject.toml` — and is read everywhere else:

```toml
# pyproject.toml
[project]
name = "asher-cli"
version = "1.0.0"
```

`app.py` reads it at runtime instead of hard-coding `VERSION = "1.0.0"`:

```python
from importlib.metadata import version, PackageNotFoundError

try:
    VERSION = version("asher-cli")
except PackageNotFoundError:
    VERSION = "dev"   # running from source without install
```

This means the version shown in the status bar header always matches whatever
is in `pyproject.toml` — no drift.

### Scheme — Semantic Versioning

```
MAJOR.MINOR.PATCH[-prerelease]

1.0.0        stable release
1.1.0        new commands or UI features (minor, backward-compatible)
1.1.1        bug fixes only
2.0.0        breaking change (e.g. config file format change, renamed commands)
1.2.0-alpha  pre-release, not on stable channel
```

Rules of thumb:
- Bump **PATCH** for bug fixes, typo corrections, dependency pin updates
- Bump **MINOR** for new commands, new config keys, new widgets
- Bump **MAJOR** if the `.env` format changes, a command is renamed/removed,
  or the config schema breaks backward compatibility

### Bumping the version

Using `hatch` (pairs naturally with `hatchling` build backend):

```bash
hatch version patch    # 1.0.0 → 1.0.1
hatch version minor    # 1.0.1 → 1.1.0
hatch version major    # 1.1.0 → 2.0.0
hatch version 1.2.0-alpha  # explicit
```

Or `bump-my-version` (more configurable):

```bash
pip install bump-my-version
bump-my-version bump patch
```

Both write directly to `pyproject.toml` and can be configured to also tag the
commit.

### Git tagging convention

Every release gets a signed tag:

```bash
git tag -s v1.1.0 -m "release: v1.1.0"
git push origin v1.1.0
```

The `v` prefix is conventional and lets GitHub Actions trigger release workflows
on `v*` tag pushes.

### Changelog

Keep a `CHANGELOG.md` in [Keep a Changelog](https://keepachangelog.com) format.
Each PR merges under `## [Unreleased]`; on release that section becomes
`## [1.1.0] — 2026-06-20`.

```markdown
## [Unreleased]
### Added
- Cat panel status badges (lock, sleep, night light, wait time)
- `/robot` slash command for switching active robot

### Fixed
- `history` command using wrong method name (`get_activity` → `get_activity_history`)
- `quit`/`exit` crash in async worker (`call_from_thread` on same thread)

## [1.0.0] — 2026-06-14
### Added
- Initial release
```

**Automation option:** `git-cliff` auto-generates changelog entries from
conventional commit messages (`feat:`, `fix:`, `chore:` prefixes):

```bash
pip install git-cliff
git cliff --tag v1.1.0 -o CHANGELOG.md
```

---

## 21. CI / CD pipeline

### Workflow overview

```
push / PR  ──► lint ──► test ──► build artifacts
                                       │
tag v*  ──────────────────────────►  release
                                    (attach binaries, publish changelog)
```

### `.github/workflows/ci.yml` — lint + test on every push

```yaml
name: CI
on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy asher/ --ignore-missing-imports

  test:
    needs: lint
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
        os: [ubuntu-latest, windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --dev
      - run: uv run pytest tests/ -v --tb=short
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: test-snapshots-${{ matrix.os }}-${{ matrix.python-version }}
          path: tests/snapshots/
```

### `.github/workflows/release.yml` ✅ — triggered on `release/*` branch push

```yaml
name: Release
on:
  push:
    branches:
      - "release/*"

jobs:
  build:
    strategy:
      matrix:
        include:
          - os: ubuntu-latest
            artifact: asher-linux
            binary: dist/asher
          - os: windows-latest
            artifact: asher-windows
            binary: dist/asher.exe
          - os: macos-latest
            artifact: asher-macos
            binary: dist/asher
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pyinstaller --onefile --name asher asher/__main__.py
      - uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}
          path: ${{ matrix.binary }}

  release:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # needed for git-cliff changelog
      - uses: actions/download-artifact@v4
        with:
          path: artifacts/
      - name: Generate changelog
        run: |
          pip install git-cliff
          git cliff --latest --strip header -o RELEASE_NOTES.md
      - uses: softprops/action-gh-release@v2
        with:
          body_path: RELEASE_NOTES.md
          files: artifacts/**/*
```

### `.github/workflows/dependency-update.yml` — Dependabot / Renovate

Use Dependabot for automatic dependency PRs:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
    labels: ["dependencies"]
    open-pull-requests-limit: 5
```

Or Renovate (more configurable, handles `uv.lock` better):

```json
// renovate.json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:best-practices"],
  "packageRules": [
    {
      "matchPackageNames": ["pylitterbot"],
      "automerge": false,
      "labels": ["pylitterbot", "dependencies"]
    }
  ]
}
```

`pylitterbot` should never be auto-merged without manual review — the Whisker
API is reverse-engineered and a minor version bump could change method names or
response schemas.

### Branch strategy

```
main          always releasable; protected, requires passing CI
feature/*     new features; merge via PR with squash
fix/*         bug fixes; merge via PR
release/v*    optional stabilisation branch for larger releases
```

Protect `main`:
- Require PR with at least 1 approval (or self-approval for a solo project)
- Require all CI jobs to pass
- Disallow force-push

### PR template

```markdown
<!-- .github/pull_request_template.md -->
## What
<!-- one-line summary -->

## Why
<!-- motivation / issue link -->

## Test plan
- [ ] Ran `pytest tests/` locally — all green
- [ ] Tested in terminal (ran `asher` and exercised changed commands)
- [ ] Updated CHANGELOG.md under [Unreleased]
- [ ] No new hard-coded `VERSION` strings (use `importlib.metadata`)
```

### Code quality gates

| Tool | Purpose | Config file |
|---|---|---|
| `ruff` | Linting + formatting (replaces flake8, black, isort) | `pyproject.toml [tool.ruff]` |
| `mypy` | Static type checking | `pyproject.toml [tool.mypy]` |
| `pytest` | Test runner | `pyproject.toml [tool.pytest.ini_options]` |
| `textual-snapshot` | TUI regression snapshots | `pyproject.toml [tool.pytest.ini_options]` |
| Dependabot / Renovate | Dependency freshness | `.github/dependabot.yml` |

Minimal `pyproject.toml` additions:

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]  # line length handled by formatter

[tool.mypy]
python_version = "3.10"
warn_return_any = true
ignore_missing_imports = true   # pylitterbot has no stubs

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Release checklist (manual steps)

1. `uv run pytest` — all green
2. `hatch version minor` (or patch/major)
3. Update `CHANGELOG.md` — move `[Unreleased]` → `[x.y.z] — YYYY-MM-DD`
4. `git add pyproject.toml CHANGELOG.md && git commit -m "release: vX.Y.Z"`
5. `git tag -s vX.Y.Z -m "release: vX.Y.Z"`
6. `git push origin main --tags`
7. GitHub Actions builds binaries and creates the release automatically

---

## 22. Desktop notifications

Yes, a CLI app can push OS-level toast notifications — the terminal doesn't need
to be in focus. The approach depends on platform but `plyer` abstracts it cleanly.

### How it works

```python
from plyer import notification   # pip install plyer

notification.notify(
    title="Asher — Cat Detected",
    message="Cycle halted at 14:32. Check the litter box.",
    app_name="Asher CLI",
    timeout=8,          # seconds before auto-dismiss
)
```

That's it. On Windows this fires a native Action Center toast. On macOS it goes
through Notification Center. On Linux it uses `libnotify` (`notify-send`).

### Installation

```bash
pip install plyer
```

Add to `pyproject.toml`:
```toml
dependencies = [
    ...
    "plyer>=2.1",
]
```

`plyer` is pure-Python with no C extensions — no binary complications for
PyInstaller packaging.

### When to notify

Only notify on **state transitions** (fault appeared, not "fault is still
active"). Wire into `_refresh_faults` from §9c:

```python
from plyer import notification as _notify

NOTIFY_EVENTS = {
    "CAT DETECTED — cycle halted":          ("Asher — Cat Detected",    8),
    "PINCH DETECT — possible obstruction":  ("Asher — Safety Cutoff",   10),
    "GLOBE MOTOR FAULT":                    ("Asher — Motor Fault",      0),  # 0 = persistent
    "DRAWER FULL — empty now":              ("Asher — Drawer Full",      8),
}

def _refresh_faults(self, robot) -> None:
    current = set(label for label, _ in self._check_faults(robot))
    for label in current - self.prev_faults:           # newly appeared
        self._log_err(f"FAULT: {label}")
        if label in NOTIFY_EVENTS:
            title, timeout = NOTIFY_EVENTS[label]
            _notify.notify(title=title, message=label,
                           app_name="Asher CLI", timeout=timeout)
    for label in self.prev_faults - current:           # cleared
        self._log_ok(f"Cleared: {label}")
    self.prev_faults = current
```

### Sound alert alongside the toast

On Windows, `winsound` is stdlib (no install needed):

```python
import sys, winsound

def _alert_sound(critical: bool = False) -> None:
    if sys.platform != "win32":
        print("\a", end="", flush=True)   # terminal bell on macOS/Linux
        return
    freq = 880 if critical else 440
    winsound.Beep(freq, 300)
```

Call `_alert_sound(critical=True)` for pinch/cat-detected, `_alert_sound()` for
drawer-full and hardware faults.

### `/notify` slash command — opt-in control

```
/notify           show current notification settings
/notify on        enable desktop notifications (default)
/notify off       disable all notifications
/notify sound off disable sound only
/notify test      fire a test notification immediately
```

Persist the preference in `config.json` (§10):
```json
{ "notifications": true, "notification_sound": true }
```

### Platform note (Windows-specific refinement)

`plyer` on Windows uses `win10toast` under the hood, which works fine but
produces older-style balloon tips on some Windows 11 builds. For a sharper
Windows 11 toast (with the app icon and action buttons), `winotify` is a
drop-in upgrade:

```python
try:
    from winotify import Notification, audio   # pip install winotify
    def _toast(title, msg, timeout):
        n = Notification(app_id="Asher CLI", title=title, msg=msg, duration="short")
        n.set_audio(audio.Default, loop=False)
        n.show()
except ImportError:
    from plyer import notification as _plyer
    def _toast(title, msg, timeout):
        _plyer.notify(title=title, message=msg, app_name="Asher CLI", timeout=timeout)
```

`winotify` is Windows-only; the `ImportError` fallback keeps the code
cross-platform.

---

## 23. Tab completion for slash commands

Inspired by Claude Code's `/` menu — when the user types `/` into the command
input, a completion overlay appears above the input bar listing all slash
commands. Narrows in real time as they type.

### Behaviour

```
/ro[b...]
  ┌──────────────────────────────────────┐
  │  /robot    switch active robot       │
  │  /refresh  change poll interval      │
  └──────────────────────────────────────┘
```

- Overlay appears immediately on `/` keypress
- Filtered as the user continues typing (prefix match)
- `Tab` or `↓` moves focus into the list; `↑` moves back to the input
- `Enter` on a completion fills the command; `Escape` dismisses without filling
- Unknown `/xyz` commands fall through to `_run_slash_cmd` with the current
  "unknown slash command" warning — completion is an enhancement, not a gate

### Textual implementation

A `ListView` (or plain `Container` of `Static` rows) mounted in `#main-area`
or just above `#input-bar`, hidden by default. Shown/hidden reactively as the
`Input.Changed` event fires:

```python
def on_input_changed(self, event: Input.Changed) -> None:
    raw = event.value
    overlay = self.query_one("#completion-overlay")
    if raw.startswith("/") and len(raw) > 0:
        prefix = raw[1:].lower()
        matches = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(prefix)]
        overlay.display = bool(matches)
        # rebuild rows...
    else:
        overlay.display = False
```

`SLASH_COMMANDS` is a dict `{name: description}` imported from
`asher/slash-commands/__init__.py`, making the registry the single source of
truth for both dispatch and completion.

### CSS sketch

```css
#completion-overlay {
    dock: bottom;
    offset-y: -3;          /* sit just above the input bar */
    background: #161b22;
    border: solid #30363d;
    width: 48;
    height: auto;
    max-height: 8;
    padding: 0 1;
    display: none;
    layer: overlay;
}

.completion-row {
    height: 1;
    padding: 0 1;
    color: #e6edf3;
}

.completion-row.--highlight {
    background: #1f6feb33;
    color: #58a6ff;
}

.completion-desc {
    color: #484f58;
}
```

---

## 24. Version display

`VERSION` is already read from `importlib.metadata` and shown in the title
chip of the status bar:

```
◆ Asher CLI v1.0.0   [robot name]   ● ONLINE   [Ready]
```

The `_refresh_title()` method in `asher/ui/__init__.py` builds this; version
falls back to `"dev"` when running from source without `pip install -e .`.

### `/version` slash command

A convenience command that prints version info to the log without requiring
the user to look at the status bar:

```
  Asher CLI v1.0.0
  Python 3.12.3
  pylitterbot 3.x.x
  textual 0.x.x
```

```python
async def _slash_version(self) -> None:
    import sys
    from importlib.metadata import version as pkg_version, PackageNotFoundError

    def _v(pkg):
        try:
            return pkg_version(pkg)
        except PackageNotFoundError:
            return "?"

    self._log_info(f"Asher CLI v{_v('asher-cli')}")
    self._log_info(f"Python {sys.version.split()[0]}")
    self._log_info(f"pylitterbot {_v('pylitterbot')}")
    self._log_info(f"textual {_v('textual')}")
```

### ~~Status bar title — model badge~~ ✅

The `#robot-lbl` widget already shows the model type appended to the robot name:

```
◆ Asher CLI v1.0.0   Idiot Box  LR4   ● ONLINE   ⟳ Cycling
```

Implemented via `robot_model(r)` in `asher/helpers.py`, called from `_refresh_status()` in `asher/monitoring/__init__.py`.

---

## 25. Headless CLI export — automate history without the TUI or MCP

`export [days|month]` (§2) already writes activity history to CSV, but only
from *inside* the running interactive TUI — a human has to launch `asher`,
wait for it to connect, and type the command. That's unusable from cron,
Windows Task Scheduler, or a systemd timer. The MCP bridge (`/mcp`, shipped)
solves automation for an AI assistant talking to the robot, but it doesn't
help someone who just wants `asher --export 7` in a nightly script with no
Claude Desktop involved at all.

### Command syntax

```
asher --export 7                        export last 7 days to the default path
asher --export 7 --output ~/hist.csv    explicit output path
asher --export month --robot "Asher 2"  export 30 days for a specific robot
```

No flags → today's behavior unchanged: launches the interactive TUI. Any
recognized flag → run headlessly and exit; the Textual `App` is never
constructed, so this works over SSH, in a container, or from Task Scheduler
with no terminal attached.

### Entry point changes

`asher/__main__.py` parses `sys.argv` with `argparse` *before* deciding
whether to build `AsherApp`:

```python
def main() -> None:
    args = _parse_args()
    if args.export is not None:
        sys.exit(asyncio.run(_run_headless_export(args)))
    AsherApp().run()
```

### Decouple `_run_export` from Textual

`_run_export(app, days)` in `asher/commands/__init__.py` currently logs via
`app._log_info` / `_log_err` / `_log_ok` (RichLog writes) and always opens
the output folder in the OS file explorer — neither makes sense headlessly
(no widget tree, no desktop session on a server). Split the CSV-writing core
out into a plain function both paths share:

```python
async def build_history_csv(
    robot: RobotProtocol, pets: list, days: int, dest: Path,
) -> None:
    """Pure logic: fetch, filter, write. No Textual, no I/O side effects beyond dest."""
    ...

async def _run_export(app: AsherApp, days: int) -> None:
    # existing TUI path: resolve dest via app, call build_history_csv,
    # log via app._log_*, then _open_folder(dest)

async def _run_headless_export(args: argparse.Namespace) -> int:
    # connect via keyring -> .env (same priority as _connect_worker), no
    # interactive login possible - print a clear error and exit 1 if missing
    # resolve robot by --robot or keyring preferred_robot or robots[0]
    # call build_history_csv, print plain text to stdout/stderr, no folder-open
```

### Credentials — same priority, no interactive fallback

Headless mode can't prompt for a password. Priority stays keyring → `.env`,
but if neither has credentials, print an actionable error and exit non-zero
rather than starting the inline login flow (there's no command bar to type
into). This mirrors the constraint already documented for the MCP bridge:
a scheduled task's environment can't be assumed to match the project's
working directory, so `.env` discovery should not rely on `find_dotenv()`'s
upward directory search — same caveat as `asher/mcp_bridge.py`.

### Exit codes (for shell scripting)

| Code | Meaning |
|---|---|
| `0` | Export succeeded |
| `1` | No credentials found (keyring or `.env`) |
| `2` | Connection or API failure |
| `3` | Failed to write the CSV (permissions, disk full) |
| `4` | `--robot` selector matched no robot on the account |

### Example automation

```bash
# crontab -e — nightly export at 03:00
0 3 * * * /usr/bin/env asher --export 7 --output /home/me/litter-history.csv >> /var/log/asher-export.log 2>&1
```

```powershell
# Windows Task Scheduler action
asher.exe --export 7 --output C:\Users\me\litter-history.csv
```

### Testing

No Textual `Pilot` needed — `build_history_csv` and `_run_headless_export`
are plain async functions, testable the same way as `mcp_bridge.main()`
(§ MCP bridge): mock `Account.connect`, mock `robot.get_activity_history`,
assert on the written CSV content and the returned exit code.

---

## 26. Remote MCP connector — access the robot from claude.ai, mobile, Cowork

The `/mcp` bridge (shipped) only works in Claude **Desktop**, because it's a
local stdio server Desktop spawns as a subprocess on the same machine. To use
it from claude.ai in a browser, the mobile app, or Cowork, it needs to become
a **remote** MCP server: a service with a public HTTPS URL that Claude's
cloud infrastructure calls directly, added via Settings → Connectors → Add
custom connector. This is a materially bigger project than the local bridge,
not an extension of it — different transport, different hosting model,
different credential-storage threat model, and a real authentication layer.

### Transport: no pylitterbot fork needed

Checked directly against the latest pylitterbot (2025.6.0, ahead of the
`2025.5.0` currently pinned): `pylitterbot.mcp.__init__.main()` still just
calls `mcp.run()` with no arguments, which the underlying FastMCP object
defaults to `stdio`-only. But `run()` itself already supports `transport=
"sse"` and `transport="streamable-http"` — that's a capability of the `mcp`
SDK FastMCP wraps, just not exposed through pylitterbot's own CLI. Since both
`pylitterbot.mcp.server.mcp` (the FastMCP instance) and `pylitterbot.mcp.tools`
(the tool registrations) are public and importable, a remote launcher can
reuse them directly with no upstream patch:

```python
# asher/mcp_remote.py (sketch — not yet written)
from pylitterbot.mcp.server import mcp
import pylitterbot.mcp.tools  # noqa: F401 — registers the tools

def main() -> None:
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

### Hosting

Needs a publicly reachable HTTPS endpoint — Claude's cloud calls the server
directly, not through the user's machine (true even when using Claude
Desktop for the local case, which is why local-only doesn't extend to other
clients). Options: a small always-on VPS, Fly.io, Render, or a Cloudflare
Worker (serverless, colder start but near-zero idle cost for a
low-traffic personal tool). TLS termination and the public domain are the
host's job either way.

### Authentication — the actual hard part

Anthropic's docs are explicit: OAuth is required for any connector touching
private user data, and a personal litter box (control + activity history +
pet data) clearly qualifies. The MCP spec mandates **OAuth 2.1 with PKCE**
(S256), no implicit grant, exact redirect-URI matching. Claude supports three
registration modes — Dynamic Client Registration, Client ID Metadata
Documents, or Anthropic holding credentials directly — DCR or CIMD is the
right choice for a self-hosted personal server. This means standing up (or
reusing a library for) a minimal OAuth 2.1 authorization server in front of
the MCP endpoint — there's no "just add a bearer token" shortcut available
for this use case. This is the long pole, not the transport change above.

### Credential storage moves off the local keyring

The whole point of the local `/mcp` bridge (§ MCP bridge, shipped) was
keeping Whisker credentials in the OS keyring, never on disk in plaintext.
A remote server can't use the local keyring at all — it runs on a VPS/Fly.io/
Cloudflare box, not the user's machine. Credentials would live as that host's
own secret store instead (Fly.io secrets, Render env vars, Cloudflare Worker
secrets) — a reasonable place for a secret, but a different threat model:
now an internet-reachable service (behind the OAuth layer above) holds the
credentials and can control a physical device, rather than a process a local
user's OS session spawns on demand.

### Why this is a separate, larger item

- New transport code (small, sketched above)
- Hosting: pick a platform, deploy, keep it patched and running
- OAuth 2.1 authorization server: the real engineering cost
- Credentials move from local keyring to cloud secrets — explicit tradeoff,
  not a strict improvement
- Ongoing hosting cost/maintenance vs. the local bridge's zero-infrastructure
  design

Reasonable to treat as an optional stretch goal, not a natural next step
after the local bridge — evaluate whether cross-device access is worth the
OAuth + hosting lift before starting.

---

## Priority suggestion

Ranked by user-visible impact vs. implementation effort:

### Foundation ✅ (done)

1. ~~**`pyproject.toml` + `importlib.metadata` version**~~ — single source of truth, packaging unlocked
2. ~~**Architecture refactor**~~ — `asher/` package with `helpers.py`, `cats.py`, `app.py`; mixin split
3. ~~**Lint + test CI**~~ — `ruff` + `mypy` + `pytest` in `.github/workflows/ci.yml`
4. ~~**Keyring credential storage**~~ — `_keyring_load/save/delete`; credentials persist across restarts
5. ~~**Slash command dispatch + `/login` `/logout` `/exit` `/help`**~~ — inline login flow, no restart needed
6. ~~**PyPI release workflow**~~ — `release.yml` triggers on `release/*` branches; OIDC trusted publisher
7. ~~**Status bar: litter level**~~ ✅ — `#litter-lbl` shown in second row
8. ~~**Status bar: panel lock indicator**~~ ✅ — `#lock-lbl` shown in top row (`⊘ Locked` / `□ Unlocked`)
9. ~~**Robot model badge in status bar**~~ ✅ — `robot_model(r)` appended to `#robot-lbl` (e.g. `Idiot Box  LR4`)
10. ~~**Status color-coding**~~ ✅ — `#online-lbl` shows contextual colored labels: `~ Cat inside`, `⟳ Cycling`, `⏸ Paused`, `✓ Cycle done`, `⚠ Drawer full`, `○ OFFLINE`

### High-value features (biggest user-visible wins)

1. **History export to CSV** (§2) — `export [days|month]` command; writes to `~/Downloads`, opens folder in OS explorer
2. **Cat panel status badges** (§18) — lock, sleep, night light, wait time under the art; high visibility, one-afternoon job
3. ~~**WebSocket subscription**~~ ✅ — real-time push updates live; 5-min poll fallback for activity history
4. **Real-time cycling indicator with elapsed time** (§11) — extend the existing `⟳ Cycling` label to show elapsed time: `⟳ Cycling 0:42`; needs a per-second tick timer active only during a cycle
5. **Token persistence** (§13) — skip password re-entry on every run
6. **Fault & safety monitoring** (§9) — cat detected, pinch, motor faults; banner + log transition + cat alert mode
7. **Readable history events** (§11) — map raw pylitterbot strings to human labels with weight, pet name, and colour
8. **History pager sub-view** (§11) — scrollable in-log display with pagination; `history 100` vs current hardcoded 25-event dump

### Commands & slash system

1. ~~**`/robot` and `/robots` slash commands**~~ ✅ — `/robots` lists, `/robot <idx|name>` switches, keyring-persisted
2. ~~**`export` command**~~ ✅ (§2) — activity history to CSV; writes to `~/Downloads`, opens folder in OS explorer
3. ~~**`/pet` slash command**~~ ✅ (§1, §14) — `/pet` lists, `/pet <idx|name>` switches; `_active_pet_idx` persists for session
4. ~~**`/cat`, `/refresh`, `/config` slash commands**~~ ✅ (§1) — cat panel toggle + colour, poll interval control, runtime config dump
5. **Tab-completion for slash commands** (§23) — Claude Code-style overlay dropdown on `/` keypress; single-source registry drives both dispatch and completion
6. **`/version` slash command** (§24) — print Python/package versions to log; model badge in status bar is already done
7. **`wait-time`, `power`, `rename`, `insight` commands** (§3) — each is a two-line wiring job
8. **Sleep schedule viewer** (§8) — read-only first, config wizard later
9. **Headless CLI export** (§25) — `asher --export 7` for cron/Task Scheduler automation, no TUI or Claude Desktop needed

### Release pipeline

1. ~~**PyPI publish**~~ (§15) ✅ — `release.yml` live; push `release/x.y.z` branch to publish
2. ~~**CI/CD pipeline**~~ ✅ — lint + test + release workflows in `.github/workflows/`
3. **Versioning discipline** (§20) — `hatch version`, `CHANGELOG.md`, signed tags
4. **Standalone binary** (§16) — PyInstaller `.exe` + macOS/Linux builds via CI matrix
5. **Dependabot / Renovate** (§21) — automated dependency PRs, `pylitterbot` pinned to manual review

### Device & platform expansion

1. **LR5 extras** (§4) — privacy, volume, camera, night-light colour — detect model first
2. **Feeder robot support** (§5) — snack, gravity, meal size commands
3. **Multi-robot tab view** (§11) — `TabbedContent` widget when `len(robots) > 1`

### Polish & stretch

1. **Config persistence** (`config.json`, §10) — runtime settings survive restarts
2. **Weight sparkline in cat panel** (§7) — 7-day ASCII chart; delightful but non-essential
3. **Desktop notifications** (§22) — `plyer` toasts + `winsound` bell on fault/cat-detected; `/notify on|off` command
4. **Dark/light theme toggle** (§12) — CSS variable swap; nice-to-have but not critical
5. **E2E test harness** (§17) — Textual Pilot tests for critical user flows; good for preventing regressions but requires maintenance
6. **Refactor to be more clean code** — base command class with a property to distinguish slash vs bare commands; reduces duplication and makes adding commands easier
7. **LR5/Evo specific features** — camera snapshots, night light color control, hopper management (whatever pylitterbot exposes)
8. **Remote MCP connector** (§26) — access from claude.ai/mobile/Cowork, not just Desktop; requires hosting + an OAuth 2.1 authorization server, bigger lift than the local `/mcp` bridge and a different credential-storage tradeoff — evaluate demand before starting



