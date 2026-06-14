"""Whisker cloud API connection and authentication."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from textual import work
from textual.widgets import RichLog

from ..helpers import ts

load_dotenv()

EMAIL = os.getenv("LITTER_ROBOT_USER") or os.getenv("LR4_EMAIL", "")
PASSWORD = os.getenv("LITTER_ROBOT_PASSWORD") or os.getenv("LR4_PASSWORD", "")


class ConnectionMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _account: Any
    _robot: Any
    _pets: list

    @work(exclusive=True)
    async def _connect_worker(self) -> None:
        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]
        if not EMAIL or not PASSWORD:
            self._log_err("No credentials found.")  # type: ignore[attr-defined]
            self._log_err("Set LITTER_ROBOT_USER and LITTER_ROBOT_PASSWORD in .env")  # type: ignore[attr-defined]
            self._set_cat("error", "no creds")  # type: ignore[attr-defined]
            return

        try:
            from pylitterbot import Account  # noqa: PLC0415

            self._account = Account()
            await self._account.connect(
                username=EMAIL, password=PASSWORD, load_robots=True, load_pets=True
            )
            self._pets = list(self._account.pets)
            robots = list(self._account.robots)

            if not robots:
                self._log_err("No Litter Robots found on this account.")  # type: ignore[attr-defined]
                self._set_cat("error", "no robots")  # type: ignore[attr-defined]
                return

            self._robot = robots[0]
            if len(robots) > 1:
                self._log_info(  # type: ignore[attr-defined]
                    f"{len(robots)} robots found — using '{getattr(robots[0], 'name', 'robot #1')}'"
                )
                for i, rb in enumerate(robots):
                    model = type(rb).__name__
                    self._log_info(  # type: ignore[attr-defined]
                        f"  [{i}] {getattr(rb, 'name', '?')} ({model}  serial={getattr(rb, 'serial', '?')})"
                    )

            await self._refresh_status()  # type: ignore[attr-defined]

            t = ts()
            t.append("✓ Connected to ", style="#3fb950")
            name = getattr(self._robot, "name", "robot")
            model = type(self._robot).__name__
            t.append(name, style="bold #e6edf3")
            t.append(f" ({model})", style="#484f58")
            log.write(t)
            self._set_cat("happy", "connected!")  # type: ignore[attr-defined]

        except ImportError:
            self._log_err("pylitterbot not installed. Run: pip install pylitterbot")  # type: ignore[attr-defined]
            self._set_cat("error", "missing dep")  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_err(f"Connection failed: {exc}")  # type: ignore[attr-defined]
            self._set_cat("error", "auth error")  # type: ignore[attr-defined]
