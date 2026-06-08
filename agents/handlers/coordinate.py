"""handlers/coordinate.py — COORDINATE intent handler (Lamport multi-worker orchestration)."""

import logging
import time

from metrics import AGENT_STATE, WORKFLOW_STEPS
from handlers.base import (
    _emit_stream_mode, _emit_turn_metadata,
    _emit_tool_start, _emit_tool_progress, _emit_tool_result,
    _score_trace,
)

logger = logging.getLogger("Router")


def handle_coordinate(user_input: str, ctx: dict):
    """Generator — route to Lamport coordinate_task after optional dev_mode_gate check."""
    session_id = ctx["session_id"]
    owner_id = ctx["owner_id"]
    turn_id = ctx["turn_id"]
    history_context = ctx["history_context"]
    extracted_context = ctx["extracted_context"]
    ace_token = ctx["ace_token"]
    template_metadata = ctx["template_metadata"]
    ultraplan_mode = ctx["ultraplan_mode"]
    dev_mode = ctx["dev_mode"]
    research_mode = ctx["research_mode"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]
    already_steered = ctx.get("already_steered", False)

    # --- DEV MODE GATE ---
    # Intercept build/project requests when dev_mode is off and not in research/plan mode.
    _build_keywords = (
        "build", "create", "make", "develop", "implement", "write a ",
        "code ", "design a", "design an", "generate a", "generate an",
        "program ", "app", "game", "website", "web app", "tool",
    )
    _is_build_request = any(kw in user_input.lower() for kw in _build_keywords)
    _research_only = research_mode or ultraplan_mode

    if not dev_mode and _is_build_request and not _research_only:
        logger.info("[Router] Coding/project request detected in standard mode — showing dev mode gate.")
        try:
            from brooks import save_pending_context as _save_ctx
            _save_ctx(
                {"type": "dev_mode_gate", "prompt": user_input},
                session_id=session_id,
                owner_id=owner_id,
            )
        except Exception as _e:
            logger.warning("[DevModeGate] Could not save context: %s", _e)
        yield {
            "type": "clarification_card",
            "clarification": {
                "question": (
                    "This looks like a project build request. Dev Mode unlocks file creation, "
                    "code execution, and a live workspace. How would you like to proceed?"
                ),
                "context": (
                    "You're in standard chat mode. Switching to **Dev Mode** gives the swarm "
                    "full implementation tools."
                ),
                "options": [
                    {
                        "label": "Switch to Dev Mode",
                        "value": "switch_to_dev_mode",
                        "description": "Open the Developer workspace",
                        "redirect": "/dev",
                    },
                    {
                        "label": "Request Dev Access",
                        "value": "request_dev_access",
                        "description": "Submit a governance request",
                    },
                    {
                        "label": "Research & Plan Only",
                        "value": "plan_only",
                        "description": "Run the swarm, no files written",
                    },
                ],
                "allow_freetext": False,
                "card_type": "dev_mode_gate",
            },
        }
        return

    logger.info("[Coordinator] DEBUG: About to call coordinate_task with ultraplan_mode=%s", ultraplan_mode)
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
            ultraplan_mode=ultraplan_mode,
            dev_mode=dev_mode,
            plan_mode=ultraplan_mode,
            research_mode=research_mode,
            already_steered=already_steered,
        ):
            yield update
            # Mirror key events as structured agent_event so the UI can render
            # the agent communication stream in real-time (Claude Code style trace).
            utype = update.get("type", "")
            ucontent = update.get("content", "")
            if not ucontent:
                continue
            if utype == "thought":
                yield {
                    "type": "agent_event",
                    "agent_name": update.get("agent_name") or update.get("pioneer_name") or "Coordinator",
                    "event_type": "thought",
                    "content": ucontent,
                }
            elif utype == "status":
                yield {
                    "type": "agent_event",
                    "agent_name": update.get("agent_name") or "Coordinator",
                    "event_type": "status",
                    "content": ucontent,
                }
            elif utype == "log":
                yield {
                    "type": "agent_event",
                    "agent_name": update.get("agent_name") or "System",
                    "event_type": "log",
                    "content": ucontent,
                }
            elif utype == "swarm_worker_created":
                worker_name = update.get("pioneer_name") or update.get("worker_id") or "Worker"
                yield {
                    "type": "agent_event",
                    "agent_name": "Coordinator",
                    "event_type": "spawned",
                    "content": f"Spawned {worker_name}: {update.get('task', '')[:120]}",
                }

        yield _emit_tool_result(tool_call_id, "coordinate_task", "Coordination complete", True)
        _score_trace(lf_trace, langfuse, 0.9, use_langfuse=use_langfuse)

    except Exception as e:
        logger.error("[Coordinator] Failed: %s", e, exc_info=True)
        if 'tool_call_id' in locals():
            yield _emit_tool_result(tool_call_id, "coordinate_task", f"Coordination failed: {e}", False)
        yield {"type": "error", "content": f"Coordination failed: {e}"}
        _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)

    AGENT_STATE.labels(agent_name="Coordinator").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="Coordinator").inc()
