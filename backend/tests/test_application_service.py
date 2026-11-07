from datetime import date
from io import BytesIO

import pymupdf
import pytest
from docx import Document
from pydantic import BaseModel

from app.domain.job import JobOffer, OfferLanguage
from app.domain.pdf import PdfConverter, PdfPageCounter
from app.infrastructure.cv_html_builder import CVHtmlBuilder
from app.infrastructure.docx_parser import DocxParser
from app.infrastructure.letter_html_builder import LetterHtmlBuilder
from app.infrastructure.pdf_parser import PdfParser
from app.services.application_service import (
    MAX_CV_BYTES,
    ApplicationRequest,
    ApplicationService,
    InvalidApplicationInputError,
)
from app.services.letter_conventions import UnsupportedLetterLanguageError
from tests.fakes import SequenceLLMProvider
from tests.test_docx_parser import make_png
from tests.test_letter_guard import make_body
from tests.test_tailoring_guard import make_cv

FAKE_PDF = b"%PDF-fake"
CV_LINES = ("Jane Doe", "Software Engineer", "jane@example.com", "+00 000 000 000")


class FakeConverter(PdfConverter):
    def __init__(self) -> None:
        self.pages: list[str] = []

    def to_pdf(self, html: str) -> bytes:
        self.pages.append(html)
        return FAKE_PDF


class OnePageCounter(PdfPageCounter):
    def count(self, pdf: bytes) -> int:
        return 1


def make_offer(language: OfferLanguage = "fr") -> JobOffer:
    return JobOffer(
        title="Stagiaire", company="Acme", language=language, contract_type="internship"
    )


def ai_answers() -> list[BaseModel]:
    tailored = make_cv().model_copy(update={"profile": "Rewritten profile."})
    return [make_offer(), make_cv(), tailored, make_body()]


def make_service(
    answers: list[BaseModel],
) -> tuple[ApplicationService, SequenceLLMProvider, FakeConverter]:
    provider = SequenceLLMProvider(answers)
    converter = FakeConverter()
    service = ApplicationService(
        llm=provider,
        converter=converter,
        counter=OnePageCounter(),
        cv_html=CVHtmlBuilder(),
        letter_html=LetterHtmlBuilder(),
        parsers={".docx": DocxParser(), ".pdf": PdfParser()},
    )
    return service, provider, converter


def make_docx(with_photo: bool = False) -> bytes:
    document = Document()
    for line in CV_LINES:
        document.add_paragraph(line)
    if with_photo:
        document.add_picture(BytesIO(make_png(300, 353)))
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    for index, line in enumerate(CV_LINES):
        page.insert_text((72, 72 + 20 * index), line)
    return bytes(document.tobytes())


def make_request(
    filename: str = "cv.docx",
    content: bytes | None = None,
    include_photo: bool = True,
) -> ApplicationRequest:
    return ApplicationRequest(
        cv_filename=filename,
        cv_content=make_docx() if content is None else content,
        job_text="Acme seeks an intern.",
        address="Oujda, Maroc",
        city="Oujda",
        gender="m",
        today=date(2026, 11, 6),
        include_photo=include_photo,
    )


def test_creates_the_tailored_cv_and_the_letter_pdfs() -> None:
    service, _, converter = make_service(ai_answers())

    result = service.create(make_request())

    assert result.cv_pdf == FAKE_PDF
    assert result.letter_pdf == FAKE_PDF
    assert result.cv.profile == "Rewritten profile."
    assert "Rewritten profile." in converter.pages[0]
    assert "Fait à Oujda, le 6 novembre 2026" in converter.pages[1]


def test_the_photo_of_the_upload_is_embedded_in_the_cv() -> None:
    service, _, converter = make_service(ai_answers())

    result = service.create(make_request(content=make_docx(with_photo=True)))

    assert result.photo_used is True
    assert "data:image/png;base64," in converter.pages[0]


def test_the_photo_can_be_disabled() -> None:
    service, _, converter = make_service(ai_answers())

    result = service.create(make_request(content=make_docx(with_photo=True), include_photo=False))

    assert result.photo_used is False
    assert "<img" not in converter.pages[0]


def test_a_file_without_a_photo_reports_it() -> None:
    service, _, _ = make_service(ai_answers())

    assert service.create(make_request()).photo_used is False


def test_pdf_uploads_are_supported() -> None:
    service, _, _ = make_service(ai_answers())

    result = service.create(make_request(filename="CV.PDF", content=make_pdf()))

    assert result.cv.header.name == "Jane Doe"


def test_contact_details_never_reach_the_ai_for_cv_calls() -> None:
    service, provider, _ = make_service(ai_answers())

    service.create(make_request())

    cv_prompts = [prompt for _, prompt in provider.calls[1:]]
    assert len(cv_prompts) == 3
    assert all("jane@example.com" not in prompt for prompt in cv_prompts)
    assert all("+00 000 000 000" not in prompt for prompt in cv_prompts)


def test_an_unsupported_file_type_is_refused_before_any_ai_call() -> None:
    service, provider, _ = make_service([])

    with pytest.raises(InvalidApplicationInputError, match="Unsupported file type"):
        service.create(make_request(filename="cv.exe"))

    assert provider.calls == []


def test_an_empty_file_is_refused() -> None:
    service, provider, _ = make_service([])

    with pytest.raises(InvalidApplicationInputError, match="empty"):
        service.create(make_request(content=b""))

    assert provider.calls == []


def test_a_file_that_is_too_large_is_refused() -> None:
    service, provider, _ = make_service([])

    with pytest.raises(InvalidApplicationInputError, match="too large"):
        service.create(make_request(content=b"x" * (MAX_CV_BYTES + 1)))

    assert provider.calls == []


def test_an_unsupported_offer_language_stops_after_one_ai_call() -> None:
    service, provider, _ = make_service([make_offer(language="de")])

    with pytest.raises(UnsupportedLetterLanguageError):
        service.create(make_request())

    assert len(provider.calls) == 1


def test_a_file_that_does_not_match_its_extension_is_refused() -> None:
    service, provider, _ = make_service([])

    with pytest.raises(InvalidApplicationInputError, match="does not match"):
        service.create(make_request(filename="cv.pdf", content=make_docx()))

    assert provider.calls == []


def test_a_corrupted_file_gives_a_clean_error() -> None:
    service, provider, _ = make_service([])

    with pytest.raises(InvalidApplicationInputError, match="could not be read"):
        service.create(make_request(content=b"PK-not-a-real-zip"))

    assert provider.calls == []
