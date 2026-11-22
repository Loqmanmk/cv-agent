from dataclasses import dataclass

from app.domain.cv import CV
from app.domain.document import PhotoSanitizer
from app.domain.letter import CoverLetter
from app.services.application_service import InvalidApplicationInputError
from app.services.document_renderer import DocumentRenderer, RenderedDocuments

MAX_DOCUMENT_CHARS = 100_000


@dataclass(frozen=True)
class RenderRequest:
    cv: CV
    letter: CoverLetter | None
    language: str
    photo_bytes: bytes | None = None


class RenderService:
    """Renders documents from data the user has reviewed. No AI is involved."""

    def __init__(self, renderer: DocumentRenderer, sanitizer: PhotoSanitizer) -> None:
        self._renderer = renderer
        self._sanitizer = sanitizer

    def render(self, request: RenderRequest) -> RenderedDocuments:
        letter_size = len(request.letter.model_dump_json()) if request.letter else 0
        size = len(request.cv.model_dump_json()) + letter_size
        if size > MAX_DOCUMENT_CHARS:
            raise InvalidApplicationInputError("The documents are too long.")
        photo = self._sanitizer.sanitize(request.photo_bytes) if request.photo_bytes else None
        return self._renderer.render(request.cv, request.letter, photo, request.language)
