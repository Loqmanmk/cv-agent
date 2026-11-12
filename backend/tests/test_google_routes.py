from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.api.google_dependencies import (
    get_external_login_service,
    get_google_client,
    get_google_limiter,
)
from app.api.rate_limit import RateLimiter
from app.domain.oauth import ExternalIdentity, OAuthError
from app.infrastructure.db.postgres_oauth import PostgresOAuthIdentityRepository
from app.infrastructure.db.postgres_sessions import PostgresSessionRepository
from app.infrastructure.db.postgres_users import PostgresUserRepository
from app.infrastructure.google_oidc import AuthorizationRequest
from app.services.external_login import ExternalLoginService
from app.services.session_service import SessionService
from tests.auth_helpers import APP_URL, build_auth_app, make_client

GOOGLE_URL = "https://accounts.google.com/o/oauth2/v2/auth?client_id=test"
STATE = "state-1"
NONCE = "nonce-1"
VERIFIER = "verifier-1"
FLOW_COOKIE = "google_signin"
JANE = ExternalIdentity("google", "g-1", "Jane.Doe@gmail.com", True)


class FakeGoogle:
    """Stands in for Google: fixed one-time values, and the identity or failure we choose."""

    def __init__(
        self, identity: ExternalIdentity = JANE, failure: OAuthError | None = None
    ) -> None:
        self.identity = identity
        self.failure = failure
        self.finished: list[tuple[str, str, str]] = []

    def start(self) -> AuthorizationRequest:
        return AuthorizationRequest(GOOGLE_URL, STATE, NONCE, VERIFIER)

    def finish(self, code: str, code_verifier: str, nonce: str) -> ExternalIdentity:
        self.finished.append((code, code_verifier, nonce))
        if self.failure is not None:
            raise self.failure
        return self.identity


def build_app(engine: Engine, google: FakeGoogle | None, limit: int = 100) -> FastAPI:
    app = build_auth_app(engine)
    sessions = SessionService(PostgresSessionRepository(engine))
    logins = ExternalLoginService(
        PostgresUserRepository(engine), PostgresOAuthIdentityRepository(engine), sessions
    )
    limiter = RateLimiter(limit, 900)
    app.dependency_overrides[get_google_client] = lambda: google
    app.dependency_overrides[get_external_login_service] = lambda: logins
    app.dependency_overrides[get_google_limiter] = lambda: limiter
    return app


def begin(client: TestClient) -> httpx.Response:
    response: httpx.Response = client.get("/auth/google/start", follow_redirects=False)
    return response


def answer(client: TestClient, **params: str) -> httpx.Response:
    query = {"code": "code-1", "state": STATE} | params
    response: httpx.Response = client.get(
        "/auth/google/callback", params=query, follow_redirects=False
    )
    return response


def login_error(response: httpx.Response) -> str:
    """The reason given to the login page, after checking that we were sent there."""
    assert response.status_code == 303
    location = urlsplit(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == f"{APP_URL}/login"
    return parse_qs(location.query)["error"][0]


def flow_cookie_header(response: httpx.Response) -> str:
    headers = [h for h in response.headers.get_list("set-cookie") if h.startswith(FLOW_COOKIE)]
    assert len(headers) == 1
    return headers[0].lower()


def count_users(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM users")).scalar_one())


def test_start_sends_the_browser_to_google_with_a_protected_cookie(clean_engine: Engine) -> None:
    response = begin(make_client(build_app(clean_engine, FakeGoogle())))

    assert response.status_code == 303
    assert response.headers["location"] == GOOGLE_URL
    cookie = flow_cookie_header(response)
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=600" in cookie


def test_a_full_sign_in_opens_a_session(clean_engine: Engine) -> None:
    google = FakeGoogle()
    client = make_client(build_app(clean_engine, google))
    begin(client)

    response = answer(client)

    assert response.status_code == 303
    assert response.headers["location"] == f"{APP_URL}/"
    assert "max-age=0" in flow_cookie_header(response)
    assert google.finished == [("code-1", VERIFIER, NONCE)]
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "jane.doe@gmail.com"
    assert me.json()["email_verified"] is True


def test_the_same_answer_cannot_be_used_twice(clean_engine: Engine) -> None:
    client = make_client(build_app(clean_engine, FakeGoogle()))
    begin(client)
    answer(client)

    assert login_error(answer(client)) == "google_failed"


def test_a_forged_state_is_refused(clean_engine: Engine) -> None:
    google = FakeGoogle()
    client = make_client(build_app(clean_engine, google))
    begin(client)

    assert login_error(answer(client, state="forged")) == "google_failed"
    assert google.finished == []
    assert client.get("/auth/me").status_code == 401


def test_an_answer_without_a_started_sign_in_is_refused(clean_engine: Engine) -> None:
    google = FakeGoogle()

    response = answer(make_client(build_app(clean_engine, google)))

    assert login_error(response) == "google_failed"
    assert google.finished == []


def test_cancelling_on_google_brings_the_user_back_to_login(clean_engine: Engine) -> None:
    client = make_client(build_app(clean_engine, FakeGoogle()))
    begin(client)

    response = client.get(
        "/auth/google/callback",
        params={"error": "access_denied", "state": STATE},
        follow_redirects=False,
    )

    assert login_error(response) == "google_cancelled"


def test_without_configuration_google_sign_in_is_unavailable(clean_engine: Engine) -> None:
    client = make_client(build_app(clean_engine, None))

    assert login_error(begin(client)) == "google_unavailable"
    assert login_error(answer(client)) == "google_unavailable"


def test_an_unverified_google_email_gets_its_own_reason(clean_engine: Engine) -> None:
    unverified = ExternalIdentity("google", "g-1", "Jane.Doe@gmail.com", False)
    client = make_client(build_app(clean_engine, FakeGoogle(identity=unverified)))
    begin(client)

    assert login_error(answer(client)) == "google_unverified"
    assert count_users(clean_engine) == 0


def test_a_refused_code_brings_the_user_back_to_login(clean_engine: Engine) -> None:
    failure = OAuthError("Signing in with Google failed. Please try again.")
    client = make_client(build_app(clean_engine, FakeGoogle(failure=failure)))
    begin(client)

    assert login_error(answer(client)) == "google_failed"
    assert client.get("/auth/me").status_code == 401


def test_too_many_sign_ins_from_one_address_are_slowed_down(clean_engine: Engine) -> None:
    client = make_client(build_app(clean_engine, FakeGoogle(), limit=1))
    begin(client)

    assert login_error(begin(client)) == "google_busy"


def test_an_overlong_code_is_refused_before_asking_google(clean_engine: Engine) -> None:
    google = FakeGoogle()
    client = make_client(build_app(clean_engine, google))
    begin(client)

    response = answer(client, code="x" * 3000)

    assert response.status_code >= 400
    assert google.finished == []
