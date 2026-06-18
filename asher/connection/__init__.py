"""Whisker cloud API connection and authentication."""

from __future__ import annotations

import contextlib
import os
from typing import Any

import keyring
import keyring.errors
from dotenv import load_dotenv
from textual import work
from textual.widgets import RichLog

from ..helpers import ts

load_dotenv()

_SERVICE = "asher-cli"


def _keyring_available() -> bool:
    try:
        keyring.get_keyring()
        return True
    except Exception:
        return False


def _keyring_load() -> tuple[str, str]:
    try:
        email = keyring.get_password(_SERVICE, "email") or ""
        password = keyring.get_password(_SERVICE, "password") or ""
        return email, password
    except Exception:
        return "", ""


def _keyring_save(email: str, password: str) -> bool:
    try:
        keyring.set_password(_SERVICE, "email", email)
        keyring.set_password(_SERVICE, "password", password)
        return True
    except Exception:
        return False


def _keyring_delete() -> None:
    for key in ("email", "password"):
        with contextlib.suppress(Exception):
            keyring.delete_password(_SERVICE, key)


class ConnectionMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _account: Any
    _robot: Any
    _pets: list

    @work(exclusive=True)
    async def _connect_worker(
        self, *, email: str = "", password: str = "", save_to_keyring: bool = False
    ) -> None:
        self._is_loading = True  # type: ignore[attr-defined]
        self._show_loading_state()  # type: ignore[attr-defined]

        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]

        if not email or not password:
            if _keyring_available():
                self._log_info("Keyring is available")  # type: ignore[attr-defined]
                email, password = _keyring_load()
            else:
                self._log_warn("Keyring not available")  # type: ignore[attr-defined]

        if not email or not password:
            env_email = os.getenv("LITTER_ROBOT_USER") or ""
            env_pass = os.getenv("LITTER_ROBOT_PASSWORD") or ""
            email = email or env_email
            password = password or env_pass

        if not email or not password:
            from textual.widgets import Static  # noqa: PLC0415

            self._is_loading = False  # type: ignore[attr-defined]
            self._show_signed_out_state()  # type: ignore[attr-defined]
            self._log_info("No saved credentials found.")  # type: ignore[attr-defined]
            self._log_info("Type /login to sign in.")  # type: ignore[attr-defined]
            self._set_cat("idle", "not signed in")  # type: ignore[attr-defined]
            self.query_one("#hint-bar", Static).update("/login to sign in")  # type: ignore[attr-defined]
            return

        try:
            from pylitterbot import Account  # noqa: PLC0415

            self._account = Account()
            await self._account.connect(
                username=email, password=password, load_robots=True, load_pets=True
            )
            self._pets = list(self._account.pets)
            robots = list(self._account.robots)

            if not robots:
                self._is_loading = False  # type: ignore[attr-defined]
                self._show_signed_out_state()  # type: ignore[attr-defined]
                self._log_err("No Litter Robots found on this account.")  # type: ignore[attr-defined]
                self._set_cat("error", "no robots")  # type: ignore[attr-defined]
                self._account = None
                return

            self._robot = robots[0]
            await self._start_monitoring()  # type: ignore[attr-defined]
            if len(robots) > 1:
                self._log_info(  # type: ignore[attr-defined]
                    f"{len(robots)} robots found — using '{getattr(robots[0], 'name', 'robot #1')}'"
                )
                for i, rb in enumerate(robots):
                    model = type(rb).__name__
                    self._log_info(  # type: ignore[attr-defined]
                        f"  [{i}] {getattr(rb, 'name', '?')} ({model}  serial={getattr(rb, 'serial', '?')})"
                    )

            await self._update_last_cat_seen()  # type: ignore[attr-defined]
            await self._refresh_status()  # type: ignore[attr-defined]

            t = ts()
            t.append("✓ Connected to ", style="#3fb950")
            name = getattr(self._robot, "name", "robot")
            model = type(self._robot).__name__
            t.append(name, style="bold #e6edf3")
            t.append(f" ({model})", style="#484f58")
            log.write(t)
            self._set_cat("happy", "connected!")  # type: ignore[attr-defined]

            if save_to_keyring:
                if _keyring_save(email, password):
                    self._log_info("Credentials saved to keyring.")  # type: ignore[attr-defined]
                else:
                    self._log_warn("Keyring unavailable - credentials saved for this session only.")  # type: ignore[attr-defined]

        except ImportError:
            self._is_loading = False  # type: ignore[attr-defined]
            self._show_signed_out_state()  # type: ignore[attr-defined]
            self._log_err("pylitterbot not installed. Run: pip install pylitterbot")  # type: ignore[attr-defined]
            self._set_cat("error", "missing dep")  # type: ignore[attr-defined]
        except Exception as exc:
            self._is_loading = False  # type: ignore[attr-defined]
            self._show_signed_out_state()  # type: ignore[attr-defined]
            self._log_err(f"Connection failed: {exc}")  # type: ignore[attr-defined]
            self._log_warn("Type '/login' to try again or '/logout' to clear credentials.")  # type: ignore[attr-defined]
            self._set_cat("error", "auth error")  # type: ignore[attr-defined]
            with contextlib.suppress(Exception):
                await self._account.disconnect()
            self._account = None
            self._robot = None
