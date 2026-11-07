import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import PurePath

from app.domain.cv import CV
from app.domain.document import (
    DocumentParser,
    ExtractedImage,
    InvalidPhotoError,
    ParsedDocument,
    PhotoSanitizer,
)
from app.domain.job import JobOffer
from app.domain.letter import CoverLetter, Gender, LetterSender
from app.domain.llm import LLMProvider
from app.domain.pdf import PdfConverter, PdfPageCounter
from app.services.cv_structurer import CVStructurer
from app.services.cv_tailor import CVTailor
from app.services.document_renderer import CVHtmlRenderer, DocumentRenderer, LetterHtmlRenderer
from app.services.job_analyzer import JobAnalyzer
from app.services.letter_assembler import LetterAssembler
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.letter_writer import LetterWriter
from app.services.masking_llm_provider import MaskingLLMProvider
from app.services.photo_selector import PhotoSelector

logger = logging.getLogger(__name__)

MAX_CV_BYTES = 5_000_000
SIGNATURES = {".docx": b"PK", ".pdf": b"%PDF"}
# German, English and Arabic need the CV translation step before they can be enabled.
PIPELINE_LANGUAGES = frozenset({"fr"})


class InvalidApplicationInputError(Exception):
    """Raised when the uploaded CV file is not acceptable."""


@dataclass(frozen=True)
class ApplicationRequest:
    cv_filename: str
    cv_content: bytes
    job_text: str
    address: str
    city: str
    gender: Gender
    today: date
    include_photo: bool = True


@dataclass(frozen=True)
class ApplicationResult:
    offer: JobOffer
    original_cv: CV
    cv: CV
    letter: CoverLetter
    cv_pdf: bytes
    letter_pdf: bytes
    photo: ExtractedImage | None

    @property
    def photo_used(self) -> bool:
        return self.photo is not None


class ApplicationService:
    """Produces a tailored CV and a cover letter, both as one-page PDFs."""

    def __init__(
        self,
        llm: LLMProvider,
        converter: PdfConverter,
        counter: PdfPageCounter,
        cv_html: CVHtmlRenderer,
        letter_html: LetterHtmlRenderer,
        parsers: Mapping[str, DocumentParser],
        photo_sanitizer: PhotoSanitizer,
    ) -> None:
        self._public_llm = llm
        self._private_llm = MaskingLLMProvider(llm)
        self._renderer = DocumentRenderer(converter, counter, cv_html, letter_html)
        self._parsers = parsers
        self._photo_sanitizer = photo_sanitizer

    def create(self, request: ApplicationRequest) -> ApplicationResult:
        parsed = self._parse(request)
        logger.info("stage 1/5: analyzing the job offer")
        offer = JobAnalyzer(self._public_llm).analyze(request.job_text)
        if offer.language not in PIPELINE_LANGUAGES:  # fail early, before more AI calls
            message = f"Applications in '{offer.language}' are not available yet."
            raise UnsupportedLetterLanguageError(message)
        logger.info("stage 2/5: structuring the CV")
        cv = CVStructurer(self._private_llm).structure(parsed.text)
        logger.info("stage 3/5: tailoring the CV")
        tailored = CVTailor(self._private_llm).tailor(cv, offer)
        logger.info("stage 4/5: writing the letter")
        body = LetterWriter(self._private_llm).write(tailored, offer, request.gender)
        sender = LetterSender(
            name=tailored.header.name,
            email=tailored.header.email,
            phone=tailored.header.phone,
            address=request.address,
            city=request.city,
            gender=request.gender,
        )
        letter = LetterAssembler().assemble(body, offer, sender, request.today)
        photo = self._select_photo(parsed.images, request.include_photo)
        logger.info("stage 5/5: rendering the PDFs")
        documents = self._renderer.render(tailored, letter, photo, offer.language)
        return ApplicationResult(
            offer=offer,
            original_cv=cv,
            cv=tailored,
            letter=letter,
            cv_pdf=documents.cv_pdf,
            letter_pdf=documents.letter_pdf,
            photo=photo,
        )

    def _select_photo(self, images: list[ExtractedImage], include: bool) -> ExtractedImage | None:
        if not include:
            return None
        candidate = PhotoSelector().select(images)
        if candidate is None:
            return None
        try:
            return self._photo_sanitizer.sanitize(candidate.data)
        except InvalidPhotoError as error:
            logger.warning("the photo of the CV was skipped: %s", error)
            return None

    def _parse(self, request: ApplicationRequest) -> ParsedDocument:
        extension = PurePath(request.cv_filename).suffix.lower()
        parser = self._parsers.get(extension)
        if parser is None:
            allowed = ", ".join(sorted(self._parsers))
            raise InvalidApplicationInputError(f"Unsupported file type. Use: {allowed}")
        if not request.cv_content:
            raise InvalidApplicationInputError("The CV file is empty.")
        if len(request.cv_content) > MAX_CV_BYTES:
            raise InvalidApplicationInputError("The CV file is too large (5 MB maximum).")
        return self._safe_parse(parser, extension, request.cv_content)

    @staticmethod
    def _safe_parse(parser: DocumentParser, extension: str, content: bytes) -> ParsedDocument:
        signature = SIGNATURES.get(extension)
        if signature and not content.startswith(signature):
            raise InvalidApplicationInputError("The file content does not match its extension.")
        try:
            return parser.parse(content)
        except Exception as exc:  # untrusted file: any parser failure is an input problem
            raise InvalidApplicationInputError("The CV file could not be read.") from exc
