import secrets
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from app.domain.email_tokens import EmailTokenRepository, TokenPurpose
from app.services.session_service import TOKEN_BYTES, TOKEN_SHAPE, hash_token

LIFETIMES: dict[TokenPurpose, timedelta] = {
    "verify_email": timedelta(hours=48),
    "reset_password": timedelta(minutes=30),
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


class EmailTokenService:
    """Issues and checks the one-time tokens sent by email."""

    def __init__(
        self,
        tokens: EmailTokenRepository,
        clock: Callable[[], datetime] = _utc_now,
        lifetimes: Mapping[TokenPurpose, timedelta] = LIFETIMES,
    ) -> None:
        self._tokens = tokens
        self._clock = clock
        self._lifetimes = lifetimes

    def issue(self, user_id: uuid.UUID, purpose: TokenPurpose) -> str:
        """A new token for the link. Older unused links of the same purpose stop working."""
        token = secrets.token_urlsafe(TOKEN_BYTES)
        now = self._clock()
        expires_at = now + self._lifetimes[purpose]
        self._tokens.replace(user_id, purpose, hash_token(token), now, expires_at)
        return token

    def consume(self, token: str | None, purpose: TokenPurpose) -> uuid.UUID | None:
        """The user of a valid token, which is then used up. None for anything else."""
        if token is None or not TOKEN_SHAPE.fullmatch(token):
            return None
        return self._tokens.consume(hash_token(token), purpose, self._clock())

    def purge_expired(self) -> int:
        return self._tokens.delete_expired(self._clock())
