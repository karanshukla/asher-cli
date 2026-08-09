# Asher CLI — Roadmap & Feature Gaps

Current state, missing functionality, and suggested additions — grounded in what
`pylitterbot` actually exposes today.

> Completed items are marked `~~strikethrough~~ ✅` inline and their full design
> notes have been moved to [`roadmap-archive/`](roadmap-archive/README.md)
> so this file reads as a short list of what's left to build.

---

## What's working now

| Area | Status |
|---|---|
| Auth — keyring (primary) → `.env` fallback → `/login` prompt | ✅ |
| Connect & load robots | ✅ |
| Status bar top row — name + model, contextual online label (Cycling/Paused/Cat inside/Cycle done/Drawer full/Offline), night light mode + brightness, panel lock indicator | ✅ |
| Status bar second row — drawer %, litter %, cat weight (with pet name), last visit | ✅ |
| Pet name from Whisker account profile | ✅ |
| Commands: clean, status, info, lock, unlock, sleep, wake, night-light on/off/auto, night-light-brightness, wait-time, power on/off, rename, insight, privacy on/off, volume, camera-audio on/off, drawer-reset (LR5 extras via adapter; gracefully refused on LR3/LR4), history, export [days\|month], help, clear, quit | ✅ |
| Slash commands: `/login`, `/logout`, `/exit`, `/help`, `/robots`, `/robot <index\|name>`, `/pets`, `/pet <index\|name>`, `/cat on\|off\|colour <hex>`, `/refresh [seconds\|off]`, `/config`, `/mcp on\|off\|status` | ✅ |
| MCP bridge — keyring-backed `pylitterbot[mcp]` launcher, auto-installs the extra, writes/removes the Claude Desktop config entry (incl. Windows MSIX path) | ✅ |
| Inline login flow (email → password in command bar, no restart) | ✅ |
| `LoginScreen` modal (`auth.py`) — available for future use | ✅ |
| Activity history (`get_activity_history`) | ✅ |
| Cat animation panel with mode changes | ✅ |
| Cat panel — mode label + status badges (status chip, lock, night light, sleep, wait) under the art | ✅ |
| Fault & safety monitoring — `#fault-banner` (in cat panel) driven by `asher/faults.py`; transition-logged; `d` to dismiss | ✅ |
| Real-time cycling indicator with elapsed time (`⟳ Cycling M:SS`) | ✅ |
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
/cat colour <hex>     change the cat art colour (color also accepted)
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

## ~~2. History export to CSV~~ ✅ → [archived](roadmap-archive/history-export.md)

`export [days|month]` writes activity history to `~/Downloads/asher-<serial>-<date>.csv` and opens the folder. Shipped — full design notes moved to the archive.

---

## 3. Missing robot commands

Real `LitterRobot3` / `LitterRobot4` / `LitterRobot5` methods in pylitterbot
that weren't wired up. The non-destructive ones are now live; the destructive
ones (`reset`, `reset-settings`, `firmware` update) are deliberately omitted.

### ~~`status` vs `info` — split the current status command~~ ✅

`status` is now the trimmed at-a-glance view — the same information shown in
the status bar, refreshed on demand:

```
  Online         yes
  Status         Ready
  Drawer         48%
  Last seen      4m ago
  Cat weight     9.1 lb
```

`info` handles the full property dump — serial number, firmware version, wait
time, all boolean flags, model type, etc. Useful for debugging or first-time
setup, not something you need every time you check in. Optional LR4/LR5-only
properties (`firmware`, `clean_cycle_wait_time_minutes`) are read via
`getattr` so `info` degrades gracefully on LR3 (renders `—` instead of
crashing):

```
  Name           Idiot Box
  Model          LR4  (LitterRobot4)
  Serial         LR4C012345
  Firmware       ESP: 1.1.50  PIC: 1.0.11
  Wait time      7 min
  Sleeping       no
  Panel locked   no
  Night light    off
  Drawer         48%
  Online         yes
  Last seen      4m ago
```

### ~~`power on` / `power off`~~ ✅
```python
await robot.set_power_status(True / False)
```
Hard-power the unit on or off. Useful for scheduled restarts.

### ~~`wait-time <minutes>`~~ ✅
```python
await robot.set_wait_time(minutes)   # VALID_WAIT_TIMES: 3, 7, 15, 25, 30
```
Sets how many minutes the robot waits after a cat visit before cleaning.
With no argument it prints the current value and the valid set; an out-of-set
value is rejected before hitting the API. Current value is also surfaced in
`info` output.

### ~~`panel-brightness <low|medium|high>`~~ ✅

```python
from pylitterbot.enums import BrightnessLevel
await robot.set_panel_brightness(BrightnessLevel.LOW)
```

An earlier audit claimed `set_panel_brightness` did not exist in
`pylitterbot==2025.6.2` — that was wrong. Both the setter and the
`panel_brightness` reader exist on `LitterRobot4` and `LitterRobot5`
(`BrightnessLevel`: LOW=25, MEDIUM=50, HIGH=100). The `panel-brightness`
command (alias `pb`) now routes through `LR4Adapter`/`LR5Adapter` and is
gracefully refused on the LR3 (no panel) via the base adapter fallback. Bare
invocation shows the current brightness.

### ~~`rename <new name>`~~ ✅
```python
await robot.set_name("new name")
```
Renames the unit in the Whisker cloud (persists across sessions). Multi-word
names are supported (`rename Idiot Box 2`); bare `rename` shows the current
name in the usage line.

### `reset` / `reset-settings` — deliberately omitted

```python
await robot.reset_settings() # settings reset only
```

`reset_settings()` exists on all three models; a full `reset()` does not.
These are destructive and irreversible cloud-side operations, so they're
intentionally left unwired. If added later, they must require a `--confirm`
flag or an interactive "are you sure?" prompt — a fat-fingered `reset` from
the command bar shouldn't be one keystroke away.

### `firmware` — deliberately omitted

```python
has_update = await robot.has_firmware_update()
details    = await robot.get_firmware_details()
```

Read-only firmware display is harmless and could be folded into `info` later,
but `robot.update_firmware()` is destructive (triggers a remote update on the
physical device) and is intentionally not wired up. Current firmware version
is already shown by `info` via the `firmware` property.

### ~~`insight [days]` — usage statistics~~ ✅
```python
insight = await robot.get_insight(days=30)
```
Renders total cycles, average cycles/day over the covered period, and the peak
day. Accepts a day count (`insight 7`) or `month` alias (= 30, the Whisker
ceiling):
```
  Cycles         42 (last 3 days)
  Avg/day        1.4
  Peak day       3 on 2026-07-20
```

---

## 4. LR5-only features

LR5 exposes additional capabilities that don't exist on LR4. The app detects
model type via the `RobotAdapter` pattern: the four interactive commands below
route through `LR5Adapter`, while the base `RobotAdapter` returns a
`"... is only available on the LR5"` message so typing them on an LR3/LR4 is
safe and informative rather than a crash.

### Shipped ✅

| Command | API | LR5 property |
|---|---|---|
| ~~`privacy on/off`~~ ✅ | `set_privacy_mode(bool)` | `privacy_mode` |
| ~~`volume <0-100>`~~ ✅ | `set_volume(int)` | `sound_volume` |
| ~~`camera-audio on/off`~~ ✅ | `set_camera_audio(bool)` | `camera_audio_enabled` |
| ~~`drawer-reset`~~ ✅ | `reset_waste_drawer()` | `is_drawer_removed` |

`volume` accepts `0-100` (the actual pylitterbot range, not the `0-10` listed
in earlier drafts of this table). Bare `volume` prints the current value
alongside the usage line. Adapter unit tests cover the happy path, rejection,
exceptions, and the LR3/LR4 "not supported" fallthrough for each command; pilot
tests in `tests/test_lr5_commands.py` exercise the command-bar dispatch end to
end against both an LR5 and an LR4 adapter.

### Not yet wired

| Command | API | LR5 property |
|---|---|---|
| `night-light color <hex>` | `set_night_light_settings(color=...)` | `night_light_color` |
| `filter reminder` | _(read-only)_ | `next_filter_replacement_date` |

`night-light color` is a natural follow-on — `LR5Adapter.set_night_light`
already calls `set_night_light_mode`; `set_night_light_settings(color=...)` is
the richer overload that also takes `mode`/`brightness`/`color`. `filter
reminder` is a read-only property that could slot into `info` output.

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

### ~~`sleep-schedule` — read-only viewer~~ ✅

The `sleep-schedule` (alias `sleepschedule`) command renders the per-day
sleep/wake window read-only. Days are sorted Mon→Sun (converted from pylitterbot's
Sun=0..Sat=6 `DayOfWeek`); enabled days show `22:00 → 07:00`, disabled days show
`off`. If `schedule.get_window()` returns an active window covering the current
time, the affected day(s) get a `● now` marker. When the whole schedule is
disabled it notes that and still lists the configured windows; when
`sleep_schedule is None` it warns that the unit is always awake and points at
`sleep`/`wake`. `_sleep_schedule` can raise on malformed data, so the whole read
is wrapped defensively and degrades to a `_log_err`. Works on LR3/LR4/LR5 — the
property exists on all three.

```
sleep-schedule            show current schedule ✅
sleep-schedule set        interactive wizard (or flags) — not yet
sleep-schedule Mon 22:00 07:00   set Monday sleep window — not yet
sleep-schedule disable    clear all days — not yet
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

## ~~9. Fault monitoring & alerts~~ ✅ → [archived](roadmap-archive/fault-monitoring.md)

Model-scoped fault detection (`asher/faults.py`) drives the in-panel `#fault-banner`; `d` dismisses. Shipped — full design notes moved to the archive.

---

## ~~10. Config file persistence~~ ✅ → [archived](roadmap-archive/config-persistence.md)

~/.asher-cli/config.json persists /refresh, /cat, /pet across restarts. Shipped — full design notes moved to the archive.

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
`wifi_mode_status` via `LR4Adapter`. Since SSID is unavailable, the `info`
command is where WiFi status is surfaced: the LR4 `wifi_mode_status` enum now
renders readably there (connected / connecting / fault / off / —). A
status-bar dot indicator remains unwired (nice-to-have).

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

### ~~Readable event labels (replace raw library strings)~~ ✅

The `history` command now renders translated, colour-coded labels instead of
raw pylitterbot enum strings. Cat-detection events append the pet name and
weight when available (`Cat detected  Asher  9.1 lb`), and unknown event
types fall through to the raw string in muted grey so new pylitterbot events
never break the display.

The label map and the pure `format_activity()` translator live in
`asher/activity_labels.py`, shared by both the `history` command and the
`export` CSV path so the two render events the same way. Timestamps also
gained the §11 refinement: same-day events show `HH:MM`, this-year events
show `mm/dd HH:MM`, and older events show the full `YYYY-MM-DD`.

**Example output:**
```
  14:22        Ready                          (muted grey)
  13:55        Clean cycle complete           (green)
  13:54        Cat detected  Asher  9.1 lb    (amber, with weight + pet)
  12:01        Drawer full — empty now        (red)
  06/14 11:30  Sleep mode on                  (muted)
```

Unit tests live in `tests/test_activity_labels.py` (17 cases covering the
label map, cat suffix logic, enum vs string actions, and unknown-event
fallback) — the module is pure and needs no Textual or event-loop harness.

### ~~History as a scrollable sub-view (pager mode)~~ ✅

`history` now pushes a `HistoryScreen` (a `ModalScreen` in
`asher/history_view.py`) over the main UI instead of dumping rows into the main
log, where they scrolled off as new output arrived. A `ScrollableContainer`
takes focus on mount, so the arrow keys, `Page Up`/`Page Down`, and
`Home`/`End` page through long histories natively; `q`, `Escape`, or `Enter`
pops back to the main view. A header bar shows the robot name and event count.

`history` also gained an optional count: bare `history` fetches 50 events (up
from the old hardcoded 25), `history 100` fetches more, and `history all`
fetches up to 500. The fetch/format logic lives in the pure
`format_history_rows()` helper (newest-first, shared timestamp rules from §11),
so the rendering stays identical to the old log rows. No new deps — just
`ScrollableContainer` + `ModalScreen` from Textual.

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

### ~~Real-time cycling indicator (requires WebSockets)~~ ✅

The `#online-lbl` chip now shows `⟳ Cycling  M:SS` with live elapsed time while
a `CLEAN_CYCLE`/`EMPTY_CYCLE` is active. `_cycle_start` is stamped on the
transition into a cycling status and a 1 s `_cycle_timer` (created lazily via
`set_interval`, stopped/null on any non-cycling status) re-renders the chip each
second via `_tick_cycle`. The `_cycling_chip()` helper is shared between the
timer and the `_refresh_status` cycling branch so they stay consistent. Because
`_refresh_status` fires on WebSocket push, the chip updates the moment the cycle
starts — no 30 s polling gap.

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

### Token persistence ✅ — avoid API re-auth on every run

`Account.__init__()` accepts a pre-existing `token` dict and a
`token_update_callback`; `connect()` with no username/password reuses a valid
token or silently refreshes it via the refresh token. The cached session token
is stored as a JSON blob in the OS keyring (key `"token"` under service
`asher-cli`), so subsequent launches skip the OAuth password login entirely —
faster startup, less password exposure, more resilient to rate-limiting.

`_connect_worker` tries the token first (via `_try_token_connect`), and only
falls back to the email/password path if the token is absent, expired, or
rejected — in which case the stale token is wiped so a poisoned token can't
loop. `token_update_callback=_keyring_save_token` is also wired into the
password-login `Account()` construction, so refreshes during a session are
captured for the next launch. Users only re-enter their password when the
refresh token itself expires (typically months).

Helpers in `asher/connection/__init__.py`:
- `_keyring_load_token() → dict | None` — returns the cached token or `None`
- `_keyring_save_token(token: dict | None)` — persists, or clears when `None`
- `_keyring_delete()` now also clears `"token"` (so `/logout` invalidates it)

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

Builds use `uv build` (the same command the release workflow runs):

```bash
# 1. Build the distribution
uv build
# → dist/asher_cli-X.Y.Z-py3-none-any.whl
# → dist/asher_cli-X.Y.Z.tar.gz

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

[`.github/workflows/release.yml`](../../.github/workflows/release.yml) is live —
see that file for the authoritative version (SHA-pinned actions). It is
triggered by pushing to any `release/*` branch (not tags — tags are for git
history only, not CI triggers), and runs three jobs:

1. **build** — `actions/checkout` (full history, `fetch-depth: 0`, for the
   changelog), `uv build`, uploads the `dist/` artifact.
2. **publish** — downloads the artifact and uses
   `pypa/gh-action-pypi-publish@release/v1` with **OIDC trusted publishing**
   (no stored API token). Runs in the `pypi` environment.
3. **github-release** — regenerates the release notes with `git-cliff` (same
   `cliff.toml` as the local `poe changelog` task) and creates the GitHub
   Release via `gh release create`, attaching the built wheels/sdist.

**Trusted publishing**: PyPI is configured to trust the OIDC token for
`karanshukla/asher-cli` → `release.yml` → `pypi` environment. No stored API
token needed.

**Hotfix flow** — branch from the last release branch directly, don't touch
`main`:

```bash
git checkout release/X.Y.Z
git checkout -b release/X.Y.(Z+1)
# cherry-pick fix, bump version in pyproject.toml
git push origin release/X.Y.(Z+1)   # → triggers publish
git tag vX.Y.(Z+1)                  # optional, for git history only
```

### Package release checklist

- [x] `bump-my-version bump minor|patch|major` — bumps version in `pyproject.toml`
  (auto-commits + tags)
- [x] `CHANGELOG.md` regenerated via `uv run poe changelog` (committed before
  the version bump)
- [x] `README.md` has `pip install asher-cli` install instructions
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

- [x] `pyproject.toml` with version, dependencies, entry point
- [x] `CHANGELOG.md` (auto-generated by git-cliff)
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

### Integration tests — pylitterbot mocking ✅

The `mock_robot` / `mock_account` fixtures in `tests/conftest.py` are wired into
command-handler tests via Textual's `Pilot` harness. Every command branch is
covered — robot commands (`test_commands_pilot.py`, `test_new_commands_pilot.py`,
`test_missing_robot_commands.py`), LR5 extras (`test_lr5_commands.py`), slash
commands (`test_app_pilot.py`, `test_commands_pilot.py`), and the export CSV
path. Tests drive the real command-bar dispatch (`pilot.press(...)`) against
mocked robots, asserting on side effects (robot API calls, log content,
keyring writes, cat mode). 300+ pilot tests across the suite.

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

### Code coverage ✅

`pytest-cov>=5.0` is in dev dependencies (`pyproject.toml`), with a
`[tool.coverage.run]` / `[tool.coverage.report]` block configured. A dedicated
`.github/workflows/coverage.yml` workflow runs
`pytest tests/ --cov=asher --cov-report=lcov --cov-report=term-missing` on a
daily cron (and manual dispatch) and uploads to Coveralls (badge in the README).

Run locally with a terminal report:

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

### Test structure ✅

```
tests/
  conftest.py                   ✅ shared fixtures (mock_robot, mock_account)
  testhelpers.py                ✅ fmt_ago, drawer_bar
  test_activity_labels.py       ✅ format_activity / ACTION_LABELS (pure)
  test_cats.py                  ✅ cat art data
  test_robot_adapters.py        ✅ LR3/4/5 adapters + make_adapter factory
  test_commands_pilot.py        ✅ robot + slash command handlers (Pilot)
  test_new_commands_pilot.py    ✅ /cat, /refresh, /config, /pet, export
  test_missing_robot_commands.py ✅ wait-time, power, rename, insight, status/info
  test_lr5_commands.py          ✅ LR5 extras (privacy, volume, camera-audio, drawer-reset)
  test_app_pilot.py             ✅ app-level Pilot flows
  test_auth.py / test_auth_pilot.py ✅ login flow
  test_connection.py / _mixin.py ✅ keyring + account connect
  test_monitoring.py            ✅ WebSocket + poll refresh
  test_mcp_*.py                 ✅ MCP bridge + config
  test_ui.py                    ✅ status bar rendering
```

`snapshots/` (baseline TUI screenshots via `textual-snapshot`) is the one
remaining item from the original suggestion that isn't yet in place.

---

## ~~18. Cat panel — robot status badges underneath the art~~ ✅ → [archived](roadmap-archive/cat-panel-badges.md)

#cat-status widget under the cat art (status chip, lock, sleep, night light, wait). Shipped — full design notes moved to the archive.

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
version = "0.2.0"
```

`asher/ui/__init__.py` reads it at runtime instead of hard-coding a version:

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

### Bumping the version ✅

The project uses [`bump-my-version`](https://github.com/callowayproject/bump-my-version),
configured in `pyproject.toml`:

```bash
uv run bump-my-version bump patch    # 0.2.0 → 0.2.1
uv run bump-my-version bump minor    # 0.2.0 → 0.3.0
uv run bump-my-version bump major    # 0.2.0 → 1.0.0
```

The `[tool.bumpversion]` block rewrites the version in `pyproject.toml`, and is
configured with `commit = true`, `tag = true`, `tag_name = "v{new_version}"`,
plus a `pre_commit_hooks` step that re-locks with `uv lock` — so a single bump
command rewrites the version, re-locks, commits, and tags in one step (the
README "Releasing" section documents the full flow). This is live and used for
every release.

### Git tagging convention

Every release gets a `v`-prefixed tag (created automatically by bump-my-version):

```bash
# created automatically by `bump-my-version bump ...`; push it manually:
git push origin vX.Y.Z
```

The `v` prefix is conventional. The release workflow keys off the
`release/*` *branch* name (not the tag) for the published version.

### Changelog — automated via git-cliff ✅

[`CHANGELOG.md`](../../CHANGELOG.md) is generated by
[git-cliff](https://git-cliff.org) from conventional-commit history, in
[Keep a Changelog](https://keepachangelog.com) format. The config lives in
[`cliff.toml`](../../cliff.toml) and groups commits by prefix (`feat` →
Features, `fix` → Bug Fixes, etc.), skipping merge/bump/Renovate noise.

**Local** — regenerate before cutting a release (idempotent; committed before
the version bump):

```bash
uv run poe changelog        # git cliff -o CHANGELOG.md
```

**CI** — the `github-release` job in `release.yml` runs
`git cliff --latest --strip header` to produce the GitHub Release body, so the
release notes always match the changelog. See §15 above for the workflow.

Because the same `cliff.toml` drives both, the GitHub Release body and
`CHANGELOG.md` cannot drift apart.

---

## 21. CI / CD pipeline

### Workflow overview

```
push / PR  ──► lint ──► test ──► build artifacts
                                       │
tag v*  ──────────────────────────►  release
                                    (attach binaries, publish changelog)
```

### `.github/workflows/ci.yml` — lint + test on every push ✅

Live and matches the spec below — `name: CI`, triggers on push to `main` and
PRs, `lint` job (`ruff check`, `ruff format --check`, `mypy`), `test` job with
the `["3.10","3.11","3.12"] × [ubuntu, windows, macos]` matrix running
`pytest tests/ -v --tb=short`. Actions are pinned to commit SHAs. A separate
`.github/workflows/coverage.yml` runs the coverage report on a daily cron and
uploads to Coveralls.

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

The live, SHA-pinned workflow is at
[`../../.github/workflows/release.yml`](../../.github/workflows/release.yml) —
read that file for the authoritative version rather than a copy here (a pasted
YAML in docs drifts from the real one). The previous design that embedded a
hypothetical PyInstaller-matrix + `softprops/action-gh-release` flow here was
aspirational and did not match what actually ships. The real workflow:

1. **build** — `uv build` (wheel + sdist), uploads `dist/` as an artifact.
2. **publish** — OIDC trusted publishing to PyPI (no API token).
3. **github-release** — regenerates release notes with `git cliff --latest`
   (same `cliff.toml` as `poe changelog`) and creates the GitHub Release,
   attaching the built wheels/sdist.

A standalone-binary build (PyInstaller/Nuitka matrix attaching `.exe`/binary
artifacts to the release) is described in §16 but not yet wired — that's a
stretch goal.

### Dependency automation ✅ (Renovate)

The project uses **Renovate** (`renovate.json`), not Dependabot — it handles
`uv.lock` better and is more configurable. The config extends
`config:recommended`, runs weekly (Mondays), and — critically for this project —
**pins `pylitterbot` to require manual review**: the Whisker API is
reverse-engineered and a minor version bump could change method names or
response schemas, so it should never be auto-merged. GitHub Actions are pinned
to commit SHAs and also bumped weekly.

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
- [ ] No new hard-coded `VERSION` strings (use `importlib.metadata`)
- [ ] Commit message follows conventional format (so git-cliff can group it)
```

### Code quality gates

| Tool | Purpose | Config file |
|---|---|---|
| `ruff` | Linting + formatting (replaces flake8, black, isort) | `pyproject.toml [tool.ruff]` |
| `mypy` | Static type checking | `pyproject.toml [tool.mypy]` |
| `pytest` | Test runner | `pyproject.toml [tool.pytest.ini_options]` |
| `textual-snapshot` | TUI regression snapshots | `pyproject.toml [tool.pytest.ini_options]` |
| Dependabot / Renovate | Dependency freshness | `renovate.json` (Renovate) |

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

1. `uv run poe check` — all green
2. `uv run poe changelog` — regenerate `CHANGELOG.md`, then
   `git add CHANGELOG.md && git commit -m "docs(changelog): update for vX.Y.Z"`
3. `uv run bump-my-version bump minor|patch|major` — bumps `pyproject.toml`,
   re-locks, commits, and tags `vX.Y.Z` in one step
4. `git push origin main --tags`
5. `git checkout -b release/X.Y.Z && git push origin release/X.Y.Z` — triggers
   PyPI publish (OIDC) + GitHub Release (notes from git-cliff) automatically

---

## ~~22. Desktop notifications~~ ✅ → [archived](roadmap-archive/desktop-notifications.md)

OS-level toast notifications on fault state transitions (cat detected, pinch, motor/retract faults, drawer full), plus an audible alert and a `/notify on|off|sound on|off|test` slash command that persists. Shipped — full design notes moved to the archive.

---

## ~~23. Tab completion for slash commands~~ ✅ → [archived](roadmap-archive/tab-completion.md)

Claude Code-style / overlay + inline ghost-text completion. Shipped — full design notes moved to the archive.

---

## 24. Version display

`VERSION` is already read from `importlib.metadata` and shown in the title
chip of the status bar:

```
◆ Asher CLI v0.2.0   [robot name]   ● ONLINE   [Ready]
```

The `_refresh_title()` method in `asher/ui/__init__.py` builds this; version
falls back to `"dev"` when running from source without `pip install -e .`.

### ~~`/version` slash command~~ ✅

`/version` (a `SlashCommand` in `asher/commands/__init__.py`) prints the
runtime versions to the log via `importlib.metadata.version()` with a
`PackageNotFoundError` → `"?"` fallback, so it degrades cleanly when run from
source without `pip install -e .`:

```
  Asher CLI v0.2.0
  Python 3.12.3
  pylitterbot 2025.6.2
  textual 8.x.x
```

### ~~Status bar title — model badge~~ ✅

The `#robot-lbl` widget already shows the model type appended to the robot name:

```
◆ Asher CLI v0.2.0   Idiot Box  LR4   ● ONLINE   ⟳ Cycling
```

Implemented via `robot_model(r)` in `asher/helpers.py`, called from `_refresh_status()` in `asher/monitoring/__init__.py`.

---

## ~~25. Headless CLI export — automate history without the TUI or MCP~~ ✅ → [archived](roadmap-archive/headless-export.md)

asher --export 7 writes CSV without launching the TUI, for cron/Task Scheduler/SSH. Shipped — full design notes moved to the archive.

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
2. ~~**Cat panel status badges** (§18)~~ ✅ — `#cat-label` (revived mode label) + `#cat-status` badges (status chip, lock, night light, sleep, wait) under the art; refreshed via `_update_cat_panel` on every status refresh
3. ~~**WebSocket subscription**~~ ✅ — real-time push updates live; 5-min poll fallback for activity history
4. ~~**Real-time cycling indicator with elapsed time** (§11)~~ ✅ — `⟳ Cycling  M:SS` chip in the status bar; `_cycle_start` + a lazy 1 s `_cycle_timer` (created on cycle start, stopped on any other status)
5. ~~**Token persistence** (§13)~~ ✅ — OAuth session token cached as JSON in the keyring; `_connect_worker` tries the token first and only falls back to email/password on failure (wiping the stale token). `token_update_callback` captures refreshes during a session, so launches skip the password login entirely until the refresh token itself expires
6. ~~**Fault & safety monitoring** (§9)~~ ✅ — `asher/faults.py` + `_refresh_faults` drive an in-panel `#fault-banner` (red/amber); enum fault props checked against healthy sentinels; transitions logged, steady state quiet; cat panel flips to `error`; `d` dismisses
7. ~~**Readable history events** (§11)~~ ✅ — `history` now renders translated, colour-coded labels via `asher/activity_labels.py` (`format_activity()`); cat-detection events append pet name + weight; shared with the `export` CSV path
8. ~~**History pager sub-view** (§11)~~ ✅ — `history` now pushes a `HistoryScreen` (`ModalScreen` in `asher/history_view.py`) with a focused `ScrollableContainer`; arrow keys / `Page Up`/`Page Down` / `Home`/`End` scroll, `q`/`Esc`/`Enter` close. Optional count arg (`history 100`, `history all`); default raised from 25 → 50. Pure `format_history_rows()` shares the timestamp/label rules with the old log rows

### Commands & slash system

1. ~~**`/robot` and `/robots` slash commands**~~ ✅ — `/robots` lists, `/robot <idx|name>` switches, keyring-persisted
2. ~~**`export` command**~~ ✅ (§2) — activity history to CSV; writes to `~/Downloads`, opens folder in OS explorer
3. ~~**`/pet` slash command**~~ ✅ (§1, §14) — `/pet` lists, `/pet <idx|name>` switches; `_active_pet_idx` persists for session
4. ~~**`/cat`, `/refresh`, `/config` slash commands**~~ ✅ (§1) — cat panel toggle + colour, poll interval control, runtime config dump
5. ~~**Tab-completion for slash commands** (§23)~~ ✅ — Claude Code-style overlay dropdown on `/` keypress; single-source registry drives both dispatch and completion
6. ~~**`/version` slash command** (§24)~~ ✅ — prints asher-cli / Python / pylitterbot / textual versions to the log via `importlib.metadata`, with a `"?"` fallback when not installed; model badge in the status bar was already done
7. ~~**`wait-time`, `power`, `rename`, `insight` commands** (§3)~~ ✅ — all four wired up; plus the `status`/`info` split (`status` trimmed to at-a-glance, `info` is the full property dump with power/cycles/litter/brightness/Wi-Fi). `panel-brightness <low|medium|high>` now wired too (the earlier claim it wasn't exposed was stale — it exists on LR4/LR5); `reset`/`reset-settings`/`firmware`-update deliberately omitted as destructive
8. ~~**Sleep schedule viewer** (§8)~~ ✅ — `sleep-schedule` (alias `sleepschedule`) renders the per-day sleep/wake window read-only, sorted Mon→Sun, with an active-window `● now` marker; config wizard/set/disable still TODO
9. ~~**Headless CLI export** (§25)~~ ✅ — `asher --export 7` writes activity history to CSV without launching the TUI, for cron/Task Scheduler/SSH; `--output` and `--robot` flags, documented exit codes; CSV core shared with the TUI `export` command via `build_history_csv()`
10. ~~**Full headless command surface** (issue #60)~~ ✅ — every robot command is now an `asher <command>` subcommand backed by the `COMMANDS` registry in `asher/headless.py`, with `--robot`/`--json` and exit code 5 for a rejected command; `--export` stays as a deprecated alias. Slash commands stay TUI-only by design

### Release pipeline

1. ~~**PyPI publish**~~ (§15) ✅ — `release.yml` live; push `release/x.y.z` branch to publish
2. ~~**CI/CD pipeline**~~ ✅ — lint + test + release workflows in `.github/workflows/`
3. ~~**Versioning discipline** (§20)~~ ✅ — `bump-my-version` configured with auto-commit + auto-tag (`v{x.y.z}`); `CHANGELOG.md` auto-generated from conventional commits via git-cliff (`cliff.toml` + `poe changelog` task + CI release notes)
4. **Standalone binary** (§16) — PyInstaller `.exe` + macOS/Linux builds via CI matrix
5. ~~**Dependabot / Renovate** (§21)~~ ✅ — Renovate (`renovate.json`) live, weekly, `pylitterbot` pinned to manual review

### Device & platform expansion

1. ~~**LR5 extras** (§4)~~ ✅ — privacy, volume, camera-audio, drawer-reset wired up via `LR5Adapter` (gracefully refused on LR3/LR4 through the base adapter). Night-light colour and filter-reminder remain as smaller follow-ons
2. **Feeder robot support** (§5) — snack, gravity, meal size commands
3. **Multi-robot tab view** (§11) — `TabbedContent` widget when `len(robots) > 1`

### Polish & stretch

1. ~~**Config persistence** (`config.json`, §10)~~ ✅ — runtime settings (`/refresh`, `/cat`, `/pet`) survive restarts via `~/.asher-cli/config.json`; `asher/config.py` provides load/save/update over a defaults dict (no Textual/pylitterbot deps); `_persist()` helper in `commands/__init__.py` wires each slash command to `config.update()`
2. **Weight sparkline in cat panel** (§7) — 7-day ASCII chart; delightful but non-essential
3. ~~**Desktop notifications** (§22)~~ ✅ — `plyer` toasts + `winsound` bell on fault transitions (cat-detected, pinch, motor/retract faults, position faults, drawer full, bonnet, laser, gas sensor); `/notify on|off|sound on|off|test` command with persistence; drawer-full promoted to a fault so it fires notifications and appears in `#fault-banner`
4. **Dark/light theme toggle** (§12) — CSS variable swap; the groundwork is done (`asher/theme.py` holds semantic roles behind `$asher-*` variables), so this is now repointing the roles at Catppuccin Latte and a command to switch
9. ~~**Catppuccin palette** (issue #61)~~ ✅ — the ad-hoc GitHub-dark hexes are consolidated into `asher/theme.py` as Catppuccin Mocha swatches plus semantic roles; `AsherApp.get_css_variables()` feeds `ui/style.tcss` and `theme.apply()` bakes the roles into screen-level CSS blocks
5. **E2E test harness** (§17) — Textual Pilot tests for critical user flows; good for preventing regressions but requires maintenance
6. **Refactor to be more clean code** — base command class with a property to distinguish slash vs bare commands; reduces duplication and makes adding commands easier
7. **LR5/Evo specific features** — camera snapshots, night light color control, hopper management (whatever pylitterbot exposes)
8. **Remote MCP connector** (§26) — access from claude.ai/mobile/Cowork, not just Desktop; requires hosting + an OAuth 2.1 authorization server, bigger lift than the local `/mcp` bridge and a different credential-storage tradeoff — evaluate demand before starting



