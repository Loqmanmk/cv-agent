import math
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.api.csrf import origin_allowed
from app.api.database import get_engine
from app.api.login_throttle import LoginThrottle
from app.api.rate_limit import RateLimiter
from app.core.config import Settings, get_settings
from app.domain.mail import EmailSender
from app.infrastructure.argon2_hasher import Argon2PasswordHasher
from app.infrastructure.db.postgres_email_tokens import PostgresEmailTokenRepository
from app.infrastructure.db.postgres_sessions import PostgresSessionRepository
from app.infrastructure.db.postgres_users import PostgresUserRepository
from app.infrastructure.outbox_sender import OutboxEmailSender
from app.services.account_service import AccountService
from app.services.email_token_service import EmailTokenService
from app.services.email_verification import VerificationService
from app.services.session_service import ActiveSession, SessionService, csrf_matches

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CSRF_HEADER = "X-CSRF-Token"
LOGIN_WINDOW_SECONDS = 900
LOGIN_ATTEMPTS_PER_ADDRESS = 30
LOGIN_ATTEMPTS_PER_ACCOUNT = 10
REGISTER_WINDOW_SECONDS = 3600
REGISTER_ATTEMPTS_PER_ADDRESS = 5
EMAIL_WINDOW_SECONDS = 3600
EMAILS_PER_ADDRESS = 10
EMAILS_PER_ACCOUNT = 3
UNVERIFIED = "Verify your email address before creating an application."

SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def get_account_service() -> AccountService:
    return AccountService(PostgresUserRepository(get_engine()), Argon2PasswordHasher())


@lru_cache
def get_session_service() -> SessionService:
    return SessionService(PostgresSessionRepository(get_engine()))


@lru_cache
def get_email_sender() -> EmailSender:
    return OutboxEmailSender(Path(get_settings().email_outbox_dir))


@lru_cache
def get_email_token_service() -> EmailTokenService:
    return EmailTokenService(PostgresEmailTokenRepository(get_engine()))


@lru_cache
def get_verification_service() -> VerificationService:
    return VerificationService(
        get_account_service(),
        get_email_token_service(),
        get_email_sender(),
        get_settings().app_base_url,
    )


@lru_cache
def get_login_throttle() -> LoginThrottle:
    return LoginThrottle(
        RateLimiter(LOGIN_ATTEMPTS_PER_ADDRESS, LOGIN_WINDOW_SECONDS),
        RateLimiter(LOGIN_ATTEMPTS_PER_ACCOUNT, LOGIN_WINDOW_SECONDS),
    )


@lru_cache
def get_email_throttle() -> LoginThrottle:
    """Limits the emails sent to one address, so nobody can flood someone's inbox."""
    return LoginThrottle(
        RateLimiter(EMAILS_PER_ADDRESS, EMAIL_WINDOW_SECONDS),
        RateLimiter(EMAILS_PER_ACCOUNT, EMAIL_WINDOW_SECONDS),
    )


@lru_cache
def get_register_limiter() -> RateLimiter:
    return RateLimiter(REGISTER_ATTEMPTS_PER_ADDRESS, REGISTER_WINDOW_SECONDS)


def client_address(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def retry_headers(wait: float) -> dict[str, str]:
    return {"Retry-After": str(math.ceil(wait))}


def require_allowed_origin(request: Request, settings: SettingsDep) -> None:
    """Refuse a state-changing browser request that comes from another website."""
    if not origin_allowed(request.headers.get("origin"), settings.cors_origin_list):
        raise HTTPException(status_code=403, detail="Origin not allowed.")


def require_user(
    request: Request,
    settings: SettingsDep,
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> ActiveSession:
    """The logged-in session. A state-changing request must also pass the origin and CSRF checks."""
    unsafe = request.method not in SAFE_METHODS
    if unsafe:
        require_allowed_origin(request, settings)
    active = sessions.authenticate(request.cookies.get(settings.session_cookie_name))
    if active is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    if unsafe and not csrf_matches(active.csrf_token, request.headers.get(CSRF_HEADER)):
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")
    return active


def require_verified_user(
    active: Annotated[ActiveSession, Depends(require_user)],
    accounts: Annotated[AccountService, Depends(get_account_service)],
) -> ActiveSession:
    """A logged-in user whose email address is confirmed: needed for what costs AI calls."""
    account = accounts.get_account(active.user_id)
    if account is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    if account.email_verified_at is None:
        raise HTTPException(status_code=403, detail=UNVERIFIED)
    return active


def get_current_user_id(active: Annotated[ActiveSession, Depends(require_user)]) -> uuid.UUID:
    return active.user_id


CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
