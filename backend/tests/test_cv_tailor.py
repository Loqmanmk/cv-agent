import pytest

from app.domain.cv import CV, SkillGroup
from app.domain.job import JobOffer
from app.services.cv_tailor import (
    MAX_ATTEMPTS,
    MAX_HEADLINE_CHARS,
    CVTailor,
    headline_from_title,
)
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

    assert result.skills == make_cv().skills
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


def test_the_headline_becomes_the_job_title_of_the_offer() -> None:
    result = CVTailor(FakeLLMProvider(make_cv())).tailor(make_cv(), make_offer())

    assert result.header.headline == "Python Developer"


def test_an_offer_without_a_title_keeps_the_headline_of_the_ai() -> None:
    offer = make_offer().model_copy(update={"title": "  "})

    result = CVTailor(FakeLLMProvider(make_cv())).tailor(make_cv(), offer)

    assert result.header.headline == make_cv().header.headline


def test_a_title_with_numbers_does_not_break_the_number_check() -> None:
    offer = make_offer().model_copy(update={"title": "Java 21 Developer"})
    provider = FakeLLMProvider(make_cv())

    result = CVTailor(provider).tailor(make_cv(), offer)

    assert result.header.headline == "Java 21 Developer"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Stagiaire DataLab (H/F)", "Stagiaire DataLab"),
        ("Data Scientist - F/H", "Data Scientist"),
        ("Softwareentwickler (m/w/d)", "Softwareentwickler"),
        ("Backend Engineer [f/m/d] - Berlin", "Backend Engineer - Berlin"),
        ("Product Designer (all genders)", "Product Designer"),
        ("  Ingénieur   DevOps  ", "Ingénieur DevOps"),
        ("مهندس برمجيات", "مهندس برمجيات"),
        ("Head of Machine Learning", "Head of Machine Learning"),
    ],
)
def test_the_job_title_is_cleaned_for_a_cv(title: str, expected: str) -> None:
    assert headline_from_title(title) == expected


def test_a_very_long_title_is_cut_between_two_words() -> None:
    headline = headline_from_title("Engineer " * 20)

    assert len(headline) <= MAX_HEADLINE_CHARS
    assert headline.endswith("Engineer")


def offer_with_keywords(keywords: list[str]) -> JobOffer:
    return JobOffer(
        title="Developer",
        company="Acme",
        language="en",
        contract_type="full_time",
        keywords=keywords,
    )


def test_dropping_a_more_relevant_project_is_rejected() -> None:
    original = make_cv()
    wrong = original.model_copy(update={"projects": [original.projects[0]]})
    provider = SequenceLLMProvider([wrong, original])

    result = CVTailor(provider).tailor(original, offer_with_keywords(["Spring Boot"]))

    assert result.projects == original.projects
    assert "fits the offer better" in provider.calls[1][1]


def test_dropping_a_less_relevant_project_is_allowed() -> None:
    original = make_cv()
    right = original.model_copy(update={"projects": [original.projects[1]]})
    provider = FakeLLMProvider(right)

    result = CVTailor(provider).tailor(original, offer_with_keywords(["Spring Boot"]))

    assert [project.title for project in result.projects] == ["Committed"]
    assert len(provider.calls) == 1
