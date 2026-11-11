import uuid

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.api.auth_dependencies import (
    get_account_service,
    get_login_throttle,
    get_register_limiter,
    get_session_service,
)
from app.api.login_throttle import LoginThrottle
from app.api.rate_limit import RateLimiter
from app.core.config import get_settings
from app.infrastructure.db.postgres_sessions import PostgresSessionRepository
from app.infrastructure.db.postgres_users import PostgresUserRepository
from app.main import create_app
from app.services.account_service import AccountService
from app.services.session_service import ActiveSession, SessionService
from tests.account_helpers import fast_hasher
from tests.test_config import IsolatedSettings

ORIGIN = "http://localhost:3000"
EMAIL = "jane.doe@example.com"
PASSWORD = "correct horse battery staple"
FAKE_SESSION = ActiveSession(user_id=uuid.UUID(int=1), csrf_token="test-csrf")
LOGIN_WINDOW = 900
REGISTER_WINDOW = 3600


def build_auth_app(
    engine: Engine,
    *,
    registration_open: bool = True,
    login_per_address: int = 100,
    login_per_account: int = 100,
    register_limit: int = 100,
) -> FastAPI:
    """The real application with real accounts and sessions, on a test database."""
    settings = IsolatedSettings(cors_origins=ORIGIN, registration_open=registration_open)
    app = create_app(settings)
    accounts = AccountService(PostgresUserRepository(engine), fast_hasher())
    sessions = SessionService(PostgresSessionRepository(engine))
    throttle = LoginThrottle(
        RateLimiter(login_per_address, LOGIN_WINDOW), RateLimiter(login_per_account, LOGIN_WINDOW)
    )
    register_limiter = RateLimiter(register_limit, REGISTER_WINDOW)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_account_service] = lambda: accounts
    app.dependency_overrides[get_session_service] = lambda: sessions
    app.dependency_overrides[get_login_throttle] = lambda: throttle
    app.dependency_overrides[get_register_limiter] = lambda: register_limiter
    return app


def make_client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def post_json(
    client: TestClient,
    path: str,
    payload: object,
    *,
    origin: str | None = ORIGIN,
    csrf: str | None = None,
) -> httpx.Response:
    headers: dict[str, str] = {}
    if origin is not None:
        headers["Origin"] = origin
    if csrf is not None:
        headers["X-CSRF-Token"] = csrf
    response: httpx.Response = client.post(path, json=payload, headers=headers)
    return response


def register(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> httpx.Response:
    return post_json(client, "/auth/register", {"email": email, "password": password})


def login(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> httpx.Response:
    return post_json(client, "/auth/login", {"email": email, "password": password})


def sign_in(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> str:
    """Create the account if needed, log in, and return the CSRF token of the session."""
    register(client, email, password)
    response = login(client, email, password)
    assert response.status_code == 200, response.text
    csrf = response.json()["csrf_token"]
    assert isinstance(csrf, str)
    return csrf
