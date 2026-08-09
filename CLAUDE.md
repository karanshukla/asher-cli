# Asher CLI — CLAUDE.md

Terminal dashboard for Litter Robot (LR3/LR4/LR5) via the Whisker cloud API.

## Stack

- **keyring** resolves to the OS-native credential store: Windows Credential Manager / macOS Keychain / Linux Secret Service.

See `pyproject.toml` for the full dependency and dev-tooling list (`[project].dependencies`, `[dependency-groups].dev`, `[tool.poe.tasks]`).

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
  theme.py          Catppuccin Mocha palette + semantic roles (BACKGROUND, MUTED, DANGER, …) + CSS_VARIABLES/apply() — the only place a hex literal belongs
  config.py         runtime settings persistence — load()/save()/update() over ~/.asher-cli/config.json; holds poll interval, cat-panel visibility/colour, active pet index, notification settings (non-secret UI prefs only; credentials stay in keyring)
  notifications.py  desktop toast + audible alert façade over plyer (fire/beep, always-safe no-op on failure/headless)
  cats.py           CATS dict (ASCII art)
  login_flow.py     LoginFlow state machine — inline email/password prompt in command bar
  robot_protocol.py RobotProtocol structural Protocol for pylitterbot robot objects
  robot_adapters.py RobotAdapter ABC + LR3/LR4/LR5 subclasses + make_adapter() factory
  mcp_config.py     Claude Desktop config read/write for the /mcp slash command
  mcp_bridge.py     asher-mcp-launch console script — keyring-backed pylitterbot MCP launcher
  faults.py         check_faults(robot) — model-scoped safety/component fault detection (status enum + per-model attr allowlist incl. LR4 USB power fault; hopper never a fault)
  history_view.py   HistoryScreen (ModalScreen) + format_history_rows()/format_history_text() — scrollable activity-history pager pushed by the `history` command; `c` copies the full history (plain text) to the clipboard via action_copy_all()
  export.py         shared activity-history CSV core + exit-code contract: build_history_csv(), resolve_dest(), resolve_robot(), parse_days(), EXIT_*, ExportError — no Textual imports; the TUI `export` command and `asher export` both call build_history_csv()
  headless.py       headless command surface for `asher <command>` — Session/Result/CommandError, the COMMANDS registry, and run(); plain strings only, no Textual, routes model differences through RobotAdapter
  completion.py     pure helpers for command completion: slash popup (slash_matches, enter_completes, render_completion) + inline ghost text (CommandSuggester) — fed by _registry, no Textual imports except the Suggester base class
  __main__.py       main() entry point — argparse subcommands (headless) vs no-args (TUI); `--export` kept as a deprecated alias
  commands/
    base.py         Command ABC, SlashCommand, CommandRegistry
    __init__.py     CommandsMixin — all command classes + registry + dispatch
  connection/       ConnectionMixin — keyring auth, _connect_worker, keyring helpers, _connect_headless() (no-UI auth for `asher --export`)
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
  test_config.py          runtime settings persistence — load/save/update over defaults
  test_notifications.py   plyer toast + beep façade — always-safe no-op paths
  test_mcp_bridge.py      mcp_bridge launcher credential/subprocess handling
  test_mcp_command.py     /mcp slash command dispatch
  test_faults.py          check_faults() — safety statuses, attribute faults, graceful degradation
  test_history_view.py    format_history_rows()/format_history_text() + HistoryScreen structure, copy-all + Pilot push/dismiss
  test_export.py          build_history_csv/resolve_dest/resolve_robot/parse_days (pure) + the legacy `--export` flag path (no Pilot, mocks _connect_headless)
  test_headless.py        headless registry/rendering (pure) + every command handler against mock robots + run() exit codes + the argparse subcommand surface
  test_completion.py      slash_matches/enter_completes/render_completion (pure) + Pilot overlay visibility/navigation/accept

.github/workflows/
  ci.yml            ruff + mypy + pytest on every push/PR
  bandit.yml        bandit security scan → SARIF → code scanning (config: [tool.bandit] in pyproject.toml)
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

## Command convention

Command names, slash-command names, and their args are not listed here — see the `_registry` in `asher/commands/__init__.py`, which is authoritative; `/help` renders it at runtime. `/mcp`'s credential-bridging design is documented in the `mcp-bridge` skill.

**Normal commands** (no prefix) are robot actions only; **slash commands** (`/` prefix) are app management only.

`/refresh`, `/cat`, `/pet`, and `/notify` persist their settings to `~/.asher-cli/config.json` (via `asher.config.update()`), so they survive restarts. Credentials and the preferred-robot serial stay in the OS keyring; the config file holds only non-secret UI preferences.

Do not add robot-control commands as slash commands, and do not add app-management commands as bare commands.

**Special cases** (accepted both with and without `/`):
`exit`, `quit`, `q` — exit the app

**Headless commands** (`asher <command>`) are a parallel registry in `asher/headless.py`: same robot actions, no Textual, plain-string + JSON output. Slash commands have no headless equivalent — they configure the TUI, which isn't running. A robot command worth scripting should exist in both registries; the shared logic lives in `RobotAdapter`, not in either command class.

> If you add a command, update the tables in `README.md` and the list in `asher/slash-commands/__init__.py`. If it's a robot command, consider adding it to `COMMANDS` in `asher/headless.py` too.

## Architecture

**Status bar philosophy:**
- **Top row** — ambient/settings info (robot name, online badge, night light mode + brightness). Not time-critical.
- **Second row** — important operational state and cat data (drawer %, litter %, cat weight, last visit). Could be subject to change

```
AsherApp (textual.App)
├── #status-bar          top dock — two rows (top: name/online/night-light/lock; bottom: drawer/litter/weight/visit)
├── #main-area
│   ├── #log             RichLog — scrollable event/command output
│   ├── #completion-overlay  Static — floating slash-command completion list (overlay: screen; hidden unless typing /); does not reserve layout space
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
| `on_input_submitted()` | routes input to login flow or `_dispatch_command` via `CommandRegistry`; Enter on a partial `/cmd` completes it instead of submitting |
| `on_input_changed()` | live-filters the `#completion-overlay` as the user types (slash commands only; hides once a space is present); also clears ghost text during the login flow |
| `on_key()` | `↑`/`↓` history nav, plus completion nav (arrows cycle the slash popup, `Tab`/`Enter` accept, `Esc` dismisses); `Tab` also accepts the inline ghost-text suggestion when the popup is closed |
| `_start_login_flow()` | begin inline email/password prompt in command bar |
| `_cmd_logout()` | delete creds from keyring, disconnect |
| `make_adapter(robot)` | factory in `robot_adapters.py` — returns correct `RobotAdapter` subclass |
| `_log_ok/err/warn/info()` | timestamped log helpers |

## Robot compatibility

pylitterbot auto-detects robot type. Commands that differ per model are handled by `RobotAdapter` subclasses in `robot_adapters.py` — `make_adapter(robot)` returns the right one based on `type(robot).__name__`. Status-bar reads use `getattr(..., default)` for graceful degradation on older models. See the `pylitterbot-ref` skill for the confirmed API surface.

## Colour

Every colour comes from `asher/theme.py` (Catppuccin Mocha). Reference the **semantic roles** (`theme.MUTED`, `theme.DANGER`, …), not the raw swatches (`theme.OVERLAY0`) and never a hex literal — a re-flavour then only repoints the roles.

- **Rich styles:** `style=theme.ACCENT`, or `style=f"bold {theme.ACCENT}"`. Prefer building `Text` objects with explicit styles over `Text.from_markup` with inline colours.
- **`ui/style.tcss`:** use the `$asher-*` variables; `AsherApp.get_css_variables()` supplies them.
- **Inline `CSS`/`DEFAULT_CSS` on a Screen or Widget:** wrap the block in `theme.apply(...)`, which bakes the `$asher-*` values in at class-definition time. A screen mounted on a host app that isn't `AsherApp` (as the Pilot tests do) would otherwise fail to parse.

## Code comments

Don't add comments above functions or inline unless the WHY is genuinely non-obvious (a hidden constraint, a subtle invariant, a workaround for a specific bug). Well-named identifiers should make the WHAT self-evident. Before reaching for a comment, check whether the explanation can instead be expressed through abstraction or encapsulation — e.g. domain logic buried in a mixin or command handler should move to a self-commenting, domain-named method rather than being explained in a comment. Favor human-readable, domain-driven names and logical flow over prose explanations, while keeping code legible to agents working in this repo.

## Development notes

- Textual and pylitterbot are both asyncio-native — compose cleanly with `@work` tasks
- All command execution runs in `@work` async workers to keep the UI responsive
- Cat modes: `idle`, `happy`, `cleaning` (animated), `sleeping`, `error`, `full`
- `VERSION` is read from `importlib.metadata.version("asher-cli")` — falls back to `"dev"` when running from source
- **No `assert` in `asher/`** — Bandit enforces this (B101 is enabled; only `tests/` is exempt, via `exclude_dirs`). For a `requires_robot` command, narrow with `if app._robot is None: return` rather than an assert: `_dispatch_command` already rejects the disconnected case, and unlike `assert` the guard survives `python -O`
- The primary login path is the inline flow in `login_flow.py` (`LoginFlow` state machine: `IDLE` → `AWAITING_EMAIL` → `AWAITING_PASSWORD`). `LoginScreen` (`auth.py`) still exists as a modal but is not used in the current main flow.
- `LoginScreen` uses `event.stop()` on `Input.Submitted` and `Button.Pressed` to prevent bubbling to the App's `on_input_submitted` (relevant if re-activating the modal path)

### IoT command timing — optimistic UI updates

`sendLitterRobot4Command` (and equivalents) return as soon as the cloud **queues** the command, not when the robot applies it. Calling `robot.refresh()` immediately after gets stale data. The fix for toggle/mode commands (lock, unlock, night-light on/off/auto) is to **update the status bar widget directly** after a successful API call, without waiting for a refresh — the WebSocket subscription will confirm the final state later. Do **not** add `asyncio.sleep(N)` + `refresh()` + `_refresh_status()` for these commands.

Commands that need a confirmed cloud state before showing a result (e.g. sleep/wake, where the state isn't known from the command arg alone) use `asyncio.sleep(2)` + `refresh()` + `_refresh_status()` as a best-effort workaround, accepting the risk of briefly stale display.

## Common tasks

**Add a robot command:** create a class inheriting `Command` in `asher/commands/__init__.py`, implement `async def run(self, app, args)`, and call `_registry.register(MyCommand())`.

**Add a slash command:** create a class inheriting `SlashCommand` (sets `prefix = "/"`), implement `async def run(self, app, args)`, register it, and document in `asher/slash-commands/__init__.py`.

**Add a headless command:** write `async def _my_command(session, args) -> Result` in `asher/headless.py` and add a `HeadlessCommand(...)` entry to `COMMANDS`. The argparse subparser is generated from the registry — nothing to add in `__main__.py`. Build the `Result` with `_rows()` (read commands) or `_outcome()` (actions) so text and JSON stay in step, and raise `CommandError` rather than printing.

**Change poll interval:** `self.set_interval(300, ...)` in `on_mount`.

**Add a new cat state:** add entry to `CATS` dict in `asher/cats.py` (str for static, list[str] for animated), then call `_set_cat("name", "label")`.

**File naming convention:** no underscores in filenames (except Python-required `__init__.py` and `__main__.py`).

## Dev workflow

See `[tool.poe.tasks]` in `pyproject.toml` for the full task list (`uv run poe <task>`).

Pre-push hook (`.githooks/pre-push`) runs: ruff check → ruff format --check → mypy. Tests are not in the hook — run them manually.

## Releasing

Follow [README § Releasing](README.md#releasing) exactly, in order: `uv run poe changelog-release X.Y.Z` and commit the result → `uv run bump-my-version bump <part>` (this commits **and tags**) → `git push && git push --tags` → only then cut and push `release/X.Y.Z`.

Regenerate with `changelog-release X.Y.Z`, never plain `changelog` — the workflow lifts the `## [X.Y.Z]` section out of the committed `CHANGELOG.md` verbatim for the GitHub Release body, and a file still saying `## [Unreleased]` fails the release job. That extraction is also why hand-refinements to a section survive into the release notes, and why re-running either changelog task afterwards silently discards them: regeneration always re-derives from commits. Refine last.

## Testing notes

- Pilot-based integration tests use `app.run_test()` with `await pilot.pause()` before querying widgets
- Helper app wrappers for screens must **not** start with `Test` (pytest will try to collect them); use e.g. `LoginTestApp`
- Mock external deps with `unittest.mock.AsyncMock` for async robot/account methods
- `from pylitterbot import Account` is a local import inside `_connect_worker` — patch it at `pylitterbot.Account`, not `asher.connection.Account`
- Coverage: ~76% overall; main gaps are async exception paths and `_connect_worker` auth flow
