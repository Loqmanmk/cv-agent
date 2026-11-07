import pytest

from app.domain.job import JobOffer, OfferLanguage
from app.domain.letter import LetterBody
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.letter_guard import MAX_WORDS, LetterViolationError
from app.services.letter_writer import MAX_ATTEMPTS, LetterWriter
from tests.fakes import FakeLLMProvider, SequenceLLMProvider
from tests.test_letter_guard import make_body
from tests.test_tailoring_guard import make_cv


def make_offer(language: OfferLanguage = "fr") -> JobOffer:
    return JobOffer(
        title="Stagiaire DataLab",
        company="Acme",
        language=language,
        contract_type="internship",
    )


def bad_body() -> LetterBody:
    return make_body(opening="[nom du poste]")


def test_returns_the_body_when_it_passes_the_guard() -> None:
    body = make_body()

    result = LetterWriter(FakeLLMProvider(body)).write(make_cv(), make_offer(), "m")

    assert result is body


def test_prompt_contains_the_data_and_the_gender_agreement() -> None:
    provider = FakeLLMProvider(make_body())

    LetterWriter(provider).write(make_cv(), make_offer(), "f")

    system_prompt, user_prompt = provider.calls[0]
    assert "in French" in system_prompt
    assert "<cv>" in user_prompt
    assert "Stagiaire DataLab" in user_prompt
    assert "feminine" in user_prompt


def test_retries_with_the_violations_as_feedback() -> None:
    provider = SequenceLLMProvider([bad_body(), make_body()])

    result = LetterWriter(provider).write(make_cv(), make_offer(), "m")

    assert result == make_body()
    assert "<problems_to_fix>" in provider.calls[1][1]
    assert "placeholder" in provider.calls[1][1]


def test_gives_up_after_the_maximum_attempts() -> None:
    provider = SequenceLLMProvider([bad_body()] * MAX_ATTEMPTS)

    with pytest.raises(LetterViolationError):
        LetterWriter(provider).write(make_cv(), make_offer(), "m")

    assert len(provider.calls) == MAX_ATTEMPTS
    assert MAX_WORDS > 0


@pytest.mark.parametrize("language", ["other"])
def test_unsupported_language_fails_before_calling_the_ai(language: OfferLanguage) -> None:
    provider = FakeLLMProvider(make_body())

    with pytest.raises(UnsupportedLetterLanguageError):
        LetterWriter(provider).write(make_cv(), make_offer(language), "m")

    assert provider.calls == []


def test_prompt_asks_for_duration_attribution_and_honest_verbs() -> None:
    provider = FakeLLMProvider(make_body())

    LetterWriter(provider).write(make_cv(), make_offer(), "m")

    system_prompt, _ = provider.calls[0]
    assert "target_line" in system_prompt
    assert "exact place" in system_prompt
    assert "discover" in system_prompt


def test_company_summary_reaches_the_prompt() -> None:
    offer = make_offer().model_copy(update={"company_summary": "Acme insures trade credit."})
    provider = FakeLLMProvider(make_body())

    LetterWriter(provider).write(make_cv(), offer, "m")

    system_prompt, user_prompt = provider.calls[0]
    assert "company_summary" in system_prompt
    assert "Acme insures trade credit." in user_prompt


def test_prompt_names_the_language_and_asks_for_western_digits() -> None:
    provider = FakeLLMProvider(make_body())

    LetterWriter(provider).write(make_cv(), make_offer("ar"), "m")

    system_prompt, _ = provider.calls[0]
    assert "Modern Standard Arabic" in system_prompt
    assert "Western digits" in system_prompt
