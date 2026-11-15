import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


class NoSavedCvError(Exception):
    """Raised when a user asks to use a saved CV but has not saved one."""

    def __init__(self) -> None:
        super().__init__("You have no saved CV. Upload your CV first.")


@dataclass(frozen=True)
class SavedCv:
    """The CV file a user keeps on their account, reused for every application."""

    filename: str
    content: bytes = field(repr=False)


@dataclass(frozen=True)
class SavedCvInfo:
    """What the website shows about the saved CV, without its content."""

    filename: str
    size: int
    uploaded_at: datetime


class SavedCvRepository(ABC):
    """Contract for anything that keeps one CV file per user."""

    @abstractmethod
    def info(self, user_id: uuid.UUID) -> SavedCvInfo | None: ...

    @abstractmethod
    def get(self, user_id: uuid.UUID) -> SavedCv | None: ...

    @abstractmethod
    def save(self, user_id: uuid.UUID, cv: SavedCv) -> SavedCvInfo:
        """Store the CV, replacing the previous one."""

    @abstractmethod
    def delete(self, user_id: uuid.UUID) -> None: ...
