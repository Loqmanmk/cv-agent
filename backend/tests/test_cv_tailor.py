import pytest

from app.domain.cv import CV, SkillGroup
from app.domain.job import JobOffer
from app.services.cv_tailor import MAX_ATTEMPTS, CVTailor
from app.services.masking_llm_provider import MaskingLLMProvider
from app.services.tailoring_guard import TailoringViolationError
from tests.fakes import FakeLLMProvider, SequenceLLMProvider
from tests.test_tailoring_guard import make_cv


def make_offer() -> JobOffer:
    return JobOffer(
        title="Python Developer",
        company="Acme",
        language="en",
        contract_type="full_time",
        keywords=["Python"],
    )


def with_invented_skill() -> CV:
    skills = [SkillGroup(category="Back-end", items=["Python", "Kubernetes"])]
    return make_cv().model_copy(update={"skills": skills})


def test_returns_the_tailored_cv_when_it_is_faithful() -> None:
    tailored = make_cv().model_copy(update={"profile": "Rewritten profile."})

    result = CVTailor(FakeLLMProvider(tailored)).tailor(make_cv(), make_offer())

    assert result.profile == "Rewritten profile."


def test_sends_the_cv_and_the_offer_as_tagged_data() -> None:
    provider = FakeLLMProvider(make_cv())

    CVTailor(provider).tailor(make_cv(), make_offer())

    _, user_prompt = provider.calls[0]
    assert "<cv>" in user_prompt
    assert "<job_offer>" in user_prompt
    assert "Python Developer" in user_prompt
    assert "<problems_to_fix>" not in user_prompt


def test_asks_only_once_when_the_first_answer_is_faithful() -> None:
    provider = FakeLLMProvider(make_cv())

    CVTailor(provider).tailor(make_cv(), make_offer())

    assert len(provider.calls) == 1


def test_retries_with_the_violations_as_feedback() -> None:
    provider = SequenceLLMProvider([with_invented_skill(), make_cv()])

    result = CVTailor(provider).tailor(make_cv(), make_offer())

    assert result == make_cv()
    assert len(provider.calls) == 2
    assert "Kubernetes" not in provider.calls[0][1]
    assert "<problems_to_fix>" in provider.calls[1][1]
    assert "Kubernetes" in provider.calls[1][1]


def test_gives_up_after_the_maximum_attempts() -> None:
    provider = SequenceLLMProvider([with_invented_skill()] * MAX_ATTEMPTS)

    with pytest.raises(TailoringViolationError) as raised:
        CVTailor(provider).tailor(make_cv(), make_offer())

    assert len(provider.calls) == MAX_ATTEMPTS
    assert "Kubernetes" in str(raised.value)


def test_contact_details_are_hidden_from_the_ai_and_restored() -> None:
    masked_header = make_cv().header.model_copy(
        update={"email": "[[EMAIL_1]]", "phone": "[[PHONE_1]]"}
    )
    ai_answer = make_cv().model_copy(update={"header": masked_header})
    inner = FakeLLMProvider(ai_answer)

    result = CVTailor(MaskingLLMProvider(inner)).tailor(make_cv(), make_offer())

    _, prompt_seen_by_ai = inner.calls[0]
    assert "jane@example.com" not in prompt_seen_by_ai
    assert "+00 000 000 000" not in prompt_seen_by_ai
    assert result.header.email == "jane@example.com"
    assert result.header.phone == "+00 000 000 000"
