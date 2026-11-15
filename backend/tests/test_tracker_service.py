import uuid
from dataclasses import replace
from typing import Any, Literal

import pytest
from sqlalchemy import Engine

from app.domain.document import InvalidPhotoError
from app.domain.tracker import ApplicationNotFoundError, InvalidTrackerInputError
from app.infrastructure.db.postgres_tracker import PostgresApplicationRepository
from app.infrastructure.photo_sanitizer import PillowPhotoSanitizer
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.tracker_service import (
    MAX_NOTES_CHARS,
    MAX_TITLE_CHARS,
    SaveRequest,
    TrackerService,
    document_filename,
    name_part,
)
from tests.db_helpers import add_user
from tests.test_application_service import FAKE_PDF, FakeConverter
from tests.test_docx_parser import make_png
from tests.test_letter_html_builder import make_letter
from tests.test_render_service import make_service as make_render_service
from tests.test_tailoring_guard import make_cv


def make_tracker(engine: Engine) -> tuple[TrackerService, FakeConverter]:
    render_service, converter = make_render_service()
    repository = PostgresApplicationRepository(engine)
    return TrackerService(repository, render_service, PillowPhotoSanitizer()), converter


def make_request(**changes: Any) -> SaveRequest:
    base = SaveRequest(
        job_title="Stagiaire DataLab",
        company="Coface",
        language="fr",
        source_url="https://example.com/job",
        status="saved",
        cv=make_cv(),
        letter=make_letter(),
    )
    return replace(base, **changes)


@pytest.fixture
def owner(clean_engine: Engine) -> uuid.UUID:
    return add_user(clean_engine, "owner@example.com")


def test_saves_an_application_and_keeps_both_pdfs(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, converter = make_tracker(clean_engine)

    summary = service.save(owner, make_request())

    assert (summary.job_title, summary.company, summary.status) == (
        "Stagiaire DataLab",
        "Coface",
        "saved",
    )
    files = service.files(owner, summary.id)
    assert (files.cv_pdf, files.letter_pdf) == (FAKE_PDF, FAKE_PDF)
    assert len(converter.pages) == 2


def test_the_pdfs_are_rendered_from_the_edited_text(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, converter = make_tracker(clean_engine)
    edited = make_cv().model_copy(update={"profile": "Edited by the user."})

    service.save(owner, make_request(cv=edited))

    assert "Edited by the user." in converter.pages[0]


def test_a_photo_is_embedded_in_the_saved_cv(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, converter = make_tracker(clean_engine)

    service.save(owner, make_request(photo_bytes=make_png(300, 353)))

    assert "data:image/png;base64," in converter.pages[0]


def test_title_and_company_are_cleaned(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, _ = make_tracker(clean_engine)

    summary = service.save(
        owner, make_request(job_title="  Data \n  Intern\t", company="  Acme   Corp ")
    )

    assert (summary.job_title, summary.company) == ("Data Intern", "Acme Corp")


def test_a_title_is_required(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, _ = make_tracker(clean_engine)

    with pytest.raises(InvalidTrackerInputError, match="job title is required"):
        service.save(owner, make_request(job_title="   "))


def test_a_title_that_is_too_long_is_refused(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, _ = make_tracker(clean_engine)

    with pytest.raises(InvalidTrackerInputError, match="too long"):
        service.save(owner, make_request(job_title="x" * (MAX_TITLE_CHARS + 1)))


def test_a_company_is_optional(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, _ = make_tracker(clean_engine)

    assert service.save(owner, make_request(company="")).company == ""


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "ftp://example.com/x",
        "not a link",
        "https:///nohost",
        "https://" + "a" * 2100,
    ],
)
def test_a_link_that_is_not_a_web_address_is_dropped(
    clean_engine: Engine, owner: uuid.UUID, url: str
) -> None:
    service, _ = make_tracker(clean_engine)

    assert service.save(owner, make_request(source_url=url)).source_url == ""


def test_a_web_link_is_kept(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, _ = make_tracker(clean_engine)

    summary = service.save(owner, make_request(source_url=" https://example.com/job?id=1 "))

    assert summary.source_url == "https://example.com/job?id=1"


def test_an_invalid_photo_saves_nothing(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, _ = make_tracker(clean_engine)

    with pytest.raises(InvalidPhotoError):
        service.save(owner, make_request(photo_bytes=b"not an image"))

    assert service.list_applications(owner) == []


def test_an_unsupported_language_saves_nothing(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, _ = make_tracker(clean_engine)

    with pytest.raises(UnsupportedLetterLanguageError):
        service.save(owner, make_request(language="other"))

    assert service.list_applications(owner) == []


def test_updates_the_status_and_the_notes(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, _ = make_tracker(clean_engine)
    saved = service.save(owner, make_request())

    updated = service.update(owner, saved.id, "applied", "  Sent on the website.  ")

    assert (updated.status, updated.notes) == ("applied", "Sent on the website.")


def test_an_unknown_status_is_refused(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, _ = make_tracker(clean_engine)
    saved = service.save(owner, make_request())

    with pytest.raises(InvalidTrackerInputError, match="Unknown status"):
        service.update(owner, saved.id, "hired")


def test_notes_that_are_too_long_are_refused(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, _ = make_tracker(clean_engine)
    saved = service.save(owner, make_request())

    with pytest.raises(InvalidTrackerInputError, match="too long"):
        service.update(owner, saved.id, notes="x" * (MAX_NOTES_CHARS + 1))


def test_deleting_removes_the_application(clean_engine: Engine, owner: uuid.UUID) -> None:
    service, _ = make_tracker(clean_engine)
    saved = service.save(owner, make_request())

    service.delete(owner, saved.id)

    assert service.list_applications(owner) == []


def test_another_user_cannot_read_or_change_an_application(
    clean_engine: Engine, owner: uuid.UUID
) -> None:
    service, _ = make_tracker(clean_engine)
    stranger = add_user(clean_engine, "stranger@example.com")
    saved = service.save(owner, make_request())

    assert service.list_applications(stranger) == []
    with pytest.raises(ApplicationNotFoundError):
        service.get(stranger, saved.id)
    with pytest.raises(ApplicationNotFoundError):
        service.update(stranger, saved.id, "rejected")
    with pytest.raises(ApplicationNotFoundError):
        service.files(stranger, saved.id)
    with pytest.raises(ApplicationNotFoundError):
        service.delete(stranger, saved.id)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Loqman MAKOURI", "Loqman_Makouri"),
        ("  jean-pierre   dupont ", "Jean_Pierre_Dupont"),
        ("Hélène Müller", "Helene_Muller"),
        ("Ronald McDonald", "Ronald_McDonald"),
        ('Evil"; filename="x', "Evil_Filename_X"),
        ("لقمان", ""),
        ("", ""),
    ],
)
def test_name_part_makes_a_safe_name(name: str, expected: str) -> None:
    assert name_part(name) == expected


@pytest.mark.parametrize(
    ("kind", "language", "expected"),
    [
        ("cv", "fr", "CV_Loqman_Makouri.pdf"),
        ("cv", "de", "CV_Loqman_Makouri.pdf"),
        ("letter", "fr", "Lettre_de_motivation_Loqman_Makouri.pdf"),
        ("letter", "de", "Anschreiben_Loqman_Makouri.pdf"),
        ("letter", "en", "Cover_Letter_Loqman_Makouri.pdf"),
        ("letter", "ar", "Cover_Letter_Loqman_Makouri.pdf"),
    ],
)
def test_document_filename_uses_the_name_of_the_person(
    kind: Literal["cv", "letter"], language: str, expected: str
) -> None:
    assert document_filename(kind, "Loqman MAKOURI", language) == expected


def test_a_name_without_latin_letters_keeps_a_clean_file_name() -> None:
    assert document_filename("cv", "لقمان", "ar") == "CV.pdf"
