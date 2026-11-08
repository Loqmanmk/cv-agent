import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from docx import Document
from docx.document import Document as DocxDocument
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image, UnidentifiedImageError

from app.domain.document import DocumentParser, ExtractedImage, ParsedDocument

MAX_UNPACKED_BYTES = 50_000_000
MAX_ARCHIVE_ENTRIES = 2000


def _check_archive(content: bytes) -> None:
    """Refuse a DOCX that would unpack to far more than any real CV."""
    with zipfile.ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise ValueError("The document contains too many files.")
    if sum(entry.file_size for entry in entries) > MAX_UNPACKED_BYTES:
        raise ValueError("The document is too large once unpacked.")


def _image_size(blob: bytes) -> tuple[int, int] | None:
    """The size of an image, or None when it cannot be read (an EMF logo, a damaged file...)."""
    try:
        with Image.open(BytesIO(blob)) as image:
            return image.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None


class DocxParser(DocumentParser):
    """Reads text and images from a .docx file."""

    def parse(self, content: bytes) -> ParsedDocument:
        _check_archive(content)
        document = Document(BytesIO(content))
        return ParsedDocument(
            text=self._extract_text(document),
            images=self._extract_images(document),
        )

    def _extract_text(self, document: DocxDocument) -> str:
        lines: list[str] = []
        for block in document.iter_inner_content():
            if isinstance(block, Paragraph):
                lines.append(block.text)
            elif isinstance(block, Table):
                lines.extend(self._table_lines(block))
        return "\n".join(line for line in lines if line.strip())

    @staticmethod
    def _table_lines(table: Table) -> list[str]:
        lines: list[str] = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            unique_cells = list(dict.fromkeys(cell for cell in cells if cell))
            lines.append(" | ".join(unique_cells))
        return lines

    @staticmethod
    def _extract_images(document: DocxDocument) -> list[ExtractedImage]:
        images: list[ExtractedImage] = []
        for relation in document.part.rels.values():
            if relation.reltype != RT.IMAGE or relation.is_external:
                continue
            blob = relation.target_part.blob
            size = _image_size(blob)
            if size is None:
                continue
            extension = PurePosixPath(relation.target_ref).suffix or ".png"
            images.append(ExtractedImage(blob, extension, size[0], size[1]))
        return images
