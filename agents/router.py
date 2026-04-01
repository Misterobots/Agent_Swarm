from phi.agent import Agent, RunResponse
from architect_agent import get_architect_agent
from security_agent import get_security_agent

# MarsRL Loop — Solver → Verifier → Corrector
from mars_loop import MarsRLLoop, mars_loop_stream
from verifier_agent import get_verifier
from corrector_agent import get_corrector

from metrics import AGENT_STATE, WORKFLOW_STEPS
import time
import sys
import subprocess
import re
import os
import json
from dispatcher import Event, EventType
from logger_setup import setup_logger
from utils.gpu_queue import request_lock, get_best_host_for_model
from phi.storage.agent.postgres import PgAgentStorage
from config import AGNO_DB_URL

logger = setup_logger("Router")

# Shared storage for conversationalist sessions (same pattern as architect_agent)
_conv_storage = PgAgentStorage(
    table_name="conversation_sessions",
    db_url=AGNO_DB_URL,
)

# --- JWT-ACE Integration ---
try:
    from intent_capabilities import get_capabilities_for_intent
    from security.token_issuer import EphemeralAgentCard, get_token_issuer
    from security.execution_context import set_current_token, clear_current_token
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
    langfuse_context = None # Stubbed for v3 compatibility until open-telemetry logic is integrated
    logger.info("[Router] Langfuse tracing enabled")
except ImportError:
    USE_LANGFUSE = False
    observe = lambda *args, **kwargs: lambda f: f  # No-op decorator
    langfuse_context = None
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
        if intent == "IMAGE":
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


def chat_swarm(
    user_input: str,
    session_id: str = "default_session",
    history: list = None,
    memory_enabled: bool = False,
    owner_id: str | None = None,
):
    """
    Generator that yields status updates and final response for UI.
    - history: Optional list of OpenAI-formatted messages [{"role": "user", "content": "..."}]
    - memory_enabled: If True, inject recent session summaries as system context.
    """
    AGENT_STATE.labels(agent_name="Router").set(2)
    WORKFLOW_STEPS.labels(status="started", agent_type="Router").inc()
    logger.info("--- [Router] chat_swarm v4.1 (ACTION_FIGURE + context-session-scoped) ---")

    # JWT-ACE state (initialized here so finally block can always access them)
    ace_token = None
    template_metadata = {}
    route_start_time = time.time()
    lf_trace = None  # Langfuse trace handle (populated below if Langfuse is active)

    # --- Langfuse top-level trace for all intents (v4 context manager) ---
    _lf_ctx = None
    if USE_LANGFUSE and langfuse:
        try:
            _lf_ctx = langfuse.start_as_current_observation(
                name="chat_swarm",
                as_type="agent",
                input={"message": user_input[:4000]},
                metadata={"session_id": session_id, "owner_id": owner_id},
            )
            _lf_ctx.__enter__()
        except Exception as e:
            _lf_ctx = None
            logger.debug(f"[Router] Trace creation failed: {e}")

    # --- HISTORY CONVERSION ---
    # PHI Agents use their own storage/history, but we can seed it or pass it.
    # For now, we'll use history to enhance the prompt if provided.
    history_context = ""
    if history:
        history_context = "\n\n[Previous Conversation History]:\n"
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_context += f"- {role.upper()}: {content}\n"
    
    # --- RAG CONTEXT INTERCEPTION ---
    import re
    extracted_context = ""
    context_match = re.search(r'<context>.*?</context>', user_input, re.DOTALL)
    if context_match:
        extracted_context = context_match.group(0)
        # Strip Open-WebUI's boilerplate injection
        user_input = re.sub(r'### Task:.*?<context>.*?</context>\s*', '', user_input, flags=re.DOTALL).strip()
        yield {"type": "log", "content": f"[Router] Intercepted RAG Context ({len(extracted_context)} chars)."}
    
    # 1. Load Context (Memory Bridge)
    from context_manager import get_pending_context, clear_context, save_pending_image_clarification
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
                    yield {"type": "thought", "content": f"→ Memory: Recalled {len(recent)} prior session summaries"}
            except Exception as _mem_err:
                logger.debug(f"[Router] Memory recall failed (non-fatal): {_mem_err}")

        # 2. Security Check (on the Merged Input)
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
        yield {"type": "thought", "content": "→ Security: PASS"}
        WORKFLOW_STEPS.labels(status="success", agent_type="Security").inc()

        # 3. Intent Routing (Neural Upgrade)
        from semantic_router import get_semantic_router
        
        yield {"type": "status", "content": "🧠 Neural Cortex: Analyzing intent..."}
        
        router_inst = get_semantic_router()
        routing_decision = router_inst.route(user_input)
        intent = routing_decision.get("intent", "RESEARCH") # Fail safe default
        confidence = routing_decision.get("confidence", 0.0)
        reasoning = routing_decision.get("reasoning", "No reasoning provided.")

        # --- KEYWORD OVERRIDE: Catch intents the LLM doesn't know about ---
        _lower = user_input.lower()
        if any(kw in _lower for kw in ["action figure", "posable", "ball joint", "figurine", "poseable"]):
            intent = "ACTION_FIGURE"
            confidence = 0.95
            reasoning = f"Keyword override: action figure keywords detected in '{user_input[:60]}'"
        
        yield {"type": "log", "content": f"[Router] Intent: {intent} ({confidence * 100:.1f}%) | Reason: {reasoning}"}
        logger.info(f"--- [Router] Neural Decision: {intent} (Conf: {confidence}) ---")

        yield {"type": "thought", "content": f"→ Intent: {intent} ({confidence * 100:.0f}% confidence)"}

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
            except Exception:
                pass

        if USE_LANGFUSE and langfuse_context:
            langfuse_context.update_current_observation(
                name="intent_routing",
                metadata={"model": router_inst.model_name, "host": router_inst.host},
                output=routing_decision,
                scores=[{"name": "routing_confidence", "value": confidence}]
            )

        # --- JWT-ACE: Issue ephemeral token for this intent ---
        ace_token, template_metadata = _issue_ephemeral_token(intent, session_id, owner_id=owner_id)
        if ace_token:
            set_current_token(ace_token) if JWT_ACE_AVAILABLE else None
            yield {"type": "log", "content": f"[JWT-ACE] Token issued for {template_metadata.get('template_id', intent)} v{template_metadata.get('template_version', '1.0')}"}

        route_start_time = time.time()

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
            from context_manager import save_pending_context
            save_pending_context({
                "type": "art_studio_redirect",
                "intent": intent,
                "prompt": user_input
            }, session_id=session_id, owner_id=owner_id)
            AGENT_STATE.labels(agent_name="Router").set(1)
            return

        # --- ROUTE: CONVERSATION / CASUAL CHAT ---
        if intent == "CONVERSATION":
            yield {"type": "status", "content": "💬 Hive Mind: Thinking..."}
            AGENT_STATE.labels(agent_name="Conversationalist").set(2)

            from phi.model.ollama import Ollama
            CONV_MODEL = _resolve_model_for_intent("CONVERSATION", os.getenv("CONV_MODEL", "qwen2.5:3b"))
            OLLAMA_HOST = get_best_host_for_model(CONV_MODEL)

            conversationalist = Agent(
                name="Hive Mind",
                model=Ollama(id=CONV_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 120.0}),
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
                with request_lock(context="text"):
                    response_stream = conversationalist.run(user_input, stream=True)
                    for chunk in response_stream:
                        if chunk.content:
                            full_content += chunk.content
                            yield {"type": "message", "content": chunk.content}
                _score_trace(lf_trace, langfuse, 0.85, output=full_content)
            except Exception as e:
                _score_trace(lf_trace, langfuse, 0.0)
                yield {"type": "error", "content": f"Conversation failed: {e}"}

            AGENT_STATE.labels(agent_name="Conversationalist").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="Conversationalist").inc()
            return

        # --- ROUTE: DEVOPS / INFRASTRUCTURE ---
        if intent == "DEVOPS":
            yield {"type": "status", "content": "🖥️ DevOps Engineer: Analyzing infrastructure task..."}
            AGENT_STATE.labels(agent_name="DevOps").set(2)

            DEVOPS_MODEL = _resolve_model_for_intent("DEVOPS", os.getenv("ARCHITECT_MODEL", "qwen2.5-coder:14b"))
            OLLAMA_HOST = get_best_host_for_model(DEVOPS_MODEL)

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

            devops_input = f"[DEVOPS TASK] {user_input}"
            if extracted_context:
                devops_input = f"{devops_input}\n\n[Attached Context]:\n{extracted_context}"

            yield {"type": "log", "content": f"[DevOps] Routing to MarsRL with infra context."}
            yield {"type": "thought", "content": f"→ Routing to Architect ({DEVOPS_MODEL}) via MarsRL loop"}
            try:
                with request_lock(context="text"):
                    for update in mars_loop_stream(devops_input, mars):
                        yield update
                _score_trace(lf_trace, langfuse, 0.9)
            except Exception as e:
                _score_trace(lf_trace, langfuse, 0.0)
                raise e

            AGENT_STATE.labels(agent_name="DevOps").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="DevOps").inc()
            return

        # --- ROUTE: DATA ANALYSIS ---
        if intent == "DATA":
            yield {"type": "status", "content": "📊 Data Analyst: Processing your data request..."}
            AGENT_STATE.labels(agent_name="DataAnalyst").set(2)

            from phi.model.ollama import Ollama
            DATA_MODEL = _resolve_model_for_intent("DATA", os.getenv("ARCHITECT_MODEL", "qwen2.5-coder:14b"))
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
                if extracted_context:
                    yield {"type": "log", "content": f"[DataAnalyst] Reading attached context ({len(extracted_context)} chars)..."}
                    final_input = f"{user_input}\n\n[Data Context]:\n{extracted_context}"

                with request_lock(context="text"):
                    response_stream = data_agent.run(final_input, stream=True)
                    yield {"type": "status", "content": "📊 Data Analyst: Generating analysis..."}
                    for chunk in response_stream:
                        if chunk.content:
                            full_content += chunk.content
                            yield {"type": "message", "content": chunk.content}
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
             from context_manager import save_pending_context
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
             
             from phi.model.ollama import Ollama
             # Config — template-driven model selection with health-aware routing
             MODEL_NAME = _resolve_model_for_intent("IMAGE", os.getenv("ARCHITECT_MODEL", "qwen2.5-coder:14b"))
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

        # --- ROUTE: DOCUMENTATION / TECHNICAL WRITING ---
        if intent == "DOCUMENTATION":
            yield {"type": "status", "content": "📝 Technical Writer: Reviewing document structure..."}
            AGENT_STATE.labels(agent_name="TechnicalWriter").set(2)
            
            # Template-driven model selection with health-aware routing
            TECH_MODEL = _resolve_model_for_intent("DOCUMENTATION", os.getenv("ARCHITECT_MODEL", "qwen3.5:9b"))
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
                    
                with request_lock(context="text"):
                    response_stream = tech_writer.run(final_input, stream=True)
                    yield {"type": "status", "content": "📝 Technical Writer: Generating document..."}
                    full_content = ""
                    for chunk in response_stream:
                        if chunk.content:
                            full_content += chunk.content
                            yield {"type": "message", "content": chunk.content}
                
                    yield {"type": "log", "content": "[TechnicalWriter] Document Transformation Complete."}
                _score_trace(lf_trace, langfuse, 0.85, output=full_content)

            except Exception as e:
                _score_trace(lf_trace, langfuse, 0.0)
                yield {"type": "error", "content": f"Technical Writing Failed: {e}"}

            AGENT_STATE.labels(agent_name="TechnicalWriter").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="TechnicalWriter").inc()
            return

        # --- ROUTE: RESEARCH / CHAT ---
        if intent == "RESEARCH":
            yield {"type": "status", "content": "📚 Librarian Agent: Accessing Archives..."}
            AGENT_STATE.labels(agent_name="Librarian").set(2)
            
            from phi.model.ollama import Ollama
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
                if extracted_context:
                    yield {"type": "log", "content": "[Librarian] Reading Attached RAG Context..."}
                    final_input = f"{user_input}\n\n[Attached Document Context]:\n{extracted_context}"
                    
                with request_lock(context="text"):
                    response_stream = researcher.run(final_input, stream=True)
                    yield {"type": "status", "content": "📚 Librarian Agent: Drafting response..."}
                    full_content = ""
                    for chunk in response_stream:
                        if chunk.content:
                            full_content += chunk.content
                            yield {"type": "message", "content": chunk.content}
                
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
            yield {"type": "response", "content": f"🧠 **Learned**: {result}"}
            _score_trace(lf_trace, langfuse, 1.0, output=result)
            return

        # --- ROUTE: IOT CONTROLLER (HOME ASSISTANT) ---
        if intent == "IOT_CONTROL":
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

        # --- ROUTE: STANDARD ARCHITECT / CODE (MarsRL Loop) ---
        # Only fall through to MarsRL if no specialized route handled this intent
        if intent not in ("CONVERSATION", "DEVOPS", "DATA", "AMBIGUOUS", "IMAGE",
                          "DOCUMENTATION", "RESEARCH", "3D", "ACTION_FIGURE",
                          "TRAIN", "IOT_CONTROL"):
            yield {"type": "status", "content": "🏗️ MarsRL: Solver → Verifier → Corrector..."}
            AGENT_STATE.labels(agent_name="Architect").set(2)

            try:
                from memory_system import memory
                code_rules = memory.get_relevant_rules(user_input, "coding_rules")
                
                final_input = user_input
                if code_rules:
                    rule_block = "\n".join([f"- {r}" for r in code_rules])
                    final_input = f"{user_input}\n\n[🧠 MEMORY] Apply these user-taught coding rules:\n{rule_block}"
                    yield {"type": "log", "content": f"[Memory] Injected {len(code_rules)} coding rules."}

                if extracted_context:
                    final_input = f"{final_input}\n\n[Attached Document Context]:\n{extracted_context}"

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

                yield {"type": "thought", "content": f"→ Routing to Architect ({os.getenv('ARCHITECT_MODEL', 'qwen2.5-coder:14b')}) via MarsRL loop"}
                with request_lock(context="text"):
                    for update in mars_loop_stream(final_input, mars):
                        # Capture MarsLoopResult for performance recording
                        if update.get("type") == "log" and "[MarsRL] Iterations:" in update.get("content", ""):
                            # Extract scores from the summary line for perf recording
                            pass
                        yield update

            except Exception as e:
                error_str = str(e)
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
        AGENT_STATE.labels(agent_name="Router").set(1)
        # Close Langfuse trace context and flush
        if USE_LANGFUSE and langfuse:
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
