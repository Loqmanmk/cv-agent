from datetime import date

import pytest

from app.domain.job import JobOffer, OfferLanguage
from app.domain.letter import CoverLetter, Gender, LetterBody, LetterSender
from app.services.letter_assembler import LetterAssembler
from app.services.letter_conventions import (
    FRENCH,
    UnsupportedLetterLanguageError,
    conventions_for,
)

BODY = LetterBody(opening="Opening.", experience="Experience.", motivation="Motivation.")


def make_offer(language: OfferLanguage = "fr", reference: str = "") -> JobOffer:
    return JobOffer(
        title="Stagiaire DataLab",
        company="Acme",
        company_address="1 rue Exemple, Paris",
        contact_person="Mme Martin",
        reference=reference,
        language=language,
        contract_type="internship",
    )


def make_sender(gender: Gender = "m") -> LetterSender:
    return LetterSender(
        name="Jane Doe",
        email="jane@example.com",
        phone="+00 000 000 000",
        address="Oujda, Maroc",
        city="Oujda",
        gender=gender,
    )


def assemble(
    offer: JobOffer | None = None,
    gender: Gender = "m",
    on: date = date(2026, 11, 6),
) -> CoverLetter:
    return LetterAssembler().assemble(BODY, offer or make_offer(), make_sender(gender), on)


def test_subject_without_reference() -> None:
    assert assemble().subject == "Objet : Candidature pour le poste de Stagiaire DataLab"


def test_subject_with_reference() -> None:
    letter = assemble(make_offer(reference="REF-42"))

    assert letter.subject == "Objet : Candidature pour le poste de Stagiaire DataLab - REF-42"


def test_place_and_date_in_french() -> None:
    assert assemble().place_date == "Fait à Oujda, le 6 novembre 2026"


def test_first_day_of_the_month_uses_the_french_ordinal() -> None:
    letter = assemble(on=date(2026, 12, 1))

    assert letter.place_date == "Fait à Oujda, le 1er décembre 2026"


def test_has_three_ai_paragraphs_then_the_fixed_closing() -> None:
    letter = assemble()

    assert letter.paragraphs[:3] == ["Opening.", "Experience.", "Motivation."]
    assert len(letter.paragraphs) == 4
    assert letter.paragraphs[3] == FRENCH.closing["m"]
    assert "heureux" in letter.paragraphs[3]


def test_feminine_closing() -> None:
    assert "heureuse" in assemble(gender="f").paragraphs[3]


def test_recipient_comes_from_the_offer() -> None:
    recipient = assemble().recipient

    assert (recipient.company, recipient.contact) == ("Acme", "Mme Martin")
    assert recipient.address == "1 rue Exemple, Paris"


def test_sender_block_greeting_and_signature() -> None:
    letter = assemble()

    assert letter.sender.address == "Oujda, Maroc"
    assert letter.sender.email == "jane@example.com"
    assert letter.greeting == "Madame, Monsieur,"
    assert letter.signature == "Jane Doe"


@pytest.mark.parametrize("language", ["other"])
def test_unsupported_language_is_refused(language: OfferLanguage) -> None:
    with pytest.raises(UnsupportedLetterLanguageError):
        assemble(make_offer(language=language))


def test_french_conventions_are_found() -> None:
    assert conventions_for("fr") is FRENCH
