import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from app.domain.cv import CV
from app.domain.document import PhotoSanitizer
from app.domain.letter import CoverLetter
from app.domain.tracker import (
    ApplicationFiles,
    ApplicationRepository,
    ApplicationStatus,
    ApplicationSummary,
    InvalidTrackerInputError,
    NewApplication,
    is_status,
)
from app.services.render_service import RenderRequest, RenderService

MAX_TITLE_CHARS = 200
MAX_COMPANY_CHARS = 200
MAX_URL_CHARS = 2000
MAX_NOTES_CHARS = 5000


@dataclass(frozen=True)
class SaveRequest:
    job_title: str
    company: str
    language: str
    source_url: str
    status: ApplicationStatus
    cv: CV
    letter: CoverLetter
    photo_bytes: bytes | None = None


DocumentKind = Literal["cv", "letter"]
LETTER_PREFIXES = {"fr": "Lettre_de_motivation", "de": "Anschreiben"}
DEFAULT_LETTER_PREFIX = "Cover_Letter"


def name_part(full_name: str) -> str:
    """The person's name as a safe file name part: "Loqman MAKOURI" -> "Loqman_Makouri".

    Only ASCII letters and digits are kept, so the name is safe in any download header.
    """
    ascii_text = unicodedata.normalize("NFKD", full_name).encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[A-Za-z0-9]+", ascii_text)
    return "_".join(
        word.capitalize() if word.isupper() else word[:1].upper() + word[1:] for word in words
    )


def document_filename(kind: DocumentKind, applicant_name: str, language: str) -> str:
    """CV_Loqman_Makouri.pdf, Lettre_de_motivation_Loqman_Makouri.pdf, Cover_Letter_....pdf"""
    prefix = "CV" if kind == "cv" else LETTER_PREFIXES.get(language, DEFAULT_LETTER_PREFIX)
    name = name_part(applicant_name)
    return f"{prefix}_{name}.pdf" if name else f"{prefix}.pdf"


def _one_line(value: str, limit: int, label: str, required: bool = False) -> str:
    text = "".join(char for char in " ".join(value.split()) if char.isprintable())
    if required and not text:
        raise InvalidTrackerInputError(f"The {label} is required.")
    if len(text) > limit:
        raise InvalidTrackerInputError(f"The {label} is too long ({limit} characters maximum).")
    return text


def _safe_source_url(value: str) -> str:
    """Keep the link only if it is an http(s) address, because it will be shown as a link."""
    url = value.strip()
    if not url or len(url) > MAX_URL_CHARS or any(char.isspace() for char in url):
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    return url if parts.scheme in ("http", "https") and parts.netloc else ""


class TrackerService:
    """Saves the applications of a user and follows their status."""

    def __init__(
        self,
        repository: ApplicationRepository,
        renderer: RenderService,
        sanitizer: PhotoSanitizer,
    ) -> None:
        self._repository = repository
        self._renderer = renderer
        self._sanitizer = sanitizer

    def save(self, user_id: uuid.UUID, request: SaveRequest) -> ApplicationSummary:
        title = _one_line(request.job_title, MAX_TITLE_CHARS, "job title", required=True)
        company = _one_line(request.company, MAX_COMPANY_CHARS, "company name")
        photo = self._sanitizer.sanitize(request.photo_bytes).data if request.photo_bytes else None
        documents = self._renderer.render(
            RenderRequest(request.cv, request.letter, request.language, photo)
        )
        return self._repository.add(
            user_id,
            NewApplication(
                job_title=title,
                company=company,
                language=request.language,
                source_url=_safe_source_url(request.source_url),
                status=request.status,
                cv_json=request.cv.model_dump_json(),
                letter_json=request.letter.model_dump_json(),
                photo=photo,
                cv_pdf=documents.cv_pdf,
                letter_pdf=documents.letter_pdf,
            ),
        )

    def list_applications(self, user_id: uuid.UUID) -> list[ApplicationSummary]:
        return self._repository.list_all(user_id)

    def get(self, user_id: uuid.UUID, application_id: int) -> ApplicationSummary:
        return self._repository.get(user_id, application_id)

    def update(
        self,
        user_id: uuid.UUID,
        application_id: int,
        status: str | None = None,
        notes: str | None = None,
    ) -> ApplicationSummary:
        if status is not None and not is_status(status):
            raise InvalidTrackerInputError("Unknown status.")
        clean_notes = notes.strip() if notes is not None else None
        if clean_notes is not None and len(clean_notes) > MAX_NOTES_CHARS:
            raise InvalidTrackerInputError(
                f"The notes are too long ({MAX_NOTES_CHARS} characters)."
            )
        valid_status = status if status is not None and is_status(status) else None
        return self._repository.update(user_id, application_id, valid_status, clean_notes)

    def delete(self, user_id: uuid.UUID, application_id: int) -> None:
        self._repository.delete(user_id, application_id)

    def files(self, user_id: uuid.UUID, application_id: int) -> ApplicationFiles:
        return self._repository.files(user_id, application_id)
