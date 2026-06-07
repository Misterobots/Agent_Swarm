"""MemPalace database layer — async SQLAlchemy + pgvector models."""

from __future__ import annotations

import asyncio
import os
import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, String, Text, Integer, Float, DateTime, Index,
    ForeignKey, UniqueConstraint, text, func,
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
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=20,
    pool_pre_ping=True,    # detect dropped connections (e.g. after pg restart)
    pool_recycle=1800,     # recycle every 30 min to avoid stale connections
)
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
        # NOTE: IVFFlat is only well-tuned after the table has data — the
        # initial index built at bootstrap on an empty table is degenerate.
        # When data volume justifies it, REINDEX or migrate to HNSW
        # (pgvector >= 0.5: postgresql_using="hnsw", with m/ef_construction
        # parameters). Tracked as a follow-up; not blocking current scale.
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
    entity_extracted = Column(Boolean, default=False, server_default="false")


class AgentSnapshot(Base):
    """Per-agent learned state snapshots."""

    __tablename__ = "agent_snapshots"
    __table_args__ = (
        Index("ix_snap_agent_owner", "agent_id", "owner_id"),
        UniqueConstraint("agent_id", "owner_id", "version",
                         name="uq_snap_agent_owner_version"),
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
        UniqueConstraint("team_id", "key", name="uq_team_mem_team_key"),
        {"schema": "mempalace"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    team_id = Column(String(100), nullable=False)
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)
    embedding = Column(Vector(VECTOR_DIM))
    author_agent = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MemoryAuditLog(Base):
    """Audit trail for memory modifications (edit, delete, create by admin)."""

    __tablename__ = "memory_audit_log"
    __table_args__ = (
        Index("ix_audit_memory_id", "memory_id"),
        {"schema": "mempalace"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    # memory_id is intentionally NOT a foreign key. Delete audits must
    # survive the deletion of the memory they describe — that is the entire
    # point of the audit trail. CASCADE would erase the trail; SET NULL
    # would erase the historical id. UUIDs make collision risk negligible.
    memory_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(20), nullable=False)          # created | edited | deleted
    actor_id = Column(String(100), nullable=False)
    actor_role = Column(String(20), nullable=False)       # user | admin
    previous_content = Column(Text)
    new_content = Column(Text)
    changed_fields = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Entity(Base):
    """Named entity extracted from memories.

    entity_type is one of: technology | project | person | concept | decision | tool
    memory_count tracks how many memories have referenced this entity (incremented
    on each extraction run that finds it).
    """

    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_owner", "owner_id"),
        # The (owner_id, lower(label)) unique index is created by the Alembic
        # migration — SQLAlchemy ORM definitions don't support functional indexes
        # so dedup is handled at the application level via SELECT-first.
        {"schema": "mempalace"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    label = Column(String(200), nullable=False)
    entity_type = Column(String(50), nullable=False)
    description = Column(Text)
    owner_id = Column(String(100))
    memory_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EntityRelation(Base):
    """Typed directed relationship between two entities.

    evidence_memory_ids (JSONB array of UUID strings) records which memories
    gave rise to this relation — useful for tracing why the edge exists.
    """

    __tablename__ = "entity_relations"
    __table_args__ = (
        Index("ix_entity_rel_source", "source_id"),
        Index("ix_entity_rel_target", "target_id"),
        Index("ix_entity_rel_owner", "owner_id"),
        UniqueConstraint("source_id", "target_id", "relation_type", name="uq_entity_rel"),
        {"schema": "mempalace"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mempalace.entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mempalace.entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type = Column(String(100), nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    evidence_memory_ids = Column(JSONB, default=list, server_default="'[]'::jsonb")
    owner_id = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExtractionLog(Base):
    """Per-attempt log of conversation extraction calls, keyed by owner_id."""

    __tablename__ = "extraction_log"
    __table_args__ = (
        Index("ix_extract_log_owner", "owner_id"),
        Index("ix_extract_log_attempted_at", "attempted_at"),
        {"schema": "mempalace"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id = Column(String(100), nullable=False)
    agent_id = Column(String(100))
    memories_stored = Column(Integer, default=0)          # 0 = nothing extracted
    conversation_length = Column(Integer, default=0)      # chars, for debug
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Bootstrap: ensure extension/schema exist, then run pending migrations
# ---------------------------------------------------------------------------
async def init_db():
    """Bootstrap database: pgvector + mempalace schema + alembic upgrade head.

    Schema changes are owned by Alembic migrations under alembic/versions/.
    This function only handles the infrastructure pieces Alembic doesn't:
    creating the pgvector extension and the mempalace schema namespace.
    """
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS mempalace"))

    # Defer alembic imports so the database module remains importable in
    # contexts where alembic isn't installed (e.g. tooling, tests).
    from alembic import command
    from alembic.config import Config

    cfg_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(cfg_path))
    # alembic.command.upgrade is sync; env.py uses asyncio.run internally,
    # so we offload to a worker thread to avoid nested event-loop issues.
    await asyncio.to_thread(command.upgrade, cfg, "head")

    logger.info("MemPalace database initialized")
