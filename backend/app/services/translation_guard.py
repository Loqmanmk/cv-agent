import re

from app.domain.cv import CV
from app.services.tailoring_guard import numbers_in, project_name

LOCKED_HEADER_FIELDS = ("name", "phone", "email", "linkedin", "github")
ARABIC_LETTER = re.compile(r"[\u0600-\u06FF]")
MIN_BULLET_WORDS = 4
MIN_LONG_NUMBER_DIGITS = 3

Pair = tuple[str, str, str]


class TranslationViolationError(Exception):
    """Raised when a translated CV changes facts or is not really translated."""

    def __init__(self, violations: list[str]) -> None:
        super().__init__("; ".join(violations))
        self.violations = violations


def _digit_count(number: str) -> int:
    return sum(character.isdigit() for character in number)


def _bullet_lists(cv: CV) -> list[list[str]]:
    return [*(e.bullets for e in cv.experiences), *(p.bullets for p in cv.projects)]


def _bullet_pairs(original: CV, translated: CV) -> list[tuple[str, str]]:
    lists = zip(_bullet_lists(original), _bullet_lists(translated), strict=True)
    return [
        (before, after)
        for before_list, after_list in lists
        for before, after in zip(before_list, after_list, strict=True)
    ]


def _structure_violations(original: CV, translated: CV) -> list[str]:
    counts = {
        "experiences": (len(original.experiences), len(translated.experiences)),
        "projects": (len(original.projects), len(translated.projects)),
        "education entries": (len(original.education), len(translated.education)),
        "skill groups": (len(original.skills), len(translated.skills)),
        "certifications": (len(original.certifications), len(translated.certifications)),
        "languages": (len(original.languages), len(translated.languages)),
        "interests": (len(original.interests), len(translated.interests)),
    }
    found = [f"the number of {name} changed" for name, (a, b) in counts.items() if a != b]
    if found:
        return found
    jobs = zip(original.experiences, translated.experiences, strict=True)
    for index, (job, new_job) in enumerate(jobs, start=1):
        if len(job.bullets) != len(new_job.bullets):
            found.append(f"experience {index}: the number of bullets changed")
    projects = zip(original.projects, translated.projects, strict=True)
    for index, (project, new_project) in enumerate(projects, start=1):
        if len(project.bullets) != len(new_project.bullets):
            found.append(f"project {index}: the number of bullets changed")
    return found


def _header_violations(original: CV, translated: CV) -> list[str]:
    return [
        f"header.{field} was changed"
        for field in LOCKED_HEADER_FIELDS
        if getattr(original.header, field) != getattr(translated.header, field)
    ]


def _experience_violations(original: CV, translated: CV) -> list[str]:
    pairs = zip(original.experiences, translated.experiences, strict=True)
    return [
        f"experience {index}: company or city changed"
        for index, (before, after) in enumerate(pairs, start=1)
        if (before.company, before.city) != (after.company, after.city)
    ]


def _project_violations(original: CV, translated: CV) -> list[str]:
    pairs = zip(original.projects, translated.projects, strict=True)
    return [
        f"project {index}: the project name '{project_name(before.title)}' was changed"
        for index, (before, after) in enumerate(pairs, start=1)
        if not after.title.startswith(project_name(before.title))
    ]


def _education_violations(original: CV, translated: CV) -> list[str]:
    pairs = zip(original.education, translated.education, strict=True)
    return [
        f"education {index}: school or city changed"
        for index, (before, after) in enumerate(pairs, start=1)
        if (before.school, before.city) != (after.school, after.city)
    ]


def _skill_violations(original: CV, translated: CV) -> list[str]:
    pairs = zip(original.skills, translated.skills, strict=True)
    return [
        f"skills group {index}: the items were changed"
        for index, (before, after) in enumerate(pairs, start=1)
        if before.items != after.items
    ]


def _certification_violations(original: CV, translated: CV) -> list[str]:
    pairs = zip(original.certifications, translated.certifications, strict=True)
    return [
        f"certification {index}: name or issuer changed"
        for index, (before, after) in enumerate(pairs, start=1)
        if (before.name, before.issuer) != (after.name, after.issuer)
    ]


def _locked_violations(original: CV, translated: CV) -> list[str]:
    return [
        *_header_violations(original, translated),
        *_experience_violations(original, translated),
        *_project_violations(original, translated),
        *_education_violations(original, translated),
        *_skill_violations(original, translated),
        *_certification_violations(original, translated),
    ]


def _numbered(prefix: str, before: list[str], after: list[str]) -> list[Pair]:
    pairs = zip(before, after, strict=True)
    return [(f"{prefix} {n}", b, a) for n, (b, a) in enumerate(pairs, start=1)]


def _header_pairs(original: CV, translated: CV) -> list[Pair]:
    old, new = original.header, translated.header
    return [
        ("headline", old.headline, new.headline),
        ("target line", old.target_line, new.target_line),
        ("location", old.location, new.location),
        ("profile", original.profile, translated.profile),
    ]


def _experience_pairs(original: CV, translated: CV) -> list[Pair]:
    pairs: list[Pair] = []
    entries = zip(original.experiences, translated.experiences, strict=True)
    for index, (before, after) in enumerate(entries, start=1):
        label = f"experience {index}"
        pairs += [
            (f"{label} title", before.title, after.title),
            (f"{label} start", before.start, after.start),
            (f"{label} end", before.end, after.end),
        ]
        pairs += _numbered(f"{label} bullet", before.bullets, after.bullets)
    return pairs


def _project_pairs(original: CV, translated: CV) -> list[Pair]:
    pairs: list[Pair] = []
    entries = zip(original.projects, translated.projects, strict=True)
    for index, (before, after) in enumerate(entries, start=1):
        label = f"project {index}"
        pairs += [
            (f"{label} title", before.title, after.title),
            (f"{label} subtitle", before.subtitle, after.subtitle),
        ]
        pairs += _numbered(f"{label} bullet", before.bullets, after.bullets)
    return pairs


def _education_pairs(original: CV, translated: CV) -> list[Pair]:
    pairs: list[Pair] = []
    entries = zip(original.education, translated.education, strict=True)
    for index, (before, after) in enumerate(entries, start=1):
        label = f"education {index}"
        pairs += [
            (f"{label} degree", before.degree, after.degree),
            (f"{label} start", before.start, after.start),
            (f"{label} end", before.end, after.end),
            (f"{label} note", before.note, after.note),
        ]
    return pairs


def _list_pairs(original: CV, translated: CV) -> list[Pair]:
    skills = zip(original.skills, translated.skills, strict=True)
    certifications = zip(original.certifications, translated.certifications, strict=True)
    languages = zip(original.languages, translated.languages, strict=True)
    pairs: list[Pair] = [
        (f"skills group {n} name", a.category, b.category) for n, (a, b) in enumerate(skills, 1)
    ]
    pairs += [
        (f"certification {n} status", a.status, b.status)
        for n, (a, b) in enumerate(certifications, 1)
    ]
    for n, (language, new_language) in enumerate(languages, 1):
        pairs.append((f"language {n} name", language.name, new_language.name))
        pairs.append((f"language {n} level", language.level, new_language.level))
    pairs += _numbered("interest", original.interests, translated.interests)
    return pairs


def _text_pairs(original: CV, translated: CV) -> list[Pair]:
    return [
        *_header_pairs(original, translated),
        *_experience_pairs(original, translated),
        *_project_pairs(original, translated),
        *_education_pairs(original, translated),
        *_list_pairs(original, translated),
    ]


def _pair_violations(pairs: list[Pair]) -> list[str]:
    found: list[str] = []
    for label, before, after in pairs:
        if before.strip() and not after.strip():
            found.append(f"{label}: the text was removed")
            continue
        if after.strip() and not before.strip():
            found.append(f"{label}: text was added where there was none")
            continue
        old, new = numbers_in(before), numbers_in(after)
        found += [f"{label}: number '{n}' was added" for n in sorted(new - old)]
        found += [
            f"{label}: number '{n}' was lost"
            for n in sorted(old - new)
            if _digit_count(n) >= MIN_LONG_NUMBER_DIGITS
        ]
    return found


def _is_translated(before: str, after: str, language: str) -> bool:
    if language == "ar":
        return ARABIC_LETTER.search(after) is not None
    return before.strip().casefold() != after.strip().casefold()


def _translation_violations(original: CV, translated: CV, language: str) -> list[str]:
    key_texts = [
        ("headline", original.header.headline, translated.header.headline),
        ("target line", original.header.target_line, translated.header.target_line),
        ("profile", original.profile, translated.profile),
    ]
    found = [
        f"{label} was not translated"
        for label, before, after in key_texts
        if before.strip() and not _is_translated(before, after, language)
    ]
    bullets = [
        (before, after)
        for before, after in _bullet_pairs(original, translated)
        if len(before.split()) >= MIN_BULLET_WORDS
    ]
    done = sum(_is_translated(before, after, language) for before, after in bullets)
    if bullets and done * 2 < len(bullets):
        found.append("most bullets were not translated")
    return found


class TranslationGuard:
    """Checks that a translated CV keeps every fact and is really translated."""

    def violations(self, original: CV, translated: CV, language: str) -> list[str]:
        structure = _structure_violations(original, translated)
        if structure:
            return structure
        return [
            *_locked_violations(original, translated),
            *_pair_violations(_text_pairs(original, translated)),
            *_translation_violations(original, translated, language),
        ]
