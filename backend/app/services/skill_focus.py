from app.domain.cv import CV, SkillGroup
from app.domain.job import JobOffer
from app.services.skill_families import (
    ALWAYS_USEFUL,
    fields_of,
    group_for,
    offer_fields,
)
from app.services.tailoring_guard import contains_term


def _asked(item: str, offer: JobOffer) -> bool:
    terms = (*offer.required_skills, *offer.nice_to_have_skills, *offer.keywords)
    return any(term.strip() and contains_term(item, term) for term in terms)


def focus_skills(original: CV, tailored: CV, offer: JobOffer) -> list[SkillGroup]:
    """The skills of the tailored CV, focused on the field of the offer.

    - A skill from an unrelated field is left out (Kubernetes for a front-end offer).
    - A skill of the CV that the offer needs comes back if the AI dropped it (MySQL for a
      back-end offer), in the group of related skills.
    - Unknown technologies, tools and testing skills are kept: they are never judged.
    - When the field of the offer is unknown, the skills are not changed.
    """
    wanted = offer_fields(offer)
    if not wanted:
        return tailored.skills
    kept_fields = wanted | ALWAYS_USEFUL

    def useful(item: str) -> bool:
        fields = fields_of(item)
        return _asked(item, offer) or not fields or bool(fields & kept_fields)

    groups = [
        SkillGroup(category=group.category, items=[item for item in group.items if useful(item)])
        for group in tailored.skills
    ]
    present = {item.casefold() for group in groups for item in group.items}
    for source in original.skills:
        for item in source.items:
            needed = _asked(item, offer) or bool(fields_of(item) & wanted)
            if needed and item.casefold() not in present:
                groups = _add(groups, item, group_for(item, groups) or source.category)
                present.add(item.casefold())
    return [group for group in groups if group.items]


def _add(groups: list[SkillGroup], item: str, category: str) -> list[SkillGroup]:
    for index, group in enumerate(groups):
        if group.category == category:
            updated = group.model_copy(update={"items": [*group.items, item]})
            return [*groups[:index], updated, *groups[index + 1 :]]
    return [*groups, SkillGroup(category=category, items=[item])]
