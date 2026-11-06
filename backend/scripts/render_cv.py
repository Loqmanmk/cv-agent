import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.domain.cv import CV
from app.domain.cv_labels import FRENCH_LABELS
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


def main() -> None:
    cv_file = DATA / "extracted" / "tailored_cv.json"
    cv = CV.model_validate_json(cv_file.read_text(encoding="utf-8"))
    photo = load_photo(DATA / "extracted" / "image1.png")
    builder = CVHtmlBuilder()
    converter = PlaywrightPdfConverter()

    def render(settings: FitSettings) -> bytes:
        html = builder.build(cv, photo, FRENCH_LABELS, settings.font_size, settings.spacing)
        return converter.to_pdf(html)

    try:
        result = OnePageFitter(PyMuPdfPageCounter()).fit(render)
    except PageOverflowError as error:
        sys.exit(f"Failed: {error}")

    settings = result.settings
    html = builder.build(cv, photo, FRENCH_LABELS, settings.font_size, settings.spacing)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "cv.html").write_text(html, encoding="utf-8")
    (OUTPUT / "cv.pdf").write_bytes(result.pdf)
    print(f"Saved to {OUTPUT / 'cv.pdf'}")
    print(f"1 page, font {settings.font_size} pt, spacing {settings.spacing}")


if __name__ == "__main__":
    main()
