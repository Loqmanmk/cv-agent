from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.domain.document import InvalidPhotoError
from app.domain.tracker import InvalidTrackerInputError
from app.infrastructure.photo_sanitizer import PillowPhotoSanitizer
from app.infrastructure.sqlite_tracker import SqliteApplicationRepository
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.tracker_service import (
    MAX_NOTES_CHARS,
    MAX_TITLE_CHARS,
    SaveRequest,
    TrackerService,
    pdf_filename,
    slug,
)
from tests.test_application_service import FAKE_PDF, FakeConverter
from tests.test_docx_parser import make_png
from tests.test_letter_html_builder import make_letter
from tests.test_render_service import make_service as make_render_service
from tests.test_tailoring_guard import make_cv


def make_tracker(tmp_path: Path) -> tuple[TrackerService, FakeConverter]:
    render_service, converter = make_render_service()
    repository = SqliteApplicationRepository(tmp_path / "tracker.db")
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


def test_saves_an_application_and_keeps_both_pdfs(tmp_path: Path) -> None:
    service, converter = make_tracker(tmp_path)

    summary = service.save(make_request())

    assert (summary.job_title, summary.company, summary.status) == (
        "Stagiaire DataLab",
        "Coface",
        "saved",
    )
    files = service.files(summary.id)
    assert (files.cv_pdf, files.letter_pdf) == (FAKE_PDF, FAKE_PDF)
    assert len(converter.pages) == 2


def test_the_pdfs_are_rendered_from_the_edited_text(tmp_path: Path) -> None:
    service, converter = make_tracker(tmp_path)
    edited = make_cv().model_copy(update={"profile": "Edited by the user."})

    service.save(make_request(cv=edited))

    assert "Edited by the user." in converter.pages[0]


def test_a_photo_is_embedded_in_the_saved_cv(tmp_path: Path) -> None:
    service, converter = make_tracker(tmp_path)

    service.save(make_request(photo_bytes=make_png(300, 353)))

    assert "data:image/png;base64," in converter.pages[0]


def test_title_and_company_are_cleaned(tmp_path: Path) -> None:
    service, _ = make_tracker(tmp_path)

    summary = service.save(make_request(job_title="  Data \n  Intern\t", company="  Acme   Corp "))

    assert (summary.job_title, summary.company) == ("Data Intern", "Acme Corp")


def test_a_title_is_required(tmp_path: Path) -> None:
    service, _ = make_tracker(tmp_path)

    with pytest.raises(InvalidTrackerInputError, match="job title is required"):
        service.save(make_request(job_title="   "))


def test_a_title_that_is_too_long_is_refused(tmp_path: Path) -> None:
    service, _ = make_tracker(tmp_path)

    with pytest.raises(InvalidTrackerInputError, match="too long"):
        service.save(make_request(job_title="x" * (MAX_TITLE_CHARS + 1)))


def test_a_company_is_optional(tmp_path: Path) -> None:
    service, _ = make_tracker(tmp_path)

    assert service.save(make_request(company="")).company == ""


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
def test_a_link_that_is_not_a_web_address_is_dropped(tmp_path: Path, url: str) -> None:
    service, _ = make_tracker(tmp_path)

    assert service.save(make_request(source_url=url)).source_url == ""


def test_a_web_link_is_kept(tmp_path: Path) -> None:
    service, _ = make_tracker(tmp_path)

    summary = service.save(make_request(source_url=" https://example.com/job?id=1 "))

    assert summary.source_url == "https://example.com/job?id=1"


def test_an_invalid_photo_saves_nothing(tmp_path: Path) -> None:
    service, _ = make_tracker(tmp_path)

    with pytest.raises(InvalidPhotoError):
        service.save(make_request(photo_bytes=b"not an image"))

    assert service.list_applications() == []


def test_an_unsupported_language_saves_nothing(tmp_path: Path) -> None:
    service, _ = make_tracker(tmp_path)

    with pytest.raises(UnsupportedLetterLanguageError):
        service.save(make_request(language="other"))

    assert service.list_applications() == []


def test_updates_the_status_and_the_notes(tmp_path: Path) -> None:
    service, _ = make_tracker(tmp_path)
    saved = service.save(make_request())

    updated = service.update(saved.id, "applied", "  Sent on the website.  ")

    assert (updated.status, updated.notes) == ("applied", "Sent on the website.")


def test_an_unknown_status_is_refused(tmp_path: Path) -> None:
    service, _ = make_tracker(tmp_path)
    saved = service.save(make_request())

    with pytest.raises(InvalidTrackerInputError, match="Unknown status"):
        service.update(saved.id, "hired")


def test_notes_that_are_too_long_are_refused(tmp_path: Path) -> None:
    service, _ = make_tracker(tmp_path)
    saved = service.save(make_request())

    with pytest.raises(InvalidTrackerInputError, match="too long"):
        service.update(saved.id, notes="x" * (MAX_NOTES_CHARS + 1))


def test_deleting_removes_the_application(tmp_path: Path) -> None:
    service, _ = make_tracker(tmp_path)
    saved = service.save(make_request())

    service.delete(saved.id)

    assert service.list_applications() == []


def test_slug_makes_a_safe_file_name_part() -> None:
    assert slug("Société Générale & Co.") == "societe-generale-co"
    assert slug('Evil"; filename="x') == "evil-filename-x"
    assert slug("") == "application"
    assert slug("شركة") == "application"


def test_pdf_filename() -> None:
    assert pdf_filename("cv", "Coface") == "cv-coface.pdf"
