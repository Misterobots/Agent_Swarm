"""MemPalace database layer — async SQLAlchemy + pgvector models."""

import os
import logging
from uuid import uuid4

from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime, Index,
    text, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from pgvector.sqlalchemy import Vector

logger = logging.getLogger("mempalace.database")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_USER = os.getenv("MEMPALACE_DB_USER", os.getenv("LANGFUSE_DB_USER", "langfuse"))
DB_PASS = os.getenv("MEMPALACE_DB_PASSWORD", os.getenv("LANGFUSE_DB_PASSWORD", "langfuseshively"))
DB_HOST = os.getenv("MEMPALACE_DB_HOST", "postgres")
DB_PORT = os.getenv("MEMPALACE_DB_PORT", "5432")
DB_NAME = os.getenv("MEMPALACE_DB_NAME", os.getenv("LANGFUSE_DB_NAME", "langfuse"))

DATABASE_URL = (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

VECTOR_DIM = 768  # nomic-embed-text dimension

# ---------------------------------------------------------------------------
# Engine + session factory
# ---------------------------------------------------------------------------
engine = create_async_engine(DATABASE_URL, echo=False, pool_size=5, max_overflow=10)
async_session = async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# ORM Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Memory(Base):
    """Semantic, episodic, and procedural memories with vector embeddings."""

    __tablename__ = "memories"
    __table_args__ = (
        Index("ix_mem_embedding", "embedding", postgresql_using="ivfflat",
              postgresql_with={"lists": 100},
              postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_mem_owner_type", "owner_id", "memory_type"),
        Index("ix_mem_team", "team_id"),
        {"schema": "mempalace"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    content = Column(Text, nullable=False)
    memory_type = Column(String(50), nullable=False)   # semantic | episodic | procedural
    domain = Column(String(100))                        # visual | coding | general | ...
    agent_id = Column(String(100))                      # creating agent
    team_id = Column(String(100))                       # NULL=individual, set=team scope
    owner_id = Column(String(100))                      # user identity
    embedding = Column(Vector(VECTOR_DIM))
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    access_count = Column(Integer, default=0)
    relevance_decay = Column(Float, default=1.0)


class AgentSnapshot(Base):
    """Per-agent learned state snapshots."""

    __tablename__ = "agent_snapshots"
    __table_args__ = (
        Index("ix_snap_agent_owner", "agent_id", "owner_id"),
        {"schema": "mempalace"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(String(100), nullable=False)
    owner_id = Column(String(100))
    snapshot_data = Column(JSONB, nullable=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TeamMemory(Base):
    """Shared key-value memory for coordinator teams."""

    __tablename__ = "team_memories"
    __table_args__ = (
        Index("ix_team_mem_team", "team_id"),
        {"schema": "mempalace"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    team_id = Column(String(100), nullable=False)
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)
    embedding = Column(Vector(VECTOR_DIM))
    author_agent = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Bootstrap: create schema + extension + tables
# ---------------------------------------------------------------------------
async def init_db():
    """Create mempalace schema, enable pgvector, and create all tables."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS mempalace"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("MemPalace database initialized")
