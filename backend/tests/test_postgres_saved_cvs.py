import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.domain.saved_cv import SavedCv
from app.infrastructure.db.postgres_saved_cvs import PostgresSavedCvRepository
from tests.db_helpers import add_user

FIRST = SavedCv(filename="cv.docx", content=b"PK-first")
SECOND = SavedCv(filename="cv.pdf", content=b"%PDF-second")


@pytest.fixture
def saved_cvs(clean_engine: Engine) -> PostgresSavedCvRepository:
    return PostgresSavedCvRepository(clean_engine)


@pytest.fixture
def user_id(clean_engine: Engine) -> uuid.UUID:
    return add_user(clean_engine, "jane@example.com")


def count_rows(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM saved_cvs")).scalar_one())


def test_a_new_user_has_no_saved_cv(
    saved_cvs: PostgresSavedCvRepository, user_id: uuid.UUID
) -> None:
    assert saved_cvs.info(user_id) is None
    assert saved_cvs.get(user_id) is None


def test_a_saved_cv_is_given_back_with_its_size_and_date(
    saved_cvs: PostgresSavedCvRepository, user_id: uuid.UUID
) -> None:
    info = saved_cvs.save(user_id, FIRST)

    assert (info.filename, info.size) == ("cv.docx", len(FIRST.content))
    assert info.uploaded_at.tzinfo is not None
    assert saved_cvs.info(user_id) == info
    assert saved_cvs.get(user_id) == FIRST


def test_saving_again_replaces_the_cv_and_keeps_one_row(
    saved_cvs: PostgresSavedCvRepository, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    saved_cvs.save(user_id, FIRST)

    saved_cvs.save(user_id, SECOND)

    assert saved_cvs.get(user_id) == SECOND
    assert count_rows(clean_engine) == 1


def test_each_user_only_sees_their_own_cv(
    saved_cvs: PostgresSavedCvRepository, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    other = add_user(clean_engine, "other@example.com")

    saved_cvs.save(user_id, FIRST)

    assert saved_cvs.get(other) is None


def test_deleting_removes_the_file(
    saved_cvs: PostgresSavedCvRepository, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    saved_cvs.save(user_id, FIRST)

    saved_cvs.delete(user_id)
    saved_cvs.delete(user_id)

    assert saved_cvs.get(user_id) is None
    assert count_rows(clean_engine) == 0


def test_deleting_the_user_deletes_the_saved_cv(
    saved_cvs: PostgresSavedCvRepository, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    saved_cvs.save(user_id, FIRST)

    with clean_engine.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})

    assert count_rows(clean_engine) == 0


def test_the_database_refuses_an_empty_file(
    saved_cvs: PostgresSavedCvRepository, user_id: uuid.UUID
) -> None:
    with pytest.raises(IntegrityError):
        saved_cvs.save(user_id, SavedCv(filename="cv.pdf", content=b""))
