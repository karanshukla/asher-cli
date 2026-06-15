"""Slash commands extend the base Command class with prefix="/".

Architecture
------------
All commands inherit from `Command` in `asher/commands/base.py`.
Slash commands subclass `SlashCommand`, which sets `prefix = "/"`.
This makes it easy to add other prefixes (e.g. `!`, `?`) in the future.

Current slash commands (defined in asher/commands/__init__.py)
---------------------------------------------------------------
/login    — show login screen; save credentials to keyring; reconnect
/logout   — delete credentials from keyring; exit

To add a new slash command
--------------------------
1. Create a class inheriting from `SlashCommand` in `asher/commands/__init__.py`.
2. Implement `async def run(self, app, args)`.
3. Register an instance in `_registry`.
"""
