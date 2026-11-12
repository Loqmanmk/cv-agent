from functools import lru_cache

from pydantic import SecretStr

from app.api.auth_dependencies import SettingsDep, get_session_service
from app.api.database import get_engine
from app.api.rate_limit import RateLimiter
from app.infrastructure.db.postgres_oauth import PostgresOAuthIdentityRepository
from app.infrastructure.db.postgres_users import PostgresUserRepository
from app.infrastructure.google_oidc import GoogleOidcClient
from app.services.external_login import ExternalLoginService

GOOGLE_WINDOW_SECONDS = 900
GOOGLE_STEPS_PER_ADDRESS = 30


@lru_cache
def _google_client(client_id: str, client_secret: str, redirect_uri: str) -> GoogleOidcClient:
    """One client per configuration, so Google's public keys stay cached between sign-ins."""
    return GoogleOidcClient(client_id, SecretStr(client_secret), redirect_uri)


def get_google_client(settings: SettingsDep) -> GoogleOidcClient | None:
    """Google sign-in, or None when this server has no Google client configured."""
    secret = settings.google_client_secret
    if not settings.google_client_id or secret is None or not secret.get_secret_value():
        return None
    return _google_client(
        settings.google_client_id, secret.get_secret_value(), settings.google_redirect_uri
    )


@lru_cache
def get_external_login_service() -> ExternalLoginService:
    engine = get_engine()
    return ExternalLoginService(
        PostgresUserRepository(engine),
        PostgresOAuthIdentityRepository(engine),
        get_session_service(),
    )


@lru_cache
def get_google_limiter() -> RateLimiter:
    """Each sign-in uses two steps (start and callback) from the same address."""
    return RateLimiter(GOOGLE_STEPS_PER_ADDRESS, GOOGLE_WINDOW_SECONDS)
