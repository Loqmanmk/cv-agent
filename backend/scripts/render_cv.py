from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image

from app.domain.cv import CV
from app.domain.cv_labels import FRENCH_LABELS
from app.domain.document import ExtractedImage
from app.infrastructure.cv_html_builder import CVHtmlBuilder
from app.infrastructure.pdf_converter import PlaywrightPdfConverter

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

    html = CVHtmlBuilder().build(cv, photo, FRENCH_LABELS)
    pdf = PlaywrightPdfConverter().to_pdf(html)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "cv.html").write_text(html, encoding="utf-8")
    (OUTPUT / "cv.pdf").write_bytes(pdf)
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        print(f"Saved to {OUTPUT / 'cv.pdf'} ({document.page_count} page(s))")


if __name__ == "__main__":
    main()
