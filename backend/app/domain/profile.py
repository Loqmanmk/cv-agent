import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, TypeGuard, get_args

from app.domain.letter import Gender

CvLanguage = Literal["fr", "de", "en", "ar"]
GENDERS: tuple[str, ...] = get_args(Gender)
CV_LANGUAGES: tuple[str, ...] = get_args(CvLanguage)


def is_gender(value: str) -> TypeGuard[Gender]:
    return value in GENDERS


def is_cv_language(value: str) -> TypeGuard[CvLanguage]:
    return value in CV_LANGUAGES


class InvalidProfileError(Exception):
    """Raised when the profile is not acceptable. The message is safe to show."""


class ProfileIncompleteError(Exception):
    """Raised when a user has not told us where they live, which the cover letter needs."""

    def __init__(self) -> None:
        super().__init__(
            "Complete your profile (at least your city) before creating an application."
        )


@dataclass(frozen=True)
class Profile:
    address: str
    city: str
    gender: Gender
    cv_language: CvLanguage

    @property
    def is_complete(self) -> bool:
        return self.city.strip() != ""


DEFAULT_PROFILE = Profile(address="", city="", gender="m", cv_language="fr")


class ProfileRepository(ABC):
    """Contract for anything that stores the profile of a user."""

    @abstractmethod
    def get(self, user_id: uuid.UUID) -> Profile:
        """The profile, or the default one when the user has not saved any."""

    @abstractmethod
    def save(self, user_id: uuid.UUID, profile: Profile) -> Profile: ...
