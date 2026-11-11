from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.auth_dependencies import (
    SettingsDep,
    client_address,
    get_account_service,
    get_login_throttle,
    get_register_limiter,
    get_session_service,
    require_allowed_origin,
    require_user,
    retry_headers,
)
from app.api.auth_schemas import AccountOut, Credentials, SessionOut
from app.api.cookies import clear_session_cookie, set_session_cookie
from app.api.login_throttle import LoginThrottle
from app.api.rate_limit import RateLimiter
from app.services.account_service import AccountService
from app.services.session_service import ActiveSession, SessionService

router = APIRouter(prefix="/auth")

Accounts = Annotated[AccountService, Depends(get_account_service)]
Sessions = Annotated[SessionService, Depends(get_session_service)]
Active = Annotated[ActiveSession, Depends(require_user)]


@router.post(
    "/register",
    status_code=201,
    response_model=AccountOut,
    dependencies=[Depends(require_allowed_origin)],
)
def register(
    body: Credentials,
    request: Request,
    accounts: Accounts,
    settings: SettingsDep,
    limiter: Annotated[RateLimiter, Depends(get_register_limiter)],
) -> AccountOut:
    if not settings.registration_open:
        raise HTTPException(status_code=403, detail="Registration is closed.")
    wait = limiter.acquire(client_address(request))
    if wait > 0:
        detail = "Too many registrations. Please try again later."
        raise HTTPException(status_code=429, detail=detail, headers=retry_headers(wait))
    return AccountOut(email=accounts.register(body.email, body.password).email)


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
    return SessionOut(email=account.email, csrf_token=started.csrf_token)


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
    return SessionOut(email=account.email, csrf_token=active.csrf_token)
