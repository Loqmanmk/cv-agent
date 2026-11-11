import uuid
from datetime import datetime

from sqlalchemy import Engine, delete, insert, select, update
from sqlalchemy.orm import sessionmaker

from app.domain.email_tokens import EmailTokenRepository, TokenPurpose
from app.infrastructure.db.models import EmailToken


class PostgresEmailTokenRepository(EmailTokenRepository):
    """Stores one-time email tokens in PostgreSQL."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    def replace(
        self,
        user_id: uuid.UUID,
        purpose: TokenPurpose,
        token_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        older = delete(EmailToken).where(
            EmailToken.user_id == user_id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
        new = insert(EmailToken).values(
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash,
            created_at=created_at,
            expires_at=expires_at,
        )
        with self._sessions.begin() as session:
            session.execute(older)
            session.execute(new)

    def find_valid(self, token_hash: str, purpose: TokenPurpose, now: datetime) -> uuid.UUID | None:
        statement = select(EmailToken.user_id).where(
            EmailToken.token_hash == token_hash,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
            EmailToken.expires_at > now,
        )
        with self._sessions.begin() as session:
            return session.execute(statement).scalar_one_or_none()

    def consume(self, token_hash: str, purpose: TokenPurpose, now: datetime) -> uuid.UUID | None:
        # One statement checks and marks the token, so two parallel uses cannot both succeed.
        statement = (
            update(EmailToken)
            .where(
                EmailToken.token_hash == token_hash,
                EmailToken.purpose == purpose,
                EmailToken.used_at.is_(None),
                EmailToken.expires_at > now,
            )
            .values(used_at=now)
            .returning(EmailToken.user_id)
        )
        with self._sessions.begin() as session:
            return session.execute(statement).scalar_one_or_none()

    def delete_expired(self, now: datetime) -> int:
        statement = delete(EmailToken).where(EmailToken.expires_at <= now).returning(EmailToken.id)
        with self._sessions.begin() as session:
            return len(session.execute(statement).all())
