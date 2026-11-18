import uuid
from pathlib import PurePath

from app.domain.cv import CV
from app.domain.saved_cv import NoSavedCvError, SavedCv, SavedCvInfo, SavedCvRepository
from app.services.application_service import check_cv_file
from app.services.cv_structurer import STRUCTURE_VERSION

MAX_FILENAME_CHARS = 200


def clean_filename(filename: str) -> str:
    """The file name without any folder or control character, short enough to show."""
    name = PurePath(filename.replace("\\", "/")).name
    name = "".join(char for char in name if char.isprintable()).strip()
    if len(name) <= MAX_FILENAME_CHARS:
        return name
    suffix = PurePath(name).suffix
    return name[: MAX_FILENAME_CHARS - len(suffix)] + suffix


class SavedCvService:
    """Keeps the CV of each user, so it is uploaded once and reused for every application."""

    def __init__(self, repository: SavedCvRepository) -> None:
        self._repository = repository

    def info(self, user_id: uuid.UUID) -> SavedCvInfo | None:
        return self._repository.info(user_id)

    def save(self, user_id: uuid.UUID, filename: str, content: bytes) -> SavedCvInfo:
        """Check the file like an upload for an application, then keep it."""
        name = clean_filename(filename)
        check_cv_file(name, content)
        return self._repository.save(user_id, SavedCv(filename=name, content=content))

    def require(self, user_id: uuid.UUID) -> SavedCv:
        """The saved CV, with its structure only when it was made by the current version."""
        saved = self._repository.get(user_id)
        if saved is None:
            raise NoSavedCvError
        if saved.structure_version != STRUCTURE_VERSION:
            return SavedCv(filename=saved.filename, content=saved.content)
        return saved

    def remember_structure(self, user_id: uuid.UUID, content: bytes, structured: CV) -> None:
        self._repository.remember_structure(user_id, content, structured, STRUCTURE_VERSION)

    def delete(self, user_id: uuid.UUID) -> None:
        self._repository.delete(user_id)
