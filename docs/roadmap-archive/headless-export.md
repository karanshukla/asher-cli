# §25 — Headless CLI export — automate history without the TUI or MCP ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §25. The original section text, preserved verbatim.

`asher --export 7` writes activity history to CSV **without launching the
TUI** — for cron, Windows Task Scheduler, systemd timers, SSH, containers.
No flags launches the interactive dashboard as before.

### Command syntax (shipped)

```
asher --export 7                         export last 7 days to ~/Downloads
asher --export 7 --output ~/hist.csv     explicit output path
asher --export month --robot "Asher 2"   30 days (Whisker ceiling) for a specific robot
```

`--robot` accepts an index or a partial, case-insensitive name; with no flag
it picks the keyring-persisted preferred robot, else `robots[0]` (same
resolution as `/robot` and `_finish_connect`). Credentials use the same
keyring → `.env` priority as the TUI but with **no interactive login prompt**
(a scheduled task can't type a password) — sign in once with `/login` first.

### Architecture

The CSV-writing core was extracted out of the TUI-bound `_run_export` so both
paths share one implementation. `asher/export.py` houses:

- `build_history_csv(robot, pets, days, dest) -> int` — pure: fetch
  (`get_activity_history(limit=500)`), filter by `now - timedelta(days=days)`,
  sort ascending, write the same 7-column CSV the TUI writes. Returns the row
  count. No Textual imports, no `_log_*`, no `_open_folder`. Reuses
  `ACTION_LABELS` / `activity_raw_text` so events render identically to the
  `history` command. Raises `ExportError` (with an exit code) on fetch/write
  failure.
- `resolve_dest(robot, output_override)` — `--output` verbatim, else the
  `~/Downloads` → `~/Documents/asher-cli` → `~` cascade the TUI uses.
- `resolve_robot(robots, selector, preferred_serial)` — mirrors `/robot` and
  `_finish_connect`; returns `None` when a selector matches nothing.
- `parse_days(raw)` — accepts a day count (1–30, clamped), `month`, or `30`.
- `_run_headless_export(args)` — the CLI entry: connect, pick robot, write
  CSV, print plain-text progress to stderr (no folder open), return the exit
  code.

`asher/connection/__init__.py` adds `_connect_headless()` (module-level, not
a `ConnectionMixin` method): tries the cached OAuth token first
(`_keyring_load_token` → `Account(token=...).connect(load_robots=True)`),
falls back to email/password from keyring → `.env`, and raises
`HeadlessAuthError(code=1)` with no creds or `code=2` on connection failure.
`.env` discovery relies on the `load_dotenv()` already called at import time,
not `find_dotenv()`'s upward search — same caveat as the MCP bridge.

`asher/commands/__init__.py`'s `_run_export` is now thin: it resolves the
dest, calls `build_history_csv`, logs progress, and opens the folder. The
`export` command and the headless path produce byte-identical CSV.

`asher/__main__.py` parses `sys.argv` with `argparse` before deciding whether
to build `AsherApp` — `--export` runs headlessly and exits; anything else
launches the TUI.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | export succeeded |
| `1` | no credentials found (keyring or `.env`) |
| `2` | connection or API failure |
| `3` | failed to write the CSV (permissions, disk full) |
| `4` | `--robot` matched no robot on the account |

### Testing

`tests/test_export.py` (41 cases) needs no Textual `Pilot` —
`build_history_csv` and `_run_headless_export` are plain async functions,
mocked the same way as `mcp_bridge.main()`. Covers: `parse_days` clamping,
`resolve_dest` cascade + override, `resolve_robot` index/name/preferred,
`build_history_csv` columns/filtering/sorting/pet-name/error paths, and
`_run_headless_export` happy path + each exit code. The existing TUI export
tests (`test_new_commands_pilot.py`) still pass unchanged — the refactor is
behaviour-preserving.

---

`export [days|month]` (§2) already writes activity history to CSV, but only
from *inside* the running interactive TUI — a human has to launch `asher`,
wait for it to connect, and type the command. That's unusable from cron,
Windows Task Scheduler, or a systemd timer. The MCP bridge (`/mcp`, shipped)
solves automation for an AI assistant talking to the robot, but it doesn't
help someone who just wants `asher --export 7` in a nightly script with no
Claude Desktop involved at all.

### Command syntax

```
asher --export 7                        export last 7 days to the default path
asher --export 7 --output ~/hist.csv    explicit output path
asher --export month --robot "Asher 2"  export 30 days for a specific robot
```

No flags → today's behavior unchanged: launches the interactive TUI. Any
recognized flag → run headlessly and exit; the Textual `App` is never
constructed, so this works over SSH, in a container, or from Task Scheduler
with no terminal attached.

### Entry point changes

`asher/__main__.py` parses `sys.argv` with `argparse` *before* deciding
whether to build `AsherApp`:

```python
def main() -> None:
    args = _parse_args()
    if args.export is not None:
        sys.exit(asyncio.run(_run_headless_export(args)))
    AsherApp().run()
```

### Decouple `_run_export` from Textual

`_run_export(app, days)` in `asher/commands/__init__.py` currently logs via
`app._log_info` / `_log_err` / `_log_ok` (RichLog writes) and always opens
the output folder in the OS file explorer — neither makes sense headlessly
(no widget tree, no desktop session on a server). Split the CSV-writing core
out into a plain function both paths share:

```python
async def build_history_csv(
    robot: RobotProtocol, pets: list, days: int, dest: Path,
) -> None:
    """Pure logic: fetch, filter, write. No Textual, no I/O side effects beyond dest."""
    ...

async def _run_export(app: AsherApp, days: int) -> None:
    # existing TUI path: resolve dest via app, call build_history_csv,
    # log via app._log_*, then _open_folder(dest)

async def _run_headless_export(args: argparse.Namespace) -> int:
    # connect via keyring -> .env (same priority as _connect_worker), no
    # interactive login possible - print a clear error and exit 1 if missing
    # resolve robot by --robot or keyring preferred_robot or robots[0]
    # call build_history_csv, print plain text to stdout/stderr, no folder-open
```

### Credentials — same priority, no interactive fallback

Headless mode can't prompt for a password. Priority stays keyring → `.env`,
but if neither has credentials, print an actionable error and exit non-zero
rather than starting the inline login flow (there's no command bar to type
into). This mirrors the constraint already documented for the MCP bridge:
a scheduled task's environment can't be assumed to match the project's
working directory, so `.env` discovery should not rely on `find_dotenv()`'s
upward directory search — same caveat as `asher/mcp_bridge.py`.

### Exit codes (for shell scripting)

| Code | Meaning |
|---|---|
| `0` | Export succeeded |
| `1` | No credentials found (keyring or `.env`) |
| `2` | Connection or API failure |
| `3` | Failed to write the CSV (permissions, disk full) |
| `4` | `--robot` selector matched no robot on the account |

### Example automation

```bash
# crontab -e — nightly export at 03:00
0 3 * * * /usr/bin/env asher --export 7 --output /home/me/litter-history.csv >> /var/log/asher-export.log 2>&1
```

```powershell
# Windows Task Scheduler action
asher.exe --export 7 --output C:\Users\me\litter-history.csv
```

### Testing

No Textual `Pilot` needed — `build_history_csv` and `_run_headless_export`
are plain async functions, testable the same way as `mcp_bridge.main()`
(§ MCP bridge): mock `Account.connect`, mock `robot.get_activity_history`,
assert on the written CSV content and the returned exit code.
