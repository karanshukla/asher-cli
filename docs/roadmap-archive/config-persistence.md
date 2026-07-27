# §10 — Config file persistence ✅

> Archived from `ROADMAP.md` §10. The original section text, preserved verbatim.

Runtime settings now persist to `~/.asher-cli/config.json` and survive
restarts. `asher/config.py` (modeled on `asher/mcp_config.py`) provides
`load()` / `save()` / `update(**changes)` over a small defaults dict — no
Textual or pylitterbot imports, pure stdlib (`json` + `pathlib`), so it's
fully unit-testable without an event loop.

```json
{
  "poll_interval_seconds": 300,
  "cat_panel_visible": true,
  "cat_panel_color": null,
  "active_pet_index": 0
}
```

`AsherApp.__init__` reads its four runtime defaults from `config.load()`
instead of hardcoding them, and `on_mount` seeds the poll timer from the
loaded interval. The `/refresh`, `/cat`, and `/pet` slash commands each
call a thin `_persist(app, **changes)` helper (in `asher/commands/__init__.py`)
right after mutating the in-memory attribute, which delegates to
`config.update()` — load-merge-save in one call. A read-only filesystem
(container, restricted environment) degrades gracefully: the `OSError` is
caught and logged as a warning so the in-session command still succeeds
even when the setting can't be written.

Defaults are merged on every load, so a stale key left by an older release
is silently ignored and a future key absent from an older file falls back
to its default. A corrupt or hand-edited JSON file degrades to defaults
rather than crashing the app.

**Explicitly not persisted** (by design):
- Credentials and the OAuth token stay in the OS keyring (secrets).
- The preferred-robot serial stays in the keyring (keyed by serial, not
  the fragile `active_robot_index` this section originally proposed —
  index would break if the cloud's robot ordering changed).
- `.env` vars stay as env vars.
- Ephemeral UI state (cat animation frame, command history, fault sets,
  timers) resets each launch as before.
