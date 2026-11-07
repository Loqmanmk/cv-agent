import sys
from pathlib import Path

from app.domain.cv_labels import LABELS_BY_LANGUAGE
from app.domain.letter import CoverLetter
from app.infrastructure.letter_html_builder import LetterHtmlBuilder
from app.infrastructure.pdf_converter import PlaywrightPdfConverter
from app.infrastructure.pdf_page_counter import PyMuPdfPageCounter
from app.services.page_fitter import LETTER_LADDER, FitSettings, OnePageFitter, PageOverflowError

DATA = Path("../data")
OUTPUT = DATA / "output"


def main(language: str) -> None:
    labels = LABELS_BY_LANGUAGE.get(language)
    if labels is None:
        sys.exit(f"Language must be one of: {', '.join(LABELS_BY_LANGUAGE)}")
    letter_file = DATA / "extracted" / f"letter_{language}.json"
    letter = CoverLetter.model_validate_json(letter_file.read_text(encoding="utf-8"))
    builder = LetterHtmlBuilder()
    converter = PlaywrightPdfConverter()

    def render(settings: FitSettings) -> bytes:
        html = builder.build(
            letter, settings.font_size, settings.spacing, labels.lang, labels.direction
        )
        return converter.to_pdf(html)

    try:
        result = OnePageFitter(PyMuPdfPageCounter(), LETTER_LADDER).fit(render)
    except PageOverflowError as error:
        sys.exit(f"Failed: {error}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f"letter_{language}.pdf"
    target.write_bytes(result.pdf)
    print(f"Saved to {target}")
    print(f"1 page, font {result.settings.font_size} pt, spacing {result.settings.spacing}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fr")
