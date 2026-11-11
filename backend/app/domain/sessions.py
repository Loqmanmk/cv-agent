import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SessionRecord:
    id: uuid.UUID
    user_id: uuid.UUID
    csrf_token: str = field(repr=False)
    last_seen_at: datetime
    expires_at: datetime
    user_is_active: bool


class SessionRepository(ABC):
    """Contract for anything that stores sessions. Only the hash of a token is ever stored."""

    @abstractmethod
    def create(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        csrf_token: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> None: ...

    @abstractmethod
    def find_by_token_hash(self, token_hash: str) -> SessionRecord | None: ...

    @abstractmethod
    def touch(self, session_id: uuid.UUID, seen_at: datetime) -> None: ...

    @abstractmethod
    def delete_by_token_hash(self, token_hash: str) -> None: ...

    @abstractmethod
    def delete_all_for_user(self, user_id: uuid.UUID) -> None: ...

    @abstractmethod
    def delete_expired(self, now: datetime, idle_cutoff: datetime) -> int:
        """Delete the sessions past their end date or idle since the cutoff. Returns the count."""
