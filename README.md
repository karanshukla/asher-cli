# Asher CLI

[![PyPI](https://img.shields.io/badge/PyPI-asher--cli-blue?logo=pypi&logoColor=white)](https://pypi.org/project/asher-cli/)
![PyPI - Version](https://img.shields.io/pypi/v/asher-cli?label=latest%20version)
[![Python](https://img.shields.io/pypi/pyversions/asher-cli)](https://pypi.org/project/asher-cli/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![CI](https://github.com/karanshukla/asher-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/karanshukla/asher-cli/actions/workflows/ci.yml)
[![Coverage Status](https://coveralls.io/repos/github/karanshukla/asher-cli/badge.svg?branch=main)](https://coveralls.io/github/karanshukla/asher-cli?branch=main)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A Claude Code-style terminal dashboard for monitoring and controlling Litter Robot via the Whisker cloud API.

<img width="808" height="351" alt="image" src="https://github.com/user-attachments/assets/6599966f-837c-419c-8692-bfda3533e730" />

## Features

- Live status bar — unit name, online/offline, drawer fill level, last activity, cat weight
- Human-readable robot status — translates raw API states into plain English (`Ready`, `Cleaning`, `Cat Detected`, `Drawer Full`, etc.)
- Real-time cycling indicator with elapsed time (`⟳ Cycling  M:SS`)
- Fault & safety monitoring — model-scoped in-panel alerts for cat detected, pinch, motor/position/gas faults (LR5: bonnet/laser/drawer); press `d` to dismiss
- Cat panel with mode label + status badges (status chip, lock, night light, sleep, wait time) under the art
- Scrollable activity-history pager — `history [count|all]` opens a full-screen, paginated view (arrow keys, `Page Up`/`Page Down`, `Home`/`End`); `c` copies the whole history to the clipboard; `q`/`Esc`/`Enter` to close
- Commands: `clean`, `status`, `info`, `lock`, `unlock`, `sleep`, `wake`, `night-light on|off|auto`, `night-light-brightness`, `panel-brightness <low|medium|high>` (LR4/LR5), `wait-time`, `power on|off`, `rename`, `insight`, `sleep-schedule`, plus LR5 extras (`privacy`, `volume`, `camera-audio`, `drawer-reset`), `history [count|all]`, `export [days|month]`, `help`, `quit`
- Slash commands for app management: `/login`, `/logout`, `/robots`, `/robot <index|name>`, `/pets`, `/pet <index|name>`, `/cat on|off|colour <hex>`, `/refresh [seconds|off]`, `/config`, `/notify on|off|sound on|off|test`, `/version`, `/mcp on|off|status`, `/exit`
- Slash-command tab completion — type `/` and a Claude Code-style overlay lists matching commands; `↑`/`↓` to move, `Tab` or `Enter` to accept, `Esc` to dismiss
- Inline ghost-text completion for bare commands — type a prefix (`cle`) and the rest (`an`) appears greyed; `Tab` or `→` to accept → `clean`
- Headless mode — every robot command also runs without the TUI (`asher status`, `asher clean`, `asher night-light auto`, `asher export 7`), with `--json` output and documented exit codes for cron / Task Scheduler / SSH
- Catppuccin Mocha throughout — one palette in `asher/theme.py` drives the TUI stylesheet and every Rich style
- Cat animation panel that reacts to robot state
- Command history (↑/↓ arrows)
- Real-time updates via WebSocket; 5-minute poll fallback

## Install

### With pipx (recommended)

```bash
pipx install asher-cli
asher
```

`pipx` installs the CLI into an isolated environment and puts `asher` on your PATH automatically. Install `pipx` with `pip install pipx` if you don't have it.

### With pip

```bash
pip install asher-cli
asher
```

### With uv

```bash
uv tool install asher-cli
asher
```

### Run from source

```bash
git clone https://github.com/karanshukla/asher-cli
cd asher-cli
uv sync
uv run asher
```

## Credentials

On first run, type `/login` at the command prompt. Your credentials are saved to the OS keyring (Windows Credential Manager / macOS Keychain / Linux Secret Service) and reused automatically on subsequent runs.

To sign out: `/logout`

`.env` fallback (for CI or existing users):

```env
LITTER_ROBOT_USER=your@email.com
LITTER_ROBOT_PASSWORD=yourpassword
```

## Commands

### Robot commands

| Command | Description |
|---|---|
| `clean` | Start a clean cycle |
| `status` | Refresh and show what matters — online state, drawer level, last activity |
| `info` | Full dump of all robot properties (serial, firmware, all settings) |
| `lock` / `unlock` | Toggle panel lockout |
| `sleep` / `wake` | Toggle sleep mode |
| `night-light on\|off\|auto` | Set night light mode |
| `night-light-brightness <level>` | Set brightness (LR5: 0-100; LR4: 25/50/100) |
| `panel-brightness <low\|medium\|high>` | Set control-panel brightness (LR4/LR5 only; shows current if omitted) |
| `wait-time <minutes>` | Set clean-cycle wait time (shows valid values / current if omitted) |
| `power on\|off` | Hard-power the unit on or off |
| `rename <new name>` | Rename the unit in the Whisker cloud |
| `insight [days\|month]` | Show cycle-usage statistics (default: 30 days) |
| `sleep-schedule` | Show the per-day sleep schedule (read-only) |
| `privacy on\|off` | Toggle LR5 privacy mode |
| `volume <0-100>` | Set LR5 sound volume |
| `camera-audio on\|off` | Toggle LR5 camera audio |
| `drawer-reset` | Reset the LR5 waste drawer level indicator |
| `history [count\|all]` | Show recent activity in a scrollable pager (default: 50 events) |
| `export [days\|month]` | Export activity history to CSV in `~/Downloads` (default: 30 days) |
| `clear` | Clear the log |
| `help` | Show command list |
| `quit` | Exit |

### Slash commands

| Command | Description |
|---|---|
| `/login` | Sign in or switch accounts |
| `/logout` | Sign out and clear saved credentials |
| `/robots` | List all robots on the account |
| `/robot <index\|name>` | Switch active robot (selection persists to keyring) |
| `/pets` | List all pets on the account |
| `/pet <index\|name>` | Switch which pet's name/weight shows in the status bar |
| `/cat on\|off` | Show or hide the cat animation panel |
| `/cat colour <hex>` | Change the cat art colour (e.g. `/cat colour #ff79c6`); `color` also accepted; `/cat reset` to revert |
| `/refresh [seconds\|off]` | Change the auto-poll interval or disable it (`/refresh 60`, `/refresh off`) |
| `/config` | Show current runtime settings (robot, refresh rate, cat panel, active pet, notifications) |
| `/notify on\|off\|sound on\|off\|test` | Toggle desktop toast notifications for fault events (cat detected, pinch, motor fault, drawer full); `test` fires a sample toast |
| `/version` | Show version info (asher-cli, Python, pylitterbot, textual) |
| `/mcp on\|off\|status` | Toggle the Litter-Robot MCP server entry in Claude Desktop |
| `/exit` | Exit Asher CLI |

**Keyboard shortcuts:** `Ctrl+L` clears the log, `Ctrl+C` quits. While typing a `/` slash command, `↑`/`↓` move through completions, `Tab` or `Enter` accepts, `Esc` dismisses. While typing a bare command, a greyed ghost suggestion appears — `Tab` or `→` accepts it.

### Headless commands (cron / Task Scheduler / SSH)

Every robot action the dashboard offers is also a subcommand that runs **without launching the TUI** — `asher` with no arguments still opens the interactive dashboard.

```bash
asher status                             at-a-glance state
asher info                               model, serial, firmware, settings
asher clean                              start a clean cycle
asher night-light auto                   set night light mode
asher wait-time 7                        set the clean-cycle wait time
asher history 20                         recent activity, newest first
asher insight 7                          cycle-usage statistics
asher export 7 --output ~/hist.csv       activity history to CSV
```

`asher --help` lists every command; `asher <command> --help` shows its arguments. The full set: `status`, `info`, `robots`, `pets`, `history`, `insight`, `sleep-schedule`, `clean`, `lock`, `unlock`, `sleep`, `wake`, `night-light`, `night-light-brightness`, `panel-brightness`, `wait-time`, `power`, `rename`, `privacy`, `volume`, `camera-audio`, `drawer-reset`, `export`.

Two flags apply to all of them:

- `--robot <index|name>` — an index or a partial, case-insensitive name (defaults to your saved preferred robot, else the first)
- `--json` — machine-readable output instead of aligned text, for piping into `jq`

```bash
asher status --json | jq -r '.drawer'
asher history 50 --json | jq '[.events[] | select(.event | startswith("Cat"))] | length'
```

Credentials use the same keyring → `.env` priority as the TUI, but with **no interactive login prompt** — a scheduled task can't type a password, so sign in once with `/login` first.

Exit codes for scripting:

| Code | Meaning |
|---|---|
| `0` | command succeeded |
| `1` | no credentials found (keyring or `.env`) |
| `2` | connection or API failure |
| `3` | failed to write the CSV (permissions, disk full) |
| `4` | `--robot` matched no robot on the account |
| `5` | bad argument, or the robot/cloud rejected the command |

```bash
# crontab — nightly export at 03:00
0 3 * * * /usr/bin/env asher export 7 --output /home/me/litter-history.csv >> /var/log/asher-export.log 2>&1

# alert when the drawer passes 85%
0 * * * * [ "$(asher status --json | jq -r '.drawer' | tr -d %)" -gt 85 ] && notify-send "Litter drawer full"
```

```powershell
# Windows Task Scheduler action
asher.exe export 7 --output C:\Users\me\litter-history.csv
```

`asher --export [days]` remains as a deprecated alias for `asher export [days]`, so existing cron entries keep working.

## Configuration

Runtime settings persist across restarts in `~/.asher-cli/config.json`, so you don't have to re-apply `/refresh 60`, `/cat colour #ff79c6`, or `/pet 1` every launch. The file is auto-created on first change and holds six non-secret UI preferences:

| Setting | Slash command | Default |
|---|---|---|
| `poll_interval_seconds` | `/refresh <seconds\|off>` | `300` |
| `cat_panel_visible` | `/cat on\|off` | `true` |
| `cat_panel_color` | `/cat colour <hex>\|reset` | `null` (default palette) |
| `active_pet_index` | `/pet <index\|name>` | `0` |
| `notifications` | `/notify on\|off` | `true` |
| `notification_sound` | `/notify sound on\|off` | `false` |

Credentials and the preferred-robot serial stay in the OS keyring; `.env` vars stay as env vars. You generally don't need to edit the file by hand — just use the slash commands — but it's plain JSON and safe to inspect or delete (deleting it restores defaults).

## Releasing

```bash
# 1. regenerate CHANGELOG.md from conventional commits (idempotent), then commit it
uv run poe changelog
git add CHANGELOG.md
git commit -m "docs(changelog): update for next release"

# 2. bump version, commit, and tag in one step, then push with tags
uv run bump-my-version bump patch    # 0.2.0 → 0.2.1
uv run bump-my-version bump minor    # 0.2.0 → 0.3.0
uv run bump-my-version bump major    # 0.2.0 → 1.0.0

git push && git push --tags

# 3. push the release branch to trigger PyPI publish (OIDC) + GitHub Release
#    (release notes auto-generated by git-cliff from the same cliff.toml)
git checkout -b release/X.Y.Z
git push origin release/X.Y.Z
```

`CHANGELOG.md` is generated by [git-cliff](https://git-cliff.org) from
conventional commits — see [`cliff.toml`](cliff.toml). Commit messages must use
`feat:`/`fix:`/`docs:`/etc. prefixes (optionally scoped, e.g. `feat(robot):`)
to appear in the changelog.

## Troubleshooting

**`asher` not found after `pip install asher-cli`**

Python's `Scripts` folder isn't on your PATH. Use `pipx` instead — it handles this automatically:

```bash
pip install pipx
pipx install asher-cli
asher
```

If you're in a virtualenv, deactivate it first:

```bash
deactivate
pip install pipx
pipx install asher-cli
```

**`pipx: command not found`**

Run it as a module instead:

```bash
python -m pip install pipx
python -m pipx install asher-cli
```

## Dev Setup

### 1. Clone and install

```bash
git clone https://github.com/karanshukla/asher-cli
cd asher-cli
uv sync                                        # installs all deps including the dev group
git config core.hooksPath .githooks            # lint + type checks run before every push
```

### 2. Configure environment (optional)

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
LITTER_ROBOT_USER=your@email.com
LITTER_ROBOT_PASSWORD=yourpassword
ASHER_CLI_DEV_MODE=true    # sets version to "dev" instead of the installed package version
```

### 3. Run with hot reload

**CSS hot reload** — Textual's devtools watch inline `CSS` strings and `.tcss` files and reload them in-place without restarting:

```bash
uv run poe dev
# equivalent to: textual run --dev asher/__main__.py
```

**Python auto-restart** — true in-process reload isn't possible with Textual's event loop, but `watchfiles` will kill and relaunch the app whenever a `.py` file changes in `asher/`:

```bash
uv run poe watch
# equivalent to: watchfiles --filter python 'python -m asher' asher
```

You can combine both — run `poe watch` for Python changes and it will naturally pick up CSS changes too on restart.

### 4. Run tests

```bash
uv run poe test                  # run all tests
uv run pytest tests/ --cov=asher # with coverage report
```

### 5. Lint, format, type-check

```bash
uv run poe fix     # auto-fix ruff issues
uv run poe lint    # check only (no fixes)
uv run poe fmt     # check formatting
uv run poe types   # mypy
uv run poe check   # run all of the above + tests (same as CI)
```

### 6. Security scan

```bash
uv run poe security # bandit, same config the Bandit workflow uses
```

Scan settings live in `[tool.bandit]` in `pyproject.toml`, so local runs and the
Bandit workflow report identical findings. Results from `main` and pull requests
are published to the repository's **Security → Code scanning** tab.

CI runs on Python 3.10 / 3.11 / 3.12 across Ubuntu, Windows, and macOS on every push.

## Changelog

The full, maintained release history lives in [CHANGELOG.md](CHANGELOG.md),
auto-generated from conventional commits by [git-cliff](https://git-cliff.org).

## Notes

- Uses the unofficial [pylitterbot](https://github.com/natekspencer/pylitterbot) library — supports LR3, LR4, LR5, and other Whisker robots
- The Whisker API is reverse-engineered and may change without notice
- Auth errors and network failures are shown in the UI with friendly messages
