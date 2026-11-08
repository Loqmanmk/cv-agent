from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeGuard, get_args

ApplicationStatus = Literal["saved", "applied", "interview", "offer", "rejected", "withdrawn"]
STATUSES: tuple[str, ...] = get_args(ApplicationStatus)


def is_status(value: str) -> TypeGuard[ApplicationStatus]:
    return value in STATUSES


class ApplicationNotFoundError(Exception):
    """Raised when a saved application does not exist."""


class InvalidTrackerInputError(Exception):
    """Raised when the data of an application is not acceptable. The message is safe to show."""


@dataclass(frozen=True)
class NewApplication:
    job_title: str
    company: str
    language: str
    source_url: str
    status: ApplicationStatus
    cv_json: str
    letter_json: str
    photo: bytes | None
    cv_pdf: bytes
    letter_pdf: bytes


@dataclass(frozen=True)
class ApplicationSummary:
    id: int
    created_at: datetime
    job_title: str
    company: str
    language: str
    source_url: str
    status: ApplicationStatus
    notes: str


@dataclass(frozen=True)
class ApplicationFiles:
    cv_pdf: bytes
    letter_pdf: bytes


class ApplicationRepository(ABC):
    """Contract for anything that can store the applications of the user."""

    @abstractmethod
    def add(self, application: NewApplication) -> ApplicationSummary: ...

    @abstractmethod
    def list_all(self) -> list[ApplicationSummary]:
        """Return every application, the newest first."""

    @abstractmethod
    def get(self, application_id: int) -> ApplicationSummary: ...

    @abstractmethod
    def update(
        self,
        application_id: int,
        status: ApplicationStatus | None,
        notes: str | None,
    ) -> ApplicationSummary: ...

    @abstractmethod
    def delete(self, application_id: int) -> None: ...

    @abstractmethod
    def files(self, application_id: int) -> ApplicationFiles: ...
