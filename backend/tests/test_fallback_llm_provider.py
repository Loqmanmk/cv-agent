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


def test_does_not_fall_back_on_a_bad_request() -> None:
    bad = RaisingProvider(LLMError("bad request"))
    spare = FakeLLMProvider(ANSWER)

    with pytest.raises(LLMError) as raised:
        FallbackLLMProvider([bad, spare]).generate("s", "u", Language)

    assert not isinstance(raised.value, LLMUnavailableError)
    assert spare.calls == []


def test_raises_with_every_reason_when_all_are_unavailable() -> None:
    providers = [
        RaisingProvider(LLMUnavailableError("first down")),
        RaisingProvider(LLMUnavailableError("second down")),
    ]

    with pytest.raises(LLMUnavailableError) as raised:
        FallbackLLMProvider(providers).generate("s", "u", Language)

    assert "first down" in str(raised.value)
    assert "second down" in str(raised.value)


def test_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="At least one provider"):
        FallbackLLMProvider([])
