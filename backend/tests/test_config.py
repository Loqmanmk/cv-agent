import pytest
from pydantic_settings import SettingsConfigDict

from app.core.config import Settings


class IsolatedSettings(Settings):
    """Settings that never read the real .env file, so tests behave the same everywhere."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")


def test_key_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    settings = IsolatedSettings()

    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "test-key"


def test_key_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert IsolatedSettings().gemini_api_key is None


def test_key_is_hidden_when_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    assert "test-key" not in repr(IsolatedSettings())
