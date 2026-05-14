"""handlers/train.py — TRAIN (memory) and IOT_CONTROL intent handlers."""

import logging
import os
import re

import requests

from phi.agent import RunResponse
from metrics import AGENT_STATE, WORKFLOW_STEPS
from handlers.base import _emit_stream_mode, _emit_turn_metadata, _score_trace

logger = logging.getLogger("Router")


def handle_train(user_input: str, ctx: dict):
    """Generator — Memory Controller: learn a new rule/correction."""
    turn_id = ctx["turn_id"]
    owner_id = ctx["owner_id"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]

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

    match = re.search(
        r"(?:remember that|correction:|learn:) (.+?) (?:means|is|should be) (.+)",
        user_input,
        re.IGNORECASE,
    )
    if match:
        keyword = match.group(1).strip()
        rule = match.group(2).strip()

    result = memory.add_rule(domain, keyword, rule)

    # Mirror into MemPalace (non-critical)
    try:
        _mp_url = os.getenv("MEMPALACE_API_URL", "http://192.168.2.102:8200")
        requests.post(
            f"{_mp_url}/v1/memories",
            json={
                "content": f"{keyword}: {rule}",
                "memory_type": "procedural",
                "domain": domain.replace("_rules", ""),
                "owner_id": owner_id,
            },
            timeout=5.0,
        )
    except Exception as mp_exc:
        logger.debug("[MemPalace] TRAIN mirror failed: %s", mp_exc)

    yield {"type": "response", "content": f"🧠 **Learned**: {result}"}
    _score_trace(lf_trace, langfuse, 1.0, output=result, use_langfuse=use_langfuse)


def handle_iot_control(user_input: str, ctx: dict):
    """Generator — IoT Controller via Home Assistant agent."""
    turn_id = ctx["turn_id"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]

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
        _score_trace(lf_trace, langfuse, 1.0, output=response.content, use_langfuse=use_langfuse)
    except Exception as e:
        _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)
        yield {"type": "error", "content": f"IoT Error: {e}"}

    AGENT_STATE.labels(agent_name="IoTController").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="IoTController").inc()
