"""MemPalace client — official ``mempalace`` library integration.

Replaces the former HTTP client with the official MemPalace Python package
(``pip install mempalace``).  All data stays local — ChromaDB embedded backend,
palace architecture (Wings → Halls → Rooms → Drawers), SQLite knowledge graph.

Usage (unchanged from the old client):
    from mempalace_client import mempalace

    mempalace.store("User prefers dark cyberpunk aesthetics", domain="visual")
    results = mempalace.search("cyberpunk art style preferences")
    extracted = mempalace.extract(conversation_text, owner_id="user_123")
    mempalace.save_snapshot("architect", {"learned_rules": [...]})
    snapshot = mempalace.get_snapshot("architect")
    mempalace.team_store("coord-abc123", "research_summary", "The analysis shows...")
    entries = mempalace.team_get("coord-abc123")
"""

import json
import logging
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("agents.mempalace_client")

# Palace root — persistent volume in the agent runtime container
PALACE_PATH = os.getenv(
    "MEMPALACE_PALACE_PATH",
    os.path.expanduser("~/.mempalace/palace"),
)

# Map old memory_type values to palace halls
_HALL_MAP = {
    "semantic": "hall_facts",
    "episodic": "hall_events",
    "procedural": "hall_advice",
    "preference": "hall_preferences",
    "discovery": "hall_discoveries",
}


def _wing_name(agent_id: Optional[str] = None, team_id: Optional[str] = None) -> str:
    """Derive a palace wing name from an agent or team identifier."""
    if team_id:
        return f"wing_team_{team_id}"
    if agent_id:
        return f"wing_{agent_id}"
    return "wing_agent_swarm"


class MemPalaceClient:
    """Client wrapping the official *mempalace* library (local, no server)."""

    def __init__(self, palace_path: str = PALACE_PATH):
        self._palace_path = palace_path
        self._backend = None       # ChromaBackend (lazy)
        self._kg = None            # KnowledgeGraph (lazy)
        self._search_fn = None     # search_memories function ref
        self._initialized = False

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------
    def _ensure_init(self) -> bool:
        if self._initialized:
            return True
        try:
            from mempalace.searcher import search_memories
            from mempalace.knowledge_graph import KnowledgeGraph

            # Ensure palace directory exists
            palace_dir = Path(self._palace_path)
            if not palace_dir.exists():
                logger.info("Initialising palace at %s", self._palace_path)
                palace_dir.mkdir(parents=True, exist_ok=True)
                try:
                    subprocess.run(
                        ["mempalace", "init", str(palace_dir)],
                        capture_output=True,
                        timeout=60,
                        check=False,
                    )
                except FileNotFoundError:
                    logger.debug("mempalace CLI not on PATH — library-only mode")

            # Try to import the ChromaDB backend abstraction
            try:
                from mempalace.backends.chroma import ChromaBackend
                self._backend = ChromaBackend(palace_path=self._palace_path)
            except ImportError:
                # Older versions may not have backends.chroma — fall back to
                # direct chromadb usage through the searcher module.
                self._backend = None
                logger.debug("ChromaBackend not found — using searcher-only mode")

            self._kg = KnowledgeGraph(palace_path=self._palace_path)
            self._search_fn = search_memories
            self._initialized = True
            return True
        except ImportError:
            logger.warning(
                "Official mempalace library not installed.  "
                "Run: pip install mempalace"
            )
            return False
        except Exception as exc:
            logger.warning("MemPalace initialisation failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def healthy(self) -> bool:
        """Return True if the palace is usable."""
        try:
            return self._ensure_init()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Memories — store / search / delete / stats
    # ------------------------------------------------------------------
    def store(
        self,
        content: str,
        memory_type: str = "semantic",
        domain: str = "general",
        agent_id: Optional[str] = None,
        team_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Store a memory as a drawer in the palace."""
        if not self._ensure_init():
            raise RuntimeError("MemPalace not available")

        wing = _wing_name(agent_id, team_id)
        hall = _HALL_MAP.get(memory_type, "hall_facts")
        room = domain or "general"
        doc_id = str(uuid.uuid4())

        doc_metadata = {
            "wing": wing,
            "hall": hall,
            "room": room,
            "memory_type": memory_type,
            "domain": domain,
            "owner_id": owner_id or "",
            "agent_id": agent_id or "",
            "team_id": team_id or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        }

        if self._backend is not None:
            self._backend.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[doc_metadata],
            )
        else:
            # Fallback: use chromadb directly via the palace collection
            try:
                import chromadb
                client = chromadb.PersistentClient(path=self._palace_path)
                col = client.get_or_create_collection("mempalace_drawers")
                col.add(ids=[doc_id], documents=[content], metadatas=[doc_metadata])
            except Exception as exc:
                logger.error("Direct ChromaDB store failed: %s", exc)
                raise

        logger.debug("Stored drawer %s in %s/%s/%s", doc_id, wing, hall, room)
        return {"id": doc_id, "wing": wing, "hall": hall, "room": room}

    def search(
        self,
        query: str,
        owner_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        team_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Semantic similarity search over palace drawers."""
        if not self._ensure_init():
            return []

        # Build ChromaDB where-filter from optional scoping params
        where_clauses: list[dict] = []
        if agent_id:
            where_clauses.append({"wing": _wing_name(agent_id)})
        if team_id:
            where_clauses.append({"wing": _wing_name(team_id=team_id)})
        if memory_type and memory_type in _HALL_MAP:
            where_clauses.append({"hall": _HALL_MAP[memory_type]})
        if domain:
            where_clauses.append({"room": domain})
        if owner_id:
            where_clauses.append({"owner_id": owner_id})

        where: Optional[dict] = None
        if len(where_clauses) == 1:
            where = where_clauses[0]
        elif len(where_clauses) > 1:
            where = {"$and": where_clauses}

        try:
            # Prefer searcher module (handles embedding + query internally)
            if self._search_fn is not None:
                raw = self._search_fn(
                    query,
                    palace_path=self._palace_path,
                    n_results=limit,
                    where=where,
                )
                # Normalise to list[dict] matching old API shape
                if isinstance(raw, list):
                    return [
                        self._normalise_result(r) for r in raw[:limit]
                    ]
                return []

            # Fallback: direct chromadb query
            import chromadb
            client = chromadb.PersistentClient(path=self._palace_path)
            col = client.get_or_create_collection("mempalace_drawers")
            results = col.query(
                query_texts=[query],
                n_results=limit,
                where=where,
            )
            return self._chroma_to_list(results)
        except Exception as exc:
            logger.warning("MemPalace search failed: %s", exc)
            return []

    def delete(self, memory_id: str) -> dict:
        """Delete a drawer by ID."""
        if not self._ensure_init():
            raise RuntimeError("MemPalace not available")
        try:
            if self._backend is not None:
                self._backend.delete(ids=[memory_id])
            else:
                import chromadb
                client = chromadb.PersistentClient(path=self._palace_path)
                col = client.get_or_create_collection("mempalace_drawers")
                col.delete(ids=[memory_id])
            return {"deleted": memory_id}
        except Exception as exc:
            logger.error("MemPalace delete failed: %s", exc)
            raise

    def stats(self) -> dict:
        """Return palace overview statistics."""
        if not self._ensure_init():
            return {"status": "unavailable"}
        try:
            import chromadb
            client = chromadb.PersistentClient(path=self._palace_path)
            col = client.get_or_create_collection("mempalace_drawers")
            count = col.count()
            return {
                "status": "ok",
                "palace_path": self._palace_path,
                "total_drawers": count,
                "backend": "chromadb",
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Memory Extraction — mine conversations into palace
    # ------------------------------------------------------------------
    def extract(
        self,
        conversation: str,
        owner_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ) -> list[dict]:
        """Extract and store memories from conversation text.

        Uses ``mempalace mine --mode convos`` under the hood.  Falls back to
        storing the raw conversation as a single drawer if the CLI is absent.
        """
        if not self._ensure_init():
            return []
        try:
            # Try programmatic convo miner first
            try:
                from mempalace.convo_miner import mine_conversation_text
                results = mine_conversation_text(
                    conversation,
                    palace_path=self._palace_path,
                    wing=_wing_name(agent_id, team_id),
                )
                if isinstance(results, list):
                    return [{"content": r} if isinstance(r, str) else r for r in results]
            except ImportError:
                pass

            # Fallback: write to temp file and call CLI
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False
                ) as tmp:
                    tmp.write(conversation)
                    tmp_path = tmp.name
                wing = _wing_name(agent_id, team_id)
                result = subprocess.run(
                    [
                        "mempalace", "mine", tmp_path,
                        "--mode", "convos",
                        "--wing", wing,
                        "--palace", self._palace_path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
                os.unlink(tmp_path)
                if result.returncode == 0:
                    return [{"status": "mined", "output": result.stdout.strip()}]
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

            # Last resort: store raw conversation as a single drawer
            stored = self.store(
                content=conversation,
                memory_type="episodic",
                domain="conversation",
                agent_id=agent_id,
                team_id=team_id,
                owner_id=owner_id,
                metadata={"source": "extract_fallback"},
            )
            return [stored]
        except Exception as exc:
            logger.warning("Memory extraction failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Agent Snapshots — mapped to agent diaries
    # ------------------------------------------------------------------
    def save_snapshot(
        self,
        agent_id: str,
        snapshot_data: dict,
        owner_id: Optional[str] = None,
    ) -> dict:
        """Save agent state via the palace diary system."""
        if not self._ensure_init():
            raise RuntimeError("MemPalace not available")
        entry = json.dumps(snapshot_data, default=str)
        try:
            from mempalace.mcp_server import diary_write
            diary_write(agent_id, entry)
            return {"agent_id": agent_id, "status": "saved"}
        except (ImportError, AttributeError):
            pass
        # Fallback: store as a drawer in a snapshot room
        return self.store(
            content=entry,
            memory_type="episodic",
            domain="agent_snapshot",
            agent_id=agent_id,
            owner_id=owner_id,
            metadata={"snapshot": True},
        )

    def get_snapshot(
        self,
        agent_id: str,
        owner_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Retrieve the latest agent snapshot from the diary."""
        if not self._ensure_init():
            return None
        try:
            from mempalace.mcp_server import diary_read
            entries = diary_read(agent_id, last_n=1)
            if entries:
                entry = entries[0] if isinstance(entries, list) else entries
                raw = entry.get("content", entry) if isinstance(entry, dict) else entry
                return json.loads(raw) if isinstance(raw, str) else raw
        except (ImportError, AttributeError, json.JSONDecodeError):
            pass
        # Fallback: search snapshot drawers
        results = self.search(
            query=f"agent snapshot {agent_id}",
            agent_id=agent_id,
            domain="agent_snapshot",
            limit=1,
        )
        if results:
            content = results[0].get("content", "")
            try:
                return json.loads(content)
            except (json.JSONDecodeError, TypeError):
                return results[0]
        return None

    # ------------------------------------------------------------------
    # Team Memory — mapped to knowledge graph + wing-scoped drawers
    # ------------------------------------------------------------------
    def team_store(
        self,
        team_id: str,
        key: str,
        value: str,
        author_agent: Optional[str] = None,
    ) -> dict:
        """Store a key→value pair in team memory.

        Uses the knowledge graph for structured team facts and a team wing
        drawer for the full content.
        """
        if not self._ensure_init():
            raise RuntimeError("MemPalace not available")

        # Knowledge graph triple: team → has_entry → key
        try:
            if self._kg is not None:
                self._kg.add_triple(
                    team_id,
                    f"has_{key}",
                    value[:500],  # KG values are concise
                    valid_from=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                )
        except Exception as exc:
            logger.debug("KG team store failed (non-fatal): %s", exc)

        # Full content in a team-wing drawer
        return self.store(
            content=value,
            memory_type="semantic",
            domain=f"team_{key}",
            team_id=team_id,
            metadata={"key": key, "author_agent": author_agent or ""},
        )

    def team_get(self, team_id: str) -> list[dict]:
        """Get all entries for a team from the knowledge graph + drawers."""
        if not self._ensure_init():
            return []
        results: list[dict] = []

        # Pull from knowledge graph
        try:
            if self._kg is not None:
                kg_results = self._kg.query_entity(team_id)
                if isinstance(kg_results, list):
                    for triple in kg_results:
                        results.append({
                            "key": triple.get("predicate", ""),
                            "value": triple.get("object", ""),
                            "source": "knowledge_graph",
                        })
        except Exception as exc:
            logger.debug("KG team_get failed: %s", exc)

        # Supplement with drawer search
        wing = _wing_name(team_id=team_id)
        try:
            drawer_results = self.search(
                query=team_id,
                team_id=team_id,
                limit=50,
            )
            for dr in drawer_results:
                results.append({
                    "key": dr.get("domain", dr.get("room", "")),
                    "value": dr.get("content", ""),
                    "source": "drawer",
                })
        except Exception:
            pass
        return results

    def team_search(
        self,
        team_id: str,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """Semantic search within a team's wing."""
        return self.search(
            query=query,
            team_id=team_id,
            limit=limit,
        )

    def team_clear(self, team_id: str) -> dict:
        """Invalidate all team entries in the knowledge graph."""
        if not self._ensure_init():
            return {"status": "unavailable"}
        try:
            if self._kg is not None:
                triples = self._kg.query_entity(team_id)
                now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if isinstance(triples, list):
                    for t in triples:
                        try:
                            self._kg.invalidate(
                                team_id,
                                t.get("predicate", ""),
                                t.get("object", ""),
                                ended=now,
                            )
                        except Exception:
                            pass
            return {"team_id": team_id, "status": "cleared"}
        except Exception as exc:
            logger.warning("Team clear failed: %s", exc)
            return {"team_id": team_id, "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_result(raw) -> dict:
        """Normalise a search result to the expected dict shape."""
        if isinstance(raw, dict):
            return {
                "content": raw.get("content", raw.get("document", "")),
                "score": raw.get("score", raw.get("distance", 0)),
                "memory_type": raw.get("memory_type", raw.get("hall", "")),
                "domain": raw.get("domain", raw.get("room", "")),
                "id": raw.get("id", ""),
                **{k: v for k, v in raw.items()
                   if k not in ("content", "document", "score", "distance",
                                "memory_type", "hall", "domain", "room", "id")},
            }
        if isinstance(raw, str):
            return {"content": raw, "score": 0}
        return {"content": str(raw), "score": 0}

    @staticmethod
    def _chroma_to_list(results: dict) -> list[dict]:
        """Convert raw chromadb query results to list[dict]."""
        out: list[dict] = []
        ids = (results.get("ids") or [[]])[0]
        docs = (results.get("documents") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        for i, doc_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            out.append({
                "id": doc_id,
                "content": docs[i] if i < len(docs) else "",
                "score": 1.0 - (distances[i] if i < len(distances) else 1.0),
                "memory_type": meta.get("memory_type", ""),
                "domain": meta.get("domain", meta.get("room", "")),
                **meta,
            })
        return out


# ---------------------------------------------------------------------------
# Singleton — graceful fallback if mempalace is not installed
# ---------------------------------------------------------------------------
mempalace = MemPalaceClient()
