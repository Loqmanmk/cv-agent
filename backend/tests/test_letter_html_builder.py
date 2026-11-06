from collections.abc import Callable

import pymupdf
import pytest

from app.domain.letter import CoverLetter, RecipientBlock, SenderBlock
from app.infrastructure.letter_html_builder import LetterHtmlBuilder
from app.infrastructure.pdf_converter import PlaywrightPdfConverter
from app.infrastructure.pdf_page_counter import PyMuPdfPageCounter
from app.services.page_fitter import LETTER_LADDER, FitSettings, OnePageFitter, PageOverflowError
from tests.test_page_fitting_integration import chromium_required


def make_letter(
    name: str = "Jane Doe",
    company: str = "Acme",
    contact: str = "",
    address: str = "",
    paragraphs: list[str] | None = None,
) -> CoverLetter:
    return CoverLetter(
        sender=SenderBlock(
            name=name,
            address="Oujda, Maroc",
            email="jane@example.com",
            phone="+00 000 000 000",
        ),
        recipient=RecipientBlock(contact=contact, company=company, address=address),
        place_date="Fait à Oujda, le 6 novembre 2026",
        subject="Objet : Candidature pour le poste de Stagiaire",
        greeting="Madame, Monsieur,",
        paragraphs=paragraphs or ["First paragraph.", "Second one.", "Third one.", "Closing."],
        signature="Jane Doe",
    )


def render_with(letter: CoverLetter) -> Callable[[FitSettings], bytes]:
    builder = LetterHtmlBuilder()
    converter = PlaywrightPdfConverter()

    def render(settings: FitSettings) -> bytes:
        return converter.to_pdf(builder.build(letter, settings.font_size, settings.spacing))

    return render


def test_contains_every_part_of_the_letter() -> None:
    html = LetterHtmlBuilder().build(make_letter())

    for text in (
        "Jane Doe",
        "Oujda, Maroc",
        "jane@example.com",
        "Acme",
        "Fait à Oujda, le 6 novembre 2026",
        "Objet : Candidature pour le poste de Stagiaire",
        "Madame, Monsieur,",
        "First paragraph.",
        "Closing.",
    ):
        assert text in html


def test_empty_recipient_lines_are_omitted() -> None:
    html = LetterHtmlBuilder().build(make_letter(company="Acme", contact="", address=""))

    assert html.count('class="recipient-line"') == 1


def test_all_recipient_lines_are_shown_when_present() -> None:
    letter = make_letter(contact="Mme Martin", address="1 rue Exemple, Paris")

    assert LetterHtmlBuilder().build(letter).count('class="recipient-line"') == 3


def test_html_in_the_content_is_escaped() -> None:
    html = LetterHtmlBuilder().build(make_letter(name="<script>alert(1)</script>"))

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_text_direction_is_a_parameter() -> None:
    html = LetterHtmlBuilder().build(make_letter(), lang="ar", direction="rtl")

    assert 'dir="rtl"' in html
    assert 'lang="ar"' in html


def test_a_normal_letter_fits_one_page_with_the_default_layout() -> None:
    paragraphs = [" ".join(["mot"] * 80)] * 4

    with chromium_required():
        result = OnePageFitter(PyMuPdfPageCounter(), LETTER_LADDER).fit(
            render_with(make_letter(paragraphs=paragraphs))
        )

    assert result.settings == LETTER_LADDER[0]


def test_an_oversized_letter_is_refused() -> None:
    paragraphs = [" ".join(["mot"] * 600)] * 4

    with chromium_required(), pytest.raises(PageOverflowError):
        OnePageFitter(PyMuPdfPageCounter(), LETTER_LADDER).fit(
            render_with(make_letter(paragraphs=paragraphs))
        )


def test_letter_ladder_never_goes_below_the_readability_floor() -> None:
    assert min(setting.font_size for setting in LETTER_LADDER) >= 9.5


def test_company_block_is_aligned_with_the_date_on_the_right() -> None:
    letter = make_letter(company="Acme")

    with chromium_required():
        pdf = PlaywrightPdfConverter().to_pdf(LetterHtmlBuilder().build(letter))

    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        page = document[0]
        company = page.search_for("Acme")[0]
        date_line = page.search_for(letter.place_date)[0]

    assert abs(company.x1 - date_line.x1) < 2
