import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.domain.cv import CV
from app.domain.cv_labels import LABELS_BY_LANGUAGE
from app.domain.document import ExtractedImage
from app.infrastructure.cv_html_builder import CVHtmlBuilder
from app.infrastructure.pdf_converter import PlaywrightPdfConverter
from app.infrastructure.pdf_page_counter import PyMuPdfPageCounter
from app.services.page_fitter import FitSettings, OnePageFitter, PageOverflowError

DATA = Path("../data")
OUTPUT = DATA / "output"


def load_photo(path: Path) -> ExtractedImage:
    content = path.read_bytes()
    with Image.open(BytesIO(content)) as image:
        width, height = image.size
    return ExtractedImage(content, path.suffix, width, height)


def main(language: str) -> None:
    labels = LABELS_BY_LANGUAGE.get(language)
    if labels is None:
        sys.exit(f"Language must be one of: {', '.join(LABELS_BY_LANGUAGE)}")
    cv_file = DATA / "extracted" / "tailored_cv.json"
    cv = CV.model_validate_json(cv_file.read_text(encoding="utf-8"))
    photo = load_photo(DATA / "extracted" / "image1.png")
    builder = CVHtmlBuilder()
    converter = PlaywrightPdfConverter()

    def render(settings: FitSettings) -> bytes:
        html = builder.build(cv, photo, labels, settings.font_size, settings.spacing)
        return converter.to_pdf(html)

    try:
        result = OnePageFitter(PyMuPdfPageCounter()).fit(render)
    except PageOverflowError as error:
        sys.exit(f"Failed: {error}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f"cv_{language}.pdf"
    target.write_bytes(result.pdf)
    print(f"Saved to {target}")
    print(f"1 page, font {result.settings.font_size} pt, spacing {result.settings.spacing}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fr")
