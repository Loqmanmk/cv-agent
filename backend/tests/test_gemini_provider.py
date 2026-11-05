from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest
from google import genai
from google.genai import errors
from pydantic import SecretStr

from app.domain.cv import Language
from app.domain.llm import LLMError
from app.infrastructure.gemini_provider import GeminiProvider

API_KEY = "test-key"


def make_provider(
    monkeypatch: pytest.MonkeyPatch,
    behavior: Callable[..., Any],
) -> GeminiProvider:
    client = genai.Client(api_key=API_KEY)
    monkeypatch.setattr(client.models, "generate_content", behavior)
    return GeminiProvider(SecretStr(API_KEY), "test-model", client)


def answering(text: str | None, calls: list[dict[str, Any]] | None = None) -> Callable[..., Any]:
    def generate_content(**kwargs: Any) -> SimpleNamespace:
        if calls is not None:
            calls.append(kwargs)
        return SimpleNamespace(text=text)

    return generate_content


def failing(**_kwargs: Any) -> NoReturn:
    raise errors.APIError(429, {"error": {"message": "quota exceeded"}})


def test_returns_the_validated_model(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(monkeypatch, answering('{"name": "French", "level": "Native"}'))

    result = provider.generate("system", "user", Language)

    assert result == Language(name="French", level="Native")


def test_sends_model_prompts_and_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    provider = make_provider(monkeypatch, answering('{"name": "A", "level": "B"}', calls))

    provider.generate("system text", "user text", Language)

    assert calls[0]["model"] == "test-model"
    assert calls[0]["contents"] == "user text"
    assert calls[0]["config"].system_instruction == "system text"
    assert calls[0]["config"].response_schema is Language


def test_empty_answer_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(monkeypatch, answering(None))

    with pytest.raises(LLMError):
        provider.generate("system", "user", Language)


def test_answer_with_wrong_structure_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(monkeypatch, answering('{"unexpected": 1}'))

    with pytest.raises(LLMError):
        provider.generate("system", "user", Language)


def test_invalid_json_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(monkeypatch, answering("not json"))

    with pytest.raises(LLMError):
        provider.generate("system", "user", Language)


def test_api_error_becomes_llm_error_without_leaking_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(monkeypatch, failing)

    with pytest.raises(LLMError) as raised:
        provider.generate("system", "user", Language)

    assert "429" in str(raised.value)
    assert API_KEY not in str(raised.value)
