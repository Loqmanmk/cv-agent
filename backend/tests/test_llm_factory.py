import pytest
from pydantic import SecretStr

from app.domain.llm import LLMError, LLMProvider
from app.infrastructure.fallback_llm_provider import FallbackLLMProvider
from app.infrastructure.gemini_provider import GeminiProvider
from app.infrastructure.groq_provider import GroqProvider
from app.infrastructure.llm_factory import build_llm_chain
from tests.test_config import IsolatedSettings


def kinds(chain: LLMProvider) -> list[type]:
    assert isinstance(chain, FallbackLLMProvider)
    return [type(provider) for provider in chain._providers]


def test_gemini_comes_first_then_groq() -> None:
    settings = IsolatedSettings(
        gemini_api_key=SecretStr("gemini-key"),
        gemini_model="a",
        gemini_fallback_models="b",
        groq_api_key=SecretStr("groq-key"),
        groq_models="x, y ,x",
    )

    assert kinds(build_llm_chain(settings)) == [
        GeminiProvider,
        GeminiProvider,
        GroqProvider,
        GroqProvider,
    ]


def test_groq_alone_is_enough() -> None:
    settings = IsolatedSettings(gemini_api_key=None, groq_api_key=SecretStr("groq-key"))

    assert set(kinds(build_llm_chain(settings))) == {GroqProvider}


def test_gemini_alone_still_works() -> None:
    settings = IsolatedSettings(gemini_api_key=SecretStr("gemini-key"), groq_api_key=None)

    assert set(kinds(build_llm_chain(settings))) == {GeminiProvider}


@pytest.mark.parametrize("empty", [None, SecretStr("")])
def test_at_least_one_key_is_required(empty: SecretStr | None) -> None:
    settings = IsolatedSettings(gemini_api_key=empty, groq_api_key=empty)

    with pytest.raises(LLMError, match="GEMINI_API_KEY or GROQ_API_KEY"):
        build_llm_chain(settings)
