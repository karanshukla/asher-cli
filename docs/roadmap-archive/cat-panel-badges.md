# §18 — Cat panel — robot status badges underneath the art ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §18. The original section text, preserved verbatim.

A `#cat-label` widget renders the mode label (`connected`, `cycling…`,
`fault!`, …) and a `#cat-status` widget below it shows **complementary** info
that the top status bar doesn't surface — deliberately avoiding duplication of
the top row's lock / night-light. The panel shows:

```
status   Ready
power    mains
cycles   1234
wait     7m
```

Lines use a fixed-width ASCII key column (no emoji or ambiguous-width glyphs)
so they stay vertically aligned in every terminal. Updated from `_refresh_status`
via `MonitoringMixin._update_cat_panel`, so it refreshes in real time on
WebSocket push. Status colour comes from the consolidated `STATUS_COLORS` map.

### Proposed layout

```
  /\_____/\
 /  o   o  \          ← ASCII art (existing)
( ==  ^  == )
 )         (
(           )
 \  |___|  /
  \_______/

  connected            ← mode label (existing)

  ● RDY                ← status line
  🔓 unlocked
  ☀ night light off
  💤 awake
  ⏱ wait: 7 min
```

### Implementation

Add a new `Static` widget (`#cat-status`) below `#cat-label` inside `#cat-panel`.
Update it in `_refresh_status` alongside the header bar:

```python
def _update_cat_status(self, r) -> None:
    status    = getattr(r, "status",              None)
    locked    = getattr(r, "panel_lock_enabled",  False)
    sleeping  = getattr(r, "is_sleeping",         False)
    night     = getattr(r, "night_light_mode_enabled", False)
    wait      = getattr(r, "clean_cycle_wait_time_minutes", None)

    lines = Text()
    # status chip
    status_str = status.value if status else "—"
    status_color = STATUS_COLORS.get(status_str, "#8b949e")
    lines.append(f"● {status_str}\n", style=status_color)
    # lock
    lines.append("🔒 locked\n"   if locked   else "🔓 unlocked\n", style="#8b949e")
    # sleep
    lines.append("💤 sleeping\n" if sleeping  else "  awake\n",    style="#8b949e")
    # night light
    lines.append("☀ light on\n"  if night    else "☾ light off\n",style="#8b949e")
    # wait time
    if wait:
        lines.append(f"⏱ wait {wait}m\n", style="#484f58")

    self.query_one("#cat-status", Static).update(lines)
```

Status → colour mapping (`STATUS_COLORS`):

| Status value | Colour |
|---|---|
| `Ready` | `#3fb950` (green) |
| `Cycling` | `#58a6ff` (blue) |
| `Cat Detected` | `#d29922` (amber) |
| `Drawer Full` | `#f85149` (red) |
| `Offline` | `#f85149` (red) |
| `Sleeping` | `#484f58` (muted) |

### CSS additions

```css
#cat-status {
    width: 22;
    height: auto;
    text-align: center;
    padding-top: 1;
    color: #8b949e;
    font-size: 0.85em;
}
```

The cat panel would also benefit from a **minimum height** so the status badges
don't get squashed when the terminal is short. Consider making the panel
collapsible (the `/cat off` slash command from §14) so users on small terminals
can reclaim the space.
