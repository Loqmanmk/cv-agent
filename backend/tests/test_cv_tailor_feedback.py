from app.domain.cv import Project
from app.services.cv_tailor import SYSTEM_PROMPT, CVTailor
from tests.fakes import SequenceLLMProvider
from tests.test_cv_tailor import offer_with_keywords
from tests.test_tailoring_guard import make_cv


def test_a_reworded_project_title_gets_a_clear_message_without_dropped_noise() -> None:
    original = make_cv().model_copy(
        update={
            "projects": [
                Project(title="PathFinder - ML project", bullets=["Model with Scikit-learn"]),
                Project(
                    title="Committed - Review tool", bullets=["Microservices with Spring Boot"]
                ),
            ]
        }
    )
    reworded = original.model_copy(
        update={
            "projects": [
                original.projects[0],
                Project(
                    title="Committed - Code review", bullets=["Microservices with Spring Boot"]
                ),
            ]
        }
    )
    provider = SequenceLLMProvider([reworded, original])

    result = CVTailor(provider).tailor(original, offer_with_keywords(["Spring Boot"]))

    assert result == original
    feedback = provider.calls[1][1]
    assert "copy a title exactly" in feedback
    assert "fits the offer better" not in feedback


def test_the_prompt_asks_to_copy_titles_exactly_and_keep_the_order() -> None:
    assert "character for character" in SYSTEM_PROMPT
    assert "same order" in SYSTEM_PROMPT
