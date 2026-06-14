# Asher CLI — CLAUDE.md

Terminal dashboard for Litter Robot (LR3/LR4/LR5) via the Whisker cloud API.

## Stack

- **Python 3.10+**
- **Textual** — async TUI framework (`textual>=0.47`)
- **pylitterbot** — unofficial Whisker API wrapper (`pylitterbot>=3.0`)
- **python-dotenv** — credential loading (`.env` fallback)
- **keyring>=24** — OS credential store (Windows Credential Manager / macOS Keychain / Linux Secret Service)

## Entry points

```
python app.py          # compatibility shim (calls asher/__main__.py)
python -m asher        # run as module
asher                  # after: pip install -e .
```

## Package structure

```
asher/
  __init__.py
  app.py            AsherApp class (thin orchestrator — composes mixins)
  auth.py           LoginScreen modal (ModalScreen[tuple[str,str]])
  helpers.py        fmt_ago(), drawer_bar(), ts(), STATUS_COLORS  (pure, testable)
  cats.py           CATS dict (ASCII art)
  __main__.py       main() entry point
  commands/         CommandsMixin — robot commands + slash-command dispatch
  connection/       ConnectionMixin — keyring auth, _connect_worker, keyring helpers
  monitoring/       MonitoringMixin — _poll_status_interval, _refresh_status
  ui/               UIMixin — CSS, compose(), log helpers, cat helpers
  slash-commands/   Convention doc + future slash-command registry

tests/
  conftest.py       shared fixtures (mock_robot, mock_account)
  testhelpers.py    unit tests for helpers.py

.github/workflows/
  ci.yml            ruff + mypy + pytest on every push/PR
```

## Credentials

Priority order on startup:

1. **OS keyring** — set automatically after first interactive login
2. **`.env` file** — fallback for existing users / CI
3. **Interactive `LoginScreen`** — shown when no credentials found anywhere

`.env` variable names (for fallback):
```
LITTER_ROBOT_USER=...      # or LR4_EMAIL
LITTER_ROBOT_PASSWORD=...  # or LR4_PASSWORD
```

Keyring service name: `asher-cli`, keys `email` and `password`.
Helper functions in `asher/connection/__init__.py`: `_keyring_load()`, `_keyring_save()`, `_keyring_delete()`.

## Command convention

**Normal commands** (no prefix) — robot actions only:
`clean`, `status`, `lock`, `unlock`, `sleep`, `wake`, `night-light on|off`, `history`, `clear`, `help`

**Slash commands** (`/` prefix) — app management only:
`/login`, `/logout`, `/exit`

**Special cases** (accepted both with and without `/`):
`exit`, `quit`, `q` — exit the app

Do not add robot-control commands as slash commands, and do not add app-management commands as bare commands.

## Architecture

```
AsherApp (textual.App)
├── #status-bar          top dock — robot name, online badge, drawer bar, last seen, cat weight
├── #main-area
│   ├── #log             RichLog — scrollable event/command output
│   └── #cat-panel       animated ASCII cat sidebar
└── #input-bar           bottom dock — command prompt input

LoginScreen (ModalScreen) — shown on first run or after /login
```

## Key methods

| Method | Purpose |
|---|---|
| `_connect_worker()` | `@work` — resolve credentials (keyring → .env → LoginScreen), authenticate |
| `_refresh_status()` | update all header widgets from robot state |
| `_poll_status_interval()` | `@work` — auto-refresh every 30s |
| `_tick_cat()` | advances multi-frame cat animation every 0.9s |
| `_run_cmd(raw)` | `@work` — parse and dispatch robot commands |
| `_run_slash_cmd(raw)` | `@work` — parse and dispatch slash commands |
| `_cmd_login()` | show LoginScreen, save creds, reconnect (no exit) |
| `_cmd_logout()` | delete creds from keyring, exit |
| `_log_ok/err/warn/info()` | timestamped log helpers |

## Robot compatibility

pylitterbot auto-detects robot type. Any attribute/method missing on a given model is caught by `getattr(..., default)` or `try/except`, so the UI degrades gracefully. Tested API surface:

- `robot.name`, `robot.serial`, `robot.is_online`
- `robot.status` (LitterBoxStatus enum)
- `robot.waste_drawer_level` (0–100)
- `robot.sleeping`, `robot.panel_lockout`, `robot.night_light_mode_enabled`
- `robot.last_seen` (datetime)
- `robot.refresh()`, `robot.start_cleaning()`
- `robot.set_sleep_mode(bool)`, `robot.set_panel_lockout(bool)`
- `robot.set_night_light_brightness(int)` or `robot.set_night_light_mode(NightLightMode)`
- `robot.get_activity(limit=int)` → list of activity objects with `.timestamp`, `.weight`, `.action_value`

## Development notes

- Textual and pylitterbot are both asyncio-native — compose cleanly with `@work` tasks
- All command execution runs in `@work` async workers to keep the UI responsive
- Cat modes: `idle`, `happy`, `cleaning` (animated), `sleeping`, `error`, `full`
- `_cmd_nightlight` tries `set_night_light_brightness` first, falls back to `set_night_light_mode`
- `VERSION` is read from `importlib.metadata.version("asher-cli")` — falls back to `"dev"` when running from source
- `LoginScreen` uses `event.stop()` on `Input.Submitted` and `Button.Pressed` to prevent bubbling to the App's `on_input_submitted`

## Common tasks

**Add a robot command:** add a branch in `_run_cmd()` in `asher/commands/__init__.py` and implement `_cmd_<name>()`.

**Add a slash command:** add a branch in `_run_slash_cmd()` in `asher/commands/__init__.py`, implement `_slash_<name>()`, and add to `slash_cmds` list in `_show_help()`. Document in `asher/slash-commands/__init__.py`.

**Change poll interval:** `self.set_interval(30, ...)` in `on_mount`.

**Add a new cat state:** add entry to `CATS` dict in `asher/cats.py` (str for static, list[str] for animated), then call `_set_cat("name", "label")`.

**Run tests:** `pytest tests/` (or `uv run pytest` if using uv).

**File naming convention:** no underscores in filenames (except Python-required `__init__.py` and `__main__.py`).
