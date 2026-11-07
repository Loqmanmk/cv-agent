from typing import Any, NoReturn

import pytest
from google.genai import errors

from app.domain.cv import Language
from app.domain.llm import LLMUnavailableError
from app.infrastructure.gemini_provider import parse_retry_seconds
from tests.test_gemini_provider import failing_first, make_provider


def quota_error(**_kwargs: Any) -> NoReturn:
    raise errors.APIError(429, {"error": {"message": "Quota exceeded. Please retry in 1h30m."}})


def test_parses_hours_minutes_and_seconds() -> None:
    assert parse_retry_seconds("Please retry in 10h25m43.5s.") == pytest.approx(37543.5)


def test_parses_seconds_only() -> None:
    assert parse_retry_seconds("Please retry in 37s") == 37


def test_parses_minutes_only() -> None:
    assert parse_retry_seconds("Please retry in 2m.") == 120


def test_returns_none_without_a_hint() -> None:
    assert parse_retry_seconds("Quota exceeded, no hint here") is None


def test_a_quota_error_carries_the_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(monkeypatch, quota_error)

    with pytest.raises(LLMUnavailableError) as raised:
        provider.generate("system", "user", Language)

    assert raised.value.retry_after_seconds == 5400


def test_an_overload_error_has_no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(monkeypatch, failing_first(100, 503, {"calls": 0}))

    with pytest.raises(LLMUnavailableError) as raised:
        provider.generate("system", "user", Language)

    assert raised.value.retry_after_seconds is None
