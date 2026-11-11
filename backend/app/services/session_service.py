import hashlib
import re
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.domain.sessions import SessionRepository

ABSOLUTE_LIFETIME = timedelta(days=30)
IDLE_LIFETIME = timedelta(days=7)
TOUCH_INTERVAL = timedelta(minutes=5)
TOKEN_BYTES = 32
TOKEN_SHAPE = re.compile(r"[A-Za-z0-9_-]{1,128}")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def hash_token(token: str) -> str:
    """The token has 256 bits of randomness, so a fast hash is enough to protect the database."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def csrf_matches(expected: str, supplied: str | None) -> bool:
    """Compare in constant time, so the answer time does not reveal how much matched."""
    if supplied is None:
        return False
    return secrets.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8"))


@dataclass(frozen=True)
class StartedSession:
    token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class ActiveSession:
    user_id: uuid.UUID
    csrf_token: str = field(repr=False)


class SessionService:
    """Starts, checks and ends login sessions."""

    def __init__(
        self,
        sessions: SessionRepository,
        clock: Callable[[], datetime] = _utc_now,
        absolute_lifetime: timedelta = ABSOLUTE_LIFETIME,
        idle_lifetime: timedelta = IDLE_LIFETIME,
        touch_interval: timedelta = TOUCH_INTERVAL,
    ) -> None:
        self._sessions = sessions
        self._clock = clock
        self._absolute_lifetime = absolute_lifetime
        self._idle_lifetime = idle_lifetime
        self._touch_interval = touch_interval

    def start(self, user_id: uuid.UUID) -> StartedSession:
        """A new session with a new random token, so an old token can never be reused."""
        token = secrets.token_urlsafe(TOKEN_BYTES)
        csrf_token = secrets.token_urlsafe(TOKEN_BYTES)
        now = self._clock()
        expires_at = now + self._absolute_lifetime
        self._sessions.create(user_id, hash_token(token), csrf_token, now, expires_at)
        return StartedSession(token, csrf_token, expires_at)

    def authenticate(self, token: str | None) -> ActiveSession | None:
        """The session of a valid token, or None. A dead session is deleted."""
        if token is None or not TOKEN_SHAPE.fullmatch(token):
            return None
        token_hash = hash_token(token)
        record = self._sessions.find_by_token_hash(token_hash)
        if record is None:
            return None
        now = self._clock()
        expired = record.expires_at <= now
        idle = record.last_seen_at + self._idle_lifetime <= now
        if expired or idle or not record.user_is_active:
            self._sessions.delete_by_token_hash(token_hash)
            return None
        if now - record.last_seen_at >= self._touch_interval:
            self._sessions.touch(record.id, now)
        return ActiveSession(record.user_id, record.csrf_token)

    def end(self, token: str | None) -> None:
        """Log out: the session is deleted on the server, so a copied cookie stops working."""
        if token is not None and TOKEN_SHAPE.fullmatch(token):
            self._sessions.delete_by_token_hash(hash_token(token))

    def end_all(self, user_id: uuid.UUID) -> None:
        """Log the user out everywhere, for example after a password change."""
        self._sessions.delete_all_for_user(user_id)

    def purge_expired(self) -> int:
        now = self._clock()
        return self._sessions.delete_expired(now, now - self._idle_lifetime)
