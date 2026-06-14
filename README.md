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
| `status` | Refresh and show full status |
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

## Notes

- Uses the unofficial [pylitterbot](https://github.com/natekspencer/pylitterbot) library — supports LR3, LR4, LR5, and other Whisker robots
- The Whisker API is reverse-engineered and may change without notice
- Auth errors and network failures are shown in the UI with friendly messages
