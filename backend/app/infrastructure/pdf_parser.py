import pymupdf

from app.domain.document import DocumentParser, ExtractedImage, ParsedDocument

MAX_PAGES = 20
MAX_IMAGE_PIXELS = 30_000_000


class PdfParser(DocumentParser):
    """Reads text and images from a PDF file."""

    def parse(self, content: bytes) -> ParsedDocument:
        with pymupdf.open(stream=content, filetype="pdf") as document:
            if document.page_count > MAX_PAGES:
                raise ValueError("The PDF has too many pages.")
            return ParsedDocument(
                text=self._extract_text(document),
                images=self._extract_images(document),
            )

    @staticmethod
    def _extract_text(document: pymupdf.Document) -> str:
        pages = [page.get_text("text", sort=True) for page in document]
        lines = "\n".join(pages).splitlines()
        return "\n".join(line for line in lines if line.strip())

    @staticmethod
    def _extract_images(document: pymupdf.Document) -> list[ExtractedImage]:
        images: list[ExtractedImage] = []
        seen: set[int] = set()
        for page in document:
            for item in page.get_images(full=True):
                xref = item[0]
                if xref in seen:
                    continue
                seen.add(xref)
                if item[2] * item[3] > MAX_IMAGE_PIXELS:
                    continue  # judged from the header, before decoding it
                info = document.extract_image(xref)
                images.append(
                    ExtractedImage(
                        data=info["image"],
                        extension=f".{info['ext']}",
                        width=info["width"],
                        height=info["height"],
                    )
                )
        return images
