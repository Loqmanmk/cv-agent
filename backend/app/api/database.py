from functools import lru_cache

from sqlalchemy import Engine

from app.core.config import get_settings
from app.infrastructure.db.engine import create_db_engine


@lru_cache
def get_engine() -> Engine:
    """One connection pool for the whole application."""
    url = get_settings().database_url
    if url is None:
        raise RuntimeError("DATABASE_URL is not set in backend/.env")
    return create_db_engine(url.get_secret_value())
