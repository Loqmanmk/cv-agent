import logging
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse

from app.api.auth_dependencies import SettingsDep, client_address, get_session_service
from app.api.cookies import set_session_cookie
from app.api.google_dependencies import (
    get_external_login_service,
    get_google_client,
    get_google_limiter,
)
from app.api.google_flow import (
    PendingSignIn,
    clear_flow_cookie,
    flow_cookie_name,
    set_flow_cookie,
)
from app.api.rate_limit import RateLimiter
from app.core.config import Settings
from app.domain.oauth import OAuthError
from app.infrastructure.google_oidc import GoogleOidcClient
from app.services.external_login import UNAVAILABLE, UNVERIFIED_EMAIL, ExternalLoginService
from app.services.mailing import clean_base_url
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/google")

# Short codes for the login page. It shows its own fixed message for each one, so a crafted
# link can never make the website display a text chosen by someone else.
FAILED = "google_failed"
CANCELLED = "google_cancelled"
NOT_CONFIGURED = "google_unavailable"
BUSY = "google_busy"
REASONS = {UNVERIFIED_EMAIL: "google_unverified", UNAVAILABLE: "account_unavailable"}

Google = Annotated[GoogleOidcClient | None, Depends(get_google_client)]
Logins = Annotated[ExternalLoginService, Depends(get_external_login_service)]
Sessions = Annotated[SessionService, Depends(get_session_service)]
Limiter = Annotated[RateLimiter, Depends(get_google_limiter)]
QueryValue = Annotated[str | None, Query(max_length=2048)]


def _redirect(url: str, settings: Settings) -> RedirectResponse:
    """A redirect that always forgets the one-time values of the sign-in."""
    response = RedirectResponse(url, status_code=303)
    clear_flow_cookie(response, settings)
    return response


def _back_to_login(settings: Settings, reason: str) -> RedirectResponse:
    query = urlencode({"error": reason})
    return _redirect(f"{clean_base_url(settings.app_base_url)}/login?{query}", settings)


def _checked_answer(
    google: GoogleOidcClient | None,
    pending: PendingSignIn | None,
    code: str | None,
    state: str | None,
    error: str | None,
) -> tuple[GoogleOidcClient, PendingSignIn, str] | str:
    """What is needed to finish the sign-in, or the reason to stop."""
    if error is not None:
        return CANCELLED if error == "access_denied" else FAILED
    if google is None:
        return NOT_CONFIGURED
    if pending is None or not code or not pending.state_matches(state):
        logger.warning("A Google callback that matches no sign-in of this browser was refused.")
        return FAILED
    return google, pending, code


@router.get("/start")
def start(
    request: Request, settings: SettingsDep, google: Google, limiter: Limiter
) -> RedirectResponse:
    if google is None:
        return _back_to_login(settings, NOT_CONFIGURED)
    if limiter.acquire(client_address(request)) > 0:
        return _back_to_login(settings, BUSY)
    authorization = google.start()
    pending = PendingSignIn(authorization.state, authorization.nonce, authorization.code_verifier)
    response = RedirectResponse(authorization.url, status_code=303)
    set_flow_cookie(response, settings, pending)
    return response


@router.get("/callback")
def callback(
    request: Request,
    settings: SettingsDep,
    google: Google,
    logins: Logins,
    sessions: Sessions,
    limiter: Limiter,
    code: QueryValue = None,
    state: QueryValue = None,
    error: QueryValue = None,
) -> RedirectResponse:
    if limiter.acquire(client_address(request)) > 0:
        return _back_to_login(settings, BUSY)
    pending = PendingSignIn.decode(request.cookies.get(flow_cookie_name(settings)))
    checked = _checked_answer(google, pending, code, state, error)
    if isinstance(checked, str):
        return _back_to_login(settings, checked)
    client, signin, answer_code = checked
    try:
        account = logins.sign_in(client.finish(answer_code, signin.code_verifier, signin.nonce))
    except OAuthError as exc:
        return _back_to_login(settings, REASONS.get(str(exc), FAILED))
    sessions.end(request.cookies.get(settings.session_cookie_name))
    started = sessions.start(account.id)
    sessions.purge_expired()
    response = _redirect(f"{clean_base_url(settings.app_base_url)}/", settings)
    set_session_cookie(response, settings, started)
    return response
