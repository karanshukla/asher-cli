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
- Scrollable activity log with timestamps
- Commands: `clean`, `status`, `lock`, `unlock`, `sleep`, `wake`, `night-light on|off|auto`, `night-light-brightness`, `history`, `export [days|month]`, `help`, `quit`
- Slash commands for app management: `/login`, `/logout`, `/robots`, `/robot <index|name>`, `/pets`, `/pet <index|name>`, `/cat on|off|color <hex>`, `/refresh [seconds|off]`, `/config`, `/exit`
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
| `history` | Show last 25 activity events |
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
| `/cat color <hex>` | Change the cat art colour (e.g. `/cat color #ff79c6`); `/cat reset` to revert |
| `/refresh [seconds\|off]` | Change the auto-poll interval or disable it (`/refresh 60`, `/refresh off`) |
| `/config` | Show current runtime settings (robot, refresh rate, cat panel, active pet) |
| `/exit` | Exit Asher CLI |

**Keyboard shortcuts:** `Ctrl+L` clears the log, `Ctrl+C` quits.

## Releasing

```bash
# bump version, commit, and tag in one step
uv run bump-my-version bump patch    # 0.0.1 → 0.0.2
uv run bump-my-version bump minor    # 0.0.2 → 0.1.0
uv run bump-my-version bump major    # 0.1.0 → 1.0.0

# then push the release branch to trigger PyPI publish
git checkout -b release/0.0.2
git push origin release/0.0.2
```

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

CI runs on Python 3.10 / 3.11 / 3.12 across Ubuntu, Windows, and macOS on every push.

## Notes

- Uses the unofficial [pylitterbot](https://github.com/natekspencer/pylitterbot) library — supports LR3, LR4, LR5, and other Whisker robots
- The Whisker API is reverse-engineered and may change without notice
- Auth errors and network failures are shown in the UI with friendly messages
