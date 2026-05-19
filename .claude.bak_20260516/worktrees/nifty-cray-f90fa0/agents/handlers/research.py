"""handlers/research.py — RESEARCH, DOCUMENTATION, and DOC_STANDARDS handlers."""

import logging
import os

from phi.agent import Agent
from phi.model.ollama import Ollama

from metrics import AGENT_STATE, WORKFLOW_STEPS
from utils.gpu_queue import request_lock, get_best_host_for_model
from handlers.base import _emit_stream_mode, _emit_turn_metadata, _score_trace, _langfuse_span

logger = logging.getLogger("Router")


def handle_research(user_input: str, ctx: dict):
    """Generator — Hive Librarian for deep research and knowledge queries."""
    turn_id = ctx["turn_id"]
    history_context = ctx["history_context"]
    constraint_context = ctx["constraint_context"]
    extracted_context = ctx["extracted_context"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]

    from church import _resolve_model_for_intent
    from agents.config import LIBRARIAN_MODEL, get_ollama_options

    yield _emit_turn_metadata(turn_id, "Librarian", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    yield {"type": "status", "content": "📚 Librarian Agent: Accessing Archives..."}
    AGENT_STATE.labels(agent_name="Librarian").set(2)

    resolved_model = _resolve_model_for_intent("RESEARCH", LIBRARIAN_MODEL)
    resolved_host = get_best_host_for_model(resolved_model)

    researcher = Agent(
        name="Librarian",
        model=Ollama(id=resolved_model, host=resolved_host, options=get_ollama_options(resolved_model)),
        instructions=(
            "You are the Hive Librarian and Scholar.\n"
            "Your goal is to provide deep historical context, literary analysis, and general knowledge.\n"
            "You are the guardian of facts and culture. Focus on: History, Literature, Philosophy, Science, and Factual Explanations.\n"
            "If the user asks for code, decline and suggest they ask the Architect.\n"
            "If the user asks for images, decline and suggest they ask the Art Director."
        ),
        show_tool_calls=False,
    )

    final_input = user_input
    if history_context:
        final_input = f"{history_context}\n\n{final_input}"
        yield {"type": "log", "content": "[Librarian] Reviewed prior turns for continuity."}
    if constraint_context:
        final_input = f"{constraint_context}\n\n{final_input}"
        yield {"type": "log", "content": "[Librarian] Injected active user constraints."}
    if extracted_context:
        yield {"type": "log", "content": "[Librarian] Reading Attached RAG Context..."}
        final_input = f"{final_input}\n\n[Attached Document Context]:\n{extracted_context}"

    full_content = ""
    try:
        with _langfuse_span("research_generation", "Librarian", resolved_model, final_input,
                            langfuse=langfuse, use_langfuse=use_langfuse) as span_result:
            with request_lock(context="text"):
                response_stream = researcher.run(final_input, stream=True)
                yield {"type": "status", "content": "📚 Librarian Agent: Drafting response..."}
                for chunk in response_stream:
                    if chunk.content:
                        yield _emit_stream_mode("responding")
                        full_content += chunk.content
                        yield {"type": "message", "content": chunk.content}
            span_result["output"] = full_content
        yield {"type": "log", "content": f"[Research] Completed query: {user_input}"}
        _score_trace(lf_trace, langfuse, 0.85, output=full_content, use_langfuse=use_langfuse)
    except Exception as e:
        _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)
        yield {"type": "error", "content": f"Research Failed: {e}"}

    AGENT_STATE.labels(agent_name="Librarian").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="Librarian").inc()


def handle_documentation(user_input: str, ctx: dict):
    """Generator — Technical Writer for docs rewriting and formatting."""
    turn_id = ctx["turn_id"]
    history_context = ctx["history_context"]
    constraint_context = ctx["constraint_context"]
    extracted_context = ctx["extracted_context"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]

    from church import _resolve_model_for_intent
    from config import ARCHITECT_MODEL, get_ollama_options as _get_ollama_options

    yield _emit_turn_metadata(turn_id, "Technical Writer", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    yield {"type": "status", "content": "📝 Technical Writer: Reviewing document structure..."}
    AGENT_STATE.labels(agent_name="TechnicalWriter").set(2)

    TECH_MODEL = _resolve_model_for_intent(
        "DOCUMENTATION",
        os.getenv("ARCHITECT_MODEL", os.getenv("PRIMARY_MODEL", "qwen3:14b")),
    )
    OLLAMA_HOST = get_best_host_for_model(TECH_MODEL)

    tech_writer = Agent(
        name="Technical Writer",
        model=Ollama(id=TECH_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 300.0}, options=_get_ollama_options(TECH_MODEL)),
        instructions=(
            "You are a Staff-Level Technical Writer.\n"
            "Your goal is to rewrite, format, and organize documentation into professional, polished markdown.\n"
            "If provided with large context files, synthesize the information accurately.\n"
            "Focus on clarity, tone, accurate citations, and structured formatting (headings, lists, bolding)."
        ),
        show_tool_calls=False,
    )

    final_input = user_input
    if history_context:
        final_input = f"{history_context}\n\n{final_input}"
        yield {"type": "log", "content": "[TechnicalWriter] Reviewed prior turns for continuity."}
    if constraint_context:
        final_input = f"{constraint_context}\n\n{final_input}"
        yield {"type": "log", "content": "[TechnicalWriter] Injected active user constraints."}

    try:
        from memory_system import memory
        doc_rules = memory.get_relevant_rules(user_input, "general_rules")
        if doc_rules:
            rule_block = "\n".join([f"- {r}" for r in doc_rules])
            final_input = f"{final_input}\n\n[🧠 MEMORY] Apply these rules:\n{rule_block}"
            yield {"type": "log", "content": f"[Memory] Injected {len(doc_rules)} stylistic rules."}
    except Exception:
        pass

    if extracted_context:
        yield {"type": "log", "content": f"[TechnicalWriter] Reading Attached RAG Context ({len(extracted_context)} chars)..."}
        final_input = f"{final_input}\n\n[Attached Document Context]:\n{extracted_context}"

    full_content = ""
    try:
        with _langfuse_span("documentation_generation", "TechnicalWriter", TECH_MODEL, final_input,
                            langfuse=langfuse, use_langfuse=use_langfuse) as span_result:
            with request_lock(context="text"):
                response_stream = tech_writer.run(final_input, stream=True)
                yield {"type": "status", "content": "📝 Technical Writer: Generating document..."}
                for chunk in response_stream:
                    if chunk.content:
                        yield _emit_stream_mode("responding")
                        full_content += chunk.content
                        yield {"type": "message", "content": chunk.content}
                yield {"type": "log", "content": "[TechnicalWriter] Document Transformation Complete."}
            span_result["output"] = full_content
        _score_trace(lf_trace, langfuse, 0.85, output=full_content, use_langfuse=use_langfuse)
    except Exception as e:
        _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)
        yield {"type": "error", "content": f"Technical Writing Failed: {e}"}

    AGENT_STATE.labels(agent_name="TechnicalWriter").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="TechnicalWriter").inc()


def handle_doc_standards(user_input: str, ctx: dict):
    """Generator — Doc Standards Agent (/standardize-doc, admin-only)."""
    import shlex
    session_id = ctx["session_id"]
    owner_id = ctx["owner_id"]
    turn_id = ctx["turn_id"]
    model = ctx.get("model")

    from church import _is_admin_session, _audit_security_event
    from config import ARCHITECT_MODEL

    yield _emit_turn_metadata(turn_id, "Doc Standards Agent", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")

    if not _is_admin_session(session_id, owner_id):
        yield {"type": "error", "content": "🔒 `/standardize-doc` requires admin privileges (L3_ADMIN)."}
        _audit_security_event("doc_standards_access_denied", {
            "session_id": session_id, "owner_id": owner_id,
            "reason": "insufficient_security_level",
        })
        logger.warning("[Router] Non-admin tried /standardize-doc: %s", owner_id)
        return

    yield {"type": "status", "content": "📄 Doc Standards Agent: Parsing command..."}
    AGENT_STATE.labels(agent_name="DocStandards").set(2)

    # Parse command flags
    try:
        parts = shlex.split(user_input)
    except ValueError:
        parts = user_input.split()

    parts = [p for p in parts if not p.lower().startswith("/standardize")]
    filepath = parts[0] if parts else ""
    flags = parts[1:] if len(parts) > 1 else []

    full_rewrite = "--full-rewrite" in flags
    dry_run = "--dry-run" in flags
    source_ref = ""
    external_urls = []

    if "--source-ref" in flags:
        idx = flags.index("--source-ref")
        if idx + 1 < len(flags):
            source_ref = flags[idx + 1]

    if "--urls" in flags:
        idx = flags.index("--urls")
        for u in flags[idx + 1:]:
            if u.startswith("--"):
                break
            if u.startswith("http"):
                external_urls.append(u)

    _model = model or os.getenv("ARCHITECT_MODEL", "qwen3:14b")

    if not filepath:
        yield {"type": "status", "content": "📄 Doc Standards Agent: No file specified — running full DocSite alignment..."}
        try:
            from specialized.doc_standards_agent import batch_scan
            for event in batch_scan(model=_model, auto_fix=not dry_run, full_rewrite=full_rewrite):
                etype = event.get("type", "")
                econtent = event.get("content", "")
                if etype in ("response", "message"):
                    yield _emit_stream_mode("responding")
                    yield {"type": "message", "content": econtent}
                else:
                    yield event
        except Exception as e:
            logger.error("[DocStandards] Batch scan failed: %s", e, exc_info=True)
            yield {"type": "error", "content": f"Doc Standards batch scan error: {e}"}

        AGENT_STATE.labels(agent_name="DocStandards").set(1)
        WORKFLOW_STEPS.labels(status="success", agent_type="DocStandards").inc()
        return

    try:
        from specialized.doc_standards_agent import standardize_document
        for event in standardize_document(
            filepath,
            model=_model,
            source_ref=source_ref,
            external_urls=external_urls or None,
            full_rewrite=full_rewrite,
            dry_run=dry_run,
        ):
            etype = event.get("type", "")
            econtent = event.get("content", "")
            if etype == "response":
                yield _emit_stream_mode("responding")
                yield {"type": "message", "content": econtent}
            else:
                yield event
    except Exception as e:
        logger.error("[DocStandards] Agent failed: %s", e, exc_info=True)
        yield {"type": "error", "content": f"Doc Standards Agent error: {e}"}

    AGENT_STATE.labels(agent_name="DocStandards").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="DocStandards").inc()
