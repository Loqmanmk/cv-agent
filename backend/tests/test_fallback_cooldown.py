import pytest

from app.domain.cv import Language
from app.domain.llm import LLMUnavailableError
from app.infrastructure.fallback_llm_provider import DEFAULT_COOLDOWN_SECONDS, FallbackLLMProvider
from tests.fakes import FakeLLMProvider
from tests.test_fallback_llm_provider import ANSWER, RaisingProvider


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def call(provider: FallbackLLMProvider) -> Language:
    return provider.generate("s", "u", Language)


def test_a_model_without_quota_is_skipped_until_it_resets() -> None:
    clock = Clock()
    quota = RaisingProvider(LLMUnavailableError("quota", retry_after_seconds=3600))
    provider = FallbackLLMProvider([quota, FakeLLMProvider(ANSWER)], clock)

    call(provider)
    call(provider)
    assert quota.calls == 1

    clock.now = 3601
    call(provider)
    assert quota.calls == 2


def test_an_overloaded_model_is_skipped_for_a_short_time() -> None:
    clock = Clock()
    busy = RaisingProvider(LLMUnavailableError("busy"))
    provider = FallbackLLMProvider([busy, FakeLLMProvider(ANSWER)], clock)

    call(provider)
    clock.now = DEFAULT_COOLDOWN_SECONDS - 1
    call(provider)
    assert busy.calls == 1

    clock.now = DEFAULT_COOLDOWN_SECONDS + 1
    call(provider)
    assert busy.calls == 2


def test_the_error_reports_the_soonest_retry_when_everything_is_exhausted() -> None:
    clock = Clock()
    only = RaisingProvider(LLMUnavailableError("quota", retry_after_seconds=600))
    provider = FallbackLLMProvider([only], clock)

    with pytest.raises(LLMUnavailableError) as first:
        call(provider)
    assert first.value.retry_after_seconds == pytest.approx(600)

    clock.now = 100
    with pytest.raises(LLMUnavailableError) as second:
        call(provider)

    assert only.calls == 1
    assert "skipped" in str(second.value)
    assert second.value.retry_after_seconds == pytest.approx(500)


def test_every_model_of_the_chain_is_tried_in_order() -> None:
    clock = Clock()
    first = RaisingProvider(LLMUnavailableError("one down"))
    second = RaisingProvider(LLMUnavailableError("two down"))
    third = FakeLLMProvider(ANSWER)
    provider = FallbackLLMProvider([first, second, third], clock)

    assert call(provider) is ANSWER
    assert (first.calls, second.calls, len(third.calls)) == (1, 1, 1)
