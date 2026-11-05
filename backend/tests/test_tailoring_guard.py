import pytest

from app.domain.cv import (
    CV,
    Certification,
    Education,
    Experience,
    Header,
    Language,
    Project,
    SkillGroup,
)
from app.services.tailoring_guard import TailoringGuard, TailoringViolationError


def make_cv() -> CV:
    return CV(
        header=Header(
            name="Jane Doe",
            headline="Student Engineer",
            target_line="Looking for a 6-month internship",
            phone="+00 000 000 000",
            email="jane@example.com",
            location="Morocco",
        ),
        profile="Fifth-year engineering student, 3 internships in web development.",
        experiences=[
            Experience(
                title="Mobile Developer",
                company="Acme",
                city="Casablanca",
                start="Aug. 2026",
                end="Sept. 2026",
                bullets=["Built an Android app with React Native", "Integrated a REST API"],
            )
        ],
        projects=[
            Project(title="PathFinder", subtitle="ML project", bullets=["Model with Scikit-learn"]),
            Project(title="Committed", bullets=["Microservices with Spring Boot"]),
        ],
        education=[Education(degree="Engineering", school="School", start="2024", end="2027")],
        skills=[
            SkillGroup(category="Back-end", items=["Python", "FastAPI"]),
            SkillGroup(category="Front-end", items=["React"]),
        ],
        certifications=[Certification(name="Cert A")],
        languages=[Language(name="French", level="Fluent")],
        interests=["Chess"],
    )


def violations_of(tailored: CV) -> list[str]:
    return TailoringGuard().violations(make_cv(), tailored)


def test_identical_cv_has_no_violations() -> None:
    assert violations_of(make_cv()) == []


def test_rewording_is_allowed() -> None:
    original = make_cv()
    tailored = original.model_copy(
        update={
            "profile": "Engineering student with strong web skills.",
            "header": original.header.model_copy(update={"headline": "Python Developer"}),
            "experiences": [
                original.experiences[0].model_copy(
                    update={"bullets": ["Delivered a REST API", "Built an Android app"]}
                )
            ],
        }
    )

    assert violations_of(tailored) == []


def test_changed_contact_detail_is_rejected() -> None:
    original = make_cv()
    header = original.header.model_copy(update={"email": "other@example.com"})

    found = violations_of(original.model_copy(update={"header": header}))

    assert any("header.email" in violation for violation in found)


def test_changed_experience_facts_are_rejected() -> None:
    original = make_cv()
    experience = original.experiences[0].model_copy(update={"company": "Google"})

    found = violations_of(original.model_copy(update={"experiences": [experience]}))

    assert any("experience 1" in violation for violation in found)


def test_removed_experience_is_rejected() -> None:
    found = violations_of(make_cv().model_copy(update={"experiences": []}))

    assert any("number of experiences" in violation for violation in found)


def test_extra_bullets_are_rejected() -> None:
    original = make_cv()
    bullets = [*original.experiences[0].bullets, "A third bullet"]
    experience = original.experiences[0].model_copy(update={"bullets": bullets})

    found = violations_of(original.model_copy(update={"experiences": [experience]}))

    assert any("more bullets" in violation for violation in found)


def test_invented_skill_is_rejected() -> None:
    skills = [SkillGroup(category="Back-end", items=["Python", "Kubernetes"])]

    found = violations_of(make_cv().model_copy(update={"skills": skills}))

    assert found == ["skill 'Kubernetes' is not in the original CV"]


def test_regrouping_and_reordering_skills_is_allowed() -> None:
    skills = [SkillGroup(category="Main stack", items=["React", "Python", "FastAPI"])]

    assert violations_of(make_cv().model_copy(update={"skills": skills})) == []


def test_invented_number_is_rejected() -> None:
    original = make_cv()
    experience = original.experiences[0].model_copy(update={"bullets": ["Cut latency by 40%"]})

    found = violations_of(original.model_copy(update={"experiences": [experience]}))

    assert found == ["number '40%' is not in the original CV"]


def test_number_from_the_original_is_allowed() -> None:
    tailored = make_cv().model_copy(update={"profile": "Completed 3 internships."})

    assert violations_of(tailored) == []


def test_unknown_project_is_rejected() -> None:
    projects = [Project(title="Invented App", bullets=["Something"])]

    found = violations_of(make_cv().model_copy(update={"projects": projects}))

    assert any("Invented App" in violation for violation in found)


def test_dropping_a_project_is_allowed() -> None:
    original = make_cv()

    assert violations_of(original.model_copy(update={"projects": original.projects[:1]})) == []


def test_changed_education_is_rejected() -> None:
    original = make_cv()
    education = [original.education[0].model_copy(update={"degree": "PhD"})]

    found = violations_of(original.model_copy(update={"education": education}))

    assert "education was changed" in found


def test_ensure_faithful_raises_with_the_violations() -> None:
    skills = [SkillGroup(category="Back-end", items=["Kubernetes"])]
    tailored = make_cv().model_copy(update={"skills": skills})

    with pytest.raises(TailoringViolationError) as raised:
        TailoringGuard().ensure_faithful(make_cv(), tailored)

    assert "Kubernetes" in str(raised.value)
    assert raised.value.violations == ["skill 'Kubernetes' is not in the original CV"]


def test_ensure_faithful_accepts_a_faithful_cv() -> None:
    TailoringGuard().ensure_faithful(make_cv(), make_cv())


def test_skill_must_match_as_a_whole_word() -> None:
    original = make_cv().model_copy(update={"profile": "Web developer with JavaScript."})
    tailored = original.model_copy(update={"skills": [SkillGroup(category="X", items=["Java"])]})

    found = TailoringGuard().violations(original, tailored)

    assert found == ["skill 'Java' is not in the original CV"]


def test_skills_with_symbols_are_matched() -> None:
    skills = [SkillGroup(category="Tools", items=["CI/CD", "C++"])]
    original = make_cv().model_copy(update={"skills": skills})

    assert TailoringGuard().violations(original, original) == []
