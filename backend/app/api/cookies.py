from typing import Literal

from fastapi import Response

from app.core.config import Settings
from app.services.session_service import StartedSession

SAME_SITE: Literal["lax", "strict", "none"] = "lax"
COOKIE_PATH = "/"


def set_session_cookie(
    response: Response,
    settings: Settings,
    started: StartedSession,
) -> None:
    """The login cookie: unreadable by scripts, sent only to this site, and Secure online."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=started.token,
        expires=started.expires_at,
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=SAME_SITE,
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=SAME_SITE,
    )
