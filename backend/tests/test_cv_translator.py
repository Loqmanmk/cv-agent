import pytest

from app.domain.cv import CV
from app.services.cv_translator import MAX_ATTEMPTS, CVTranslator
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.masking_llm_provider import MaskingLLMProvider
from app.services.translation_guard import TranslationViolationError
from tests.fakes import FakeLLMProvider, SequenceLLMProvider
from tests.test_tailoring_guard import make_cv
from tests.test_translation_guard import german


def not_translated() -> CV:
    return make_cv()


def test_returns_the_translated_cv() -> None:
    translated = german(make_cv())

    result = CVTranslator(FakeLLMProvider(translated)).translate(make_cv(), "de")

    assert result is translated


def test_the_prompt_names_the_language_and_tags_the_cv() -> None:
    provider = FakeLLMProvider(german(make_cv()))

    CVTranslator(provider).translate(make_cv(), "de")

    system_prompt, user_prompt = provider.calls[0]
    assert "German" in system_prompt
    assert "Western digits" in system_prompt
    assert user_prompt.startswith("<cv>")
    assert "<problems_to_fix>" not in user_prompt


def test_retries_with_the_violations_as_feedback() -> None:
    provider = SequenceLLMProvider([not_translated(), german(make_cv())])

    result = CVTranslator(provider).translate(make_cv(), "de")

    assert result == german(make_cv())
    assert "<problems_to_fix>" in provider.calls[1][1]
    assert "profile was not translated" in provider.calls[1][1]


def test_gives_up_after_the_maximum_attempts() -> None:
    provider = SequenceLLMProvider([not_translated()] * MAX_ATTEMPTS)

    with pytest.raises(TranslationViolationError) as raised:
        CVTranslator(provider).translate(make_cv(), "de")

    assert len(provider.calls) == MAX_ATTEMPTS
    assert "profile was not translated" in raised.value.violations


def test_an_unsupported_language_fails_before_calling_the_ai() -> None:
    provider = FakeLLMProvider(german(make_cv()))

    with pytest.raises(UnsupportedLetterLanguageError):
        CVTranslator(provider).translate(make_cv(), "other")

    assert provider.calls == []


def test_contact_details_are_hidden_from_the_ai_and_restored() -> None:
    cv = make_cv()
    masked = german(cv).model_copy(
        update={
            "header": german(cv).header.model_copy(
                update={"email": "[[EMAIL_1]]", "phone": "[[PHONE_1]]"}
            )
        }
    )
    inner = FakeLLMProvider(masked)

    result = CVTranslator(MaskingLLMProvider(inner)).translate(cv, "de")

    _, prompt_seen_by_ai = inner.calls[0]
    assert "jane@example.com" not in prompt_seen_by_ai
    assert "+00 000 000 000" not in prompt_seen_by_ai
    assert result.header.email == "jane@example.com"
    assert result.header.phone == "+00 000 000 000"
