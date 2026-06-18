"""Command base classes and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import AsherApp


class Command(ABC):
    """Base class for all Asher CLI commands."""

    name: str = ""
    description: str = ""
    aliases: tuple[str, ...] = ()
    prefix: str = ""  # e.g. "" or "/"
    requires_robot: bool = False

    @property
    def is_slash(self) -> bool:
        """Whether this command uses a slash prefix."""
        return self.prefix == "/"

    @property
    def full_name(self) -> str:
        """Name including prefix (e.g. '/login')."""
        return f"{self.prefix}{self.name}"

    @property
    def display_name(self) -> str:
        """Name shown in help text."""
        if self.aliases:
            return f"{self.name} / {' / '.join(self.aliases)}"
        return self.name

    @property
    def help_name(self) -> str:
        """Formatted name for help output."""
        if self.prefix:
            return self.full_name
        return self.display_name

    @abstractmethod
    async def run(self, app: AsherApp, args: list[str]) -> None:
        """Execute the command."""


class SlashCommand(Command):
    """Commands invoked with a leading slash (e.g. /login, /logout)."""

    prefix: str = "/"


class CommandRegistry:
    """Maps command names and aliases to Command instances."""

    def __init__(self) -> None:
        self._by_name: dict[str, Command] = {}
        self._order: list[Command] = []

    def register(self, cmd: Command) -> None:
        """Register a command and all its aliases."""
        self._by_name[cmd.name] = cmd
        for alias in cmd.aliases:
            self._by_name[alias] = cmd
        if cmd not in self._order:
            self._order.append(cmd)

    def get(self, name: str) -> Command | None:
        return self._by_name.get(name)

    @property
    def all(self) -> list[Command]:
        return list(self._order)

    @property
    def robot(self) -> list[Command]:
        return [c for c in self._order if not c.is_slash]

    @property
    def slash(self) -> list[Command]:
        return [c for c in self._order if c.is_slash]
