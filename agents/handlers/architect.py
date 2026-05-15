"""handlers/architect.py — Default ARCHITECT/CODE handler (fast-pass or MarsRL loop)."""

import logging
import re
import sys
import subprocess
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


def handle_architect(user_input: str, ctx: dict):
    """Generator — default code/architecture handler: fast-pass or full MarsRL loop."""
    session_id = ctx["session_id"]
    turn_id = ctx["turn_id"]
    intent = ctx.get("intent", "COORDINATE")
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
    from config import ARCHITECT_MODEL, get_ollama_options
    from role_model_resolver import get_model_for_role
    from security_agent import get_security_agent
    from mars_loop import MarsRLLoop, mars_loop_stream
    from leibniz_agent import get_architect_agent
    from verifier_agent import get_verifier
    from dijkstra_agent import get_corrector

    ARCH_MODEL = get_model_for_role(uid, "coder", default=ARCHITECT_MODEL)
    ARCH_MODEL = ctx.get("model") if ctx.get("model") and ctx.get("model") != "hive-fast" else ARCH_MODEL
    ARCH_MODEL = ARCH_MODEL or ARCHITECT_MODEL
    OLLAMA_HOST = get_best_host_for_model(ARCH_MODEL)

    try:
        from memory_system import memory
        code_rules = memory.get_relevant_rules(user_input, "coding_rules")
    except Exception:
        code_rules = []

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

    if fast_mode:
        yield _emit_turn_metadata(turn_id, "Architect (Fast)", ["thinking", "responding"])
        yield _emit_stream_mode("thinking")
        yield {"type": "status", "content": "⚡ Architect (Fast): Generating..."}
        AGENT_STATE.labels(agent_name="Architect").set(2)
        yield {"type": "thought", "content": f"→ Hive Fast: single-pass Architect ({ARCH_MODEL})"}

        fast_agent = Agent(
            name="Architect",
            model=Ollama(id=ARCH_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 120.0}, options=get_ollama_options(ARCH_MODEL)),
            storage=conv_storage,
            session_id=session_id,
            add_history_to_messages=True,
            num_history_responses=10,
            instructions=(
                "You are the Hive Mind Architect, an expert software engineer and system designer.\n"
                "Write clean, correct, production-quality code. Explain your reasoning concisely.\n"
                "You run on local hardware in a self-hosted home lab."
            ),
            show_tool_calls=False,
        )
        full_content = ""
        try:
            with _langfuse_span("architect_fast_generation", "Architect", ARCH_MODEL, final_input,
                                langfuse=langfuse, use_langfuse=use_langfuse) as span_result:
                with request_lock(context="text"):
                    yield _emit_stream_mode("responding")
                    for chunk in fast_agent.run(final_input, stream=True):
                        if chunk.content:
                            full_content += chunk.content
                            yield {"type": "message", "content": chunk.content}
                span_result["output"] = full_content
            _score_trace(lf_trace, langfuse, 0.85, output=full_content, use_langfuse=use_langfuse)
        except Exception as e:
            _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)
            raise

    else:
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
            max_iter=ctx.get("solving_max_iter") or 2,
            intent=intent,
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

        yield {"type": "log", "content": f"[MarsRL] Intent: {intent} | Loop initialized."}
        yield {"type": "thought", "content": f"→ Routing to Architect ({ARCH_MODEL}) via MarsRL loop"}

        tool_call_id = f"tool-architect-{int(time.time()*1000)}"
        try:
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
            yield _emit_tool_result(tool_call_id, "marsrl_loop", f"Architect loop failed: {error_str}", False)
            yield {"type": "log", "content": f"[Exception] MarsRL Crash: {error_str}"}

            package_match = (
                re.search(r"No module named '(\w+)'", error_str)
                or re.search(r"custom_nodes\\(\w+)", error_str)
            )
            if package_match:
                missing_pkg = package_match.group(1)
                yield {"type": "status", "content": f"🚨 Gatekeeper: Missing '{missing_pkg}'"}
                security = get_security_agent()
                review = security.review_dependency(missing_pkg)
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
                raise

    WORKFLOW_STEPS.labels(status="success", agent_type="Architect").inc()
    AGENT_STATE.labels(agent_name="Architect").set(1)
