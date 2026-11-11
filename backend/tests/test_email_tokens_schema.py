import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from tests.db_helpers import add_user

CREATED = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
INSERT = text(
    "INSERT INTO email_tokens (user_id, purpose, token_hash, created_at, expires_at) "
    "VALUES (:user_id, :purpose, :token_hash, :created, :expires)"
)


def add_token(
    connection: Connection,
    user_id: uuid.UUID,
    token_hash: str = "hash-1",
    purpose: str = "verify_email",
    expires: datetime = CREATED + timedelta(hours=1),
) -> None:
    connection.execute(
        INSERT,
        {
            "user_id": user_id,
            "purpose": purpose,
            "token_hash": token_hash,
            "created": CREATED,
            "expires": expires,
        },
    )


def test_two_tokens_cannot_share_a_hash(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)
    with clean_engine.begin() as connection:
        add_token(connection, user_id, "same-hash")

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_token(connection, user_id, "same-hash", purpose="reset_password")


def test_an_unknown_purpose_is_refused(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_token(connection, user_id, purpose="delete_account")


def test_a_token_must_expire_after_it_is_created(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_token(connection, user_id, expires=CREATED)


def test_deleting_a_user_deletes_their_tokens_only(clean_engine: Engine) -> None:
    first = add_user(clean_engine, "first@example.com")
    second = add_user(clean_engine, "second@example.com")

    with clean_engine.begin() as connection:
        add_token(connection, first, "hash-first")
        add_token(connection, second, "hash-second")
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": first})
        remaining = connection.execute(text("SELECT count(*) FROM email_tokens")).scalar_one()

    assert remaining == 1
