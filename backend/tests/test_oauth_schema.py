import uuid

import pytest
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from tests.db_helpers import add_user

INSERT = text(
    "INSERT INTO oauth_identities (user_id, provider, subject, email) "
    "VALUES (:user_id, :provider, :subject, 'jane@example.com')"
)


def link(
    connection: Connection, user_id: uuid.UUID, subject: str = "g-1", provider: str = "google"
) -> None:
    connection.execute(INSERT, {"user_id": user_id, "provider": provider, "subject": subject})


def test_one_provider_identity_belongs_to_one_user(clean_engine: Engine) -> None:
    first = add_user(clean_engine, "first@example.com")
    second = add_user(clean_engine, "second@example.com")
    with clean_engine.begin() as connection:
        link(connection, first)

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        link(connection, second)


def test_an_unknown_provider_is_refused(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        link(connection, user_id, provider="facebook")


def test_deleting_a_user_deletes_their_identities(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)
    with clean_engine.begin() as connection:
        link(connection, user_id)
        connection.execute(text("DELETE FROM users"))
        remaining = connection.execute(text("SELECT count(*) FROM oauth_identities")).scalar_one()

    assert remaining == 0
