"""Whisker account credentials — the OS keyring, plus ``.env`` in dev mode.

Shared by every surface that authenticates: the TUI's connect worker, the
headless commands, and the background watcher. No Textual imports.
"""

from __future__ import annotations

import contextlib
import json
import os
from typing import Any

import keyring
import keyring.errors
from dotenv import load_dotenv

from .helpers import dev_mode

load_dotenv()

SERVICE = "asher-cli"


class HeadlessAuthError(Exception):
    """Raised when the headless path can't obtain credentials or connect.

    Carries the exit code the caller should surface (matches ROADMAP §25):
    1 = no credentials, 2 = connection/API failure.
    """

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


def from_env() -> tuple[str, str]:
    """Credentials from ``.env``/the environment — development only.

    Gated on dev mode so that in a real install the OS keyring is the *only*
    place credentials come from. A ``LITTER_ROBOT_USER`` left over in a shell
    profile or a checked-out ``.env`` would otherwise silently outrank the
    keyring and authenticate as somebody else's account.
    """
    if not dev_mode():
        return "", ""
    return os.getenv("LITTER_ROBOT_USER") or "", os.getenv("LITTER_ROBOT_PASSWORD") or ""


def keyring_available() -> bool:
    try:
        keyring.get_keyring()
        return True
    except Exception:
        return False


def load() -> tuple[str, str]:
    try:
        email = keyring.get_password(SERVICE, "email") or ""
        password = keyring.get_password(SERVICE, "password") or ""
        return email, password
    except Exception:
        return "", ""


def save(email: str, password: str) -> bool:
    try:
        keyring.set_password(SERVICE, "email", email)
        keyring.set_password(SERVICE, "password", password)
        return True
    except Exception:
        return False


def delete() -> None:
    for key in ("email", "password", "preferred_robot", "token"):
        with contextlib.suppress(Exception):
            keyring.delete_password(SERVICE, key)


def save_preferred_robot(serial: str) -> None:
    with contextlib.suppress(Exception):
        keyring.set_password(SERVICE, "preferred_robot", serial)


def load_preferred_robot() -> str:
    try:
        return keyring.get_password(SERVICE, "preferred_robot") or ""
    except Exception:
        return ""


def load_token() -> dict | None:
    """Return the cached OAuth session token dict, or None if absent/unreadable."""
    try:
        raw = keyring.get_password(SERVICE, "token")
    except Exception:
        return None
    if not raw:
        return None
    try:
        loaded = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def save_token(token: dict | None) -> None:
    """Persist the OAuth session token (JSON blob), or clear it when None.

    pylitterbot fires `token_update_callback` on every refresh, so this also
    serves as the "clear a poisoned/expired token" path: pass None to wipe it.
    """
    if not token:
        with contextlib.suppress(Exception):
            keyring.delete_password(SERVICE, "token")
        return
    with contextlib.suppress(Exception):
        keyring.set_password(SERVICE, "token", json.dumps(token))


def password_login() -> tuple[str, str]:
    email, password = load() if keyring_available() else ("", "")
    if not email or not password:
        env_email, env_password = from_env()
        email = email or env_email
        password = password or env_password
    return email, password


def available() -> bool:
    """Whether a background watcher could authenticate without prompting.

    A presence check, deliberately not a login: it costs no network round-trip,
    so starting the watcher still works offline, which is the whole point of its
    reconnect loop. It exists so ``asher watch start`` can refuse up front
    instead of reporting a pid for a process that stops a moment later.
    """
    if load_token():
        return True
    email, password = password_login()
    return bool(email and password)


async def connect_headless() -> Any:
    """Connect for the headless CLI — no TUI, no prompts.

    Same credential priority as the TUI's connect worker — cached OAuth token
    first, then email/password from the OS keyring, then (in dev mode only)
    ``.env`` — but with **no interactive login fallback** (there's no command bar
    to type into). A scheduled task's environment can't be assumed to match the
    project dir, so ``.env`` discovery relies on the ``load_dotenv()`` already
    called at import time rather than an upward directory search.

    Returns a connected ``Account`` on success. Raises :class:`HeadlessAuthError`
    (exit code 1 = no credentials, 2 = connection failure) otherwise — the caller
    maps those to process exit codes.
    """
    from pylitterbot import Account  # noqa: PLC0415

    token = load_token()
    if token:
        try:
            account = Account(token=token, token_update_callback=save_token)
            await account.connect(load_robots=True, load_pets=True)
            return account
        except Exception:
            save_token(None)
            with contextlib.suppress(Exception):
                await account.disconnect()  # type: ignore[possibly-undefined]

    email, password = password_login()
    if not email or not password:
        raise HeadlessAuthError(
            "No credentials found. Run asher-cli and sign in with /login at least once.",
            1,
        )

    try:
        account = Account(token_update_callback=save_token)
        await account.connect(username=email, password=password, load_robots=True, load_pets=True)
    except Exception as exc:
        raise HeadlessAuthError(f"Connection failed: {exc}", 2) from exc
    return account
