import logging
import os
import time
from pathlib import Path

from sqlalchemy import create_engine, inspect, pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("cloudforge.database")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cloudforge:cloudforge@localhost:5432/cloudforge"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def run_migrations(max_attempts: int = 30, delay_seconds: float = 2.0) -> None:
    """Bring the database schema up to date via Alembic.

    Waits for the database to become reachable before migrating, so the API and
    worker do not crash when they start at the same time as Postgres (or right
    after a Docker/host restart). Without this retry the first connection raised
    and the whole app failed to start permanently.

    Databases created before this change (by the old
    ``Base.metadata.create_all`` startup) already have the tables but no
    ``alembic_version`` row. Those are stamped as current first, so adopting
    Alembic never tries to recreate existing tables or delete data.
    """
    from alembic import command
    from alembic.config import Config as AlembicConfig

    backend_dir = Path(__file__).resolve().parents[1]
    cfg = AlembicConfig(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    sync_url = DATABASE_URL.replace("+asyncpg", "+psycopg2")

    existing = None
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            sync_engine = create_engine(sync_url, poolclass=pool.NullPool)
            try:
                existing = set(inspect(sync_engine).get_table_names())
            finally:
                sync_engine.dispose()
            break
        except Exception as exc:  # noqa: BLE001 - retry on any connection error
            last_error = exc
            logger.warning(
                "Database not reachable (attempt %d/%d): %s",
                attempt, max_attempts, exc,
            )
            time.sleep(delay_seconds)

    if existing is None:
        raise RuntimeError(
            f"Database not reachable after {max_attempts} attempts"
        ) from last_error

    if "users" in existing and "alembic_version" not in existing:
        command.stamp(cfg, "head")
    command.upgrade(cfg, "head")


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
