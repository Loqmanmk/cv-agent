import pytest

from app.domain.cv import SkillGroup
from app.domain.job import JobOffer
from app.services.skill_families import (
    BACKEND,
    CLOUD,
    DATA_AI,
    DATABASE,
    DEVOPS,
    FRONTEND,
    category_fields,
    fields_of,
    group_for,
    offer_fields,
)

GROUPS = [
    SkillGroup(category="Intelligence Artificielle et Data", items=["Python", "Pandas"]),
    SkillGroup(category="DevOps, Cloud et Linux", items=["Docker", "CI/CD", "Linux"]),
    SkillGroup(category="Bases de données SQL et NoSQL", items=["MySQL", "PostgreSQL"]),
    SkillGroup(category="Développement Back-end", items=["FastAPI", "Laravel"]),
    SkillGroup(category="Développement Front-end et Mobile", items=["React.js", "TypeScript"]),
]


def offer(title: str, skills: list[str] | None = None) -> JobOffer:
    return JobOffer(
        title=title,
        language="en",
        contract_type="full_time",
        required_skills=skills or [],
    )


@pytest.mark.parametrize(
    ("skill", "fields"),
    [
        ("Kubernetes", {DEVOPS}),
        ("  kubernetes ", {DEVOPS}),
        ("React.js", {FRONTEND}),
        ("Python", {BACKEND, DATA_AI}),
        ("PHP 8", {BACKEND}),
        ("Snowflake-like unknown tool", set()),
    ],
)
def test_the_field_of_a_technology_is_known(skill: str, fields: set[str]) -> None:
    assert fields_of(skill) == fields


@pytest.mark.parametrize(
    ("skill", "group"),
    [
        ("Kubernetes", "DevOps, Cloud et Linux"),
        ("AWS", "DevOps, Cloud et Linux"),
        ("MongoDB", "Bases de données SQL et NoSQL"),
        ("Kafka", "Développement Back-end"),
        ("Vue.js", "Développement Front-end et Mobile"),
        ("PyTorch", "Intelligence Artificielle et Data"),
    ],
)
def test_a_new_skill_goes_to_the_group_of_related_skills(skill: str, group: str) -> None:
    assert group_for(skill, GROUPS) == group


def test_the_name_of_a_group_is_used_when_no_related_skill_is_in_it() -> None:
    groups = [SkillGroup(category="Outils DevOps", items=["Make"])]

    assert group_for("Kubernetes", groups) == "Outils DevOps"


def test_an_unknown_technology_has_no_group() -> None:
    assert group_for("Snowflake-like unknown tool", GROUPS) is None


def test_the_fields_of_an_offer_come_from_its_skills_and_its_title() -> None:
    assert offer_fields(offer("Frontend Developer")) == {FRONTEND}
    assert offer_fields(offer("Développeur Back-end Java")) == {BACKEND, DATABASE}
    assert offer_fields(offer("Ingénieur", ["Kubernetes"])) == {DEVOPS, CLOUD}
    assert offer_fields(offer("Full-Stack Developer")) == {FRONTEND, BACKEND, DATABASE}
    assert offer_fields(offer("Stagiaire DataLab")) == {DATA_AI, DATABASE}


def test_an_offer_without_a_known_field_has_none() -> None:
    assert offer_fields(offer("Assistant commercial", ["Communication"])) == set()


def test_the_name_of_a_category_tells_its_field() -> None:
    assert category_fields("Bases de données SQL et NoSQL") == {DATABASE}
    assert DEVOPS in category_fields("DevOps, Cloud et Linux")
