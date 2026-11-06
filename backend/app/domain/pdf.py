from abc import ABC, abstractmethod


class PdfConverter(ABC):
    """Contract for anything that can turn an HTML page into a PDF."""

    @abstractmethod
    def to_pdf(self, html: str) -> bytes:
        """Return the PDF bytes of the rendered HTML page."""
