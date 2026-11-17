from dataclasses import dataclass

from app.domain.cv import CV, Experience, Project
from app.domain.job import JobOffer
from app.services.skill_families import group_for
from app.services.tailoring_guard import contains_term, strings_in

MAX_SKILL_CHARS = 60


@dataclass(frozen=True)
class MissingSkill:
    """A skill the offer asks for that the CV does not mention."""

    name: str
    required: bool
    # The skill group of the tailored CV it belongs in, or None to put it in a new group.
    group: str | None = None


@dataclass(frozen=True)
class MatchReport:
    """How the tailored CV matches the offer, and every change made to get there.

    It is computed by comparing the documents, not written by the AI, so the user can trust it.
    """

    matched_skills: list[str]
    missing_skills: list[MissingSkill]
    changes: list[str]


def _offer_skills(offer: JobOffer) -> list[tuple[str, bool]]:
    """The skills of the offer, required ones first, without duplicates or long phrases."""
    seen: set[str] = set()
    skills: list[tuple[str, bool]] = []
    for names, required in ((offer.required_skills, True), (offer.nice_to_have_skills, False)):
        for name in names:
            clean = " ".join(name.split())
            key = clean.casefold()
            if clean and len(clean) <= MAX_SKILL_CHARS and key not in seen:
                seen.add(key)
                skills.append((clean, required))
    return skills


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _bullet_changes(label: str, before: list[str], after: list[str]) -> list[str]:
    reworded = sum(bullet not in before for bullet in after)
    removed = max(len(before) - len(after), 0)
    found: list[str] = []
    if reworded:
        found.append(f"{label}: {_plural(reworded, 'bullet')} reworded for the offer.")
    if removed:
        found.append(f"{label}: {_plural(removed, 'bullet')} left out to save space.")
    if not reworded and not removed and before != after:
        found.append(f"{label}: bullets reordered, the most relevant first.")
    return found


def _experience_label(experience: Experience) -> str:
    return f"{experience.title} ({experience.company})"


def _project_changes(original: CV, tailored: CV) -> list[str]:
    kept = {project.title: project for project in tailored.projects}
    found: list[str] = []
    for project in original.projects:
        after: Project | None = kept.get(project.title)
        if after is None:
            found.append(f"Project left out to keep one page: {project.title}.")
        else:
            found.extend(_bullet_changes(project.title, project.bullets, after.bullets))
    return found


def _skill_changes(original: CV, tailored: CV) -> list[str]:
    kept = {item.casefold() for group in tailored.skills for item in group.items}
    dropped = [
        item for group in original.skills for item in group.items if item.casefold() not in kept
    ]
    found: list[str] = []
    if original.skills != tailored.skills:
        found.append("Skills regrouped and reordered: the ones the offer asks for come first.")
    if dropped:
        found.append(f"Skills left out to save space: {', '.join(dropped)}.")
    return found


def _changes(original: CV, tailored: CV) -> list[str]:
    found: list[str] = []
    if original.header.headline != tailored.header.headline:
        found.append(
            f'Headline changed to "{tailored.header.headline}" (was "{original.header.headline}").'
        )
    if original.header.target_line != tailored.header.target_line:
        found.append("Target line rewritten for this offer.")
    if original.profile != tailored.profile:
        found.append("Profile rewritten with the words of the offer.")
    for before, after in zip(original.experiences, tailored.experiences, strict=False):
        found.extend(_bullet_changes(_experience_label(before), before.bullets, after.bullets))
    found.extend(_project_changes(original, tailored))
    found.extend(_skill_changes(original, tailored))
    return found


def build_match_report(original: CV, tailored: CV, offer: JobOffer) -> MatchReport:
    corpus = " ".join(strings_in(original.model_dump()))
    matched: list[str] = []
    missing: list[MissingSkill] = []
    for name, required in _offer_skills(offer):
        if contains_term(corpus, name):
            matched.append(name)
        else:
            missing.append(
                MissingSkill(name=name, required=required, group=group_for(name, tailored.skills))
            )
    return MatchReport(
        matched_skills=matched, missing_skills=missing, changes=_changes(original, tailored)
    )
