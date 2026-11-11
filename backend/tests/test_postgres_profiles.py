import uuid

import pytest
from sqlalchemy import Engine, text

from app.domain.profile import DEFAULT_PROFILE, Profile
from app.infrastructure.db.postgres_profiles import PostgresProfileRepository
from tests.db_helpers import add_user

PROFILE = Profile(address="12 rue Exemple", city="Oujda", gender="f", cv_language="de")


@pytest.fixture
def profiles(clean_engine: Engine) -> PostgresProfileRepository:
    return PostgresProfileRepository(clean_engine)


@pytest.fixture
def user_id(clean_engine: Engine) -> uuid.UUID:
    return add_user(clean_engine, "jane@example.com")


def test_a_user_without_a_profile_gets_the_default(
    profiles: PostgresProfileRepository, user_id: uuid.UUID
) -> None:
    assert profiles.get(user_id) == DEFAULT_PROFILE


def test_a_saved_profile_is_returned(
    profiles: PostgresProfileRepository, user_id: uuid.UUID
) -> None:
    assert profiles.save(user_id, PROFILE) == PROFILE
    assert profiles.get(user_id) == PROFILE


def test_saving_again_replaces_the_profile_and_keeps_one_row(
    profiles: PostgresProfileRepository, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    profiles.save(user_id, PROFILE)
    moved = Profile(address="", city="Berlin", gender="f", cv_language="en")

    profiles.save(user_id, moved)

    assert profiles.get(user_id) == moved
    with clean_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM profiles")).scalar_one() == 1


def test_each_user_has_their_own_profile(
    profiles: PostgresProfileRepository, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    other = add_user(clean_engine, "other@example.com")

    profiles.save(user_id, PROFILE)

    assert profiles.get(other) == DEFAULT_PROFILE
