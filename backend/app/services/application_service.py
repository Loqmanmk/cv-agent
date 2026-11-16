import logging
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import PurePath

from app.domain.cv import CV
from app.domain.document import (
    MAX_CV_BYTES,
    DocumentParser,
    ExtractedImage,
    InvalidPhotoError,
    ParsedDocument,
    PhotoSanitizer,
)
from app.domain.job import JobOffer, OfferLanguage
from app.domain.letter import CoverLetter, Gender, LetterSender
from app.domain.llm import LLMProvider
from app.domain.pdf import PdfConverter, PdfPageCounter
from app.services.cv_structurer import CVStructurer
from app.services.cv_tailor import CVTailor
from app.services.cv_translator import CVTranslator
from app.services.document_renderer import CVHtmlRenderer, DocumentRenderer, LetterHtmlRenderer
from app.services.job_analyzer import JobAnalyzer
from app.services.language_detector import detect_language
from app.services.letter_assembler import LetterAssembler
from app.services.letter_conventions import conventions_for
from app.services.letter_writer import LetterWriter
from app.services.masking_llm_provider import MaskingLLMProvider
from app.services.match_report import MatchReport, build_match_report
from app.services.photo_selector import PhotoSelector

logger = logging.getLogger(__name__)

SIGNATURES = {".docx": b"PK", ".pdf": b"%PDF"}


class InvalidApplicationInputError(Exception):
    """Raised when the uploaded CV file is not acceptable."""


def check_cv_file(filename: str, content: bytes, allowed: Collection[str] = SIGNATURES) -> str:
    """The extension of an acceptable CV file, or InvalidApplicationInputError."""
    extension = PurePath(filename).suffix.lower()
    if extension not in allowed:
        raise InvalidApplicationInputError(
            f"Unsupported file type. Use: {', '.join(sorted(allowed))}"
        )
    if not content:
        raise InvalidApplicationInputError("The CV file is empty.")
    if len(content) > MAX_CV_BYTES:
        raise InvalidApplicationInputError("The CV file is too large (5 MB maximum).")
    signature = SIGNATURES.get(extension)
    if signature and not content.startswith(signature):
        raise InvalidApplicationInputError("The file content does not match its extension.")
    return extension


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
    cv_language: OfferLanguage = "fr"


@dataclass(frozen=True)
class ApplicationResult:
    offer: JobOffer
    original_cv: CV
    cv: CV
    letter: CoverLetter
    cv_pdf: bytes
    letter_pdf: bytes
    photo: ExtractedImage | None
    report: MatchReport

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
        logger.info("stage: analyzing the job offer")
        offer = JobAnalyzer(self._public_llm).analyze(request.job_text)
        conventions_for(offer.language)  # fail early, before spending more AI calls
        logger.info("stage: structuring the CV")
        cv = CVStructurer(self._private_llm).structure(parsed.text)
        # The language the CV is really written in wins over the setting of the profile, so a
        # CV already in the language of the offer is never sent to a pointless translation.
        cv_language = detect_language(parsed.text) or request.cv_language
        if cv_language != offer.language:
            logger.info("stage: translating the CV from %s to %s", cv_language, offer.language)
            cv = CVTranslator(self._private_llm).translate(cv, offer.language)
        logger.info("stage: tailoring the CV")
        tailored = CVTailor(self._private_llm).tailor(cv, offer)
        logger.info("stage: writing the letter")
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
        logger.info("stage: rendering the PDFs")
        documents = self._renderer.render(tailored, letter, photo, offer.language)
        return ApplicationResult(
            offer=offer,
            original_cv=cv,
            cv=tailored,
            letter=letter,
            cv_pdf=documents.cv_pdf,
            letter_pdf=documents.letter_pdf,
            photo=photo,
            report=build_match_report(cv, tailored, offer),
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
        extension = check_cv_file(request.cv_filename, request.cv_content, self._parsers)
        return self._safe_parse(self._parsers[extension], request.cv_content)

    @staticmethod
    def _safe_parse(parser: DocumentParser, content: bytes) -> ParsedDocument:
        try:
            return parser.parse(content)
        except Exception as exc:  # untrusted file: any parser failure is an input problem
            raise InvalidApplicationInputError("The CV file could not be read.") from exc
