# §4 — LR5-only features ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §4. The shipped subsections only — what's still open stays in the roadmap. Original text, preserved verbatim.

LR5 exposes additional capabilities that don't exist on LR4. The app detects
model type via the `RobotAdapter` pattern: the four interactive commands below
route through `LR5Adapter`, while the base `RobotAdapter` returns a
`"... is only available on the LR5"` message so typing them on an LR3/LR4 is
safe and informative rather than a crash.

### Shipped ✅

| Command | API | LR5 property |
|---|---|---|
| ~~`privacy on/off`~~ ✅ | `set_privacy_mode(bool)` | `privacy_mode` |
| ~~`volume <0-100>`~~ ✅ | `set_volume(int)` | `sound_volume` |
| ~~`camera-audio on/off`~~ ✅ | `set_camera_audio(bool)` | `camera_audio_enabled` |
| ~~`drawer-reset`~~ ✅ | `reset_waste_drawer()` | `is_drawer_removed` |
| ~~`night-light color <hex>`~~ ✅ | `set_night_light_settings(color=...)` | `night_light_color` |
| ~~`filter reminder`~~ ✅ | _(read-only)_ | `next_filter_replacement_date` |

`volume` accepts `0-100` (the actual pylitterbot range, not the `0-10` listed
in earlier drafts of this table). Bare `volume` prints the current value
alongside the usage line. Adapter unit tests cover the happy path, rejection,
exceptions, and the LR3/LR4 "not supported" fallthrough for each command; pilot
tests in `tests/test_lr5_commands.py` exercise the command-bar dispatch end to
end against both an LR5 and an LR4 adapter.

`night-light color <hex>` takes the same `#RRGGBB` (or 3-digit shorthand) a
user would type anywhere else; `helpers.hex_colour()` normalises and rejects it
locally, so a typo never becomes a cloud round trip. `filter reminder` is the
read-only `next_filter_replacement_date`, rendered by `helpers.fmt_until()` as
a `Filter due` row in `info` — present only on models that report one.

`get_activities(limit, offset, activity_type)` (plural, LR5-only) is what backs
`history --type` (§11). Its `offset` parameter is still unused — pagination
beyond a single `limit` remains open.
