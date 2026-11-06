from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pymupdf
import pytest
from playwright.sync_api import Error as PlaywrightError

from app.domain.cv import CV
from app.domain.cv_labels import FRENCH_LABELS
from app.infrastructure.cv_html_builder import CVHtmlBuilder
from app.infrastructure.pdf_converter import PlaywrightPdfConverter
from app.infrastructure.pdf_page_counter import PyMuPdfPageCounter
from app.services.page_fitter import FitSettings, OnePageFitter, PageOverflowError
from tests.test_tailoring_guard import make_cv


@contextmanager
def chromium_required() -> Iterator[None]:
    try:
        yield
    except PlaywrightError:
        pytest.skip("Chromium is not installed: run 'uv run playwright install chromium'")


def render_with(cv: CV) -> Callable[[FitSettings], bytes]:
    builder = CVHtmlBuilder()
    converter = PlaywrightPdfConverter()

    def render(settings: FitSettings) -> bytes:
        html = builder.build(cv, None, FRENCH_LABELS, settings.font_size, settings.spacing)
        return converter.to_pdf(html)

    return render


def test_page_counter_counts_pages() -> None:
    document = pymupdf.open()
    document.new_page()
    document.new_page()

    assert PyMuPdfPageCounter().count(bytes(document.tobytes())) == 2


def test_a_normal_cv_keeps_the_default_layout() -> None:
    with chromium_required():
        result = OnePageFitter(PyMuPdfPageCounter()).fit(render_with(make_cv()))

    assert result.settings == FitSettings(9.0, 1.0)


def test_an_oversized_cv_is_refused_with_a_clear_error() -> None:
    cv = make_cv()
    long_experience = cv.experiences[0].model_copy(update={"bullets": ["A long bullet"] * 300})
    oversized = cv.model_copy(update={"experiences": [long_experience]})
    ladder = [FitSettings(9.0, 1.0), FitSettings(8.0, 0.5)]

    with chromium_required(), pytest.raises(PageOverflowError):
        OnePageFitter(PyMuPdfPageCounter(), ladder).fit(render_with(oversized))
