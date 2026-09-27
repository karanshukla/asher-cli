# Roadmap archive — completed sections

Shipped roadmap items, moved out of the main [`ROADMAP.md`](../ROADMAP.md)
so that file reads as a short list of *what's left to build*. Each entry below
is the original section text preserved verbatim for reference; nothing here is
still pending. Where a section was only partly shipped, the archive holds the
shipped subsections and the file's header note says what stayed behind.

Section bodies predate the package reorganisation into `asher/core`,
`asher/robot`, `asher/tui`, `asher/desktop` and `asher/mcp`, so file paths
inside them use the old flat layout.

| § | Section | What it shipped |
|---|---|---|
| 1 | [Slash commands — configuration at runtime](runtime-slash-commands.md) | `/robots` + `/robot`, `/login` + `/logout`, `/cat`, `/refresh`, `/config`, `/pet` |
| 2 | [History export to CSV](history-export.md) | `export [days\|month]` command — writes `~/Downloads/asher-<serial>-<date>.csv`, opens the folder |
| 3 | [Missing robot commands](robot-commands.md) | `status`/`info` split, `power`, `wait-time`, `panel-brightness`, `rename`, `insight` |
| 4 | [LR5-only features](lr5-features.md) | `privacy`, `volume`, `camera-audio`, `drawer-reset`, `night-light color`, `Filter due` in `info`, via `LR5Adapter` |
| 6 | [Real-time WebSocket updates](websocket-updates.md) | `robot.subscribe()` push updates in `asher/tui/monitoring.py`; the poll is now a 300 s fallback |
| 7 | [Pet features — multi-pet support](multi-pet.md) | `/pets` lists, `/pet <index\|name>` pins which pet the status bar shows |
| 8 | [Sleep schedule](sleep-schedule.md) | `sleep-schedule` viewer + `set`/`disable`, contextual `sleep`/`wake` per model |
| 9 | [Fault monitoring & alerts](fault-monitoring.md) | `asher/core/faults.py` model-scoped fault detection driving `#fault-banner`; `d` dismisses |
| 10 | [Config file persistence](config-persistence.md) | `~/.asher-cli/config.json` — `/refresh`, `/cat`, `/pet` survive restarts |
| 11 | [UI / UX gaps](ui-ux.md) | litter level, colour-coded status chip, `cycles` badge, readable history labels + dated timestamps, `HistoryScreen` pager, `⟳ Cycling M:SS`, `history --type` |
| 13 | [Credential & token persistence](credentials.md) | keyring credentials + cached OAuth token (now `asher/core/credentials.py`) |
| 14 | [Slash command design spec](slash-command-spec.md) | `/` dispatch and the slash command table as built |
| 17 | [E2E Textual Pilot harness](e2e-pilot.md) | `run_test()` Pilot suites driving the real command bar against mocked robots |
| 18 | [Cat panel status badges](cat-panel-badges.md) | `#cat-status` widget under the cat art — status chip, lock, sleep, night light, wait |
| 23 | [Tab completion](tab-completion.md) | Claude Code-style `/` overlay + inline ghost-text completion for bare commands |
| 24 | [Version display](version-display.md) | version in the title chip, `/version`, model badge on `#robot-lbl` |
| 25 | [Headless CLI export](headless-export.md) | `asher --export 7` writes CSV without launching the TUI, for cron / Task Scheduler / SSH |
| 22 | [Desktop notifications](desktop-notifications.md) | `plyer` toasts on fault transitions + `/notify on\|off\|sound on\|off\|test` command; drawer-full promoted to a fault |

## Dropped

Items removed from the roadmap without shipping as written — superseded, not pending.

- **§12 `.env` wizard** — replaced by the inline `/login` flow; the keyring is now the only credential source outside dev mode.
- **§13 `subscribe_for_updates`** — superseded by the per-robot `robot.subscribe()` the TUI already manages (§6).
- **§19 Architecture refactor** — proposed for the old single-file `app.py`; the package split (and more) happened. The one piece never done, `StatusBar`/`CatPanel` widget extraction, stays open in the roadmap.
