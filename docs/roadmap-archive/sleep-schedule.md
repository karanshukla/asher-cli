# §8 — Sleep schedule ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §8. The original section text, preserved verbatim.

`robot.sleep_schedule` returns a `SleepSchedule` with per-day `SleepScheduleDay`
objects (day, sleep_time, wake_time, is_enabled). This is more granular than the
current `sleep` / `wake` toggle.

### ~~`sleep-schedule` — read-only viewer~~ ✅

The `sleep-schedule` (alias `sleepschedule`) command renders the per-day
sleep/wake window read-only. Days are sorted Mon→Sun (converted from pylitterbot's
Sun=0..Sat=6 `DayOfWeek`); enabled days show `22:00 → 07:00`, disabled days show
`off`. If `schedule.get_window()` returns an active window covering the current
time, the affected day(s) get a `● now` marker. When the whole schedule is
disabled it notes that and still lists the configured windows; when
`sleep_schedule is None` it warns that the unit is always awake and points at
`sleep`/`wake`. `_sleep_schedule` can raise on malformed data, so the whole read
is wrapped defensively and degrades to a `_log_err`. Works on LR3/LR4/LR5 — the
property exists on all three.

```
sleep-schedule                        show current schedule ✅
sleep-schedule set Mon 22:00 07:00    set Monday's sleep window ✅
sleep-schedule set all 22:00 07:00    set every day ✅
sleep-schedule disable                turn every day off ✅
```

### ~~`sleep-schedule set` / `disable`~~ ✅

Writing a schedule is `RobotAdapter.set_sleep_window(weekday, sleep, wake)` /
`disable_sleep_schedule()`, so each model answers for itself:

- **LR5** — `set_sleep_mode(True, <minutes>, wake_time=<minutes>, day_of_week=…)`
  per day, or every day when no day is named. `day_of_week` is passed in
  pylitterbot's `DayOfWeek` numbering (Sun=0), *not* the Mon=0 its docstring
  claims: the value is matched against the `dayOfWeek` field of the schedule the
  cloud returned, and those follow the enum.
- **LR3** — one window for every day and a firmware-fixed 8-hour sleep, so only
  the start time is sent and the message says the wake time was ignored; naming
  a single day is refused rather than silently applied to all seven.
- **LR4** — no schedule setter exists in the API at all; both paths return the
  shared `LR4_SCHEDULE_NOTE` pointing at the Whisker app.

`disable` rides on the same `set_sleep(False)` each model already implements
rather than repeating the dispatch. Days and times are parsed by
`helpers.parse_day()` / `helpers.parse_clock()` before any call is made, so a
typo is a local message.

### ~~Contextual sleep/wake toggle~~ ✅

LR4 does not implement `set_sleep_mode` — calling it raises `NotImplementedError`.
LR3 and LR5 both support it but with different signatures:

- **LR3**: `set_sleep_mode(value: bool, sleep_time: time | None)`
- **LR5**: `set_sleep_mode(value: bool, sleep_time: int | time | None, *, wake_time, day_of_week)`

`sleep` / `wake` route through `RobotAdapter.set_sleep()`, which dispatches per
model: LR3 and LR5 toggle sleep mode, and the LR4 explains its schedule-based
sleep and points at `sleep-schedule`.
