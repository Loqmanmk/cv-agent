import zipfile
from io import BytesIO

import pymupdf
import pytest

from app.infrastructure import pdf_parser
from app.infrastructure.docx_parser import MAX_ARCHIVE_ENTRIES, MAX_UNPACKED_BYTES, DocxParser
from app.infrastructure.pdf_parser import MAX_PAGES, PdfParser
from tests.test_docx_parser import make_docx
from tests.test_pdf_parser import make_pdf


def zip_with(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def docx_with_broken_image() -> bytes:
    original = zipfile.ZipFile(BytesIO(make_docx(with_image=True)))
    entries = {
        info.filename: b"this is not an image"
        if info.filename.startswith("word/media/")
        else original.read(info.filename)
        for info in original.infolist()
    }
    return zip_with(entries)


def test_a_docx_that_unpacks_to_far_too_much_is_refused() -> None:
    bomb = zip_with({"word/document.xml": b"\0" * (MAX_UNPACKED_BYTES + 1)})

    assert len(bomb) < 1_000_000
    with pytest.raises(ValueError, match="too large once unpacked"):
        DocxParser().parse(bomb)


def test_a_docx_with_too_many_files_is_refused() -> None:
    crowded = zip_with({f"file{index}.txt": b"x" for index in range(MAX_ARCHIVE_ENTRIES + 1)})

    with pytest.raises(ValueError, match="too many files"):
        DocxParser().parse(crowded)


def test_a_normal_docx_is_still_read() -> None:
    assert "Jane Doe" in DocxParser().parse(make_docx()).text


def test_an_image_that_cannot_be_read_is_skipped_and_the_text_is_kept() -> None:
    result = DocxParser().parse(docx_with_broken_image())

    assert "Jane Doe" in result.text
    assert result.images == []


def test_a_pdf_with_too_many_pages_is_refused() -> None:
    document = pymupdf.open()
    for _ in range(MAX_PAGES + 1):
        document.new_page()

    with pytest.raises(ValueError, match="too many pages"):
        PdfParser().parse(bytes(document.tobytes()))


def test_a_normal_pdf_is_still_read() -> None:
    assert "Jane Doe" in PdfParser().parse(make_pdf()).text


def test_a_pdf_image_with_too_many_pixels_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_pdf_parser import make_png

    document = pymupdf.open()
    page = document.new_page()
    page.insert_image(pymupdf.Rect(72, 72, 132, 152), stream=make_png(30, 40))
    monkeypatch.setattr(pdf_parser, "MAX_IMAGE_PIXELS", 100)

    assert PdfParser().parse(bytes(document.tobytes())).images == []
