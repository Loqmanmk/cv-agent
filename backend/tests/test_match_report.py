from app.domain.cv import CV, Project, SkillGroup
from app.domain.job import JobOffer
from app.services.match_report import MAX_SKILL_CHARS, MissingSkill, build_match_report
from tests.test_tailoring_guard import make_cv


def make_offer(required: list[str], nice: list[str] | None = None) -> JobOffer:
    return JobOffer(
        title="Data Engineer",
        company="Acme",
        language="en",
        contract_type="full_time",
        required_skills=required,
        nice_to_have_skills=nice or [],
    )


def skills_of(cv: CV) -> list[str]:
    return [item for group in cv.skills for item in group.items]


def test_skills_already_in_the_cv_are_matched_and_the_others_listed() -> None:
    cv = make_cv()
    known = skills_of(cv)[0]

    report = build_match_report(cv, cv, make_offer([known, "Kubernetes"], ["Terraform"]))

    assert report.matched_skills == [known]
    assert report.missing_skills == [
        MissingSkill(name="Kubernetes", required=True),
        MissingSkill(name="Terraform", required=False),
    ]


def test_a_skill_is_matched_wherever_the_cv_mentions_it() -> None:
    cv = make_cv().model_copy(update={"profile": "I build pipelines with Apache Airflow."})

    report = build_match_report(cv, cv, make_offer(["airflow"]))

    assert report.matched_skills == ["airflow"]
    assert report.missing_skills == []


def test_duplicates_empty_and_overlong_skills_are_ignored() -> None:
    cv = make_cv()
    long_phrase = "x" * (MAX_SKILL_CHARS + 1)

    report = build_match_report(
        cv, cv, make_offer(["Kubernetes", " ", long_phrase], ["kubernetes", "Go  lang"])
    )

    assert report.missing_skills == [
        MissingSkill(name="Kubernetes", required=True),
        MissingSkill(name="Go lang", required=False),
    ]


def test_an_unchanged_cv_reports_no_change() -> None:
    cv = make_cv()

    assert build_match_report(cv, cv, make_offer([])).changes == []


def test_every_kind_of_change_is_reported() -> None:
    original = make_cv()
    header = original.header.model_copy(
        update={"headline": "Data Engineer", "target_line": "Open to data roles"}
    )
    experience = original.experiences[0]
    tailored = original.model_copy(
        update={
            "header": header,
            "profile": "Rewritten profile.",
            "experiences": [
                experience.model_copy(update={"bullets": ["A reworded bullet"]}),
                *original.experiences[1:],
            ],
            "projects": original.projects[:1],
            "skills": [SkillGroup(category="Data", items=skills_of(original)[:1])],
        }
    )

    changes = build_match_report(original, tailored, make_offer([])).changes

    text = "\n".join(changes)
    assert f'Headline changed to "Data Engineer" (was "{original.header.headline}")' in text
    assert "Target line rewritten" in text
    assert "Profile rewritten" in text
    assert f"{experience.title} ({experience.company}): 1 bullet reworded" in text
    for project in original.projects[1:]:
        assert f"Project left out to keep one page: {project.title}." in changes
    assert "Skills regrouped and reordered" in text
    assert "Skills left out to save space" in text


def test_reordered_bullets_are_reported_as_reordered() -> None:
    original = make_cv().model_copy(
        update={"projects": [Project(title="PathFinder", bullets=["First", "Second"])]}
    )
    tailored = original.model_copy(
        update={"projects": [Project(title="PathFinder", bullets=["Second", "First"])]}
    )

    changes = build_match_report(original, tailored, make_offer([])).changes

    assert changes == ["PathFinder: bullets reordered, the most relevant first."]
