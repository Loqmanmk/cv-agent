import uuid

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, Engine, create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError

from app.domain.tracker import STATUSES
from app.infrastructure.db.models import Base
from tests.conftest import alembic_config

INSERT_APPLICATION = text(
    "INSERT INTO applications "
    "(user_id, job_title, company, language, source_url, status, cv_json, letter_json, "
    "cv_pdf, letter_pdf) "
    "VALUES (:user_id, 'Developer', 'Acme', 'fr', '', :status, '{}', '{}', :pdf, :pdf)"
)


def add_user(connection: Connection, email: str = "jane@example.com") -> uuid.UUID:
    result = connection.execute(
        text("INSERT INTO users (email, password_hash) VALUES (:email, 'hash') RETURNING id"),
        {"email": email},
    )
    user_id = result.scalar_one()
    assert isinstance(user_id, uuid.UUID)
    return user_id


def add_application(connection: Connection, user_id: uuid.UUID, status: str = "saved") -> None:
    connection.execute(INSERT_APPLICATION, {"user_id": user_id, "status": status, "pdf": b"%PDF"})


def count_applications(connection: Connection) -> int:
    return int(connection.execute(text("SELECT count(*) FROM applications")).scalar_one())


def test_the_migration_creates_both_tables_with_the_expected_columns(clean_engine: Engine) -> None:
    inspector = inspect(clean_engine)

    assert set(inspector.get_table_names()) == {
        "users",
        "applications",
        "sessions",
        "profiles",
        "usage_events",
        "email_tokens",
        "alembic_version",
    }
    assert {column["name"] for column in inspector.get_columns("users")} == {
        "id",
        "email",
        "password_hash",
        "is_active",
        "email_verified_at",
        "plan",
        "created_at",
    }
    assert {column["name"] for column in inspector.get_columns("applications")} == {
        "id",
        "user_id",
        "created_at",
        "job_title",
        "company",
        "language",
        "source_url",
        "status",
        "notes",
        "cv_json",
        "letter_json",
        "photo",
        "cv_pdf",
        "letter_pdf",
    }


def test_the_models_match_the_migration(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})

        assert compare_metadata(context, Base.metadata) == []


def test_the_migration_can_be_undone(empty_database: URL) -> None:
    config = alembic_config(empty_database)
    command.upgrade(config, "head")

    command.downgrade(config, "base")

    engine = create_engine(empty_database)
    try:
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    finally:
        engine.dispose()


def test_the_applications_index_serves_the_listing_of_one_user(clean_engine: Engine) -> None:
    indexes = {
        index["name"]: index["column_names"]
        for index in inspect(clean_engine).get_indexes("applications")
    }

    assert indexes["ix_applications_user_id_id"] == ["user_id", "id"]


def test_a_new_user_gets_a_random_id_and_safe_defaults(clean_engine: Engine) -> None:
    with clean_engine.begin() as connection:
        user_id = add_user(connection)
        row = connection.execute(
            text("SELECT is_active, email_verified_at, created_at FROM users WHERE id = :id"),
            {"id": user_id},
        ).one()

    assert row.is_active is True
    assert row.email_verified_at is None
    assert row.created_at.tzinfo is not None


def test_two_users_cannot_share_an_email(clean_engine: Engine) -> None:
    with clean_engine.begin() as connection:
        add_user(connection, "jane@example.com")

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_user(connection, "jane@example.com")


def test_an_email_must_be_stored_in_lowercase(clean_engine: Engine) -> None:
    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_user(connection, "Jane@Example.com")


def test_an_application_has_defaults_and_an_optional_photo(clean_engine: Engine) -> None:
    with clean_engine.begin() as connection:
        add_application(connection, add_user(connection))
        row = connection.execute(
            text("SELECT id, notes, photo, created_at FROM applications")
        ).one()

    assert row.id == 1
    assert row.notes == ""
    assert row.photo is None
    assert row.created_at.tzinfo is not None


@pytest.mark.parametrize("status", STATUSES)
def test_every_status_of_the_application_is_accepted(clean_engine: Engine, status: str) -> None:
    with clean_engine.begin() as connection:
        add_application(connection, add_user(connection), status)

        assert count_applications(connection) == 1


def test_an_unknown_status_is_refused(clean_engine: Engine) -> None:
    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_application(connection, add_user(connection), "hired")


def test_an_application_must_belong_to_an_existing_user(clean_engine: Engine) -> None:
    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_application(connection, uuid.uuid4())


def test_deleting_a_user_deletes_their_applications_only(clean_engine: Engine) -> None:
    with clean_engine.begin() as connection:
        first = add_user(connection, "first@example.com")
        second = add_user(connection, "second@example.com")
        add_application(connection, first)
        add_application(connection, second)

        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": first})

        assert count_applications(connection) == 1
