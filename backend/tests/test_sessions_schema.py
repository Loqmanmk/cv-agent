import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from tests.db_helpers import add_user

CREATED = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
INSERT = text(
    "INSERT INTO sessions (user_id, token_hash, csrf_token, created_at, last_seen_at, expires_at) "
    "VALUES (:user_id, :token_hash, 'csrf', :created, :created, :expires)"
)


def add_session(
    connection: Connection,
    user_id: uuid.UUID,
    token_hash: str | None = None,
    expires: datetime = CREATED + timedelta(days=30),
) -> None:
    connection.execute(
        INSERT,
        {
            "user_id": user_id,
            "token_hash": token_hash or uuid.uuid4().hex,
            "created": CREATED,
            "expires": expires,
        },
    )


def session_count(connection: Connection) -> int:
    return int(connection.execute(text("SELECT count(*) FROM sessions")).scalar_one())


def test_a_session_gets_a_random_id(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)

    with clean_engine.begin() as connection:
        add_session(connection, user_id)
        session_id = connection.execute(text("SELECT id FROM sessions")).scalar_one()

    assert isinstance(session_id, uuid.UUID)


def test_two_sessions_cannot_share_a_token_hash(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)
    with clean_engine.begin() as connection:
        add_session(connection, user_id, "same-hash")

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_session(connection, user_id, "same-hash")


def test_a_session_must_end_after_it_starts(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_session(connection, user_id, expires=CREATED)


def test_a_session_must_belong_to_an_existing_user(clean_engine: Engine) -> None:
    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_session(connection, uuid.uuid4())


def test_deleting_a_user_deletes_their_sessions_only(clean_engine: Engine) -> None:
    first = add_user(clean_engine, "first@example.com")
    second = add_user(clean_engine, "second@example.com")
    with clean_engine.begin() as connection:
        add_session(connection, first, "hash-first")
        add_session(connection, second, "hash-second")

        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": first})

        assert session_count(connection) == 1
