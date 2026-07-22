# Asher CLI — CLAUDE.md

Terminal dashboard for Litter Robot (LR3/LR4/LR5) via the Whisker cloud API.

## Stack

- **Python 3.10+**
- **Textual** — async TUI framework (`textual>=0.47`)
- **pylitterbot** — unofficial Whisker API wrapper (`pylitterbot>=3.0`)
- **python-dotenv** — credential loading (`.env` fallback)
- **keyring>=24** — OS credential store (Windows Credential Manager / macOS Keychain / Linux Secret Service)

## Tooling

- **uv** — dependency management and task runner (`uv sync`, `uv run`)
- **poethepoet** — task aliases via `uv run poe <task>`
- **ruff** — linter and formatter
- **mypy** — static type checking
- **pytest + pytest-asyncio + pytest-cov** — tests
- **textual-dev** — CSS hot reload devtools
- **watchfiles** — Python auto-restart on file change

## Entry points

```
python app.py          # compatibility shim (calls asher/__main__.py)
python -m asher        # run as module
asher                  # after: uv sync && uv run asher  OR  pip install -e .
```

## Package structure

```
asher/
  __init__.py
  app.py            AsherApp class (thin orchestrator — composes mixins)
  auth.py           LoginScreen modal (ModalScreen[tuple[str,str]]) — available, not primary flow
  helpers.py        fmt_ago(), drawer_bar(), ts(), robot_model()  (pure, testable)
  constants.py      STATUS_COLORS, ROBOT_MODELS
  cats.py           CATS dict (ASCII art)
  login_flow.py     LoginFlow state machine — inline email/password prompt in command bar
  robot_protocol.py RobotProtocol structural Protocol for pylitterbot robot objects
  robot_adapters.py RobotAdapter ABC + LR3/LR4/LR5 subclasses + make_adapter() factory
  mcp_config.py     Claude Desktop config read/write for the /mcp slash command
  mcp_bridge.py     asher-mcp-launch console script — keyring-backed pylitterbot MCP launcher
  faults.py         check_faults(robot) — model-scoped safety/component fault detection (status enum + per-model attr allowlist; hopper never a fault)
  __main__.py       main() entry point
  commands/
    base.py         Command ABC, SlashCommand, CommandRegistry
    __init__.py     CommandsMixin — all command classes + registry + dispatch
  connection/       ConnectionMixin — keyring auth, _connect_worker, keyring helpers
  monitoring/       MonitoringMixin — _poll_status_interval, _refresh_status
  ui/               UIMixin — CSS, compose(), log helpers, cat helpers
  slash-commands/   Convention doc

tests/
  testhelpers.py          unit tests for helpers.py
  test_cats.py            CATS dict structure
  test_auth.py            LoginScreen CSS / structure
  test_auth_pilot.py      Textual Pilot integration tests for LoginScreen
  test_app_pilot.py       Textual Pilot integration tests for AsherApp
  test_commands_pilot.py  Textual Pilot integration tests for command dispatch
  test_connection.py      keyring helper functions
  test_connection_mixin.py ConnectionMixin structure
  test_monitoring.py      MonitoringMixin async methods
  test_ui.py              UIMixin constants, CSS, helper existence
  test_mcp_config.py      Claude Desktop config read/write
  test_mcp_bridge.py      mcp_bridge launcher credential/subprocess handling
  test_mcp_command.py     /mcp slash command dispatch
  test_faults.py          check_faults() — safety statuses, attribute faults, graceful degradation

.github/workflows/
  ci.yml            ruff + mypy + pytest on every push/PR
```

## Credentials

Priority order on startup:

1. **OS keyring** — set automatically after first interactive login
2. **`.env` file** — fallback for existing users / CI
3. **Inline login flow** — shown when no credentials found anywhere (email → password prompt in command bar)

`.env` variable names (for fallback):
```
LITTER_ROBOT_USER=...
LITTER_ROBOT_PASSWORD=...
```

Keyring service name: `asher-cli`, keys `email` and `password`.
Helper functions in `asher/connection/__init__.py`: `_keyring_load()`, `_keyring_save()`, `_keyring_delete()`.

## MCP bridge (`/mcp`)

pylitterbot ships an optional MCP server (`pip install pylitterbot[mcp]`, run via `python -m pylitterbot.mcp`) that lets an MCP client like Claude Desktop monitor/control the robot directly. Its own docs configure it with plaintext credentials in the client's JSON config — asher-cli avoids that:

- `/mcp on|off|status` (in `asher/commands/__init__.py`, logic in `asher/mcp_config.py`) adds/removes an entry (named by `mcp_config._SERVER_NAME`) in every `claude_desktop_config.json` this OS's Claude Desktop might read (`mcp_config.config_paths()` — on Windows this includes both the standard installer path and any MSIX/Microsoft Store virtualized path). The entry's `command` is `sys.executable -m asher.mcp_bridge` — never the credentials themselves.
- `/mcp on` also auto-installs pylitterbot's `mcp` extra via `sys.executable -m pip install "pylitterbot[mcp]==<installed version>"` if the `mcp` package isn't importable yet.
- `asher/mcp_bridge.py` (console script `asher-mcp-launch`) is what Claude Desktop actually spawns. It reads email/password from the OS keyring at process start, sets them as `LITTER_ROBOT_USERNAME`/`LITTER_ROBOT_PASSWORD` (pylitterbot's expected names — note these differ from asher-cli's own `.env` var `LITTER_ROBOT_USER`) in that process's environment only, then execs `python -m pylitterbot.mcp`. No credentials ever touch the on-disk MCP config.
- `/mcp on` requires keyring credentials. If none are found but `.env` fallback credentials are set, it copies them into the keyring automatically (since the bridge process can't reliably discover a project-relative `.env` — Claude Desktop controls its working directory, not asher-cli).
- Requires the `mcp` extra: `uv sync --extra mcp` / `pip install asher-cli[mcp]`. Restart Claude Desktop after toggling for the change to take effect.

## Command convention

**Normal commands** (no prefix) — robot actions only:
`clean`, `status`, `info`, `lock`, `unlock`, `sleep`, `wake`, `night-light on|off|auto`, `night-light-brightness <level>`, `wait-time <minutes>`, `power on|off`, `rename <name>`, `insight [days|month]`, `sleep-schedule`, `privacy on|off`, `volume <0-100>`, `camera-audio on|off`, `drawer-reset`, `history`, `export [days|month]`, `clear`, `help`, `quit`

**Slash commands** (`/` prefix) — app management only:
`/login`, `/logout`, `/robots`, `/robot <index|name>`, `/pets`, `/pet <index|name>`, `/cat on|off|color <hex>`, `/refresh [seconds|off]`, `/config`, `/version`, `/mcp on|off|status`, `/exit`

> The authoritative list is the `_registry` in `asher/commands/__init__.py`; `/help` renders it at runtime. If you add a command, update the tables in `README.md` and the list in `asher/slash-commands/__init__.py`.

**Special cases** (accepted both with and without `/`):
`exit`, `quit`, `q` — exit the app

Do not add robot-control commands as slash commands, and do not add app-management commands as bare commands.

## Architecture

**Status bar philosophy:**
- **Top row** — ambient/settings info (robot name, online badge, night light mode + brightness). Not time-critical.
- **Second row** — important operational state and cat data (drawer %, litter %, cat weight, last visit). Could be subject to change

```
AsherApp (textual.App)
├── #status-bar          top dock — two rows (top: name/online/night-light/lock; bottom: drawer/litter/weight/visit)
├── #main-area
│   ├── #log             RichLog — scrollable event/command output
│   └── #cat-panel       animated ASCII cat sidebar
│       ├── #cat-fx      animated FX strip
│       ├── #cat-art     the ASCII cat
│       ├── #cat-label   mode label (connected / cycling… / fault!)
│       ├── #cat-status  complementary badges (status, power, cycles, wait time) — no lock/night-light (those are top-row only)
│       └── #fault-banner  hidden unless check_faults() returns active faults; `d` dismisses
└── #bottom-dock         bottom dock
    ├── #input-bar / #input-row   command prompt ("> " label + CmdInput)
    └── #hint-bar        shortcut hints / login flow prompts

LoginScreen (ModalScreen) — available in auth.py but not the primary auth path
```

## Key methods

| Method | Purpose |
|---|---|
| `_connect_worker()` | `@work` — resolve credentials (keyring → .env → inline login), authenticate |
| `_refresh_status()` | update all header widgets + cat panel + fault banner from robot state |
| `_update_cat_panel(robot)` | render `#cat-label` + `#cat-status` (complementary: status, power, cycles, wait); called from `_refresh_status` |
| `_refresh_faults(robot)` | run `check_faults()`, render `#fault-banner`, log transitions; sets cat mode to `error` while faults active |
| `_cycling_chip()` / `_start_cycle_timer()` / `_stop_cycle_timer()` / `_tick_cycle()` | `⟳ Cycling M:SS` chip + lazy 1s elapsed timer |
| `_poll_status_interval()` | `@work` — poll fallback every 300s (5 min); WebSocket is primary |
| `_tick_cat()` | advances multi-frame cat animation every 0.4s |
| `_dispatch_command(command, args)` | `@work` — calls `command.run(app, args)` from the registry |
| `on_input_submitted()` | routes input to login flow or `_dispatch_command` via `CommandRegistry` |
| `_start_login_flow()` | begin inline email/password prompt in command bar |
| `_cmd_logout()` | delete creds from keyring, disconnect |
| `make_adapter(robot)` | factory in `robot_adapters.py` — returns correct `RobotAdapter` subclass |
| `_log_ok/err/warn/info()` | timestamped log helpers |

## Robot compatibility

pylitterbot auto-detects robot type. Commands that differ per model are handled by `RobotAdapter` subclasses in `robot_adapters.py` — `make_adapter(robot)` returns the right one based on `type(robot).__name__`. Status-bar reads use `getattr(..., default)` for graceful degradation on older models. Tested API surface:

- `robot.name`, `robot.serial`, `robot.is_online`
- `robot.status` (LitterBoxStatus enum)
- `robot.waste_drawer_level` (0–100)
- `robot.sleep_mode_enabled`, `robot.panel_lock_enabled`, `robot.night_light_mode_enabled`
- `robot.last_seen` (datetime)
- `robot.refresh()`, `robot.start_cleaning()`
- `robot.set_sleep_mode(bool)`, `robot.set_panel_lockout(bool)`
- `robot.set_night_light_brightness(int)` or `robot.set_night_light_mode(NightLightMode)`
- `robot.get_activity_history(limit=int)` → list of `Activity` objects with `.timestamp` and `.action` (`LitterBoxStatus` enum)

## Code comments

Don't add comments above functions or inline unless the WHY is genuinely non-obvious (a hidden constraint, a subtle invariant, a workaround for a specific bug). Well-named identifiers should make the WHAT self-evident. Before reaching for a comment, check whether the explanation can instead be expressed through abstraction or encapsulation — e.g. domain logic buried in a mixin or command handler should move to a self-commenting, domain-named method rather than being explained in a comment. Favor human-readable, domain-driven names and logical flow over prose explanations, while keeping code legible to agents working in this repo.

## Development notes

- Textual and pylitterbot are both asyncio-native — compose cleanly with `@work` tasks
- All command execution runs in `@work` async workers to keep the UI responsive
- Cat modes: `idle`, `happy`, `cleaning` (animated), `sleeping`, `error`, `full`
- `VERSION` is read from `importlib.metadata.version("asher-cli")` — falls back to `"dev"` when running from source
- The primary login path is the inline flow in `login_flow.py` (`LoginFlow` state machine: `IDLE` → `AWAITING_EMAIL` → `AWAITING_PASSWORD`). `LoginScreen` (`auth.py`) still exists as a modal but is not used in the current main flow.
- `LoginScreen` uses `event.stop()` on `Input.Submitted` and `Button.Pressed` to prevent bubbling to the App's `on_input_submitted` (relevant if re-activating the modal path)

### IoT command timing — optimistic UI updates

`sendLitterRobot4Command` (and equivalents) return as soon as the cloud **queues** the command, not when the robot applies it. Calling `robot.refresh()` immediately after gets stale data. The fix for toggle/mode commands (lock, unlock, night-light on/off/auto) is to **update the status bar widget directly** after a successful API call, without waiting for a refresh — the WebSocket subscription will confirm the final state later. Do **not** add `asyncio.sleep(N)` + `refresh()` + `_refresh_status()` for these commands.

Commands that need a confirmed cloud state before showing a result (e.g. sleep/wake, where the state isn't known from the command arg alone) use `asyncio.sleep(2)` + `refresh()` + `_refresh_status()` as a best-effort workaround, accepting the risk of briefly stale display.

## Common tasks

**Add a robot command:** create a class inheriting `Command` in `asher/commands/__init__.py`, implement `async def run(self, app, args)`, and call `_registry.register(MyCommand())`.

**Add a slash command:** create a class inheriting `SlashCommand` (sets `prefix = "/"`), implement `async def run(self, app, args)`, register it, and document in `asher/slash-commands/__init__.py`.

**Change poll interval:** `self.set_interval(300, ...)` in `on_mount`.

**Add a new cat state:** add entry to `CATS` dict in `asher/cats.py` (str for static, list[str] for animated), then call `_set_cat("name", "label")`.

**File naming convention:** no underscores in filenames (except Python-required `__init__.py` and `__main__.py`).

## Dev workflow

```bash
uv sync                  # install all deps (including dev group)
uv run poe dev           # run with CSS hot reload (textual --dev)
uv run poe watch         # run with Python auto-restart on file change (watchfiles)
uv run poe test          # run test suite
uv run poe check         # ruff + mypy + pytest (same as CI)
uv run poe fix           # auto-fix ruff issues
```

Pre-push hook (`.githooks/pre-push`) runs: ruff check → ruff format --check → mypy. Tests are not in the hook — run them manually.

## Testing notes

- Pilot-based integration tests use `app.run_test()` with `await pilot.pause()` before querying widgets
- Helper app wrappers for screens must **not** start with `Test` (pytest will try to collect them); use e.g. `LoginTestApp`
- Mock external deps with `unittest.mock.AsyncMock` for async robot/account methods
- `from pylitterbot import Account` is a local import inside `_connect_worker` — patch it at `pylitterbot.Account`, not `asher.connection.Account`
- Coverage: ~76% overall; main gaps are async exception paths and `_connect_worker` auth flow
