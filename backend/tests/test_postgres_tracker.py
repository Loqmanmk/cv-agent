import uuid

import pytest
from sqlalchemy import Engine, text

from app.domain.tracker import ApplicationNotFoundError, NewApplication
from app.infrastructure.db.postgres_tracker import PostgresApplicationRepository
from tests.db_helpers import add_user

MISSING_ID = 10**9


def make_new(title: str = "Developer", company: str = "Acme") -> NewApplication:
    return NewApplication(
        job_title=title,
        company=company,
        language="fr",
        source_url="https://example.com/job",
        status="saved",
        cv_json='{"header": {"name": "Jane Doe"}, "profile": "Hello"}',
        letter_json='{"subject": "Hi"}',
        photo=b"photo",
        cv_pdf=b"%PDF-cv",
        letter_pdf=b"%PDF-letter",
    )


@pytest.fixture
def repository(clean_engine: Engine) -> PostgresApplicationRepository:
    return PostgresApplicationRepository(clean_engine)


@pytest.fixture
def owner(clean_engine: Engine) -> uuid.UUID:
    return add_user(clean_engine, "owner@example.com")


@pytest.fixture
def stranger(clean_engine: Engine) -> uuid.UUID:
    return add_user(clean_engine, "stranger@example.com")


def test_adds_an_application_with_an_id_a_date_and_no_notes(
    repository: PostgresApplicationRepository, owner: uuid.UUID
) -> None:
    summary = repository.add(owner, make_new())

    assert summary.id >= 1
    assert summary.created_at.tzinfo is not None
    assert (summary.job_title, summary.company, summary.status) == ("Developer", "Acme", "saved")
    assert summary.notes == ""


def test_gets_what_was_added(repository: PostgresApplicationRepository, owner: uuid.UUID) -> None:
    added = repository.add(owner, make_new())

    assert repository.get(owner, added.id) == added


def test_lists_the_newest_first_and_only_the_applications_of_the_user(
    repository: PostgresApplicationRepository, owner: uuid.UUID, stranger: uuid.UUID
) -> None:
    repository.add(owner, make_new("First"))
    repository.add(stranger, make_new("Not yours"))
    repository.add(owner, make_new("Second"))

    assert [item.job_title for item in repository.list_all(owner)] == ["Second", "First"]
    assert [item.job_title for item in repository.list_all(stranger)] == ["Not yours"]


def test_an_empty_tracker_lists_nothing(
    repository: PostgresApplicationRepository, owner: uuid.UUID
) -> None:
    assert repository.list_all(owner) == []


def test_updates_the_status_and_keeps_the_notes(
    repository: PostgresApplicationRepository, owner: uuid.UUID
) -> None:
    added = repository.add(owner, make_new())
    repository.update(owner, added.id, None, "Called the recruiter")

    updated = repository.update(owner, added.id, "applied", None)

    assert (updated.status, updated.notes) == ("applied", "Called the recruiter")


def test_updates_the_notes_and_keeps_the_status(
    repository: PostgresApplicationRepository, owner: uuid.UUID
) -> None:
    added = repository.add(owner, make_new())
    repository.update(owner, added.id, "interview", None)

    updated = repository.update(owner, added.id, None, "Interview on Monday")

    assert (updated.status, updated.notes) == ("interview", "Interview on Monday")


def test_an_update_without_changes_returns_the_application(
    repository: PostgresApplicationRepository, owner: uuid.UUID
) -> None:
    added = repository.add(owner, make_new())

    assert repository.update(owner, added.id, None, None) == added


def test_deletes_an_application(
    repository: PostgresApplicationRepository, owner: uuid.UUID
) -> None:
    added = repository.add(owner, make_new())

    repository.delete(owner, added.id)

    assert repository.list_all(owner) == []


def test_returns_the_stored_pdfs(
    repository: PostgresApplicationRepository, owner: uuid.UUID
) -> None:
    added = repository.add(owner, make_new())

    files = repository.files(owner, added.id)

    assert (files.cv_pdf, files.letter_pdf) == (b"%PDF-cv", b"%PDF-letter")
    assert files.applicant_name == "Jane Doe"


def test_unknown_applications_are_reported(
    repository: PostgresApplicationRepository, owner: uuid.UUID
) -> None:
    with pytest.raises(ApplicationNotFoundError):
        repository.get(owner, MISSING_ID)
    with pytest.raises(ApplicationNotFoundError):
        repository.update(owner, MISSING_ID, "applied", None)
    with pytest.raises(ApplicationNotFoundError):
        repository.delete(owner, MISSING_ID)
    with pytest.raises(ApplicationNotFoundError):
        repository.files(owner, MISSING_ID)


def test_another_user_cannot_touch_an_application(
    repository: PostgresApplicationRepository, owner: uuid.UUID, stranger: uuid.UUID
) -> None:
    added = repository.add(owner, make_new())

    with pytest.raises(ApplicationNotFoundError):
        repository.get(stranger, added.id)
    with pytest.raises(ApplicationNotFoundError):
        repository.update(stranger, added.id, "rejected", "stolen")
    with pytest.raises(ApplicationNotFoundError):
        repository.delete(stranger, added.id)
    with pytest.raises(ApplicationNotFoundError):
        repository.files(stranger, added.id)

    untouched = repository.get(owner, added.id)
    assert (untouched.status, untouched.notes) == ("saved", "")


def test_the_cv_and_the_letter_are_stored_as_json_documents(
    repository: PostgresApplicationRepository, owner: uuid.UUID, clean_engine: Engine
) -> None:
    repository.add(owner, make_new())

    with clean_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT jsonb_typeof(cv_json) AS kind, "
                "cv_json->>'profile' AS profile FROM applications"
            )
        ).one()

    assert (row.kind, row.profile) == ("object", "Hello")


def test_sql_in_the_data_is_stored_as_plain_text(
    repository: PostgresApplicationRepository, owner: uuid.UUID, clean_engine: Engine
) -> None:
    hostile = "x'); DROP TABLE applications; --"

    added = repository.add(owner, make_new(hostile, hostile))
    repository.update(owner, added.id, None, hostile)

    stored = repository.get(owner, added.id)
    assert (stored.job_title, stored.company, stored.notes) == (hostile, hostile, hostile)
    with clean_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM applications")).scalar_one() == 1
