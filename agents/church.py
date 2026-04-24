from phi.agent import Agent, RunResponse
from phi.model.ollama import Ollama
from leibniz_agent import get_architect_agent
from security_agent import get_security_agent

# MarsRL Loop — Solver → Verifier → Corrector
from mars_loop import MarsRLLoop, mars_loop_stream
from verifier_agent import get_verifier
from dijkstra_agent import get_corrector

from metrics import AGENT_STATE, WORKFLOW_STEPS
import time
import sys
import subprocess
import re
import os
import json
import requests
from dispatcher import Event, EventType
from logger_setup import setup_logger
from utils.gpu_queue import request_lock, get_best_host_for_model
from phi.storage.agent.postgres import PgAgentStorage
from config import AGNO_DB_URL

logger = setup_logger("Router")
security_audit_logger = setup_logger("SecurityAudit")

# --- Anthropic Provider (admin-only) ---
try:
    from providers.anthropic_provider import AnthropicProvider, is_available as anthropic_available, SUPPORTED_MODELS as ANTHROPIC_MODELS
    from config import ADMIN_ONLY_MODELS, ANTHROPIC_MODEL
    ANTHROPIC_ENABLED = anthropic_available()
    if ANTHROPIC_ENABLED:
        logger.info("[Router] Anthropic provider available (admin-only)")
except ImportError:
    ANTHROPIC_ENABLED = False
    ADMIN_ONLY_MODELS = set()
    ANTHROPIC_MODEL = ""
    logger.debug("[Router] Anthropic provider not loaded")

# Shared storage for conversationalist sessions (same pattern as architect_agent)
_conv_storage = PgAgentStorage(
    table_name="conversation_sessions",
    db_url=AGNO_DB_URL,
)

# --- JWT-ACE Integration ---
try:
    from intent_capabilities import get_capabilities_for_intent, get_session_capabilities
    from security.token_issuer import EphemeralAgentCard, get_token_issuer, derive_child_card
    from security.execution_context import (
        set_current_token, clear_current_token,
        set_active_scope, clear_active_scope,
    )
    JWT_ACE_AVAILABLE = True
    logger.info("[Router] JWT-ACE capability gating enabled")
except ImportError as e:
    JWT_ACE_AVAILABLE = False
    logger.warning(f"[Router] JWT-ACE not available: {e}")

# --- Template Registry ---
try:
    from expertise.template_registry import get_template_registry, PerformanceRecord
    TEMPLATES_AVAILABLE = True
    logger.info("[Router] ExpertiseTemplate registry enabled")
except ImportError as e:
    TEMPLATES_AVAILABLE = False
    logger.warning(f"[Router] Template registry not available: {e}")

# --- A/B Testing ---
try:
    from training.ab_test import get_ab_manager
    AB_TESTING_AVAILABLE = True
    logger.info("[Router] A/B testing enabled")
except ImportError as e:
    AB_TESTING_AVAILABLE = False
    logger.warning(f"[Router] A/B testing not available: {e}")

def _resolve_model_for_intent(intent: str, fallback_model: str) -> str:
    """
    Look up the default_model from the ExpertiseTemplate registry for a given intent.
    If an active A/B test exists for the template, probabilistically route to candidate.
    Falls back to the provided default if templates are unavailable or no match found.
    """
    if not TEMPLATES_AVAILABLE:
        return fallback_model
    try:
        registry = get_template_registry()
        templates = registry.list_templates(intent=intent)
        if templates and templates[0].default_model:
            resolved = templates[0].default_model
            template_id = templates[0].id
            logger.debug(f"[Router] Template resolved model for {intent}: {resolved}")

            # A/B test hook: check for active test and probabilistically route
            if AB_TESTING_AVAILABLE:
                try:
                    ab_mgr = get_ab_manager()
                    resolved = ab_mgr.route_model(template_id, resolved)
                except Exception as e:
                    logger.debug(f"[Router] A/B routing check failed: {e}")

            return resolved
    except Exception as e:
        logger.debug(f"[Router] Template model lookup failed for {intent}: {e}")
    return fallback_model


# --- Langfuse Tracing ---
try:
    from langfuse import Langfuse, observe
    import os
    
    langfuse = Langfuse(
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-dev"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-dev"),
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3001")
    )
    USE_LANGFUSE = True
    logger.info("[Router] Langfuse tracing enabled")
except ImportError:
    USE_LANGFUSE = False
    observe = lambda *args, **kwargs: lambda f: f  # No-op decorator
    logger.warning("[Router] Langfuse not available, tracing disabled")

@observe(name="handle_task_event")  # Langfuse traces this function
def handle_task_event(event: Event):
    """
    Callback for Dispatcher.
    Unwraps event and runs the swarm.
    Traced by Langfuse for observability.
    """
    print(f"DEBUG ROUTER: handle_task_event called with payload keys: {event.payload.keys()}")
    user_input = event.payload.get("task")
    intent = event.payload.get("intent", "DEFAULT") # From Dispatcher
    target_device = event.payload.get("target_device", "auto")
    session_id = event.payload.get("session_id", "default_session")
    owner_id = event.payload.get("owner_id")

    if not user_input:
        return
    
    # Enrich the current Langfuse trace (created by @observe decorator)
    if USE_LANGFUSE and langfuse:
        try:
            langfuse.update_current_span(
                metadata={
                    "intent": intent,
                    "target_device": target_device,
                    "session_id": session_id,
                    "owner_id": owner_id,
                }
            )
        except Exception as e:
            logger.warning(f"[Router] Trace update failed: {e}")
        
    logger.info(f"--- [Router] Processing Async Event: {user_input} (Intent: {intent}) ---")

    try:
        if intent == "VISION":
            # Direct Route to VLM for image analysis
            logger.info(f"[Router] Routing to Vision Analyst (moondream)")
            # Vision requires image data in the payload; without it, log and skip
            image_data = event.payload.get("image_data")
            if not image_data:
                logger.info("[Vision] No image data attached to async task — skipping VLM call")
                # Fall through to Orchestrator for a text-based response
                from teams import get_orchestrator
                orchestrator = get_orchestrator()
                response = orchestrator.run(user_input)
                logger.info(f"[Orchestrator] Final Response: {response.content}")
            else:
                vision_host = get_best_host_for_model("moondream:latest")
                payload = {
                    "model": "moondream:latest",
                    "prompt": user_input,
                    "images": [image_data],
                    "stream": False
                }
                res = requests.post(f"{vision_host}/api/generate", json=payload, timeout=120)
                if res.status_code == 200:
                    analysis = res.json().get("response", "No analysis returned.")
                    logger.info(f"[Vision] Analysis: {analysis}")
                else:
                    logger.error(f"[Vision] VLM returned status {res.status_code}")

        elif intent == "IMAGE":
            # Direct Route to Creative Team / Image Gen
            from specialized.image_gen import generate_image
            logger.info(f"[Router] Routing to Image Gen (Device: {target_device})")
            
            # Execute
            with request_lock(context="image"):
                response = generate_image(user_input, target_device=target_device)
            logger.info(f"[ImageGen] Result: {response}")
            
        elif intent == "3D":
             # Direct Route to 3D Pipeline
             from specialized.image_gen import generate_image
             # ... (Add 3D logic if needed, or just use image gen for concept art first)
             logger.info("[Router] Routing to 3D Pipeline (starting with concept art)...")
             with request_lock(context="image"):
                 response = generate_image(f"Concept art for 3d modeling: {user_input}", target_device=target_device)
             logger.info(f"[3D] Concept Art Result: {response}")
             # trigger forge here if implemented

        elif intent == "COORDINATE":
            # Multi-worker orchestration via Lamport Mode
            from lamport import coordinate_task
            logger.info(f"[Router] Routing to Lamport Mode (async path)")
            for update in coordinate_task(
                user_input=user_input,
                session_id=session_id,
                owner_id=owner_id,
            ):
                if update.get("type") == "response":
                    logger.info(f"[Coordinator] Final: {update['content'][:200]}")
                elif update.get("type") == "error":
                    logger.error(f"[Coordinator] Error: {update['content']}")
             
        else:
            # Default: Orchestrator with session persistence
            from teams import get_orchestrator
            orchestrator = get_orchestrator()
            # Run the orchestrator (it handles delegation to teams)
            response = orchestrator.run(user_input)
            logger.info(f"[Orchestrator] Final Response: {response.content}")
        
    except Exception as e:
        logger.error(f"Task Execution Failed: {e}")

    # Reset state after loop
    AGENT_STATE.labels(agent_name="Router").set(1)

# --- JWT-ACE Token Issuance ---
def _issue_ephemeral_token(intent: str, session_id: str, owner_id: str | None = None) -> tuple:
    """
    Issue a JWT-ACE token for the given intent.

    Returns:
        (token_str, template_metadata_dict) or (None, {}) on failure
    """
    if not JWT_ACE_AVAILABLE:
        return None, {}

    try:
        caps = get_capabilities_for_intent(intent)

        # Look up template version if registry is available
        template_version = "1.0"
        template_system_prompt = None
        if TEMPLATES_AVAILABLE:
            try:
                registry = get_template_registry()
                tv = registry.get_template_version(caps["template_id"], "latest")
                if tv:
                    template_version = tv.version
                    template_system_prompt = tv.system_prompt
            except Exception as e:
                logger.debug(f"[JWT-ACE] Template lookup failed (using defaults): {e}")

        card = EphemeralAgentCard(
            template_id=caps["template_id"],
            template_version=template_version,
            agent_name=caps["agent_name"],
            activated_capabilities=caps["capabilities"],
            security_level=caps["security_level"],
            user_id=owner_id,
            session_id=session_id,
            expiry_hours=caps["expiry_hours"],
        )

        issuer = get_token_issuer()
        token = issuer.issue_token(card)

        metadata = {
            "template_id": caps["template_id"],
            "template_version": template_version,
            "agent_instance_id": card.agent_instance_id,
            "token_capabilities": caps["capabilities"],
            "system_prompt_override": template_system_prompt,
        }

        logger.info(
            f"[JWT-ACE] Token issued for {caps['agent_name']} "
            f"(template: {caps['template_id']} v{template_version}, "
            f"{len(caps['capabilities'])} capabilities)"
        )
        return token, metadata

    except Exception as e:
        logger.warning(f"[JWT-ACE] Token issuance failed (non-fatal): {e}")
        return None, {}


def _issue_session_card(session_id: str, owner_id: str | None = None) -> tuple:
    """
    Issue a session-level JWT-ACE card with the **union** of all intent
    capabilities.  Per-intent narrowing is handled via ``set_active_scope()``.

    Returns:
        (token_str, card, metadata_dict)  or  (None, None, {})  on failure
    """
    if not JWT_ACE_AVAILABLE:
        return None, None, {}

    try:
        session_caps = get_session_capabilities()

        template_version = "1.0"
        if TEMPLATES_AVAILABLE:
            try:
                registry = get_template_registry()
                tv = registry.get_template_version(session_caps["template_id"], "latest")
                if tv:
                    template_version = tv.version
            except Exception:
                pass

        card = EphemeralAgentCard(
            template_id=session_caps["template_id"],
            template_version=template_version,
            agent_name=session_caps["agent_name"],
            activated_capabilities=session_caps["capabilities"],
            security_level=session_caps["security_level"],
            user_id=owner_id,
            session_id=session_id,
            expiry_hours=session_caps["expiry_hours"],
        )

        issuer = get_token_issuer()
        token = issuer.issue_token(card)

        metadata = {
            "template_id": session_caps["template_id"],
            "template_version": template_version,
            "agent_instance_id": card.agent_instance_id,
            "token_capabilities": session_caps["capabilities"],
        }

        logger.info(
            f"[JWT-ACE] Session card issued for {session_id} "
            f"({len(session_caps['capabilities'])} capabilities, "
            f"level {session_caps['security_level']})"
        )
        return token, card, metadata

    except Exception as e:
        logger.warning(f"[JWT-ACE] Session card issuance failed (non-fatal): {e}")
        return None, None, {}


def _record_performance(intent: str, template_metadata: dict, result_data: dict):
    """Record execution performance for template evolution."""
    if not TEMPLATES_AVAILABLE or not template_metadata.get("template_id"):
        return
    try:
        registry = get_template_registry()
        record = PerformanceRecord(
            template_id=template_metadata["template_id"],
            template_version=template_metadata.get("template_version", "1.0"),
            trace_id=result_data.get("trace_id"),
            session_id=result_data.get("session_id"),
            intent=intent,
            solver_score=result_data.get("solver_score"),
            verifier_score=result_data.get("verifier_score"),
            final_score=result_data.get("final_score"),
            corrector_invoked=result_data.get("corrector_invoked", False),
            iterations=result_data.get("iterations", 1),
            latency_ms=result_data.get("latency_ms"),
        )
        registry.record_performance(record)
    except Exception as e:
        logger.debug(f"[JWT-ACE] Performance recording failed (non-fatal): {e}")


# --- SPECIALIZED INTENT DETECTION ---
# (Keyword-based detect_intent() was removed in favor of neural semantic_router)
def _score_trace(lf_trace, langfuse_inst, score: float, output: str = None):
    """Score the current Langfuse trace as a training candidate and optionally set its output."""
    if not langfuse_inst or not USE_LANGFUSE:
        return
    try:
        if output:
            langfuse_inst.set_current_trace_io(output={"response": output[:4000]})
        langfuse_inst.score_current_trace(
            name="training_candidate",
            value=score,
        )
    except Exception as e:
        logger.debug(f"[Router] Trace scoring failed: {e}")


from contextlib import contextmanager

@contextmanager
def _langfuse_span(name: str, agent_name: str, model_id: str, input_text: str):
    """Create a Langfuse observation span around an agent execution.
    Yields a dict that the caller should populate with 'output' when done."""
    result = {"output": ""}
    if USE_LANGFUSE and langfuse:
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
            logger.debug(f"[Router] Span creation failed for {name}: {e}")
            yield result
    else:
        yield result


def _is_explicit_train_request(text: str) -> bool:
    """Return True only for clear, intentional memory-training instructions."""
    if not text:
        return False

    normalized = text.strip().lower()
    explicit_prefixes = (
        "learn:",
        "correction:",
        "remember that",
        "remember this rule",
        "store this rule",
        "add rule",
    )
    if normalized.startswith(explicit_prefixes):
        return True

    # Structured teaching pattern used by the trainer route.
    teach_pattern = re.search(
        r"(?:remember that|correction:|learn:)\s+(.+?)\s+(?:means|is|should be)\s+(.+)",
        text,
        re.IGNORECASE,
    )
    return bool(teach_pattern)


def _extract_constraint_context(history: list | None, user_input: str) -> str:
    """Extract important user constraints from prior turns for requirement continuity."""
    if not history:
        return ""

    keywords = (
        "constraint",
        "must",
        "avoid",
        "maintenance window",
        "no-downtime",
        "no downtime",
        "requirement",
    )
    constraints = []
    for msg in history:
        _role = msg.get("role", "user") if isinstance(msg, dict) else getattr(msg, "role", "user")
        if _role != "user":
            continue
        _content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        content = str(_content).strip()
        if not content:
            continue
        lowered = content.lower()
        if any(k in lowered for k in keywords):
            constraints.append(content)

    if not constraints:
        return ""

    # Keep only the most recent few constraints to reduce prompt bloat.
    recent = constraints[-3:]
    block = "\n".join([f"- {c}" for c in recent])
    return (
        "[Active User Constraints - Must Respect]\n"
        f"{block}\n"
        "Do not ignore these constraints in the final answer."
    )


def _is_admin_session(session_id: str, owner_id: str | None) -> bool:
    """Check if the current session holds L3_ADMIN or higher."""
    if not JWT_ACE_AVAILABLE:
        return False
    try:
        from security.execution_context import get_current_token
        from security.token_issuer import get_token_validator

        token = get_current_token()
        if not token:
            return False

        validator = get_token_validator()
        card = validator.validate_token(token)
        level = str(getattr(card, "security_level", "L1_PUBLIC"))
        ranks = {
            "L1_PUBLIC": 1,
            "L2_USER": 2,
            "L3_ADMIN": 3,
            "L4_SYSTEM": 4,
        }
        return ranks.get(level, 0) >= ranks["L3_ADMIN"]
    except Exception:
        pass
    return False


def _is_anthropic_model(model_name: str) -> bool:
    """Return True if the requested model is an Anthropic/Claude model."""
    return model_name in ADMIN_ONLY_MODELS or model_name.startswith("claude-")


def _audit_security_event(event_type: str, context: dict[str, object]) -> None:
    """Emit structured security audit events with contextual fields."""
    payload = {
        "event_type": event_type,
        "component": "router",
        "source": "chat_swarm",
        **context,
    }
    security_audit_logger.warning(json.dumps(payload, ensure_ascii=True))


# --- Stream Event Helper Functions ---
def _emit_stream_mode(mode: str) -> dict:
    """Emit a stream mode indicator (thinking, responding, tool-use, requesting, compacting)."""
    return {"type": "stream_mode", "streamMode": mode}


def _emit_turn_metadata(turn_id: str, agent_name: str, stream_modes: list = None) -> dict:
    """Emit turn-level metadata for UI turn grouping and navigation."""
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
    """Emit a turn boundary marker to help frontend group messages by turn."""
    return {
        "type": "turn_boundary",
        "content": f"[Turn {turn_id} {final_status}]",
        "turnId": turn_id,
    }


def _emit_tool_start(tool_call_id: str, tool_name: str, tool_input: dict = None) -> dict:
    """Emit a tool execution start event."""
    return {
        "type": "tool_start",
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "tool_input": tool_input or {},
        "tool_state": "queued",
    }


def _emit_tool_progress(tool_call_id: str, tool_name: str, progress: float = 0, status_msg: str = "") -> dict:
    """Emit a tool in-progress event."""
    return {
        "type": "tool_progress",
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "tool_state": "executing",
        "tool_progress": min(progress, 100),
        "content": status_msg,
    }


def _emit_tool_result(tool_call_id: str, tool_name: str, output: str, success: bool = True, artifacts: list = None) -> dict:
    """Emit a tool result event with optional artifacts."""
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
    """Emit a hint about whether conversation should auto-continue after tool execution."""
    return {
        "type": "continuation",
        "continuationHint": hint_type,
        "content": reason,
    }


def _parse_think_tags(text: str):
    """Parse streaming text that may contain <think>...</think> blocks.
    
    Yields (type, content) tuples where type is 'thought' or 'message'.
    Handles partial tags across chunk boundaries via a simple state machine.
    """
    import re
    # Split on think tags, preserving them
    parts = re.split(r'(<think>|</think>)', text)
    in_think = False
    for part in parts:
        if part == '<think>':
            in_think = True
            continue
        elif part == '</think>':
            in_think = False
            continue
        if part:
            yield ("thought" if in_think else "message", part)


# ---------------------------------------------------------------------------
# Grounding helpers
# ---------------------------------------------------------------------------

# Keywords that suggest the query needs live / external information
_WEB_GROUNDING_KEYWORDS = frozenset([
    "latest", "current", "today", "now", "news", "recent", "recently",
    "yesterday", "this week", "this month", "this year", "2024", "2025",
    "who won", "what is the price", "stock price", "weather", "trending",
    "breaking", "just announced", "released", "update", "version",
])


def _needs_web_grounding(query: str) -> bool:
    """Return True when the query likely benefits from live web results."""
    q = query.lower()
    return any(kw in q for kw in _WEB_GROUNDING_KEYWORDS)


def _retrieve_doc_context(query: str, owner_id: str | None, limit: int = 5) -> list[dict]:
    """Query PgVector for the top-*limit* relevant knowledge-base chunks.

    Returns a list of dicts with keys ``source`` and ``content``.
    Returns an empty list on any error so the caller can stay non-fatal.
    """
    try:
        import os as _os
        from agno.vectordb.pgvector import PgVector, SearchType
        from agno.embedder.ollama import OllamaEmbedder

        db_url = _os.getenv("AGNO_DB_URL", "postgresql+psycopg://ai:ai@localhost:5532/ai")
        collection = "architect_knowledge"

        embedder = OllamaEmbedder(id="nomic-embed-text", dimensions=768)
        vdb = PgVector(
            table_name=collection,
            db_url=db_url,
            search_type=SearchType.hybrid,
            embedder=embedder,
        )
        rows = vdb.search(query=query, limit=limit)
        results: list[dict] = []
        for row in rows or []:
            content = getattr(row, "content", None) or str(row)
            meta = getattr(row, "meta_data", {}) or {}
            source = meta.get("source", meta.get("name", "unknown"))
            results.append({"source": source, "content": content})
        return results
    except Exception as exc:
        import logging as _logging
        _logging.getLogger("Router").debug("[Router] Doc grounding retrieval failed: %s", exc)
        return []


def chat_swarm(
    user_input: str,
    session_id: str = "default_session",
    history: list = None,
    memory_enabled: bool = False,
    owner_id: str | None = None,
    model: str | None = None,
    skill: str | None = None,
    style: str | None = None,
    research_mode: bool = False,
    ultraplan_mode: bool = False,
    ultrathink_mode: bool = False,
    attachments: list | None = None,
    grounding_web: bool = False,
    grounding_docs: bool = False,
    grounding_file: bool = False,
    swarm_mode: bool = False,
):
    """
    Generator that yields status updates and final response for UI.
    - history: Optional list of OpenAI-formatted messages [{"role": "user", "content": "..."}]
    - memory_enabled: If True, inject recent session summaries as system context.
    - skill: Routing hint to bias intent classification.
    - style: Response style modifier for the system prompt.
    - research_mode: If True, forces deep multi-step reasoning via MarsRL.
    - ultraplan_mode: If True, decompose task into plan only — no execution.
    - ultrathink_mode: If True, use deeper reasoning with visible chain-of-thought.
    - attachments: File attachments from the UI.
    - grounding_web: If True and owner has permission, run intent-aware web search
      and inject top results as [Web Grounding Context] before the prompt.
    - grounding_docs: If True and owner has permission, query the knowledge base and
      inject relevant chunks as [Document Context] before the prompt.
    - grounding_file: If True and owner has permission, scan the workspace for relevant
      files and inject matched content as [File Context] before the prompt.
    """
    AGENT_STATE.labels(agent_name="Router").set(2)
    WORKFLOW_STEPS.labels(status="started", agent_type="Router").inc()
    logger.info("--- [Router] chat_swarm v4.1 (ACTION_FIGURE + context-session-scoped) ---")

    # JWT-ACE state (initialized here so finally block can always access them)
    ace_token = None
    ace_card = None  # EphemeralAgentCard for this session
    template_metadata = {}
    route_start_time = time.time()
    lf_trace = None  # Langfuse trace handle (populated below if Langfuse is active)
    turn_id = f"{session_id}-{int(time.time()*1000)}"

    # Collect thought/log events for Langfuse trace narrative
    _trace_thoughts = []  # {"type": "thought"|"log", "content": "..."}

    def _t(content: str) -> dict:
        """Create a thought event and collect it for tracing."""
        _trace_thoughts.append({"type": "thought", "content": content, "ts": time.time()})
        return {"type": "thought", "content": content}

    def _l(content: str) -> dict:
        """Create a log event and collect it for tracing."""
        _trace_thoughts.append({"type": "log", "content": content, "ts": time.time()})
        return {"type": "log", "content": content}

    # --- Langfuse top-level trace for all intents (v4 context manager) ---
    _lf_ctx = None
    if USE_LANGFUSE and langfuse:
        try:
            _lf_ctx = langfuse.start_as_current_observation(
                name="chat_swarm",
                as_type="agent",
                input={"message": user_input[:4000]},
                metadata={"session_id": session_id, "owner_id": owner_id, "model": model},
            )
            _lf_ctx.__enter__()
            lf_trace = langfuse.get_current_trace_id()
        except Exception as e:
            _lf_ctx = None
            logger.debug(f"[Router] Trace creation failed: {e}")

    # --- JWT-ACE: Issue session-level card (broad capabilities) ---
    if JWT_ACE_AVAILABLE:
        ace_token, ace_card, template_metadata = _issue_session_card(session_id, owner_id)
        if ace_token:
            set_current_token(ace_token)
            yield {"type": "log", "content": f"[JWT-ACE] Session card issued ({template_metadata.get('template_id', 'session_agent')})"}

    # --- HISTORY CONVERSION ---
    # PHI Agents use their own storage/history, but we can seed it or pass it.
    # For now, we'll use history to enhance the prompt if provided.
    history_context = ""
    if history:
        history_context = "\n\n[Previous Conversation History]:\n"
        for msg in history:
            role = msg.get("role", "user") if isinstance(msg, dict) else getattr(msg, "role", "user")
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            history_context += f"- {role.upper()}: {content}\n"
    
    # --- RAG CONTEXT INTERCEPTION ---
    import re
    extracted_context = ""
    context_match = re.search(r'<context>.*?</context>', user_input, re.DOTALL)
    if context_match:
        extracted_context = context_match.group(0)
        # Strip Open-WebUI's boilerplate injection
        user_input = re.sub(r'### Task:.*?<context>.*?</context>\s*', '', user_input, flags=re.DOTALL).strip()
        yield _l(f"[Router] Intercepted RAG Context ({len(extracted_context)} chars).")
    
    # 1. Load Context (Memory Bridge)
    from brooks import get_pending_context, clear_context, save_pending_image_clarification
    pending_ctx = get_pending_context(session_id=session_id, owner_id=owner_id)
    
    # Check if this is a reply to a clarification
    if pending_ctx:
        if pending_ctx.get("type") == "image_clarification":
            original_prompt = pending_ctx.get("prompt", "")
            # Guard: discard stale/snowballing context (>500 chars means it's been re-merged)
            if len(original_prompt) > 500:
                logger.warning(f"--- [Router] Discarding stale context ({len(original_prompt)} chars) ---")
                yield {"type": "log", "content": "[Context Manager] Stale context discarded."}
                clear_context(session_id=session_id, owner_id=owner_id)
            else:
                logger.info(f"--- [Router] Merging Context. Original: '{original_prompt}' + New: '{user_input}' ---")
                user_input = f"{original_prompt} {user_input}"
                yield {"type": "log", "content": f"[Context Manager] Context Merged: '{user_input}'"}
                clear_context(session_id=session_id, owner_id=owner_id)
            
        elif pending_ctx.get("type") == "art_studio_redirect":
            # This was saved for the Art Studio workspace — clear it, don't merge
            clear_context(session_id=session_id, owner_id=owner_id)

        elif pending_ctx.get("type") == "ambiguity_resolution":
            original = pending_ctx.get("prompt")
            question = pending_ctx.get("question")
            logger.info(f"--- [Router] Resolving Ambiguity. Original: '{original}' + Answer: '{user_input}' ---")
            
            # Composite prompt for the Semantic Router
            user_input = f"Original Request: '{original}'\nSystem Question: '{question}'\nUser Answer: '{user_input}'"
            
            yield {"type": "log", "content": f"[Context Manager] Ambiguity Resolved. Analying composite input..."}
            clear_context(session_id=session_id, owner_id=owner_id)

    try:
        yield _emit_turn_metadata(turn_id, "Router", ["thinking"])
        yield _emit_stream_mode("thinking")
        # 1b. Memory Recall — inject prior session summaries as system context
        if memory_enabled:
            try:
                from memory_system import memory as _mem
                recent = _mem.get_recent_summaries(n=5, owner_id=owner_id)
                if recent:
                    recall_text = "\n".join(
                        f"- [{s.get('date', '?')}] {s.get('topic', '')}: {s.get('summary', '')}"
                        for s in recent
                    )
                    recall_msg = {"role": "system", "content": f"[Prior Session Context]\n{recall_text}"}
                    if history is None:
                        history = [recall_msg]
                    else:
                        history = [recall_msg] + list(history)
                    yield _t(f"→ Memory: Recalled {len(recent)} prior session summaries")
            except Exception as _mem_err:
                logger.debug(f"[Router] Memory recall failed (non-fatal): {_mem_err}")

        # 1c. MemPalace Semantic Recall — inject relevant memories from vector store
        if memory_enabled:
            try:
                import httpx as _httpx_recall
                _mp_url = os.getenv("MEMPALACE_API_URL", "http://192.168.2.102:8200")
                with _httpx_recall.Client(timeout=10.0) as _mp_client:
                    _mp_resp = _mp_client.post(
                        f"{_mp_url}/v1/memories/search",
                        json={"query": user_input, "owner_id": owner_id, "limit": 5},
                    )
                if _mp_resp.status_code == 200:
                    relevant = _mp_resp.json()
                    strong = [m for m in relevant if (m.get("score") or 0) > 0.5]
                    if strong:
                        semantic_text = "\n".join(f"- {m['content']}" for m in strong)
                        mp_msg = {"role": "system", "content": f"[Relevant Memories]\n{semantic_text}"}
                        if history is None:
                            history = [mp_msg]
                        else:
                            history.append(mp_msg)
                        yield _t(f"→ MemPalace: {len(strong)} relevant memories recalled")
            except Exception as _mp_err:
                logger.debug(f"[Router] MemPalace recall failed (non-fatal): {_mp_err}")

        # 1d. Web Grounding — inject live search results when permitted and intent warrants it
        if grounding_web:
            try:
                from grounding_permissions import grounding_permissions as _gp
                if _gp.is_permitted(owner_id or "", "web_grounding"):
                    if _needs_web_grounding(user_input):
                        from tools.web_browser import web_search as _web_search
                        yield {"type": "status", "content": "🌐 Web Grounding: Searching..."}
                        results = _web_search(user_input, num_results=5)
                        if results:
                            snippets = "\n".join(
                                f"[{i+1}] {r.get('title','')}\n{r.get('url','')}\n{r.get('snippet','')}"
                                for i, r in enumerate(results)
                            )
                            web_msg = {"role": "system", "content": f"[Web Grounding Context]\n{snippets}"}
                            if history is None:
                                history = [web_msg]
                            else:
                                history.append(web_msg)
                            yield _t(f"→ Web grounding: {len(results)} results injected")
                        else:
                            yield _t("→ Web grounding: no results returned")
                    else:
                        yield _t("→ Web grounding: skipped (query does not need live data)")
                else:
                    logger.warning(
                        "[Router] Web grounding requested by %s but permission not granted", owner_id
                    )
                    yield {"type": "status", "content": "⚠️ Web grounding not permitted — submit a governance request."}
            except Exception as _wg_err:
                logger.error("[Router] Web grounding failed (non-fatal): %s", _wg_err)

        # 1e. Document Grounding — inject relevant knowledge-base chunks when permitted
        if grounding_docs:
            try:
                from grounding_permissions import grounding_permissions as _gp
                if _gp.is_permitted(owner_id or "", "docs_grounding"):
                    chunks = _retrieve_doc_context(user_input, owner_id, limit=5)
                    if chunks:
                        doc_text = "\n\n".join(
                            f"[Source: {c.get('source','unknown')}]\n{c.get('content','')}"
                            for c in chunks
                        )
                        doc_msg = {"role": "system", "content": f"[Document Context]\n{doc_text}"}
                        if history is None:
                            history = [doc_msg]
                        else:
                            history.append(doc_msg)
                        yield _t(f"→ Doc grounding: {len(chunks)} chunks injected")
                    else:
                        yield _t("→ Doc grounding: no relevant chunks found")
                else:
                    logger.warning(
                        "[Router] Doc grounding requested by %s but permission not granted", owner_id
                    )
                    yield {"type": "status", "content": "⚠️ Document grounding not permitted — submit a governance request."}
            except Exception as _dg_err:
                logger.error("[Router] Doc grounding failed (non-fatal): %s", _dg_err)

        # 1f. File Grounding — inject workspace file content when permitted
        if grounding_file:
            try:
                from grounding_permissions import grounding_permissions as _gp
                if _gp.is_permitted(owner_id or "", "file_grounding"):
                    import os as _os
                    _workspace_root = _os.environ.get("WORKSPACE_PATH", "/workspace")
                    yield {"type": "status", "content": "📁 File Grounding: Scanning workspace..."}
                    _query_words = set(user_input.lower().split())
                    _file_snippets: list[str] = []
                    try:
                        for _root, _dirs, _files in _os.walk(_workspace_root):
                            # Skip hidden dirs and common noise dirs
                            _dirs[:] = [d for d in _dirs if not d.startswith(".") and d not in (
                                "__pycache__", "node_modules", ".git", ".venv", "venv"
                            )]
                            for _fname in _files:
                                if not _fname.endswith((".py", ".md", ".txt", ".json", ".yaml", ".yml", ".sh", ".env")):
                                    continue
                                _fpath = _os.path.join(_root, _fname)
                                _rel = _os.path.relpath(_fpath, _workspace_root)
                                # Relevance: filename or path words must intersect query
                                _path_words = set(_rel.lower().replace("/", " ").replace("_", " ").replace("-", " ").split())
                                if not _query_words.intersection(_path_words):
                                    continue
                                try:
                                    with open(_fpath, "r", encoding="utf-8", errors="ignore") as _fh:
                                        _content = _fh.read(2000)  # cap at 2 KB per file
                                    _file_snippets.append(f"[File: {_rel}]\n{_content}")
                                    if len(_file_snippets) >= 5:
                                        break
                                except Exception:
                                    pass
                            if len(_file_snippets) >= 5:
                                break
                    except Exception as _walk_err:
                        logger.warning("[Router] File grounding walk error: %s", _walk_err)
                    if _file_snippets:
                        file_msg = {"role": "system", "content": "[File Context]\n" + "\n\n".join(_file_snippets)}
                        if history is None:
                            history = [file_msg]
                        else:
                            history.append(file_msg)
                        yield _t(f"→ File grounding: {len(_file_snippets)} file(s) injected")
                    else:
                        yield _t("→ File grounding: no matching files found")
                else:
                    logger.warning(
                        "[Router] File grounding requested by %s but permission not granted", owner_id
                    )
                    yield {"type": "status", "content": "⚠️ File grounding not permitted — submit a governance request."}
            except Exception as _fg_err:
                logger.error("[Router] File grounding failed (non-fatal): %s", _fg_err)
        yield {"type": "status", "content": "🔒 Security Agent: Scanning input..."}
        security = get_security_agent()
        AGENT_STATE.labels(agent_name="Security").set(2)
        
        security_check: RunResponse = security.run(f"Validate this user command for safety: {user_input}")
        yield {"type": "log", "content": f"[Security Analysis] Algo: Llama-Guard | Output: {security_check.content}"}
        
        AGENT_STATE.labels(agent_name="Security").set(1)
        
        if "UNSAFE" in security_check.content.upper():
            yield {"type": "error", "content": f"🚫 BLOCKED: {security_check.content}"}
            WORKFLOW_STEPS.labels(status="blocked", agent_type="Security").inc()
            return # HITL Block

        yield {"type": "status", "content": "✅ Security Agent: Input Cleared."}
        yield _t("→ Security: PASS")
        WORKFLOW_STEPS.labels(status="success", agent_type="Security").inc()

        # --- ANTHROPIC FAST-PATH (admin-only Claude models) ---
        if model and _is_anthropic_model(model):
            if not _is_admin_session(session_id, owner_id):
                yield {"type": "error", "content": "🔒 Claude models require admin privileges. Falling back to local model."}
                logger.warning(f"[Router] Non-admin tried Anthropic model: {model}")
                _audit_security_event(
                    "claude_access_denied",
                    {
                        "requested_model": model,
                        "session_id": session_id,
                        "owner_id": owner_id,
                        "reason": "insufficient_security_level",
                    },
                )
                model = None  # Fall through to normal Ollama routing
            elif ANTHROPIC_ENABLED:
                yield {"type": "status", "content": f"☁️ Claude ({model}): Generating..."}
                yield _t(f"→ Provider: Anthropic ({model})")
                try:
                    provider = AnthropicProvider(model=model)
                    api_messages = [{"role": "user", "content": user_input}]
                    if history:
                        api_messages = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in history]
                        api_messages.append({"role": "user", "content": user_input})

                    for chunk in provider.generate_stream(
                        prompt=user_input,
                        messages=api_messages,
                        system="You are Hive Mind, a helpful AI assistant in a self-hosted home lab.",
                    ):
                        yield chunk.as_dict()

                    _score_trace(lf_trace, langfuse, 0.9, output="[anthropic stream]")
                    WORKFLOW_STEPS.labels(status="success", agent_type="Anthropic").inc()
                except Exception as e:
                    logger.error(f"[Router] Anthropic provider error: {e}")
                    yield {"type": "error", "content": f"Claude API error: {e}"}
                    _score_trace(lf_trace, langfuse, 0.0)
                finally:
                    AGENT_STATE.labels(agent_name="Router").set(1)
                return
            else:
                logger.warning(
                    f"[Router] Claude model requested but provider unavailable: {model}"
                )
                _audit_security_event(
                    "claude_provider_unavailable",
                    {
                        "requested_model": model,
                        "session_id": session_id,
                        "owner_id": owner_id,
                        "reason": "provider_not_configured",
                    },
                )
                yield {
                    "type": "error",
                    "content": "Claude provider is not configured. Falling back to local model.",
                }
                model = None

        # 3. Intent Routing (Neural Upgrade)
        # Short-circuit: swarm_mode has a fixed intent, skip the LLM neural router
        if swarm_mode:
            intent = "COORDINATE"
            confidence = 1.0
            reasoning = "swarm_mode=True bypasses neural router"
            yield {"type": "status", "content": "🧩 Swarm Mode: Routing directly to multi-agent coordinator..."}
        else:
            from semantic_router import get_semantic_router
            
            yield {"type": "status", "content": "🧠 Neural Cortex: Analyzing intent..."}
            
            router_inst = get_semantic_router()
            routing_decision = router_inst.route(user_input)
            intent = routing_decision.get("intent", "RESEARCH") # Fail safe default
            confidence = routing_decision.get("confidence", 0.0)
            reasoning = routing_decision.get("reasoning", "No reasoning provided.")

        constraint_context = _extract_constraint_context(history, user_input)

        # --- KEYWORD OVERRIDE: Catch intents the LLM doesn't know about ---
        _lower = user_input.lower()
        if _is_explicit_train_request(user_input) and intent != "TRAIN":
            intent = "TRAIN"
            confidence = 0.98
            reasoning = f"Keyword override: explicit training directive detected in '{user_input[:60]}'"
        if any(kw in _lower for kw in ["action figure", "posable", "ball joint", "figurine", "poseable"]):
            intent = "ACTION_FIGURE"
            confidence = 0.95
            reasoning = f"Keyword override: action figure keywords detected in '{user_input[:60]}'"
        # --- /standardize-doc command (admin-only) ---
        if _lower.strip().startswith("/standardize-doc"):
            intent = "DOC_STANDARDS"
            confidence = 1.0
            reasoning = "Slash command: /standardize-doc"
        
        yield _l(f"[Router] Intent: {intent} ({confidence * 100:.1f}%) | Reason: {reasoning}")
        logger.info(f"--- [Router] Neural Decision: {intent} (Conf: {confidence}) ---")

        if intent == "TRAIN" and not _is_explicit_train_request(user_input):
            logger.info(
                "[Router] TRAIN intent downgraded to CONVERSATION due to missing explicit training directive. "
                f"Input preview: {user_input[:120]}"
            )
            yield {
                "type": "log",
                "content": "[Router] TRAIN intent downgraded to CONVERSATION (missing explicit training directive).",
            }
            intent = "CONVERSATION"
            confidence = max(confidence, 0.75)

        yield _t(f"→ Intent: {intent} ({confidence * 100:.0f}% confidence)")

        # --- FAST MODE: hive-fast skips MarsRL verification loop ---
        _fast_mode = (model == "hive-fast")
        if _fast_mode:
            yield _l("[Router] Hive Fast mode — single-pass, no MarsRL verification.")

        # --- SKILL HINT OVERRIDE ---
        # If the UI sent an explicit skill hint, override intent when confidence is low
        _skill_to_intent = {
            "code": "DEVOPS",
            "devops": "DEVOPS",
            "data": "DATA",
            "creative": "IMAGE",
            "research": "RESEARCH",
        }
        if skill and skill in _skill_to_intent and confidence < 0.80:
            old_intent = intent
            intent = _skill_to_intent[skill]
            yield _t(f"→ Skill override: {old_intent} → {intent} (skill={skill})")

        # --- RESEARCH MODE OVERRIDE ---
        if research_mode and intent not in ("IMAGE", "3D", "ACTION_FIGURE", "TRAIN"):
            intent = "RESEARCH"
            yield _t("→ Research mode activated: forcing RESEARCH intent")

        # --- SWARM MODE OVERRIDE ---
        if swarm_mode and intent not in ("IMAGE", "3D", "ACTION_FIGURE", "TRAIN"):
            intent = "COORDINATE"
            yield _t("→ Swarm Mode: routing to multi-agent coordinator")

        # --- ULTRAPLAN MODE: Plan-Only (no execution) ---
        if ultraplan_mode:
            yield _emit_turn_metadata(turn_id, "Planner", ["thinking", "responding"])
            yield _emit_stream_mode("thinking")
            yield {"type": "status", "content": "📋 Planner: Decomposing task..."}
            yield _t("→ UltraPlan mode: generating plan only (no execution)")

            PLAN_MODEL = _resolve_model_for_intent("CONVERSATION", os.getenv("PLAN_MODEL", os.getenv("PRIMARY_MODEL", "qwen3:14b")))
            OLLAMA_HOST = get_best_host_for_model(PLAN_MODEL)

            plan_system_prompt = (
                "You are a task planning agent. Your ONLY job is to analyze the user's request "
                "and produce a structured execution plan. You must NOT execute any steps.\n\n"
                "Output format:\n"
                "## Plan: [Brief title]\n\n"
                "**Goal**: [One sentence summary of what the user wants]\n\n"
                "**Steps**:\n"
                "1. **[Step Name]** — [Description of what this step does]\n"
                "   - Dependencies: [none | step numbers this depends on]\n"
                "   - Agent: [which specialist would handle this: Code Developer, Art Director, Librarian, etc.]\n"
                "2. **[Step Name]** — [Description]\n"
                "   ...\n\n"
                "**Estimated Complexity**: [Low | Medium | High]\n"
                "**Notes**: [Any caveats, risks, or alternative approaches]\n\n"
                "IMPORTANT: Output ONLY the plan. Do NOT execute, implement, or produce any code/content. "
                "The user will review this plan and decide whether to proceed."
            )

            if ultrathink_mode:
                plan_system_prompt += (
                    "\n\nBefore writing the plan, think deeply about the request. "
                    "Consider edge cases, dependencies, and potential issues. "
                    "Show your reasoning process wrapped in <think>...</think> tags before the plan."
                )

            planner = Agent(
                name="Planner",
                model=Ollama(id=PLAN_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 120.0}),
                session_id=session_id,
                instructions=plan_system_prompt,
                show_tool_calls=False,
            )

            try:
                with request_lock(context="text"):
                    yield _emit_stream_mode("responding")
                    response_stream = planner.run(user_input, stream=True)
                    for chunk in response_stream:
                        if chunk.content:
                            yield {"type": "plan", "content": chunk.content}
            except Exception as e:
                yield {"type": "error", "content": f"Plan generation failed: {e}"}
                logger.error(f"[Router] UltraPlan failed: {e}", exc_info=True)

            WORKFLOW_STEPS.labels(status="success", agent_type="Planner").inc()
            AGENT_STATE.labels(agent_name="Router").set(1)
            return

        # --- ULTRATHINK MODE: Inject chain-of-thought system prompt ---
        if ultrathink_mode:
            think_instruction = (
                "[Deep Reasoning Mode] Think through this problem step-by-step before answering. "
                "Show your reasoning process: identify the key aspects, consider alternatives, "
                "evaluate tradeoffs, and then provide your final answer. "
                "Wrap your internal reasoning in <think>...</think> tags. "
                "After the thinking block, provide your clear final response."
            )
            think_msg = {"role": "system", "content": think_instruction}
            if history is None:
                history = [think_msg]
            else:
                history = list(history) + [think_msg]
            yield _t("→ UltraThink: deep reasoning mode activated")

        # --- STYLE SYSTEM PROMPT ---
        _style_prompts = {
            "concise": "Respond as concisely as possible. Use bullet points and short sentences.",
            "explanatory": "Explain your reasoning step-by-step. Be thorough and educational.",
            "formal": "Respond in a formal, professional tone.",
            "technical": "Use precise technical language. Include code examples where relevant.",
            "casual": "Respond in a friendly, casual tone. Keep it conversational.",
        }
        _style_instruction = _style_prompts.get(style or "", "")
        if _style_instruction:
            style_msg = {"role": "system", "content": f"[Style Instruction] {_style_instruction}"}
            if history is None:
                history = [style_msg]
            else:
                history = list(history) + [style_msg]
            yield _t(f"→ Style: {style}")

        if USE_LANGFUSE and langfuse:
            try:
                langfuse.update_current_span(
                    metadata={
                        "intent": intent,
                        "confidence": confidence,
                        "reasoning": reasoning[:200],
                        "owner_id": owner_id,
                    }
                )
                # Create a dedicated span for intent classification
                with langfuse.start_as_current_observation(
                    name="intent_classification",
                    as_type="span",
                    input={"user_input": user_input[:2000]},
                    output={"intent": intent, "confidence": confidence, "reasoning": reasoning[:200]},
                    metadata={
                        "model": router_inst.model_name if hasattr(router_inst, "model_name") else "semantic_router",
                        "fast_mode": _fast_mode,
                    },
                ):
                    pass
            except Exception:
                pass

        # --- JWT-ACE: Set active scope for this intent ---
        if JWT_ACE_AVAILABLE:
            intent_caps = get_capabilities_for_intent(intent)
            set_active_scope(intent_caps.get("capabilities", []))
            yield {"type": "log", "content": f"[JWT-ACE] Active scope set for {intent_caps.get('template_id', intent)} ({len(intent_caps.get('capabilities', []))} caps)"}
            # Preserve per-intent metadata for performance recording
            template_metadata.update({
                "template_id": intent_caps.get("template_id", template_metadata.get("template_id")),
                "template_version": template_metadata.get("template_version", "1.0"),
                "intent_capabilities": intent_caps.get("capabilities", []),
            })

        route_start_time = time.time()

        # --- ROUTE: VISION (Image Analysis via VLM) ---
        # Must be checked BEFORE CREATIVE_INTENTS to prevent "what do you see
        # in this image?" from being redirected to the Art Studio.
        if intent == "VISION":
            yield _emit_turn_metadata(turn_id, "Vision Analyst", ["thinking", "responding"])
            yield _emit_stream_mode("thinking")
            yield {"type": "status", "content": "👁️ Vision Analyst: Analyzing image..."}
            AGENT_STATE.labels(agent_name="VisionAnalyst").set(2)

            VISION_MODEL = "moondream:latest"
            VISION_HOST = get_best_host_for_model(VISION_MODEL)

            try:
                # Extract base64 image from attachments if present
                image_data = None
                if extracted_context:
                    # Check if extracted_context contains base64 image data
                    b64_match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', extracted_context)
                    if b64_match:
                        image_data = b64_match.group(1)
                    elif extracted_context.startswith("/9j/") or extracted_context.startswith("iVBOR"):
                        # Raw base64 without data URI prefix
                        image_data = extracted_context

                if not image_data:
                    yield {"type": "response", "content": (
                        "👁️ **Vision Analyst**\n\n"
                        "I can analyze images, but I don't see one attached to your message. "
                        "Please upload an image and ask your question again."
                    )}
                    _score_trace(lf_trace, langfuse, 0.5)
                    AGENT_STATE.labels(agent_name="VisionAnalyst").set(1)
                    return

                vlm_prompt = user_input
                if history_context:
                    vlm_prompt = f"{history_context}\n\n{vlm_prompt}"

                payload = {
                    "model": VISION_MODEL,
                    "prompt": vlm_prompt,
                    "images": [image_data],
                    "stream": False
                }

                yield _emit_stream_mode("responding")
                res = requests.post(f"{VISION_HOST}/api/generate", json=payload, timeout=120)
                if res.status_code == 200:
                    analysis = res.json().get("response", "No analysis returned.")
                    yield {"type": "response", "content": f"👁️ **Vision Analyst**\n\n{analysis}"}
                    _score_trace(lf_trace, langfuse, 0.9, output=analysis)
                else:
                    yield {"type": "error", "content": f"Vision model returned status {res.status_code}"}
                    _score_trace(lf_trace, langfuse, 0.0)

            except Exception as e:
                logger.error(f"[Vision] Analysis failed: {e}", exc_info=True)
                yield {"type": "error", "content": f"Vision analysis failed: {e}"}
                _score_trace(lf_trace, langfuse, 0.0)

            AGENT_STATE.labels(agent_name="VisionAnalyst").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="VisionAnalyst").inc()
            return

        # --- ROUTE: COORDINATE (Multi-Worker Orchestration) ---
        if intent == "COORDINATE":
            yield _emit_turn_metadata(turn_id, "Coordinator", ["thinking", "tool-use", "responding"])
            yield _emit_stream_mode("thinking")
            yield {"type": "status", "content": "🧩 Coordinator Mode: Initializing multi-worker orchestration..."}
            AGENT_STATE.labels(agent_name="Coordinator").set(2)

            try:
                from lamport import coordinate_task

                tool_call_id = f"tool-coordinator-{int(time.time()*1000)}"
                yield _emit_tool_start(tool_call_id, "coordinate_task", {"intent": "COORDINATE"})
                yield _emit_stream_mode("tool-use")

                for update in coordinate_task(
                    user_input=user_input,
                    session_id=session_id,
                    owner_id=owner_id,
                    history_context=history_context,
                    extracted_context=extracted_context,
                    ace_token=ace_token,
                    template_metadata=template_metadata,
                ):
                    yield update

                yield _emit_tool_result(tool_call_id, "coordinate_task", "Coordination complete", True)
                _score_trace(lf_trace, langfuse, 0.9)
            except Exception as e:
                logger.error(f"[Coordinator] Failed: {e}", exc_info=True)
                if 'tool_call_id' in locals():
                    yield _emit_tool_result(tool_call_id, "coordinate_task", f"Coordination failed: {e}", False)
                yield {"type": "error", "content": f"Coordination failed: {e}"}
                _score_trace(lf_trace, langfuse, 0.0)

            AGENT_STATE.labels(agent_name="Coordinator").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="Coordinator").inc()
            return

        # --- ART WORKSPACE OFFER (for creative intents) ---
        # Creative intents redirect to the Art Studio workspace instead of
        # running heavy generation pipelines inline in chat.
        CREATIVE_INTENTS = {"IMAGE", "3D", "ACTION_FIGURE"}
        if intent in CREATIVE_INTENTS:
            mode_label = {"IMAGE": "Image", "3D": "3D Model", "ACTION_FIGURE": "Action Figure"}.get(intent, intent)
            yield {
                "type": "workspace_offer",
                "content": json.dumps({
                    "intent": intent,
                    "prompt": user_input,
                    "message": f"This looks like a creative request. Switch to the Art Studio for {mode_label} generation."
                })
            }
            yield {
                "type": "response",
                "content": (
                    f"🎨 **Creative Request Detected: {mode_label}**\n\n"
                    f"Switch to the **Art Studio** workspace (sidebar) for:\n"
                    f"- Advanced generation controls & model selection\n"
                    f"- Real-time 3D preview\n"
                    f"- Gallery management & batch export\n"
                    f"- Image upload for direct 3D conversion\n\n"
                    f"Your prompt has been saved and will auto-fill when you enter the Art Studio."
                )
            }
            # Save prompt so Art Studio can pick it up
            from brooks import save_pending_context
            save_pending_context({
                "type": "art_studio_redirect",
                "intent": intent,
                "prompt": user_input
            }, session_id=session_id, owner_id=owner_id)
            AGENT_STATE.labels(agent_name="Router").set(1)
            return

        # --- ROUTE: CONVERSATION / CASUAL CHAT ---
        if intent == "CONVERSATION":
            yield _emit_turn_metadata(turn_id, "Hive Mind", ["thinking", "responding"])
            yield _emit_stream_mode("thinking")
            yield {"type": "status", "content": "💬 Hive Mind: Thinking..."}
            AGENT_STATE.labels(agent_name="Conversationalist").set(2)

            CONV_MODEL = _resolve_model_for_intent("CONVERSATION", os.getenv("CONV_MODEL", os.getenv("PRIMARY_MODEL", "qwen3:14b")))
            OLLAMA_HOST = get_best_host_for_model(CONV_MODEL)

            conversationalist = Agent(
                name="Hive Mind",
                model=Ollama(
                    id=CONV_MODEL,
                    host=OLLAMA_HOST,
                    client_kwargs={"timeout": 120.0},
                ),
                storage=_conv_storage,
                session_id=session_id,
                add_history_to_messages=True,
                num_history_responses=10,
                instructions="""You are Hive Mind, a friendly and knowledgeable AI assistant in a self-hosted home lab.
                You have a warm, direct personality. You can answer general questions, chat casually, explain concepts clearly,
                and help the user understand their AI system. Keep responses concise unless depth is clearly needed.
                You are running entirely on local hardware — no cloud dependencies.""",
                show_tool_calls=False,
            )

            full_content = ""
            try:
                with _langfuse_span("conversation_generation", "Conversationalist", CONV_MODEL, user_input) as span_result:
                    with request_lock(context="text"):
                        response_stream = conversationalist.run(user_input, stream=True)
                        for chunk in response_stream:
                            if chunk.content:
                                yield _emit_stream_mode("responding")
                                full_content += chunk.content
                                yield {"type": "message", "content": chunk.content}
                    span_result["output"] = full_content
                _score_trace(lf_trace, langfuse, 0.85, output=full_content)
            except Exception as e:
                _score_trace(lf_trace, langfuse, 0.0)
                yield {"type": "error", "content": f"Conversation failed: {e}"}

            AGENT_STATE.labels(agent_name="Conversationalist").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="Conversationalist").inc()
            return

        # --- ROUTE: DEVOPS / INFRASTRUCTURE ---
        if intent == "DEVOPS":
            yield _emit_turn_metadata(turn_id, "DevOps Engineer", ["thinking", "tool-use", "responding"])
            yield _emit_stream_mode("thinking")
            yield {"type": "status", "content": "🖥️ DevOps Engineer: Analyzing infrastructure task..."}
            AGENT_STATE.labels(agent_name="DevOps").set(2)

            DEVOPS_MODEL = _resolve_model_for_intent("DEVOPS", os.getenv("ARCHITECT_MODEL", os.getenv("PRIMARY_MODEL", "qwen3:14b")))
            OLLAMA_HOST = get_best_host_for_model(DEVOPS_MODEL)

            devops_input = f"[DEVOPS TASK] {user_input}"
            if history_context:
                devops_input = f"{history_context}\n\n{devops_input}"
                yield {"type": "log", "content": "[DevOps] Reviewed prior turns for continuity."}
            if constraint_context:
                devops_input = f"{constraint_context}\n\n{devops_input}"
                yield {"type": "log", "content": "[DevOps] Injected active user constraints."}
            if extracted_context:
                devops_input = f"{devops_input}\n\n[Attached Context]:\n{extracted_context}"

            if _fast_mode:
                # --- HIVE FAST: single-pass Ollama (no MarsRL) ---
                yield _t(f"→ Hive Fast: single-pass DevOps ({DEVOPS_MODEL})")
                devops_agent = Agent(
                    name="DevOps Engineer",
                    model=Ollama(id=DEVOPS_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 120.0}),
                    storage=_conv_storage,
                    session_id=session_id,
                    add_history_to_messages=True,
                    num_history_responses=10,
                    instructions="You are a DevOps engineer in a self-hosted home lab. Help with infrastructure, Docker, networking, and system administration tasks.",
                    show_tool_calls=False,
                )
                full_content = ""
                try:
                    with _langfuse_span("devops_fast_generation", "DevOps", DEVOPS_MODEL, devops_input) as span_result:
                        with request_lock(context="text"):
                            yield _emit_stream_mode("responding")
                            response_stream = devops_agent.run(devops_input, stream=True)
                            for chunk in response_stream:
                                if chunk.content:
                                    full_content += chunk.content
                                    yield {"type": "message", "content": chunk.content}
                        span_result["output"] = full_content
                    _score_trace(lf_trace, langfuse, 0.85, output=full_content)
                except Exception as e:
                    _score_trace(lf_trace, langfuse, 0.0)
                    yield {"type": "error", "content": f"DevOps task failed: {e}"}
            else:
                # --- HIVE MIND: full MarsRL loop ---
                solver = get_architect_agent(session_id=session_id)
                verifier = get_verifier()
                corrector = get_corrector()

                mars = MarsRLLoop(
                    solver=solver,
                    verifier=verifier,
                    corrector=corrector,
                    max_iter=2,
                    intent=intent,
                    session_id=session_id,
                    token=ace_token,
                    template_metadata=template_metadata,
                )

                yield {"type": "log", "content": f"[DevOps] Routing to MarsRL with infra context."}
                yield _t(f"→ Routing to Architect ({DEVOPS_MODEL}) via MarsRL loop")
                try:
                    tool_call_id = f"tool-devops-{int(time.time()*1000)}"
                    yield _emit_tool_start(tool_call_id, "marsrl_loop", {"intent": "DEVOPS", "model": DEVOPS_MODEL})
                    with request_lock(context="text"):
                        yield _emit_stream_mode("tool-use")
                        yield _emit_tool_progress(tool_call_id, "marsrl_loop", 25, "Initializing MarsRL loop")
                        for update in mars_loop_stream(devops_input, mars):
                            yield update
                        yield _emit_tool_progress(tool_call_id, "marsrl_loop", 100, "MarsRL loop complete")
                    yield _emit_tool_result(tool_call_id, "marsrl_loop", "DevOps plan generated", True)
                    _score_trace(lf_trace, langfuse, 0.9)
                except Exception as e:
                    yield _emit_tool_result(tool_call_id, "marsrl_loop", f"DevOps execution failed: {e}", False)
                    _score_trace(lf_trace, langfuse, 0.0)
                    raise e

            AGENT_STATE.labels(agent_name="DevOps").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="DevOps").inc()
            return

        # --- ROUTE: DATA ANALYSIS ---
        if intent == "DATA":
            yield _emit_turn_metadata(turn_id, "Data Analyst", ["thinking", "responding"])
            yield _emit_stream_mode("thinking")
            yield {"type": "status", "content": "📊 Data Analyst: Processing your data request..."}
            AGENT_STATE.labels(agent_name="DataAnalyst").set(2)

            DATA_MODEL = _resolve_model_for_intent("DATA", os.getenv("ARCHITECT_MODEL", os.getenv("PRIMARY_MODEL", "qwen3:14b")))
            OLLAMA_HOST = get_best_host_for_model(DATA_MODEL)

            data_agent = Agent(
                name="Data Analyst",
                model=Ollama(id=DATA_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 300.0}),
                instructions="""You are a Staff-Level Data Engineer and Analyst.
                Expertise: SQL, Python (pandas/numpy/polars), data pipelines, statistical analysis, and data visualization.
                For SQL queries: write clean, well-commented SQL with CTEs where appropriate.
                For Python: use pandas or polars, include sample output in comments.
                For analysis: provide clear findings with supporting logic.
                Always explain your approach before diving into code.""",
                show_tool_calls=False,
            )

            full_content = ""
            try:
                final_input = user_input
                if history_context:
                    final_input = f"{history_context}\n\n{final_input}"
                    yield {"type": "log", "content": "[DataAnalyst] Reviewed prior turns for continuity."}
                if extracted_context:
                    yield {"type": "log", "content": f"[DataAnalyst] Reading attached context ({len(extracted_context)} chars)..."}
                    final_input = f"{final_input}\n\n[Data Context]:\n{extracted_context}"

                with _langfuse_span("data_analysis_generation", "DataAnalyst", DATA_MODEL, final_input) as span_result:
                    with request_lock(context="text"):
                        response_stream = data_agent.run(final_input, stream=True)
                        yield {"type": "status", "content": "📊 Data Analyst: Generating analysis..."}
                        for chunk in response_stream:
                            if chunk.content:
                                yield _emit_stream_mode("responding")
                                full_content += chunk.content
                                yield {"type": "message", "content": chunk.content}
                    span_result["output"] = full_content
                _score_trace(lf_trace, langfuse, 0.85, output=full_content)
            except Exception as e:
                _score_trace(lf_trace, langfuse, 0.0)
                yield {"type": "error", "content": f"Data analysis failed: {e}"}

            AGENT_STATE.labels(agent_name="DataAnalyst").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="DataAnalyst").inc()
            return

        # --- AMBIGUITY CHECK ---
        if intent == "AMBIGUOUS":
             question = routing_decision.get("disambiguation_question", "Could you clarify your request?")
             
             # SAVE CONTEXT so we remember what was ambiguous
             from brooks import save_pending_context
             save_pending_context({
                 "type": "ambiguity_resolution",
                 "prompt": user_input,
                 "question": question
             }, session_id=session_id, owner_id=owner_id)
             
             yield {"type": "response", "content": f"🤔 **Ambiguous Request:** {question}"}
             _score_trace(lf_trace, langfuse, 0.7, output=question)
             AGENT_STATE.labels(agent_name="Router").set(1)
             return
        
        # --- CONSULTATIVE LAYER: ART DIRECTOR ---
        if intent == "IMAGE":
             # The user rejected fast-path: We ALWAYS consult the Art Director.
             yield {"type": "status", "content": "🎨 Art Director: Reviewing your vision..."}
             AGENT_STATE.labels(agent_name="ArtDirector").set(2)
             
             # Config — template-driven model selection with health-aware routing
             MODEL_NAME = _resolve_model_for_intent("IMAGE", os.getenv("ARCHITECT_MODEL", os.getenv("PRIMARY_MODEL", "qwen3:14b")))
             OLLAMA_HOST = get_best_host_for_model(MODEL_NAME)
             
             art_director = Agent(
                 name="Art Director",
                 model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST, client_kwargs={"timeout": 300.0}),
                 instructions="""You are the AI Art Director. Your goal is to ensure image prompts are vividly detailed.
                 
                 CRITICAL RULES:
                 1. **Check for Style**: Does the prompt specify "Photo", "Painting", "3D Render", or "Sketch"? If not, ask!
                 2. **Check for Setting**: Does the prompt specify a location? If not, ask!
                 3. **Check for Subject Detail**: "A dog" is bad. "A Golden Retriever" is okay. "A black labrador puppy" is good.
                 
                 RESPONSE FORMAT:
                 - If ANY of the above are missing/vague, return: 'CLARIFY: [Direct question asking for the missing detail]'
                 - If the prompt is fully detailed (Subject + Style + Setting), return: 'EXECUTE'
                 """,
                 show_tool_calls=False
             )
             
             try:
                 # 0. LEARNED MEMORY INJECTION
                 from memory_system import memory
                 learned_rules = memory.get_relevant_rules(user_input, "visual_rules")
                 
                 memory_context = ""
                 if learned_rules:
                     memory_context = f"\n\n[🧠 MEMORY]: The user has previously taught you:\n" + "\n".join([f"- {r}" for r in learned_rules])
                 
                 # Check specificity
                 review_prompt = f"Review this prompt: '{user_input}'{memory_context}"
                 review: RunResponse = art_director.run(review_prompt)
                 
                 if "CLARIFY:" in review.content:
                     # HITL STOP: Return the clarifying question and EXIT the generator.
                     # SAVE CONTEXT so we remember next time.
                     save_pending_image_clarification(user_input, session_id=session_id, owner_id=owner_id)
                     
                     question = review.content.replace("CLARIFY:", "").strip()
                     yield {"type": "response", "content": f"🎨 **Art Director:** {question}"}
                     _score_trace(lf_trace, langfuse, 0.7, output=question)
                     AGENT_STATE.labels(agent_name="ArtDirector").set(1)
                     return
                 
                 yield {"type": "log", "content": "[Art Director] Prompt approved for Execution."}
                 
             except Exception as e:
                 # Fallback: If AD fails, just execute.
                 logger.error(f"Art Director Failed: {e}")
                 yield {"type": "log", "content": "[Art Director] Offline. Skipping review."}
                 
             AGENT_STATE.labels(agent_name="ArtDirector").set(1)

        # --- ROUTE: DOC STANDARDS AGENT (admin-only /standardize-doc) ---
        if intent == "DOC_STANDARDS":
            yield _emit_turn_metadata(turn_id, "Doc Standards Agent", ["thinking", "responding"])
            yield _emit_stream_mode("thinking")

            # Admin gate
            if not _is_admin_session(session_id, owner_id):
                yield {"type": "error", "content": "🔒 `/standardize-doc` requires admin privileges (L3_ADMIN)."}
                _audit_security_event("doc_standards_access_denied", {
                    "session_id": session_id, "owner_id": owner_id,
                    "reason": "insufficient_security_level",
                })
                logger.warning(f"[Router] Non-admin tried /standardize-doc: {owner_id}")
                return

            yield {"type": "status", "content": "📄 Doc Standards Agent: Parsing command..."}
            AGENT_STATE.labels(agent_name="DocStandards").set(2)

            # Parse command: /standardize-doc <filepath> [--flag ...]
            import shlex
            try:
                parts = shlex.split(user_input)
            except ValueError:
                parts = user_input.split()

            # Strip the command prefix
            parts = [p for p in parts if not p.lower().startswith("/standardize")]
            filepath = parts[0] if parts else ""
            flags = parts[1:] if len(parts) > 1 else []

            if not filepath:
                # No filepath → full DocSite alignment scan
                yield {"type": "status", "content": "📄 Doc Standards Agent: No file specified — running full DocSite alignment..."}
                try:
                    from specialized.doc_standards_agent import batch_scan
                    for event in batch_scan(
                        model=model,
                        auto_fix=not dry_run,
                        full_rewrite=full_rewrite,
                    ):
                        etype = event.get("type", "")
                        econtent = event.get("content", "")
                        if etype in ("response", "message"):
                            yield _emit_stream_mode("responding")
                            yield {"type": "message", "content": econtent}
                        else:
                            yield event
                except Exception as e:
                    logger.error(f"[DocStandards] Batch scan failed: {e}", exc_info=True)
                    yield {"type": "error", "content": f"Doc Standards batch scan error: {e}"}

                AGENT_STATE.labels(agent_name="DocStandards").set(1)
                WORKFLOW_STEPS.labels(status="success", agent_type="DocStandards").inc()
                return

            full_rewrite = "--full-rewrite" in flags
            dry_run = "--dry-run" in flags
            source_ref = ""
            external_urls = []

            # Parse --source-ref value
            if "--source-ref" in flags:
                idx = flags.index("--source-ref")
                if idx + 1 < len(flags):
                    source_ref = flags[idx + 1]

            # Parse --urls values
            if "--urls" in flags:
                idx = flags.index("--urls")
                for u in flags[idx + 1:]:
                    if u.startswith("--"):
                        break
                    if u.startswith("http"):
                        external_urls.append(u)

            try:
                from specialized.doc_standards_agent import standardize_document
                for event in standardize_document(
                    filepath,
                    model=model,
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
                logger.error(f"[DocStandards] Agent failed: {e}", exc_info=True)
                yield {"type": "error", "content": f"Doc Standards Agent error: {e}"}

            AGENT_STATE.labels(agent_name="DocStandards").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="DocStandards").inc()
            return

        # --- ROUTE: DOCUMENTATION / TECHNICAL WRITING ---
        if intent == "DOCUMENTATION":
            yield _emit_turn_metadata(turn_id, "Technical Writer", ["thinking", "responding"])
            yield _emit_stream_mode("thinking")
            yield {"type": "status", "content": "📝 Technical Writer: Reviewing document structure..."}
            AGENT_STATE.labels(agent_name="TechnicalWriter").set(2)
            
            # Template-driven model selection with health-aware routing
            TECH_MODEL = _resolve_model_for_intent("DOCUMENTATION", os.getenv("ARCHITECT_MODEL", os.getenv("PRIMARY_MODEL", "qwen3:14b")))
            OLLAMA_HOST = get_best_host_for_model(TECH_MODEL)
            
            tech_writer = Agent(
                name="Technical Writer",
                model=Ollama(id=TECH_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 300.0}),
                instructions="""You are a Staff-Level Technical Writer.
                Your goal is to rewrite, format, and organize documentation into professional, polished markdown.
                If provided with large context files, synthesize the information accurately.
                Focus on clarity, tone, accurate citations, and structured formatting (headings, lists, bolding).
                """,
                show_tool_calls=False
            )
            
            try:
                final_input = user_input
                if history_context:
                    final_input = f"{history_context}\n\n{final_input}"
                    yield {"type": "log", "content": "[TechnicalWriter] Reviewed prior turns for continuity."}
                if constraint_context:
                    final_input = f"{constraint_context}\n\n{final_input}"
                    yield {"type": "log", "content": "[TechnicalWriter] Injected active user constraints."}
                
                # Context integration
                from memory_system import memory
                doc_rules = memory.get_relevant_rules(user_input, "general_rules")
                if doc_rules:
                    rule_block = "\n".join([f"- {r}" for r in doc_rules])
                    final_input = f"{final_input}\n\n[🧠 MEMORY] Apply these rules:\n{rule_block}"
                    yield {"type": "log", "content": f"[Memory] Injected {len(doc_rules)} stylistic rules."}
                    
                if extracted_context:
                    yield {"type": "log", "content": f"[TechnicalWriter] Reading Attached RAG Context ({len(extracted_context)} chars)..."}
                    final_input = f"{final_input}\n\n[Attached Document Context]:\n{extracted_context}"
                    
                with _langfuse_span("documentation_generation", "TechnicalWriter", TECH_MODEL, final_input) as span_result:
                    with request_lock(context="text"):
                        response_stream = tech_writer.run(final_input, stream=True)
                        yield {"type": "status", "content": "📝 Technical Writer: Generating document..."}
                        full_content = ""
                        for chunk in response_stream:
                            if chunk.content:
                                yield _emit_stream_mode("responding")
                                full_content += chunk.content
                                yield {"type": "message", "content": chunk.content}
                    
                        yield {"type": "log", "content": "[TechnicalWriter] Document Transformation Complete."}
                    span_result["output"] = full_content
                _score_trace(lf_trace, langfuse, 0.85, output=full_content)

            except Exception as e:
                _score_trace(lf_trace, langfuse, 0.0)
                yield {"type": "error", "content": f"Technical Writing Failed: {e}"}

            AGENT_STATE.labels(agent_name="TechnicalWriter").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="TechnicalWriter").inc()
            return

        # --- ROUTE: RESEARCH / CHAT ---
        if intent == "RESEARCH":
            yield _emit_turn_metadata(turn_id, "Librarian", ["thinking", "responding"])
            yield _emit_stream_mode("thinking")
            yield {"type": "status", "content": "📚 Librarian Agent: Accessing Archives..."}
            AGENT_STATE.labels(agent_name="Librarian").set(2)
            
            from agents.config import LIBRARIAN_MODEL

            resolved_model = _resolve_model_for_intent("RESEARCH", LIBRARIAN_MODEL)
            resolved_host = get_best_host_for_model(resolved_model)

            researcher = Agent(
                name="Librarian",
                model=Ollama(id=resolved_model, host=resolved_host),
                instructions="""You are the Hive Librarian and Scholar.
                Your goal is to provide deep historical context, literary analysis, and general knowledge.
                You are the guardian of facts and culture. Focus on: History, Literature, Philosophy, Science, and Factual Explanations.
                If the user asks for code, decline and suggest they ask the Architect.
                If the user asks for images, decline and suggest they ask the Art Director.
                """,
                show_tool_calls=False
            )
            
            try:
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
                    
                with _langfuse_span("research_generation", "Librarian", resolved_model, final_input) as span_result:
                    with request_lock(context="text"):
                        response_stream = researcher.run(final_input, stream=True)
                        yield {"type": "status", "content": "📚 Librarian Agent: Drafting response..."}
                        full_content = ""
                        for chunk in response_stream:
                            if chunk.content:
                                yield _emit_stream_mode("responding")
                                full_content += chunk.content
                                yield {"type": "message", "content": chunk.content}
                    span_result["output"] = full_content
                
                yield {"type": "log", "content": f"[Research] Completed query: {user_input}"}
                _score_trace(lf_trace, langfuse, 0.85, output=full_content)

            except Exception as e:
                _score_trace(lf_trace, langfuse, 0.0)
                yield {"type": "error", "content": f"Research Failed: {e}"}

            AGENT_STATE.labels(agent_name="Librarian").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="Librarian").inc()
            return

        # --- ROUTE: 3D GENERATION ---
        if intent == "3D":
            yield {"type": "status", "content": "🔮 Router: Detected 3D Generation Request."}
            
            # Step A: Concept Art
            yield {"type": "status", "content": "🎨 Creative Studio: Generating Concept Art..."}
            AGENT_STATE.labels(agent_name="CreativeStudio").set(2)
            
            from specialized.image_gen import generate_image
            
            concept_prompt = f"Concept art for 3d modeling, neutral background: {user_input}"
            yield {"type": "log", "content": f"[CreativeStudio] Prompt Optimized: '{concept_prompt}'"}
            
            try:
                with request_lock(context="image"):
                    img_result = generate_image(concept_prompt) 
                yield {"type": "status", "content": f"🖼️ {img_result}"}
                yield {"type": "log", "content": f"[CreativeStudio] Output: {img_result}"}
                AGENT_STATE.labels(agent_name="CreativeStudio").set(1)
                
                import re
                match = re.search(r"Generated Image: ([\w\.-]+)", img_result)
                
                if match:
                    filename = match.group(1)
                    full_image_path = f"/app/comfy_io/output/{filename}" 
                    
                    # Step B: 3D Forge
                    yield {"type": "status", "content": "⚒️ Creature Forge: Hammering Geometry..."}
                    AGENT_STATE.labels(agent_name="Forge").set(2)
                    
                    from specialized.forge_agent import generate_3d_model
                    
                    yield {"type": "log", "content": f"[Forge] Processing: {full_image_path} (High-Res Mode)"}
                    with request_lock(context="image"):
                        forge_result = generate_3d_model(full_image_path)
                    AGENT_STATE.labels(agent_name="Forge").set(1)
                    
                    # Yield 3D Artifact
                    yield {
                        "type": "artifact", 
                        "content": {
                            "type": "3d_model", 
                            "path": f"{filename}.glb", 
                            "name": f"Creature_{filename}"
                        }
                    }
                    
                    yield {"type": "response", "content": forge_result}
                    WORKFLOW_STEPS.labels(status="success", agent_type="Forge").inc()
                    return
                else:
                    yield {"type": "error", "content": f"Failed to parse image filename from: {img_result}"}
                    WORKFLOW_STEPS.labels(status="error", agent_type="CreativeStudio").inc()
                    return
            except Exception as e:
                yield {"type": "error", "content": f"Concept Generation Failed: {e}"}
                yield {"type": "log", "content": f"[Exception] {str(e)}"}
                return

        # --- ROUTE: ACTION FIGURE GENERATION ---
        if intent == "ACTION_FIGURE":
            yield {"type": "status", "content": "🦾 Router: Detected Action Figure Request."}

            # Step A: Concept Art (T-Pose optimized)
            yield {"type": "status", "content": "🎨 Action Figure Forge: Generating T-Pose Concept Art..."}
            AGENT_STATE.labels(agent_name="ActionFigureForge").set(2)

            from specialized.image_gen import generate_image

            concept_prompt = (
                f"T-pose character concept art for 3D action figure, "
                f"full body front view, neutral gray background, "
                f"arms extended to sides, symmetrical pose, "
                f"clean silhouette for 3D modeling: {user_input}"
            )
            yield {"type": "log", "content": f"[ActionFigureForge] Prompt: '{concept_prompt}'"}

            try:
                with request_lock(context="image"):
                    img_result = generate_image(concept_prompt)
                yield {"type": "status", "content": f"🖼️ {img_result}"}
                yield {"type": "log", "content": f"[ActionFigureForge] Concept Art: {img_result}"}

                import re
                match = re.search(r"Generated Image: ([\w\.-]+)", img_result)

                if match:
                    filename = match.group(1)
                    full_image_path = f"/app/comfy_io/output/{filename}"

                    # Step B: Action Figure Pipeline (3D mesh + segmentation + joints)
                    yield {"type": "status", "content": "⚒️ Action Figure Forge: Generating mesh & adding ball-socket joints..."}

                    from specialized.action_figure_agent import generate_action_figure

                    yield {"type": "log", "content": f"[ActionFigureForge] Processing: {full_image_path}"}
                    with request_lock(context="image"):
                        figure_result = generate_action_figure(full_image_path)
                    AGENT_STATE.labels(agent_name="ActionFigureForge").set(1)

                    # Yield Action Figure Artifact
                    yield {
                        "type": "artifact",
                        "content": {
                            "type": "action_figure",
                            "path": f"action_figures/",
                            "name": f"ActionFigure_{filename}"
                        }
                    }

                    yield {"type": "response", "content": figure_result}
                    WORKFLOW_STEPS.labels(status="success", agent_type="ActionFigureForge").inc()
                    return
                else:
                    yield {"type": "error", "content": f"Failed to parse image filename from: {img_result}"}
                    WORKFLOW_STEPS.labels(status="error", agent_type="ActionFigureForge").inc()
                    return
            except Exception as e:
                yield {"type": "error", "content": f"Action Figure Generation Failed: {e}"}
                yield {"type": "log", "content": f"[Exception] {str(e)}"}
                return

        # --- ROUTE: IMAGE GENERATION ---
        elif intent == "IMAGE":
            yield {"type": "status", "content": "🎨 Creative Studio: Spinning up..."}
            AGENT_STATE.labels(agent_name="CreativeStudio").set(2)
            
            from specialized.image_gen import generate_image
            yield {"type": "log", "content": f"[CreativeStudio] Generating with flux-schnell: '{user_input}'"}
            with request_lock(context="image"):
                response = generate_image(user_input)
            
            # Extraction logic for artifact delivery
            import re
            image_match = re.search(r"Generated Image: ([\w\.-]+)", response)
            if image_match:
                filename = image_match.group(1)
                delivery_dir = os.path.join(os.getcwd(), "delivered_artifacts")
                if not os.path.exists(delivery_dir):
                    os.makedirs(delivery_dir, exist_ok=True)
                    
                delivery_path = os.path.join(delivery_dir, filename)
                COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://host.docker.internal:8188")
                
                try:
                    import requests
                    url = f"{COMFYUI_HOST}/view"
                    params = {"filename": filename, "subfolder": "", "type": "output"}
                    for i in range(10):
                        r = requests.get(url, params=params, timeout=10)
                        if r.status_code == 200:
                            with open(delivery_path, 'wb') as f:
                                f.write(r.content)
                            yield {
                                "type": "artifact",
                                "content": {
                                    "type": "image",
                                    "name": filename,
                                    "path": delivery_path, 
                                    "docker_path": f"/app/comfy_io/output/{filename}" 
                                }
                            }
                            break
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"Download error: {e}")
            
            AGENT_STATE.labels(agent_name="CreativeStudio").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="CreativeStudio").inc()
            yield {"type": "response", "content": response}
            _score_trace(lf_trace, langfuse, 0.9, output=response)
            return

        # --- ROUTE: TRAINER (FEEDBACK LOOP) ---
        if intent == "TRAIN":
            yield _emit_turn_metadata(turn_id, "Memory Controller", ["thinking", "responding"])
            yield _emit_stream_mode("thinking")
            yield {"type": "status", "content": "🧠 Memory Controller: Learning new skill..."}
            from memory_system import memory
            
            domain = "general_rules" 
            keyword = "general"
            rule = user_input
            
            if "code" in user_input or "python" in user_input or "script" in user_input:
                domain = "coding_rules"
            elif "image" in user_input or "style" in user_input or "look" in user_input:
                domain = "visual_rules"
                
            import re
            match = re.search(r"(?:remember that|correction:|learn:) (.+?) (?:means|is|should be) (.+)", user_input, re.IGNORECASE)
            
            if match:
                keyword = match.group(1).strip()
                rule = match.group(2).strip()
                
            result = memory.add_rule(domain, keyword, rule)

            # Also store in MemPalace as a procedural memory
            try:
                from mempalace_client import mempalace as _mp
                _mp.store(
                    content=f"{keyword}: {rule}",
                    memory_type="procedural",
                    domain=domain.replace("_rules", ""),
                    owner_id=owner_id,
                )
            except Exception:
                pass

            yield {"type": "response", "content": f"🧠 **Learned**: {result}"}
            _score_trace(lf_trace, langfuse, 1.0, output=result)
            return

        # --- ROUTE: IOT CONTROLLER (HOME ASSISTANT) ---
        if intent == "IOT_CONTROL":
            yield _emit_turn_metadata(turn_id, "IoT Controller", ["thinking", "responding"])
            yield _emit_stream_mode("thinking")
            yield {"type": "status", "content": "🏠 IoT Controller: Connecting to Home..."}
            AGENT_STATE.labels(agent_name="IoTController").set(2)

            from specialized.iot_agent import get_iot_agent
            iot_agent = get_iot_agent()

            try:
                yield {"type": "log", "content": f"[IoT] Dispatching: '{user_input}'"}
                response: RunResponse = iot_agent.run(user_input)
                yield {"type": "response", "content": response.content}
                _score_trace(lf_trace, langfuse, 1.0, output=response.content)
            except Exception as e:
                _score_trace(lf_trace, langfuse, 0.0)
                yield {"type": "error", "content": f"IoT Error: {e}"}

            AGENT_STATE.labels(agent_name="IoTController").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="IoTController").inc()
            return

        # --- ROUTE: STANDARD ARCHITECT / CODE (MarsRL Loop or Fast Pass) ---
        # Only fall through if no specialized route handled this intent
        if intent not in ("CONVERSATION", "DEVOPS", "DATA", "AMBIGUOUS", "IMAGE",
                          "DOCUMENTATION", "RESEARCH", "3D", "ACTION_FIGURE",
                          "TRAIN", "IOT_CONTROL", "VISION", "COORDINATE"):

            ARCH_MODEL = os.getenv('ARCHITECT_MODEL', os.getenv('PRIMARY_MODEL', 'qwen3:14b'))
            OLLAMA_HOST = get_best_host_for_model(ARCH_MODEL)

            try:
                from memory_system import memory
                code_rules = memory.get_relevant_rules(user_input, "coding_rules")
                
                final_input = user_input
                if history_context:
                    final_input = f"{history_context}\n\n{final_input}"
                    yield {"type": "log", "content": "[Architect] Reviewed prior turns for continuity."}
                if constraint_context:
                    final_input = f"{constraint_context}\n\n{final_input}"
                    yield {"type": "log", "content": "[Architect] Injected active user constraints."}
                if code_rules:
                    rule_block = "\n".join([f"- {r}" for r in code_rules])
                    final_input = f"{final_input}\n\n[🧠 MEMORY] Apply these user-taught coding rules:\n{rule_block}"
                    yield {"type": "log", "content": f"[Memory] Injected {len(code_rules)} coding rules."}

                if extracted_context:
                    final_input = f"{final_input}\n\n[Attached Document Context]:\n{extracted_context}"

                if _fast_mode:
                    # --- HIVE FAST: single-pass Ollama (no MarsRL) ---
                    yield _emit_turn_metadata(turn_id, "Architect (Fast)", ["thinking", "responding"])
                    yield _emit_stream_mode("thinking")
                    yield {"type": "status", "content": "⚡ Architect (Fast): Generating..."}
                    AGENT_STATE.labels(agent_name="Architect").set(2)
                    yield _t(f"→ Hive Fast: single-pass Architect ({ARCH_MODEL})")

                    fast_agent = Agent(
                        name="Architect",
                        model=Ollama(id=ARCH_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 120.0}),
                        storage=_conv_storage,
                        session_id=session_id,
                        add_history_to_messages=True,
                        num_history_responses=10,
                        instructions="""You are the Hive Mind Architect, an expert software engineer and system designer.
Write clean, correct, production-quality code. Explain your reasoning concisely.
You run on local hardware in a self-hosted home lab.""",
                        show_tool_calls=False,
                    )
                    full_content = ""
                    with _langfuse_span("architect_fast_generation", "Architect", ARCH_MODEL, final_input) as span_result:
                        with request_lock(context="text"):
                            yield _emit_stream_mode("responding")
                            response_stream = fast_agent.run(final_input, stream=True)
                            for chunk in response_stream:
                                if chunk.content:
                                    full_content += chunk.content
                                    yield {"type": "message", "content": chunk.content}
                        span_result["output"] = full_content
                    _score_trace(lf_trace, langfuse, 0.85, output=full_content)
                else:
                    # --- HIVE MIND: full MarsRL loop ---
                    yield _emit_turn_metadata(turn_id, "Architect", ["thinking", "tool-use", "responding"])
                    yield _emit_stream_mode("thinking")
                    yield {"type": "status", "content": "🏗️ MarsRL: Solver → Verifier → Corrector..."}
                    AGENT_STATE.labels(agent_name="Architect").set(2)

                    solver = get_architect_agent(session_id=session_id)
                    verifier = get_verifier()
                    corrector = get_corrector()

                    mars = MarsRLLoop(
                        solver=solver,
                        verifier=verifier,
                        corrector=corrector,
                        max_iter=2,
                        intent=intent,
                        session_id=session_id,
                        token=ace_token,
                        template_metadata=template_metadata,
                    )

                    yield {"type": "log", "content": f"[MarsRL] Intent: {intent} | Loop initialized."}

                    yield _t(f"→ Routing to Architect ({ARCH_MODEL}) via MarsRL loop")
                    tool_call_id = f"tool-architect-{int(time.time()*1000)}"
                    yield _emit_tool_start(tool_call_id, "marsrl_loop", {"intent": intent})
                    with request_lock(context="text"):
                        yield _emit_stream_mode("tool-use")
                        yield _emit_tool_progress(tool_call_id, "marsrl_loop", 20, "Solver started")
                        for update in mars_loop_stream(final_input, mars):
                            if update.get("type") == "log" and "[MarsRL] Iterations:" in update.get("content", ""):
                                pass
                            yield update
                        yield _emit_tool_progress(tool_call_id, "marsrl_loop", 100, "Loop complete")
                    yield _emit_tool_result(tool_call_id, "marsrl_loop", "Architect response generated", True)

            except Exception as e:
                error_str = str(e)
                if 'tool_call_id' in locals():
                    yield _emit_tool_result(tool_call_id, "marsrl_loop", f"Architect loop failed: {error_str}", False)
                yield {"type": "log", "content": f"[Exception] MarsRL Crash: {error_str}"}

                package_match = re.search(r"No module named '(\w+)'", error_str) or \
                                re.search(r"custom_nodes\\(\w+)", error_str)

                if package_match:
                    missing_pkg = package_match.group(1)
                    yield {"type": "status", "content": f"🚨 Gatekeeper: Missing '{missing_pkg}'"}
                    security = get_security_agent()
                    review = security.review_dependency(missing_pkg)
                    # Allow only normalized package names (no URL/options/extras markers).
                    is_valid_pkg = bool(re.fullmatch(r"[A-Za-z0-9_\-]+", missing_pkg))
                    if review.content == "SAFE" and is_valid_pkg:
                        subprocess.check_call([sys.executable, "-m", "pip", "install", missing_pkg])
                        yield {"type": "status", "content": f"💾 Fixed: Installed '{missing_pkg}'."}
                    elif not is_valid_pkg:
                        yield {"type": "error", "content": f"🚫 Security: Blocked invalid package token '{missing_pkg}'"}
                        return
                    else:
                        yield {"type": "error", "content": f"🚫 Security: Blocked '{missing_pkg}'"}
                        return
                else:
                    raise e

            WORKFLOW_STEPS.labels(status="success", agent_type="Architect").inc()
            AGENT_STATE.labels(agent_name="Architect").set(1)

    except Exception as e:
        yield {"type": "error", "content": f"🔥 Error: {e}"}
        WORKFLOW_STEPS.labels(status="error", agent_type="Router").inc()
    finally:
        try:
            # Emit the Langfuse trace ID as turn metadata so the UI can
            # show it in the expandable Agent Trace, not in the response body.
            if USE_LANGFUSE and lf_trace:
                yield {"type": "turn_metadata", "turnMetadata": {"traceId": lf_trace}}
            yield _emit_stream_mode("requesting")
            yield _emit_continuation_hint("await_user", "Turn complete")
            yield _emit_turn_boundary(turn_id, "completed")
        except Exception:
            pass
        AGENT_STATE.labels(agent_name="Router").set(1)
        # Close Langfuse trace context and flush
        if USE_LANGFUSE and langfuse:
            try:
                # Flush collected thoughts/logs as a dedicated reasoning span
                if _trace_thoughts:
                    reasoning_text = "\n".join(
                        f"[{t.get('type','?')}] {t.get('content','')}" for t in _trace_thoughts
                    )
                    with langfuse.start_as_current_observation(
                        name="reasoning_narrative",
                        as_type="span",
                        input={"user_input": user_input[:2000]},
                        output={"reasoning": reasoning_text[:8000]},
                        metadata={
                            "step_count": len(_trace_thoughts),
                            "intent": intent if 'intent' in dir() else "UNKNOWN",
                            "model": model,
                            "fast_mode": _fast_mode if '_fast_mode' in dir() else False,
                            "elapsed_s": round(time.time() - route_start_time, 2),
                        },
                    ):
                        pass
            except Exception as e:
                logger.debug(f"[Router] Reasoning span failed: {e}")
            try:
                if _lf_ctx is not None:
                    _lf_ctx.__exit__(None, None, None)
            except Exception:
                pass
            try:
                langfuse.flush()
            except Exception:
                pass
        # Clean up JWT-ACE execution context
        if JWT_ACE_AVAILABLE:
            try:
                clear_active_scope()
                clear_current_token()
            except Exception:
                pass
        # Record performance metrics
        if template_metadata:
            latency_ms = int((time.time() - route_start_time) * 1000) if 'route_start_time' in dir() else None
            _record_performance(intent if 'intent' in dir() else "UNKNOWN", template_metadata, {
                "session_id": session_id,
                "latency_ms": latency_ms,
            })
        # Record A/B test result if applicable
        if AB_TESTING_AVAILABLE and template_metadata.get("template_id"):
            try:
                ab_mgr = get_ab_manager()
                # Use final_score from performance if available, else default
                ab_score = template_metadata.get("final_score", 0.0)
                model_used = template_metadata.get("model_used")
                if model_used and ab_score:
                    ab_mgr.record_result(
                        template_id=template_metadata["template_id"],
                        model_used=model_used,
                        score=ab_score,
                        latency_ms=latency_ms,
                    )
            except Exception:
                pass

def run_swarm(user_input: str):
    """CLI Wrapper for chat_swarm"""
    print(f"--- [Swarm] Receiving Task: {user_input} ---")
    for update in chat_swarm(user_input, session_id="cli_session"):
        print(f"[{update['type'].upper()}] {update['content']}")

if __name__ == "__main__":
    run_swarm("Write a Python script to calculate the Fibonacci sequence.")
