"""UI layout, CSS, cat panel, and log helpers."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

from dotenv import load_dotenv
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.css.query import NoMatches
from textual.widgets import Input, RichLog, Static

from ..cats import CATS
from ..helpers import ts

load_dotenv()

if os.getenv("ASHER_CLI_DEV_MODE", "false").lower() == "true":
    VERSION = "dev"
else:
    try:
        VERSION = pkg_version("asher-cli")
    except PackageNotFoundError:
        VERSION = "dev"

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

_CAT_PALETTES: dict[str, list[str]] = {
    "idle": ["#58a6ff", "#6cb0ff", "#7db8ff", "#6cb0ff"],
    "happy": ["#3fb950", "#4bc45a", "#56cf64", "#4bc45a"],
    "sleeping": ["#8b949e", "#9fa8b1", "#b0b8c1", "#9fa8b1"],
    "cleaning": ["#58a6ff", "#6cb0ff", "#7db8ff", "#6cb0ff"],
    "error": ["#f85149", "#ff7b72", "#f85149", "#ff7b72"],
    "full": ["#d29922", "#e3b341", "#d29922", "#e3b341"],
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
        "✨✨✨  ✨✨✨  ✨✨✨  ✨✨✨   \n  ✨✨✨  ✨✨✨  ✨✨✨  ✨✨✨ \n    ✨✨✨  ✨✨✨  ✨✨✨  ✨",
        " ✨✨✨  ✨✨✨  ✨✨✨  ✨✨✨  \n   ✨✨✨  ✨✨✨  ✨✨✨  ✨✨✨\n     ✨✨✨  ✨✨✨  ✨✨✨  ✨",
        "  ✨✨✨  ✨✨✨  ✨✨✨  ✨✨✨ \n    ✨✨✨  ✨✨✨  ✨✨✨  ✨✨✨\n      ✨✨✨  ✨✨✨  ✨✨✨  ",
        "   ✨✨✨  ✨✨✨  ✨✨✨  ✨✨✨\n     ✨✨✨  ✨✨✨  ✨✨✨  ✨✨\n       ✨✨✨  ✨✨✨  ✨✨✨ ",
    ],
    "error": [
        "⚡⚡   ⚡⚡   ⚡⚡   ⚡⚡     \n  ⚡⚡   ⚡⚡   ⚡⚡   ⚡⚡   \n    ⚡⚡   ⚡⚡   ⚡⚡   ⚡⚡ ",
        " ⚡⚡   ⚡⚡   ⚡⚡   ⚡⚡    \n   ⚡⚡   ⚡⚡   ⚡⚡   ⚡⚡  \n     ⚡⚡   ⚡⚡   ⚡⚡   ⚡⚡",
        "  ⚡⚡   ⚡⚡   ⚡⚡   ⚡⚡   \n    ⚡⚡   ⚡⚡   ⚡⚡   ⚡⚡ \n      ⚡⚡   ⚡⚡   ⚡⚡   ⚡",
        "   ⚡⚡   ⚡⚡   ⚡⚡   ⚡⚡  \n     ⚡⚡   ⚡⚡   ⚡⚡   ⚡⚡\n       ⚡⚡   ⚡⚡   ⚡⚡   ",
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
                yield Static("", id="status-lbl", classes="chunk")
            with Container(classes="srow"):
                yield Static("", id="drawer-lbl", classes="chunk")
                yield Static("│", classes="sep")
                yield Static("", id="weight-lbl", classes="chunk")
                yield Static("│", classes="sep")
                yield Static("", id="clean-lbl", classes="chunk")

        with Container(id="main-area"):
            yield RichLog(id="log", highlight=True, markup=True, wrap=True, min_width=0)
            with Container(id="cat-panel"):
                yield Static("", id="cat-fx")
                yield Static(CATS["idle"][0], id="cat-art")  # type: ignore[arg-type]

        with Container(id="bottom-dock"):
            with Container(id="input-bar"), Container(id="input-row"):
                yield Static(">", id="prompt")
                yield Input(placeholder="type a command  (help for list)…", id="cmd-input")
            yield Static(
                "help · clean · status · history · /login · /logout · quit",
                id="hint-bar",
            )

    def _refresh_title(self) -> None:
        t = Text()
        t.append("◆ ", style="bold #58a6ff")
        t.append("Asher CLI", style="bold #e6edf3")
        t.append(f" v{VERSION}", style="#484f58")
        self.query_one("#title-lbl", Static).update(t)  # type: ignore[attr-defined]

    def _show_loading_state(self) -> None:
        self.query_one("#online-lbl", Static).update(  # type: ignore[attr-defined]
            Text(f"{_SPINNER[0]} connecting…", style="#484f58")
        )
        dash = Text("—", style="#30363d")
        for wid in ("#robot-lbl", "#status-lbl", "#drawer-lbl", "#weight-lbl", "#clean-lbl"):
            self.query_one(wid, Static).update(dash)  # type: ignore[attr-defined]

    def _show_signed_out_state(self) -> None:
        self.query_one("#online-lbl", Static).update(  # type: ignore[attr-defined]
            Text("not signed in", style="#484f58")
        )

        self.query_one("#robot-lbl", Static).update(  # type: ignore[attr-defined]
            Text("—", style="#30363d")
        )
        self.query_one("#status-lbl", Static).update(  # type: ignore[attr-defined]
            Text("[—]", style="#30363d")
        )

        drawer = Text()
        drawer.append("Drawer ", style="#484f58")
        drawer.append("—", style="#30363d")
        self.query_one("#drawer-lbl", Static).update(drawer)  # type: ignore[attr-defined]

        weight = Text()
        weight.append("cat 🐱 ", style="#484f58")
        weight.append("—", style="#30363d")
        self.query_one("#weight-lbl", Static).update(weight)  # type: ignore[attr-defined]

        self.query_one("#clean-lbl", Static).update(  # type: ignore[attr-defined]
            Text("Last visit —", style="#484f58")
        )

    def _show_welcome(self) -> None:
        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]
        log.write("")
        log.write(
            Text.from_markup(" [bold #58a6ff]◆ Asher CLI[/] [#484f58]— Litter Robot Dashboard[/]")
        )
        log.write(Text.from_markup(" [#484f58]Connecting to Whisker cloud API…[/]"))
        log.write(
            Text.from_markup(
                " [#484f58]Type [/][#3fb950]help[/][#484f58] to see available commands.[/]"
            )
        )
        log.write(Text.from_markup(" [#21262d]" + "─" * 52 + "[/]"))
        log.write("")

    def _set_cat(self, mode: str, label: str = "") -> None:
        self._cat_mode = mode
        self._cat_frame = 0
        self._cat_fx_idx = 0
        cats = CATS.get(mode, CATS["idle"])
        frame = cats[0]
        palette = _CAT_PALETTES.get(mode, ["#58a6ff"])
        color = palette[0]
        self.query_one("#cat-art", Static).update(Text(frame, style=color))  # type: ignore[attr-defined]
        fx = _CAT_FX.get(mode, [""])
        self.query_one("#cat-fx", Static).update(Text(fx[0], style=color))  # type: ignore[attr-defined]

    def _tick_cat(self) -> None:
        try:
            if self._is_loading:
                self._spinner_idx = (self._spinner_idx + 1) % len(_SPINNER)
                self.query_one("#online-lbl", Static).update(  # type: ignore[attr-defined]
                    Text(f"{_SPINNER[self._spinner_idx]} connecting…", style="#484f58")
                )

                # shimmer placeholders
                shimmer = _SPINNER[self._spinner_idx]
                bar = Text()
                bar.append("Drawer ", style="#484f58")
                bar.append(f"{shimmer} —", style="#30363d")
                self.query_one("#drawer-lbl", Static).update(bar)  # type: ignore[attr-defined]

                wt = Text()
                wt.append("cat 🐱 ", style="#484f58")
                wt.append(f"{shimmer}", style="#30363d")
                self.query_one("#weight-lbl", Static).update(wt)  # type: ignore[attr-defined]

                self.query_one("#clean-lbl", Static).update(  # type: ignore[attr-defined]
                    Text(f"Last visit {shimmer}", style="#484f58")
                )

                self.query_one("#robot-lbl", Static).update(  # type: ignore[attr-defined]
                    Text(f"{shimmer}", style="#30363d")
                )
                self.query_one("#status-lbl", Static).update(  # type: ignore[attr-defined]
                    Text(f"[{shimmer}]", style="#30363d")
                )

            cats = CATS.get(self._cat_mode, CATS["idle"])
            self._cat_frame = (self._cat_frame + 1) % len(cats)
            frame = cats[self._cat_frame]
            palette = _CAT_PALETTES.get(self._cat_mode, ["#58a6ff"])
            color = palette[self._cat_frame % len(palette)]
            self.query_one("#cat-art", Static).update(Text(frame, style=color))  # type: ignore[attr-defined]

            fx = _CAT_FX.get(self._cat_mode, [""])
            self._cat_fx_idx = (self._cat_fx_idx + 1) % len(fx)
            self.query_one("#cat-fx", Static).update(Text(fx[self._cat_fx_idx], style=color))  # type: ignore[attr-defined]
        except NoMatches:
            pass

    def _log_ok(self, msg: str) -> None:
        t = ts()
        t.append(f"✓ {msg}", style="#3fb950")
        self.query_one("#log", RichLog).write(t)  # type: ignore[attr-defined]

    def _log_err(self, msg: str) -> None:
        t = ts()
        t.append(f"✖ {msg}", style="#f85149")
        self.query_one("#log", RichLog).write(t)  # type: ignore[attr-defined]

    def _log_warn(self, msg: str) -> None:
        t = ts()
        t.append(f"⚠ {msg}", style="#d29922")
        self.query_one("#log", RichLog).write(t)  # type: ignore[attr-defined]

    def _log_info(self, msg: str) -> None:
        t = ts()
        t.append(f"  {msg}", style="#8b949e")
        self.query_one("#log", RichLog).write(t)  # type: ignore[attr-defined]

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()  # type: ignore[attr-defined]

    def action_blur_input(self) -> None:
        self.query_one("#cmd-input", Input).blur()  # type: ignore[attr-defined]
