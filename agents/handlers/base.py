"""
handlers/base.py — Shared utilities for all intent handlers.

Provides:
  - Stream event emitters (_emit_*)
  - _parse_think_tags
  - _needs_web_grounding / _WEB_GROUNDING_KEYWORDS
  - _retrieve_doc_context
  - _score_trace  (Langfuse helper — accepts langfuse instance + flag via ctx)
  - _langfuse_span (context manager — same)

All handlers receive a ``ctx`` dict built in chat_swarm().  Relevant keys:
  session_id, owner_id, uid, turn_id, history, history_context,
  constraint_context, extracted_context, model, ace_token,
  template_metadata, lf_trace, langfuse, use_langfuse, fast_mode,
  research_mode, ultraplan_mode, dev_mode, conv_storage, routing_decision,
  solving_max_iter, solving_max_time, solving_solver_n_drafts,
  solving_solver_max_time, solving_verifier_n_runs, solving_verifier_max_time,
  solving_corrector_n_passes, solving_corrector_max_time.
"""

import logging
import re
from contextlib import contextmanager

logger = logging.getLogger("Router")


# ---------------------------------------------------------------------------
# Stream event helpers (pure functions)
# ---------------------------------------------------------------------------

def _emit_stream_mode(mode: str) -> dict:
    return {"type": "stream_mode", "streamMode": mode}


def _emit_turn_metadata(turn_id: str, agent_name: str, stream_modes: list = None) -> dict:
    return {
        "type": "turn_metadata",
        "turnId": turn_id,
        "turnMetadata": {
            "turnId": turn_id,
            "agentName": agent_name,
            "streamModes": stream_modes or [],
            "toolsInvoked": [],
            "continuable": True,
        },
    }


def _emit_turn_boundary(turn_id: str, final_status: str = "completed") -> dict:
    return {
        "type": "turn_boundary",
        "content": f"[Turn {turn_id} {final_status}]",
        "turnId": turn_id,
    }


def _emit_tool_start(tool_call_id: str, tool_name: str, tool_input: dict = None) -> dict:
    return {
        "type": "tool_start",
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "tool_input": tool_input or {},
        "tool_state": "queued",
    }


def _emit_tool_progress(tool_call_id: str, tool_name: str, progress: float = 0, status_msg: str = "") -> dict:
    return {
        "type": "tool_progress",
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "tool_state": "executing",
        "tool_progress": min(progress, 100),
        "content": status_msg,
    }


def _emit_tool_result(tool_call_id: str, tool_name: str, output: str, success: bool = True, artifacts: list = None) -> dict:
    return {
        "type": "tool_result",
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "tool_output": output,
        "tool_state": "completed" if success else "error",
        "content": output,
        "artifacts": artifacts or [],
    }


def _emit_continuation_hint(hint_type: str = "auto_continue", reason: str = "") -> dict:
    return {
        "type": "continuation",
        "continuationHint": hint_type,
        "content": reason,
    }


def _emit_suggested_followups(followups: list) -> dict:
    """Emit 2 LLM-generated contextual follow-up suggestions for the UI chip strip.

    Each followup is ``{"label": str, "prompt": str}`` — label is a 3-5 word
    action phrase; prompt is the full message to send when the chip is clicked.
    """
    return {
        "type": "suggested_followups",
        "followups": followups[:2],  # always cap at 2 contextual chips
    }


# ---------------------------------------------------------------------------
# Think-tag parser
# ---------------------------------------------------------------------------

def _parse_think_tags(text: str):
    """Yield (type, content) tuples — type is 'thought' or 'message'."""
    parts = re.split(r'(<think>|</think>)', text)
    in_think = False
    for part in parts:
        if part == '<think>':
            in_think = True
        elif part == '</think>':
            in_think = False
        elif part:
            yield ("thought" if in_think else "message", part)


# ---------------------------------------------------------------------------
# Grounding helpers
# ---------------------------------------------------------------------------

_WEB_GROUNDING_KEYWORDS = frozenset([
    "latest", "current", "today", "now", "news", "recent", "recently",
    "yesterday", "this week", "this month", "this year", "2024", "2025",
    "who won", "what is the price", "stock price", "weather", "trending",
    "breaking", "just announced", "released", "update", "version",
])


def _needs_web_grounding(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in _WEB_GROUNDING_KEYWORDS)


def _retrieve_doc_context(query: str, owner_id, limit: int = 5) -> list:
    """Query PgVector for relevant knowledge-base chunks. Returns [] on error."""
    try:
        import os as _os
        from agno.vectordb.pgvector import PgVector, SearchType
        from agno.embedder.ollama import OllamaEmbedder

        db_url = _os.getenv("AGNO_DB_URL", "postgresql+psycopg://ai:ai@localhost:5532/ai")
        embedder = OllamaEmbedder(id="nomic-embed-text", dimensions=768)
        vdb = PgVector(
            table_name="architect_knowledge",
            db_url=db_url,
            search_type=SearchType.hybrid,
            embedder=embedder,
        )
        rows = vdb.search(query=query, limit=limit)
        results = []
        for row in rows or []:
            content = getattr(row, "content", None) or str(row)
            meta = getattr(row, "meta_data", {}) or {}
            source = meta.get("source", meta.get("name", "unknown"))
            results.append({"source": source, "content": content})
        return results
    except Exception as exc:
        logger.debug("[Router] Doc grounding retrieval failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Langfuse observability helpers
# ---------------------------------------------------------------------------

def _score_trace(lf_trace, langfuse_inst, score: float, output: str = None, use_langfuse: bool = True):
    """Score the current Langfuse trace. No-op when Langfuse is unavailable."""
    if not langfuse_inst or not use_langfuse:
        return
    try:
        if output:
            langfuse_inst.set_current_trace_io(output={"response": output[:4000]})
        langfuse_inst.score_current_trace(name="training_candidate", value=score)
    except Exception as e:
        logger.debug("[Router] Trace scoring failed: %s", e)


@contextmanager
def _langfuse_span(name: str, agent_name: str, model_id: str, input_text: str,
                   *, langfuse=None, use_langfuse: bool = False):
    """Create a Langfuse generation span. Yields a dict for the caller to fill 'output'."""
    result = {"output": ""}
    if use_langfuse and langfuse:
        try:
            ctx = langfuse.start_as_current_observation(
                name=name,
                as_type="generation",
                input={"prompt": input_text[:4000]},
                metadata={"agent": agent_name, "model": model_id},
            )
            ctx.__enter__()
            try:
                yield result
            finally:
                try:
                    langfuse.update_current_observation(
                        output={"response": result["output"][:4000]},
                        metadata={"response_len": len(result["output"])},
                    )
                except Exception:
                    pass
                ctx.__exit__(None, None, None)
        except Exception as e:
            logger.debug("[Router] Span creation failed for %s: %s", name, e)
            yield result
    else:
        yield result
