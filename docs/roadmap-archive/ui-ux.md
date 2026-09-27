# §11 — UI / UX gaps ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §11. The shipped subsections only — what's still open stays in the roadmap. Original text, preserved verbatim.
>
> Three headings below predate their ✅: the cycle counter shipped as the `cycles` badge in `#cat-status` (`scoops_saved_count` is still open), colour-coded status as the contextual `#online-lbl` chip, and the timestamp refinement (year for older events) with the readable-labels work.

### ~~Status bar: litter level~~ ✅
`robot.litter_level` is shown in the second row of the status bar as `Litter N%`.
`litter_level_state` (Low / Nominal / High) is not shown — numeric % is sufficient.

### Status bar: cycle counter
`robot.cycle_count` and `robot.scoops_saved_count` (scoops saved vs. traditional
box) — nice vanity stats for the right-side cat panel caption area.

### Color-coded status
The `[RDY]` status token is always the same grey. Map `LitterBoxStatus` values to
colours:
- `READY` → green
- `CYCLING` → blue (animated)
- `DRAWER_FULL` → red
- `CAT_DETECTED` → amber
- `OFFLINE` → red

### ~~Readable event labels (replace raw library strings)~~ ✅

The `history` command now renders translated, colour-coded labels instead of
raw pylitterbot enum strings. Cat-detection events append the pet name and
weight when available (`Cat detected  Asher  9.1 lb`), and unknown event
types fall through to the raw string in muted grey so new pylitterbot events
never break the display.

The label map and the pure `format_activity()` translator live in
`asher/activity_labels.py`, shared by both the `history` command and the
`export` CSV path so the two render events the same way. Timestamps also
gained the §11 refinement: same-day events show `HH:MM`, this-year events
show `mm/dd HH:MM`, and older events show the full `YYYY-MM-DD`.

**Example output:**
```
  14:22        Ready                          (muted grey)
  13:55        Clean cycle complete           (green)
  13:54        Cat detected  Asher  9.1 lb    (amber, with weight + pet)
  12:01        Drawer full — empty now        (red)
  06/14 11:30  Sleep mode on                  (muted)
```

Unit tests live in `tests/test_activity_labels.py` (17 cases covering the
label map, cat suffix logic, enum vs string actions, and unknown-event
fallback) — the module is pure and needs no Textual or event-loop harness.

### ~~History as a scrollable sub-view (pager mode)~~ ✅

`history` now pushes a `HistoryScreen` (a `ModalScreen` in
`asher/history_view.py`) over the main UI instead of dumping rows into the main
log, where they scrolled off as new output arrived. A `ScrollableContainer`
takes focus on mount, so the arrow keys, `Page Up`/`Page Down`, and
`Home`/`End` page through long histories natively; `q`, `Escape`, or `Enter`
pops back to the main view. A header bar shows the robot name and event count.

`history` also gained an optional count: bare `history` fetches 50 events (up
from the old hardcoded 25), `history 100` fetches more, and `history all`
fetches up to 500. The fetch/format logic lives in the pure
`format_history_rows()` helper (newest-first, shared timestamp rules from §11),
so the rendering stays identical to the old log rows. No new deps — just
`ScrollableContainer` + `ModalScreen` from Textual.

**Behaviour:**
- `history` command pushes a `HistoryScreen` over the main app
- Full-width, full-height overlay with its own scroll container
- Page Up / Page Down, arrow keys, Home / End all work naturally
- `q`, `Escape`, or `Enter` pops back to the main view instantly
- A header bar shows the robot name and event count

**Textual implementation:**

```python
from textual.screen import Screen
from textual.widgets import Static, Footer
from textual.containers import ScrollableContainer

class HistoryScreen(Screen):
    BINDINGS = [
        ("escape,q,enter", "app.pop_screen", "Close"),
        ("page_up",        "scroll_up",      "Page up"),
        ("page_down",      "scroll_down",    "Page down"),
    ]

    def __init__(self, rows: list[Text], title: str) -> None:
        super().__init__()
        self._rows  = rows
        self._title = title

    def compose(self):
        yield Static(self._title, id="history-header")
        with ScrollableContainer(id="history-scroll"):
            for row in self._rows:
                yield Static(row)
        yield Footer()

    def action_scroll_up(self):
        self.query_one("#history-scroll").scroll_page_up()

    def action_scroll_down(self):
        self.query_one("#history-scroll").scroll_page_down()
```

Invoke it from `_cmd_history_list`:

```python
rows = [_fmt_row(act, self._pets) for act in acts]
title = Text(f"  Activity history — {self._robot.name}  ({len(acts)} events)  [q] close",
             style="bold #58a6ff")
await self.app.push_screen(HistoryScreen(rows, title))
```

**CSS sketch:**

```css
HistoryScreen {
    background: #0d1117;
    border: solid #30363d;
}

#history-header {
    dock: top;
    height: 1;
    background: #161b22;
    padding: 0 2;
    color: #58a6ff;
}

#history-scroll {
    padding: 1 2;
}
```

This approach means `history 100` is just as usable as `history 10` — the
events don't pollute the log and the user can scroll at their own pace.

### ~~Real-time cycling indicator (requires WebSockets)~~ ✅

The `#online-lbl` chip now shows `⟳ Cycling  M:SS` with live elapsed time while
a `CLEAN_CYCLE`/`EMPTY_CYCLE` is active. `_cycle_start` is stamped on the
transition into a cycling status and a 1 s `_cycle_timer` (created lazily via
`set_interval`, stopped/null on any non-cycling status) re-renders the chip each
second via `_tick_cycle`. The `_cycling_chip()` helper is shared between the
timer and the `_refresh_status` cycling branch so they stay consistent. Because
`_refresh_status` fires on WebSocket push, the chip updates the moment the cycle
starts — no 30 s polling gap.

**What's needed:**
- WebSocket subscription (§6) — `robot.subscribe()` fires `EVENT_UPDATE`
  immediately when the status transitions to `CLEAN_CYCLE` or back to `READY`.
- Animated status chip — while `status == CLEAN_CYCLE`, pulse the `[RDY]` chip
  blue and add a spinner character (Textual's `LoadingIndicator` or a manual
  `_tick` frame cycle):
  ```
  ◆ Asher CLI   Idiot Box   ● ONLINE   [⠙ CYCLING]
  ```
- Cat animation — switch to `"cleaning"` mode (already defined) the moment the
  cycle starts; revert to `idle` on `READY`.
- Elapsed time — show how long the current cycle has been running:
  ```
  [⠙ CYCLING  0:42]
  ```
  Track `_cycle_start: datetime | None` on the transition to `CLEAN_CYCLE`;
  update the chip every second via a `set_interval(1, ...)` timer that's active
  only while cycling.

This is the primary reason to implement WebSocket (§6) — the cycling indicator
is meaningless without it.

### Timestamps in activity history
The history output currently shows `mm/dd HH:MM`. Adding the year for older
events and relative time (like the status bar's "7d ago") would be cleaner.

### ~~`history --type cat` filter (LR5)~~ ✅
`history [count|all] --type <kind>` filters on the LR5 via
`get_activities(limit, activity_type=…)`. Friendly words map to cloud types in
`constants.ACTIVITY_TYPES` (`cat` → `PET_VISIT`, `clean` → `CYCLE_COMPLETED`, …)
and anything unlisted is passed through uppercased, so a type the app doesn't
know yet is still reachable. The returned dicts are reduced to `Activity`
objects the shared `format_activity()` already renders. LR3/LR4 have no such
parameter, so `RobotAdapter.supports_history_filter` is False there and the
command says so instead of silently returning everything.
