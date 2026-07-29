# §2 — History export to CSV ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §2. The original section text, preserved verbatim.

Writes activity history to a CSV file and opens the containing folder in the OS file explorer.

### Command syntax

`export` is a bare robot command (no `/` prefix) — it queries the robot for history and produces a local file artifact.

```
export            export last 30 days (Whisker API maximum — good default)
export 7          export last 7 days
export 14         export last 14 days
export month      alias for 30 days — explicit "I want everything Whisker will give me"
```

Whisker caps history at 30 days regardless of what you request — this is the hard ceiling.

### CSV columns

| Column | Source | Example |
|---|---|---|
| `timestamp` | `act.timestamp`, converted to local timezone, ISO 8601 | `2026-06-20T14:32:00+10:00` |
| `event` | human label from `ACTION_LABELS` map (§11) | `Clean cycle complete` |
| `raw_event` | `act.action.text` or `str(act.action)` | `Clean Cycle Complete` |
| `weight_lb` | `act.weight` | `9.1` |
| `pet_name` | resolved from `account.pets` by `pet_id` | `Asher` |
| `robot_name` | `robot.name` | `Idiot Box` |
| `robot_serial` | `robot.serial` | `LR4C012345` |

Rows sorted ascending by timestamp (oldest first). Empty cells left blank — no `null` or `N/A`.

### Output path

Default: `~/Downloads/asher-<serial>-<YYYY-MM-DD>.csv`

Example: `~/Downloads/asher-LR4C012345-2026-06-20.csv`

`~/Downloads` is the standard export destination on Windows, macOS, and most Linux desktops. If it doesn't exist, fall back to `~/Documents/asher-cli/` (create if needed), then `~`.

### Open folder after export

After writing, open the containing directory in the OS file explorer:

```python
import subprocess, sys
from pathlib import Path

def _open_folder(path: Path) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])
```

`explorer /select,<file>` highlights the specific file in Windows Explorer rather than just opening the folder — gives instant visual confirmation. `open -R` does the same in macOS Finder. Linux falls back to opening the parent directory with the default file manager.

### Log output during export

```
  Fetching history (last 30 days)…
  Writing asher-LR4C012345-2026-06-20.csv… 128 events
  Saved → ~/Downloads/asher-LR4C012345-2026-06-20.csv
  Opening folder…
```

Error cases:
- No robot connected → `"No robot connected"` (same as other robot commands)
- API failure → `"Failed to fetch history: <message>"`
- Write failure → `"Failed to write CSV: <message>"` (e.g. permissions issue) + suggest fallback path

### Data fetching

`get_activity_history(limit=N)` doesn't accept a date range — it returns the most recent N events. To implement day-based filtering:

1. Fetch with a high limit (e.g. `limit=500`) to ensure full coverage up to 30 days
2. Filter client-side: keep only events where `act.timestamp >= now - timedelta(days=N)`

For LR5, the richer `get_activities(limit, offset, activity_type)` (see §4) could be used for paginated export, but `get_activity_history` works for all models.

### Implementation sketch

Add `ExportCommand` in `asher/commands/__init__.py` inheriting `Command`:

```python
class ExportCommand(Command):
    name = "export"
    description = "export activity history to CSV"
    requires_robot = True

    async def run(self, app: AsherApp, args: list[str]) -> None:
        # parse days arg
        raw = args[0].lower() if args else "month"
        if raw in ("month", "30"):
            days = 30
        else:
            try:
                days = max(1, min(30, int(raw)))
            except ValueError:
                app._log_warn(f"Unknown period '{raw}' — use a number of days or 'month'")
                return

        await _run_export(app, days)
```

`_run_export` is a module-level async function (not a method) to keep `ExportCommand.run` thin and the logic independently testable.

### Naming note

The `help` output should list `export` alongside other robot commands, with a note on accepted args:

```
  export [days|month]   export activity history to CSV (default: 30 days)
```
