import hashlib
import uuid

from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

from app.domain.cv import CV
from app.domain.saved_cv import SavedCv, SavedCvInfo, SavedCvRepository
from app.infrastructure.db.models import SavedCvRecord

INFO_COLUMNS = (
    SavedCvRecord.filename,
    func.octet_length(SavedCvRecord.content).label("size"),
    SavedCvRecord.uploaded_at,
)


class PostgresSavedCvRepository(SavedCvRepository):
    """Stores one CV file per user in PostgreSQL. Deleting the user deletes the file."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    def info(self, user_id: uuid.UUID) -> SavedCvInfo | None:
        statement = select(*INFO_COLUMNS).where(SavedCvRecord.user_id == user_id)
        with self._sessions.begin() as session:
            row = session.execute(statement).one_or_none()
        if row is None:
            return None
        return SavedCvInfo(filename=row.filename, size=int(row.size), uploaded_at=row.uploaded_at)

    def get(self, user_id: uuid.UUID) -> SavedCv | None:
        statement = select(
            SavedCvRecord.filename,
            SavedCvRecord.content,
            SavedCvRecord.structured_cv,
            SavedCvRecord.structure_version,
        ).where(SavedCvRecord.user_id == user_id)
        with self._sessions.begin() as session:
            row = session.execute(statement).one_or_none()
        if row is None:
            return None
        structured = None if row.structured_cv is None else CV.model_validate(row.structured_cv)
        return SavedCv(
            filename=row.filename,
            content=bytes(row.content),
            structured=structured,
            structure_version=row.structure_version,
        )

    def save(self, user_id: uuid.UUID, cv: SavedCv) -> SavedCvInfo:
        # A new file has not been read yet: any structure of the previous file is forgotten.
        values = {
            "filename": cv.filename,
            "content": cv.content,
            "structured_cv": None,
            "structure_version": None,
        }
        statement = (
            insert(SavedCvRecord)
            .values(user_id=user_id, **values)
            .on_conflict_do_update(
                index_elements=["user_id"], set_={**values, "uploaded_at": func.now()}
            )
            .returning(*INFO_COLUMNS)
        )
        with self._sessions.begin() as session:
            row = session.execute(statement).one()
        return SavedCvInfo(filename=row.filename, size=int(row.size), uploaded_at=row.uploaded_at)

    def remember_structure(
        self, user_id: uuid.UUID, content: bytes, structured: CV, version: int
    ) -> None:
        # Compared by fingerprint: if the user replaced the file meanwhile, nothing is stored.
        fingerprint = hashlib.sha256(content).digest()
        statement = (
            update(SavedCvRecord)
            .where(
                SavedCvRecord.user_id == user_id,
                func.sha256(SavedCvRecord.content) == fingerprint,
            )
            .values(structured_cv=structured.model_dump(mode="json"), structure_version=version)
        )
        with self._sessions.begin() as session:
            session.execute(statement)

    def delete(self, user_id: uuid.UUID) -> None:
        with self._sessions.begin() as session:
            session.execute(delete(SavedCvRecord).where(SavedCvRecord.user_id == user_id))
