# §14 — Slash commands — full design spec ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §14. Parsing and the command table as designed. Every row without a ✅ that names `/robot`, `/pets`, `/pet`, `/refresh`, `/cat on|off|color`, `/config`, `export` or `/notify` has since shipped; `/account`, `/cat style`, `/config set`, `/theme` and `/log` are still open in the roadmap. The Tab-completion subsection that followed was superseded by [§23](tab-completion.md). Original text, preserved verbatim.

Slash commands (`/foo`) are distinguished from robot-action commands (`clean`,
`status`) by the leading `/`. They configure the app rather than send commands
to the robot.

### Parsing ✅

Dispatch is live in `on_input_submitted` in `asher/commands/__init__.py`:

```python
if raw.startswith("/"):
    self._run_slash_cmd(raw)
else:
    self._run_cmd(raw)
```

### Full slash command table

| Command | Description | Implementation note |
|---|---|---|
| `/login` ✅ | Enter credentials inline, save to keyring, reconnect | Inline flow in command bar |
| `/logout` ✅ | Delete keyring credentials, disconnect | `_keyring_delete()` + disconnect |
| `/exit` ✅ | Exit the app | `self.exit()` |
| `/help` ✅ | Show all commands | Two-section output: robot cmds + slash cmds |
| `/robot [index\|name]` | List or switch active robot | `self._robot = robots[n]` + status refresh |
| `/pets` | List all pets with index and active indicator | mirrors `/robots` |
| `/pet <index\|name>` | Switch which pet shows in status bar | `self._active_pet_idx = n` |
| `/account` | Show account info | `account.user_id`, email from keyring |
| `/refresh [seconds\|off]` | Change poll interval | Cancel + recreate `set_interval` timer |
| `/cat [on\|off]` | Show/hide cat panel | `add_class` / `remove_class` on `#cat-panel` |
| `/cat color <hex>` | Change cat art colour | Update `_cat_color` attr, redraw |
| `/cat style <n>` | Switch ASCII art set | Swap `CATS` dict at runtime |
| `/config` | Show all current settings | Read-only dump |
| `/config set <key> <val>` | Change a setting | Write to `config.json` |
| `/theme [dark\|light]` | Swap colour scheme | Swap Textual CSS variables |
| `/log [n]` | Set max log lines to keep | `RichLog(max_lines=n)` |
| `export [days\|month]` | Export activity history to CSV | See §2 for full spec |
| `/notify [on\|off\|test]` | Desktop notification settings | See §22 |
