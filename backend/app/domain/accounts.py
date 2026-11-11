import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


class InvalidEmailError(Exception):
    """Raised when an email address is not acceptable. The message is safe to show."""


class WeakPasswordError(Exception):
    """Raised when a new password breaks the rules. The problems are safe to show."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


class EmailAlreadyRegisteredError(Exception):
    """Raised when an account already exists for the email."""


class InvalidCredentialsError(Exception):
    """Raised when a login fails. It never says why."""


@dataclass(frozen=True)
class Account:
    id: uuid.UUID
    email: str
    is_active: bool
    email_verified_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class StoredAccount:
    account: Account
    password_hash: str = field(repr=False)


class PasswordHasher(ABC):
    """Contract for anything that can hash and check passwords."""

    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, stored_hash: str, password: str) -> bool:
        """True only if the password matches. A hash that cannot be read never matches."""

    @abstractmethod
    def needs_rehash(self, stored_hash: str) -> bool:
        """True when the hash was made with weaker settings than the current ones."""


class UserRepository(ABC):
    """Contract for anything that stores user accounts."""

    @abstractmethod
    def create(self, email: str, password_hash: str) -> Account:
        """Create the account, or raise EmailAlreadyRegisteredError."""

    @abstractmethod
    def find_by_email(self, email: str) -> StoredAccount | None: ...

    @abstractmethod
    def find_by_id(self, user_id: uuid.UUID) -> Account | None: ...

    @abstractmethod
    def update_password_hash(self, user_id: uuid.UUID, password_hash: str) -> None: ...
