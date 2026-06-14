"""Asher CLI — Litter Robot terminal dashboard."""

from __future__ import annotations

import contextlib
from typing import Any

from textual import events
from textual.app import App
from textual.binding import Binding
from textual.widgets import Input

from .commands import CommandsMixin
from .connection import ConnectionMixin
from .monitoring import MonitoringMixin
from .ui import UIMixin


class AsherApp(UIMixin, ConnectionMixin, MonitoringMixin, CommandsMixin, App):  # type: ignore[type-arg]
    CSS = UIMixin.CSS  # must live in AsherApp.__dict__ so Textual gives it full user-CSS priority
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_log", "Clear log"),
        Binding("escape", "blur_input", "Focus log", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._account: Any = None
        self._robot: Any = None
        self._pets: list = []
        self._cat_mode: str = "idle"
        self._cat_frame: int = 0
        self._cmd_history: list[str] = []
        self._hist_idx: int = -1
        self._login_state: str = ""   # "" | "awaiting_email" | "awaiting_password"
        self._login_email: str = ""

    _INPUT_STYLES = "border: none; background: #161b22; outline: none;"

    def on_mount(self) -> None:
        self._refresh_title()
        self._show_welcome()
        self._connect_worker()
        self.set_interval(30, self._poll_status_interval)
        self.set_interval(0.9, self._tick_cat)
        inp = self.query_one("#cmd-input", Input)
        inp.set_styles(self._INPUT_STYLES)
        inp.focus()

    def on_focus(self, event: events.Focus) -> None:
        if getattr(event.widget, "id", None) == "cmd-input":
            event.widget.set_styles(self._INPUT_STYLES)  # type: ignore[union-attr]

    async def on_unmount(self) -> None:
        if self._account:
            with contextlib.suppress(Exception):
                await self._account.disconnect()
