"""Asher CLI — Litter Robot terminal dashboard."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.timer import Timer

from textual.app import App
from textual.binding import Binding
from textual.widgets import Input

from . import theme
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
        from .config import load as _load_config  # noqa: PLC0415

        _cfg = _load_config()
        self._poll_interval: int = _cfg["poll_interval_seconds"]
        self._poll_timer: Timer | None = None
        self._cat_panel_visible: bool = _cfg["cat_panel_visible"]
        self._cat_color: str | None = _cfg["cat_panel_color"]
        self._active_pet_idx: int = _cfg["active_pet_index"]
        self._notifications_enabled: bool = _cfg["notifications"]
        self._notification_sound: bool = _cfg["notification_sound"]
        self._prev_faults: set[str] = set()
        self._fault_dismissed: set[str] = set()
        self._cycle_start: Any = None
        self._cycle_timer: Timer | None = None
        self._completion_matches: list = []
        self._completion_idx: int = 0

    def get_css_variables(self) -> dict[str, str]:
        """Expose the Catppuccin roles to every stylesheet as ``$asher-*``.

        Covers ``ui/style.tcss`` and the screen-level ``CSS`` blocks alike, so a
        re-flavour touches only ``asher/theme.py``.
        """
        return {**super().get_css_variables(), **theme.CSS_VARIABLES}

    def on_mount(self) -> None:
        self._refresh_title()
        self._show_welcome()
        self._show_loading_state()
        self.query_one("#cat-panel").display = self._cat_panel_visible
        self._connect_worker()
        if self._poll_interval > 0:
            self._poll_timer = self.set_interval(self._poll_interval, self._poll_status_interval)
        else:
            self._poll_timer = None
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
