from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, pool

from alembic import context

# Make the backend package importable when Alembic is invoked as a console
# script (its sys.path[0] is the bin dir, not the project root).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base and every model so their tables are registered on the metadata
# (needed for autogenerate and for a correct target_metadata).
from app.database import Base
import app.models  # noqa: F401  (registers all ORM models)

target_metadata = Base.metadata


def _database_url() -> str:
    """Synchronous database URL for migrations (Alembic runs on psycopg2).

    DATABASE_URL is the same variable the app uses; convert asyncpg -> psycopg2
    so one value drives both the runtime engine and migrations.
    """
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cloudforge:cloudforge@localhost:5432/cloudforge",
    )
    return url.replace("+asyncpg", "+psycopg2")


def run_migrations_offline():
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
