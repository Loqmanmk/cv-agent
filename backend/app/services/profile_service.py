import uuid

from app.domain.letter import Gender
from app.domain.profile import (
    CvLanguage,
    InvalidProfileError,
    Profile,
    ProfileIncompleteError,
    ProfileRepository,
)

MAX_ADDRESS_CHARS = 300
MAX_CITY_CHARS = 100


def _one_line(value: str, limit: int, label: str) -> str:
    """One clean line: no line breaks, no repeated spaces, no invisible characters."""
    text = "".join(char for char in " ".join(value.split()) if char.isprintable())
    if len(text) > limit:
        raise InvalidProfileError(f"The {label} is too long ({limit} characters maximum).")
    return text


class ProfileService:
    """Reads and updates the profile of a user."""

    def __init__(self, profiles: ProfileRepository) -> None:
        self._profiles = profiles

    def get_profile(self, user_id: uuid.UUID) -> Profile:
        return self._profiles.get(user_id)

    def update_profile(
        self,
        user_id: uuid.UUID,
        address: str,
        city: str,
        gender: Gender,
        cv_language: CvLanguage,
    ) -> Profile:
        profile = Profile(
            address=_one_line(address, MAX_ADDRESS_CHARS, "address"),
            city=_one_line(city, MAX_CITY_CHARS, "city"),
            gender=gender,
            cv_language=cv_language,
        )
        return self._profiles.save(user_id, profile)

    def require_complete(self, user_id: uuid.UUID) -> Profile:
        """The profile, when it has everything an application needs."""
        profile = self._profiles.get(user_id)
        if not profile.is_complete:
            raise ProfileIncompleteError
        return profile
