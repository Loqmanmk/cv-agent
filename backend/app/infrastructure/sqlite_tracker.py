import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.tracker import (
    ApplicationFiles,
    ApplicationNotFoundError,
    ApplicationRepository,
    ApplicationStatus,
    ApplicationSummary,
    NewApplication,
    is_status,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    job_title TEXT NOT NULL,
    company TEXT NOT NULL,
    language TEXT NOT NULL,
    source_url TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT NOT NULL,
    cv_json TEXT NOT NULL,
    letter_json TEXT NOT NULL,
    photo BLOB,
    cv_pdf BLOB NOT NULL,
    letter_pdf BLOB NOT NULL
)
"""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _summary(row: tuple[Any, ...]) -> ApplicationSummary:
    status = str(row[6])
    if not is_status(status):
        raise ValueError(f"Unknown status in the database: {status}")
    return ApplicationSummary(
        id=int(row[0]),
        created_at=datetime.fromisoformat(str(row[1])),
        job_title=str(row[2]),
        company=str(row[3]),
        language=str(row[4]),
        source_url=str(row[5]),
        status=status,
        notes=str(row[7]),
    )


class SqliteApplicationRepository(ApplicationRepository):
    """Stores the applications in one SQLite file."""

    def __init__(self, path: Path | str, clock: Callable[[], datetime] = _utc_now) -> None:
        self._path = Path(path)
        self._clock = clock
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def add(self, application: NewApplication) -> ApplicationSummary:
        created_at = self._clock()
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO applications (created_at, job_title, company, language, source_url, "
                "status, notes, cv_json, letter_json, photo, cv_pdf, letter_pdf) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    created_at.isoformat(),
                    application.job_title,
                    application.company,
                    application.language,
                    application.source_url,
                    application.status,
                    "",
                    application.cv_json,
                    application.letter_json,
                    application.photo,
                    application.cv_pdf,
                    application.letter_pdf,
                ),
            )
            new_id = cursor.lastrowid
        if new_id is None:
            raise RuntimeError("The application could not be saved.")
        return ApplicationSummary(
            id=new_id,
            created_at=created_at,
            job_title=application.job_title,
            company=application.company,
            language=application.language,
            source_url=application.source_url,
            status=application.status,
            notes="",
        )

    def list_all(self) -> list[ApplicationSummary]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, created_at, job_title, company, language, source_url, status, notes "
                "FROM applications ORDER BY id DESC"
            ).fetchall()
        return [_summary(row) for row in rows]

    def get(self, application_id: int) -> ApplicationSummary:
        with self._connect() as db:
            row = db.execute(
                "SELECT id, created_at, job_title, company, language, source_url, status, notes "
                "FROM applications WHERE id = ?",
                (application_id,),
            ).fetchone()
        if row is None:
            raise ApplicationNotFoundError(f"Application {application_id} was not found.")
        return _summary(row)

    def update(
        self,
        application_id: int,
        status: ApplicationStatus | None,
        notes: str | None,
    ) -> ApplicationSummary:
        self.get(application_id)
        with self._connect() as db:
            if status is not None:
                db.execute(
                    "UPDATE applications SET status = ? WHERE id = ?", (status, application_id)
                )
            if notes is not None:
                db.execute(
                    "UPDATE applications SET notes = ? WHERE id = ?", (notes, application_id)
                )
        return self.get(application_id)

    def delete(self, application_id: int) -> None:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM applications WHERE id = ?", (application_id,))
            deleted = cursor.rowcount
        if deleted == 0:
            raise ApplicationNotFoundError(f"Application {application_id} was not found.")

    def files(self, application_id: int) -> ApplicationFiles:
        with self._connect() as db:
            row = db.execute(
                "SELECT cv_pdf, letter_pdf FROM applications WHERE id = ?", (application_id,)
            ).fetchone()
        if row is None:
            raise ApplicationNotFoundError(f"Application {application_id} was not found.")
        return ApplicationFiles(cv_pdf=bytes(row[0]), letter_pdf=bytes(row[1]))
