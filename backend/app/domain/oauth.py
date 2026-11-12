import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, get_args

Provider = Literal["google"]
PROVIDERS: tuple[str, ...] = get_args(Provider)


class OAuthError(Exception):
    """Raised when signing in with a provider fails. The message is safe to show."""


@dataclass(frozen=True)
class ExternalIdentity:
    """Who the provider says the user is. `subject` never changes, the email can."""

    provider: Provider
    subject: str
    email: str
    email_verified: bool


class OAuthIdentityRepository(ABC):
    """Contract for anything that remembers which provider identity belongs to which user."""

    @abstractmethod
    def find_user(self, provider: Provider, subject: str) -> uuid.UUID | None: ...

    @abstractmethod
    def link(self, user_id: uuid.UUID, provider: Provider, subject: str, email: str) -> None:
        """Remember the identity. Linking the same identity twice changes nothing."""
