import re

from app.domain.cv import CV

LOCKED_HEADER_FIELDS = ("name", "phone", "email", "linkedin", "github", "location")
NUMBER = re.compile(r"\d[\d.,%]*")


class TailoringViolationError(Exception):
    """Raised when a tailored CV breaks the faithfulness rules."""

    def __init__(self, violations: list[str]) -> None:
        super().__init__("; ".join(violations))
        self.violations = violations


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    return []


def _numbers(text: str) -> set[str]:
    return {number.rstrip(".,") for number in NUMBER.findall(text)}


def _tailorable_text(cv: CV) -> list[str]:
    parts = [cv.header.headline, cv.header.target_line, cv.profile, *cv.interests]
    for experience in cv.experiences:
        parts.extend(experience.bullets)
    for project in cv.projects:
        parts.extend([project.subtitle, *project.bullets])
    return parts


class TailoringGuard:
    """Checks that a tailored CV only rewords and reorders the original facts."""

    def violations(self, original: CV, tailored: CV) -> list[str]:
        corpus = " ".join(_strings(original.model_dump()))
        return [
            *self._locked_violations(original, tailored),
            *self._experience_violations(original, tailored),
            *self._project_violations(original, tailored),
            *self._skill_violations(tailored, corpus.lower()),
            *self._number_violations(tailored, corpus),
        ]

    def ensure_faithful(self, original: CV, tailored: CV) -> None:
        found = self.violations(original, tailored)
        if found:
            raise TailoringViolationError(found)

    @staticmethod
    def _locked_violations(original: CV, tailored: CV) -> list[str]:
        found = [
            f"header.{field} was changed"
            for field in LOCKED_HEADER_FIELDS
            if getattr(original.header, field) != getattr(tailored.header, field)
        ]
        if original.education != tailored.education:
            found.append("education was changed")
        if original.certifications != tailored.certifications:
            found.append("certifications were changed")
        if original.languages != tailored.languages:
            found.append("languages were changed")
        return found

    @staticmethod
    def _experience_violations(original: CV, tailored: CV) -> list[str]:
        if len(original.experiences) != len(tailored.experiences):
            return ["the number of experiences was changed"]
        found: list[str] = []
        pairs = zip(original.experiences, tailored.experiences, strict=True)
        for index, (before, after) in enumerate(pairs, start=1):
            if before.model_dump(exclude={"bullets"}) != after.model_dump(exclude={"bullets"}):
                found.append(f"experience {index}: title, company, city or dates changed")
            if len(after.bullets) > len(before.bullets):
                found.append(f"experience {index}: more bullets than the original")
        return found

    @staticmethod
    def _project_violations(original: CV, tailored: CV) -> list[str]:
        originals = {project.title: project for project in original.projects}
        found: list[str] = []
        for project in tailored.projects:
            before = originals.get(project.title)
            if before is None:
                found.append(f"project '{project.title}' is not in the original CV")
            elif len(project.bullets) > len(before.bullets):
                found.append(f"project '{project.title}': more bullets than the original")
        return found

    @staticmethod
    def _skill_violations(tailored: CV, lowered_corpus: str) -> list[str]:
        return [
            f"skill '{item}' is not in the original CV"
            for group in tailored.skills
            for item in group.items
            if item.lower() not in lowered_corpus
        ]

    @staticmethod
    def _number_violations(tailored: CV, corpus: str) -> list[str]:
        known = _numbers(corpus)
        used = _numbers(" ".join(_tailorable_text(tailored)))
        return [f"number '{number}' is not in the original CV" for number in sorted(used - known)]
