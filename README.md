# Asher CLI

A Claude Code-style terminal dashboard for monitoring and controlling Litter Robot via the Whisker cloud API.

<img width="808" height="351" alt="image" src="https://github.com/user-attachments/assets/6599966f-837c-419c-8692-bfda3533e730" />

## Features

- Live status bar — unit name, online/offline, drawer fill level, last activity, cat weight
- Human-readable robot status — translates raw API states into plain English (`Ready`, `Cleaning`, `Cat Detected`, `Drawer Full`, etc.)
- Scrollable activity log with timestamps
- Commands: `clean`, `status`, `lock`, `unlock`, `sleep`, `wake`, `night-light`, `history`, `help`, `quit`
- Slash commands for app management: `/login`, `/logout`, `/exit`
- Cat animation panel that reacts to robot state
- Command history (↑/↓ arrows)
- Auto-refreshes every 30 seconds

## Install

```bash
pip install asher-cli
asher
```

Or run from source:

```bash
git clone https://github.com/karanshukla/asher-cli
cd asher-cli
pip install -e .
asher
```

### Dev setup

```bash
uv sync --dev
git config core.hooksPath .githooks   # run lint + tests before every push
```

```bash
uv run poe check   # ruff + mypy + pytest (same as CI)
uv run poe fix     # auto-fix ruff issues
uv run poe test    # tests only
uv run poe types   # mypy only
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
| `night-light on\|off` | Toggle night light |
| `history` | Show last 25 activity events |
| `clear` | Clear the log |
| `help` | Show command list |
| `quit` | Exit |

### Slash commands

| Command | Description |
|---|---|
| `/login` | Sign in or switch accounts |
| `/logout` | Sign out and clear saved credentials |
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

## Testing

```bash
uv run pytest
```

CI runs on Python 3.10 / 3.11 / 3.12 across Ubuntu, Windows, and macOS on every push.

## Notes

- Uses the unofficial [pylitterbot](https://github.com/natekspencer/pylitterbot) library — supports LR3, LR4, LR5, and other Whisker robots
- The Whisker API is reverse-engineered and may change without notice
- Auth errors and network failures are shown in the UI with friendly messages
