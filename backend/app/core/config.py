from functools import lru_cache
from typing import Literal

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
    applicant_address: str = ""
    applicant_city: str = ""
    applicant_gender: Literal["m", "f"] = "m"
    applicant_cv_language: Literal["fr", "de", "en", "ar"] = "fr"
    cors_origins: str = "http://localhost:3000"
    rate_limit_per_hour: int = 10
    render_rate_limit_per_hour: int = 60
    fetch_rate_limit_per_hour: int = 30
    tracker_db_path: str = "../data/tracker.db"
    hsts_enabled: bool = False
    database_url: SecretStr | None = None

    @property
    def gemini_model_chain(self) -> list[str]:
        """The main model first, then the fallbacks, without duplicates."""
        names = [self.gemini_model, *self.gemini_fallback_models.split(",")]
        return list(dict.fromkeys(name.strip() for name in names if name.strip()))

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
