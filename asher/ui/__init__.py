"""UI layout, CSS, cat panel, and log helpers."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Input, RichLog, Static

from ..cats import CATS
from ..helpers import ts

try:
    VERSION = pkg_version("asher-cli")
except PackageNotFoundError:
    VERSION = "dev"

_CSS = """
Screen {
    background: #0d1117;
    color: #c9d1d9;
}

/* ── Status bar ── */
#status-bar {
    background: #161b22;
    height: 4;
    border-bottom: solid #30363d;
    dock: top;
    padding: 0;
    layout: vertical;
}

.srow {
    height: 2;
    layout: horizontal;
    align: left middle;
    padding: 0 2;
}

.srow:first-child {
    border-bottom: solid #30363d;
}

.sep {
    color: #30363d;
    width: auto;
    height: 1;
    padding: 0 1;
}

.chunk {
    width: auto;
    padding: 0 2 0 0;
    height: 1;
}

/* ── Main ── */
#main-area {
    layout: horizontal;
    height: 1fr;
}

#log {
    width: 1fr;
    height: 1fr;
    background: #0d1117;
    padding: 1 2;
    overflow-x: hidden;
    scrollbar-background: #161b22;
    scrollbar-color: #30363d;
    scrollbar-color-hover: #58a6ff;
}

/* ── Cat panel ── */
#cat-panel {
    width: 30;
    background: #0d1117;
    border-left: solid #21262d;
    align: center middle;
    padding: 1 2;
    height: 1fr;
    layout: vertical;
}

#cat-art {
    color: #58a6ff;
    text-align: left;
    width: 26;
    content-align: left middle;
}

#cat-label {
    color: #484f58;
    text-style: italic;
    text-align: left;
    width: 26;
    padding-top: 1;
    height: 3;
}

/* ── Input area (outer dock + hint below the box) ── */
#bottom-dock {
    dock: bottom;
    height: 4;
    background: #161b22;
    layout: vertical;
    padding: 0 0 0 0;
}

#input-bar {
    background: #161b22;
    height: 3;
    border-top: solid #30363d;
    border-bottom: solid #30363d;
    layout: vertical;
    padding: 0 2;
}

#input-row {
    layout: horizontal;
    height: 1;
    align: left middle;
}

#prompt {
    color: #3fb950;
    width: auto;
    text-style: bold;
    padding: 0 1 0 0;
    height: 1;
}

#hint-bar {
    color: #484f58;
    height: 1;
    padding: 0 2;
}

#cmd-input {
    width: 1fr;
    background: #161b22;
    color: #e6edf3;
    border: none;
    height: 1;
    padding: 0;
}

Input {
    border: none;
    background: #161b22;
    padding: 0;
}
"""


_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class UIMixin:
    CSS: str = _CSS

    # declared for type checkers; assigned in AsherApp.__init__
    _cat_mode: str
    _cat_frame: int
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
                yield Static(CATS["idle"], id="cat-art")  # type: ignore[arg-type]
                yield Static("idle", id="cat-label")

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
        cats = CATS.get(mode, CATS["idle"])
        frame = cats[0] if isinstance(cats, list) else cats
        color = "#f85149" if mode == "error" else "#d29922" if mode == "full" else "#58a6ff"
        self.query_one("#cat-art", Static).update(Text(frame, style=color))  # type: ignore[attr-defined]
        self.query_one("#cat-label", Static).update(  # type: ignore[attr-defined]
            Text(label or mode, style="italic #484f58")
        )

    def _tick_cat(self) -> None:
        if self._is_loading:
            self._spinner_idx = (self._spinner_idx + 1) % len(_SPINNER)
            self.query_one("#online-lbl", Static).update(  # type: ignore[attr-defined]
                Text(f"{_SPINNER[self._spinner_idx]} connecting…", style="#484f58")
            )
        cats = CATS.get(self._cat_mode, CATS["idle"])
        if not isinstance(cats, list):
            return
        self._cat_frame = (self._cat_frame + 1) % len(cats)
        frame = cats[self._cat_frame]
        self.query_one("#cat-art", Static).update(Text(frame, style="#58a6ff"))  # type: ignore[attr-defined]

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
