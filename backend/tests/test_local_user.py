from sqlalchemy import Engine, text

from app.infrastructure.db.local_user import LOCAL_EMAIL, UNUSABLE_HASH, LocalUser


def user_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM users")).scalar_one())


def test_the_local_user_is_created_once_and_found_again(clean_engine: Engine) -> None:
    first = LocalUser(clean_engine).user_id()
    second = LocalUser(clean_engine).user_id()

    assert first == second
    assert user_count(clean_engine) == 1


def test_the_id_is_remembered_by_the_same_instance(clean_engine: Engine) -> None:
    local = LocalUser(clean_engine)

    assert local.user_id() == local.user_id()


def test_the_local_user_cannot_log_in(clean_engine: Engine) -> None:
    LocalUser(clean_engine).user_id()

    with clean_engine.connect() as connection:
        row = connection.execute(text("SELECT email, password_hash FROM users")).one()

    assert row.email == LOCAL_EMAIL
    assert row.password_hash == UNUSABLE_HASH
