from app.domain.cv import Project
from app.services.tailoring_guard import project_name
from tests.test_tailoring_guard import make_cv, violations_of


def test_a_changed_experience_field_is_reported_with_its_original_value() -> None:
    original = make_cv()
    experience = original.experiences[0].model_copy(update={"title": "Senior Developer"})

    found = violations_of(original.model_copy(update={"experiences": [experience]}))

    assert found == ["experience 1: title must stay 'Mobile Developer', not 'Senior Developer'"]


def test_an_unknown_project_message_lists_the_titles_to_copy() -> None:
    projects = [Project(title="Invented App", bullets=["Something"])]

    found = violations_of(make_cv().model_copy(update={"projects": projects}))

    assert found == [
        "project 'Invented App' is not in the original CV; "
        "copy a title exactly from: 'PathFinder', 'Committed'"
    ]


def test_project_name_is_the_part_before_the_first_separator() -> None:
    assert project_name("PathFinder - Orientation par ML") == "PathFinder"
    assert project_name("PathFinder") == "PathFinder"
