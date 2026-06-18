# Asher CLI — Roadmap & Feature Gaps

Current state, missing functionality, and suggested additions — grounded in what
`pylitterbot` actually exposes today.

---

## What's working now

| Area | Status |
|---|---|
| Auth — keyring (primary) → `.env` fallback → `/login` prompt | ✅ |
| Connect & load robots | ✅ |
| Status bar (name, online, drawer %, last seen, pet weight) | ✅ |
| Pet name from Whisker account profile | ✅ |
| Commands: clean, status, lock, unlock, sleep, wake, night-light, history, help, clear, quit | ✅ |
| Slash commands: `/login`, `/logout`, `/exit`, `/help` | ✅ |
| Inline login flow (email → password in command bar, no restart) | ✅ |
| `LoginScreen` modal (`auth.py`) — available for future use | ✅ |
| Activity history (`get_activity_history`) | ✅ |
| Cat animation panel with mode changes | ✅ |
| Command history (↑/↓) | ✅ |
| WebSocket real-time updates (LR4 primary; poll fallback every 5 min for activity history) | ✅ |
| LR4 / LR5 / LR3 polymorphic support | ✅ (getattr fallback) |
| PyPI release workflow (`release.yml` — `release/*` branches) | ✅ |

---

## 1. Slash commands — configuration at runtime

Everything below would be `/command` style, similar to Claude Code, so they're
visually distinct from robot-action commands.

### `/robot` — switch active robot

```
/robot            list all robots on the account
/robot 0          switch to robot by index
/robot "Asher 2"  switch to robot by name
```

The app already fetches all robots on connect — switching just needs
`self._robot = robots[n]` and a status bar refresh. Useful for households with
multiple units (e.g. LR4 + LR5).

### ~~`/auth`~~ → `/login` ✅ — update credentials without restart

`/login` starts an inline credential entry flow directly in the command bar:
the prompt label changes to `email ›` then `password ›`, the password field
masks input as `••••••••`, and on submit the credentials are saved to the OS
keyring and the connection is re-established — no restart needed.

`/logout` disconnects, deletes credentials from keyring, and prompts
`/login` to sign back in.

### `/cat` — configure the cat animation

```
/cat off          hide the cat panel entirely (more log space)
/cat on           show the cat panel
/cat color blue   change the cat art colour (#58a6ff default)
/cat style 2      pick an alternate ASCII art set
```

The panel is currently a fixed 24-column sidebar. Toggling it requires adding
`display: none` to `#cat-panel` via `add_class` / `remove_class`.

### `/refresh` — change the poll interval

```
/refresh 10       poll every 10 s
/refresh 60       poll every 60 s (lighter on API)
/refresh off      disable auto-refresh (manual `status` only)
```

`self.set_interval` can't be changed after mount — needs to cancel the existing
timer and create a new one, or gate the `_poll_status_interval` worker behind a
configurable flag.

### `/config` — show current runtime config

```
/config
  robot          Idiot Box (LR4, index 0)
  refresh        30 s
  cat panel      on / blue
  credentials    threeheadeddoggy@gmail.com (from .env)
```

Read-only dump of the app's current settings. No API call needed.

### `/pet` — switch which pet's name/weight is shown

```
/pet              list pets on the account
/pet 0            show Whisker pet at index 0 in the status bar
```

`account.pets` already contains all pet profiles. The status bar currently hard-
codes `pets[0]`. With multiple cats this matters.

---

## 2. Missing robot commands

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

## 3. LR5-only features

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

## 4. Feeder Robot support

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

## 5. Real-time WebSocket updates (replace polling)

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

## 6. Pet features

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

## 7. Sleep schedule

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

## 8. Fault monitoring & alerts

### 8a. Safety events (highest priority — surface immediately)

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

### 8b. Hardware faults

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

### 8c. Surfacing strategy

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

**Desktop notification** (see §11) — cat detected and pinch faults are good
candidates for an OS-level `plyer` notification, since the user may not be
watching the terminal.

---

## 9. Config file persistence

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

## 10. UI / UX gaps

### Status bar: litter level
`robot.litter_level` and `robot.litter_level_state` (Low / Nominal / High) are
never shown. Could sit next to the drawer bar:

```
Drawer [████░░░░] 48%   Litter: Nominal   Asher 🐱 9.1 lb
```

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
The distinction matters: fault detection (§8) is a safety event that halted a
cycle; live presence is ambient state while a cat is using the box.

**Status bar** — add a `🐱 IN` badge in the second row that appears while
`is_cat_detected` is true and disappears when the cat leaves:

```
Drawer [████░░░░] 48%   Litter: Nominal   🐱 IN   Asher 9.1 lb   7m ago
```

**Cat panel** — switch the cat art to a `"present"` mode (new state, cat-in-box
ASCII art or a distinct label like `"visiting…"`). Switch back to `idle` once
`is_cat_detected` returns false.

WebSocket (§5) makes this responsive — with 30 s polling you'll likely miss the
entire visit. With real-time push the badge appears the moment the sensor trips.

---

### Real-time cycling indicator (requires WebSockets)

`LitterBoxStatus.CLEAN_CYCLE` is already caught by the `[RDY]` status chip,
but polling every 30 s means a full clean cycle (typically 2–4 min) can start
and finish between polls, showing only `Ready` to the user the whole time.

**What's needed:**
- WebSocket subscription (§5) — `robot.subscribe()` fires `EVENT_UPDATE`
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

This is the primary reason to implement WebSocket (§5) — the cycling indicator
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

## 11. Stretch / nice-to-have

| Idea | Notes |
|---|---|
| Desktop notifications | `plyer` / `winotify` toasts + `winsound` bell — see §20 |
| Export to CSV | `history export` → writes activity to `.csv` |
| Weight sparkline in cat panel | Replace idle cat with a 7-day weight chart |
| Dark / light theme toggle | `/theme light` swaps colour palette |
| Startup robot selection | If multiple robots, prompt on launch instead of defaulting to `[0]` |
| `.env` wizard | First-run prompt if no `.env` found, writes creds interactively |
| Reconnect on network drop | Currently a failed poll is silently swallowed; should show a banner and retry |

---

## 12. Account management

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

## 13. Slash commands — full design spec

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
| `/pet [index\|name]` | List or switch which pet shows in status bar | `self._active_pet = pets[n]` |
| `/account` | Show account info | `account.user_id`, email from keyring |
| `/refresh [seconds\|off]` | Change poll interval | Cancel + recreate `set_interval` timer |
| `/cat [on\|off]` | Show/hide cat panel | `add_class` / `remove_class` on `#cat-panel` |
| `/cat color <hex>` | Change cat art colour | Update `_cat_color` attr, redraw |
| `/cat style <n>` | Switch ASCII art set | Swap `CATS` dict at runtime |
| `/config` | Show all current settings | Read-only dump |
| `/config set <key> <val>` | Change a setting | Write to `config.json` |
| `/theme [dark\|light]` | Swap colour scheme | Swap Textual CSS variables |
| `/log [n]` | Set max log lines to keep | `RichLog(max_lines=n)` |
| `/export [path]` | Export last activity to CSV | Write `activity_export.csv` |
| `/notify [on\|off\|test]` | Desktop notification settings | See §20 |

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

## 14. PyPI publishing — `pip install asher-cli`

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

## 15. Standalone binary — no Python required

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

## 15. Testing

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

## 16. Cat panel — robot status badges underneath the art

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
collapsible (the `/cat off` slash command from §13) so users on small terminals
can reclaim the space.

---

## 17. Architecture refactor — modular structure

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

## 18. Versioning

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

## 19. CI / CD pipeline

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

## 20. Desktop notifications

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
active"). Wire into `_refresh_faults` from §8c:

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

Persist the preference in `config.json` (§9):
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

## 21. Tab completion for slash commands

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

## 22. Version display

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

### Status bar title — model badge

Once the robot is connected, show its model type next to the name so the user
knows at a glance which API surface is available:

```
◆ Asher CLI v1.0.0   Idiot Box (LR4)   ● ONLINE   [Ready]
```

`type(robot).__name__` already returns `"LitterRobot4"`, `"LitterRobot5"`, etc.
Strip the `"LitterRobot"` prefix for display: `model = type(robot).__name__.replace("LitterRobot", "LR")`.

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

### High-value features (biggest user-visible wins)

4. **Cat panel status badges** (§16) — lock, sleep, night light, wait time under the art; high visibility, one-afternoon job
5. **WebSocket subscription** (§5) — replace 30 s polling with real-time push updates; prerequisite for live cat presence and cycling indicator
6. **Live cat presence indicator** (§10) — `🐱 IN` badge + `"present"` cat mode while `is_cat_detected` is true; requires WebSocket (§5) to be useful
7. **Real-time cycling indicator** (§10) — animated `[⠙ CYCLING 0:42]` chip with elapsed time; requires WebSocket (§5)
8. **Token persistence** (§12) — skip password re-entry on every run
9. **Fault & safety monitoring** (§8) — cat detected, pinch, motor faults; banner + log transition + cat alert mode
10. **Status color-coding** (§10) — `LitterBoxStatus` → colour in status bar and cat badges
11. **Readable history events** (§10) — map raw pylitterbot strings to human labels with weight, pet name, and colour
12. **History pager sub-view** (§10) — `push_screen(HistoryScreen)` with Page Up/Down and `q` to dismiss; events no longer dump into the main log

### Commands & slash system

9. **`/robot` and `/pet` slash commands** (§1, §13) — robot/pet switcher; needs `/account` setup first
10. **Tab-completion for slash commands** (§21) — Claude Code-style overlay dropdown on `/` keypress; single-source registry drives both dispatch and completion
11. **`/version` command + model badge in status bar** (§22) — show Python/package versions in log; show `LR4`/`LR5` model next to robot name
12. **`wait-time`, `power`, `rename`, `insight` commands** (§2) — each is a two-line wiring job
13. **Sleep schedule viewer** (§7) — read-only first, config wizard later

### Release pipeline

13. ~~**PyPI publish**~~ (§14) ✅ — `release.yml` live; push `release/x.y.z` branch to publish
14. **Versioning discipline** (§18) — `hatch version`, `CHANGELOG.md`, signed tags
15. **Standalone binary** (§15) — PyInstaller `.exe` + macOS/Linux builds via CI matrix
16. **Dependabot / Renovate** (§19) — automated dependency PRs, `pylitterbot` pinned to manual review

### Device & platform expansion

17. **LR5 extras** (§3) — privacy, volume, camera, night-light colour — detect model first
18. **Feeder robot support** (§4) — snack, gravity, meal size commands
19. **Multi-robot tab view** (§10) — `TabbedContent` widget when `len(robots) > 1`

### Polish & stretch

20. **Config persistence** (`config.json`, §9) — runtime settings survive restarts
21. **Weight sparkline in cat panel** (§6) — 7-day ASCII chart; delightful but non-essential
22. **Desktop notifications** (§20) — `plyer` toasts + `winsound` bell on fault/cat-detected; `/notify on|off` command
23. **Dark/light theme toggle** (§11) — CSS variable swap; nice-to-have but not critical
24. **Startup animation** (§11) — cute but adds friction to quick status checks; could be opt-in
25. **E2E test harness** (§15) — Textual Pilot tests for critical user flows; good for preventing regressions but requires maintenance
26. **Refactor to be more clean code** - example: have a base command class, and have a property to determine whether its a slash command or not, instead of having two separate methods for slash and non-slash commands. This would reduce code duplication and make it easier to add new commands in the future.


