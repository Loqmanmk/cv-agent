from io import BytesIO

from docx import Document
from PIL import Image

from app.infrastructure.docx_parser import DocxParser


def make_png(width: int, height: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def make_docx(*, with_image: bool = False) -> bytes:
    document = Document()
    document.add_paragraph("Jane Doe")
    document.add_paragraph("Software Engineer")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Python"
    table.rows[0].cells[1].text = "FastAPI"
    if with_image:
        document.add_picture(BytesIO(make_png(30, 40)))
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_extracts_paragraph_text() -> None:
    result = DocxParser().parse(make_docx())

    assert "Jane Doe" in result.text
    assert "Software Engineer" in result.text


def test_extracts_table_text() -> None:
    result = DocxParser().parse(make_docx())

    assert "Python | FastAPI" in result.text


def test_keeps_document_order() -> None:
    result = DocxParser().parse(make_docx())

    assert result.text.index("Jane Doe") < result.text.index("Python")


def test_extracts_image_with_its_size() -> None:
    result = DocxParser().parse(make_docx(with_image=True))

    assert len(result.images) == 1
    assert result.images[0].extension == ".png"
    assert (result.images[0].width, result.images[0].height) == (30, 40)


def test_document_without_image_has_no_images() -> None:
    result = DocxParser().parse(make_docx())

    assert result.images == []
