# Asher CLI

A Claude Code-style terminal dashboard for monitoring and controlling Litter Robot via a Python Whisker cloud API

<img width="808" height="351" alt="image" src="https://github.com/user-attachments/assets/6599966f-837c-419c-8692-bfda3533e730" />

## Features

- Live status bar — unit name, online/offline, drawer fill level, last activity, cat weight
- Scrollable activity log with timestamps
- Command prompt supporting: `clean`, `status`, `lock`, `unlock`, `sleep`, `wake`, `night-light`, `history`, `help`, `quit`
- Cat animation panel that reacts to robot state
- Command history (↑/↓ arrows)
- Auto-refreshes every 30 seconds

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Create `.env`

```env
LITTER_ROBOT_USER=your@email.com
LITTER_ROBOT_PASSWORD=yourpassword
```

Both `LITTER_ROBOT_USER`/`LITTER_ROBOT_PASSWORD` and `LR4_EMAIL`/`LR4_PASSWORD` are accepted.

### 3. Run

```bash
python app.py
```

## Commands

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

**Keyboard shortcuts:** `Ctrl+L` clears the log, `Ctrl+C` quits.

## Notes

- Uses the unofficial [pylitterbot](https://github.com/natekspencer/pylitterbot) library — supports LR3, LR4, LR5, and other Whisker robots
- The Whisker API is reverse-engineered and may change without notice
- Auth errors and network failures are shown in the UI with friendly messages
