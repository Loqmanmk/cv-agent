from app.domain.job import JobOffer
from app.domain.letter import LetterBody
from app.services.letter_guard import LetterGuard
from tests.test_tailoring_guard import make_cv

FILLER = " ".join(["Acme", *["mot"] * 49])


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


def test_letter_must_name_the_company() -> None:
    plain = " ".join(["mot"] * 50)
    body = LetterBody(opening=plain, experience=plain, motivation=plain)

    assert violations_of(body) == ["the letter never mentions the company name 'Acme'"]


def test_company_summary_numbers_are_allowed_in_the_letter() -> None:
    offer = make_offer().model_copy(update={"company_summary": "Active in 58 countries."})
    body = make_body(motivation="Acme est présent dans 58 pays")

    assert LetterGuard().violations(body, make_cv(), offer) == []


def test_a_strong_word_or_a_long_paragraph_is_only_a_matter_of_style() -> None:
    body = make_body(opening="Acme, centre d'expertise " + "mot " * 120)

    serious = LetterGuard().serious_violations(body, make_cv(), make_offer())

    assert serious == []
    assert len(violations_of(body)) == 2


def test_invented_facts_and_placeholders_stay_serious() -> None:
    body = make_body(opening="[poste] 999", experience="Kubernetes")

    serious = LetterGuard().serious_violations(body, make_cv(), make_offer())

    assert any("placeholder" in problem for problem in serious)
    assert any("999" in problem for problem in serious)
    assert any("Kubernetes" in problem for problem in serious)


def test_the_ai_is_told_not_to_use_a_strong_word_even_about_the_company() -> None:
    found = violations_of(make_body(opening="Acme est un centre d'expertise"))

    assert any("not even about the company" in problem for problem in found)
