import json
import uuid
from typing import Any

from sqlalchemy import Engine, Row, delete, insert, select, update
from sqlalchemy.orm import sessionmaker

from app.domain.tracker import (
    ApplicationFiles,
    ApplicationNotFoundError,
    ApplicationRepository,
    ApplicationStatus,
    ApplicationSummary,
    NewApplication,
    is_status,
)
from app.infrastructure.db.models import ApplicationRecord

SUMMARY_COLUMNS = (
    ApplicationRecord.id,
    ApplicationRecord.created_at,
    ApplicationRecord.job_title,
    ApplicationRecord.company,
    ApplicationRecord.language,
    ApplicationRecord.source_url,
    ApplicationRecord.status,
    ApplicationRecord.notes,
)


def _summary(row: Row[Any]) -> ApplicationSummary:
    status = str(row.status)
    if not is_status(status):
        raise ValueError(f"Unknown status in the database: {status}")
    return ApplicationSummary(
        id=int(row.id),
        created_at=row.created_at,
        job_title=row.job_title,
        company=row.company,
        language=row.language,
        source_url=row.source_url,
        status=status,
        notes=row.notes,
    )


def _owned(user_id: uuid.UUID, application_id: int) -> tuple[Any, Any]:
    return (
        ApplicationRecord.user_id == user_id,
        ApplicationRecord.id == application_id,
    )


class PostgresApplicationRepository(ApplicationRepository):
    """Stores the applications in PostgreSQL. Every query is limited to the owner."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    def add(self, user_id: uuid.UUID, application: NewApplication) -> ApplicationSummary:
        statement = (
            insert(ApplicationRecord)
            .values(
                user_id=user_id,
                job_title=application.job_title,
                company=application.company,
                language=application.language,
                source_url=application.source_url,
                status=application.status,
                notes="",
                cv_json=json.loads(application.cv_json),
                letter_json=json.loads(application.letter_json),
                photo=application.photo,
                cv_pdf=application.cv_pdf,
                letter_pdf=application.letter_pdf,
            )
            .returning(*SUMMARY_COLUMNS)
        )
        with self._sessions.begin() as session:
            return _summary(session.execute(statement).one())

    def list_all(self, user_id: uuid.UUID) -> list[ApplicationSummary]:
        statement = (
            select(*SUMMARY_COLUMNS)
            .where(ApplicationRecord.user_id == user_id)
            .order_by(ApplicationRecord.id.desc())
        )
        with self._sessions.begin() as session:
            return [_summary(row) for row in session.execute(statement)]

    def get(self, user_id: uuid.UUID, application_id: int) -> ApplicationSummary:
        statement = select(*SUMMARY_COLUMNS).where(*_owned(user_id, application_id))
        with self._sessions.begin() as session:
            row = session.execute(statement).one_or_none()
        if row is None:
            raise ApplicationNotFoundError
        return _summary(row)

    def update(
        self,
        user_id: uuid.UUID,
        application_id: int,
        status: ApplicationStatus | None,
        notes: str | None,
    ) -> ApplicationSummary:
        changes: dict[str, object] = {}
        if status is not None:
            changes["status"] = status
        if notes is not None:
            changes["notes"] = notes
        if not changes:
            return self.get(user_id, application_id)
        statement = (
            update(ApplicationRecord)
            .where(*_owned(user_id, application_id))
            .values(**changes)
            .returning(*SUMMARY_COLUMNS)
        )
        with self._sessions.begin() as session:
            row = session.execute(statement).one_or_none()
        if row is None:
            raise ApplicationNotFoundError
        return _summary(row)

    def delete(self, user_id: uuid.UUID, application_id: int) -> None:
        statement = (
            delete(ApplicationRecord)
            .where(*_owned(user_id, application_id))
            .returning(ApplicationRecord.id)
        )
        with self._sessions.begin() as session:
            deleted = session.execute(statement).first()
        if deleted is None:
            raise ApplicationNotFoundError

    def files(self, user_id: uuid.UUID, application_id: int) -> ApplicationFiles:
        statement = select(ApplicationRecord.cv_pdf, ApplicationRecord.letter_pdf).where(
            *_owned(user_id, application_id)
        )
        with self._sessions.begin() as session:
            row = session.execute(statement).one_or_none()
        if row is None:
            raise ApplicationNotFoundError
        return ApplicationFiles(cv_pdf=bytes(row.cv_pdf), letter_pdf=bytes(row.letter_pdf))
