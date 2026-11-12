import uuid

from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

from app.domain.oauth import OAuthIdentityRepository, Provider
from app.infrastructure.db.models import OAuthIdentity


class PostgresOAuthIdentityRepository(OAuthIdentityRepository):
    """Remembers which provider identity belongs to which user."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    def find_user(self, provider: Provider, subject: str) -> uuid.UUID | None:
        statement = select(OAuthIdentity.user_id).where(
            OAuthIdentity.provider == provider, OAuthIdentity.subject == subject
        )
        with self._sessions.begin() as session:
            return session.execute(statement).scalar_one_or_none()

    def link(self, user_id: uuid.UUID, provider: Provider, subject: str, email: str) -> None:
        statement = (
            insert(OAuthIdentity)
            .values(user_id=user_id, provider=provider, subject=subject, email=email)
            .on_conflict_do_nothing(index_elements=["provider", "subject"])
        )
        with self._sessions.begin() as session:
            session.execute(statement)
