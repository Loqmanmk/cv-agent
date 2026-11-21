from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables or the .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.6-flash"
    gemini_fallback_models: str = (
        "gemini-3.5-flash,gemini-3.7-flash,gemini-3.8-flash,gemini-3-flash-preview,"
        "gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-flash-lite-latest,"
        "gemini-3.1-flash-lite-preview"
    )
    groq_api_key: SecretStr | None = None
    groq_models: str = "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b"
    cors_origins: str = "http://localhost:3000"
    rate_limit_per_hour: int = 10
    render_rate_limit_per_hour: int = 60
    fetch_rate_limit_per_hour: int = 30
    hsts_enabled: bool = False
    database_url: SecretStr | None = None
    cookie_secure: bool = False
    registration_open: bool = False
    email_outbox_dir: str = "../data/outbox"
    email_backend: str = "outbox"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: str = "starttls"
    smtp_username: str = ""
    smtp_password: SecretStr | None = None
    email_from_address: str = ""
    email_from_name: str = "CV Agent"
    app_base_url: str = "http://localhost:3000"
    google_client_id: str = ""
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    @property
    def gemini_model_chain(self) -> list[str]:
        """The main model first, then the fallbacks, without duplicates."""
        names = [self.gemini_model, *self.gemini_fallback_models.split(",")]
        return list(dict.fromkeys(name.strip() for name in names if name.strip()))

    @property
    def groq_model_list(self) -> list[str]:
        names = self.groq_models.split(",")
        return list(dict.fromkeys(name.strip() for name in names if name.strip()))

    @property
    def session_cookie_name(self) -> str:
        """The __Host- prefix makes browsers refuse a cookie that is not Secure."""
        return "__Host-session" if self.cookie_secure else "session"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
