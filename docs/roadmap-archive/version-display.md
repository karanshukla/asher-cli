# §24 — Version display ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §24. The original section text, preserved verbatim.

`VERSION` is already read from `importlib.metadata` and shown in the title
chip of the status bar:

```
◆ Asher CLI v0.2.0   [robot name]   ● ONLINE   [Ready]
```

The `_refresh_title()` method in `asher/ui/__init__.py` builds this; version
falls back to `"dev"` when running from source without `pip install -e .`.

### ~~`/version` slash command~~ ✅

`/version` (a `SlashCommand` in `asher/commands/__init__.py`) prints the
runtime versions to the log via `importlib.metadata.version()` with a
`PackageNotFoundError` → `"?"` fallback, so it degrades cleanly when run from
source without `pip install -e .`:

```
  Asher CLI v0.2.0
  Python 3.12.3
  pylitterbot 2025.6.2
  textual 8.x.x
```

### ~~Status bar title — model badge~~ ✅

The `#robot-lbl` widget already shows the model type appended to the robot name:

```
◆ Asher CLI v0.2.0   Idiot Box  LR4   ● ONLINE   ⟳ Cycling
```

Implemented via `robot_model(r)` in `asher/helpers.py`, called from `_refresh_status()` in `asher/monitoring/__init__.py`.
