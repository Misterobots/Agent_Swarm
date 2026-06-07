"""LLM-powered entity and relationship extraction from MemPalace memories.

Pipeline
--------
1. Fetch unprocessed memories (entity_extracted=False) for an owner.
2. Batch them (default 5 per LLM call) so the model sees cross-memory context.
3. For each batch: call LLM → parse entities + relations → upsert to DB.
4. Mark memories entity_extracted=True.

Design notes
------------
- Entity dedup uses case-insensitive label lookup (SELECT-first, INSERT-if-not-found).
  The migration enforces the same constraint via a functional unique index on
  (owner_id, lower(label)), so even concurrent runs are safe.
- Relations use the UniqueConstraint uq_entity_rel; duplicate extraction just
  adds the new memory ID to evidence_memory_ids.
- All upserts within one batch share a single DB session/transaction for atomicity.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update

from .database import async_session, Entity, EntityRelation, Memory
from .embeddings import EXTRACT_MODEL, OLLAMA_HOST, _get_client

logger = logging.getLogger("mempalace.entity_extractor")

# ── Valid enum values (LLM output is validated against these) ─────────────────
VALID_ENTITY_TYPES = frozenset({
    "technology", "project", "person", "concept", "decision", "tool",
})
VALID_RELATION_TYPES = frozenset({
    "uses", "depends-on", "created-by", "decided-to", "contradicts",
    "is-part-of", "leads-to", "implements", "replaces", "related-to",
})

ENTITY_EXTRACTION_PROMPT = """\
You are analyzing stored AI agent memories to build a knowledge graph.

Given these memories:
{memories}

Extract:
1. Named entities mentioned across all memories (technologies, projects, people, \
concepts, decisions, tools).
2. Typed relationships between those entities.

Return ONLY a JSON object with this exact structure:
{{
  "entities": [
    {{"label": "exact name or concept", "type": "technology|project|person|concept|decision|tool"}}
  ],
  "relations": [
    {{"source": "label", "relation": "uses|depends-on|created-by|decided-to|contradicts|\
is-part-of|leads-to|implements|replaces|related-to", "target": "label"}}
  ]
}}

Rules:
- Use specific names, not generic descriptions ("Firebase" not "a database")
- Only extract entities explicitly mentioned in the memories
- Only extract relationships clearly stated or strongly implied
- source and target MUST exactly match labels listed in the entities array
- Return [] for either array if nothing meaningful to extract
- No text outside the JSON object

JSON:"""


# ═══════════════════════════════════════════════════════════════════════════
# LLM call
# ═══════════════════════════════════════════════════════════════════════════

async def _call_entity_llm(memories_text: str) -> dict:
    """Call the LLM and return parsed {entities, relations} dict.

    Returns {"entities": [], "relations": []} on any failure.
    """
    client = _get_client()
    prompt = ENTITY_EXTRACTION_PROMPT.format(memories=memories_text)
    empty = {"entities": [], "relations": []}

    try:
        resp = await client.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": EXTRACT_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.05, "num_predict": 2048},
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        parsed = _parse_entity_json(raw)
        if parsed is None:
            logger.warning("Entity LLM: no valid JSON in response (len=%d)", len(raw))
            return empty
        return parsed
    except Exception as exc:
        logger.warning("Entity LLM call failed: %s", exc)
        return empty


def _parse_entity_json(raw: str) -> Optional[dict]:
    """Best-effort extraction of {entities, relations} from LLM output."""
    # Strip markdown fences
    if "```" in raw:
        parts = raw.split("```")
        for part in parts[1::2]:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    pass

    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Extract the first {...} block
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    end = start
    for i, ch in enumerate(raw[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if depth != 0:
        return None
    fragment = raw[start:end]
    # Fix trailing commas
    cleaned = re.sub(r",\s*([}\]])", r"\1", fragment)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# DB helpers
# ═══════════════════════════════════════════════════════════════════════════

async def _get_or_create_entity(
    session,
    label: str,
    entity_type: str,
    owner_id: str,
    label_cache: dict[str, str],
) -> Optional[str]:
    """Return entity UUID string, creating the entity if it doesn't exist.

    label_cache: mutable dict lowercased_label → uuid_string (in-memory dedup
    within a single extraction run avoids repeated round-trips for the same label).
    """
    key = label.lower().strip()
    if not key:
        return None

    if key in label_cache:
        # Increment memory_count for this mention
        existing_id = UUID(label_cache[key])
        await session.execute(
            update(Entity)
            .where(Entity.id == existing_id)
            .values(memory_count=Entity.memory_count + 1,
                    updated_at=datetime.now(timezone.utc))
        )
        return label_cache[key]

    # Check DB (case-insensitive)
    result = await session.execute(
        select(Entity)
        .where(Entity.owner_id == owner_id)
        .where(func.lower(Entity.label) == key)
        .limit(1)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.memory_count += 1
        existing.updated_at = datetime.now(timezone.utc)
        label_cache[key] = str(existing.id)
        return str(existing.id)

    # Normalise entity_type
    etype = entity_type.lower().strip()
    if etype not in VALID_ENTITY_TYPES:
        etype = "concept"

    entity = Entity(
        label=label.strip(),
        entity_type=etype,
        owner_id=owner_id,
        memory_count=1,
    )
    session.add(entity)
    await session.flush()  # materialize the UUID
    label_cache[key] = str(entity.id)
    logger.debug("Created entity: %r [%s] owner=%s", label, etype, owner_id)
    return str(entity.id)


async def _upsert_relation(
    session,
    source_id: str,
    target_id: str,
    relation_type: str,
    owner_id: str,
    evidence_memory_id: Optional[str],
) -> bool:
    """Insert relation; on conflict append evidence and return False (existing)."""
    rtype = relation_type.lower().strip()
    if rtype not in VALID_RELATION_TYPES:
        rtype = "related-to"

    src_uuid = UUID(source_id)
    tgt_uuid = UUID(target_id)

    result = await session.execute(
        select(EntityRelation)
        .where(EntityRelation.source_id == src_uuid)
        .where(EntityRelation.target_id == tgt_uuid)
        .where(EntityRelation.relation_type == rtype)
        .limit(1)
    )
    existing = result.scalar_one_or_none()

    if existing:
        if evidence_memory_id:
            ev = list(existing.evidence_memory_ids or [])
            if evidence_memory_id not in ev:
                ev.append(evidence_memory_id)
                existing.evidence_memory_ids = ev
        return False

    evidence = [evidence_memory_id] if evidence_memory_id else []
    rel = EntityRelation(
        source_id=src_uuid,
        target_id=tgt_uuid,
        relation_type=rtype,
        confidence=1.0,
        evidence_memory_ids=evidence,
        owner_id=owner_id,
    )
    session.add(rel)
    logger.debug("Created relation: %s -[%s]-> %s", source_id[:8], rtype, target_id[:8])
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

async def run_entity_extraction(
    owner_id: str,
    batch_size: int = 5,
    max_memories: int = 200,
) -> dict:
    """Extract entities and relationships from unprocessed memories for owner.

    Idempotent: memories marked entity_extracted=True are skipped.
    Returns extraction stats dict.
    """
    stats = {
        "memories_processed": 0,
        "entities_created": 0,
        "entities_updated": 0,
        "relations_created": 0,
        "batches_failed": 0,
    }

    # ── Fetch unprocessed memories ─────────────────────────────────────────
    async with async_session() as session:
        result = await session.execute(
            select(Memory.id, Memory.content, Memory.memory_type, Memory.domain)
            .where(Memory.owner_id == owner_id)
            .where(Memory.entity_extracted == False)  # noqa: E712
            .order_by(Memory.created_at.desc())
            .limit(max_memories)
        )
        memory_rows = result.all()

    if not memory_rows:
        logger.info("Entity extraction: no unprocessed memories for owner=%s", owner_id)
        return stats

    # ── Load existing entity label→id map (for cross-batch dedup) ─────────
    label_cache: dict[str, str] = {}
    async with async_session() as session:
        result = await session.execute(
            select(Entity.id, Entity.label).where(Entity.owner_id == owner_id)
        )
        for eid, elabel in result.all():
            label_cache[elabel.lower().strip()] = str(eid)

    logger.info(
        "Entity extraction starting: %d memories, %d existing entities (owner=%s)",
        len(memory_rows), len(label_cache), owner_id,
    )

    # ── Process in batches ─────────────────────────────────────────────────
    for batch_start in range(0, len(memory_rows), batch_size):
        batch = memory_rows[batch_start : batch_start + batch_size]
        memory_ids = [str(row.id) for row in batch]

        # Format memories for LLM
        lines = []
        for i, row in enumerate(batch, 1):
            lines.append(f"[{i}] ({row.memory_type}/{row.domain or 'general'}) {row.content}")
        memories_text = "\n".join(lines)

        try:
            extracted = await _call_entity_llm(memories_text)
            entities_raw = extracted.get("entities") or []
            relations_raw = extracted.get("relations") or []

            entities_before = len(label_cache)

            async with async_session() as session:
                # Upsert entities first (relations reference them)
                for ent in entities_raw:
                    label = (ent.get("label") or "").strip()
                    etype = (ent.get("type") or "concept").strip()
                    if not label:
                        continue
                    prev_size = len(label_cache)
                    eid = await _get_or_create_entity(
                        session, label, etype, owner_id, label_cache
                    )
                    if eid and len(label_cache) > prev_size:
                        stats["entities_created"] += 1
                    elif eid:
                        stats["entities_updated"] += 1

                # Upsert relations (source + target must be in label_cache)
                for rel in relations_raw:
                    src_label = (rel.get("source") or "").lower().strip()
                    tgt_label = (rel.get("target") or "").lower().strip()
                    rtype = (rel.get("relation") or "related-to").strip()

                    src_id = label_cache.get(src_label)
                    tgt_id = label_cache.get(tgt_label)

                    if not src_id or not tgt_id or src_id == tgt_id:
                        logger.debug(
                            "Skipping relation %r -[%s]-> %r: entity not found",
                            src_label, rtype, tgt_label,
                        )
                        continue

                    # Use first memory in the batch as evidence anchor
                    created = await _upsert_relation(
                        session, src_id, tgt_id, rtype, owner_id,
                        evidence_memory_id=memory_ids[0] if memory_ids else None,
                    )
                    if created:
                        stats["relations_created"] += 1

                # Mark memories processed
                await session.execute(
                    update(Memory)
                    .where(Memory.id.in_([UUID(mid) for mid in memory_ids]))
                    .values(entity_extracted=True)
                )
                await session.commit()

            stats["memories_processed"] += len(batch)
            logger.info(
                "Batch %d-%d done: +%d entities, cache=%d",
                batch_start + 1, batch_start + len(batch),
                len(label_cache) - entities_before, len(label_cache),
            )

        except Exception as exc:
            logger.error(
                "Entity extraction batch %d-%d failed: %s",
                batch_start + 1, batch_start + len(batch), exc,
                exc_info=True,
            )
            stats["batches_failed"] += 1

    logger.info(
        "Entity extraction complete (owner=%s): %s",
        owner_id, stats,
    )
    return stats
