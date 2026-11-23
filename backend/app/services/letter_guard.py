import re

from app.domain.cv import CV
from app.domain.job import JobOffer
from app.domain.letter import LetterBody
from app.services.letter_conventions import conventions_for
from app.services.tailoring_guard import contains_term, numbers_in, strings_in

MIN_WORDS = 30
MAX_WORDS = 130
BRACKETS = re.compile(r"[\[\]{}<>]")
INCLUSIVE_FORM = re.compile(r"\((?:e|s|se|in|ة)\)", re.IGNORECASE)


class LetterViolationError(Exception):
    """Raised when the letter paragraphs break the rules."""

    def __init__(self, violations: list[str]) -> None:
        super().__init__("; ".join(violations))
        self.violations = violations


class LetterGuard:
    """Checks the paragraphs written by the AI.

    Some problems are serious: an invented fact, number or skill, a placeholder, a letter
    that never names the company. Others are only style: a too strong word or a paragraph a
    little too long. Style problems are sent back to the AI to fix, but they never stop the
    application: the user reads and can edit the letter before sending it.
    """

    def violations(self, body: LetterBody, cv: CV, offer: JobOffer) -> list[str]:
        """Every problem, serious or of style, to send back to the AI."""
        return self._check(body, cv, offer, style=True)

    def serious_violations(self, body: LetterBody, cv: CV, offer: JobOffer) -> list[str]:
        """Only the problems that make the letter unfaithful or unusable."""
        return self._check(body, cv, offer, style=False)

    def _check(self, body: LetterBody, cv: CV, offer: JobOffer, *, style: bool) -> list[str]:
        overclaims = conventions_for(offer.language).overclaims
        paragraphs = {
            "opening": body.opening,
            "experience": body.experience,
            "motivation": body.motivation,
        }
        cv_text = " ".join(strings_in(cv.model_dump()))
        offer_text = " ".join(strings_in(offer.model_dump()))
        allowed_numbers = numbers_in(cv_text) | numbers_in(offer_text)
        found: list[str] = []
        for name, text in paragraphs.items():
            found.extend(self._paragraph_violations(name, text, allowed_numbers))
            if style:
                found.extend(self._length_violations(name, text))
                found.extend(self._overclaim_violations(name, text, overclaims))
        found.extend(self._claim_violations(body.experience, cv_text, offer))
        found.extend(self._company_violations(list(paragraphs.values()), offer.company))
        return found

    @staticmethod
    def _paragraph_violations(name: str, text: str, allowed_numbers: set[str]) -> list[str]:
        found: list[str] = []
        if BRACKETS.search(text):
            found.append(f"{name}: contains a placeholder or bracket")
        if INCLUSIVE_FORM.search(text):
            found.append(f"{name}: use one gender agreement, not (e) forms")
        for number in sorted(numbers_in(text) - allowed_numbers):
            found.append(f"{name}: number '{number}' is not in the CV or the offer")
        return found

    @staticmethod
    def _length_violations(name: str, text: str) -> list[str]:
        words = len(text.split())
        if MIN_WORDS <= words <= MAX_WORDS:
            return []
        return [f"{name}: {words} words, expected {MIN_WORDS} to {MAX_WORDS}"]

    @staticmethod
    def _overclaim_violations(name: str, text: str, overclaims: tuple[str, ...]) -> list[str]:
        return [
            f"{name}: '{term}' overstates the candidate's level. Do not use this word at all, "
            "not even about the company; describe the level honestly"
            for term in overclaims
            if contains_term(text, term)
        ]

    @staticmethod
    def _claim_violations(experience: str, cv_text: str, offer: JobOffer) -> list[str]:
        terms = dict.fromkeys([*offer.required_skills, *offer.nice_to_have_skills, *offer.keywords])
        return [
            f"experience: claims '{term}', which is not in the CV "
            "(mention it only as something to learn, in the motivation paragraph)"
            for term in terms
            if contains_term(experience, term) and not contains_term(cv_text, term)
        ]

    @staticmethod
    def _company_violations(texts: list[str], company: str) -> list[str]:
        if not company or any(contains_term(text, company) for text in texts):
            return []
        return [f"the letter never mentions the company name '{company}'"]
