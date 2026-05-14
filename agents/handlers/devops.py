"""handlers/devops.py — DEVOPS, DATA, and AMBIGUOUS intent handlers."""

import logging
import time

from phi.agent import Agent
from phi.model.ollama import Ollama

from metrics import AGENT_STATE, WORKFLOW_STEPS
from utils.gpu_queue import request_lock, get_best_host_for_model
from handlers.base import (
    _emit_stream_mode, _emit_turn_metadata,
    _emit_tool_start, _emit_tool_progress, _emit_tool_result,
    _score_trace, _langfuse_span,
)

logger = logging.getLogger("Router")


def handle_devops(user_input: str, ctx: dict):
    """Generator — DevOps Engineer (fast-pass or MarsRL loop)."""
    session_id = ctx["session_id"]
    turn_id = ctx["turn_id"]
    history_context = ctx["history_context"]
    constraint_context = ctx["constraint_context"]
    extracted_context = ctx["extracted_context"]
    ace_token = ctx["ace_token"]
    template_metadata = ctx["template_metadata"]
    fast_mode = ctx["fast_mode"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]
    conv_storage = ctx["conv_storage"]
    uid = ctx.get("uid")

    from church import _resolve_model_for_intent
    from config import DEVOPS_MODEL as _DEVOPS_MODEL_DEFAULT
    from role_model_resolver import get_model_for_role
    from mars_loop import MarsRLLoop, mars_loop_stream
    from leibniz_agent import get_architect_agent
    from verifier_agent import get_verifier
    from dijkstra_agent import get_corrector

    yield _emit_turn_metadata(turn_id, "DevOps Engineer", ["thinking", "tool-use", "responding"])

    DEVOPS_MODEL = get_model_for_role(uid, "devops", default=_DEVOPS_MODEL_DEFAULT)
    DEVOPS_MODEL = _resolve_model_for_intent("DEVOPS", DEVOPS_MODEL)
    yield {"type": "status", "content": "🖥️ DevOps Engineer: Analyzing infrastructure task..."}
    AGENT_STATE.labels(agent_name="DevOps").set(2)

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

    if fast_mode:
        yield {"type": "thought", "content": f"→ Hive Fast: single-pass DevOps ({DEVOPS_MODEL})"}
        devops_agent = Agent(
            name="DevOps Engineer",
            model=Ollama(id=DEVOPS_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 120.0}),
            storage=conv_storage,
            session_id=session_id,
            add_history_to_messages=True,
            num_history_responses=10,
            instructions="You are a DevOps engineer in a self-hosted home lab. Help with infrastructure, Docker, networking, and system administration tasks.",
            show_tool_calls=False,
        )
        full_content = ""
        try:
            with _langfuse_span("devops_fast_generation", "DevOps", DEVOPS_MODEL, devops_input,
                                langfuse=langfuse, use_langfuse=use_langfuse) as span_result:
                with request_lock(context="text"):
                    yield _emit_stream_mode("responding")
                    for chunk in devops_agent.run(devops_input, stream=True):
                        if chunk.content:
                            full_content += chunk.content
                            yield {"type": "message", "content": chunk.content}
                span_result["output"] = full_content
            _score_trace(lf_trace, langfuse, 0.85, output=full_content, use_langfuse=use_langfuse)
        except Exception as e:
            _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)
            yield {"type": "error", "content": f"DevOps task failed: {e}"}
    else:
        solver = get_architect_agent(session_id=session_id)
        verifier = get_verifier()
        corrector = get_corrector()

        mars = MarsRLLoop(
            solver=solver,
            verifier=verifier,
            corrector=corrector,
            max_iter=ctx.get("solving_max_iter") or 2,
            intent="DEVOPS",
            session_id=session_id,
            token=ace_token,
            template_metadata=template_metadata,
            max_time=ctx.get("solving_max_time"),
            solver_n_drafts=ctx.get("solving_solver_n_drafts") or 1,
            solver_max_time=ctx.get("solving_solver_max_time"),
            verifier_n_runs=ctx.get("solving_verifier_n_runs") or 1,
            verifier_max_time=ctx.get("solving_verifier_max_time"),
            corrector_n_passes=ctx.get("solving_corrector_n_passes") or 1,
            corrector_max_time=ctx.get("solving_corrector_max_time"),
        )

        yield {"type": "log", "content": "[DevOps] Routing to MarsRL with infra context."}
        yield {"type": "thought", "content": f"→ Routing to Architect ({DEVOPS_MODEL}) via MarsRL loop"}
        tool_call_id = f"tool-devops-{int(time.time()*1000)}"
        try:
            yield _emit_tool_start(tool_call_id, "marsrl_loop", {"intent": "DEVOPS", "model": DEVOPS_MODEL})
            with request_lock(context="text"):
                yield _emit_stream_mode("tool-use")
                yield _emit_tool_progress(tool_call_id, "marsrl_loop", 25, "Initializing MarsRL loop")
                for update in mars_loop_stream(devops_input, mars):
                    yield update
                yield _emit_tool_progress(tool_call_id, "marsrl_loop", 100, "MarsRL loop complete")
            yield _emit_tool_result(tool_call_id, "marsrl_loop", "DevOps plan generated", True)
            _score_trace(lf_trace, langfuse, 0.9, use_langfuse=use_langfuse)
        except Exception as e:
            yield _emit_tool_result(tool_call_id, "marsrl_loop", f"DevOps execution failed: {e}", False)
            _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)
            raise

    AGENT_STATE.labels(agent_name="DevOps").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="DevOps").inc()


def handle_data(user_input: str, ctx: dict):
    """Generator — Data Analyst."""
    turn_id = ctx["turn_id"]
    history_context = ctx["history_context"]
    extracted_context = ctx["extracted_context"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]
    uid = ctx.get("uid")

    from church import _resolve_model_for_intent
    from config import ANALYST_MODEL as _ANALYST_MODEL_DEFAULT
    from role_model_resolver import get_model_for_role

    yield _emit_turn_metadata(turn_id, "Data Analyst", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    yield {"type": "status", "content": "📊 Data Analyst: Processing your data request..."}

    DATA_MODEL = get_model_for_role(uid, "analyst", default=_ANALYST_MODEL_DEFAULT)
    DATA_MODEL = _resolve_model_for_intent("DATA", DATA_MODEL)
    OLLAMA_HOST = get_best_host_for_model(DATA_MODEL)
    AGENT_STATE.labels(agent_name="DataAnalyst").set(2)

    data_agent = Agent(
        name="Data Analyst",
        model=Ollama(id=DATA_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 300.0}),
        instructions=(
            "You are a Staff-Level Data Engineer and Analyst.\n"
            "Expertise: SQL, Python (pandas/numpy/polars), data pipelines, statistical analysis, and data visualization.\n"
            "For SQL queries: write clean, well-commented SQL with CTEs where appropriate.\n"
            "For Python: use pandas or polars, include sample output in comments.\n"
            "For analysis: provide clear findings with supporting logic.\n"
            "Always explain your approach before diving into code."
        ),
        show_tool_calls=False,
    )

    final_input = user_input
    if history_context:
        final_input = f"{history_context}\n\n{final_input}"
        yield {"type": "log", "content": "[DataAnalyst] Reviewed prior turns for continuity."}
    if extracted_context:
        yield {"type": "log", "content": f"[DataAnalyst] Reading attached context ({len(extracted_context)} chars)..."}
        final_input = f"{final_input}\n\n[Data Context]:\n{extracted_context}"

    full_content = ""
    try:
        with _langfuse_span("data_analysis_generation", "DataAnalyst", DATA_MODEL, final_input,
                            langfuse=langfuse, use_langfuse=use_langfuse) as span_result:
            with request_lock(context="text"):
                response_stream = data_agent.run(final_input, stream=True)
                yield {"type": "status", "content": "📊 Data Analyst: Generating analysis..."}
                for chunk in response_stream:
                    if chunk.content:
                        yield _emit_stream_mode("responding")
                        full_content += chunk.content
                        yield {"type": "message", "content": chunk.content}
            span_result["output"] = full_content
        _score_trace(lf_trace, langfuse, 0.85, output=full_content, use_langfuse=use_langfuse)
    except Exception as e:
        _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)
        yield {"type": "error", "content": f"Data analysis failed: {e}"}

    AGENT_STATE.labels(agent_name="DataAnalyst").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="DataAnalyst").inc()


def handle_ambiguous(user_input: str, ctx: dict):
    """Generator — return a disambiguation clarification card."""
    session_id = ctx["session_id"]
    owner_id = ctx["owner_id"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]
    routing_decision = ctx.get("routing_decision", {})

    question = routing_decision.get("disambiguation_question", "Could you clarify your request?")

    from brooks import save_pending_context
    save_pending_context(
        {"type": "ambiguity_resolution", "prompt": user_input, "question": question},
        session_id=session_id,
        owner_id=owner_id,
    )

    yield {
        "type": "clarification_card",
        "clarification": {
            "question": question,
            "context": None,
            "options": [
                {"label": "Generate an image", "value": "IMAGE", "description": "Render a visual using the AI art studio"},
                {"label": "Write creative content", "value": "CREATIVE", "description": "Stories, scene descriptions, fiction, lore"},
                {"label": "Research this topic", "value": "RESEARCH", "description": "Deep knowledge and analysis"},
                {"label": "Build / code something", "value": "COORDINATE", "description": "Apps, scripts, or complex tasks"},
                {"label": "Just answer me", "value": "CONVERSATION", "description": "Conversational response"},
            ],
            "allow_freetext": True,
            "card_type": "ambiguity",
        },
    }
    _score_trace(lf_trace, langfuse, 0.7, output=question, use_langfuse=use_langfuse)
    AGENT_STATE.labels(agent_name="Router").set(1)
