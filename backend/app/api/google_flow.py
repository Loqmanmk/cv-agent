import secrets
from dataclasses import dataclass, field
from typing import Self

from fastapi import Response

from app.core.config import Settings

FLOW_MAX_AGE_SECONDS = 600
FLOW_COOKIE_PATH = "/"
MAX_COOKIE_LENGTH = 512
SEPARATOR = "."


def flow_cookie_name(settings: Settings) -> str:
    """The __Host- prefix makes browsers refuse a cookie that is not Secure."""
    return "__Host-google_signin" if settings.cookie_secure else "google_signin"


@dataclass(frozen=True)
class PendingSignIn:
    """The one-time values of a Google sign-in, kept by the browser until Google answers."""

    state: str = field(repr=False)
    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)

    def encode(self) -> str:
        return SEPARATOR.join((self.state, self.nonce, self.code_verifier))

    @classmethod
    def decode(cls, value: str | None) -> Self | None:
        """The values read back from the cookie, or None when the cookie is missing or damaged."""
        if not value or len(value) > MAX_COOKIE_LENGTH:
            return None
        parts = value.split(SEPARATOR)
        if len(parts) != 3 or not all(parts):
            return None
        return cls(*parts)

    def state_matches(self, state: str | None) -> bool:
        """Whether Google sent back the state of this browser (a forged callback has another)."""
        if state is None:
            return False
        return secrets.compare_digest(self.state.encode(), state.encode())


def set_flow_cookie(response: Response, settings: Settings, pending: PendingSignIn) -> None:
    """Short-lived, unreadable by scripts, and sent back on Google's redirect (SameSite=Lax)."""
    response.set_cookie(
        key=flow_cookie_name(settings),
        value=pending.encode(),
        max_age=FLOW_MAX_AGE_SECONDS,
        path=FLOW_COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_flow_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=flow_cookie_name(settings),
        path=FLOW_COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
