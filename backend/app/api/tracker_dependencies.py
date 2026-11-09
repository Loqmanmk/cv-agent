import uuid
from functools import lru_cache

from sqlalchemy import Engine

from app.core.config import get_settings
from app.infrastructure.db.engine import create_db_engine
from app.infrastructure.db.local_user import LocalUser
from app.infrastructure.tracker_factory import build_tracker_service
from app.services.tracker_service import TrackerService


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if url is None:
        raise RuntimeError("DATABASE_URL is not set in backend/.env")
    return create_db_engine(url.get_secret_value())


@lru_cache
def get_local_user() -> LocalUser:
    return LocalUser(get_engine())


@lru_cache
def get_tracker_service() -> TrackerService:
    return build_tracker_service(get_engine())


def get_current_user_id() -> uuid.UUID:
    """The owner of the request. TEMPORARY: Step 48 replaces this with the logged-in user."""
    return get_local_user().user_id()
