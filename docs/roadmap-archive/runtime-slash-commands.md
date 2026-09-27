# §1 — Slash commands — configuration at runtime ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §1. The original section text, preserved verbatim.

Everything below would be `/command` style, similar to Claude Code, so they're
visually distinct from robot-action commands.

### ~~`/robot` — switch active robot~~ ✅

Two separate commands are live:

```
/robots           list all robots on the account (with active indicator)
/robot 0          switch to robot by index
/robot "Asher 2"  switch to robot by (partial, case-insensitive) name
```

Switching unsubscribes WebSocket from the old robot, re-subscribes to the new
one, and refreshes the status bar. The chosen robot's serial is saved to keyring
and auto-restored on the next launch.

### ~~`/auth`~~ → `/login` ✅ — update credentials without restart

`/login` starts an inline credential entry flow directly in the command bar:
the prompt label changes to `email ›` then `password ›`, the password field
masks input as `••••••••`, and on submit the credentials are saved to the OS
keyring and the connection is re-established — no restart needed.

`/logout` disconnects, deletes credentials from keyring, and prompts
`/login` to sign back in.

### ~~`/cat` — configure the cat animation~~ ✅

```
/cat off              hide the cat panel entirely (more log space)
/cat on               show the cat panel
/cat colour <hex>     change the cat art colour (color also accepted)
/cat reset            revert to default palette colours
```

Toggling sets `widget.display = False/True` directly. Colour override stored in
`_cat_color` and applied in `_set_cat` / `_tick_cat` instead of the per-mode
palette. `/cat style` (alternate art sets) is not yet implemented.

### ~~`/refresh` — change the poll interval~~ ✅

```
/refresh 10       poll every 10 s
/refresh 60       poll every 60 s (lighter on API)
/refresh off      disable auto-refresh (manual `status` only)
/refresh          show current interval
```

Timer ref stored as `_poll_timer` in `AsherApp.__init__`; on change, old timer
is stopped via `timer.stop()` and a new one created with `set_interval`.
`_poll_interval` stores the current value for `/config` display.

### ~~`/config` — show current runtime config~~ ✅

```
/config
  robot          Idiot Box (LR4, index 0)
  refresh        300s
  cat panel      on  #58a6ff (default)
  active pet     Asher (index 0)
```

Read-only dump of current runtime settings. No API call needed.

### ~~`/pet` — switch which pet's name/weight is shown~~ ✅

```
/pet              list pets on the account
/pet 0            show Whisker pet at index 0 in the status bar
/pet luna         switch by partial, case-insensitive name
```

`_active_pet_idx` stored on `AsherApp`; `_refresh_status` reads it instead of
hard-coding `pets[0]`. Supports both index and name lookup.
