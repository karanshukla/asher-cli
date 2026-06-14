# Asher CLI — Roadmap & Feature Gaps

Current state, missing functionality, and suggested additions — grounded in what
`pylitterbot` actually exposes today.

---

## What's working now

| Area | Status |
|---|---|
| Auth (email/password via `.env`) | ✅ |
| Connect & load robots | ✅ |
| Status bar (name, online, drawer %, last seen, pet weight) | ✅ |
| Pet name from Whisker account profile | ✅ |
| Commands: clean, status, lock, unlock, sleep, wake, night-light, history, help, clear, quit | ✅ |
| Activity history (`get_activity_history`) | ✅ |
| Cat animation panel with mode changes | ✅ |
| Command history (↑/↓) | ✅ |
| Auto-refresh every 30 s | ✅ |
| LR4 / LR5 / LR3 polymorphic support | ✅ (getattr fallback) |

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

### `/auth` — update credentials without restart

```
/auth email@example.com p@ssw0rd
```

Disconnects the current session, writes the new values to `.env`, then
reconnects. Avoids the need to edit the file and restart manually.

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

---

## 8. Fault monitoring & alerts

The following properties indicate hardware faults — none are surfaced in the UI:

| Property | Meaning |
|---|---|
| `globe_motor_fault_status` | Globe motor stall |
| `globe_motor_retract_fault_status` | Globe retract fault |
| `usb_fault_status` | USB power fault |
| `is_waste_drawer_full` | Boolean version of drawer full |
| `is_hopper_removed` _(LR4)_ | Litter hopper removed |
| `is_bonnet_removed` _(LR5)_ | Bonnet lid removed |
| `is_laser_dirty` _(LR5)_ | Laser sensor needs cleaning |
| `is_gas_sensor_fault_detected` _(LR5)_ | Gas / odor sensor fault |

Suggested: auto-scan these on every refresh and show a persistent amber or red
banner beneath the status bar if any fault is active. Also set the cat to "error"
mode.

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
| Desktop notifications | `plyer` or `win10toast` on drawer full / fault |
| Export to CSV | `history export` → writes activity to `.csv` |
| Weight sparkline in cat panel | Replace idle cat with a 7-day weight chart |
| Sound alert on fault | `winsound.Beep` (Windows) / `os.system("afplay")` (Mac) |
| Dark / light theme toggle | `/theme light` swaps colour palette |
| Startup robot selection | If multiple robots, prompt on launch instead of defaulting to `[0]` |
| `.env` wizard | First-run prompt if no `.env` found, writes creds interactively |
| Reconnect on network drop | Currently a failed poll is silently swallowed; should show a banner and retry |

---

## 12. Account management

### Token persistence (avoid re-login on every run)

`Account.connect()` accepts a pre-existing `token` dict and exposes a
`token_update_callback`. If we save the session token to a local file after
first login, subsequent runs skip the username/password auth entirely — faster
startup and more resilient to rate-limiting.

```python
TOKEN_FILE = Path("~/.asher_token.json").expanduser()

def load_token() -> dict | None:
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return None

def save_token(token: dict | None) -> None:
    if token:
        TOKEN_FILE.write_text(json.dumps(token))

account = Account(
    token=load_token(),
    token_update_callback=save_token,
)
```

The token is automatically refreshed by pylitterbot when it expires (via
`session.refresh_tokens()`). This means the user only has to enter their
password once.

**Security note:** the token file should be `chmod 600` on Unix. On Windows,
consider the Credential Manager via `keyring` instead of a plaintext file.

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

### Parsing

Current `_run_cmd` dispatches on the first word. Extend it:

```python
if raw.startswith("/"):
    await self._run_slash(raw[1:])
else:
    await self._run_robot_cmd(raw)
```

### Full slash command table

| Command | Description | Implementation note |
|---|---|---|
| `/robot [index\|name]` | List or switch active robot | `self._robot = robots[n]` + status refresh |
| `/pet [index\|name]` | List or switch which pet shows in status bar | `self._active_pet = pets[n]` |
| `/auth <email> <pass>` | Re-authenticate | Disconnect, update `.env`, reconnect |
| `/account` | Show account info | `account.user_id`, email from `.env` |
| `/account logout` | Clear saved token | Delete `~/.asher_token.json` |
| `/refresh [seconds\|off]` | Change poll interval | Cancel + recreate `set_interval` timer |
| `/cat [on\|off]` | Show/hide cat panel | `add_class` / `remove_class` on `#cat-panel` |
| `/cat color <hex>` | Change cat art colour | Update `_cat_color` attr, redraw |
| `/cat style <n>` | Switch ASCII art set | Swap `CATS` dict at runtime |
| `/config` | Show all current settings | Read-only dump |
| `/config set <key> <val>` | Change a setting | Write to `config.json` |
| `/theme [dark\|light]` | Swap colour scheme | Swap Textual CSS variables |
| `/log [n]` | Set max log lines to keep | `RichLog(max_lines=n)` |
| `/export [path]` | Export last activity to CSV | Write `activity_export.csv` |
| `/help` | List all slash commands | Separate from robot `help` |

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

## 14. Packaging as a standalone binary

### Option A — `pipx` (simplest, recommended)

`pipx` installs into an isolated venv and exposes the command globally.
Requires a proper `pyproject.toml`:

```toml
[project]
name = "asher-cli"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = [
    "pylitterbot>=3.0.0",
    "textual>=0.47.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
asher = "asher_cli.app:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Then:
```bash
pipx install .
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

### Unit tests

The core logic to test in isolation (no Whisker API, no Textual):

| Function | Test |
|---|---|
| `fmt_ago(dt)` | Various timedeltas — seconds, minutes, hours, days, None |
| `drawer_bar(pct)` | 0%, 50%, 85%, 100% — verify bar length and colour |
| Command parsing in `_run_cmd` | Verify correct method called for each verb |

```python
# tests/test_helpers.py
from datetime import datetime, timedelta, timezone
from app import fmt_ago, drawer_bar

def test_fmt_ago_minutes():
    dt = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert fmt_ago(dt) == "5m ago"

def test_drawer_bar_full_is_red():
    bar = drawer_bar(90)
    assert "#f85149" in bar._spans[1].style   # red segment
```

### Integration tests — pylitterbot mocking

Rather than hitting the live API, mock `Account`:

```python
# tests/conftest.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

@pytest.fixture
def mock_robot():
    r = MagicMock()
    r.name = "Test Box"
    r.is_online = True
    r.waste_drawer_level = 42.0
    r.pet_weight = 9.1
    r.status.value = "Ready"
    r.last_seen = datetime.now(timezone.utc)
    r.refresh = AsyncMock()
    r.start_cleaning = AsyncMock(return_value=True)
    r.set_panel_lockout = AsyncMock(return_value=True)
    r.get_activity_history = AsyncMock(return_value=[])
    return r

@pytest.fixture
def mock_account(mock_robot):
    a = MagicMock()
    a.robots = [mock_robot]
    a.pets = []
    a.connect = AsyncMock()
    a.disconnect = AsyncMock()
    return a
```

Then test the app worker methods by injecting the mock:

```python
# tests/test_commands.py
async def test_clean_calls_start_cleaning(mock_robot, mock_account):
    app = AsherApp()
    app._robot = mock_robot
    await app._cmd_clean()
    mock_robot.start_cleaning.assert_called_once()
```

### TUI / snapshot tests

Textual has a built-in test harness:

```python
from textual.testing import AppTest

async def test_help_renders(mock_account):
    async with AppTest(AsherApp()) as pilot:
        await pilot.press("h", "e", "l", "p", "enter")
        assert "clean" in pilot.app.query_one("#log").renderable
```

And snapshot tests via `textual-snapshot` that render the app to a file and
diff it on CI:

```bash
pip install textual-snapshot
pytest --snapshot-update   # generate baseline
pytest                     # compare on CI
```

### CI pipeline (GitHub Actions)

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pytest tests/ -v
  build:
    needs: test
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run pyinstaller --onefile --name asher app.py
      - uses: actions/upload-artifact@v4
        with:
          name: asher-${{ matrix.os }}
          path: dist/asher*
```

### Suggested test structure

```
tests/
  conftest.py          shared fixtures (mock_robot, mock_account, mock_app)
  test_helpers.py      pure function tests (fmt_ago, drawer_bar)
  test_commands.py     command handler integration tests
  test_slash.py        slash command tests
  test_ui.py           Textual snapshot / pilot tests
  snapshots/           baseline TUI screenshots
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
asher_cli/
  __init__.py
  app.py            AsherApp class only — compose, mount, bindings
  commands.py       _run_cmd, _run_slash, all _cmd_* methods (mixin or module)
  status.py         _refresh_status, _update_cat_status, header widget logic
  config.py         Config dataclass, load_config(), save_config()
  cats.py           CATS dict, _set_cat(), _tick_cat(), cat art definitions
  helpers.py        fmt_ago(), drawer_bar(), ts(), STATUS_COLORS
  widgets/
    __init__.py
    status_bar.py   StatusBar(Widget) — self-contained header widget
    cat_panel.py    CatPanel(Widget) — art + label + status badges
    log_panel.py    LogPanel(Widget) — RichLog wrapper with helpers
    input_bar.py    InputBar(Widget) — prompt + Input + completion
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

1. Create `asher_cli/` package, move `app.py` → `asher_cli/app.py`
2. Extract `helpers.py` first (zero dependencies, easy test wins)
3. Extract `cats.py` (pure data)
4. Extract `config.py` (no Textual dependency)
5. Extract `StatusBar` widget (isolate header from app logic)
6. Extract `CatPanel` widget
7. Extract `CommandHandler` (biggest win for testability)
8. Update `pyproject.toml` entry point: `asher = "asher_cli.__main__:main"`

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
      - run: uv run mypy asher_cli/ --ignore-missing-imports

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

### `.github/workflows/release.yml` — triggered on `v*` tag

```yaml
name: Release
on:
  push:
    tags: ["v*"]

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
      - run: uv run pyinstaller --onefile --name asher asher_cli/__main__.py
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

## Priority suggestion

Ranked by user-visible impact vs. implementation effort:

### Foundation (do these first — everything else builds on them)

1. **`pyproject.toml` + `importlib.metadata` version** (§18) — single source of truth, unlocks packaging and CI
2. **Architecture refactor** (§17) — extract helpers + widgets; makes the codebase testable before adding more features
3. **Lint + test CI** (§19 `ci.yml`) — `ruff` + `mypy` + `pytest` gate on every PR; free confidence net

### High-value features (biggest user-visible wins)

4. **Cat panel status badges** (§16) — lock, sleep, night light, wait time under the art; high visibility, one-afternoon job
5. **WebSocket subscription** (§5) — replace 30 s polling with real-time push updates
6. **Token persistence** (§12) — skip password re-entry on every run
7. **Fault monitoring** (§8) — safety alerts; just read properties already on the robot object
8. **Status color-coding** (§10) — `LitterBoxStatus` → colour in status bar and cat badges

### Commands & slash system

9. **`/robot` and `/pet` slash commands** (§1, §13) — robot/pet switcher
10. **`wait-time`, `power`, `rename`, `insight` commands** (§2) — each is a two-line wiring job
11. **Sleep schedule viewer** (§7) — read-only first, config wizard later
12. **Tab-completion for slash commands** (§13) — overlay dropdown on `/` keypress

### Release pipeline

13. **Versioning discipline** (§18) — tag convention, `hatch version`, `CHANGELOG.md`
14. **Release CI** (§19 `release.yml`) — auto-build binaries + GitHub Release on `v*` tag
15. **Dependabot / Renovate** (§19) — automated dependency PRs, `pylitterbot` pinned to manual review

### Device & platform expansion

16. **LR5 extras** (§3) — privacy, volume, camera, night-light colour — detect model first
17. **Feeder robot support** (§4) — snack, gravity, meal size commands
18. **Multi-robot tab view** (§10) — `TabbedContent` widget when `len(robots) > 1`

### Polish & stretch

19. **Config persistence** (`config.json`, §12) — runtime settings survive restarts
20. **`pipx` install + standalone binary** (§14) — for non-developer users
21. **Weight sparkline in cat panel** (§6) — 7-day ASCII chart; delightful but non-essential
22. **Desktop / sound notifications** (§11) — `plyer` on drawer full or faults
23. **Dark/light theme toggle** (§11) — CSS variable swap; nice-to-have but not critical
24. **Startup Animation** (§9) — cute but adds friction to quick status checks; could be opt-in
```


