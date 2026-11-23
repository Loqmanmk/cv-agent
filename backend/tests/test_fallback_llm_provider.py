import pytest
from pydantic import BaseModel

from app.domain.cv import Language
from app.domain.llm import LLMError, LLMProvider, LLMUnavailableError
from app.infrastructure.fallback_llm_provider import FallbackLLMProvider
from tests.fakes import FakeLLMProvider

ANSWER = Language(name="French", level="Native")


class RaisingProvider(LLMProvider):
    def __init__(self, error: LLMError) -> None:
        self._error = error
        self.calls = 0

    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        self.calls += 1
        raise self._error


def test_uses_the_next_provider_when_one_is_unavailable() -> None:
    down = RaisingProvider(LLMUnavailableError("down"))

    result = FallbackLLMProvider([down, FakeLLMProvider(ANSWER)]).generate("s", "u", Language)

    assert result is ANSWER
    assert down.calls == 1


def test_stops_at_the_first_success() -> None:
    down = RaisingProvider(LLMUnavailableError("down"))

    FallbackLLMProvider([FakeLLMProvider(ANSWER), down]).generate("s", "u", Language)

    assert down.calls == 0


def test_a_malformed_answer_moves_on_to_the_next_provider() -> None:
    bad = RaisingProvider(LLMError("unexpected structure"))
    spare = FakeLLMProvider(ANSWER)

    assert FallbackLLMProvider([bad, spare]).generate("s", "u", Language) == ANSWER
    assert len(spare.calls) == 1


def test_raises_the_error_itself_when_every_provider_answered_badly() -> None:
    providers = [RaisingProvider(LLMError("first bad")), RaisingProvider(LLMError("second bad"))]

    with pytest.raises(LLMError) as raised:
        FallbackLLMProvider(providers).generate("s", "u", Language)

    assert not isinstance(raised.value, LLMUnavailableError)


def test_a_mix_of_busy_and_bad_providers_counts_as_busy() -> None:
    providers = [
        RaisingProvider(LLMUnavailableError("busy")),
        RaisingProvider(LLMError("bad")),
    ]

    with pytest.raises(LLMUnavailableError, match="busy.*bad"):
        FallbackLLMProvider(providers).generate("s", "u", Language)


def test_raises_with_every_reason_when_all_are_unavailable() -> None:
    providers = [
        RaisingProvider(LLMUnavailableError("first down")),
        RaisingProvider(LLMUnavailableError("second down")),
    ]

    with pytest.raises(LLMUnavailableError) as raised:
        FallbackLLMProvider(providers).generate("s", "u", Language)

    assert "first down" in str(raised.value)
    assert "second down" in str(raised.value)


def test_the_provider_that_answered_last_is_tried_first() -> None:
    clock = iter(range(0, 10_000, 1000))  # each call is 1000 s later: every cooldown is over
    down = RaisingProvider(LLMUnavailableError("busy"))
    spare = FakeLLMProvider(ANSWER)
    chain = FallbackLLMProvider([down, spare], clock=lambda: float(next(clock)))

    chain.generate("s", "u", Language)
    chain.generate("s", "u", Language)

    assert down.calls == 1
    assert len(spare.calls) == 2


class AnswersOnceProvider(LLMProvider):
    """Answers the first call, then is out of quota."""

    def __init__(self) -> None:
        self.calls = 0

    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        self.calls += 1
        if self.calls > 1:
            raise LLMUnavailableError("out of quota now")
        return response_model.model_validate(ANSWER.model_dump())


def test_the_usual_order_comes_back_when_the_last_good_provider_fails() -> None:
    clock = iter(range(0, 10_000, 1000))
    first = RaisingProvider(LLMUnavailableError("busy"))
    second = AnswersOnceProvider()
    third = FakeLLMProvider(ANSWER)
    chain = FallbackLLMProvider([first, second, third], clock=lambda: float(next(clock)))

    chain.generate("s", "u", Language)  # first is busy, second answers
    chain.generate("s", "u", Language)  # second fails: first, then third

    assert (first.calls, second.calls, len(third.calls)) == (2, 2, 1)


def test_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="At least one provider"):
        FallbackLLMProvider([])
