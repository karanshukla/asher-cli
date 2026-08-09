"""Pure helpers for slash-command tab completion.

No Textual imports — data-in, data-out — so matching, selection, and rendering
are unit-testable without an event loop. Fed by the live ``_registry.slash``
list from ``asher.commands``, making the registry the single source of truth
for both dispatch and completion (the §23 goal: one registry, two consumers).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.suggester import Suggester

from . import theme

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .commands.base import Command

# Fixed-width name column so descriptions stay vertically aligned regardless
# of command-name length. Wide enough for the longest slash name plus padding.
_NAME_COL = 14


def slash_matches(commands: Sequence[Command], text: str) -> list[Command]:
    """Return the slash commands whose name prefix-matches ``text``.

    Only fires when ``text`` starts with ``/``; bare commands are not completed.
    Matching is case-insensitive on the part after the slash, and registry
    order is preserved so the list is deterministic. A bare ``/`` returns every
    slash command (nothing typed yet to filter on).
    """
    if not text.startswith("/"):
        return []
    prefix = text[1:].lower()
    if not prefix:
        return list(commands)
    return [c for c in commands if c.name.startswith(prefix)]


def enter_completes(matches: Sequence[Command], selected_idx: int, text: str) -> Command | None:
    """Return the command Enter should fill, or ``None`` to submit normally.

    When the completion overlay is visible and the first token of ``text`` is a
    *partial* slash command (doesn't exactly equal a registered command name),
    Enter fills the completion instead of submitting — so ``/log`` + Enter
    completes to ``/login `` rather than erroring as unknown. Once the typed
    command matches exactly (``/login``), Enter submits as usual. Returns
    ``None`` whenever there's nothing to complete: no matches, no leading
    slash, args already present after the command, or an exact name match.

    The exact-match check is against *any* match, not just the selected one:
    typing ``/pet`` exactly matches the ``pet`` command even though ``pets``
    also appears in the prefix matches, so Enter must submit rather than
    silently expanding to ``/pets``.
    """
    if not matches or not text.startswith("/"):
        return None
    first = text.split()[0] if text.split() else text
    typed = first[1:].lower()
    if any(c.name.lower() == typed for c in matches):
        return None
    if 0 <= selected_idx < len(matches):
        return matches[selected_idx]
    return matches[0]


def render_completion(matches: Sequence[Command], selected_idx: int) -> Text:
    """Render the overlay as a multi-line Rich Text block, one row per match.

    The selected row is inverted (white text on the accent-blue background) so
    it reads as the current pick; other rows show the command name in accent
    blue and the description in muted grey, matching the ``/help`` palette.
    """
    if not matches:
        return Text("")
    lines: list[Text] = []
    for i, cmd in enumerate(matches):
        name = f"/{cmd.name}".ljust(_NAME_COL)
        line = Text()
        if i == selected_idx:
            line.append(name, style=f"bold {theme.SELECTION_FG} on {theme.SELECTION_BG}")
            line.append(f"  {cmd.description}", style=f"{theme.FOREGROUND} on {theme.SELECTION_BG}")
        else:
            line.append(name, style=theme.ACCENT)
            line.append(f"  {cmd.description}", style=theme.MUTED)
        lines.append(line)
    return Text("\n").join(lines)


class CommandSuggester(Suggester):
    """Inline ghost-text completer for bare robot commands (names + aliases).

    Drives Textual's built-in ``Input`` suggestion rendering: typing a prefix
    shows the rest of the matching command name greyed after the cursor, and
    Right-arrow / Tab accept it into ``value``. Constructed from
    ``_registry.robot`` so any newly registered bare command or alias gets
    ghost-text suggestions with no extra wiring — mirroring how the slash
    popup reads ``_registry.slash``.
    """

    def __init__(self, names: Sequence[str]) -> None:
        super().__init__(use_cache=True, case_sensitive=False)
        self._names = [n.casefold() for n in names]

    async def get_suggestion(self, value: str) -> str | None:
        if not value:
            return None
        for name in self._names:
            if name.startswith(value) and name != value:
                return name
        return None
