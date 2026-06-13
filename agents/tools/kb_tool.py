"""kb_tool.py — host-side knowledge-base search for swarm coder/architect workers.

Queries PgVector (Hopper:5432, table architect_knowledge) directly from
agent_runtime — no sandbox network egress needed.  Reuses the same KB config
as leibniz_agent.get_architect_agent().
"""

import logging
from config import AGNO_DB_URL

logger = logging.getLogger("kb_tool")


def kb_search(query: str, limit: int = 5) -> str:
    """Search the Memex architect knowledge base for relevant context.

    Returns up to `limit` matched passages (truncated at 800 chars each).
    Falls back gracefully if the DB is unreachable or phidata is not installed.
    """
    if not AGNO_DB_URL:
        return "Knowledge base unavailable: AGNO_DB_URL not configured."
    try:
        from phi.knowledge.combined import CombinedKnowledgeBase
        from phi.vectordb.pgvector import PgVector

        kb = CombinedKnowledgeBase(
            sources=[],
            vector_db=PgVector(table_name="architect_knowledge", db_url=AGNO_DB_URL),
        )
        results = kb.search(query, num_documents=min(max(1, limit), 8))
        if not results:
            return "No relevant knowledge base entries found."
        parts = []
        for i, doc in enumerate(results, 1):
            content = getattr(doc, "content", None) or str(doc)
            parts.append(f"[{i}]\n{content[:800]}")
        return "\n\n".join(parts)
    except Exception as e:
        logger.warning(f"[kb_tool] kb_search failed: {e}")
        return f"kb_search error: {e}"
