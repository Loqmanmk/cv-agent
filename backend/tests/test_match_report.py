from app.domain.cv import CV, Project, SkillGroup
from app.domain.job import JobOffer, SkillField
from app.services.match_report import (
    MAX_SKILL_CHARS,
    MatchScore,
    MissingSkill,
    build_match_report,
    score_of,
)
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


def test_a_missing_skill_names_the_group_it_belongs_in() -> None:
    cv = make_cv()

    report = build_match_report(cv, cv, make_offer(["Django", "Snowflake-like unknown"]))

    assert [skill.group for skill in report.missing_skills] == ["Back-end", None]


def test_a_skill_joins_its_group_even_when_the_tailoring_left_that_group_out() -> None:
    original = make_cv().model_copy(
        update={
            "skills": [
                SkillGroup(category="Développement Front-end", items=["Angular"]),
                SkillGroup(category="IA", items=["Pandas"]),
            ]
        }
    )
    tailored = original.model_copy(update={"skills": original.skills[1:]})

    report = build_match_report(original, tailored, make_offer(["Vue.js"]))

    assert report.missing_skills[0].group == "Développement Front-end"


def test_a_skill_of_another_field_gets_a_new_group_named_by_the_ai() -> None:
    cv = make_cv()
    offer = make_offer(["market research", "lead qualification"]).model_copy(
        update={
            "skill_fields": [
                SkillField(skill="market research", field="Business & Strategy"),
                SkillField(skill="Lead  qualification", field="Business & Strategy"),
            ]
        }
    )

    report = build_match_report(cv, cv, offer)

    assert [skill.group for skill in report.missing_skills] == [
        "Business & Strategy",
        "Business & Strategy",
    ]


def test_the_field_of_the_ai_reuses_a_group_of_the_cv_of_the_same_kind() -> None:
    cv = make_cv().model_copy(
        update={"skills": [SkillGroup(category="Bases de données", items=["MySQL"])]}
    )
    offer = make_offer(["Snowflake-like unknown"]).model_copy(
        update={"skill_fields": [SkillField(skill="Snowflake-like unknown", field="Databases")]}
    )

    report = build_match_report(cv, cv, offer)

    assert report.missing_skills[0].group == "Bases de données"


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


def test_the_score_counts_a_required_skill_twice_as_much_as_a_nice_one() -> None:
    cv = make_cv()
    known = skills_of(cv)[0]

    report = build_match_report(cv, cv, make_offer([known, "Kubernetes"], ["Terraform"]))

    # 2 of the 2 + 2 + 1 points: the known required skill only.
    assert report.score == MatchScore(
        value=40, required_matched=1, required_total=2, nice_matched=0, nice_total=1
    )


def test_a_cv_with_every_skill_scores_100() -> None:
    cv = make_cv()
    known = skills_of(cv)

    report = build_match_report(cv, cv, make_offer(known[:1], known[1:2]))

    assert report.score.value == 100


def test_an_offer_without_skills_has_no_score() -> None:
    cv = make_cv()

    assert build_match_report(cv, cv, make_offer([])).score.value is None


def test_the_score_is_rounded_and_stays_between_0_and_100() -> None:
    assert score_of(0, 3, 0, 0) == 0
    assert score_of(1, 3, 0, 0) == 33
    assert score_of(2, 3, 1, 1) == 71
