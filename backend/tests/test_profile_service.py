import uuid

import pytest
from sqlalchemy import Engine

from app.domain.profile import DEFAULT_PROFILE, InvalidProfileError, ProfileIncompleteError
from app.infrastructure.db.postgres_profiles import PostgresProfileRepository
from app.services.profile_service import MAX_ADDRESS_CHARS, MAX_CITY_CHARS, ProfileService
from tests.db_helpers import add_user


@pytest.fixture
def service(clean_engine: Engine) -> ProfileService:
    return ProfileService(PostgresProfileRepository(clean_engine))


@pytest.fixture
def user_id(clean_engine: Engine) -> uuid.UUID:
    return add_user(clean_engine, "jane@example.com")


def test_a_new_user_has_a_profile_that_is_not_complete(
    service: ProfileService, user_id: uuid.UUID
) -> None:
    assert service.get_profile(user_id) == DEFAULT_PROFILE
    with pytest.raises(ProfileIncompleteError):
        service.require_complete(user_id)


def test_the_text_is_cleaned_before_saving(service: ProfileService, user_id: uuid.UUID) -> None:
    saved = service.update_profile(user_id, "  12  rue\nExemple ", " Ouj\u200bda\t", "f", "de")

    assert (saved.address, saved.city, saved.gender, saved.cv_language) == (
        "12 rue Exemple",
        "Oujda",
        "f",
        "de",
    )


@pytest.mark.parametrize(
    ("address", "city"),
    [("x" * (MAX_ADDRESS_CHARS + 1), "Oujda"), ("", "x" * (MAX_CITY_CHARS + 1))],
)
def test_a_text_that_is_too_long_is_refused(
    service: ProfileService, user_id: uuid.UUID, address: str, city: str
) -> None:
    with pytest.raises(InvalidProfileError, match="too long"):
        service.update_profile(user_id, address, city, "m", "fr")


def test_a_profile_with_a_city_is_complete(service: ProfileService, user_id: uuid.UUID) -> None:
    service.update_profile(user_id, "", "Oujda", "m", "fr")

    assert service.require_complete(user_id).city == "Oujda"


def test_a_city_made_of_spaces_is_not_enough(service: ProfileService, user_id: uuid.UUID) -> None:
    service.update_profile(user_id, "", "   ", "m", "fr")

    with pytest.raises(ProfileIncompleteError):
        service.require_complete(user_id)
