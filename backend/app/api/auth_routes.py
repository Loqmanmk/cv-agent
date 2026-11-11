from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.auth_dependencies import (
    SettingsDep,
    client_address,
    get_account_service,
    get_email_throttle,
    get_login_throttle,
    get_register_limiter,
    get_session_service,
    get_verification_service,
    require_allowed_origin,
    require_user,
    retry_headers,
)
from app.api.auth_schemas import Credentials, EmailBody, MessageOut, SessionOut, TokenBody
from app.api.cookies import clear_session_cookie, set_session_cookie
from app.api.login_throttle import LoginThrottle
from app.api.rate_limit import RateLimiter
from app.services.account_service import AccountService
from app.services.email_verification import VerificationService
from app.services.session_service import ActiveSession, SessionService

CHECK_INBOX = "Check your inbox: we sent you a link to confirm your email address."
VERIFIED = "Your email address is verified."
INVALID_LINK = "This link is invalid or has expired. Ask for a new one."
TOO_MANY_EMAILS = "Too many emails were requested. Please try again later."

router = APIRouter(prefix="/auth")

Accounts = Annotated[AccountService, Depends(get_account_service)]
Sessions = Annotated[SessionService, Depends(get_session_service)]
Active = Annotated[ActiveSession, Depends(require_user)]
Verification = Annotated[VerificationService, Depends(get_verification_service)]
EmailThrottle = Annotated[LoginThrottle, Depends(get_email_throttle)]


def _limit_emails(throttle: LoginThrottle, request: Request, email: str) -> None:
    wait = throttle.acquire(client_address(request), email)
    if wait > 0:
        raise HTTPException(status_code=429, detail=TOO_MANY_EMAILS, headers=retry_headers(wait))


@router.post(
    "/register",
    status_code=202,
    response_model=MessageOut,
    dependencies=[Depends(require_allowed_origin)],
)
def register(
    body: Credentials,
    request: Request,
    settings: SettingsDep,
    verification: Verification,
    emails: EmailThrottle,
    limiter: Annotated[RateLimiter, Depends(get_register_limiter)],
) -> MessageOut:
    if not settings.registration_open:
        raise HTTPException(status_code=403, detail="Registration is closed.")
    wait = limiter.acquire(client_address(request))
    if wait > 0:
        detail = "Too many registrations. Please try again later."
        raise HTTPException(status_code=429, detail=detail, headers=retry_headers(wait))
    _limit_emails(emails, request, body.email)
    verification.register(body.email, body.password)
    return MessageOut(detail=CHECK_INBOX)


@router.post(
    "/resend-verification",
    status_code=202,
    response_model=MessageOut,
    dependencies=[Depends(require_allowed_origin)],
)
def resend_verification(
    body: EmailBody, request: Request, verification: Verification, emails: EmailThrottle
) -> MessageOut:
    _limit_emails(emails, request, body.email)
    verification.resend(body.email)
    return MessageOut(detail=CHECK_INBOX)


@router.post(
    "/verify-email", response_model=MessageOut, dependencies=[Depends(require_allowed_origin)]
)
def verify_email(body: TokenBody, verification: Verification) -> MessageOut:
    if not verification.verify(body.token):
        raise HTTPException(status_code=400, detail=INVALID_LINK)
    return MessageOut(detail=VERIFIED)


@router.post("/login", response_model=SessionOut, dependencies=[Depends(require_allowed_origin)])
def login(
    body: Credentials,
    request: Request,
    response: Response,
    accounts: Accounts,
    sessions: Sessions,
    settings: SettingsDep,
    throttle: Annotated[LoginThrottle, Depends(get_login_throttle)],
) -> SessionOut:
    wait = throttle.acquire(client_address(request), body.email)
    if wait > 0:
        detail = "Too many login attempts. Please try again later."
        raise HTTPException(status_code=429, detail=detail, headers=retry_headers(wait))
    account = accounts.authenticate(body.email, body.password)
    sessions.end(request.cookies.get(settings.session_cookie_name))
    started = sessions.start(account.id)
    sessions.purge_expired()
    set_session_cookie(response, settings, started)
    return SessionOut(
        email=account.email,
        csrf_token=started.csrf_token,
        email_verified=account.email_verified_at is not None,
    )


@router.post("/logout", status_code=204)
def logout(
    request: Request, settings: SettingsDep, sessions: Sessions, _active: Active
) -> Response:
    sessions.end(request.cookies.get(settings.session_cookie_name))
    response = Response(status_code=204)
    clear_session_cookie(response, settings)
    return response


@router.post("/logout-all", status_code=204)
def logout_all(settings: SettingsDep, sessions: Sessions, active: Active) -> Response:
    sessions.end_all(active.user_id)
    response = Response(status_code=204)
    clear_session_cookie(response, settings)
    return response


@router.get("/me", response_model=SessionOut)
def me(active: Active, accounts: Accounts) -> SessionOut:
    account = accounts.get_account(active.user_id)
    if account is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    return SessionOut(
        email=account.email,
        csrf_token=active.csrf_token,
        email_verified=account.email_verified_at is not None,
    )
