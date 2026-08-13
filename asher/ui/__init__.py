"""UI layout, CSS, cat panel, and log helpers."""

from __future__ import annotations

import contextlib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

from dotenv import load_dotenv
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.css.query import NoMatches
from textual.widgets import Input, RichLog, Static

from .. import theme
from ..cats import CATS
from ..completion import CommandSuggester
from ..helpers import dev_mode, ts

load_dotenv()


class CmdInput(Input):
    """Input with all focus borders and tints removed.

    Carries the bare-command ``CommandSuggester`` for inline ghost-text
    completion; Tab accepts the suggestion (Right-arrow already does via
    Textual's default ``action_cursor_right``).
    """

    DEFAULT_CSS = Input.DEFAULT_CSS + theme.apply("""
    CmdInput {
        border: none !important;
        height: 1;
        padding: 0;
        background: $asher-panel;
        &:focus {
            border: none !important;
            background-tint: 0%;
        }
    }
    """)

    BINDINGS = [
        Binding("tab", "accept_suggestion", "Accept suggestion", show=False),
    ]

    def action_accept_suggestion(self) -> None:
        if self._suggestion and self.cursor_at_end:
            self.value = self._suggestion
            self.cursor_position = len(self.value)


if dev_mode():
    VERSION = "dev"
else:
    try:
        VERSION = pkg_version("asher-cli")
    except PackageNotFoundError:
        VERSION = "dev"

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def _build_command_suggester() -> CommandSuggester:
    """Build the inline ghost-text suggester from the live bare-command registry.

    Reads ``_registry.robot`` (names + aliases) so newly registered commands
    appear in ghost text with no extra wiring. Imported lazily to keep the
    command module out of the UI import graph at module load.
    """
    from ..commands import _registry  # noqa: PLC0415

    names: list[str] = []
    for cmd in _registry.robot:
        names.append(cmd.name)
        names.extend(cmd.aliases)
    return CommandSuggester(names)


_CAT_PALETTES: dict[str, list[str]] = {
    "idle": theme.ACCENT_PULSE,
    "happy": theme.OK_PULSE,
    "sleeping": theme.SUBTLE_PULSE,
    "cleaning": theme.ACCENT_PULSE,
    "error": theme.DANGER_PULSE,
    "full": theme.WARN_PULSE,
}

_CAT_FX: dict[str, list[str]] = {
    "idle": [
        "✦✦  ···  ✦✦   ···   ✦✦  \n  ✦✦  ···  ✦✦   ···   ✦✦\n    ✦✦  ···  ✦✦   ···   ✦",
        " ✦✦  ···  ✦✦   ···   ✦✦ \n   ✦✦  ···  ✦✦   ···   ✦✦\n      ✦✦  ···  ✦✦   ···  ",
        "  ✦✦  ···  ✦✦   ···   ✦✦\n    ✦✦  ···  ✦✦   ···   ✦✦\n       ✦✦  ···  ✦✦   ··· ",
        "   ✦✦  ···  ✦✦   ···   ✦✦\n     ✦✦  ···  ✦✦   ···   ✦\n        ✦✦  ···  ✦✦   ···",
    ],
    "happy": [
        "♥♥   ♥♥   ♥♥   ♥♥      \n  ♥♥   ♥♥   ♥♥   ♥♥    \n    ♥♥   ♥♥   ♥♥   ♥♥  ",
        " ♥♥   ♥♥   ♥♥   ♥♥     \n   ♥♥   ♥♥   ♥♥   ♥♥   \n     ♥♥   ♥♥   ♥♥   ♥♥ ",
        "  ♥♥   ♥♥   ♥♥   ♥♥    \n    ♥♥   ♥♥   ♥♥   ♥♥  \n      ♥♥   ♥♥   ♥♥   ♥♥",
        "   ♥♥   ♥♥   ♥♥   ♥♥   \n     ♥♥   ♥♥   ♥♥   ♥♥ \n       ♥♥   ♥♥   ♥♥   ♥♥",
    ],
    "sleeping": [
        "☾☾   zZzZ   zZzZ       \n  ☾☾   zZzZ   zZzZ     \n    ☾☾   zZzZ   zZzZ   ",
        " ☾☾   zZzZ   zZzZ      \n   ☾☾   zZzZ   zZzZ    \n     ☾☾   zZzZ   zZzZ  ",
        "  ☾☾   zZzZ   zZzZ     \n    ☾☾   zZzZ   zZzZ   \n      ☾☾   zZzZ   zZzZ ",
        "   ☾☾   zZzZ   zZzZ    \n     ☾☾   zZzZ   zZzZ  \n       ☾☾   zZzZ   zZzZ",
    ],
    "cleaning": [
        "***  ***  ***  ***   \n  ***  ***  ***  *** \n    ***  ***  ***  *",
        " ***  ***  ***  ***  \n   ***  ***  ***  ***\n     ***  ***  ***  *",
        "  ***  ***  ***  *** \n    ***  ***  ***  ***\n      ***  ***  ***  ",
        "   ***  ***  ***  ***\n     ***  ***  ***  **\n       ***  ***  *** ",
    ],
    "error": [
        "!!   !!   !!   !!     \n  !!   !!   !!   !!   \n    !!   !!   !!   !! ",
        " !!   !!   !!   !!    \n   !!   !!   !!   !!  \n     !!   !!   !!   !!",
        "  !!   !!   !!   !!   \n    !!   !!   !!   !! \n      !!   !!   !!   !",
        "   !!   !!   !!   !!  \n     !!   !!   !!   !!\n       !!   !!   !!   ",
    ],
    "full": [
        "!!   !!   !!   !!       \n  !!   !!   !!   !!     \n    !!   !!   !!   !!   ",
        " !!   !!   !!   !!      \n   !!   !!   !!   !!   \n     !!   !!   !!   !!  ",
        "  !!   !!   !!   !!     \n    !!   !!   !!   !!  \n      !!   !!   !!   !!",
        "   !!   !!   !!   !!    \n     !!   !!   !!   !! \n       !!   !!   !!   !!",
    ],
}


class UIMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _cat_mode: str
    _cat_frame: int
    _cat_fx_idx: int
    _is_loading: bool
    _spinner_idx: int

    def compose(self) -> ComposeResult:
        with Container(id="status-bar"):
            with Container(classes="srow"):
                yield Static("", id="title-lbl", classes="chunk")
                yield Static("", id="robot-lbl", classes="chunk")
                yield Static("", id="online-lbl", classes="chunk")
                yield Static("", id="nightlight-lbl", classes="chunk")
                yield Static("", id="lock-lbl", classes="chunk")
            with Container(classes="srow"):
                yield Static("", id="drawer-lbl", classes="chunk")
                yield Static("│", classes="sep")
                yield Static("", id="litter-lbl", classes="chunk")
                yield Static("│", classes="sep")
                yield Static("", id="weight-lbl", classes="chunk")
                yield Static("│", classes="sep")
                yield Static("", id="clean-lbl", classes="chunk")

        with Container(id="main-area"):
            yield RichLog(id="log", highlight=True, markup=True, wrap=True, min_width=0)
            yield Static("", id="completion-overlay")
            with Container(id="cat-panel"):
                yield Static("", id="cat-fx")
                yield Static(CATS["idle"][0], id="cat-art")  # type: ignore[arg-type]
                yield Static("", id="cat-label")
                yield Static("", id="cat-status")
                yield Static("", id="fault-banner")

        with Container(id="bottom-dock"):
            with Container(id="input-bar"), Container(id="input-row"):
                yield Static(">", id="prompt")
                yield CmdInput(
                    placeholder="type a command  (help for list)…",
                    id="cmd-input",
                    suggester=_build_command_suggester(),
                )
            yield Static(
                "help · clean · status · history · /login · /logout · quit",
                id="hint-bar",
            )

    def _refresh_title(self) -> None:
        t = Text()
        t.append("◆ ", style=f"bold {theme.ACCENT}")
        t.append("Asher CLI", style=f"bold {theme.FOREGROUND_BRIGHT}")
        t.append(f" v{VERSION}", style=theme.MUTED)
        self.query_one("#title-lbl", Static).update(t)  # type: ignore[attr-defined]

    def _show_loading_state(self) -> None:
        self.query_one("#online-lbl", Static).update(  # type: ignore[attr-defined]
            Text(f"{_SPINNER[0]} connecting…", style=theme.MUTED)
        )
        dash = Text("—", style=theme.DIM)
        for wid in (
            "#robot-lbl",
            "#nightlight-lbl",
            "#lock-lbl",
            "#drawer-lbl",
            "#litter-lbl",
            "#weight-lbl",
            "#clean-lbl",
        ):
            self.query_one(wid, Static).update(dash)  # type: ignore[attr-defined]

    def _show_signed_out_state(self) -> None:
        self.query_one("#online-lbl", Static).update(  # type: ignore[attr-defined]
            Text("not signed in", style=theme.MUTED)
        )

        self.query_one("#robot-lbl", Static).update(  # type: ignore[attr-defined]
            Text("—", style=theme.DIM)
        )
        self.query_one("#nightlight-lbl", Static).update(  # type: ignore[attr-defined]
            Text("○", style=theme.MUTED)
        )
        self.query_one("#lock-lbl", Static).update(Text("□", style=theme.MUTED))  # type: ignore[attr-defined]

        drawer = Text()
        drawer.append("Drawer ", style=theme.MUTED)
        drawer.append("—", style=theme.DIM)
        self.query_one("#drawer-lbl", Static).update(drawer)  # type: ignore[attr-defined]

        litter = Text()
        litter.append("Litter ", style=theme.MUTED)
        litter.append("—", style=theme.DIM)
        self.query_one("#litter-lbl", Static).update(litter)  # type: ignore[attr-defined]

        weight = Text()
        weight.append("cat ", style=theme.MUTED)
        weight.append("—", style=theme.DIM)
        self.query_one("#weight-lbl", Static).update(weight)  # type: ignore[attr-defined]

        self.query_one("#clean-lbl", Static).update(  # type: ignore[attr-defined]
            Text("Last visit —", style=theme.MUTED)
        )

    @work(thread=True)
    def _announce_update(self) -> None:
        """Log a one-line notice when a newer release is published.

        A thread worker because it makes a network request, and the dashboard
        must not wait on PyPI to finish starting. It only ever tells you an
        upgrade exists; nothing here installs anything (see :mod:`asher.updates`
        for why that stays manual).
        """
        from ..updates import check  # noqa: PLC0415

        update = check()
        if update is not None:
            self.call_from_thread(self._log_warn, update.notice)  # type: ignore[attr-defined]

    def _show_welcome(self) -> None:
        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]
        log.write("")
        banner = Text(" ◆ Asher CLI", style=f"bold {theme.ACCENT}")
        banner.append(" — Litter Robot Dashboard", style=theme.MUTED)
        log.write(banner)
        log.write(Text(" Connecting to Whisker cloud API…", style=theme.MUTED))
        hint = Text(" Type ", style=theme.MUTED)
        hint.append("help", style=theme.OK)
        hint.append(" to see available commands.", style=theme.MUTED)
        log.write(hint)
        log.write(Text(" " + "─" * 52, style=theme.BORDER_SUBTLE))
        log.write("")

    def _set_cat(self, mode: str, label: str = "") -> None:
        self._cat_mode = mode
        self._cat_label = label
        self._cat_frame = 0
        self._cat_fx_idx = 0
        cats = CATS.get(mode, CATS["idle"])
        frame = cats[0]
        palette = _CAT_PALETTES.get(mode, [theme.ACCENT])
        color = getattr(self, "_cat_color", None) or palette[0]
        self.query_one("#cat-art", Static).update(Text(frame, style=color))  # type: ignore[attr-defined]
        fx = _CAT_FX.get(mode, [""])
        self.query_one("#cat-fx", Static).update(Text(fx[0], style=color))  # type: ignore[attr-defined]
        label_txt = Text(label, style=theme.SUBTLE) if label else Text("")
        self.query_one("#cat-label", Static).update(label_txt)  # type: ignore[attr-defined]

    def _tick_cat(self) -> None:
        try:
            if self._is_loading:
                self._spinner_idx = (self._spinner_idx + 1) % len(_SPINNER)
                self.query_one("#online-lbl", Static).update(  # type: ignore[attr-defined]
                    Text(f"{_SPINNER[self._spinner_idx]} connecting…", style=theme.MUTED)
                )

                # shimmer placeholders
                shimmer = _SPINNER[self._spinner_idx]
                bar = Text()
                bar.append("Drawer ", style=theme.MUTED)
                bar.append(f"{shimmer} —", style=theme.DIM)
                self.query_one("#drawer-lbl", Static).update(bar)  # type: ignore[attr-defined]

                lit = Text()
                lit.append("Litter ", style=theme.MUTED)
                lit.append(f"{shimmer}", style=theme.DIM)
                self.query_one("#litter-lbl", Static).update(lit)  # type: ignore[attr-defined]

                wt = Text()
                wt.append("cat 🐱 ", style=theme.MUTED)
                wt.append(f"{shimmer}", style=theme.DIM)
                self.query_one("#weight-lbl", Static).update(wt)  # type: ignore[attr-defined]

                self.query_one("#clean-lbl", Static).update(  # type: ignore[attr-defined]
                    Text(f"Last visit {shimmer}", style=theme.MUTED)
                )

                self.query_one("#robot-lbl", Static).update(  # type: ignore[attr-defined]
                    Text(f"{shimmer}", style=theme.DIM)
                )
                self.query_one("#nightlight-lbl", Static).update(  # type: ignore[attr-defined]
                    Text(f"○ {shimmer}", style=theme.DIM)
                )
                self.query_one("#lock-lbl", Static).update(  # type: ignore[attr-defined]
                    Text(f"{shimmer}", style=theme.DIM)
                )

            cats = CATS.get(self._cat_mode, CATS["idle"])
            self._cat_frame = (self._cat_frame + 1) % len(cats)
            frame = cats[self._cat_frame]
            palette = _CAT_PALETTES.get(self._cat_mode, [theme.ACCENT])
            color = getattr(self, "_cat_color", None) or palette[self._cat_frame % len(palette)]
            self.query_one("#cat-art", Static).update(Text(frame, style=color))  # type: ignore[attr-defined]

            fx = _CAT_FX.get(self._cat_mode, [""])
            self._cat_fx_idx = (self._cat_fx_idx + 1) % len(fx)
            self.query_one("#cat-fx", Static).update(Text(fx[self._cat_fx_idx], style=color))  # type: ignore[attr-defined]
        except NoMatches:
            pass

    def _log_ok(self, msg: str) -> None:
        t = ts()
        t.append(f"✓ {msg}", style=theme.OK)
        self.query_one("#log", RichLog).write(t)  # type: ignore[attr-defined]

    def _log_err(self, msg: str) -> None:
        t = ts()
        t.append(f"✖ {msg}", style=theme.DANGER)
        self.query_one("#log", RichLog).write(t)  # type: ignore[attr-defined]

    def _log_warn(self, msg: str) -> None:
        t = ts()
        t.append(f"⚠ {msg}", style=theme.WARN)
        self.query_one("#log", RichLog).write(t)  # type: ignore[attr-defined]

    def _log_info(self, msg: str) -> None:
        t = ts()
        t.append(f"  {msg}", style=theme.SUBTLE)
        self.query_one("#log", RichLog).write(t)  # type: ignore[attr-defined]

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()  # type: ignore[attr-defined]

    def action_blur_input(self) -> None:
        self.query_one("#cmd-input", Input).blur()  # type: ignore[attr-defined]

    def action_dismiss_fault(self) -> None:
        """Hide the fault banner until the set of active faults changes."""
        with contextlib.suppress(NoMatches):
            banner = self.query_one("#fault-banner", Static)  # type: ignore[attr-defined]
            banner.display = False
