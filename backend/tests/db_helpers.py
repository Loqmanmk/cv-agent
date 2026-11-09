import uuid

from sqlalchemy import Engine, text


def add_user(engine: Engine, email: str = "jane@example.com") -> uuid.UUID:
    with engine.begin() as connection:
        user_id = connection.execute(
            text("INSERT INTO users (email, password_hash) VALUES (:email, 'hash') RETURNING id"),
            {"email": email},
        ).scalar_one()
    assert isinstance(user_id, uuid.UUID)
    return user_id
