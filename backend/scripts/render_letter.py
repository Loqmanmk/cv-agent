import sys
from pathlib import Path

from app.domain.letter import CoverLetter
from app.infrastructure.letter_html_builder import LetterHtmlBuilder
from app.infrastructure.pdf_converter import PlaywrightPdfConverter
from app.infrastructure.pdf_page_counter import PyMuPdfPageCounter
from app.services.page_fitter import LETTER_LADDER, FitSettings, OnePageFitter, PageOverflowError

DATA = Path("../data")
OUTPUT = DATA / "output"


def main() -> None:
    letter_file = DATA / "extracted" / "letter.json"
    letter = CoverLetter.model_validate_json(letter_file.read_text(encoding="utf-8"))
    builder = LetterHtmlBuilder()
    converter = PlaywrightPdfConverter()

    def render(settings: FitSettings) -> bytes:
        return converter.to_pdf(builder.build(letter, settings.font_size, settings.spacing))

    try:
        result = OnePageFitter(PyMuPdfPageCounter(), LETTER_LADDER).fit(render)
    except PageOverflowError as error:
        sys.exit(f"Failed: {error}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "letter.pdf").write_bytes(result.pdf)
    print(f"Saved to {OUTPUT / 'letter.pdf'}")
    print(f"1 page, font {result.settings.font_size} pt, spacing {result.settings.spacing}")


if __name__ == "__main__":
    main()
