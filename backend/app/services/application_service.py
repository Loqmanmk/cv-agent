import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import PurePath
from typing import Protocol

from app.domain.cv import CV
from app.domain.cv_labels import LABELS_BY_LANGUAGE, CVLabels
from app.domain.document import DocumentParser, ExtractedImage, ParsedDocument
from app.domain.job import JobOffer
from app.domain.letter import CoverLetter, Gender, LetterSender
from app.domain.llm import LLMProvider
from app.domain.pdf import PdfConverter, PdfPageCounter
from app.services.cv_structurer import CVStructurer
from app.services.cv_tailor import CVTailor
from app.services.job_analyzer import JobAnalyzer
from app.services.letter_assembler import LetterAssembler
from app.services.letter_conventions import conventions_for
from app.services.letter_writer import LetterWriter
from app.services.masking_llm_provider import MaskingLLMProvider
from app.services.page_fitter import LADDER, LETTER_LADDER, FitSettings, OnePageFitter
from app.services.photo_selector import PhotoSelector

logger = logging.getLogger(__name__)

MAX_CV_BYTES = 5_000_000
SIGNATURES = {".docx": b"PK", ".pdf": b"%PDF"}


class InvalidApplicationInputError(Exception):
    """Raised when the uploaded CV file is not acceptable."""


class CVHtmlRenderer(Protocol):
    def build(
        self,
        cv: CV,
        photo: ExtractedImage | None,
        labels: CVLabels,
        font_size: float,
        spacing: float,
    ) -> str: ...


class LetterHtmlRenderer(Protocol):
    def build(
        self,
        letter: CoverLetter,
        font_size: float,
        spacing: float,
        lang: str,
        direction: str,
    ) -> str: ...


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
    cv: CV
    letter: CoverLetter
    cv_pdf: bytes
    letter_pdf: bytes
    photo_used: bool


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
    ) -> None:
        self._public_llm = llm
        self._private_llm = MaskingLLMProvider(llm)
        self._converter = converter
        self._counter = counter
        self._cv_html = cv_html
        self._letter_html = letter_html
        self._parsers = parsers

    def create(self, request: ApplicationRequest) -> ApplicationResult:
        parsed = self._parse(request)
        logger.info("stage 1/5: analyzing the job offer")
        offer = JobAnalyzer(self._public_llm).analyze(request.job_text)
        conventions_for(offer.language)  # fail early, before spending more AI calls
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
        photo = PhotoSelector().select(parsed.images) if request.include_photo else None
        logger.info("stage 5/5: rendering the PDFs")
        labels = LABELS_BY_LANGUAGE[offer.language]
        return ApplicationResult(
            offer=offer,
            cv=tailored,
            letter=letter,
            cv_pdf=self._render_cv(tailored, photo, labels),
            letter_pdf=self._render_letter(letter, labels),
            photo_used=photo is not None,
        )

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

    def _render_cv(self, cv: CV, photo: ExtractedImage | None, labels: CVLabels) -> bytes:
        def render(settings: FitSettings) -> bytes:
            html = self._cv_html.build(cv, photo, labels, settings.font_size, settings.spacing)
            return self._converter.to_pdf(html)

        return OnePageFitter(self._counter, LADDER).fit(render).pdf

    def _render_letter(self, letter: CoverLetter, labels: CVLabels) -> bytes:
        def render(settings: FitSettings) -> bytes:
            html = self._letter_html.build(
                letter, settings.font_size, settings.spacing, labels.lang, labels.direction
            )
            return self._converter.to_pdf(html)

        return OnePageFitter(self._counter, LETTER_LADDER).fit(render).pdf
