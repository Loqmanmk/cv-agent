from app.domain.cv import SkillGroup
from app.domain.job import JobOffer
from app.services.skill_focus import focus_skills
from tests.test_tailoring_guard import make_cv

SKILLS = [
    SkillGroup(category="Back-end", items=["Laravel", "FastAPI"]),
    SkillGroup(category="Bases de données", items=["MySQL", "Redis"]),
    SkillGroup(category="DevOps", items=["Docker", "Kubernetes"]),
    SkillGroup(category="Front-end", items=["React.js", "TypeScript"]),
    SkillGroup(category="Outils", items=["Git", "Jira", "n8n-like unknown"]),
]


def offer(title: str, skills: list[str] | None = None) -> JobOffer:
    return JobOffer(
        title=title,
        language="fr",
        contract_type="internship",
        required_skills=skills or [],
    )


def items(groups: list[SkillGroup]) -> list[str]:
    return [item for group in groups for item in group.items]


def test_a_front_end_offer_leaves_out_back_end_and_devops_skills() -> None:
    cv = make_cv().model_copy(update={"skills": SKILLS})

    focused = focus_skills(cv, cv, offer("Développeur Front-end", ["React"]))

    assert [group.category for group in focused] == ["Front-end", "Outils"]
    assert "Kubernetes" not in items(focused)
    assert "Laravel" not in items(focused)


def test_tools_and_unknown_technologies_are_always_kept() -> None:
    cv = make_cv().model_copy(update={"skills": SKILLS})

    focused = focus_skills(cv, cv, offer("Développeur Front-end"))

    assert {"Git", "Jira", "n8n-like unknown"} <= set(items(focused))


def test_a_skill_the_offer_names_is_kept_even_from_another_field() -> None:
    cv = make_cv().model_copy(update={"skills": SKILLS})

    focused = focus_skills(cv, cv, offer("Développeur Front-end", ["React", "Docker"]))

    assert "Docker" in items(focused)


def test_database_skills_the_ai_dropped_come_back_for_a_back_end_offer() -> None:
    cv = make_cv().model_copy(update={"skills": SKILLS})
    tailored = cv.model_copy(
        update={"skills": [SkillGroup(category="Stack", items=["Laravel", "FastAPI"])]}
    )

    focused = focus_skills(cv, tailored, offer("Développeur Back-end PHP"))

    assert focused[0] == SkillGroup(category="Stack", items=["Laravel", "FastAPI"])
    assert SkillGroup(category="Bases de données", items=["MySQL", "Redis"]) in focused


def test_a_restored_skill_joins_the_group_of_related_skills() -> None:
    cv = make_cv().model_copy(update={"skills": SKILLS})
    tailored = cv.model_copy(
        update={"skills": [SkillGroup(category="Infra", items=["Docker"]), *SKILLS[4:]]}
    )

    focused = focus_skills(cv, tailored, offer("DevOps Engineer"))

    assert focused[0] == SkillGroup(category="Infra", items=["Docker", "Kubernetes"])


def test_skills_are_unchanged_when_the_field_of_the_offer_is_unknown() -> None:
    cv = make_cv().model_copy(update={"skills": SKILLS})

    assert focus_skills(cv, cv, offer("Assistant commercial")) == SKILLS
