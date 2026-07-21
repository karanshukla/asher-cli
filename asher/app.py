"""Asher CLI — Litter Robot terminal dashboard."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.timer import Timer

from textual.app import App
from textual.binding import Binding
from textual.widgets import Input

from .commands import CommandsMixin
from .connection import ConnectionMixin
from .monitoring import MonitoringMixin
from .robot_adapters import RobotAdapter
from .robot_protocol import RobotProtocol
from .ui import UIMixin


class AsherApp(UIMixin, ConnectionMixin, MonitoringMixin, CommandsMixin, App):  # type: ignore[type-arg]
    CSS_PATH = "ui/style.tcss"
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_log", "Clear log"),
        Binding("escape", "blur_input", "Focus log", show=False),
        Binding("d", "dismiss_fault", "Dismiss fault banner", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._account: Any = None
        self._robots: list[RobotProtocol] = []
        self._robot: RobotProtocol | None = None
        self._adapter: RobotAdapter | None = None
        self._pets: list = []
        self._cat_mode: str = "idle"
        self._cat_frame: int = 0
        self._cat_fx_idx: int = 0
        self._cmd_history: list[str] = []
        self._hist_idx: int = -1
        from .login_flow import LoginFlow

        self._login = LoginFlow()
        self._last_cat_seen: Any = None
        self._is_loading: bool = True
        self._spinner_idx: int = 0
        self._poll_interval: int = 300
        self._poll_timer: Timer | None = None
        self._cat_panel_visible: bool = True
        self._cat_color: str | None = None
        self._active_pet_idx: int = 0
        self._prev_faults: set[str] = set()
        self._fault_dismissed: set[str] = set()
        self._cycle_start: Any = None
        self._cycle_timer: Timer | None = None

    def on_mount(self) -> None:
        self._refresh_title()
        self._show_welcome()
        self._show_loading_state()
        self._connect_worker()
        self._poll_timer = self.set_interval(300, self._poll_status_interval)
        self.set_interval(0.4, self._tick_cat)
        self.query_one("#cmd-input", Input).focus()

    async def on_unmount(self) -> None:
        if self._robot:
            with contextlib.suppress(Exception):
                await self._robot.unsubscribe()
        if self._account:
            with contextlib.suppress(Exception):
                await self._account.disconnect()
        print("meow")
