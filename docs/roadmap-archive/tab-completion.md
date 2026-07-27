# §23 — Tab completion for slash commands ✅

> Archived from `ROADMAP.md` §23. The original section text, preserved verbatim.

Inspired by Claude Code's `/` menu — when the user types `/` into the command
input, a completion overlay appears listing all slash commands and narrows in
real time as they type.

### Behaviour (shipped)

```
/lo[g...]
  ┌──────────────────────────────────────┐
  │  /login    sign in or switch accounts│   ← highlighted (selected)
  │  /logout   sign out and re-enter ... │
  └──────────────────────────────────────┘
```

- Overlay appears immediately on `/` keypress (via `on_input_changed`)
- Filtered as the user continues typing (case-insensitive prefix match against
  `_registry.slash`)
- `↑`/`↓` move the selection; `Tab` or `Enter` accept (filling `/name ` with a
  trailing space ready for args); `Esc` dismisses without filling
- Typing a space hides the overlay — completion covers only the command name,
  not arguments
- Enter on a *partial* command (`/log`) completes to `/login ` instead of
  erroring as unknown; Enter on an *exact* match (`/login`, or `/pet` even
  though it's a prefix of `/pets`) submits the command normally
- Unknown `/xyz` commands still fall through to the "unknown slash command"
  warning — completion is an enhancement, not a gate

### Implementation

Two complementary completion modes share `asher/completion.py`:

**Slash popup** (the `/` overlay above) — pure helpers `slash_matches`,
`enter_completes`, `render_completion` read `_registry.slash` directly, so any
newly registered `SlashCommand` appears in the overlay with no per-command
wiring. No Textual imports, unit-testable without an event loop.

**Inline ghost text** (bare commands) — `CommandSuggester(Suggester)` drives
Textual's built-in `Input` suggestion rendering: typing a prefix (`cle`)
shows the rest (`an`) greyed after the cursor via the `input--suggestion`
component class, and `Right-arrow` / `Tab` accept it into `value`. Built from
`_registry.robot` (names + aliases), so newly registered bare commands get
ghost text with no extra wiring. Exact-match suppression (`name != value`)
stops the ghost from appending to a complete word.

The overlay is a `Static` widget (`#completion-overlay`) mounted inside
`#main-area`. It uses Textual's `overlay: screen` CSS property (not
`dock + layer`, which reserves layout space) to float over `#log`'s last rows
without squeezing the log while hidden — verified against the Textual 8.x
source and runtime. `#main-area` declares `layers: base overlay` so the
overlay paints above the log; unstyled children (`#log`, `#cat-panel`) land on
the base layer automatically. Toggling is via `widget.display` plus a content
`update()` from `render_completion()` (one `Text` block, one row per match,
selected row inverted to white-on-accent-blue).

Navigation is handled in `CommandsMixin.on_key`: while the overlay is open,
`↑`/`↓`/`Tab`/`Esc`/`Enter` are intercepted (with `event.prevent_default()`)
and take precedence over history navigation; once closed, `↑`/`↓` revert to
the existing command-history behaviour. The overlay is suppressed during the
inline login flow so it doesn't fight the email/password prompts.

### CSS (live in `asher/ui/style.tcss`)

```css
#main-area {
    layout: horizontal;
    height: 1fr;
    layers: base overlay;
}

#completion-overlay {
    layer: overlay;
    overlay: screen;          /* floats over #log without reserving space */
    dock: bottom;
    height: auto;
    max-height: 8;
    background: #161b22;
    border: solid #30363d;
    padding: 0 1;
    display: none;
}
```

Unit + Pilot tests live in `tests/test_completion.py` (31 cases: pure
matching/enter-decision/rendering, plus Pilot-driven overlay visibility,
filtering, arrow-key selection, Tab/Esc/Enter behaviour, and suppression
during the login flow).
