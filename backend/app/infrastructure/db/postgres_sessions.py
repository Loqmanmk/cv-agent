import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy import Engine, delete, insert, or_, select, update
from sqlalchemy.orm import sessionmaker

from app.domain.sessions import SessionRecord, SessionRepository
from app.infrastructure.db.models import User, UserSession


class SessionLookup(Protocol):
    id: uuid.UUID
    user_id: uuid.UUID
    csrf_token: str
    last_seen_at: datetime
    expires_at: datetime
    is_active: bool


class PostgresSessionRepository(SessionRepository):
    """Stores the sessions in PostgreSQL. The unique token hash is enforced by the database."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    def create(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        csrf_token: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        statement = insert(UserSession).values(
            user_id=user_id,
            token_hash=token_hash,
            csrf_token=csrf_token,
            created_at=created_at,
            last_seen_at=created_at,
            expires_at=expires_at,
        )
        with self._sessions.begin() as session:
            session.execute(statement)

    def find_by_token_hash(self, token_hash: str) -> SessionRecord | None:
        statement = (
            select(
                UserSession.id,
                UserSession.user_id,
                UserSession.csrf_token,
                UserSession.last_seen_at,
                UserSession.expires_at,
                User.is_active,
            )
            .join(User, User.id == UserSession.user_id)
            .where(UserSession.token_hash == token_hash)
        )
        with self._sessions.begin() as session:
            row: SessionLookup | None = session.execute(statement).one_or_none()
        if row is None:
            return None
        return SessionRecord(
            id=row.id,
            user_id=row.user_id,
            csrf_token=row.csrf_token,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            user_is_active=row.is_active,
        )

    def touch(self, session_id: uuid.UUID, seen_at: datetime) -> None:
        statement = (
            update(UserSession).where(UserSession.id == session_id).values(last_seen_at=seen_at)
        )
        with self._sessions.begin() as session:
            session.execute(statement)

    def delete_by_token_hash(self, token_hash: str) -> None:
        statement = delete(UserSession).where(UserSession.token_hash == token_hash)
        with self._sessions.begin() as session:
            session.execute(statement)

    def delete_all_for_user(self, user_id: uuid.UUID) -> None:
        statement = delete(UserSession).where(UserSession.user_id == user_id)
        with self._sessions.begin() as session:
            session.execute(statement)

    def delete_expired(self, now: datetime, idle_cutoff: datetime) -> int:
        statement = (
            delete(UserSession)
            .where(or_(UserSession.expires_at <= now, UserSession.last_seen_at <= idle_cutoff))
            .returning(UserSession.id)
        )
        with self._sessions.begin() as session:
            return len(session.execute(statement).all())
