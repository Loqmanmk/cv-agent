from app.domain.job import JobOffer
from app.domain.letter import LetterBody
from app.services.letter_guard import LetterGuard
from tests.test_tailoring_guard import make_cv

FILLER = " ".join(["mot"] * 50)


def make_offer() -> JobOffer:
    return JobOffer(
        title="Stagiaire",
        company="Acme",
        language="fr",
        contract_type="internship",
        required_skills=["Python", "Kubernetes"],
    )


def make_body(experience: str = "", motivation: str = "", opening: str = "") -> LetterBody:
    return LetterBody(
        opening=f"{FILLER} {opening}".strip(),
        experience=f"{FILLER} {experience}".strip(),
        motivation=f"{FILLER} {motivation}".strip(),
    )


def violations_of(body: LetterBody) -> list[str]:
    return LetterGuard().violations(body, make_cv(), make_offer())


def test_valid_letter_has_no_violations() -> None:
    assert violations_of(make_body()) == []


def test_placeholder_is_rejected() -> None:
    found = violations_of(make_body(opening="pour le poste de [nom du poste]"))

    assert "opening: contains a placeholder or bracket" in found


def test_inclusive_gender_form_is_rejected() -> None:
    found = violations_of(make_body(motivation="Je suis motivé(e) par votre offre"))

    assert any("gender agreement" in violation for violation in found)


def test_too_short_paragraph_is_rejected() -> None:
    body = LetterBody(opening="Trop court.", experience=FILLER, motivation=FILLER)

    found = violations_of(body)

    assert found == ["opening: 2 words, expected 30 to 130"]


def test_too_long_paragraph_is_rejected() -> None:
    body = LetterBody(opening=" ".join(["mot"] * 131), experience=FILLER, motivation=FILLER)

    assert any("131 words" in violation for violation in violations_of(body))


def test_invented_number_is_rejected() -> None:
    found = violations_of(make_body(experience="J'ai réduit le temps de 40%"))

    assert found == ["experience: number '40%' is not in the CV or the offer"]


def test_number_from_the_cv_is_allowed() -> None:
    assert violations_of(make_body(experience="J'ai fait 3 stages")) == []


def test_experience_may_not_claim_a_tool_that_is_only_in_the_offer() -> None:
    found = violations_of(make_body(experience="Je maîtrise Kubernetes"))

    assert len(found) == 1
    assert "claims 'Kubernetes'" in found[0]


def test_tool_from_the_cv_is_allowed_in_the_experience() -> None:
    assert violations_of(make_body(experience="Je maîtrise Python")) == []


def test_offer_only_tool_is_allowed_in_the_motivation() -> None:
    assert violations_of(make_body(motivation="Je souhaite apprendre Kubernetes")) == []


def test_overclaim_word_is_rejected() -> None:
    found = violations_of(make_body(experience="J'ai une véritable expertise en Python"))

    assert any("overstates" in violation and "expertise" in violation for violation in found)


def test_overclaim_check_matches_whole_words_only() -> None:
    assert violations_of(make_body(experience="Mon expérience en Python")) == []
