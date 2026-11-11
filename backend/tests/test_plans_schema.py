import uuid

import pytest
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from tests.db_helpers import add_user


def add_profile(connection: Connection, user_id: uuid.UUID) -> None:
    connection.execute(text("INSERT INTO profiles (user_id) VALUES (:id)"), {"id": user_id})


def add_usage(connection: Connection, user_id: uuid.UUID, kind: str = "application") -> None:
    connection.execute(
        text("INSERT INTO usage_events (user_id, kind) VALUES (:id, :kind)"),
        {"id": user_id, "kind": kind},
    )


def test_a_new_user_is_on_the_free_plan(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)

    with clean_engine.connect() as connection:
        plan = connection.execute(
            text("SELECT plan FROM users WHERE id = :id"), {"id": user_id}
        ).scalar_one()

    assert plan == "free"


def test_an_unknown_plan_is_refused(clean_engine: Engine) -> None:
    add_user(clean_engine)

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        connection.execute(text("UPDATE users SET plan = 'gold'"))


def test_a_new_profile_has_safe_defaults(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)

    with clean_engine.begin() as connection:
        add_profile(connection, user_id)
        row = connection.execute(
            text("SELECT address, city, gender, cv_language FROM profiles")
        ).one()

    assert tuple(row) == ("", "", "m", "fr")


def test_a_profile_refuses_an_unknown_gender(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO profiles (user_id, gender) VALUES (:id, 'x')"), {"id": user_id}
        )


def test_a_profile_refuses_an_unknown_cv_language(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO profiles (user_id, cv_language) VALUES (:id, 'es')"),
            {"id": user_id},
        )


def test_a_user_has_at_most_one_profile(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)
    with clean_engine.begin() as connection:
        add_profile(connection, user_id)

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_profile(connection, user_id)


def test_a_usage_event_refuses_an_unknown_kind(clean_engine: Engine) -> None:
    user_id = add_user(clean_engine)

    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        add_usage(connection, user_id, "download")


def test_deleting_a_user_deletes_their_profile_and_their_usage(clean_engine: Engine) -> None:
    first = add_user(clean_engine, "first@example.com")
    second = add_user(clean_engine, "second@example.com")

    with clean_engine.begin() as connection:
        for user_id in (first, second):
            add_profile(connection, user_id)
            add_usage(connection, user_id)
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": first})
        profiles = connection.execute(text("SELECT count(*) FROM profiles")).scalar_one()
        events = connection.execute(text("SELECT count(*) FROM usage_events")).scalar_one()

    assert (profiles, events) == (1, 1)
