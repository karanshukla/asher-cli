"""Whisker cloud API connection and authentication."""

from __future__ import annotations

import contextlib
import json
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..robot_adapters import RobotAdapter
    from ..robot_protocol import RobotProtocol

import keyring
import keyring.errors
from dotenv import load_dotenv
from textual import work
from textual.widgets import RichLog

from ..helpers import robot_model, ts

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
    for key in ("email", "password", "preferred_robot", "token"):
        with contextlib.suppress(Exception):
            keyring.delete_password(_SERVICE, key)


def _keyring_save_robot(serial: str) -> None:
    with contextlib.suppress(Exception):
        keyring.set_password(_SERVICE, "preferred_robot", serial)


def _keyring_load_robot() -> str:
    try:
        return keyring.get_password(_SERVICE, "preferred_robot") or ""
    except Exception:
        return ""


def _keyring_load_token() -> dict | None:
    """Return the cached OAuth session token dict, or None if absent/unreadable."""
    try:
        raw = keyring.get_password(_SERVICE, "token")
    except Exception:
        return None
    if not raw:
        return None
    try:
        loaded = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _keyring_save_token(token: dict | None) -> None:
    """Persist the OAuth session token (JSON blob), or clear it when None.

    pylitterbot fires `token_update_callback` on every refresh, so this also
    serves as the "clear a poisoned/expired token" path: pass None to wipe it.
    """
    if not token:
        with contextlib.suppress(Exception):
            keyring.delete_password(_SERVICE, "token")
        return
    with contextlib.suppress(Exception):
        keyring.set_password(_SERVICE, "token", json.dumps(token))


class ConnectionMixin:
    # declared for type checkers; assigned in AsherApp.__init__
    _account: Any
    _robot: RobotProtocol | None
    _adapter: RobotAdapter | None
    _robots: list[RobotProtocol]
    _pets: list

    @work(exclusive=True)
    async def _connect_worker(
        self, *, email: str = "", password: str = "", save_to_keyring: bool = False
    ) -> None:
        self._is_loading = True  # type: ignore[attr-defined]
        self._show_loading_state()  # type: ignore[attr-defined]

        log = self.query_one("#log", RichLog)  # type: ignore[attr-defined]

        # Interactive login passes explicit creds — don't short-circuit on the
        # cached token (a fresh password was just entered). Auto-connect at
        # launch and poll fallback try the token first to skip the OAuth login.
        if not email and not password and await self._try_token_connect(log):
            return

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

            # token_update_callback captures token refreshes during this session
            # so subsequent launches can skip the password login entirely.
            self._account = Account(token_update_callback=_keyring_save_token)
            await self._account.connect(
                username=email, password=password, load_robots=True, load_pets=True
            )
            if not await self._finish_connect(log):
                return

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
            self._adapter = None

    async def _try_token_connect(self, log: RichLog) -> bool:
        """Attempt to connect using a cached OAuth token.

        Returns True if the token path resolved the connection (success OR a
        terminal "no robots" state) so the caller doesn't retry with a
        password. Returns False only when there's no token or token auth
        itself failed — in that case the stale token is wiped and the caller
        falls back to username/password.
        """
        token = _keyring_load_token()
        if not token:
            return False
        try:
            from pylitterbot import Account  # noqa: PLC0415

            self._account = Account(token=token, token_update_callback=_keyring_save_token)
            await self._account.connect(load_robots=True, load_pets=True)
        except Exception:
            # Stale/expired/invalid token — wipe it so a poisoned token can't
            # loop, then let the caller fall back to the password flow.
            _keyring_save_token(None)
            with contextlib.suppress(Exception):
                if self._account is not None:
                    await self._account.disconnect()
            self._account = None
            self._log_info("Saved session expired — signing in with password.")  # type: ignore[attr-defined]
            return False
        await self._finish_connect(log)
        return True

    async def _finish_connect(self, log: RichLog) -> bool:
        """Shared post-connect setup for both token and password auth paths.

        Loads pets/robots, picks the preferred robot, starts monitoring, and
        renders the "connected" status. Returns True on success; on an empty
        robot list shows the error state and returns False.
        """
        self._pets = list(self._account.pets)
        robots = list(self._account.robots)

        if not robots:
            self._is_loading = False  # type: ignore[attr-defined]
            self._show_signed_out_state()  # type: ignore[attr-defined]
            self._log_err("No Litter Robots found on this account.")  # type: ignore[attr-defined]
            self._set_cat("error", "no robots")  # type: ignore[attr-defined]
            self._account = None
            return False

        self._robots = robots
        preferred_serial = _keyring_load_robot()
        self._robot = next(
            (rb for rb in robots if getattr(rb, "serial", None) == preferred_serial),
            robots[0],
        )
        from ..robot_adapters import make_adapter  # noqa: PLC0415

        self._adapter = make_adapter(self._robot)
        await self._start_monitoring()  # type: ignore[attr-defined]
        if len(robots) > 1:
            self._log_info(  # type: ignore[attr-defined]
                f"{len(robots)} robots found — using '{getattr(robots[0], 'name', 'robot #1')}'"
            )
            for i, rb in enumerate(robots):
                self._log_info(  # type: ignore[attr-defined]
                    f"  [{i}] {getattr(rb, 'name', '?')} ({robot_model(rb)}  serial={getattr(rb, 'serial', '?')})"
                )

        await self._update_last_cat_seen()  # type: ignore[attr-defined]
        await self._refresh_status()  # type: ignore[attr-defined]

        t = ts()
        t.append("✓ Connected to ", style="#3fb950")
        name = getattr(self._robot, "name", "robot")
        t.append(name, style="bold #e6edf3")
        t.append(f" ({robot_model(self._robot)})", style="#484f58")
        log.write(t)
        self._set_cat("happy", "connected!")  # type: ignore[attr-defined]
        return True
