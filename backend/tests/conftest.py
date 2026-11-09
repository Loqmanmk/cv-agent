import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NoReturn

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError

from app.core.config import Settings

BACKEND = Path(__file__).resolve().parent.parent


def _database_unavailable(reason: str) -> NoReturn:
    """Skip on a developer machine. In CI (REQUIRE_DATABASE is set) a skip would hide a problem."""
    if os.environ.get("REQUIRE_DATABASE"):
        pytest.fail(reason)
    pytest.skip(reason)


def alembic_config(url: URL) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    rendered = url.render_as_string(hide_password=False).replace("%", "%%")
    config.set_main_option("sqlalchemy.url", rendered)
    return config


@pytest.fixture(scope="session")
def server_url() -> URL:
    configured = Settings().database_url
    if configured is None:
        _database_unavailable("DATABASE_URL is not set. Start PostgreSQL: docker compose up -d")
    url = make_url(configured.get_secret_value())
    engine = create_engine(url)
    try:
        with engine.connect():
            pass
    except OperationalError:
        _database_unavailable("PostgreSQL is not reachable. Start it: docker compose up -d")
    finally:
        engine.dispose()
    return url


@contextmanager
def temporary_database(server_url: URL) -> Iterator[URL]:
    """A new empty database, deleted afterwards. Your real database is never touched."""
    name = f"cvagent_test_{uuid.uuid4().hex}"
    admin = create_engine(server_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        try:
            yield server_url.set(database=name)
        finally:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()


@pytest.fixture
def empty_database(server_url: URL) -> Iterator[URL]:
    with temporary_database(server_url) as url:
        yield url


@pytest.fixture(scope="module")
def migrated_engine(server_url: URL) -> Iterator[Engine]:
    with temporary_database(server_url) as url:
        command.upgrade(alembic_config(url), "head")
        engine = create_engine(url)
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def clean_engine(migrated_engine: Engine) -> Engine:
    """The migrated database with no rows, so each test starts from zero."""
    with migrated_engine.begin() as connection:
        connection.execute(text("TRUNCATE users RESTART IDENTITY CASCADE"))
    return migrated_engine
