import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, NoReturn

import httpx
import pytest
from google import genai
from google.genai import errors, types
from pydantic import SecretStr

from app.domain.cv import Language
from app.domain.llm import LLMError, LLMUnavailableError
from app.infrastructure.gemini_provider import MAX_ATTEMPTS, MAX_OVERLOADED_ATTEMPTS, GeminiProvider

API_KEY = "test-key"
VALID_ANSWER = '{"name": "French", "level": "Native"}'


def make_provider(
    monkeypatch: pytest.MonkeyPatch,
    behavior: Callable[..., Any],
) -> GeminiProvider:
    client = genai.Client(api_key=API_KEY)
    monkeypatch.setattr(client.models, "generate_content", behavior)
    return GeminiProvider(SecretStr(API_KEY), "test-model", client, sleep=lambda _: None)


def answering(text: str | None, calls: list[dict[str, Any]] | None = None) -> Callable[..., Any]:
    def generate_content(**kwargs: Any) -> SimpleNamespace:
        if calls is not None:
            calls.append(kwargs)
        return SimpleNamespace(text=text)

    return generate_content


def failing_first(
    failures: int,
    code: int,
    state: dict[str, int],
) -> Callable[..., Any]:
    def generate_content(**_kwargs: Any) -> SimpleNamespace:
        state["calls"] += 1
        if state["calls"] <= failures:
            raise errors.APIError(code, {"error": {"message": "failure"}})
        return SimpleNamespace(text=VALID_ANSWER)

    return generate_content


def unreachable(**_kwargs: Any) -> NoReturn:
    raise httpx.ConnectError("getaddrinfo failed")


def test_returns_the_validated_model(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(monkeypatch, answering(VALID_ANSWER))

    assert provider.generate("system", "user", Language) == Language(name="French", level="Native")


def test_sends_model_prompts_and_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    provider = make_provider(monkeypatch, answering(VALID_ANSWER, calls))

    provider.generate("system text", "user text", Language)

    config = calls[0]["config"]
    assert calls[0]["model"] == "test-model"
    assert calls[0]["contents"] == "user text"
    assert config.system_instruction == "system text"
    assert "name" in config.response_json_schema["properties"]
    assert "additionalProperties" not in json.dumps(config.response_json_schema)


def test_unknown_fields_are_still_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = '{"name": "French", "level": "Native", "invented": "x"}'
    provider = make_provider(monkeypatch, answering(answer))

    with pytest.raises(LLMError):
        provider.generate("system", "user", Language)


def test_empty_answer_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(monkeypatch, answering(None))

    with pytest.raises(LLMError):
        provider.generate("system", "user", Language)


def test_invalid_json_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(monkeypatch, answering("not json"))

    with pytest.raises(LLMError):
        provider.generate("system", "user", Language)


def test_an_overloaded_model_is_left_quickly_for_the_next_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"calls": 0}
    provider = make_provider(monkeypatch, failing_first(100, 503, state))

    with pytest.raises(LLMUnavailableError) as raised:
        provider.generate("system", "user", Language)

    assert "503" in str(raised.value)
    assert API_KEY not in str(raised.value)
    assert state["calls"] == MAX_OVERLOADED_ATTEMPTS == 1


def test_a_server_error_is_retried_more_times(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"calls": 0}
    provider = make_provider(monkeypatch, failing_first(100, 500, state))

    with pytest.raises(LLMError):
        provider.generate("system", "user", Language)

    assert state["calls"] == MAX_ATTEMPTS


def test_does_not_retry_a_bad_request(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"calls": 0}
    provider = make_provider(monkeypatch, failing_first(100, 400, state))

    with pytest.raises(LLMError):
        provider.generate("system", "user", Language)

    assert state["calls"] == 1


def test_network_error_becomes_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(monkeypatch, unreachable)

    with pytest.raises(LLMError):
        provider.generate("system", "user", Language)


def test_quota_error_is_not_retried_and_is_marked_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"calls": 0}
    provider = make_provider(monkeypatch, failing_first(100, 429, state))

    with pytest.raises(LLMUnavailableError):
        provider.generate("system", "user", Language)

    assert state["calls"] == 1


def test_bad_request_is_not_marked_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"calls": 0}
    provider = make_provider(monkeypatch, failing_first(100, 400, state))

    with pytest.raises(LLMError) as raised:
        provider.generate("system", "user", Language)

    assert not isinstance(raised.value, LLMUnavailableError)


def test_network_error_is_marked_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(monkeypatch, unreachable)

    with pytest.raises(LLMUnavailableError):
        provider.generate("system", "user", Language)


def too_slow(**_kwargs: Any) -> NoReturn:
    raise httpx.ReadTimeout("timed out")


def test_a_model_that_does_not_answer_in_time_is_left_for_the_next_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(monkeypatch, too_slow)

    with pytest.raises(LLMUnavailableError, match="no answer within 75 s"):
        provider.generate("system", "user", Language)


def test_the_client_gives_up_a_call_after_the_time_limit() -> None:
    provider = GeminiProvider(SecretStr(API_KEY), "gemini-3-flash-preview", timeout_seconds=12.5)

    options = provider._client._api_client._http_options

    assert options.timeout == 12_500


def thinking_of(monkeypatch: pytest.MonkeyPatch, model: str) -> Any:
    calls: list[dict[str, Any]] = []
    client = genai.Client(api_key=API_KEY)
    monkeypatch.setattr(client.models, "generate_content", answering(VALID_ANSWER, calls))
    GeminiProvider(SecretStr(API_KEY), model, client).generate("s", "u", Language)
    return calls[0]["config"].thinking_config


def test_gemini_3_models_think_at_the_low_level_to_answer_faster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thinking = thinking_of(monkeypatch, "gemini-3.7-flash")

    assert thinking.thinking_level == types.ThinkingLevel.LOW


def test_older_models_keep_their_own_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    assert thinking_of(monkeypatch, "gemini-2.5-flash") is None
