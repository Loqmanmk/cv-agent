import pytest
from pydantic import ValidationError
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


def test_model_chain_has_the_main_model_first_without_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_MODEL", "model-a")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "model-b, model-a ,model-c")

    assert IsolatedSettings().gemini_model_chain == ["model-a", "model-b", "model-c"]


def test_gender_must_be_m_or_f(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICANT_GENDER", "x")

    with pytest.raises(ValidationError):
        IsolatedSettings()


def test_cv_language_defaults_to_french_and_is_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPLICANT_CV_LANGUAGE", raising=False)
    assert IsolatedSettings().applicant_cv_language == "fr"

    monkeypatch.setenv("APPLICANT_CV_LANGUAGE", "xx")
    with pytest.raises(ValidationError):
        IsolatedSettings()
