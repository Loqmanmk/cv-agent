from io import BytesIO

import pymupdf
from PIL import Image

from app.infrastructure.pdf_parser import PdfParser


def make_png(width: int, height: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def make_pdf(*, with_text: bool = True, with_image: bool = False) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    if with_text:
        page.insert_text((72, 72), "Jane Doe")
        page.insert_text((72, 100), "Software Engineer")
    if with_image:
        page.insert_image(pymupdf.Rect(72, 150, 132, 230), stream=make_png(30, 40))
    return bytes(document.tobytes())


def test_extracts_text() -> None:
    result = PdfParser().parse(make_pdf())

    assert "Jane Doe" in result.text
    assert "Software Engineer" in result.text


def test_keeps_reading_order() -> None:
    result = PdfParser().parse(make_pdf())

    assert result.text.index("Jane Doe") < result.text.index("Software Engineer")


def test_extracts_image_with_its_size() -> None:
    result = PdfParser().parse(make_pdf(with_image=True))

    assert len(result.images) == 1
    assert result.images[0].extension == ".png"
    assert (result.images[0].width, result.images[0].height) == (30, 40)


def test_pdf_without_image_has_no_images() -> None:
    result = PdfParser().parse(make_pdf())

    assert result.images == []


def test_pdf_without_text_layer_gives_empty_text() -> None:
    result = PdfParser().parse(make_pdf(with_text=False))

    assert result.text == ""


def test_same_image_on_two_pages_is_extracted_once() -> None:
    document = pymupdf.open()
    first_page = document.new_page()
    xref = first_page.insert_image(pymupdf.Rect(72, 72, 132, 152), stream=make_png(30, 40))
    second_page = document.new_page()
    second_page.insert_image(pymupdf.Rect(72, 72, 132, 152), xref=xref)

    result = PdfParser().parse(bytes(document.tobytes()))

    assert len(result.images) == 1
