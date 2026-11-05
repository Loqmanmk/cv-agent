import pytest

from app.domain.job import JobOffer
from app.services.job_analyzer import MAX_CHARS, JobAnalysisError, JobAnalyzer
from tests.fakes import FakeLLMProvider

OFFER_TEXT = "Acme seeks a Python developer. Experience with FastAPI and Docker. Kubernetes a plus."


def make_offer(
    required: list[str] | None = None,
    nice: list[str] | None = None,
    keywords: list[str] | None = None,
    missions: list[str] | None = None,
) -> JobOffer:
    return JobOffer(
        title="Python Developer",
        company="Acme",
        language="en",
        contract_type="full_time",
        required_skills=required or [],
        nice_to_have_skills=nice or [],
        keywords=keywords or [],
        missions=missions or [],
    )


def test_returns_the_offer_built_by_the_provider() -> None:
    offer = make_offer(required=["Python"])

    result = JobAnalyzer(FakeLLMProvider(offer)).analyze(OFFER_TEXT)

    assert result.title == "Python Developer"
    assert result.required_skills == ["Python"]


def test_sends_the_offer_text_inside_tags() -> None:
    provider = FakeLLMProvider(make_offer())

    JobAnalyzer(provider).analyze(OFFER_TEXT)

    _, user_prompt = provider.calls[0]
    assert user_prompt.startswith("<job_offer>")
    assert OFFER_TEXT in user_prompt


def test_rejects_empty_text() -> None:
    with pytest.raises(JobAnalysisError):
        JobAnalyzer(FakeLLMProvider(make_offer())).analyze("  \n ")


def test_rejects_text_that_is_too_long() -> None:
    with pytest.raises(JobAnalysisError):
        JobAnalyzer(FakeLLMProvider(make_offer())).analyze("x" * (MAX_CHARS + 1))


def test_drops_skills_that_are_not_in_the_offer() -> None:
    offer = make_offer(required=["Python", "Rust"])

    result = JobAnalyzer(FakeLLMProvider(offer)).analyze(OFFER_TEXT)

    assert result.required_skills == ["Python"]


def test_grounding_ignores_case_and_covers_all_skill_lists() -> None:
    offer = make_offer(
        required=["python", "Go"],
        nice=["KUBERNETES", "Terraform"],
        keywords=["fastapi", "GraphQL"],
    )

    result = JobAnalyzer(FakeLLMProvider(offer)).analyze(OFFER_TEXT)

    assert result.required_skills == ["python"]
    assert result.nice_to_have_skills == ["KUBERNETES"]
    assert result.keywords == ["fastapi"]


def test_keeps_missions_unchanged() -> None:
    offer = make_offer(missions=["Build and maintain REST APIs"])

    result = JobAnalyzer(FakeLLMProvider(offer)).analyze(OFFER_TEXT)

    assert result.missions == ["Build and maintain REST APIs"]


def test_drops_sentences_that_are_not_short_skills() -> None:
    sentence = "Maîtrise de Python, son écosystème et des bonnes pratiques"
    offer = make_offer(required=[sentence, "Python"])

    result = JobAnalyzer(FakeLLMProvider(offer)).analyze(f"{sentence}. Python requis.")

    assert result.required_skills == ["Python"]
