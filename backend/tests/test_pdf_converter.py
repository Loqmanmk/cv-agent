import pymupdf
import pytest
from playwright.sync_api import Error as PlaywrightError

from app.domain.cv_labels import FRENCH_LABELS
from app.infrastructure.cv_html_builder import CVHtmlBuilder
from app.infrastructure.pdf_converter import PlaywrightPdfConverter
from tests.test_tailoring_guard import make_cv


def test_converts_the_cv_to_a_one_page_pdf() -> None:
    html = CVHtmlBuilder().build(make_cv(), None, FRENCH_LABELS)

    try:
        pdf = PlaywrightPdfConverter().to_pdf(html)
    except PlaywrightError:
        pytest.skip("Chromium is not installed: run 'uv run playwright install chromium'")

    assert pdf.startswith(b"%PDF")
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        assert document.page_count == 1
        assert "Jane Doe" in document[0].get_text()
