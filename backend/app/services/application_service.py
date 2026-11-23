import logging
from collections.abc import Callable, Collection, Mapping
from concurrent.futures import ThreadPoolExecutor
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
from app.domain.jobs import Stage
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
from app.services.reading_cache import ReadingCache, key_of

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
    # The CV already read by the AI on an earlier application, to skip reading it again.
    structured_cv: CV | None = None
    # Without a letter, the application is faster: one AI step and one PDF less.
    include_letter: bool = True


@dataclass(frozen=True)
class ScoreRequest:
    """What is needed to score a CV against an offer, before creating anything."""

    cv_filename: str
    cv_content: bytes
    job_text: str
    structured_cv: CV | None = None


@dataclass(frozen=True)
class MatchPreview:
    offer: JobOffer
    # The CV as read from the file: it can be kept with the saved CV for next time.
    structured_cv: CV
    report: MatchReport


@dataclass(frozen=True)
class ApplicationResult:
    offer: JobOffer
    # The CV as read from the file, before any translation: it can be reused next time.
    structured_cv: CV
    original_cv: CV
    cv: CV
    letter: CoverLetter | None
    cv_pdf: bytes
    letter_pdf: bytes | None
    photo: ExtractedImage | None
    report: MatchReport

    @property
    def photo_used(self) -> bool:
        return self.photo is not None


def _ignore_stage(_stage: Stage) -> None:
    return None


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
        offers: ReadingCache[JobOffer] | None = None,
        structures: ReadingCache[CV] | None = None,
    ) -> None:
        self._public_llm = llm
        self._private_llm = MaskingLLMProvider(llm)
        self._renderer = DocumentRenderer(converter, counter, cv_html, letter_html)
        self._parsers = parsers
        self._photo_sanitizer = photo_sanitizer
        self._offers = offers if offers is not None else ReadingCache[JobOffer]()
        self._structures = structures if structures is not None else ReadingCache[CV]()

    def preview(self, request: ScoreRequest) -> MatchPreview:
        """How well the CV fits the offer, before spending anything on documents.

        Only the offer and the CV are read; what was read is kept a short while, so creating
        the application just after does not read them again.
        """
        extension = check_cv_file(request.cv_filename, request.cv_content, self._parsers)
        if request.structured_cv is not None:
            offer, cv = self._analyze(request.job_text), request.structured_cv
        else:
            parsed = self._safe_parse(self._parsers[extension], request.cv_content)
            offer, cv = self._offer_and_structure(request.job_text, request.cv_content, parsed)
        return MatchPreview(offer=offer, structured_cv=cv, report=build_match_report(cv, cv, offer))

    def create(
        self, request: ApplicationRequest, on_stage: Callable[[Stage], None] = _ignore_stage
    ) -> ApplicationResult:
        """on_stage is told each step as it starts, so the page can show the progress."""
        on_stage("reading")
        parsed = self._parse(request)
        offer, structured = self._read_offer_and_cv(request, parsed)
        cv = structured
        # The language the CV is really written in wins over the setting of the profile, so a
        # CV already in the language of the offer is never sent to a pointless translation.
        cv_language = detect_language(parsed.text) or request.cv_language
        if cv_language != offer.language:
            logger.info("stage: translating the CV from %s to %s", cv_language, offer.language)
            on_stage("translating")
            cv = CVTranslator(self._private_llm).translate(cv, offer.language)
        on_stage("tailoring")
        tailored, letter = self._tailor_and_write(cv, offer, request)
        photo = self._select_photo(parsed.images, request.include_photo)
        logger.info("stage: rendering the PDFs")
        on_stage("rendering")
        documents = self._renderer.render(tailored, letter, photo, offer.language)
        return ApplicationResult(
            offer=offer,
            structured_cv=structured,
            original_cv=cv,
            cv=tailored,
            letter=letter,
            cv_pdf=documents.cv_pdf,
            letter_pdf=documents.letter_pdf,
            photo=photo,
            report=build_match_report(cv, tailored, offer),
        )

    def _tailor_and_write(
        self, cv: CV, offer: JobOffer, request: ApplicationRequest
    ) -> tuple[CV, CoverLetter | None]:
        """The tailored CV and the letter, written at the same time.

        The letter is written from the full CV, which holds the same true facts as the
        tailored one, so it does not have to wait for the tailoring.
        """
        if not request.include_letter:
            logger.info("stage: tailoring the CV (no letter asked)")
            return CVTailor(self._private_llm).tailor(cv, offer), None
        logger.info("stage: tailoring the CV and writing the letter at the same time")
        with ThreadPoolExecutor(max_workers=1) as pool:
            letter = pool.submit(self._write_letter, cv, offer, request)
            tailored = CVTailor(self._private_llm).tailor(cv, offer)
            return tailored, letter.result()

    def _write_letter(self, cv: CV, offer: JobOffer, request: ApplicationRequest) -> CoverLetter:
        body = LetterWriter(self._private_llm).write(cv, offer, request.gender)
        sender = LetterSender(
            name=cv.header.name,
            email=cv.header.email,
            phone=cv.header.phone,
            address=request.address,
            city=request.city,
            gender=request.gender,
        )
        return LetterAssembler().assemble(body, offer, sender, request.today)

    def _read_offer_and_cv(
        self, request: ApplicationRequest, parsed: ParsedDocument
    ) -> tuple[JobOffer, CV]:
        if request.structured_cv is not None:
            logger.info("stage: analyzing the job offer (the saved CV is already read)")
            return self._analyze(request.job_text), request.structured_cv
        return self._offer_and_structure(request.job_text, request.cv_content, parsed)

    def _offer_and_structure(
        self, job_text: str, cv_content: bytes, parsed: ParsedDocument
    ) -> tuple[JobOffer, CV]:
        """The offer and the CV, read at the same time since neither needs the other."""
        logger.info("stage: analyzing the job offer and structuring the CV at the same time")
        with ThreadPoolExecutor(max_workers=1) as pool:
            offer = pool.submit(self._analyze, job_text)
            cv = self._structures.get_or_make(
                key_of(cv_content), lambda: CVStructurer(self._private_llm).structure(parsed.text)
            )
            return offer.result(), cv

    def _analyze(self, job_text: str) -> JobOffer:
        offer = self._offers.get_or_make(
            key_of(job_text), lambda: JobAnalyzer(self._public_llm).analyze(job_text)
        )
        conventions_for(offer.language)  # fail early, before spending more AI calls
        return offer

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
