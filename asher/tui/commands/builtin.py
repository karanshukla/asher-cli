"""App commands that need no robot: help, clear, quit."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import AsherApp

from textual.widgets import RichLog

from .base import Command

# ── app commands (no robot required) ────────────────────────────────────────


class HelpCommand(Command):
    name = "help"
    aliases = ("commands",)
    description = "show this message"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        app._show_help()


class ClearCommand(Command):
    name = "clear"
    description = "clear the log"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        app.query_one("#log", RichLog).clear()


class QuitCommand(Command):
    name = "quit"
    aliases = ("exit", "q")
    description = "exit Asher CLI"

    @property
    def display_name(self) -> str:
        return "quit / exit"

    async def run(self, app: AsherApp, args: list[str]) -> None:
        app.exit()
