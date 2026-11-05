import pytest

from app.domain.llm import LLMError
from app.infrastructure.fallback_llm_provider import FallbackLLMProvider
from app.infrastructure.llm_factory import build_gemini_chain
from tests.test_config import IsolatedSettings


def test_builds_a_fallback_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    assert isinstance(build_gemini_chain(IsolatedSettings()), FallbackLLMProvider)


def test_requires_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(LLMError):
        build_gemini_chain(IsolatedSettings())
