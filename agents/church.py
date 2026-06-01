"""
church.py — Router thin wrapper.

All intent handlers live in agents/handlers/<name>.py.
Pending-context dispatch lives in agents/routing/gates.py.

Public API preserved:
  handle_task_event(event)
  chat_swarm(user_input, ...)
  get_best_host_for_model(model)  — re-exported from gpu_queue
  run_swarm(user_input)
"""

from phi.agent import Agent, RunResponse
from phi.model.ollama import Ollama
from leibniz_agent import get_architect_agent
from security_agent import get_security_agent

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
from pathlib import Path
from dispatcher import Event, EventType
from logger_setup import setup_logger
from utils.gpu_queue import request_lock, get_best_host_for_model
from phi.storage.agent.postgres import PgAgentStorage
from role_model_resolver import get_model_for_role
from config import (
    AGNO_DB_URL, PLANNING_MAX_ITER, PLANNING_MAX_TIME,
    ARCHITECT_MODEL, COORDINATOR_MODEL, CODER_MODEL, DEVOPS_MODEL,
    RESEARCHER_MODEL, ANALYST_MODEL, VERIFIER_MODEL, get_ollama_options
)

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

# --- Langfuse Tracing ---
try:
    from langfuse import Langfuse, observe

    langfuse = Langfuse(
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-dev"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-dev"),
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3001"),
    )
    USE_LANGFUSE = True
    logger.info("[Router] Langfuse tracing enabled")
except ImportError:
    USE_LANGFUSE = False
    observe = lambda *args, **kwargs: lambda f: f
    logger.warning("[Router] Langfuse not available, tracing disabled")


# ---------------------------------------------------------------------------
# Template / A/B model resolution
# ---------------------------------------------------------------------------

def _resolve_model_for_intent(intent: str, fallback_model: str) -> str:
    """Look up the default model from the ExpertiseTemplate registry for a given intent."""
    if not TEMPLATES_AVAILABLE:
        return fallback_model
    try:
        registry = get_template_registry()
        templates = registry.list_templates(intent=intent)
        if templates and templates[0].default_model:
            resolved = templates[0].default_model
            template_id = templates[0].id
            logger.debug(f"[Router] Template resolved model for {intent}: {resolved}")
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


# ---------------------------------------------------------------------------
# JWT-ACE helpers
# ---------------------------------------------------------------------------

@observe(name="handle_task_event")
def handle_task_event(event: Event):
    """Callback for Dispatcher. Unwraps event and runs the swarm."""
    print(f"DEBUG ROUTER: handle_task_event called with payload keys: {event.payload.keys()}")
    user_input = event.payload.get("task")
    intent = event.payload.get("intent", "DEFAULT")
    target_device = event.payload.get("target_device", "auto")
    session_id = event.payload.get("session_id", "default_session")
    owner_id = event.payload.get("owner_id")

    if not user_input:
        return

    if USE_LANGFUSE and langfuse:
        try:
            langfuse.update_current_span(metadata={
                "intent": intent, "target_device": target_device,
                "session_id": session_id, "owner_id": owner_id,
            })
        except Exception as e:
            logger.warning(f"[Router] Trace update failed: {e}")

    logger.info(f"--- [Router] Processing Async Event: {user_input} (Intent: {intent}) ---")

    try:
        if intent == "VISION":
            image_data = event.payload.get("image_data")
            if not image_data:
                logger.info("[Vision] No image data attached to async task — skipping VLM call")
                from teams import get_orchestrator
                orchestrator = get_orchestrator()
                response = orchestrator.run(user_input)
                logger.info(f"[Orchestrator] Final Response: {response.content}")
            else:
                vision_host = get_best_host_for_model("moondream:latest")
                payload = {"model": "moondream:latest", "prompt": user_input, "images": [image_data], "stream": False}
                res = requests.post(f"{vision_host}/api/generate", json=payload, timeout=120)
                if res.status_code == 200:
                    logger.info(f"[Vision] Analysis: {res.json().get('response', 'No analysis returned.')}")
                else:
                    logger.error(f"[Vision] VLM returned status {res.status_code}")

        elif intent == "3D":
            from specialized.image_gen import generate_image
            logger.info("[Router] Routing to 3D Pipeline (starting with concept art)...")
            with request_lock(context="image"):
                response = generate_image(f"Concept art for 3d modeling: {user_input}", target_device=target_device)
            logger.info(f"[3D] Concept Art Result: {response}")

        elif intent == "COORDINATE":
            from lamport import coordinate_task
            logger.info(f"[Router] Routing to Lamport Mode (async path)")
            for update in coordinate_task(user_input=user_input, session_id=session_id, owner_id=owner_id, ultraplan_mode=False):
                if update.get("type") == "response":
                    logger.info(f"[Coordinator] Final: {update['content'][:200]}")
                elif update.get("type") == "error":
                    logger.error(f"[Coordinator] Error: {update['content']}")

        else:
            from teams import get_orchestrator
            orchestrator = get_orchestrator()
            response = orchestrator.run(user_input)
            logger.info(f"[Orchestrator] Final Response: {response.content}")

    except Exception as e:
        logger.error(f"Task Execution Failed: {e}")

    AGENT_STATE.labels(agent_name="Router").set(1)


def _issue_ephemeral_token(intent: str, session_id: str, owner_id=None) -> tuple:
    """Issue a JWT-ACE token for the given intent. Returns (token_str, metadata) or (None, {})."""
    if not JWT_ACE_AVAILABLE:
        return None, {}
    try:
        caps = get_capabilities_for_intent(intent)
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
        logger.info(f"[JWT-ACE] Token issued for {caps['agent_name']} (template: {caps['template_id']} v{template_version})")
        return token, metadata
    except Exception as e:
        logger.warning(f"[JWT-ACE] Token issuance failed (non-fatal): {e}")
        return None, {}


def _issue_session_card(session_id: str, owner_id=None) -> tuple:
    """Issue a session-level JWT-ACE card. Returns (token_str, card, metadata) or (None, None, {})."""
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
        logger.info(f"[JWT-ACE] Session card issued for {session_id} ({len(session_caps['capabilities'])} capabilities)")
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


# ---------------------------------------------------------------------------
# Security / session helpers
# ---------------------------------------------------------------------------

def _score_trace(lf_trace, langfuse_inst, score: float, output: str = None):
    """Score the current Langfuse trace. Delegates to handlers.base for the real impl."""
    from handlers.base import _score_trace as _base_score
    _base_score(lf_trace, langfuse_inst, score, output=output, use_langfuse=USE_LANGFUSE)


from contextlib import contextmanager

@contextmanager
def _langfuse_span(name: str, agent_name: str, model_id: str, input_text: str):
    """Langfuse generation span. Delegates to handlers.base."""
    from handlers.base import _langfuse_span as _base_span
    with _base_span(name, agent_name, model_id, input_text, langfuse=langfuse, use_langfuse=USE_LANGFUSE) as result:
        yield result


def _is_explicit_train_request(text: str) -> bool:
    """Return True only for clear, intentional memory-training instructions."""
    if not text:
        return False
    normalized = text.strip().lower()
    explicit_prefixes = ("learn:", "correction:", "remember that", "remember this rule", "store this rule", "add rule")
    if normalized.startswith(explicit_prefixes):
        return True
    return bool(re.search(
        r"(?:remember that|correction:|learn:)\s+(.+?)\s+(?:means|is|should be)\s+(.+)",
        text, re.IGNORECASE,
    ))


def _extract_constraint_context(history: list | None, user_input: str) -> str:
    """Extract important user constraints from prior turns for requirement continuity."""
    if not history:
        return ""
    keywords = (
        "constraint", "must", "avoid", "maintenance window", "no-downtime", "no downtime",
        "requirement", "succinct", "brief", "concise", "short", "quick",
        "simple list", "just list", "keep it short", "don't elaborate",
    )
    constraints = []
    brevity_count = 0
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
            if any(brev in lowered for brev in ("succinct", "brief", "concise", "short", "quick", "simple list")):
                brevity_count += 1
    if not constraints:
        return ""
    recent = constraints[-3:]
    block = "\n".join([f"- {c}" for c in recent])
    if brevity_count >= 2:
        block += "\n- CRITICAL: User has requested brevity MULTIPLE times. Provide ONLY a concise bulleted list. NO explanations, NO elaboration, NO project plans."
    return f"[Active User Constraints - Must Respect]\n{block}\nDo not ignore these constraints in the final answer."


def _is_admin_session(session_id: str, owner_id=None) -> bool:
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
        ranks = {"L1_PUBLIC": 1, "L2_USER": 2, "L3_ADMIN": 3, "L4_SYSTEM": 4}
        return ranks.get(level, 0) >= ranks["L3_ADMIN"]
    except Exception:
        pass
    return False


def _is_anthropic_model(model_name: str) -> bool:
    return model_name in ADMIN_ONLY_MODELS or model_name.startswith("claude-")


def _audit_security_event(event_type: str, context: dict) -> None:
    payload = {"event_type": event_type, "component": "router", "source": "chat_swarm", **context}
    security_audit_logger.warning(json.dumps(payload, ensure_ascii=True))


# ---------------------------------------------------------------------------
# chat_swarm — main dispatch generator
# ---------------------------------------------------------------------------

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
    dev_mode: bool = False,
    design_mode: bool = False,
    workshop_mode: bool = False,
    solving_max_iter: int | None = None,
    solving_max_time: int | None = None,
    solving_solver_n_drafts: int | None = None,
    solving_solver_max_time: int | None = None,
    solving_verifier_n_runs: int | None = None,
    solving_verifier_max_time: int | None = None,
    solving_corrector_n_passes: int | None = None,
    solving_corrector_max_time: int | None = None,
):
    """Generator: yield status/message/error events for the UI."""
    AGENT_STATE.labels(agent_name="Router").set(2)
    WORKFLOW_STEPS.labels(status="started", agent_type="Router").inc()
    logger.info("--- [Router] chat_swarm v5.0 (modular handlers) ---")

    # State that the finally block always needs
    ace_token = None
    ace_card = None
    template_metadata = {}
    route_start_time = time.time()
    lf_trace = None
    turn_id = f"{session_id}-{int(time.time()*1000)}"
    uid = owner_id
    _trace_thoughts = []

    def _t(content: str) -> dict:
        _trace_thoughts.append({"type": "thought", "content": content, "ts": time.time()})
        return {"type": "thought", "content": content}

    def _l(content: str) -> dict:
        _trace_thoughts.append({"type": "log", "content": content, "ts": time.time()})
        return {"type": "log", "content": content}

    # Langfuse top-level trace
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

    # JWT-ACE session card
    if JWT_ACE_AVAILABLE:
        ace_token, ace_card, template_metadata = _issue_session_card(session_id, owner_id)
        if ace_token:
            set_current_token(ace_token)
            yield {"type": "log", "content": f"[JWT-ACE] Session card issued ({template_metadata.get('template_id', 'session_agent')})"}

    # History → history_context string
    history_context = ""
    if history:
        history_context = "\n\n[Previous Conversation History]:\n"
        for msg in history:
            role = msg.get("role", "user") if isinstance(msg, dict) else getattr(msg, "role", "user")
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            history_context += f"- {role.upper()}: {content}\n"

    # RAG context interception
    extracted_context = ""
    context_match = re.search(r'<context>.*?</context>', user_input, re.DOTALL)
    if context_match:
        extracted_context = context_match.group(0)
        user_input = re.sub(r'### Task:.*?<context>.*?</context>\s*', '', user_input, flags=re.DOTALL).strip()
        yield _l(f"[Router] Intercepted RAG Context ({len(extracted_context)} chars).")

    # Attachment bridge — promote attachments into extracted_context so every
    # handler that reads ctx["extracted_context"] can reach them.
    #
    # Rules:
    #   image/*  → appended as data-URI (handle_vision picks the first one;
    #              design/other handlers see the placeholder text after stripping)
    #   text/*/json/pdf → base64-decoded and appended as labelled text block
    #   Multiple attachments are APPENDED, not overwritten.
    if attachments:
        import base64 as _b64
        image_count = 0
        for att in attachments:
            mime = att.get("mimeType", "")
            data = att.get("data", "")
            name = att.get("name", "file")
            if not data:
                continue
            if mime.startswith("image/"):
                # First image goes at the top of extracted_context (handle_vision
                # uses the first data-URI it finds); subsequent images are appended.
                image_uri = f"data:{mime};base64,{data}"
                if image_count == 0 and not extracted_context:
                    extracted_context = image_uri
                else:
                    extracted_context = (extracted_context + "\n" + image_uri).strip()
                image_count += 1
                yield _l(f"[Router] Image attachment #{image_count} promoted to context: {name} ({mime})")
            else:
                try:
                    decoded = _b64.b64decode(data).decode("utf-8", errors="replace")
                    extracted_context += f"\n\n[Attached file: {name}]\n{decoded[:12000]}"
                    yield _l(f"[Router] Text attachment injected: {name} ({len(decoded)} chars)")
                except Exception as _ae:
                    yield _l(f"[Router] Could not decode attachment {name}: {_ae}")

    # ---------------------------------------------------------------------------
    # Pending context dispatch
    # ---------------------------------------------------------------------------
    from brooks import get_pending_context, clear_context, save_pending_image_clarification
    pending_ctx = get_pending_context(session_id=session_id, owner_id=owner_id)

    if pending_ctx:
        from routing.gates import handle_pending_context
        _pending_result = {"handled": False, "user_input": user_input}
        yield from handle_pending_context(
            pending_ctx, user_input,
            session_id=session_id,
            owner_id=owner_id,
            history=history,
            extracted_context=extracted_context,
            ace_token=ace_token,
            ultraplan_mode=ultraplan_mode,
            dev_mode=dev_mode,
            result=_pending_result,
        )
        if _pending_result["handled"]:
            return
        user_input = _pending_result["user_input"]
        # Carry the already_steered flag forward so coordinate_task skips the
        # nuance gate on the re-entry after a swarm steering answer.
        _already_steered = _pending_result.get("already_steered", False)

    try:
        from handlers.base import _emit_turn_metadata, _emit_stream_mode, _emit_turn_boundary, _emit_continuation_hint

        yield _emit_turn_metadata(turn_id, "Router", ["thinking"])
        yield _emit_stream_mode("thinking")

        # Memory recall
        if memory_enabled:
            try:
                from memory_system import memory as _mem
                recent = _mem.get_recent_summaries(n=5, owner_id=owner_id)
                if recent:
                    recall_text = "\n".join(f"- [{s.get('date', '?')}] {s.get('topic', '')}: {s.get('summary', '')}" for s in recent)
                    recall_msg = {"role": "system", "content": f"[Prior Session Context]\n{recall_text}"}
                    history = [recall_msg] + list(history) if history else [recall_msg]
                    yield _t(f"→ Memory: Recalled {len(recent)} prior session summaries")
            except Exception as _mem_err:
                logger.debug(f"[Router] Memory recall failed (non-fatal): {_mem_err}")

        # MemPalace semantic recall
        if memory_enabled:
            try:
                import httpx as _httpx_recall
                _mp_url = os.getenv("MEMPALACE_API_URL", "http://192.168.2.102:8200")
                with _httpx_recall.Client(timeout=3.0) as _mp_client:  # was 10 s; keep pre-routing fast
                    _mp_resp = _mp_client.post(f"{_mp_url}/v1/memories/search", json={"query": user_input, "owner_id": owner_id, "limit": 5})
                if _mp_resp.status_code == 200:
                    strong = [m for m in _mp_resp.json() if (m.get("score") or 0) > 0.5]
                    if strong:
                        mp_msg = {"role": "system", "content": f"[Relevant Memories]\n" + "\n".join(f"- {m['content']}" for m in strong)}
                        history = list(history) + [mp_msg] if history else [mp_msg]
                        yield _t(f"→ MemPalace: {len(strong)} relevant memories recalled")
            except Exception as _mp_err:
                logger.debug(f"[Router] MemPalace recall failed (non-fatal): {_mp_err}")

        # Web grounding — each snippet is trust-scanned inside web_browser.web_search()
        # before it is returned, so no additional scan is needed here.
        if grounding_web:
            try:
                from grounding_permissions import grounding_permissions as _gp
                from handlers.base import _needs_web_grounding
                if _gp.is_permitted(owner_id or "", "web_grounding"):
                    if _needs_web_grounding(user_input):
                        from tools.web_browser import web_search as _web_search
                        yield {"type": "status", "content": "🌐 Web Grounding: Searching..."}
                        results = _web_search(user_input, num_results=5)
                        if results:
                            snippets = "\n".join(f"[{i+1}] {r.get('title','')}\n{r.get('url','')}\n{r.get('snippet','')}" for i, r in enumerate(results))
                            history = list(history or []) + [{"role": "system", "content": f"[Web Grounding Context]\n{snippets}"}]
                            web_ctx = snippets
                            extracted_context = (extracted_context + f"\n\n[Web Grounding Results]\n{web_ctx}") if extracted_context else f"[Web Grounding Results]\n{web_ctx}"
                            yield _t(f"→ Web grounding: {len(results)} results injected")
                        else:
                            yield _t("→ Web grounding: no results returned")
                    else:
                        yield _t("→ Web grounding: skipped (query does not need live data)")
                else:
                    yield {"type": "status", "content": "⚠️ Web grounding not permitted — submit a governance request."}
            except Exception as _wg_err:
                logger.error("[Router] Web grounding failed (non-fatal): %s", _wg_err)

        # Doc grounding
        if grounding_docs:
            try:
                from grounding_permissions import grounding_permissions as _gp
                from handlers.base import _retrieve_doc_context
                if _gp.is_permitted(owner_id or "", "docs_grounding"):
                    chunks = _retrieve_doc_context(user_input, owner_id, limit=5)
                    if chunks:
                        # Scan each retrieved chunk for prompt injection / poisoning before injecting
                        # into the prompt. INGESTED trust = scan once, then cache by content hash so
                        # the same chunk is not re-scanned on subsequent retrievals.
                        try:
                            from utils.content_trust import sanitize_external_content, TrustLevel as _TL
                            _safe: list[dict] = []
                            for _c in chunks:
                                _raw = _c.get("content", "")
                                _clean, _ok = sanitize_external_content(
                                    _raw, _TL.INGESTED, source=f"doc:{_c.get('source', 'unknown')}"
                                )
                                if not _ok:
                                    logger.warning(
                                        "[Router] Doc chunk from %r redacted by trust scanner",
                                        _c.get("source"),
                                    )
                                _safe.append({**_c, "content": _clean})
                            chunks = _safe
                        except Exception as _ct_err:
                            logger.warning("[Router] Doc trust scan unavailable (non-fatal): %s", _ct_err)
                        doc_text = "\n\n".join(f"[Source: {c.get('source','unknown')}]\n{c.get('content','')}" for c in chunks)
                        history = list(history or []) + [{"role": "system", "content": f"[Document Context]\n{doc_text}"}]
                        yield _t(f"→ Doc grounding: {len(chunks)} chunks injected")
                    else:
                        yield _t("→ Doc grounding: no relevant chunks found")
                else:
                    yield {"type": "status", "content": "⚠️ Document grounding not permitted — submit a governance request."}
            except Exception as _dg_err:
                logger.error("[Router] Doc grounding failed (non-fatal): %s", _dg_err)

        # File grounding
        if grounding_file:
            try:
                from grounding_permissions import grounding_permissions as _gp
                if _gp.is_permitted(owner_id or "", "file_grounding"):
                    _workspace_root = os.environ.get("WORKSPACE_PATH", "/workspace")
                    yield {"type": "status", "content": "📁 File Grounding: Scanning workspace..."}
                    _query_words = set(user_input.lower().split())
                    _file_snippets: list[str] = []
                    try:
                        for _root, _dirs, _files in os.walk(_workspace_root):
                            _dirs[:] = [d for d in _dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".git", ".venv", "venv")]
                            for _fname in _files:
                                if not _fname.endswith((".py", ".md", ".txt", ".json", ".yaml", ".yml", ".sh", ".env")):
                                    continue
                                _fpath = os.path.join(_root, _fname)
                                _rel = os.path.relpath(_fpath, _workspace_root)
                                _path_words = set(_rel.lower().replace("/", " ").replace("_", " ").replace("-", " ").split())
                                if not _query_words.intersection(_path_words):
                                    continue
                                try:
                                    with open(_fpath, "r", encoding="utf-8", errors="ignore") as _fh:
                                        _content = _fh.read(2000)
                                    # Fast regex scan — workspace files are user-owned but could
                                    # contain crafted injection payloads (e.g. a poisoned config).
                                    # No GPU call; just drop the file if the pattern fires.
                                    try:
                                        from utils.content_trust import fast_injection_scan as _fis
                                        if _fis(_content):
                                            logger.warning(
                                                "[Router] Injection pattern in workspace file %r — skipping",
                                                _rel,
                                            )
                                            continue
                                    except Exception:
                                        pass
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
                        history = list(history or []) + [{"role": "system", "content": "[File Context]\n" + "\n\n".join(_file_snippets)}]
                        yield _t(f"→ File grounding: {len(_file_snippets)} file(s) injected")
                    else:
                        yield _t("→ File grounding: no matching files found")
                else:
                    yield {"type": "status", "content": "⚠️ File grounding not permitted — submit a governance request."}
            except Exception as _fg_err:
                logger.error("[Router] File grounding failed (non-fatal): %s", _fg_err)

        # Security scan
        yield {"type": "status", "content": "🔒 Security Agent: Scanning input..."}
        security = get_security_agent()
        AGENT_STATE.labels(agent_name="Security").set(2)
        security_check: RunResponse = security.run(f"Validate this user command for safety: {user_input}")
        yield {"type": "log", "content": f"[Security Analysis] Algo: Llama-Guard | Output: {security_check.content}"}
        AGENT_STATE.labels(agent_name="Security").set(1)
        if "UNSAFE" in security_check.content.upper():
            yield {"type": "error", "content": f"🚫 BLOCKED: {security_check.content}"}
            WORKFLOW_STEPS.labels(status="blocked", agent_type="Security").inc()
            return
        yield {"type": "status", "content": "✅ Security Agent: Input Cleared."}
        yield _t("→ Security: PASS")
        WORKFLOW_STEPS.labels(status="success", agent_type="Security").inc()

        # Anthropic fast-path
        if model and _is_anthropic_model(model):
            _user_anthropic_key: str | None = None
            if owner_id:
                try:
                    from provider_keys import get_key as _get_provider_key
                    _key_record = _get_provider_key(owner_id, "anthropic")
                    if _key_record:
                        _user_anthropic_key = _key_record.get_api_key()
                except Exception as _pk_err:
                    logger.warning(f"[Router] Could not fetch user Anthropic key: {_pk_err}")

            _use_admin_key = not _user_anthropic_key and _is_admin_session(session_id, owner_id) and ANTHROPIC_ENABLED
            _resolved_key = _user_anthropic_key or (ANTHROPIC_API_KEY if _use_admin_key else None)
            _key_source = "user-stored" if _user_anthropic_key else "admin-env"

            if not _resolved_key:
                yield {"type": "error", "content": "🔑 No Anthropic API key found. Add your key in **Settings → Provider API Keys** to use Claude models."}
                model = None
            else:
                yield {"type": "status", "content": f"☁️ Claude ({model}): Generating..."}
                yield _t(f"→ Provider: Anthropic ({model}) [{_key_source}]")
                try:
                    provider = AnthropicProvider(api_key=_resolved_key, model=model)
                    api_messages = [{"role": "user", "content": user_input}]
                    if history:
                        api_messages = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in history]
                        api_messages.append({"role": "user", "content": user_input})
                    for chunk in provider.generate_stream(prompt=user_input, messages=api_messages, system="You are Hive Mind, a helpful AI assistant in a self-hosted home lab."):
                        yield chunk.as_dict()
                    _score_trace(lf_trace, langfuse, 0.9, output="[anthropic stream]")
                    WORKFLOW_STEPS.labels(status="success", agent_type="Anthropic").inc()
                except Exception as e:
                    logger.error(f"[Router] Anthropic provider error ({_key_source}): {e}")
                    yield {"type": "error", "content": f"Claude API error: {e}"}
                    _score_trace(lf_trace, langfuse, 0.0)
                finally:
                    AGENT_STATE.labels(agent_name="Router").set(1)
                return

        # ---------------------------------------------------------------------------
        # Slash command dispatch
        # Fires BEFORE the routing block so it skips the LLM router entirely.
        # Each command strips its own prefix so handlers receive only the payload.
        # ---------------------------------------------------------------------------
        _sc = user_input.strip()
        _scl = _sc.lower()
        _research_slash = False  # sentinel: /research explicitly requested
        _SLASH_TABLE = [
            # (prefix,       mode_flag,      extra)
            ("/workshop",   "workshop_mode",   None),
            ("/grill",      "workshop_mode",   None),
            ("/design",     "design_mode",     None),
            ("/build",      "swarm_mode",      None),
            ("/swarm",      "swarm_mode",      None),
            ("/plan",       "swarm_mode",      "ultraplan"),
            ("/research",   None,              "research"),
            ("/think",      None,              "think"),
        ]
        for _sc_cmd, _sc_flag, _sc_extra in _SLASH_TABLE:
            if _scl.startswith(_sc_cmd + " ") or _scl == _sc_cmd:
                user_input = _sc[len(_sc_cmd):].strip()
                if _sc_flag == "workshop_mode":  workshop_mode    = True
                elif _sc_flag == "design_mode":  design_mode      = True
                elif _sc_flag == "swarm_mode":   swarm_mode       = True
                if _sc_extra == "ultraplan":     ultraplan_mode   = True
                if _sc_extra == "think":         ultrathink_mode  = True
                if _sc_extra == "research":      _research_slash  = True; research_mode = True
                break

        # ---------------------------------------------------------------------------
        # Intent routing
        # ---------------------------------------------------------------------------
        if swarm_mode:
            # Fast keyword scan to protect media intents without a full LLM router call.
            # The full route() call (tier-4 LLM) can take 5–30 s when qwen3:8b is cold
            # (evicted from VRAM by a prior 30B inference).  We use two sub-millisecond
            # tiers instead:
            #   1. fast_classify()  — existing regex rules (VISION / ACTION_FIGURE / IOT / TRAIN)
            #   2. Inline regex     — IMAGE / 3D / DESIGN / CREATIVE (not in fast_classify)
            # If neither tier fires, go straight to COORDINATE — no Ollama call.
            import re as _re_sw
            _SWARM_MEDIA_RE = _re_sw.compile(
                r"\b(generate|create|draw|paint|render|make)\b.{0,50}"
                r"\b(image|photo|picture|illustration|artwork|poster)\b"
                r"|\b(3d model|3d print|mesh|glb|obj|blender|sculpt)\b"
                r"|\b(landing page|saas landing|pitch deck|slide deck|html prototype"
                r"|dashboard design|mobile ui|wireframe|mockup|ui design|ux design)\b"
                r"|\b(write|compose)\b.{0,30}\b(story|poem|fiction|roleplay|narrative|lore)\b",
                _re_sw.I,
            )
            _SWARM_MEDIA_INTENT_MAP = {
                "draw": "IMAGE", "paint": "IMAGE", "generate": "IMAGE",
                "3d model": "3D", "3d print": "3D", "mesh": "3D", "glb": "3D",
                "landing page": "DESIGN", "pitch deck": "DESIGN", "slide deck": "DESIGN",
                "write": "CREATIVE", "compose": "CREATIVE",
            }
            from semantic_router import get_semantic_router
            _pre_router = get_semantic_router()
            # Tier 1: existing fast_classify regex rules
            _fast_pre = _pre_router.fast_classify(user_input)
            _pre_intent = (_fast_pre or {}).get("intent", "")
            _pre_conf = (_fast_pre or {}).get("confidence", 0.90)
            # Tier 2: inline media regex (IMAGE / 3D / DESIGN / CREATIVE)
            if not _pre_intent:
                _m = _SWARM_MEDIA_RE.search(user_input)
                if _m:
                    _matched = _m.group(0).lower()
                    _pre_intent = next(
                        (v for k, v in _SWARM_MEDIA_INTENT_MAP.items() if k in _matched),
                        "DESIGN",  # conservative fallback if regex matched but key not found
                    )
                    _pre_conf = 0.88
            if _pre_intent in ("IMAGE", "3D", "ACTION_FIGURE", "DESIGN", "TRAIN", "CREATIVE", "VISION"):
                intent = _pre_intent
                confidence = _pre_conf
                reasoning = f"swarm_mode override exempted: {_pre_intent} (fast-path)"
            else:
                intent = "COORDINATE"
                confidence = 1.0
                reasoning = "swarm_mode=True bypasses neural router"
                yield {"type": "status", "content": "🧩 Swarm Mode: Routing directly to multi-agent coordinator..."}
        elif workshop_mode:
            intent = "WORKSHOP"
            confidence = 1.0
            reasoning = "workshop_mode=True bypasses neural router"
            yield {"type": "status", "content": "🎯 Workshop: Starting discovery session..."}
        elif design_mode:
            intent = "DESIGN"
            confidence = 1.0
            reasoning = "design_mode=True bypasses neural router"
            yield {"type": "status", "content": "🎨 Design Studio: Activating..."}
        elif _research_slash:
            intent = "RESEARCH"
            confidence = 1.0
            reasoning = "Slash command: /research bypasses neural router"
            yield {"type": "status", "content": "🔬 Research Mode: Activating..."}
        else:
            from semantic_router import get_semantic_router
            yield {"type": "status", "content": "🧠 Neural Cortex: Analyzing intent..."}
            router_inst = get_semantic_router()
            routing_decision = router_inst.route(user_input)
            intent = routing_decision.get("intent", "RESEARCH")
            confidence = routing_decision.get("confidence", 0.0)
            reasoning = routing_decision.get("reasoning", "No reasoning provided.")

        routing_decision = locals().get("routing_decision", {})
        constraint_context = _extract_constraint_context(history, user_input)

        # Keyword overrides — kept minimal; only genuinely unambiguous signals
        _lower = user_input.lower()

        # Workshop session continuation — auto-route Phase-2 replies
        if intent not in ("WORKSHOP", "IMAGE", "3D", "ACTION_FIGURE", "DESIGN", "TRAIN", "RESEARCH") and history_context:
            _WORKSHOP_SENTINELS = (
                "Answer any or all of these and I'll draft your Product Brief.",
                "▶️ Design Mode Prompt",
            )
            if any(s in history_context for s in _WORKSHOP_SENTINELS):
                intent = "WORKSHOP"; confidence = 0.92; reasoning = "Workshop session continuation (history)"

        if _is_explicit_train_request(user_input) and intent != "TRAIN":
            intent = "TRAIN"; confidence = 0.98; reasoning = "Keyword override: explicit training directive"
        if any(kw in _lower for kw in ["action figure", "posable", "ball joint", "figurine", "poseable"]):
            intent = "ACTION_FIGURE"; confidence = 0.95; reasoning = "Keyword override: action figure keywords"
        _design_keywords = ["landing page", "saas landing", "mockup", "wireframe", "prototype", "ui design", "ux design", "pitch deck", "slide deck", "presentation deck", "html slideshow", "dashboard design", "mobile app design", "mobile ui", "web prototype", "html prototype"]
        if any(kw in _lower for kw in _design_keywords) and intent not in ("IMAGE", "ACTION_FIGURE"):
            intent = "DESIGN"; confidence = 0.95; reasoning = "Keyword override: design/UI keywords"
        if _lower.strip().startswith("/standardize-doc"):
            intent = "DOC_STANDARDS"; confidence = 1.0; reasoning = "Slash command: /standardize-doc"
        if intent == "CODE":
            intent = "COORDINATE"; confidence = max(confidence, 0.88); reasoning = "CODE promoted to COORDINATE"

        yield _l(f"[Router] Intent: {intent} ({confidence * 100:.1f}%) | Reason: {reasoning}")
        logger.info(f"--- [Router] Neural Decision: {intent} (Conf: {confidence}) ---")

        if intent == "TRAIN" and not _is_explicit_train_request(user_input):
            logger.info("[Router] TRAIN intent downgraded to CONVERSATION (missing explicit training directive).")
            yield {"type": "log", "content": "[Router] TRAIN intent downgraded to CONVERSATION."}
            intent = "CONVERSATION"; confidence = max(confidence, 0.75)

        yield _t(f"→ Intent: {intent} ({confidence * 100:.0f}% confidence)")

        # ---------------------------------------------------------------------------
        # Confidence gate — when the router isn't sure, ask rather than guess wrong.
        # Intents exempt: CONVERSATION and TRAIN are low-risk guesses; VISION and
        # ACTION_FIGURE fast-paths are highly specific; DOC_STANDARDS is a slash cmd.
        # ---------------------------------------------------------------------------
        _CONFIDENCE_GATE = 0.80
        _GATE_EXEMPT = frozenset({
            "CONVERSATION", "TRAIN", "VISION", "ACTION_FIGURE", "DOC_STANDARDS", "AMBIGUOUS",
        })
        if confidence < _CONFIDENCE_GATE and intent not in _GATE_EXEMPT:
            _disam_q = (
                routing_decision.get("disambiguation_question")
                or f"I want to make sure I handle this correctly — what would you like me to do?"
            )
            from brooks import save_pending_context as _save_amb
            _save_amb(
                {"type": "ambiguity_resolution", "prompt": user_input, "question": _disam_q},
                session_id=session_id,
                owner_id=owner_id,
            )
            yield _l(f"[Router] Confidence gate triggered: {intent} at {confidence:.0%} < {_CONFIDENCE_GATE:.0%}")
            yield {"type": "clarification_card", "clarification": {
                "question": _disam_q,
                "context": f"I classified this as **{intent}** but I'm only {confidence:.0%} confident — I'd rather ask than get it wrong.",
                "options": [
                    {"label": "Generate an image", "value": "IMAGE", "description": "Render a visual using the AI art studio"},
                    {"label": "Write creative content", "value": "CREATIVE", "description": "Stories, scene descriptions, fiction, lore"},
                    {"label": "Research this topic", "value": "RESEARCH", "description": "Deep knowledge and analysis"},
                    {"label": "Build / code something", "value": "COORDINATE", "description": "Apps, scripts, or complex tasks"},
                    {"label": "Just answer me", "value": "CONVERSATION", "description": "Conversational response"},
                ],
                "allow_freetext": True,
                "card_type": "ambiguity",
            }}
            return

        _fast_mode = (model == "hive-fast")
        if _fast_mode:
            yield _l("[Router] Hive Fast mode — single-pass, no MarsRL verification.")

        # Skill hint override
        _skill_to_intent = {"code": "DEVOPS", "devops": "DEVOPS", "data": "DATA", "creative": "IMAGE", "research": "RESEARCH"}
        if skill and skill in _skill_to_intent and confidence < 0.80:
            old_intent = intent
            intent = _skill_to_intent[skill]
            yield _t(f"→ Skill override: {old_intent} → {intent} (skill={skill})")

        if research_mode and intent not in ("IMAGE", "3D", "ACTION_FIGURE", "DESIGN", "TRAIN"):
            intent = "RESEARCH"; yield _t("→ Research mode activated: forcing RESEARCH intent")
        if swarm_mode and intent not in ("IMAGE", "3D", "ACTION_FIGURE", "DESIGN", "TRAIN", "CREATIVE"):
            intent = "COORDINATE"; yield _t("→ Swarm Mode: routing to multi-agent coordinator")

        # UltraPlan mode (plan only)
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
                "Output format:\n## Plan: [Brief title]\n\n**Goal**: [One sentence summary]\n\n"
                "**Steps**:\n1. **[Step Name]** — [Description]\n   - Dependencies: [none | step numbers]\n"
                "   - Agent: [specialist]\n\n"
                "**Estimated Complexity**: [Low | Medium | High]\n**Notes**: [caveats, risks]\n\n"
                "IMPORTANT: Output ONLY the plan. Do NOT execute, implement, or produce any code/content."
            )
            if ultrathink_mode:
                plan_system_prompt += "\n\nBefore writing the plan, wrap your reasoning in <think>...</think> tags."

            planner = Agent(
                name="Planner",
                model=Ollama(id=PLAN_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 120.0}, options=get_ollama_options(PLAN_MODEL)),
                session_id=session_id,
                instructions=plan_system_prompt,
                show_tool_calls=False,
            )
            try:
                with request_lock(context="text"):
                    yield _emit_stream_mode("responding")
                    plan_chunks = 0
                    start_time = time.time()
                    for chunk in planner.run(user_input, stream=True):
                        if chunk.content:
                            yield {"type": "plan", "content": chunk.content}
                            plan_chunks += 1
                        if PLANNING_MAX_ITER and plan_chunks >= PLANNING_MAX_ITER:
                            yield {"type": "status", "content": f"🛑 Planning iteration limit reached ({PLANNING_MAX_ITER}). Stopping."}
                            break
                        if PLANNING_MAX_TIME and (time.time() - start_time) > PLANNING_MAX_TIME:
                            yield {"type": "status", "content": f"⏰ Planning time limit reached ({PLANNING_MAX_TIME}s). Stopping."}
                            break
            except Exception as e:
                yield {"type": "error", "content": f"Plan generation failed: {e}"}
                logger.error("[Router] UltraPlan failed: %s", e, exc_info=True)
            WORKFLOW_STEPS.labels(status="success", agent_type="Planner").inc()
            AGENT_STATE.labels(agent_name="Router").set(1)
            return

        # UltraThink
        if ultrathink_mode:
            think_msg = {"role": "system", "content": (
                "[Deep Reasoning Mode] Think through this problem step-by-step before answering. "
                "Wrap your reasoning in <think>...</think> tags. After the thinking block, provide your clear final response."
            )}
            history = list(history) + [think_msg] if history else [think_msg]
            yield _t("→ UltraThink: deep reasoning mode activated")

        # Style system prompt
        _style_prompts = {
            "concise": "Respond as concisely as possible. Use bullet points and short sentences.",
            "explanatory": "Explain your reasoning step-by-step. Be thorough and educational.",
            "formal": "Respond in a formal, professional tone.",
            "technical": "Use precise technical language. Include code examples where relevant.",
            "casual": "Respond in a friendly, casual tone. Keep it conversational.",
        }
        _style_instruction = _style_prompts.get(style or "", "")
        if _style_instruction:
            history = list(history or []) + [{"role": "system", "content": f"[Style Instruction] {_style_instruction}"}]
            yield _t(f"→ Style: {style}")

        # Langfuse intent classification span
        if USE_LANGFUSE and langfuse:
            try:
                langfuse.update_current_span(metadata={"intent": intent, "confidence": confidence, "reasoning": reasoning[:200], "owner_id": owner_id})
                with langfuse.start_as_current_observation(
                    name="intent_classification", as_type="span",
                    input={"user_input": user_input[:2000]},
                    output={"intent": intent, "confidence": confidence, "reasoning": reasoning[:200]},
                    metadata={"fast_mode": _fast_mode},
                ):
                    pass
            except Exception:
                pass

        # JWT-ACE scope for this intent
        if JWT_ACE_AVAILABLE:
            intent_caps = get_capabilities_for_intent(intent)
            set_active_scope(intent_caps.get("capabilities", []))
            yield {"type": "log", "content": f"[JWT-ACE] Active scope set for {intent_caps.get('template_id', intent)}"}
            template_metadata.update({
                "template_id": intent_caps.get("template_id", template_metadata.get("template_id")),
                "template_version": template_metadata.get("template_version", "1.0"),
                "intent_capabilities": intent_caps.get("capabilities", []),
            })

        route_start_time = time.time()

        # Build shared handler context
        # _already_steered may have been set when a swarm_steering pending context
        # was resolved above; default False for all other paths.
        if "_already_steered" not in dir():
            _already_steered = False
        is_admin = _is_admin_session(session_id, owner_id)
        # Strip non-Ollama-model values from `model`. The frontend sends UI
        # tier labels like "Home-AI-Swarm" or "default" that aren't real
        # Ollama identifiers. Real model names always include a tag separator
        # (e.g. "qwen3:8b", "qwen3-coder:30b"). When the frontend sends a UI
        # label, handlers should fall back to their template/env defaults
        # rather than try to invoke a non-existent Ollama model — which would
        # cause Phi Agent's generator to throw "generator didn't stop after
        # throw()" and surface a backend error in the chat UI.
        _handler_model = model if (model and ":" in model and model != "hive-fast") else None

        ctx = {
            "session_id": session_id,
            "owner_id": owner_id,
            "uid": uid,
            "turn_id": turn_id,
            "history": history,
            "history_context": history_context,
            "constraint_context": constraint_context,
            "extracted_context": extracted_context,
            "model": _handler_model,
            "ace_token": ace_token,
            "template_metadata": template_metadata,
            "lf_trace": lf_trace,
            "langfuse": langfuse,
            "use_langfuse": USE_LANGFUSE,
            "fast_mode": _fast_mode,
            "research_mode": research_mode,
            "ultraplan_mode": ultraplan_mode,
            "dev_mode": dev_mode,
            "conv_storage": _conv_storage,
            "is_admin": is_admin,
            "already_steered": _already_steered,
            "intent": intent,
            "routing_decision": routing_decision,
            "solving_max_iter": solving_max_iter,
            "solving_max_time": solving_max_time,
            "solving_solver_n_drafts": solving_solver_n_drafts,
            "solving_solver_max_time": solving_solver_max_time,
            "solving_verifier_n_runs": solving_verifier_n_runs,
            "solving_verifier_max_time": solving_verifier_max_time,
            "solving_corrector_n_passes": solving_corrector_n_passes,
            "solving_corrector_max_time": solving_corrector_max_time,
        }

        # ---------------------------------------------------------------------------
        # Handler dispatch
        # ---------------------------------------------------------------------------
        if intent == "VISION":
            from handlers.vision import handle_vision
            yield from handle_vision(user_input, ctx)
            return

        if intent == "COORDINATE":
            from handlers.coordinate import handle_coordinate
            yield from handle_coordinate(user_input, ctx)
            return

        if intent == "CONVERSATION":
            from handlers.conversation import handle_conversation
            yield from handle_conversation(user_input, ctx)
            return

        if intent == "DEVOPS":
            from handlers.devops import handle_devops
            yield from handle_devops(user_input, ctx)
            return

        if intent == "DATA":
            from handlers.devops import handle_data
            yield from handle_data(user_input, ctx)
            return

        if intent == "AMBIGUOUS":
            from handlers.devops import handle_ambiguous
            yield from handle_ambiguous(user_input, ctx)
            return

        if intent == "IMAGE":
            from handlers.image import handle_image
            yield from handle_image(user_input, ctx)
            return

        if intent == "3D":
            from handlers.media import handle_3d
            yield from handle_3d(user_input, ctx)
            return

        if intent == "ACTION_FIGURE":
            from handlers.media import handle_action_figure
            yield from handle_action_figure(user_input, ctx)
            return

        if intent == "DOC_STANDARDS":
            from handlers.research import handle_doc_standards
            yield from handle_doc_standards(user_input, ctx)
            return

        if intent == "DOCUMENTATION":
            from handlers.research import handle_documentation
            yield from handle_documentation(user_input, ctx)
            return

        if intent == "CREATIVE":
            from handlers.creative import handle_creative
            yield from handle_creative(user_input, ctx)
            return

        if intent == "RESEARCH":
            from handlers.research import handle_research
            yield from handle_research(user_input, ctx)
            return

        if intent == "WORKSHOP":
            from handlers.workshop import handle_workshop
            yield from handle_workshop(user_input, ctx)
            return

        if intent == "DESIGN":
            from handlers.design import handle_design
            yield from handle_design(user_input, ctx)
            return

        if intent == "TRAIN":
            from handlers.train import handle_train
            yield from handle_train(user_input, ctx)
            return

        if intent == "IOT_CONTROL":
            from handlers.train import handle_iot_control
            yield from handle_iot_control(user_input, ctx)
            return

        # Default: architect / code
        from handlers.architect import handle_architect
        yield from handle_architect(user_input, ctx)

    except Exception as e:
        yield {"type": "error", "content": f"🔥 Error: {e}"}
        WORKFLOW_STEPS.labels(status="error", agent_type="Router").inc()

    finally:
        try:
            from handlers.base import _emit_stream_mode, _emit_turn_boundary, _emit_continuation_hint
            if USE_LANGFUSE and lf_trace:
                yield {"type": "turn_metadata", "turnMetadata": {"traceId": lf_trace}}
            # Fallback preview URL
            try:
                _url_file = "/tmp/web_builder_last_url.txt"
                if os.path.exists(_url_file):
                    _url_mtime = os.path.getmtime(_url_file)
                    _turn_start = route_start_time if 'route_start_time' in dir() else 0
                    if _url_mtime >= _turn_start:
                        with open(_url_file) as _f:
                            _fallback_url = _f.read().strip()
                        if _fallback_url:
                            yield {"type": "set_preview_url", "content": _fallback_url}
                            logger.info(f"[church] Fallback set_preview_url emitted: {_fallback_url}")
            except Exception as _fe:
                logger.debug(f"[church] Fallback preview URL check failed: {_fe}")
            yield _emit_stream_mode("requesting")
            yield _emit_continuation_hint("await_user", "Turn complete")
            yield _emit_turn_boundary(turn_id, "completed")
        except Exception:
            pass
        AGENT_STATE.labels(agent_name="Router").set(1)

        # Flush Langfuse
        if USE_LANGFUSE and langfuse:
            try:
                if _trace_thoughts:
                    reasoning_text = "\n".join(f"[{t.get('type','?')}] {t.get('content','')}" for t in _trace_thoughts)
                    with langfuse.start_as_current_observation(
                        name="reasoning_narrative", as_type="span",
                        input={"user_input": user_input[:2000]},
                        output={"reasoning": reasoning_text[:8000]},
                        metadata={"step_count": len(_trace_thoughts), "intent": intent if 'intent' in dir() else "UNKNOWN", "model": model, "fast_mode": _fast_mode if '_fast_mode' in dir() else False, "elapsed_s": round(time.time() - route_start_time, 2)},
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

        # JWT-ACE cleanup
        if JWT_ACE_AVAILABLE:
            try:
                clear_active_scope()
                clear_current_token()
            except Exception:
                pass

        # Performance recording
        if template_metadata:
            latency_ms = int((time.time() - route_start_time) * 1000) if 'route_start_time' in dir() else None
            _record_performance(intent if 'intent' in dir() else "UNKNOWN", template_metadata, {"session_id": session_id, "latency_ms": latency_ms})

        # A/B test result
        if AB_TESTING_AVAILABLE and template_metadata.get("template_id"):
            try:
                ab_mgr = get_ab_manager()
                ab_score = template_metadata.get("final_score", 0.0)
                model_used = template_metadata.get("model_used")
                if model_used and ab_score:
                    ab_mgr.record_result(template_id=template_metadata["template_id"], model_used=model_used, score=ab_score, latency_ms=latency_ms)
            except Exception:
                pass


def run_swarm(user_input: str):
    """CLI wrapper for chat_swarm."""
    print(f"--- [Swarm] Receiving Task: {user_input} ---")
    for update in chat_swarm(user_input, session_id="cli_session"):
        print(f"[{update['type'].upper()}] {update['content']}")


if __name__ == "__main__":
    run_swarm("Write a Python script to calculate the Fibonacci sequence.")
