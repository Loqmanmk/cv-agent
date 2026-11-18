import uuid
from datetime import UTC, datetime

import pytest

from app.domain.cv import CV
from app.domain.saved_cv import NoSavedCvError, SavedCv, SavedCvInfo, SavedCvRepository
from app.services.application_service import InvalidApplicationInputError
from app.services.saved_cv_service import MAX_FILENAME_CHARS, SavedCvService, clean_filename
from tests.test_application_service import make_docx, make_pdf

USER = uuid.UUID(int=7)


class MemorySavedCvs(SavedCvRepository):
    def __init__(self) -> None:
        self.stored: dict[uuid.UUID, SavedCv] = {}

    def info(self, user_id: uuid.UUID) -> SavedCvInfo | None:
        raise NotImplementedError

    def get(self, user_id: uuid.UUID) -> SavedCv | None:
        return self.stored.get(user_id)

    def save(self, user_id: uuid.UUID, cv: SavedCv) -> SavedCvInfo:
        self.stored[user_id] = cv
        return SavedCvInfo(cv.filename, len(cv.content), datetime.now(UTC))

    def delete(self, user_id: uuid.UUID) -> None:
        self.stored.pop(user_id, None)

    def remember_structure(
        self, user_id: uuid.UUID, content: bytes, structured: CV, version: int
    ) -> None:
        saved = self.stored[user_id]
        if saved.content == content:
            self.stored[user_id] = SavedCv(saved.filename, saved.content, structured, version)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("cv.docx", "cv.docx"),
        ("C:\\fakepath\\Mon CV.pdf", "Mon CV.pdf"),
        ("../../etc/cv.pdf", "cv.pdf"),
        ("cv\x00\n.pdf", "cv.pdf"),
    ],
)
def test_the_file_name_keeps_no_folder_and_no_control_character(
    filename: str, expected: str
) -> None:
    assert clean_filename(filename) == expected


def test_a_long_file_name_is_shortened_but_keeps_its_extension() -> None:
    name = clean_filename("x" * 500 + ".docx")

    assert len(name) == MAX_FILENAME_CHARS
    assert name.endswith(".docx")


def test_a_valid_cv_is_saved_with_a_clean_name() -> None:
    repository = MemorySavedCvs()

    SavedCvService(repository).save(USER, "C:\\fakepath\\cv.pdf", make_pdf())

    assert repository.stored[USER].filename == "cv.pdf"


@pytest.mark.parametrize(
    ("filename", "content"),
    [("cv.txt", b"hello"), ("cv.pdf", b""), ("cv.pdf", b"PK-not-a-pdf"), ("cv.docx", b"%PDF")],
)
def test_a_file_that_is_not_a_cv_is_refused(filename: str, content: bytes) -> None:
    repository = MemorySavedCvs()

    with pytest.raises(InvalidApplicationInputError):
        SavedCvService(repository).save(USER, filename, content)

    assert repository.stored == {}


def test_the_saved_cv_is_given_back() -> None:
    repository = MemorySavedCvs()
    service = SavedCvService(repository)
    service.save(USER, "cv.docx", make_docx())

    assert service.require(USER).filename == "cv.docx"


def test_the_structure_of_the_saved_cv_is_given_back() -> None:
    from tests.test_tailoring_guard import make_cv

    repository = MemorySavedCvs()
    service = SavedCvService(repository)
    content = make_docx()
    service.save(USER, "cv.docx", content)

    service.remember_structure(USER, content, make_cv())

    assert service.require(USER).structured == make_cv()


def test_a_structure_from_an_older_version_is_not_reused() -> None:
    from tests.test_tailoring_guard import make_cv

    repository = MemorySavedCvs()
    content = make_docx()
    repository.stored[USER] = SavedCv("cv.docx", content, make_cv(), structure_version=0)

    assert SavedCvService(repository).require(USER).structured is None


def test_asking_for_a_missing_saved_cv_says_what_to_do() -> None:
    with pytest.raises(NoSavedCvError, match="Upload your CV first"):
        SavedCvService(MemorySavedCvs()).require(USER)
