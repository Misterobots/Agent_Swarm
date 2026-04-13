"""MemPalace — Hierarchical Semantic Memory Service for Agent Swarm.

Provides three memory subsystems:
  1. Semantic memories — vector-searchable facts extracted from conversations
  2. Agent snapshots  — per-agent learned state persistence
  3. Team memories    — shared state for coordinator task teams
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, func, update, text

from .database import async_session, init_db, Memory, AgentSnapshot, TeamMemory
from .embeddings import embed_text, embed_texts, extract_memories, close_client

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("mempalace")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MemPalace starting — initializing database …")
    await init_db()
    logger.info("MemPalace ready")
    yield
    await close_client()
    logger.info("MemPalace shutdown")


app = FastAPI(
    title="MemPalace",
    description="Hierarchical semantic memory for Agent Swarm",
    version="0.1.0",
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════════════

class MemoryCreate(BaseModel):
    content: str
    memory_type: str = "semantic"      # semantic | episodic | procedural
    domain: str = "general"
    agent_id: Optional[str] = None
    team_id: Optional[str] = None
    owner_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class MemoryOut(BaseModel):
    id: str
    content: str
    memory_type: str
    domain: Optional[str]
    agent_id: Optional[str]
    team_id: Optional[str]
    owner_id: Optional[str]
    metadata: dict
    created_at: str
    access_count: int
    score: Optional[float] = None


class SearchQuery(BaseModel):
    query: str
    owner_id: Optional[str] = None
    agent_id: Optional[str] = None
    team_id: Optional[str] = None
    memory_type: Optional[str] = None
    domain: Optional[str] = None
    limit: int = 10


class ExtractionRequest(BaseModel):
    conversation: str
    owner_id: Optional[str] = None
    agent_id: Optional[str] = None
    team_id: Optional[str] = None


class SnapshotCreate(BaseModel):
    agent_id: str
    owner_id: Optional[str] = None
    snapshot_data: dict


class SnapshotOut(BaseModel):
    id: str
    agent_id: str
    owner_id: Optional[str]
    snapshot_data: dict
    version: int
    created_at: str


class TeamMemoryCreate(BaseModel):
    key: str
    value: str
    author_agent: Optional[str] = None


class TeamMemoryOut(BaseModel):
    id: str
    team_id: str
    key: str
    value: str
    author_agent: Optional[str]
    created_at: str


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _memory_to_out(m: Memory, score: float | None = None) -> MemoryOut:
    return MemoryOut(
        id=str(m.id),
        content=m.content,
        memory_type=m.memory_type,
        domain=m.domain,
        agent_id=m.agent_id,
        team_id=m.team_id,
        owner_id=m.owner_id,
        metadata=m.metadata_ or {},
        created_at=m.created_at.isoformat() if m.created_at else "",
        access_count=m.access_count or 0,
        score=score,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    async with async_session() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "service": "mempalace"}


# ═══════════════════════════════════════════════════════════════════════════
# Memories — CRUD + Semantic Search
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/v1/memories", response_model=MemoryOut)
async def store_memory(req: MemoryCreate):
    """Store a memory with auto-generated embedding."""
    embedding = await embed_text(req.content)
    mem = Memory(
        content=req.content,
        memory_type=req.memory_type,
        domain=req.domain,
        agent_id=req.agent_id,
        team_id=req.team_id,
        owner_id=req.owner_id,
        embedding=embedding,
        metadata_=req.metadata,
    )
    async with async_session() as session:
        session.add(mem)
        await session.commit()
        await session.refresh(mem)
    logger.info("Stored memory %s [%s/%s] for owner=%s",
                mem.id, mem.memory_type, mem.domain, mem.owner_id)
    return _memory_to_out(mem)


@app.post("/v1/memories/search", response_model=list[MemoryOut])
async def search_memories(req: SearchQuery):
    """Semantic similarity search over memories."""
    query_embedding = await embed_text(req.query)

    # Build cosine distance expression
    distance = Memory.embedding.cosine_distance(query_embedding).label("distance")

    stmt = select(Memory, distance).order_by(distance)

    # Filters
    if req.owner_id:
        stmt = stmt.where(Memory.owner_id == req.owner_id)
    if req.agent_id:
        stmt = stmt.where(Memory.agent_id == req.agent_id)
    if req.team_id:
        stmt = stmt.where(Memory.team_id == req.team_id)
    if req.memory_type:
        stmt = stmt.where(Memory.memory_type == req.memory_type)
    if req.domain:
        stmt = stmt.where(Memory.domain == req.domain)

    stmt = stmt.limit(req.limit)

    async with async_session() as session:
        rows = (await session.execute(stmt)).all()
        # Bump access counts
        ids = [row[0].id for row in rows]
        if ids:
            await session.execute(
                update(Memory)
                .where(Memory.id.in_(ids))
                .values(access_count=Memory.access_count + 1)
            )
            await session.commit()

    results = []
    for mem, dist in rows:
        similarity = 1.0 - (dist or 0.0)
        results.append(_memory_to_out(mem, score=round(similarity, 4)))
    return results


@app.delete("/v1/memories/{memory_id}")
async def delete_memory(memory_id: UUID):
    """Delete a specific memory."""
    async with async_session() as session:
        result = await session.execute(
            delete(Memory).where(Memory.id == memory_id)
        )
        await session.commit()
    if result.rowcount == 0:
        raise HTTPException(404, "Memory not found")
    return {"status": "deleted", "id": str(memory_id)}


@app.get("/v1/memories/stats")
async def memory_stats():
    """Return memory counts by type and domain."""
    async with async_session() as session:
        rows = (await session.execute(
            select(
                Memory.memory_type,
                Memory.domain,
                func.count(Memory.id),
            ).group_by(Memory.memory_type, Memory.domain)
        )).all()
    return {
        "total": sum(r[2] for r in rows),
        "breakdown": [
            {"type": r[0], "domain": r[1], "count": r[2]}
            for r in rows
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Memory Extraction — auto-extract from conversations
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/v1/extract", response_model=list[MemoryOut])
async def extract_and_store(req: ExtractionRequest):
    """Extract memories from conversation text and store them."""
    extracted = await extract_memories(req.conversation)
    if not extracted:
        return []

    # Generate embeddings in batch
    contents = [m["content"] for m in extracted]
    embeddings = await embed_texts(contents)

    stored = []
    async with async_session() as session:
        for item, emb in zip(extracted, embeddings):
            mem = Memory(
                content=item["content"],
                memory_type=item["type"],
                domain=item.get("domain", "general"),
                agent_id=req.agent_id,
                team_id=req.team_id,
                owner_id=req.owner_id,
                embedding=emb,
            )
            session.add(mem)
            stored.append(mem)
        await session.commit()
        for mem in stored:
            await session.refresh(mem)

    logger.info("Extracted %d memories from conversation (owner=%s, agent=%s)",
                len(stored), req.owner_id, req.agent_id)
    return [_memory_to_out(m) for m in stored]


# ═══════════════════════════════════════════════════════════════════════════
# Agent Snapshots
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/v1/snapshots", response_model=SnapshotOut)
async def save_snapshot(req: SnapshotCreate):
    """Save a versioned agent state snapshot."""
    async with async_session() as session:
        # Get current max version
        result = await session.execute(
            select(func.coalesce(func.max(AgentSnapshot.version), 0))
            .where(AgentSnapshot.agent_id == req.agent_id)
            .where(AgentSnapshot.owner_id == req.owner_id)
        )
        max_ver = result.scalar() or 0

        snap = AgentSnapshot(
            agent_id=req.agent_id,
            owner_id=req.owner_id,
            snapshot_data=req.snapshot_data,
            version=max_ver + 1,
        )
        session.add(snap)
        await session.commit()
        await session.refresh(snap)

    logger.info("Snapshot saved: agent=%s owner=%s v%d",
                req.agent_id, req.owner_id, snap.version)
    return SnapshotOut(
        id=str(snap.id),
        agent_id=snap.agent_id,
        owner_id=snap.owner_id,
        snapshot_data=snap.snapshot_data,
        version=snap.version,
        created_at=snap.created_at.isoformat() if snap.created_at else "",
    )


@app.get("/v1/snapshots/{agent_id}", response_model=Optional[SnapshotOut])
async def get_snapshot(agent_id: str, owner_id: Optional[str] = None):
    """Get the latest snapshot for an agent."""
    stmt = (
        select(AgentSnapshot)
        .where(AgentSnapshot.agent_id == agent_id)
        .order_by(AgentSnapshot.version.desc())
        .limit(1)
    )
    if owner_id:
        stmt = stmt.where(AgentSnapshot.owner_id == owner_id)

    async with async_session() as session:
        result = await session.execute(stmt)
        snap = result.scalar_one_or_none()

    if not snap:
        return None

    return SnapshotOut(
        id=str(snap.id),
        agent_id=snap.agent_id,
        owner_id=snap.owner_id,
        snapshot_data=snap.snapshot_data,
        version=snap.version,
        created_at=snap.created_at.isoformat() if snap.created_at else "",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Team Memory
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/v1/team/{team_id}", response_model=TeamMemoryOut)
async def store_team_memory(team_id: str, req: TeamMemoryCreate):
    """Store or update a key-value pair in team memory."""
    embedding = await embed_text(f"{req.key}: {req.value}")

    async with async_session() as session:
        # Upsert: check if key exists
        existing = await session.execute(
            select(TeamMemory)
            .where(TeamMemory.team_id == team_id)
            .where(TeamMemory.key == req.key)
        )
        existing_mem = existing.scalar_one_or_none()

        if existing_mem:
            existing_mem.value = req.value
            existing_mem.embedding = embedding
            existing_mem.author_agent = req.author_agent
            mem = existing_mem
        else:
            mem = TeamMemory(
                team_id=team_id,
                key=req.key,
                value=req.value,
                embedding=embedding,
                author_agent=req.author_agent,
            )
            session.add(mem)

        await session.commit()
        await session.refresh(mem)

    return TeamMemoryOut(
        id=str(mem.id),
        team_id=mem.team_id,
        key=mem.key,
        value=mem.value,
        author_agent=mem.author_agent,
        created_at=mem.created_at.isoformat() if mem.created_at else "",
    )


@app.get("/v1/team/{team_id}", response_model=list[TeamMemoryOut])
async def get_team_memories(team_id: str):
    """Get all memories for a team."""
    async with async_session() as session:
        result = await session.execute(
            select(TeamMemory)
            .where(TeamMemory.team_id == team_id)
            .order_by(TeamMemory.created_at)
        )
        mems = result.scalars().all()

    return [
        TeamMemoryOut(
            id=str(m.id),
            team_id=m.team_id,
            key=m.key,
            value=m.value,
            author_agent=m.author_agent,
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in mems
    ]


@app.post("/v1/team/{team_id}/search", response_model=list[TeamMemoryOut])
async def search_team_memory(team_id: str, req: SearchQuery):
    """Semantic search within a team's memory."""
    query_embedding = await embed_text(req.query)
    distance = TeamMemory.embedding.cosine_distance(query_embedding).label("distance")

    stmt = (
        select(TeamMemory, distance)
        .where(TeamMemory.team_id == team_id)
        .order_by(distance)
        .limit(req.limit)
    )

    async with async_session() as session:
        rows = (await session.execute(stmt)).all()

    return [
        TeamMemoryOut(
            id=str(m.id),
            team_id=m.team_id,
            key=m.key,
            value=m.value,
            author_agent=m.author_agent,
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m, _ in rows
    ]


@app.delete("/v1/team/{team_id}")
async def clear_team_memory(team_id: str):
    """Clear all memories for a team (post-coordination cleanup)."""
    async with async_session() as session:
        result = await session.execute(
            delete(TeamMemory).where(TeamMemory.team_id == team_id)
        )
        await session.commit()
    return {"status": "cleared", "team_id": team_id, "deleted": result.rowcount}
