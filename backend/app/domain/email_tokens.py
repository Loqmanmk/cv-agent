import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal, get_args

TokenPurpose = Literal["verify_email", "reset_password"]
TOKEN_PURPOSES: tuple[str, ...] = get_args(TokenPurpose)


class EmailTokenRepository(ABC):
    """Contract for anything that stores one-time email tokens. Only hashes are stored."""

    @abstractmethod
    def replace(
        self,
        user_id: uuid.UUID,
        purpose: TokenPurpose,
        token_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        """Store a new token and delete the unused older ones of the same purpose."""

    @abstractmethod
    def consume(self, token_hash: str, purpose: TokenPurpose, now: datetime) -> uuid.UUID | None:
        """Mark a valid token as used and return its user. A token works only once."""

    @abstractmethod
    def delete_expired(self, now: datetime) -> int: ...
