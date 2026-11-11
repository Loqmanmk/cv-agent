import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy import Engine, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

from app.domain.accounts import (
    Account,
    EmailAlreadyRegisteredError,
    StoredAccount,
    UserRepository,
)
from app.infrastructure.db.models import User


class AccountRow(Protocol):
    id: uuid.UUID
    email: str
    is_active: bool
    email_verified_at: datetime | None
    created_at: datetime


class CredentialsRow(AccountRow, Protocol):
    password_hash: str


def _account(row: AccountRow) -> Account:
    return Account(
        id=row.id,
        email=row.email,
        is_active=row.is_active,
        email_verified_at=row.email_verified_at,
        created_at=row.created_at,
    )


ACCOUNT_COLUMNS = (User.id, User.email, User.is_active, User.email_verified_at, User.created_at)


class PostgresUserRepository(UserRepository):
    """Stores the accounts in PostgreSQL. The unique email is enforced by the database."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    def create(self, email: str, password_hash: str) -> Account:
        statement = (
            insert(User)
            .values(email=email, password_hash=password_hash)
            .on_conflict_do_nothing(index_elements=["email"])
            .returning(*ACCOUNT_COLUMNS)
        )
        with self._sessions.begin() as session:
            row = session.execute(statement).one_or_none()
        if row is None:
            raise EmailAlreadyRegisteredError
        return _account(row)

    def find_by_email(self, email: str) -> StoredAccount | None:
        statement = select(*ACCOUNT_COLUMNS, User.password_hash).where(User.email == email)
        with self._sessions.begin() as session:
            row: CredentialsRow | None = session.execute(statement).one_or_none()
        if row is None:
            return None
        return StoredAccount(_account(row), row.password_hash)

    def update_password_hash(self, user_id: uuid.UUID, password_hash: str) -> None:
        statement = update(User).where(User.id == user_id).values(password_hash=password_hash)
        with self._sessions.begin() as session:
            session.execute(statement)
