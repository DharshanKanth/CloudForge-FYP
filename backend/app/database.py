import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cloudforge:cloudforge@localhost:5432/cloudforge"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def run_migrations() -> None:
    """Bring the database schema up to date via Alembic.

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
    sync_engine = create_engine(sync_url, poolclass=pool.NullPool)
    try:
        existing = set(inspect(sync_engine).get_table_names())
    finally:
        sync_engine.dispose()

    if "users" in existing and "alembic_version" not in existing:
        command.stamp(cfg, "head")
    command.upgrade(cfg, "head")


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
