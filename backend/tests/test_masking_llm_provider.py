from app.domain.cv import CV, Experience, Header
from app.services.cv_structurer import CVStructurer
from app.services.masking_llm_provider import MaskingLLMProvider
from tests.fakes import FakeLLMProvider


def masked_header() -> Header:
    return Header(
        name="Jane Doe",
        headline="Software Engineer",
        phone="[[PHONE_1]]",
        email="[[EMAIL_1]]",
    )


def test_inner_provider_never_sees_personal_data() -> None:
    inner = FakeLLMProvider(masked_header())

    MaskingLLMProvider(inner).generate("system", "Jane jane@example.com +33 6 12 34 56 78", Header)

    _, prompt = inner.calls[0]
    assert "jane@example.com" not in prompt
    assert "+33 6 12 34 56 78" not in prompt


def test_real_values_are_restored_in_the_answer() -> None:
    inner = FakeLLMProvider(masked_header())

    result = MaskingLLMProvider(inner).generate(
        "system", "Jane jane@example.com +33 6 12 34 56 78", Header
    )

    assert result.email == "jane@example.com"
    assert result.phone == "+33 6 12 34 56 78"


def test_values_are_restored_in_nested_fields() -> None:
    cv = CV(
        header=masked_header(),
        profile="Reach me at [[EMAIL_1]]",
        experiences=[
            Experience(
                title="Dev", company="Acme", start="2020", end="2021", bullets=["Mail [[EMAIL_1]]"]
            )
        ],
    )

    result = MaskingLLMProvider(FakeLLMProvider(cv)).generate(
        "system", "jane@example.com +33 6 12 34 56 78", CV
    )

    assert result.profile == "Reach me at jane@example.com"
    assert result.experiences[0].bullets == ["Mail jane@example.com"]


def test_system_prompt_is_not_changed() -> None:
    inner = FakeLLMProvider(masked_header())

    MaskingLLMProvider(inner).generate("keep me@this.com", "x", Header)

    assert inner.calls[0][0] == "keep me@this.com"


def test_structurer_still_passes_its_grounding_check() -> None:
    cv = CV(header=masked_header(), profile="Backend developer.")
    llm = MaskingLLMProvider(FakeLLMProvider(cv))
    raw_text = "Jane Doe\nSoftware Engineer\njane@example.com\n+33 6 12 34 56 78"

    result = CVStructurer(llm).structure(raw_text)

    assert result.header.email == "jane@example.com"
