# Asher CLI — Roadmap & Feature Gaps

What's left to build — grounded in what `pylitterbot` actually exposes today.

> Completed items are marked `~~strikethrough~~ ✅` inline and their full design
> notes have been moved to [`roadmap-archive/`](roadmap-archive/README.md)
> so this file reads as a short list of what's left to build. Process and
> reference material (tests, CI, versioning, releasing) lives in
> [`CONTRIBUTING.md`](CONTRIBUTING.md). Section numbers are stable; gaps are
> archived or moved sections.

---

## What's working now

| Area | Status |
|---|---|
| Auth — OS keyring (cached OAuth token, then email/password) → inline `/login` prompt; `.env` only in dev mode | ✅ |
| Connect & load robots; preferred robot persisted to keyring and restored on launch | ✅ |
| Status bar top row — name + model, contextual online label (Cycling/Paused/Cat inside/Cycle done/Drawer full/Offline), night light mode + brightness, panel lock | ✅ |
| Status bar second row — drawer %, litter %, cat weight (with pet name), last visit | ✅ |
| Robot commands: clean, status, info, lock, unlock, sleep, wake, night-light on/off/auto/color, night-light-brightness, panel-brightness, wait-time, power on/off, rename, insight, sleep-schedule (view/set/disable), history [count\|all] [--type], export [days\|month]; LR5: privacy, volume, camera-audio, drawer-reset (refused gracefully on LR3/LR4) | ✅ |
| Slash commands: `/login`, `/logout`, `/help`, `/robots`, `/robot`, `/pets`, `/pet`, `/cat`, `/refresh`, `/config`, `/notify`, `/watch`, `/mcp`, `/version` — `/`-overlay + ghost-text completion | ✅ |
| Runtime settings persisted to `~/.asher-cli/config.json` | ✅ |
| MCP bridge — keyring-backed `pylitterbot[mcp]` launcher, writes/removes the Claude Desktop config entry (incl. Windows MSIX path) | ✅ |
| Activity history pager (`HistoryScreen`) with readable, colour-coded labels; `c` copies all | ✅ |
| Cat panel — animated art, mode label, status badges (status, power, cycles, wait) | ✅ |
| Fault & safety monitoring — `#fault-banner` driven by `asher/core/faults.py`; `d` dismisses | ✅ |
| Desktop notifications + audible alert on fault transitions (`/notify`) | ✅ |
| Real-time WebSocket updates; 300 s poll fallback | ✅ |
| `⟳ Cycling M:SS` chip with live elapsed time | ✅ |
| LR3 / LR4 / LR5 via the `RobotAdapter` pattern (`asher/robot/adapters.py`) | ✅ |
| Headless commands — `asher <command>` with `--robot` / `--json`, documented exit codes, no TUI (`asher/headless.py`) | ✅ |
| Background watcher daemon — `asher watch start\|stop\|status\|run\|enable\|disable`, `/watch` from the TUI (`asher/desktop/daemon.py`, `watcher.py`) | ✅ |
| System tray icon over the watcher, degrades to headless (`asher/desktop/tray.py`) | ✅ |
| Login-item autostart — launchd / systemd `--user` / Windows registry (`asher watch enable`) | ✅ |
| PyPI update check — once a day, report-only (`asher update`, `/version`) | ✅ |
| PyPI release workflow (`release.yml` — `release/*` branches) | ✅ |

---

## ~~1. Slash commands — configuration at runtime~~ ✅ → [archived](roadmap-archive/runtime-slash-commands.md)

`/robots` `/robot` `/login` `/logout` `/cat` `/refresh` `/config` `/pet`. Still open from this area: `/cat style` and friends — see §14.

---

## ~~2. History export to CSV~~ ✅ → [archived](roadmap-archive/history-export.md)

`export [days|month]` writes activity history to `~/Downloads/asher-<serial>-<date>.csv` and opens the folder. Shipped — full design notes moved to the archive.

---

## 3. Robot commands

~~`status`/`info` split, `power`, `wait-time`, `panel-brightness`, `rename`, `insight`~~ ✅ → [archived](roadmap-archive/robot-commands.md)

### Read-only firmware check in `info`

```python
has_update = await robot.has_firmware_update()
details    = await robot.get_firmware_details()
```

Harmless (LR4/LR5), and `info` already shows the current `firmware` string. A
`Firmware update  available` row would be enough.

### `reset` / `reset-settings` / firmware update — deliberately omitted

`reset_settings()` exists on all three models (a full `reset()` does not);
`update_firmware()` triggers a remote update on the physical device. Both are
destructive and irreversible, so they stay unwired. If ever added they need a
`--confirm` flag or an "are you sure?" prompt — a fat-fingered `reset` shouldn't
be one keystroke away.

---

## 4. LR5-only features

~~`privacy`, `volume`, `camera-audio`, `drawer-reset`, `night-light color`, `Filter due`~~ ✅ → [archived](roadmap-archive/lr5-features.md)

Open:
- **Camera** — `camera_metadata` is exposed; snapshots/streams would need more
  than pylitterbot gives today.
- **Hopper** — `hopper_status` / `hopper_status_text` / `is_hopper_removed` /
  `hopper_fault` are readable; could surface in `info` and the fault banner
  (the hopper is never a fault today — see `asher/core/faults.py`).

---

## 5. Feeder Robot support

`pylitterbot` supports the Feeder Robot and `account.robots` includes it, but
the app treats every robot as a litter box — the default (preferred or
`robots[0]`) could be the feeder.

- Filter the robot list, or give the feeder its own adapter/sub-context
- Feeder commands:

```
snack             → await robot.give_snack()
gravity on/off    → await robot.set_gravity_mode(bool)
meal-size <n>     → await robot.set_meal_insert_size(float)
```

---

## ~~6. Real-time WebSocket updates~~ ✅ → [archived](roadmap-archive/websocket-updates.md)

`robot.subscribe()` in `asher/tui/monitoring.py`; the poll is a 300 s fallback for activity history.

---

## 7. Pet features

~~Multi-pet (`/pets`, `/pet`)~~ ✅ → [archived](roadmap-archive/multi-pet.md)

### Weight history sparkline

```python
history = await pet.fetch_weight_history(limit=60)   # list[WeightMeasurement]
```

```
  Asher weight — last 14 days
  9.1 ▁▂▂▁▂▂▃▂▂▁▁▂▂▂  8.8 lb avg
```

In the log, or replacing the idle cat in the panel.

### Pet detail card

```
/pet info
  Name      Asher
  Breed     Domestic Shorthair
  Age       4 yrs
  Weight    9.1 lb (last reading 2h ago)
  Visits    6 this week
```

### Visit reassignment (LR5 only)

```python
await robot.reassign_pet_visit(event_id, from_pet_id=..., to_pet_id=...)
```

Corrects a visit weight-ID pinned on the wrong cat.

---

## ~~8. Sleep schedule~~ ✅ → [archived](roadmap-archive/sleep-schedule.md)

`sleep-schedule` viewer + `set`/`disable`, per-model `sleep`/`wake`.

---

## ~~9. Fault monitoring & alerts~~ ✅ → [archived](roadmap-archive/fault-monitoring.md)

Model-scoped fault detection (`asher/core/faults.py`) drives the in-panel `#fault-banner`; `d` dismisses. Shipped — full design notes moved to the archive.

---

## ~~10. Config file persistence~~ ✅ → [archived](roadmap-archive/config-persistence.md)

~/.asher-cli/config.json persists /refresh, /cat, /pet across restarts. Shipped — full design notes moved to the archive.

---

## 11. UI / UX gaps

~~Litter level, colour-coded status, cycle counter, readable history + dated timestamps, history pager, cycling indicator, `history --type`~~ ✅ → [archived](roadmap-archive/ui-ux.md)

### Status bar: Wi-Fi dot

No model exposes the SSID. `info` already renders the LR4 `wifi_mode_status`
readably; the status bar doesn't show anything yet.

| Model | Available |
|---|---|
| LR5 | `wifi_rssi` (dBm) — `>= -60` excellent, `>= -70` good, `>= -80` weak, else poor → `▂▄▆█` bars |
| LR4 | `wifi_mode_status` — `ROUTER_CONNECTED` green; `*_WAITING` / `*_FAULT` amber; `OFF`/`NONE` muted |
| LR3 | nothing |

### Cat presence distinct from a fault

`LitterBoxStatus.CAT_DETECTED` is in the fault table in `asher/core/faults.py`
("cycle halted"), so a cat simply using the box raises `#fault-banner` and
flips the cat panel to `error`. The top-row chip already says `~ Cat inside`.
Live presence is ambient state, not a safety event: drop it from the fault set
(keep a real halt — e.g. cat detected mid-cycle — as the fault) and give it a
`"visiting…"` cat mode instead.

### Tabs for multiple robots

`TabbedContent` when `len(robots) > 1`, so switching doesn't need `/robot n`.

### `history` pagination

`history all` tops out at 500 events. LR5's `get_activities(limit, offset, …)`
takes an `offset` the adapter doesn't use yet; LR3/LR4 have no offset at all.

### `scoops_saved_count`

The `cycles` badge shipped; scoops-saved (vs. a traditional box) is the other
vanity stat for the cat panel.

---

## 12. Stretch / nice-to-have

| Idea | Notes |
|---|---|
| `/theme light` | `asher/core/theme.py` already routes everything through semantic roles behind `$asher-*` variables; this is repointing them at Catppuccin Latte plus a command to switch |
| Reconnect banner | `_poll_status_interval` in `asher/tui/monitoring.py` swallows every exception — a dropped connection is invisible. Show a banner and retry with backoff (the watcher already does, in `asher/desktop/watcher.py`) |
| Robot picker at startup | Prompt when there are several robots and no preferred serial. Low value now the choice persists |
| `StatusBar` / `CatPanel` widgets | Left over from the old §19 refactor: the header and cat panel are still containers of `Static`s queried from the mixins. Extracting them would give each one `update(robot)` |

---

## 13. Account management

~~Credential + token persistence~~ ✅ → [archived](roadmap-archive/credentials.md) — now `asher/core/credentials.py`.

### `/account`

```
/account              show logged-in email and user_id
/account refresh      re-fetch all robots and pets from the API
```

### Multi-account (stretch)

`Account` is stateless enough to hold several. `/account switch 1` would need a
list of cached tokens in the keyring rather than one.

---

## 14. Slash commands — what's left

~~Parsing, `/robot` `/pets` `/pet` `/refresh` `/cat` `/config` `/notify`, `export`, tab completion~~ ✅ → [archived](roadmap-archive/slash-command-spec.md)

| Command | Description | Note |
|---|---|---|
| `/config set <key> <val>` | Change a setting | `asher.core.config.update()` |
| `/cat style <n>` | Alternate ASCII art set | Swap `CATS` in `asher/tui/cats.py` |
| `/log [n]` | Max log lines to keep | `RichLog(max_lines=n)` |
| `/theme [dark\|light]` | See §12 | |
| `/account` | See §13 | |

---

## 15. PyPI publishing → [CONTRIBUTING.md § Releasing](CONTRIBUTING.md#releasing)

Live. Moved to the contributor guide.

---

## 16. Standalone binary — no Python required

`pipx` / `uv tool` installs are covered in the README. What's left is a true
standalone binary built in CI and attached to the GitHub Release.

**PyInstaller**

```bash
pyinstaller --onefile --name asher --collect-data textual asher/__main__.py
```

- `textual` ships CSS/assets that need `--collect-data textual`; so does
  `asher/tui/style.tcss`.
- `aiohttp` (via pylitterbot) has C extensions — bundle the right platform wheels.
- `keyring` backends are discovered via entry points; check they survive freezing.
- ~30–60 MB, no Python needed.

**Nuitka** — `python -m nuitka --standalone --onefile asher/__main__.py`.
Slower build, smaller/faster binary.

Checklist:
- [ ] `build.yml` matrix (ubuntu / windows / macos) running one of the above
- [ ] Binaries attached to the GitHub Release by `release.yml`

---

## 17. Testing → [CONTRIBUTING.md § Testing](CONTRIBUTING.md#testing)

Unit, Pilot integration/E2E ([archived](roadmap-archive/e2e-pilot.md)), coverage — all live. Reference moved to the contributor guide.

---

## ~~18. Cat panel — robot status badges underneath the art~~ ✅ → [archived](roadmap-archive/cat-panel-badges.md)

#cat-status widget under the cat art (status chip, lock, sleep, night light, wait). Shipped — full design notes moved to the archive.

---

## ~~19. Architecture refactor~~ — dropped, see [archive](roadmap-archive/README.md#dropped)

Written for the old single-file `app.py`; the package split happened. Widget extraction is the one open leftover (§12).

---

## 20. Versioning → [CONTRIBUTING.md § Versioning](CONTRIBUTING.md#versioning)

## 21. CI / CD → [CONTRIBUTING.md § CI / CD](CONTRIBUTING.md#ci--cd)

---

## ~~22. Desktop notifications~~ ✅ → [archived](roadmap-archive/desktop-notifications.md)

OS-level toast notifications on fault state transitions (cat detected, pinch, motor/retract faults, drawer full), plus an audible alert and a `/notify on|off|sound on|off|test` slash command that persists. Shipped — full design notes moved to the archive.

---

## ~~23. Tab completion for slash commands~~ ✅ → [archived](roadmap-archive/tab-completion.md)

Claude Code-style / overlay + inline ghost-text completion. Shipped — full design notes moved to the archive.

---

## ~~24. Version display~~ ✅ → [archived](roadmap-archive/version-display.md)

Version in the title chip, `/version`, model badge on `#robot-lbl`.

---

## ~~25. Headless CLI export — automate history without the TUI or MCP~~ ✅ → [archived](roadmap-archive/headless-export.md)

asher --export 7 writes CSV without launching the TUI, for cron/Task Scheduler/SSH. Shipped — full design notes moved to the archive.

---

## 26. Remote MCP connector — claude.ai, mobile, Cowork

The `/mcp` bridge only works in Claude **Desktop**: it's a local stdio server
Desktop spawns. Everywhere else needs a **remote** MCP server — a public HTTPS
endpoint Claude's cloud calls directly, added under Settings → Connectors. A
separate, bigger project, not an extension of the bridge.

**Transport — no fork needed.** pylitterbot's own CLI runs stdio only, but its
FastMCP instance (`pylitterbot.mcp.server.mcp`) and tool registrations
(`pylitterbot.mcp.tools`) are importable, and FastMCP's `run()` already takes
`transport="streamable-http"`:

```python
# asher/mcp/remote.py (sketch — not written)
from pylitterbot.mcp.server import mcp
import pylitterbot.mcp.tools  # noqa: F401 — registers the tools

def main() -> None:
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

**Hosting** — VPS, Fly.io, Render, or a Cloudflare Worker; TLS and the domain
are the host's job.

**Auth — the long pole.** A connector touching private data needs OAuth 2.1
with PKCE (S256), exact redirect-URI matching, and DCR or CIMD client
registration. No bearer-token shortcut.

**Credentials leave the keyring.** They'd live in the host's secret store — an
internet-reachable service holding credentials that control a physical device,
instead of a process the local OS session spawns on demand. A tradeoff, not an
improvement.

Evaluate whether cross-device access is worth the OAuth + hosting lift before
starting.

---

## Priority suggestion

What's left, ranked by user-visible impact vs. effort. The done list is in
[`roadmap-archive/`](roadmap-archive/README.md).

### High value

1. **Cat presence ≠ fault** (§11) — stop a normal visit raising the fault banner
2. **Reconnect banner** (§12) — a dropped connection is currently silent in the TUI
3. **Weight sparkline** (§7)

### Commands

1. **Pet detail card** (§7)
2. **Read-only firmware check in `info`** (§3)
3. **`/config set`, `/log [n]`, `/cat style`** (§14)
4. **`/account`** (§13)

### Device & platform

1. **Feeder Robot** (§5) — snack, gravity, meal size
2. **LR5 hopper / camera** (§4)
3. **Visit reassignment** (§7, LR5)
4. **Standalone binaries** (§16) — PyInstaller/Nuitka CI matrix

### Polish & stretch

1. **`/theme light`** (§12) — groundwork done
2. **Wi-Fi dot** (§11)
3. **Multi-robot tabs** (§11)
4. **`history` pagination via `offset`** (§11)
5. **`scoops_saved_count`** (§11)
6. **`StatusBar` / `CatPanel` widget extraction** (§12)
7. **Robot picker at startup** (§12) — low value
8. **Multi-account** (§13)
9. **Remote MCP connector** (§26) — hosting + OAuth 2.1; evaluate demand first
