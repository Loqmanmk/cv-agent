from app.domain.cv_labels import (
    ARABIC_LABELS,
    ENGLISH_LABELS,
    FRENCH_LABELS,
    GERMAN_LABELS,
)
from app.infrastructure.cv_html_builder import CVHtmlBuilder
from app.infrastructure.letter_html_builder import LetterHtmlBuilder
from app.infrastructure.pdf_converter import PlaywrightPdfConverter
from app.infrastructure.pdf_page_counter import PyMuPdfPageCounter
from tests.test_letter_html_builder import make_letter
from tests.test_page_fitting_integration import chromium_required
from tests.test_tailoring_guard import make_cv


def test_german_cv_uses_german_titles_and_no_space_before_colons() -> None:
    html = CVHtmlBuilder().build(make_cv(), None, GERMAN_LABELS)

    assert 'lang="de"' in html
    assert "Berufserfahrung" in html
    assert "<strong>Telefon:</strong>" in html


def test_english_cv_uses_english_titles() -> None:
    html = CVHtmlBuilder().build(make_cv(), None, ENGLISH_LABELS)

    assert "Professional experience" in html
    assert "<strong>Phone:</strong>" in html


def test_french_cv_keeps_the_space_before_the_colon() -> None:
    html = CVHtmlBuilder().build(make_cv(), None, FRENCH_LABELS)

    assert "<strong>Téléphone :</strong>" in html


def test_skill_groups_and_languages_follow_the_colon_style() -> None:
    html = CVHtmlBuilder().build(make_cv(), None, ENGLISH_LABELS)

    assert "<strong>Back-end:</strong>" in html
    assert "French: Fluent" in html


def test_arabic_cv_is_right_to_left_with_arabic_titles() -> None:
    html = CVHtmlBuilder().build(make_cv(), None, ARABIC_LABELS)

    assert 'dir="rtl"' in html
    assert 'lang="ar"' in html
    assert "الخبرات المهنية" in html
    assert "<strong>الهاتف:</strong>" in html


def test_contact_details_are_isolated_from_the_text_direction() -> None:
    cv_html = CVHtmlBuilder().build(make_cv(), None, ARABIC_LABELS)
    letter_html = LetterHtmlBuilder().build(make_letter(), lang="ar", direction="rtl")

    assert "<bdi>jane@example.com</bdi>" in cv_html
    assert "<bdi>+00 000 000 000</bdi>" in cv_html
    assert "<bdi>jane@example.com</bdi>" in letter_html


def test_letter_blocks_follow_the_writing_direction_and_keep_line_breaks() -> None:
    html = LetterHtmlBuilder().build(make_letter())

    assert "text-align: end" in html
    assert "text-align: right" not in html
    assert "white-space: pre-line" in html


def test_an_arabic_cv_renders_on_one_page() -> None:
    html = CVHtmlBuilder().build(make_cv(), None, ARABIC_LABELS)

    with chromium_required():
        pdf = PlaywrightPdfConverter().to_pdf(html)

    assert pdf.startswith(b"%PDF")
    assert PyMuPdfPageCounter().count(pdf) == 1


def test_an_arabic_letter_renders_on_one_page() -> None:
    html = LetterHtmlBuilder().build(make_letter(), lang="ar", direction="rtl")

    with chromium_required():
        pdf = PlaywrightPdfConverter().to_pdf(html)

    assert PyMuPdfPageCounter().count(pdf) == 1


def test_a_german_cv_renders_on_one_page() -> None:
    html = CVHtmlBuilder().build(make_cv(), None, GERMAN_LABELS)

    with chromium_required():
        pdf = PlaywrightPdfConverter().to_pdf(html)

    assert PyMuPdfPageCounter().count(pdf) == 1
