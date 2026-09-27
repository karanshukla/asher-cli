# §3 — Missing robot commands ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §3. The shipped commands only; the deliberately-omitted notes (`reset`, `firmware` update) stay in the roadmap. Original text, preserved verbatim.

Real `LitterRobot3` / `LitterRobot4` / `LitterRobot5` methods in pylitterbot
that weren't wired up. The non-destructive ones are now live; the destructive
ones (`reset`, `reset-settings`, `firmware` update) are deliberately omitted.

### ~~`status` vs `info` — split the current status command~~ ✅

`status` is now the trimmed at-a-glance view — the same information shown in
the status bar, refreshed on demand:

```
  Online         yes
  Status         Ready
  Drawer         48%
  Last seen      4m ago
  Cat weight     9.1 lb
```

`info` handles the full property dump — serial number, firmware version, wait
time, all boolean flags, model type, etc. Useful for debugging or first-time
setup, not something you need every time you check in. Optional LR4/LR5-only
properties (`firmware`, `clean_cycle_wait_time_minutes`) are read via
`getattr` so `info` degrades gracefully on LR3 (renders `—` instead of
crashing):

```
  Name           Idiot Box
  Model          LR4  (LitterRobot4)
  Serial         LR4C012345
  Firmware       ESP: 1.1.50  PIC: 1.0.11
  Wait time      7 min
  Sleeping       no
  Panel locked   no
  Night light    off
  Drawer         48%
  Online         yes
  Last seen      4m ago
```

### ~~`power on` / `power off`~~ ✅
```python
await robot.set_power_status(True / False)
```
Hard-power the unit on or off. Useful for scheduled restarts.

### ~~`wait-time <minutes>`~~ ✅
```python
await robot.set_wait_time(minutes)   # VALID_WAIT_TIMES: 3, 7, 15, 25, 30
```
Sets how many minutes the robot waits after a cat visit before cleaning.
With no argument it prints the current value and the valid set; an out-of-set
value is rejected before hitting the API. Current value is also surfaced in
`info` output.

### ~~`panel-brightness <low|medium|high>`~~ ✅

```python
from pylitterbot.enums import BrightnessLevel
await robot.set_panel_brightness(BrightnessLevel.LOW)
```

An earlier audit claimed `set_panel_brightness` did not exist in
`pylitterbot==2025.6.2` — that was wrong. Both the setter and the
`panel_brightness` reader exist on `LitterRobot4` and `LitterRobot5`
(`BrightnessLevel`: LOW=25, MEDIUM=50, HIGH=100). The `panel-brightness`
command (alias `pb`) now routes through `LR4Adapter`/`LR5Adapter` and is
gracefully refused on the LR3 (no panel) via the base adapter fallback. Bare
invocation shows the current brightness.

### ~~`rename <new name>`~~ ✅
```python
await robot.set_name("new name")
```
Renames the unit in the Whisker cloud (persists across sessions). Multi-word
names are supported (`rename Idiot Box 2`); bare `rename` shows the current
name in the usage line.

### ~~`insight [days]` — usage statistics~~ ✅
```python
insight = await robot.get_insight(days=30)
```
Renders total cycles, average cycles/day over the covered period, and the peak
day. Accepts a day count (`insight 7`) or `month` alias (= 30, the Whisker
ceiling):
```
  Cycles         42 (last 3 days)
  Avg/day        1.4
  Peak day       3 on 2026-07-20
```
