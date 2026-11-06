import pymupdf

from app.domain.pdf import PdfPageCounter


class PyMuPdfPageCounter(PdfPageCounter):
    """Counts PDF pages with PyMuPDF."""

    def count(self, pdf: bytes) -> int:
        with pymupdf.open(stream=pdf, filetype="pdf") as document:
            return int(document.page_count)
