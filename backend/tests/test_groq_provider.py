import json
from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr

from app.domain.cv import Language
from app.domain.llm import LLMError, LLMUnavailableError
from app.infrastructure.groq_provider import (
    API_URL,
    BAD_ANSWER_PAUSE,
    GONE_PAUSE,
    TOO_LARGE_PAUSE,
    GroqProvider,
)

API_KEY = "gsk_test-key"
VALID = '{"name": "French", "level": "Native"}'


def make_provider(handler: Callable[[httpx.Request], httpx.Response]) -> GroqProvider:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return GroqProvider(SecretStr(API_KEY), "openai/gpt-oss-120b", http)


def answer(content: object) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def error(status: int, message: str = "", code: str = "", retry_after: str = "") -> httpx.Response:
    headers = {"retry-after": retry_after} if retry_after else {}
    body = {"error": {"message": message, "code": code}}
    return httpx.Response(status, json=body, headers=headers)


def test_a_valid_answer_is_returned_as_the_expected_model() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return answer(VALID)

    result = make_provider(handler).generate("system", "user", Language)

    assert result == Language(name="French", level="Native")
    sent = json.loads(requests[0].content)
    assert str(requests[0].url) == API_URL
    assert requests[0].headers["authorization"] == f"Bearer {API_KEY}"
    assert sent["model"] == "openai/gpt-oss-120b"
    assert [message["role"] for message in sent["messages"]] == ["system", "user"]
    assert sent["response_format"]["json_schema"]["schema"] == Language.model_json_schema()


@pytest.mark.parametrize("status", [429, 498, 500, 502, 503, 504])
def test_a_busy_or_limited_model_lets_the_next_one_answer(status: int) -> None:
    provider = make_provider(lambda _: error(status, "busy", retry_after="7"))

    with pytest.raises(LLMUnavailableError) as raised:
        provider.generate("system", "user", Language)

    assert raised.value.retry_after_seconds == 7.0
    assert API_KEY not in str(raised.value)


@pytest.mark.parametrize(
    ("response", "pause"),
    [
        (error(413, "Request too large"), TOO_LARGE_PAUSE),
        (error(404, "The model has been decommissioned"), GONE_PAUSE),
        (error(400, "Failed to generate JSON", code="json_validate_failed"), BAD_ANSWER_PAUSE),
        (answer('{"name": 3}'), BAD_ANSWER_PAUSE),
        (answer(""), BAD_ANSWER_PAUSE),
        (httpx.Response(200, json={"unexpected": True}), BAD_ANSWER_PAUSE),
    ],
    ids=["too-large", "retired", "invalid-json", "wrong-structure", "empty", "unreadable"],
)
def test_a_problem_of_this_model_moves_to_the_next_one(
    response: httpx.Response, pause: float
) -> None:
    with pytest.raises(LLMUnavailableError) as raised:
        make_provider(lambda _: response).generate("system", "user", Language)

    assert raised.value.retry_after_seconds == pause


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_key_is_reported_without_the_key(status: int) -> None:
    with pytest.raises(LLMError, match="GROQ_API_KEY") as raised:
        make_provider(lambda _: error(status, "Invalid API Key")).generate("s", "u", Language)

    assert not isinstance(raised.value, LLMUnavailableError)
    assert API_KEY not in str(raised.value)


def test_a_network_error_lets_the_next_model_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(LLMUnavailableError, match="network error"):
        make_provider(handler).generate("system", "user", Language)


def test_another_bad_request_is_a_plain_error() -> None:
    with pytest.raises(LLMError) as raised:
        make_provider(lambda _: error(400, "bad parameter")).generate("s", "u", Language)

    assert not isinstance(raised.value, LLMUnavailableError)
