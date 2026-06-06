"""MemPalace — Hierarchical Semantic Memory Service for Agent Swarm.

Provides three memory subsystems:
  1. Semantic memories — vector-searchable facts extracted from conversations
  2. Agent snapshots  — per-agent learned state persistence
  3. Team memories    — shared state for coordinator task teams
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, func, update, text, case
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from .database import async_session, init_db, Memory, AgentSnapshot, TeamMemory, MemoryAuditLog, ExtractionLog
from .embeddings import embed_text, embed_texts, extract_memories, close_client
from . import graph as graph_lib

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("mempalace")


# ---------------------------------------------------------------------------
# MCP server — defined before lifespan because lifespan references _mcp.
# Tool implementations are registered further down once the ORM models and
# helpers are in scope. Mounted onto the FastAPI app at the bottom of the file.
# ---------------------------------------------------------------------------
_mcp = FastMCP(
    "MemPalace",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["192.168.2.102:*", "localhost:*", "127.0.0.1:*", "hopper:*"],
    ),
)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # StreamableHTTP session manager must be started before handling MCP requests
    async with _mcp.session_manager.run():
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
    wing: Optional[str] = None
    hall: Optional[str] = None
    room: Optional[str] = None


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


# ── Palace Viewer schemas ──────────────────────────────────────────────────

class RoomOut(BaseModel):
    name: str
    drawer_count: int


class HallOut(BaseModel):
    name: str
    rooms: list[RoomOut]


class WingOut(BaseModel):
    name: str
    halls: list[HallOut]


class PalaceLayoutOut(BaseModel):
    wings: list[WingOut]
    total_memories: int


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    memory_type: Optional[str] = None
    domain: Optional[str] = None
    metadata: Optional[dict] = None


class AuditLogOut(BaseModel):
    id: str
    memory_id: str
    action: str
    actor_id: str
    actor_role: str
    previous_content: Optional[str]
    new_content: Optional[str]
    changed_fields: dict
    created_at: str


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _score(dist: float | None) -> float:
    """Convert pgvector cosine distance to a similarity score.

    pgvector's cosine_distance returns 0.0 (identical) … 2.0 (opposite).
    Similarity = 1 - distance, so the result is in [-1.0, 1.0]. Round
    to 4 decimals for compact JSON.
    """
    return round(1.0 - (dist or 0.0), 4)


def _memory_to_out(m: Memory, score: float | None = None) -> MemoryOut:
    meta = m.metadata_ or {}
    return MemoryOut(
        id=str(m.id),
        content=m.content,
        memory_type=m.memory_type,
        domain=m.domain,
        agent_id=m.agent_id,
        team_id=m.team_id,
        owner_id=m.owner_id,
        metadata=meta,
        created_at=m.created_at.isoformat() if m.created_at else "",
        access_count=m.access_count or 0,
        score=score,
        wing=meta.get("wing"),
        hall=meta.get("hall"),
        room=meta.get("room"),
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
async def store_memory(req: MemoryCreate, actor_id: str = ""):
    """Store a memory with auto-generated embedding."""
    owner_id = (req.owner_id or "").strip()
    if not owner_id:
        raise HTTPException(400, "owner_id is required for memory writes")

    embedding = await embed_text(req.content)
    mem = Memory(
        content=req.content,
        memory_type=req.memory_type,
        domain=req.domain,
        agent_id=req.agent_id,
        team_id=req.team_id,
        owner_id=owner_id,
        embedding=embedding,
        metadata_=req.metadata,
    )
    async with async_session() as session:
        session.add(mem)
        await session.flush()
        session.add(MemoryAuditLog(
            memory_id=mem.id,
            action="created",
            actor_id=actor_id or req.agent_id or owner_id,
            actor_role="user",
            previous_content=None,
            new_content=mem.content,
            changed_fields={},
        ))
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

    return [_memory_to_out(mem, score=_score(dist)) for mem, dist in rows]


@app.delete("/v1/memories/{memory_id}")
async def delete_memory(memory_id: UUID, actor_id: str = "anonymous"):
    """Delete a specific memory and audit the action."""
    async with async_session() as session:
        existing = (await session.execute(
            select(Memory).where(Memory.id == memory_id)
        )).scalar_one_or_none()
        if not existing:
            raise HTTPException(404, "Memory not found")

        prev_content = existing.content
        await session.execute(delete(Memory).where(Memory.id == memory_id))
        session.add(MemoryAuditLog(
            memory_id=memory_id,
            action="deleted",
            actor_id=actor_id,
            actor_role="user",
            previous_content=prev_content,
            new_content=None,
            changed_fields={},
        ))
        await session.commit()
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


@app.get("/v1/palace/audit/extractions")
async def extraction_audit():
    """Per-owner extraction metrics: attempts, memories stored, success rate, last seen.

    Single aggregate query — uses conditional aggregation for the success-only
    metrics (memories_stored > 0) and a correlated subquery for the live memory
    count, instead of fanning out to three separate round-trips.
    """
    success_count = func.sum(
        case((ExtractionLog.memories_stored > 0, 1), else_=0)
    ).label("success_count")
    last_success_at = func.max(
        case((ExtractionLog.memories_stored > 0, ExtractionLog.attempted_at))
    ).label("last_success_at")
    current_memory_count = (
        select(func.count(Memory.id))
        .where(Memory.owner_id == ExtractionLog.owner_id)
        .correlate(ExtractionLog)
        .scalar_subquery()
        .label("current_memory_count")
    )

    stmt = (
        select(
            ExtractionLog.owner_id,
            func.count(ExtractionLog.id).label("total_attempts"),
            func.sum(ExtractionLog.memories_stored).label("total_stored"),
            func.max(ExtractionLog.attempted_at).label("last_attempt_at"),
            success_count,
            last_success_at,
            current_memory_count,
        )
        .group_by(ExtractionLog.owner_id)
        .order_by(func.max(ExtractionLog.attempted_at).desc())
    )

    async with async_session() as session:
        rows = (await session.execute(stmt)).all()

    result = []
    for row in rows:
        attempts = row.total_attempts or 0
        result.append({
            "owner_id": row.owner_id,
            "owner_id_short": (row.owner_id[:8] + "...") if row.owner_id else "",
            "total_attempts": attempts,
            "total_memories_stored": int(row.total_stored or 0),
            "current_memory_count": row.current_memory_count or 0,
            "success_rate": round((row.success_count or 0) / attempts, 4) if attempts else 0.0,
            "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
            "last_success_at": row.last_success_at.isoformat() if row.last_success_at else None,
        })

    logger.info("Extraction audit served: %d unique owners", len(result))
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Memory Extraction — auto-extract from conversations
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/v1/extract", response_model=list[MemoryOut])
async def extract_and_store(req: ExtractionRequest):
    """Extract memories from conversation text and store them."""
    owner_id = (req.owner_id or "").strip()
    if not owner_id:
        raise HTTPException(400, "owner_id is required for extraction")

    extracted = await extract_memories(req.conversation)

    embeddings: list[list[float]] = []
    if extracted:
        embeddings = await embed_texts([m["content"] for m in extracted])

    stored: list[Memory] = []
    # Single transaction: store memories + the extraction-attempt audit row
    # commit together, so the log can never disagree with what was stored.
    async with async_session() as session:
        for item, emb in zip(extracted, embeddings):
            mem = Memory(
                content=item["content"],
                memory_type=item["type"],
                domain=item.get("domain", "general"),
                agent_id=req.agent_id,
                team_id=req.team_id,
                owner_id=owner_id,
                embedding=emb,
            )
            session.add(mem)
            stored.append(mem)

        session.add(ExtractionLog(
            owner_id=owner_id,
            agent_id=req.agent_id,
            memories_stored=len(stored),
            conversation_length=len(req.conversation),
        ))
        await session.commit()
        for mem in stored:
            await session.refresh(mem)

    logger.info("Extracted %d memories from conversation (owner=%s, agent=%s)",
                len(stored), owner_id, req.agent_id)
    return [_memory_to_out(m) for m in stored]


# ═══════════════════════════════════════════════════════════════════════════
# Agent Snapshots
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/v1/snapshots", response_model=SnapshotOut)
async def save_snapshot(req: SnapshotCreate):
    """Save a versioned agent state snapshot.

    Race-safe: retries on the unique (agent_id, owner_id, version) constraint
    if a concurrent writer claimed the same version.
    """
    last_err: Exception | None = None
    for _ in range(5):
        async with async_session() as session:
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
            try:
                await session.commit()
                await session.refresh(snap)
                break
            except IntegrityError as exc:
                last_err = exc
                await session.rollback()
                continue
    else:
        logger.error("Snapshot save failed after retries: %s", last_err)
        raise HTTPException(503, "Snapshot save contention — retry later")

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
    """Store or update a key-value pair in team memory.

    Atomic upsert via INSERT ... ON CONFLICT (team_id, key) DO UPDATE — safe
    against concurrent writers thanks to uq_team_mem_team_key.
    """
    embedding = await embed_text(f"{req.key}: {req.value}")

    stmt = pg_insert(TeamMemory).values(
        team_id=team_id,
        key=req.key,
        value=req.value,
        embedding=embedding,
        author_agent=req.author_agent,
    ).on_conflict_do_update(
        constraint="uq_team_mem_team_key",
        set_={
            "value": req.value,
            "embedding": embedding,
            "author_agent": req.author_agent,
        },
    ).returning(TeamMemory)

    async with async_session() as session:
        result = await session.execute(stmt)
        mem = result.scalar_one()
        await session.commit()

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


# ═══════════════════════════════════════════════════════════════════════════
# Palace Viewer — Layout & Navigation
# ═══════════════════════════════════════════════════════════════════════════

_HALL_MAP = {
    "semantic": "hall_facts",
    "episodic": "hall_events",
    "procedural": "hall_advice",
    "preference": "hall_preferences",
    "discovery": "hall_discoveries",
}
_HALL_MAP_REVERSE = {v: k for k, v in _HALL_MAP.items()}


def _derive_wing(
    agent_id: str | None,
    team_id: str | None,
    owner_id: str | None = None,
) -> str:
    if team_id:
        return f"wing_team_{team_id}"
    if agent_id:
        return f"wing_agent_{agent_id}"
    if owner_id:
        return f"wing_owner_{owner_id}"
    return "wing_self"


@app.get("/v1/palace/layout", response_model=PalaceLayoutOut)
async def palace_layout(
    owner_id: Optional[str] = None,
    agent_id: Optional[str] = None,
):
    """Return hierarchical palace layout: wings → halls → rooms → drawer counts."""
    async with async_session() as session:
        stmt = select(
            Memory.agent_id,
            Memory.team_id,
            Memory.owner_id,
            Memory.memory_type,
            Memory.domain,
            func.count(Memory.id).label("cnt"),
        ).group_by(Memory.agent_id, Memory.team_id, Memory.owner_id, Memory.memory_type, Memory.domain)

        if owner_id:
            stmt = stmt.where(Memory.owner_id == owner_id)
        if agent_id:
            stmt = stmt.where(Memory.agent_id == agent_id)

        rows = (await session.execute(stmt)).all()

    # Build the hierarchy in-memory
    wings_map: dict[str, dict[str, dict[str, int]]] = {}
    total = 0
    for (aid, tid, oid, mtype, domain, cnt) in rows:
        wing_name = _derive_wing(aid, tid, oid)
        hall_name = _HALL_MAP.get(mtype, f"hall_{mtype}")
        room_name = domain or "general"
        total += cnt

        wings_map.setdefault(wing_name, {})
        wings_map[wing_name].setdefault(hall_name, {})
        wings_map[wing_name][hall_name][room_name] = (
            wings_map[wing_name][hall_name].get(room_name, 0) + cnt
        )

    wings = []
    for wname, halls in sorted(wings_map.items()):
        hall_list = []
        for hname, rooms in sorted(halls.items()):
            room_list = [
                RoomOut(name=rname, drawer_count=rcnt)
                for rname, rcnt in sorted(rooms.items())
            ]
            hall_list.append(HallOut(name=hname, rooms=room_list))
        wings.append(WingOut(name=wname, halls=hall_list))

    return PalaceLayoutOut(wings=wings, total_memories=total)


# ═══════════════════════════════════════════════════════════════════════════
# MCP / SSE — Model Context Protocol tools (server defined at module top)
# Mounted at /mcp; SSE endpoint accessible at /mcp/sse
# ═══════════════════════════════════════════════════════════════════════════

@_mcp.tool()
async def search_memories_mcp(
    query: str,
    owner_id: str = "",
    agent_id: str = "",
    limit: int = 10,
) -> str:
    """Semantic search over memories in MemPalace. Returns top matches with scores.

    owner_id is required to scope the search — without it, agents would
    see memories across all users.
    """
    if not owner_id.strip():
        return "Error: owner_id is required to scope the search"
    query_embedding = await embed_text(query)
    distance = Memory.embedding.cosine_distance(query_embedding).label("distance")
    stmt = select(Memory, distance).order_by(distance)
    stmt = stmt.where(Memory.owner_id == owner_id)
    if agent_id:
        stmt = stmt.where(Memory.agent_id == agent_id)
    stmt = stmt.limit(limit)
    async with async_session() as session:
        rows = (await session.execute(stmt)).all()
    if not rows:
        return "No memories found."
    return "\n".join(
        f"[{_score(dist)}] ({mem.memory_type}/{mem.domain}) {mem.content}"
        for mem, dist in rows
    )


@_mcp.tool()
async def store_memory_mcp(
    content: str,
    memory_type: str = "semantic",
    domain: str = "general",
    agent_id: str = "",
    owner_id: str = "",
) -> str:
    """Store a new memory in MemPalace with an auto-generated embedding.

    owner_id is required — memories without an owner cannot be retrieved
    via the palace viewer or filtered by user.
    """
    if not owner_id.strip():
        return "Error: owner_id is required for memory writes"
    embedding = await embed_text(content)
    mem = Memory(
        content=content,
        memory_type=memory_type,
        domain=domain,
        agent_id=agent_id or None,
        owner_id=owner_id,
        embedding=embedding,
        metadata_={},
    )
    async with async_session() as session:
        session.add(mem)
        await session.commit()
        await session.refresh(mem)
    logger.info("[MCP] Stored memory %s [%s/%s]", mem.id, memory_type, domain)
    return f"Stored memory {mem.id} [{memory_type}/{domain}]"


@_mcp.tool()
async def get_memory_stats_mcp() -> str:
    """Return total memory count and breakdown by type and domain."""
    async with async_session() as session:
        rows = (await session.execute(
            select(
                Memory.memory_type,
                Memory.domain,
                func.count(Memory.id),
            ).group_by(Memory.memory_type, Memory.domain)
        )).all()
    total = sum(r[2] for r in rows)
    lines = [f"Total: {total}"]
    for mtype, domain, cnt in sorted(rows):
        lines.append(f"  {mtype}/{domain}: {cnt}")
    return "\n".join(lines)


@_mcp.tool()
async def extract_from_conversation_mcp(
    conversation: str,
    owner_id: str = "",
    agent_id: str = "",
    domain: str = "general",
) -> str:
    """Extract and store multiple memories from a conversation or session summary.

    Pass a ~500-word summary of the session (decisions made, bugs fixed, patterns
    discovered, configurations confirmed).  The LLM extraction pipeline will
    identify discrete facts and store each one with an embedding.

    Returns a summary of how many memories were stored.
    """
    extracted = await extract_memories(conversation)
    if not extracted:
        return "No memories extracted from conversation."

    contents = [m["content"] for m in extracted]
    embeddings = await embed_texts(contents)

    stored_ids = []
    async with async_session() as session:
        for item, emb in zip(extracted, embeddings):
            mem = Memory(
                content=item["content"],
                memory_type=item.get("type", "semantic"),
                domain=item.get("domain", domain),
                agent_id=agent_id or None,
                owner_id=owner_id or None,
                embedding=emb,
                metadata_={},
            )
            session.add(mem)
            stored_ids.append(item["content"][:80])
        await session.commit()

    logger.info("[MCP] extract_from_conversation stored %d memories (owner=%s)", len(stored_ids), owner_id)
    lines = [f"Stored {len(stored_ids)} memories:"]
    for s in stored_ids:
        lines.append(f"  - {s}…")
    return "\n".join(lines)


app.mount("/mcp", _mcp.streamable_http_app())


# ═══════════════════════════════════════════════════════════════════════════
# Palace Graph — knowledge graph from vector similarity
# ═══════════════════════════════════════════════════════════════════════════

_GRAPH_NODE_HARD_MAX = 2_000  # absolute safety cap for browser + query cost


@app.get("/v1/palace/graph")
async def palace_graph(
    owner_id: Optional[str] = Query(None, description="Scope to a single owner"),
    agent_id: Optional[str] = Query(None, description="Further narrow to one agent"),
    threshold: float = Query(0.35, ge=0.0, le=2.0,
                             description="Cosine *distance* cutoff for edges (lower = stricter)"),
    top_k: int = Query(5, ge=1, le=20,
                       description="Max neighbours per node"),
    limit: int = Query(300, ge=1, le=_GRAPH_NODE_HARD_MAX,
                       description="Max nodes (ordered by access_count desc)"),
    fmt: str = Query("json", alias="format",
                     description="'json' for node-link JSON, 'html' for standalone D3 page"),
):
    """Build an interactive knowledge graph from MemPalace memories.

    Nodes = memories, edges = semantic similarity (cosine distance < threshold).
    Communities are detected automatically and shown as colour clusters.

    Returns either:
      - application/json  — graphify-compatible node-link JSON + GRAPH_REPORT section
      - text/html         — self-contained D3 v7 force-directed page (format=html)
    """
    async with async_session() as session:
        # ── 1. Fetch nodes (ordered by hottest memories first) ──────────────
        node_stmt = (
            select(
                Memory.id,
                Memory.content,
                Memory.memory_type,
                Memory.domain,
                Memory.agent_id,
                Memory.owner_id,
                Memory.access_count,
                Memory.created_at,
            )
            .order_by(Memory.access_count.desc(), Memory.created_at.desc())
            .limit(min(limit, _GRAPH_NODE_HARD_MAX))
        )
        if owner_id:
            node_stmt = node_stmt.where(Memory.owner_id == owner_id)
        if agent_id:
            node_stmt = node_stmt.where(Memory.agent_id == agent_id)

        node_rows = (await session.execute(node_stmt)).all()

    if not node_rows:
        empty_graph = {"directed": False, "multigraph": False, "graph": {},
                       "nodes": [], "links": []}
        empty_analysis = {"god_nodes": [], "bridges": [], "communities": [],
                          "stats": {"node_count": 0, "edge_count": 0,
                                    "community_count": 0, "density": 0.0}}
        if fmt == "html":
            return HTMLResponse(graph_lib.render_html(empty_graph, empty_analysis))
        return {"graph": empty_graph, "analysis": empty_analysis}

    node_ids = [str(row.id) for row in node_rows]

    # ── 2. Derive edges via pgvector self-join ─────────────────────────────
    # Use a plain-text query: join the scoped set against itself, keep pairs
    # below the distance threshold, then apply per-node top_k in Python.
    # The IVFFlat index is not invoked here (self-join), but at N<=2000 the
    # sequential pairwise scan is fast enough (~50-200 ms on Hopper).
    async with async_session() as session:
        edge_sql = text("""
            SELECT
                a.id::text           AS src,
                b.id::text           AS tgt,
                ROUND(
                    (1.0 - (a.embedding <=> b.embedding))::numeric, 4
                )                    AS weight,
                (a.embedding <=> b.embedding) AS dist
            FROM mempalace.memories a
            JOIN mempalace.memories b ON b.id > a.id
            WHERE a.id  = ANY(:ids)
              AND b.id  = ANY(:ids)
              AND (a.embedding <=> b.embedding) < :threshold
            ORDER BY a.id, (a.embedding <=> b.embedding)
        """)
        edge_rows = (
            await session.execute(
                edge_sql,
                {"ids": node_ids, "threshold": threshold},
            )
        ).all()

    # ── 3. Apply per-node top_k cap in Python ─────────────────────────────
    neighbour_count: dict[str, int] = {}
    edges: list[dict] = []
    for row in edge_rows:
        src, tgt = row.src, row.tgt
        cnt_s = neighbour_count.get(src, 0)
        cnt_t = neighbour_count.get(tgt, 0)
        if cnt_s >= top_k and cnt_t >= top_k:
            continue
        edges.append({"source": src, "target": tgt, "weight": float(row.weight)})
        neighbour_count[src] = cnt_s + 1
        neighbour_count[tgt] = cnt_t + 1

    # ── 4. Build node dicts ────────────────────────────────────────────────
    nodes = [
        {
            "id": str(row.id),
            # Short label: first ~50 chars (readable in graph)
            "label": (row.content or "")[:50].replace("\n", " ").strip(),
            # Full preview for tooltip / selected panel
            "content_preview": (row.content or "")[:250].replace("\n", " ").strip(),
            "memory_type": row.memory_type or "semantic",
            "domain": row.domain or "general",
            "agent_id": row.agent_id,
            "owner_id": row.owner_id,
            "access_count": row.access_count or 0,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in node_rows
    ]

    # ── 5. Build graph, detect communities, analyse ────────────────────────
    G = graph_lib.build_graph(nodes, edges)
    graph_lib.detect_communities(G)

    # Propagate community attr back onto node dicts (for JSON export)
    for n in nodes:
        n["community"] = G.nodes[n["id"]].get("community", 0)

    analysis = graph_lib.analyze(G)
    graph_json = graph_lib.to_node_link_json(G)

    logger.info(
        "Graph built: %d nodes, %d edges, %d communities (owner=%s, agent=%s, threshold=%.2f)",
        G.number_of_nodes(), G.number_of_edges(),
        analysis["stats"]["community_count"], owner_id, agent_id, threshold,
    )

    # ── 6. Return ──────────────────────────────────────────────────────────
    if fmt == "html":
        html = graph_lib.render_html(graph_json, analysis)
        return HTMLResponse(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    return {"graph": graph_json, "analysis": analysis}


@app.get("/v1/palace/room", response_model=list[MemoryOut])
async def palace_room_memories(
    wing: str,
    hall: str,
    room: str,
    owner_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """Fetch memories for a specific palace room (used by the 3D drawer view)."""
    memory_type = _HALL_MAP_REVERSE.get(hall)

    stmt = select(Memory).where(Memory.domain == room)
    if memory_type:
        stmt = stmt.where(Memory.memory_type == memory_type)
    if owner_id:
        stmt = stmt.where(Memory.owner_id == owner_id)

    # Filter by wing — prefix encodes scope (team/agent/owner/self)
    if wing.startswith("wing_team_"):
        team_id = wing[len("wing_team_"):]
        stmt = stmt.where(Memory.team_id == team_id)
    elif wing.startswith("wing_agent_"):
        agent_id = wing[len("wing_agent_"):]
        stmt = stmt.where(Memory.agent_id == agent_id)
    elif wing.startswith("wing_owner_"):
        wing_owner = wing[len("wing_owner_"):]
        stmt = stmt.where(Memory.owner_id == wing_owner)

    stmt = stmt.order_by(Memory.created_at.desc()).limit(limit).offset(offset)

    async with async_session() as session:
        rows = (await session.execute(stmt)).scalars().all()

    return [_memory_to_out(m) for m in rows]


# ═══════════════════════════════════════════════════════════════════════════
# Memory Edit (PATCH) + Audit Trail
# ═══════════════════════════════════════════════════════════════════════════

@app.patch("/v1/memories/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: UUID,
    req: MemoryUpdate,
    actor_id: str,
):
    """Update a memory's content/fields and log the change.

    actor_id is required and recorded in the audit log. actor_role is fixed
    to "user" until authenticated identity is wired in — clients cannot
    self-promote to admin via query string.
    """
    actor_role = "user"
    async with async_session() as session:
        result = await session.execute(
            select(Memory).where(Memory.id == memory_id)
        )
        mem = result.scalar_one_or_none()
        if not mem:
            raise HTTPException(404, "Memory not found")

        # Track changes for audit
        changed: dict = {}
        prev_content = mem.content

        if req.content is not None and req.content != mem.content:
            changed["content"] = {"old": mem.content, "new": req.content}
            mem.content = req.content
            mem.embedding = await embed_text(req.content)

        if req.memory_type is not None and req.memory_type != mem.memory_type:
            changed["memory_type"] = {"old": mem.memory_type, "new": req.memory_type}
            mem.memory_type = req.memory_type

        if req.domain is not None and req.domain != mem.domain:
            changed["domain"] = {"old": mem.domain, "new": req.domain}
            mem.domain = req.domain

        if req.metadata is not None:
            changed["metadata"] = {"old": mem.metadata_, "new": req.metadata}
            mem.metadata_ = req.metadata

        if not changed:
            return _memory_to_out(mem)

        # Write audit log
        audit = MemoryAuditLog(
            memory_id=memory_id,
            action="edited",
            actor_id=actor_id,
            actor_role=actor_role,
            previous_content=prev_content,
            new_content=mem.content,
            changed_fields=changed,
        )
        session.add(audit)
        await session.commit()
        await session.refresh(mem)

    logger.info("Memory %s edited by %s (%s): %s",
                memory_id, actor_id, actor_role, list(changed.keys()))
    return _memory_to_out(mem)


@app.get("/v1/memories/{memory_id}/audit", response_model=list[AuditLogOut])
async def get_audit_log(memory_id: UUID):
    """Get the audit trail for a specific memory."""
    async with async_session() as session:
        result = await session.execute(
            select(MemoryAuditLog)
            .where(MemoryAuditLog.memory_id == memory_id)
            .order_by(MemoryAuditLog.created_at.desc())
        )
        logs = result.scalars().all()

    return [
        AuditLogOut(
            id=str(log.id),
            memory_id=str(log.memory_id),
            action=log.action,
            actor_id=log.actor_id,
            actor_role=log.actor_role,
            previous_content=log.previous_content,
            new_content=log.new_content,
            changed_fields=log.changed_fields or {},
            created_at=log.created_at.isoformat() if log.created_at else "",
        )
        for log in logs
    ]
