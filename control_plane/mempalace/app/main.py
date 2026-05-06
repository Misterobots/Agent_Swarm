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

from .database import async_session, init_db, Memory, AgentSnapshot, TeamMemory, MemoryAuditLog, ExtractionLog
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
async def store_memory(req: MemoryCreate):
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


@app.get("/v1/palace/audit/extractions")
async def extraction_audit():
    """Per-owner extraction metrics: attempts, memories stored, success rate, last seen."""
    async with async_session() as session:
        # Aggregate extraction_log by owner_id
        agg = (await session.execute(
            select(
                ExtractionLog.owner_id,
                func.count(ExtractionLog.id).label("total_attempts"),
                func.sum(ExtractionLog.memories_stored).label("total_stored"),
                func.max(ExtractionLog.attempted_at).label("last_attempt_at"),
            ).group_by(ExtractionLog.owner_id)
            .order_by(func.max(ExtractionLog.attempted_at).desc())
        )).all()

        # Successful attempts per owner (memories_stored > 0)
        success_attempt_rows = (await session.execute(
            select(
                ExtractionLog.owner_id,
                func.count(ExtractionLog.id).label("success_count"),
                func.max(ExtractionLog.attempted_at).label("last_success_at"),
            )
            .where(ExtractionLog.memories_stored > 0)
            .group_by(ExtractionLog.owner_id)
        )).all()
        success_map = {r.owner_id: (r.success_count, r.last_success_at) for r in success_attempt_rows}

        # Memory count per owner from memories table
        mem_counts = (await session.execute(
            select(Memory.owner_id, func.count(Memory.id).label("memory_count"))
            .group_by(Memory.owner_id)
        )).all()
        mem_count_map = {r.owner_id: r.memory_count for r in mem_counts}

    result = []
    for row in agg:
        attempts = row.total_attempts or 0
        stored = int(row.total_stored or 0)
        success_count, last_success_at = success_map.get(row.owner_id, (0, None))
        success_rate = round(success_count / attempts, 4) if attempts > 0 else 0.0
        result.append({
            "owner_id": row.owner_id,
            "owner_id_short": row.owner_id[:8] + "..." if row.owner_id else "",
            "total_attempts": attempts,
            "total_memories_stored": stored,
            "current_memory_count": mem_count_map.get(row.owner_id, 0),
            "success_rate": success_rate,
            "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
            "last_success_at": last_success_at.isoformat() if last_success_at else None,
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

    stored = []
    if extracted:
        # Generate embeddings in batch
        contents = [m["content"] for m in extracted]
        embeddings = await embed_texts(contents)

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
            await session.commit()
            for mem in stored:
                await session.refresh(mem)

    # Always log the extraction attempt (even if 0 memories stored)
    async with async_session() as session:
        log_entry = ExtractionLog(
            owner_id=owner_id,
            agent_id=req.agent_id,
            memories_stored=len(stored),
            conversation_length=len(req.conversation),
        )
        session.add(log_entry)
        await session.commit()

    logger.info("Extracted %d memories from conversation (owner=%s, agent=%s)",
                len(stored), owner_id, req.agent_id)
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


def _derive_wing(agent_id: str | None, team_id: str | None) -> str:
    if team_id:
        return f"wing_team_{team_id}"
    if agent_id:
        return f"wing_{agent_id}"
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
            Memory.memory_type,
            Memory.domain,
            func.count(Memory.id).label("cnt"),
        ).group_by(Memory.agent_id, Memory.team_id, Memory.memory_type, Memory.domain)

        if owner_id:
            stmt = stmt.where(Memory.owner_id == owner_id)
        if agent_id:
            stmt = stmt.where(Memory.agent_id == agent_id)

        rows = (await session.execute(stmt)).all()

    # Build the hierarchy in-memory
    wings_map: dict[str, dict[str, dict[str, int]]] = {}
    total = 0
    for (aid, tid, mtype, domain, cnt) in rows:
        wing_name = _derive_wing(aid, tid)
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
# MCP / SSE — Model Context Protocol endpoint for VS Code + agents
# Mounted at /mcp; SSE endpoint accessible at /mcp/sse
# ═══════════════════════════════════════════════════════════════════════════

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

_mcp = FastMCP(
    "MemPalace",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["192.168.2.102:*", "localhost:*", "127.0.0.1:*", "hopper:*"],
    ),
)


@_mcp.tool()
async def search_memories_mcp(
    query: str,
    owner_id: str = "",
    agent_id: str = "",
    limit: int = 10,
) -> str:
    """Semantic search over memories in MemPalace. Returns top matches with scores."""
    query_embedding = await embed_text(query)
    distance = Memory.embedding.cosine_distance(query_embedding).label("distance")
    stmt = select(Memory, distance).order_by(distance)
    if owner_id:
        stmt = stmt.where(Memory.owner_id == owner_id)
    if agent_id:
        stmt = stmt.where(Memory.agent_id == agent_id)
    stmt = stmt.limit(limit)
    async with async_session() as session:
        rows = (await session.execute(stmt)).all()
    if not rows:
        return "No memories found."
    lines = []
    for mem, dist in rows:
        score = round(1.0 - (dist or 0.0), 4)
        lines.append(f"[{score}] ({mem.memory_type}/{mem.domain}) {mem.content}")
    return "\n".join(lines)


@_mcp.tool()
async def store_memory_mcp(
    content: str,
    memory_type: str = "semantic",
    domain: str = "general",
    agent_id: str = "",
    owner_id: str = "",
) -> str:
    """Store a new memory in MemPalace with an auto-generated embedding."""
    embedding = await embed_text(content)
    mem = Memory(
        content=content,
        memory_type=memory_type,
        domain=domain,
        agent_id=agent_id or None,
        owner_id=owner_id or None,
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
                memory_type=item.get("memory_type", "semantic"),
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
    # Reverse-derive filters from palace coordinates
    # hall → memory_type
    reverse_hall = {v: k for k, v in _HALL_MAP.items()}
    memory_type = reverse_hall.get(hall)

    stmt = select(Memory).where(Memory.domain == room)
    if memory_type:
        stmt = stmt.where(Memory.memory_type == memory_type)
    if owner_id:
        stmt = stmt.where(Memory.owner_id == owner_id)

    # Filter by wing (agent or team)
    if wing.startswith("wing_team_"):
        team_id = wing[len("wing_team_"):]
        stmt = stmt.where(Memory.team_id == team_id)
    elif wing.startswith("wing_") and wing not in ("wing_agent_swarm", "wing_self"):
        agent_id = wing[len("wing_"):]
        stmt = stmt.where(Memory.agent_id == agent_id)

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
    actor_id: str = "anonymous",
    actor_role: str = "user",
):
    """Update a memory's content/fields and log the change."""
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
