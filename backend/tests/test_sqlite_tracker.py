from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.domain.tracker import ApplicationNotFoundError, NewApplication
from app.infrastructure.sqlite_tracker import SqliteApplicationRepository


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        value = self.now
        self.now += timedelta(minutes=1)
        return value


def make_new(title: str = "Developer", company: str = "Acme") -> NewApplication:
    return NewApplication(
        job_title=title,
        company=company,
        language="fr",
        source_url="https://example.com/job",
        status="saved",
        cv_json='{"cv": 1}',
        letter_json='{"letter": 1}',
        photo=b"photo",
        cv_pdf=b"%PDF-cv",
        letter_pdf=b"%PDF-letter",
    )


def make_repository(tmp_path: Path) -> SqliteApplicationRepository:
    return SqliteApplicationRepository(tmp_path / "tracker.db", Clock())


def test_adds_an_application_with_an_id_a_date_and_no_notes(tmp_path: Path) -> None:
    summary = make_repository(tmp_path).add(make_new())

    assert summary.id == 1
    assert summary.created_at == datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
    assert (summary.job_title, summary.company, summary.status) == ("Developer", "Acme", "saved")
    assert summary.notes == ""


def test_lists_the_newest_application_first(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.add(make_new("First"))
    repository.add(make_new("Second"))

    assert [item.job_title for item in repository.list_all()] == ["Second", "First"]


def test_an_empty_tracker_lists_nothing(tmp_path: Path) -> None:
    assert make_repository(tmp_path).list_all() == []


def test_gets_one_application(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    added = repository.add(make_new())

    assert repository.get(added.id) == added


def test_updates_the_status_and_keeps_the_notes(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    added = repository.add(make_new())
    repository.update(added.id, None, "Called the recruiter")

    updated = repository.update(added.id, "applied", None)

    assert (updated.status, updated.notes) == ("applied", "Called the recruiter")


def test_updates_the_notes_and_keeps_the_status(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    added = repository.add(make_new())
    repository.update(added.id, "interview", None)

    updated = repository.update(added.id, None, "Interview on Monday")

    assert (updated.status, updated.notes) == ("interview", "Interview on Monday")


def test_an_update_without_changes_returns_the_application(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    added = repository.add(make_new())

    assert repository.update(added.id, None, None) == added


def test_deletes_an_application(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    added = repository.add(make_new())

    repository.delete(added.id)

    assert repository.list_all() == []


def test_returns_the_stored_pdfs(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    added = repository.add(make_new())

    files = repository.files(added.id)

    assert (files.cv_pdf, files.letter_pdf) == (b"%PDF-cv", b"%PDF-letter")


def test_unknown_applications_are_reported(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)

    with pytest.raises(ApplicationNotFoundError):
        repository.get(99)
    with pytest.raises(ApplicationNotFoundError):
        repository.update(99, "applied", None)
    with pytest.raises(ApplicationNotFoundError):
        repository.delete(99)
    with pytest.raises(ApplicationNotFoundError):
        repository.files(99)


def test_the_data_survives_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "tracker.db"
    SqliteApplicationRepository(path).add(make_new("Kept"))

    reopened = SqliteApplicationRepository(path)

    assert [item.job_title for item in reopened.list_all()] == ["Kept"]


def test_the_folder_of_the_database_is_created(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "folder" / "tracker.db"

    SqliteApplicationRepository(path)

    assert path.exists()


def test_sql_in_the_data_is_stored_as_plain_text(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    hostile = "x'); DROP TABLE applications; --"

    repository.add(make_new(hostile, hostile))
    repository.update(1, None, hostile)

    stored = repository.get(1)
    assert (stored.job_title, stored.company, stored.notes) == (hostile, hostile, hostile)
    assert len(repository.list_all()) == 1
