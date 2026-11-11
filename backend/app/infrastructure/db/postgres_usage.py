import uuid
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import Engine, delete, func, insert, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.plans import (
    Plan,
    Reservation,
    UnknownUserError,
    UsageKind,
    UsageRepository,
    is_plan,
)
from app.infrastructure.db.models import UsageEvent, User


def _plan(value: str) -> Plan:
    if not is_plan(value):
        raise ValueError(f"Unknown plan in the database: {value}")
    return value


def _count(session: Session, user_id: uuid.UUID, kind: UsageKind, since: datetime) -> int:
    statement = (
        select(func.count())
        .select_from(UsageEvent)
        .where(
            UsageEvent.user_id == user_id,
            UsageEvent.kind == kind,
            UsageEvent.created_at >= since,
        )
    )
    return int(session.execute(statement).scalar_one())


class PostgresUsageRepository(UsageRepository):
    """Counts the use of the platform in PostgreSQL."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    def reserve(
        self,
        user_id: uuid.UUID,
        kind: UsageKind,
        now: datetime,
        since: datetime,
        limits: Mapping[Plan, int],
    ) -> Reservation:
        # The user row stays locked until the end of the transaction, so a second request for
        # the same user waits here and then counts the use that the first one added.
        locked = select(User.plan).where(User.id == user_id).with_for_update()
        with self._sessions.begin() as session:
            value = session.execute(locked).scalar_one_or_none()
            if value is None:
                raise UnknownUserError
            plan = _plan(value)
            used = _count(session, user_id, kind, since)
            if used >= limits[plan]:
                return Reservation(None, plan, used)
            statement = (
                insert(UsageEvent)
                .values(user_id=user_id, kind=kind, created_at=now)
                .returning(UsageEvent.id)
            )
            new_id = session.execute(statement).scalar_one()
        return Reservation(int(new_id), plan, used + 1)

    def release(self, user_id: uuid.UUID, reservation_id: int) -> None:
        statement = delete(UsageEvent).where(
            UsageEvent.id == reservation_id, UsageEvent.user_id == user_id
        )
        with self._sessions.begin() as session:
            session.execute(statement)

    def used_since(self, user_id: uuid.UUID, kind: UsageKind, since: datetime) -> int:
        with self._sessions.begin() as session:
            return _count(session, user_id, kind, since)

    def plan_of(self, user_id: uuid.UUID) -> Plan:
        with self._sessions.begin() as session:
            value = session.execute(
                select(User.plan).where(User.id == user_id)
            ).scalar_one_or_none()
        if value is None:
            raise UnknownUserError
        return _plan(value)
