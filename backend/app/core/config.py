from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables or the .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.6-flash"
    gemini_fallback_models: str = "gemini-3.5-flash,gemini-3.1-flash-lite"
    applicant_address: str = ""
    applicant_city: str = ""
    applicant_gender: Literal["m", "f"] = "m"
    cors_origins: str = "http://localhost:3000"
    rate_limit_per_hour: int = 10

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
