"""Login flow state machine."""

from __future__ import annotations

from enum import Enum, auto


class LoginState(Enum):
    IDLE = auto()
    AWAITING_EMAIL = auto()
    AWAITING_PASSWORD = auto()


class LoginFlow:
    """Tracks the interactive login prompt state and the email captured so far."""

    def __init__(self) -> None:
        self._state = LoginState.IDLE
        self._email = ""

    # ── state checks ──────────────────────────────────────────────────────

    @property
    def state(self) -> LoginState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state is not LoginState.IDLE

    @property
    def email(self) -> str:
        if self._state is not LoginState.AWAITING_PASSWORD:
            raise RuntimeError("email only available in AWAITING_PASSWORD state")
        return self._email

    # ── transitions ───────────────────────────────────────────────────────

    def start(self) -> None:
        """Enter the login flow, awaiting email input."""
        self._state = LoginState.AWAITING_EMAIL
        self._email = ""

    def set_email(self, email: str) -> None:
        """Capture email and transition to awaiting password."""
        if self._state is not LoginState.AWAITING_EMAIL:
            raise RuntimeError("set_email only valid in AWAITING_EMAIL state")
        self._email = email
        self._state = LoginState.AWAITING_PASSWORD

    def complete(self) -> str:
        """Finish the flow, return the captured email, and reset to IDLE."""
        if self._state is not LoginState.AWAITING_PASSWORD:
            raise RuntimeError("complete only valid in AWAITING_PASSWORD state")
        captured = self._email
        self._state = LoginState.IDLE
        self._email = ""
        return captured
