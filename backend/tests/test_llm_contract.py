import pytest

from app.domain.cv import Header
from app.domain.llm import LLMError, LLMProvider
from tests.fakes import FakeLLMProvider


def make_header() -> Header:
    return Header(
        name="Jane Doe",
        headline="Software Engineer",
        phone="+00 000 000 000",
        email="jane@example.com",
    )


def test_interface_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


def test_provider_returns_the_requested_model() -> None:
    header = make_header()
    provider = FakeLLMProvider(header)

    result = provider.generate("system", "user", Header)

    assert result is header


def test_provider_records_the_prompts() -> None:
    provider = FakeLLMProvider(make_header())

    provider.generate("system text", "user text", Header)

    assert provider.calls == [("system text", "user text")]


def test_wrong_model_raises_llm_error() -> None:
    from app.domain.cv import Language

    provider = FakeLLMProvider(make_header())

    with pytest.raises(LLMError):
        provider.generate("system", "user", Language)
