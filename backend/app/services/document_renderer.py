from dataclasses import dataclass
from typing import Protocol

from app.domain.cv import CV
from app.domain.cv_labels import LABELS_BY_LANGUAGE, CVLabels
from app.domain.document import ExtractedImage
from app.domain.letter import CoverLetter
from app.domain.pdf import PdfConverter, PdfPageCounter
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.page_fitter import LADDER, LETTER_LADDER, FitSettings, OnePageFitter


class CVHtmlRenderer(Protocol):
    def build(
        self,
        cv: CV,
        photo: ExtractedImage | None,
        labels: CVLabels,
        font_size: float,
        spacing: float,
    ) -> str: ...


class LetterHtmlRenderer(Protocol):
    def build(
        self,
        letter: CoverLetter,
        font_size: float,
        spacing: float,
        lang: str,
        direction: str,
    ) -> str: ...


@dataclass(frozen=True)
class RenderedDocuments:
    cv_pdf: bytes
    letter_pdf: bytes | None


class DocumentRenderer:
    """Renders a CV, and its cover letter when there is one, to one-page PDFs."""

    def __init__(
        self,
        converter: PdfConverter,
        counter: PdfPageCounter,
        cv_html: CVHtmlRenderer,
        letter_html: LetterHtmlRenderer,
    ) -> None:
        self._converter = converter
        self._counter = counter
        self._cv_html = cv_html
        self._letter_html = letter_html

    def render(
        self,
        cv: CV,
        letter: CoverLetter | None,
        photo: ExtractedImage | None,
        language: str,
    ) -> RenderedDocuments:
        labels = LABELS_BY_LANGUAGE.get(language)
        if labels is None:
            raise UnsupportedLetterLanguageError(f"No document layout for '{language}' yet.")
        return RenderedDocuments(
            cv_pdf=self._render_cv(cv, photo, labels),
            letter_pdf=self._render_letter(letter, labels) if letter is not None else None,
        )

    def _render_cv(self, cv: CV, photo: ExtractedImage | None, labels: CVLabels) -> bytes:
        def render(settings: FitSettings) -> bytes:
            html = self._cv_html.build(cv, photo, labels, settings.font_size, settings.spacing)
            return self._converter.to_pdf(html)

        return OnePageFitter(self._counter, LADDER).fit(render).pdf

    def _render_letter(self, letter: CoverLetter, labels: CVLabels) -> bytes:
        def render(settings: FitSettings) -> bytes:
            html = self._letter_html.build(
                letter, settings.font_size, settings.spacing, labels.lang, labels.direction
            )
            return self._converter.to_pdf(html)

        return OnePageFitter(self._counter, LETTER_LADDER).fit(render).pdf
