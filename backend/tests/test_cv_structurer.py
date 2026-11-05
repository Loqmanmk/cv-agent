import pytest

from app.domain.cv import CV, Header
from app.services.cv_structurer import CVStructurer, CVStructuringError
from tests.fakes import FakeLLMProvider

RAW_TEXT = "Jane Doe\nSoftware Engineer\nJane@Example.com\n+00 000 000 000"


def make_cv(email: str = "jane@example.com") -> CV:
    header = Header(
        name="Jane Doe",
        headline="Software Engineer",
        phone="+00 000 000 000",
        email=email,
    )
    return CV(header=header, profile="Backend developer.")


def test_returns_the_cv_built_by_the_provider() -> None:
    cv = make_cv()

    result = CVStructurer(FakeLLMProvider(cv)).structure(RAW_TEXT)

    assert result is cv


def test_sends_the_cv_text_inside_tags() -> None:
    provider = FakeLLMProvider(make_cv())

    CVStructurer(provider).structure(RAW_TEXT)

    _, user_prompt = provider.calls[0]
    assert user_prompt.startswith("<cv_text>")
    assert RAW_TEXT in user_prompt


def test_rejects_empty_text() -> None:
    with pytest.raises(CVStructuringError):
        CVStructurer(FakeLLMProvider(make_cv())).structure("   \n ")


def test_rejects_an_email_that_is_not_in_the_text() -> None:
    provider = FakeLLMProvider(make_cv(email="invented@fake.com"))

    with pytest.raises(CVStructuringError):
        CVStructurer(provider).structure(RAW_TEXT)


def test_email_check_ignores_letter_case() -> None:
    provider = FakeLLMProvider(make_cv(email="JANE@EXAMPLE.COM"))

    assert CVStructurer(provider).structure(RAW_TEXT).header.email == "JANE@EXAMPLE.COM"
