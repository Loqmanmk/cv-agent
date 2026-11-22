import pytest

from app.domain.document import InvalidPhotoError
from app.infrastructure.cv_html_builder import CVHtmlBuilder
from app.infrastructure.letter_html_builder import LetterHtmlBuilder
from app.infrastructure.photo_sanitizer import PillowPhotoSanitizer
from app.services.application_service import InvalidApplicationInputError
from app.services.document_renderer import DocumentRenderer
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.render_service import MAX_DOCUMENT_CHARS, RenderRequest, RenderService
from tests.test_application_service import FAKE_PDF, FakeConverter, OnePageCounter
from tests.test_docx_parser import make_png
from tests.test_letter_html_builder import make_letter
from tests.test_tailoring_guard import make_cv


def make_service() -> tuple[RenderService, FakeConverter]:
    converter = FakeConverter()
    renderer = DocumentRenderer(converter, OnePageCounter(), CVHtmlBuilder(), LetterHtmlBuilder())
    return RenderService(renderer, PillowPhotoSanitizer()), converter


def make_request(photo: bytes | None = None, language: str = "fr") -> RenderRequest:
    return RenderRequest(cv=make_cv(), letter=make_letter(), language=language, photo_bytes=photo)


def test_renders_the_cv_and_the_letter() -> None:
    service, converter = make_service()

    documents = service.render(make_request())

    assert documents.cv_pdf == FAKE_PDF
    assert documents.letter_pdf == FAKE_PDF
    assert any("Jane Doe" in page for page in converter.pages)
    assert any("Objet : Candidature" in page for page in converter.pages)


def test_renders_only_the_cv_without_a_letter() -> None:
    service, converter = make_service()
    request = RenderRequest(cv=make_cv(), letter=None, language="fr")

    documents = service.render(request)

    assert documents.cv_pdf == FAKE_PDF
    assert documents.letter_pdf is None
    assert len(converter.pages) == 1


def test_renders_the_text_as_edited_by_the_user() -> None:
    service, converter = make_service()
    edited = make_cv().model_copy(update={"profile": "Edited by the user."})

    service.render(RenderRequest(edited, make_letter(), "fr"))

    assert any("Edited by the user." in page for page in converter.pages)


def test_embeds_a_sanitized_photo() -> None:
    service, converter = make_service()

    service.render(make_request(photo=make_png(300, 353)))

    assert any("data:image/png;base64," in page for page in converter.pages)


def test_no_photo_means_no_image() -> None:
    service, converter = make_service()

    service.render(make_request(photo=None))

    assert all("<img" not in page for page in converter.pages)


def test_an_empty_photo_is_treated_as_no_photo() -> None:
    service, converter = make_service()

    service.render(make_request(photo=b""))

    assert all("<img" not in page for page in converter.pages)


def test_an_invalid_photo_is_refused() -> None:
    service, _ = make_service()

    with pytest.raises(InvalidPhotoError):
        service.render(make_request(photo=b"not an image"))


def test_an_unsupported_language_is_refused() -> None:
    service, _ = make_service()

    with pytest.raises(UnsupportedLetterLanguageError):
        service.render(make_request(language="other"))


def test_documents_that_are_too_long_are_refused() -> None:
    service, converter = make_service()
    huge = make_cv().model_copy(update={"profile": "x" * MAX_DOCUMENT_CHARS})

    with pytest.raises(InvalidApplicationInputError, match="too long"):
        service.render(RenderRequest(huge, make_letter(), "fr"))

    assert converter.pages == []
