# Roadmap archive — completed sections

Shipped roadmap items, moved out of the main [`ROADMAP.md`](../../ROADMAP.md)
so that file reads as a short list of *what's left to build*. Each entry below
is the original section text preserved verbatim for reference; nothing here is
still pending.

| § | Section | What it shipped |
|---|---|---|
| 2 | [History export to CSV](history-export.md) | `export [days\|month]` command — writes `~/Downloads/asher-<serial>-<date>.csv`, opens the folder |
| 9 | [Fault monitoring & alerts](fault-monitoring.md) | `asher/faults.py` model-scoped fault detection driving `#fault-banner`; `d` dismisses |
| 10 | [Config file persistence](config-persistence.md) | `~/.asher-cli/config.json` — `/refresh`, `/cat`, `/pet` survive restarts |
| 18 | [Cat panel status badges](cat-panel-badges.md) | `#cat-status` widget under the cat art — status chip, lock, sleep, night light, wait |
| 23 | [Tab completion](tab-completion.md) | Claude Code-style `/` overlay + inline ghost-text completion for bare commands |
| 25 | [Headless CLI export](headless-export.md) | `asher --export 7` writes CSV without launching the TUI, for cron / Task Scheduler / SSH |
| 22 | [Desktop notifications](desktop-notifications.md) | `plyer` toasts on fault transitions + `/notify on\|off\|sound on\|off\|test` command; drawer-full promoted to a fault |
