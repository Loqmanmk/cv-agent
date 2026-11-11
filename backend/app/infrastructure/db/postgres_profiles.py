import uuid
from typing import Protocol

from sqlalchemy import Engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

from app.domain.profile import (
    DEFAULT_PROFILE,
    Profile,
    ProfileRepository,
    is_cv_language,
    is_gender,
)
from app.infrastructure.db.models import ProfileRecord

PROFILE_COLUMNS = (
    ProfileRecord.address,
    ProfileRecord.city,
    ProfileRecord.gender,
    ProfileRecord.cv_language,
)


class ProfileRow(Protocol):
    address: str
    city: str
    gender: str
    cv_language: str


def _profile(row: ProfileRow) -> Profile:
    gender = str(row.gender)
    language = str(row.cv_language)
    if not is_gender(gender):
        raise ValueError(f"Unknown gender in the database: {gender}")
    if not is_cv_language(language):
        raise ValueError(f"Unknown CV language in the database: {language}")
    return Profile(address=row.address, city=row.city, gender=gender, cv_language=language)


class PostgresProfileRepository(ProfileRepository):
    """Stores one profile per user in PostgreSQL."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    def get(self, user_id: uuid.UUID) -> Profile:
        statement = select(*PROFILE_COLUMNS).where(ProfileRecord.user_id == user_id)
        with self._sessions.begin() as session:
            row: ProfileRow | None = session.execute(statement).one_or_none()
        return DEFAULT_PROFILE if row is None else _profile(row)

    def save(self, user_id: uuid.UUID, profile: Profile) -> Profile:
        values = {
            "address": profile.address,
            "city": profile.city,
            "gender": profile.gender,
            "cv_language": profile.cv_language,
        }
        statement = (
            insert(ProfileRecord)
            .values(user_id=user_id, **values)
            .on_conflict_do_update(
                index_elements=["user_id"], set_={**values, "updated_at": func.now()}
            )
            .returning(*PROFILE_COLUMNS)
        )
        with self._sessions.begin() as session:
            row: ProfileRow = session.execute(statement).one()
        return _profile(row)
