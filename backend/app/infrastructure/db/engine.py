from sqlalchemy import Engine, create_engine


def create_db_engine(url: str) -> Engine:
    """One connection pool for the whole application. Dead connections are replaced."""
    return create_engine(url, pool_pre_ping=True)
