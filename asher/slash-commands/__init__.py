"""Slash-command registry — app management commands (prefixed with /).

Convention
----------
- Normal commands (no prefix): robot actions — clean, status, lock, etc.
- Slash commands (/prefix):    app management — /login, /logout, /exit, /reload, …
- Special cases (no prefix OK): exit, quit — accepted both ways.

Dispatch flow
-------------
on_input_submitted  →  raw.startswith("/")  →  _run_slash_cmd()  (CommandsMixin)
                    →  otherwise            →  _run_cmd()         (CommandsMixin)

Current slash commands (implemented in asher/commands/__init__.py)
------------------------------------------------------------------
/login    — show login screen; save credentials to keyring; reconnect
/logout   — delete credentials from keyring; exit
/exit     — exit the app
/help     — show help (also available without slash)

To add a new slash command
--------------------------
1. Add a branch in _run_slash_cmd() in asher/commands/__init__.py.
2. Implement _cmd_<name>() on CommandsMixin.
3. Add an entry to the slash_cmds list in _show_help().
"""
