from datetime import UTC, datetime

from fastapi import Response

from app.api.cookies import clear_session_cookie, set_session_cookie
from app.services.session_service import StartedSession
from tests.test_config import IsolatedSettings

STARTED = StartedSession(
    "tok",
    "csrf-secret",
    datetime(2026, 12, 9, 12, 0, tzinfo=UTC),
)


def cookie_after(action: str, secure: bool) -> str:
    settings = IsolatedSettings(cookie_secure=secure)
    response = Response()
    if action == "set":
        set_session_cookie(response, settings, STARTED)
    else:
        clear_session_cookie(response, settings)
    return response.headers["set-cookie"].lower()


def test_the_cookie_carries_the_token_and_cannot_be_read_by_scripts() -> None:
    header = cookie_after("set", secure=False)

    assert header.startswith("session=tok;")
    assert "httponly" in header
    assert "samesite=lax" in header
    assert "path=/" in header
    assert "expires=" in header


def test_the_cookie_is_not_marked_secure_on_a_development_machine() -> None:
    assert "secure" not in cookie_after("set", secure=False)


def test_in_production_the_cookie_is_secure_and_uses_the_host_prefix() -> None:
    header = cookie_after("set", secure=True)

    assert header.startswith("__host-session=tok;")
    assert "secure" in header
    assert "domain" not in header


def test_the_csrf_token_never_goes_into_the_cookie() -> None:
    assert "csrf" not in cookie_after("set", secure=False)


def test_clearing_the_cookie_expires_it_with_the_same_attributes() -> None:
    header = cookie_after("clear", secure=False)

    assert header.startswith('session="";')
    assert "max-age=0" in header
    assert "httponly" in header
    assert "path=/" in header


def test_clearing_the_production_cookie_uses_its_prefixed_name() -> None:
    header = cookie_after("clear", secure=True)

    assert header.startswith('__host-session="";')
    assert "secure" in header
