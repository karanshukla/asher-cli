# Asher CLI — CLAUDE.md

Terminal dashboard for Litter Robot (LR3/LR4/LR5) via the Whisker cloud API.

## Stack

- **Python 3.10+**
- **Textual** — async TUI framework (`textual>=0.47`)
- **pylitterbot** — unofficial Whisker API wrapper (`pylitterbot>=3.0`)
- **python-dotenv** — credential loading

## Entry point

```
python app.py
```

All logic lives in `app.py` (single-file architecture).

## Credentials

Loaded from `.env` at project root. Supported variable names:

```
LITTER_ROBOT_USER=...      # or LR4_EMAIL
LITTER_ROBOT_PASSWORD=...  # or LR4_PASSWORD
```

## Architecture

```
AsherApp (textual.App)
├── #status-bar          top dock — robot name, online badge, drawer bar, last seen, cat weight
├── #main-area
│   ├── #log             RichLog — scrollable event/command output
│   └── #cat-panel       animated ASCII cat sidebar
└── #input-bar           bottom dock — command prompt input
```

## Key methods

| Method | Purpose |
|---|---|
| `_connect_worker()` | `@work` — authenticate and load robots on startup |
| `_refresh_status()` | update all header widgets from robot state |
| `_poll_status_interval()` | `@work` — auto-refresh every 30s |
| `_tick_cat()` | advances multi-frame cat animation every 0.9s |
| `_run_cmd(raw)` | `@work` — parse and dispatch CLI commands |
| `_log_ok/err/warn/info()` | timestamped log helpers |

## Commands

`clean`, `status`, `lock`, `unlock`, `sleep`, `wake`, `night-light on|off`, `history`, `clear`, `help`, `quit`

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

## Common tasks

**Add a new command:** add a branch in `_run_cmd()` and implement `_cmd_<name>()`.

**Change poll interval:** `self.set_interval(30, ...)` in `on_mount`.

**Add a new cat state:** add entry to `CATS` dict (str for static, list[str] for animated), call `_set_cat("name", "label")`.
