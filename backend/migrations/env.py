from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.infrastructure.db.models import Base

config = context.config
target_metadata = Base.metadata


def database_url() -> str:
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured
    secret = get_settings().database_url
    if secret is None:
        raise RuntimeError("DATABASE_URL is not set in backend/.env")
    return secret.get_secret_value()


def run_migrations() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = database_url()
    engine = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported. Run them against a database.")
run_migrations()
