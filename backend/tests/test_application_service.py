from datetime import date
from io import BytesIO

import pymupdf
import pytest
from docx import Document
from pydantic import BaseModel

from app.domain.cv import CV
from app.domain.document import MAX_CV_BYTES
from app.domain.job import JobOffer, OfferLanguage
from app.domain.pdf import PdfConverter, PdfPageCounter
from app.infrastructure.cv_html_builder import CVHtmlBuilder
from app.infrastructure.docx_parser import DocxParser
from app.infrastructure.letter_html_builder import LetterHtmlBuilder
from app.infrastructure.pdf_parser import PdfParser
from app.infrastructure.photo_sanitizer import PillowPhotoSanitizer
from app.services.application_service import (
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
        photo_sanitizer=PillowPhotoSanitizer(),
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
    cv_language: OfferLanguage = "fr",
    structured_cv: CV | None = None,
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
        cv_language=cv_language,
        structured_cv=structured_cv,
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


def test_an_unsupported_offer_language_stops_before_tailoring() -> None:
    # The offer and the CV are read at the same time, then the pipeline stops.
    service, provider, _ = make_service([make_offer(language="other"), make_cv()])

    with pytest.raises(UnsupportedLetterLanguageError):
        service.create(make_request())

    assert len(provider.calls) == 2


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


def test_a_photo_in_an_unsupported_format_is_skipped_and_not_fatal() -> None:
    from PIL import Image

    gif = BytesIO()
    Image.new("RGB", (300, 353), "white").save(gif, format="GIF")
    document = Document()
    for line in CV_LINES:
        document.add_paragraph(line)
    document.add_picture(BytesIO(gif.getvalue()))
    buffer = BytesIO()
    document.save(buffer)
    service, _, converter = make_service(ai_answers())

    result = service.create(make_request(content=buffer.getvalue()))

    assert result.photo_used is False
    assert "<img" not in converter.pages[0]


def test_the_result_keeps_the_original_cv_next_to_the_tailored_one() -> None:
    service, _, _ = make_service(ai_answers())

    result = service.create(make_request())

    assert result.original_cv.profile == make_cv().profile
    assert result.cv.profile == "Rewritten profile."


def test_a_german_offer_translates_the_cv_before_tailoring() -> None:
    from tests.test_translation_guard import german

    translated = german(make_cv())
    tailored = translated.model_copy(update={"profile": "Neu geschriebenes Profil."})
    answers: list[BaseModel] = [make_offer("de"), make_cv(), translated, tailored, make_body()]
    service, provider, converter = make_service(answers)

    result = service.create(make_request())

    assert len(provider.calls) == 5
    assert "German" in provider.calls[2][0]
    assert result.original_cv.header.headline == "Ingenieurstudentin"
    assert result.cv.profile == "Neu geschriebenes Profil."
    assert "Berufserfahrung" in converter.pages[0]
    assert "Sehr geehrte Damen und Herren," in converter.pages[1]


def test_contact_details_never_reach_the_ai_during_translation() -> None:
    from tests.test_translation_guard import german

    translated = german(make_cv())
    answers: list[BaseModel] = [make_offer("de"), make_cv(), translated, translated, make_body()]
    service, provider, _ = make_service(answers)

    service.create(make_request())

    translation_prompt = provider.calls[2][1]
    assert "jane@example.com" not in translation_prompt
    assert "+00 000 000 000" not in translation_prompt


def test_no_translation_when_the_cv_is_already_in_the_offer_language() -> None:
    answers: list[BaseModel] = [make_offer("de"), make_cv(), make_cv(), make_body()]
    service, provider, _ = make_service(answers)

    service.create(make_request(cv_language="de"))

    assert len(provider.calls) == 4


def docx_with(text: str) -> bytes:
    document = Document()
    for line in (*CV_LINES, text):
        document.add_paragraph(line)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_a_cv_written_in_the_offer_language_is_not_translated_whatever_the_profile_says() -> None:
    from tests.test_language_detector import ENGLISH

    answers: list[BaseModel] = [make_offer("en"), make_cv(), make_cv(), make_body()]
    service, provider, _ = make_service(answers)

    service.create(make_request(content=docx_with(ENGLISH), cv_language="fr"))

    assert len(provider.calls) == 4


def test_a_cv_in_another_language_than_the_profile_says_is_translated() -> None:
    from tests.test_language_detector import FRENCH
    from tests.test_translation_guard import german

    translated = german(make_cv())
    answers: list[BaseModel] = [make_offer("de"), make_cv(), translated, translated, make_body()]
    service, provider, _ = make_service(answers)

    service.create(make_request(content=docx_with(FRENCH), cv_language="de"))

    assert len(provider.calls) == 5
    assert "German" in provider.calls[2][0]


def test_a_cv_already_read_is_not_sent_to_the_ai_again() -> None:
    service, provider, _ = make_service([make_offer(), make_cv(), make_body()])

    result = service.create(make_request(structured_cv=make_cv()))

    assert len(provider.calls) == 3
    assert all("<cv_text>" not in prompt for _, prompt in provider.calls)
    assert result.structured_cv == make_cv()


def test_the_cv_read_from_the_file_is_given_back_to_be_kept() -> None:
    service, _, _ = make_service([make_offer(), make_cv(), make_cv(), make_body()])

    result = service.create(make_request())

    assert result.structured_cv == make_cv()


def test_a_translation_that_breaks_the_guard_stops_the_pipeline() -> None:
    from app.services.translation_guard import TranslationViolationError

    answers: list[BaseModel] = [make_offer("de"), make_cv(), *[make_cv()] * 3]
    service, provider, _ = make_service(answers)

    with pytest.raises(TranslationViolationError):
        service.create(make_request())

    assert len(provider.calls) == 5
