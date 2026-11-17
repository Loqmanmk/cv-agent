"""Which field each technology belongs to, so a CV keeps the skills that serve the offer.

A small fixed table is used on purpose: the result is the same every time, it costs no AI
call and it can be tested. A technology that is not in the table is never removed.
"""

import re
from collections.abc import Iterable

from app.domain.cv import SkillGroup
from app.domain.job import JobOffer

FRONTEND = "frontend"
BACKEND = "backend"
DATABASE = "database"
DEVOPS = "devops"
CLOUD = "cloud"
DATA_AI = "data_ai"
MOBILE = "mobile"
TESTING = "testing"
TOOLS = "tools"

# Fields useful in every job: they are never removed from a CV.
ALWAYS_USEFUL = frozenset({TESTING, TOOLS})

TERMS: dict[str, str] = {
    FRONTEND: """react|react.js|reactjs|angular|angularjs|vue|vue.js|vuejs|next.js|nextjs|nuxt|
        svelte|javascript|js|typescript|ts|html|html5|css|css3|tailwind|tailwind css|bootstrap|
        sass|scss|redux|webpack|vite|jquery|figma|es6|javascript es6|ui|ux|responsive design""",
    BACKEND: """node.js|nodejs|node|express|express.js|nestjs|django|flask|fastapi|spring|
        spring boot|laravel|symfony|php|php 8|java|c#|.net|asp.net|ruby|ruby on rails|rails|go|
        golang|rust|kotlin|python|api|apis|api rest|rest|rest api|restful|graphql|microservices|
        grpc|jwt|oauth|websockets|rabbitmq|kafka|poo|oop|mvc|c++|scala""",
    DATABASE: """sql|mysql|postgresql|postgres|oracle|sql server|sqlite|mongodb|redis|cassandra|
        elasticsearch|mariadb|nosql|dynamodb|firebase|supabase|neo4j|pl/sql|t-sql|orm|
        sqlalchemy|hibernate|prisma""",
    DEVOPS: """docker|kubernetes|k8s|helm|jenkins|ci/cd|ci|cd|github actions|gitlab ci|
        terraform|ansible|nginx|apache|linux|bash|shell|prometheus|grafana|argocd|argo cd|
        openshift|devops|vagrant|puppet|chef""",
    CLOUD: """aws|azure|gcp|google cloud|heroku|vercel|netlify|cloud|serverless|lambda|
        cloudflare|digitalocean|s3|ec2""",
    DATA_AI: """python|machine learning|ml|deep learning|nlp|llm|llms|tensorflow|pytorch|keras|
        scikit-learn|sklearn|pandas|numpy|spark|pyspark|hadoop|airflow|power bi|tableau|r|matlab|
        computer vision|vision artificielle|cnn|opencv|hugging face|langchain|data science|
        statistics|statistiques|jupyter|dbt|intelligence artificielle|ia|ai|data|big data|
        rag|generative ai|ia générative|mlops|etl|data analysis|analyse de données|excel""",
    MOBILE: """react native|flutter|dart|swift|swiftui|kotlin|android|ios|expo|xamarin|ionic|
        jetpack compose|mobile""",
    TESTING: """jest|junit|pytest|selenium|cypress|playwright|unit testing|unit tests|
        tests unitaires|tdd|postman|vitest|mocha|testing library|sonarqube|qa""",
    TOOLS: """git|github|gitlab|bitbucket|jira|confluence|scrum|agile|kanban|trello|clean code|
        uml|n8n|notion|slack|vs code|intellij|merise|design patterns|solid""",
}

TABLE: dict[str, frozenset[str]] = {}
for _field, _terms in TERMS.items():
    for _term in _terms.split("|"):
        _key = " ".join(_term.split()).casefold()
        if _key:
            TABLE[_key] = TABLE.get(_key, frozenset()) | {_field}

# Words of a job title that tell the field even when the offer lists no technology.
TITLE_HINTS: dict[str, tuple[str, ...]] = {
    FRONTEND: ("front", "frontend", "front-end", "ui", "web designer", "intégrateur"),
    BACKEND: ("back", "backend", "back-end", "api", "software engineer", "développeur java"),
    DATA_AI: ("data", "machine learning", "ml", "ia", "ai", "intelligence", "ki", "datalab"),
    DEVOPS: ("devops", "sre", "platform", "infrastructure", "système", "system"),
    CLOUD: ("cloud",),
    MOBILE: ("mobile", "android", "ios", "flutter"),
}
FULL_STACK = ("full stack", "fullstack", "full-stack")

# A field that needs another one: a back-end developer works with databases, and so on.
IMPLIED: dict[str, frozenset[str]] = {
    BACKEND: frozenset({DATABASE}),
    DATA_AI: frozenset({DATABASE}),
    DEVOPS: frozenset({CLOUD}),
    CLOUD: frozenset({DEVOPS}),
}

# Words of a skill category name, in the four languages, that tell its field.
CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    FRONTEND: ("front", "frontend", "interface", "web"),
    BACKEND: ("back", "backend", "serveur", "server"),
    DATABASE: ("données", "donnees", "database", "databases", "datenbank", "datenbanken", "sql"),
    DEVOPS: ("devops", "linux", "ops", "déploiement", "deployment", "infrastructure"),
    CLOUD: ("cloud",),
    DATA_AI: ("data", "intelligence", "ia", "ai", "ki", "machine", "ml"),
    MOBILE: ("mobile",),
    TESTING: ("test", "tests", "qualité", "quality"),
    TOOLS: ("outils", "outil", "tools", "werkzeuge", "gestion", "méthodes", "methods"),
}

VERSION = re.compile(r"\s+v?\d+(\.\d+)*$")
WORDS = re.compile(r"[^\W_]+(?:[-.][^\W_]+)*", re.UNICODE)


def fields_of(skill: str) -> frozenset[str]:
    """The fields of a technology ("Kubernetes" -> devops), empty when it is unknown."""
    key = " ".join(skill.split()).casefold()
    return TABLE.get(key) or TABLE.get(VERSION.sub("", key), frozenset())


def _with_implied(fields: Iterable[str]) -> frozenset[str]:
    found = set(fields)
    for field in list(found):
        found |= IMPLIED.get(field, frozenset())
    return frozenset(found)


def _has_hint(text: str, hints: Iterable[str]) -> bool:
    words = text.casefold()
    return any(re.search(rf"(?<!\w){re.escape(hint)}(?!\w)", words) for hint in hints)


def offer_fields(offer: JobOffer) -> frozenset[str]:
    """The fields the offer is about, from its technologies and its job title."""
    fields: set[str] = set()
    for skill in (*offer.required_skills, *offer.nice_to_have_skills, *offer.keywords):
        fields |= fields_of(skill)
    title = offer.title.casefold()
    if _has_hint(title, FULL_STACK):
        fields |= {FRONTEND, BACKEND}
    fields |= {field for field, hints in TITLE_HINTS.items() if _has_hint(title, hints)}
    return _with_implied(fields)


def category_fields(category: str) -> frozenset[str]:
    return frozenset(field for field, hints in CATEGORY_HINTS.items() if _has_hint(category, hints))


def group_for(skill: str, groups: list[SkillGroup]) -> str | None:
    """The skill group a new skill belongs in: the one holding the most related skills.

    "Kubernetes" goes to the group that already holds Docker or Jenkins, or else to a group
    whose name says DevOps. None when no group fits.
    """
    fields = fields_of(skill)
    if not fields:
        return None
    best: tuple[int, str] | None = None
    for group in groups:
        related = sum(bool(fields & fields_of(item)) for item in group.items)
        if related and (best is None or related > best[0]):
            best = (related, group.category)
    if best is not None:
        return best[1]
    named = [group.category for group in groups if fields & category_fields(group.category)]
    return named[0] if named else None
