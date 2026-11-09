import uuid

from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert

from app.infrastructure.db.models import User

LOCAL_EMAIL = "local@cvagent.invalid"
# Not a valid password hash, so no password can ever match it: this user cannot log in.
UNUSABLE_HASH = "!"


class LocalUser:
    """The one owner of the data until real accounts exist (Step 48)."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._user_id: uuid.UUID | None = None

    def user_id(self) -> uuid.UUID:
        if self._user_id is None:
            with self._engine.begin() as connection:
                connection.execute(
                    insert(User)
                    .values(email=LOCAL_EMAIL, password_hash=UNUSABLE_HASH)
                    .on_conflict_do_nothing(index_elements=["email"])
                )
                self._user_id = connection.execute(
                    select(User.id).where(User.email == LOCAL_EMAIL)
                ).scalar_one()
        return self._user_id
