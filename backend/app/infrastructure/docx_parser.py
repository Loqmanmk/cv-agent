from io import BytesIO
from pathlib import PurePosixPath

from docx import Document
from docx.document import Document as DocxDocument
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image

from app.domain.document import DocumentParser, ExtractedImage, ParsedDocument


class DocxParser(DocumentParser):
    """Reads text and images from a .docx file."""

    def parse(self, content: bytes) -> ParsedDocument:
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
            with Image.open(BytesIO(blob)) as image:
                width, height = image.size
            extension = PurePosixPath(relation.target_ref).suffix or ".png"
            images.append(ExtractedImage(blob, extension, width, height))
        return images
