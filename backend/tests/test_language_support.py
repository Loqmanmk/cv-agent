from dataclasses import fields
from datetime import date

import pytest

from app.domain.cv_labels import (
    ARABIC_LABELS,
    ENGLISH_LABELS,
    FRENCH_LABELS,
    GERMAN_LABELS,
    LABELS_BY_LANGUAGE,
)
from app.domain.job import JobOffer, OfferLanguage
from app.domain.letter import CoverLetter, LetterBody, LetterSender
from app.services.letter_assembler import LetterAssembler
from app.services.letter_conventions import UnsupportedLetterLanguageError, conventions_for
from app.services.letter_guard import LetterGuard
from tests.test_letter_guard import make_body, make_offer
from tests.test_tailoring_guard import make_cv

LANGUAGES = ["fr", "de", "en", "ar"]
BODY = LetterBody(opening="One.", experience="Two.", motivation="Three.")
SENDER = LetterSender(
    name="Jane Doe",
    email="jane@example.com",
    phone="+00 000 000 000",
    address="Oujda, Maroc",
    city="Oujda",
    gender="f",
)


def letter_in(
    language: OfferLanguage,
    reference: str = "",
    on: date = date(2026, 11, 6),
) -> CoverLetter:
    offer = JobOffer(
        title="Data Intern",
        company="Acme",
        reference=reference,
        language=language,
        contract_type="internship",
    )
    return LetterAssembler().assemble(BODY, offer, SENDER, on)


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_has_complete_conventions(language: str) -> None:
    conventions = conventions_for(language)

    assert len(conventions.months) == 12
    assert all(month.strip() for month in conventions.months)
    assert "{title}" in conventions.subject
    assert "{reference}" in conventions.subject_with_reference
    for placeholder in ("{city}", "{day}", "{month}", "{year}"):
        assert placeholder in conventions.place_date
    assert conventions.closing["m"].strip()
    assert conventions.closing["f"].strip()
    assert conventions.overclaims


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_has_complete_cv_labels(language: str) -> None:
    labels = LABELS_BY_LANGUAGE[language]

    assert labels.lang == language
    assert all(getattr(labels, field.name).strip() for field in fields(labels))


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_assembled_letter_has_four_paragraphs_and_the_signature(
    language: OfferLanguage,
) -> None:
    letter = letter_in(language)

    assert letter.paragraphs[:3] == ["One.", "Two.", "Three."]
    assert len(letter.paragraphs) == 4
    assert letter.signature == "Jane Doe"
    assert letter.recipient.company == "Acme"


def test_german_letter() -> None:
    letter = letter_in("de")

    assert letter.greeting == "Sehr geehrte Damen und Herren,"
    assert letter.subject == "Bewerbung als Data Intern"
    assert letter.place_date == "Oujda, 6. November 2026"
    assert letter.paragraphs[3].endswith("Mit freundlichen Grüßen")


def test_german_subject_with_a_reference() -> None:
    assert letter_in("de", reference="REF-42").subject == "Bewerbung als Data Intern - REF-42"


def test_english_letter() -> None:
    letter = letter_in("en")

    assert letter.greeting == "Dear Hiring Manager,"
    assert letter.subject == "Application for the position of Data Intern"
    assert letter.place_date == "Oujda, 6 November 2026"
    assert letter.paragraphs[3].endswith("Yours sincerely,")


def test_arabic_letter() -> None:
    letter = letter_in("ar")

    assert letter.greeting == "تحية طيبة وبعد،"
    assert letter.subject == "الموضوع: الترشح لمنصب Data Intern"
    assert letter.place_date == "Oujda، في 6 نوفمبر 2026"
    assert letter.paragraphs[3].endswith("وتفضلوا بقبول فائق الاحترام والتقدير،")


def test_only_french_uses_an_ordinal_for_the_first_day() -> None:
    first = date(2026, 12, 1)

    assert letter_in("fr", on=first).place_date == "Fait à Oujda, le 1er décembre 2026"
    assert letter_in("de", on=first).place_date == "Oujda, 1. Dezember 2026"
    assert letter_in("en", on=first).place_date == "Oujda, 1 December 2026"


def test_only_arabic_is_written_right_to_left() -> None:
    directions = {language: LABELS_BY_LANGUAGE[language].direction for language in LANGUAGES}

    assert directions == {"fr": "ltr", "de": "ltr", "en": "ltr", "ar": "rtl"}


def test_only_french_puts_a_space_before_the_colon() -> None:
    assert FRENCH_LABELS.colon == " :"
    assert {GERMAN_LABELS.colon, ENGLISH_LABELS.colon, ARABIC_LABELS.colon} == {":"}


def test_other_languages_are_still_refused() -> None:
    with pytest.raises(UnsupportedLetterLanguageError):
        conventions_for("other")


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("de", "Ich habe Expertise in Python"),
        ("en", "I am an expert in Python"),
        ("ar", "أنا خبير في Python"),
    ],
)
def test_overclaims_are_detected_in_every_language(language: OfferLanguage, text: str) -> None:
    offer = make_offer().model_copy(update={"language": language})

    found = LetterGuard().violations(make_body(experience=text), make_cv(), offer)

    assert any("overstates" in violation for violation in found)


@pytest.mark.parametrize(
    "text",
    ["Ich bin ein motivierter Ingenieur(in)", "أنا مهندس(ة) متحمس"],
)
def test_gender_forms_of_other_languages_are_rejected(text: str) -> None:
    found = LetterGuard().violations(make_body(motivation=text), make_cv(), make_offer())

    assert any("gender agreement" in violation for violation in found)
