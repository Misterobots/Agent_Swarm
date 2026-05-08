"""Alembic migration environment for MemPalace.

Uses async SQLAlchemy (asyncpg) to match the runtime app. The DB URL is
sourced from app.database.DATABASE_URL so migrations always target the same
DB the app talks to. Migrations are restricted to the `mempalace` schema;
the alembic_version table also lives there.
"""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Make the app package importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, DATABASE_URL  # noqa: E402
# Importing pgvector ensures the Vector type is registered for autogenerate.
from pgvector.sqlalchemy import Vector  # noqa: E402,F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Restrict autogenerate + reflection to the mempalace schema."""
    if type_ == "table" and getattr(obj, "schema", None) != "mempalace":
        return False
    return True


def run_migrations_offline() -> None:
    """Generate SQL without a live DB connection (--sql mode)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="mempalace",
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema="mempalace",
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
