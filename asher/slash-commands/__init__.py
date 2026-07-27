"""Slash commands extend the base Command class with prefix="/".

Architecture
------------
All commands inherit from `Command` in `asher/commands/base.py`.
Slash commands subclass `SlashCommand`, which sets `prefix = "/"`.
This makes it easy to add other prefixes (e.g. `!`, `?`) in the future.

Current slash commands are defined in `asher/commands/__init__.py` and
registered in the `_registry` block at the bottom of that module. The
authoritative, always-up-to-date list is the registry itself — run
`/help` in the app, or iterate `_registry.slash`. At a glance:

    /login                 show login screen; save credentials to keyring; reconnect
    /logout                delete credentials from keyring; exit
    /robots                list all robots on the account
    /robot <index|name>    switch active robot (persists to keyring)
    /pets                  list all pets on the account
    /pet <index|name>      switch which pet's name/weight shows in the status bar
    /cat on|off|colour ... show/hide the cat panel, or recolour the art
    /refresh [seconds|off] change the auto-poll interval or disable it
    /config                show current runtime settings
    /version               show asher-cli / Python / pylitterbot / textual versions
    /mcp on|off|status     manage the Litter-Robot MCP server entry in Claude Desktop
    /exit                  exit Asher CLI

To add a new slash command
--------------------------
1. Create a class inheriting from `SlashCommand` in `asher/commands/__init__.py`.
2. Implement `async def run(self, app, args)`.
3. Register an instance in `_registry`.

Remember to also update the slash-command table in `README.md`.

Tab completion
--------------
Slash commands get Claude Code-style completion for free: typing `/` opens a
floating overlay (`#completion-overlay`) that filters the registry in real time.
`↑`/`↓` move the selection, `Tab` or `Enter` accept (filling `/name ` ready for
args), and `Esc` dismisses. No per-command wiring is needed — the pure helpers
in `asher/completion.py` read `_registry.slash` directly, so any newly
registered `SlashCommand` appears in the overlay automatically.
"""
