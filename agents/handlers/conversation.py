"""handlers/conversation.py — CONVERSATION intent handler (3-tier access control)."""

import json
import logging
import re

import requests

from phi.agent import Agent
from phi.model.ollama import Ollama

from metrics import AGENT_STATE, WORKFLOW_STEPS
from utils.gpu_queue import request_lock, get_best_host_for_model, pre_lock_status_events
from handlers.base import (
    _emit_stream_mode, _emit_turn_metadata, _score_trace, _langfuse_span,
    _emit_suggested_followups,
)

logger = logging.getLogger("Router")


def handle_conversation(user_input: str, ctx: dict):
    """Generator — Hive Mind conversationalist with 3-tier access control."""
    session_id = ctx["session_id"]
    owner_id = ctx["owner_id"]
    turn_id = ctx["turn_id"]
    history_context = ctx["history_context"]
    constraint_context = ctx["constraint_context"]
    extracted_context = ctx["extracted_context"]
    dev_mode = ctx["dev_mode"]
    fast_mode = ctx.get("fast_mode", False)
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]
    conv_storage = ctx["conv_storage"]
    is_admin = ctx.get("is_admin", False)

    # Lazy import to avoid circular deps
    from church import _resolve_model_for_intent
    import os
    from config import ARCHITECT_MODEL, get_ollama_options

    yield _emit_turn_metadata(turn_id, "Hive Mind", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    yield {"type": "status", "content": "💬 Hive Mind: Thinking..."}
    AGENT_STATE.labels(agent_name="Conversationalist").set(2)

    # Model resolution:
    # 1. fast_mode (model="hive-fast") forces the small ROUTER_MODEL — already
    #    hot in VRAM from the intent classifier. No GPU eviction, fastest path.
    # 2. Otherwise, _resolve_model_for_intent reads from the template registry.
    #    The CONVERSATION template default is qwen3:8b (same hot model).
    # 3. Explicit ctx["model"] override wins last (unless it's the sentinel
    #    "hive-fast", which we treat as a *flag* not a real model name).
    if fast_mode:
        CONV_MODEL = os.getenv("ROUTER_MODEL", "qwen3:8b")
        yield {"type": "thought", "content": f"→ Hive Fast: conversation on {CONV_MODEL} (router model, already hot)"}
    else:
        # Trust the template registry (CONVERSATION default is qwen3:8b).
        # NOTE: we deliberately do NOT honor ctx["model"] here — the frontend
        # often sends UI tier names like "Home-AI-Swarm" that aren't real
        # Ollama identifiers. If you want to force a specific model, set the
        # CONV_MODEL env var or update the template registry default.
        CONV_MODEL = _resolve_model_for_intent(
            "CONVERSATION",
            os.getenv("CONV_MODEL", os.getenv("PRIMARY_MODEL", "qwen3:8b")),
        )
    OLLAMA_HOST = get_best_host_for_model(CONV_MODEL)

    if is_admin:
        from tools.file_ops import read_file, write_file, list_dir
        from tools.terminal import run_command
        from tools.admin_file_ops import admin_read_file, admin_write_file, admin_list_dir
        from tools.git_ops import git_status, git_checkout, git_commit, git_push, git_pull, git_branch_list

        agent_tools = [
            read_file, write_file, list_dir, run_command,
            admin_read_file, admin_write_file, admin_list_dir,
            git_status, git_checkout, git_commit, git_push, git_pull, git_branch_list,
        ]
        instructions = (
            "You are Hive Mind, the AI assistant for the Agent Swarm infrastructure.\n\n"
            "ADMIN MODE ACTIVE - Full System Access:\n\n"
            "YOUR CAPABILITIES:\n"
            "1. **Workspace Files**: read_file, write_file, list_dir (sandbox: /workspace/)\n"
            "2. **Admin Files**: admin_read_file, admin_write_file, admin_list_dir (any path)\n"
            "3. **Terminal**: run_command (execute commands, Docker, SSH)\n"
            "4. **Git Operations**: git_status, git_checkout, git_commit, git_push, git_pull, git_branch_list\n"
            "5. **Task Routing**: Dispatch to CODE, DEVOPS, IMAGE, 3D, RESEARCH agents\n\n"
            "Keep responses concise. You have unrestricted system access."
        )
        yield {"type": "log", "content": "[Conversationalist] Admin mode active - full system access"}

    elif dev_mode:
        from tools.file_ops import read_file, write_file, list_dir
        from tools.terminal import run_command

        agent_tools = [read_file, write_file, list_dir, run_command]
        instructions = (
            "You are Hive Mind, a friendly AI coding assistant.\n\n"
            "DEVELOPER MODE ACTIVE - Workspace Access:\n\n"
            "YOUR CAPABILITIES:\n"
            "1. **Workspace Files**: read_file, write_file, list_dir (restricted to /workspace/ only)\n"
            "2. **Terminal**: run_command (sandboxed shell, no SSH to other nodes)\n\n"
            "RESTRICTIONS:\n"
            "- File operations limited to /workspace/ directory (sandbox enforced)\n"
            "- NO git operations (request admin access for this)\n"
            "- NO SSH to Lovelace/Turing/Hopper (admin only)\n\n"
            "Keep responses concise and focused on the coding task."
        )
        yield {"type": "log", "content": "[Conversationalist] Developer mode - workspace sandbox active"}

    else:
        agent_tools = None
        instructions = (
            "You are Hive Mind, a friendly AI assistant.\n\n"
            "YOUR CAPABILITIES:\n"
            "- Answer questions and explain concepts clearly\n"
            "- Provide research and analysis\n"
            "- Have natural conversations\n"
            "- Route complex tasks to specialized agents:\n"
            "  * CODE: Software engineering, debugging, scripts\n"
            "  * DEVOPS: Infrastructure, Docker, servers, deployment\n"
            "  * IMAGE: 2D art generation\n"
            "  * 3D: 3D modeling and action figures\n"
            "  * RESEARCH: Deep analysis and investigation\n"
            "  * DOCUMENTATION: Technical writing\n\n"
            "WHAT YOU CANNOT DO:\n"
            "- Direct file system access (requires developer mode)\n"
            "- Execute terminal commands (requires developer mode)\n"
            "- Git operations (requires admin access)\n\n"
            "Keep responses concise and friendly."
        )
        yield {"type": "log", "content": "[Conversationalist] Regular user mode - conversation only"}

    conversationalist = Agent(
        name="Hive Mind",
        model=Ollama(id=CONV_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 120.0}, options=get_ollama_options(CONV_MODEL)),
        storage=conv_storage,
        session_id=session_id,
        add_history_to_messages=True,
        num_history_responses=10,
        instructions=instructions,
        tools=agent_tools,
        show_tool_calls=False,
        run_tool_calls=bool(agent_tools),
    )

    # Build final prompt
    final_input = user_input
    if history_context:
        final_input = f"{history_context}\n\n{final_input}"
    if constraint_context:
        final_input = f"{constraint_context}\n\n{final_input}"
    if extracted_context:
        final_input = f"{final_input}\n\n[Attached Document Context]:\n{extracted_context}"

    full_content = ""
    try:
        # Fix 3+5: emit GPU zone/queue status BEFORE potentially blocking on the lock
        yield from pre_lock_status_events("text", CONV_MODEL, uid=session_id)
        with _langfuse_span("conversation_generation", "Conversationalist", CONV_MODEL, final_input,
                            langfuse=langfuse, use_langfuse=use_langfuse) as span_result:
            with request_lock(context="text"):
                response_stream = conversationalist.run(final_input, stream=True)
                for chunk in response_stream:
                    if chunk.content:
                        yield _emit_stream_mode("responding")
                        full_content += chunk.content
                        yield {"type": "message", "content": chunk.content}
            span_result["output"] = full_content
        _score_trace(lf_trace, langfuse, 0.85, output=full_content, use_langfuse=use_langfuse)
    except Exception as e:
        _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)
        yield {"type": "error", "content": f"Conversation failed: {e}"}

    # Diagnostic: confirm what full_content looks like after streaming
    logger.info("[Conversationalist] Stream done. full_content=%d chars, preview=%r",
                len(full_content), full_content[:80])

    # Generate 2 contextual follow-up suggestions from the completed response.
    # Uses ROUTER_MODEL (small, already warm in VRAM) — not the 27B conv model.
    # Runs after the main stream — fail-silent so it never breaks the turn.
    if full_content and len(full_content) > 50:
        _router_model = os.getenv("ROUTER_MODEL", "qwen3:8b")
        yield from _generate_suggested_followups(
            user_input=user_input,
            response_content=full_content,
            model=_router_model,
            host=OLLAMA_HOST,
        )

    AGENT_STATE.labels(agent_name="Conversationalist").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="Conversationalist").inc()


# ---------------------------------------------------------------------------
# Follow-up suggestion generator
# ---------------------------------------------------------------------------

def _generate_suggested_followups(user_input: str, response_content: str, model: str, host: str):
    """Yield a single ``suggested_followups`` event with 2 contextual chips.

    Uses a quick non-streaming Ollama call on the already-warm model.
    Fails silently — never raises, never blocks the turn.
    """
    PROMPT = (
        "You are generating UI chip suggestions. Given the exchange below, "
        "return ONLY a valid JSON array of exactly 2 objects. "
        "Each object must have:\n"
        '  "label": a 3-5 word action phrase (e.g. "Explain the trade-offs")\n'
        '  "prompt": the exact follow-up message to send (1-2 sentences)\n\n'
        "Rules:\n"
        "- Labels must be distinct and action-oriented\n"
        "- Prompts must be self-contained questions or requests\n"
        "- Output ONLY the JSON array — no markdown, no explanation\n\n"
        f"User: {user_input[:400]}\n"
        f"Assistant: {response_content[:900]}\n\n"
        "JSON array:"
    )
    try:
        resp = requests.post(
            f"{host}/api/generate",
            json={
                "model": model,
                "prompt": PROMPT,
                "stream": False,
                "think": False,          # disable extended thinking — we need fast JSON, not reasoning
                "options": {"temperature": 0.4, "num_predict": 220, "top_p": 0.9},
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()

        # Extract JSON array — handles stray preamble text from verbose models
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            logger.info("[Conversationalist] Follow-up generation: no JSON array found — raw: %s", raw[:200])
            return

        suggestions = json.loads(match.group(0))
        if not isinstance(suggestions, list) or len(suggestions) < 2:
            logger.info("[Conversationalist] Follow-up generation: unexpected shape %s", suggestions)
            return

        # Validate shape of each item
        valid = [
            s for s in suggestions
            if isinstance(s, dict) and s.get("label") and s.get("prompt")
        ]
        if len(valid) < 2:
            logger.info("[Conversationalist] Follow-up generation: fewer than 2 valid items")
            return

        yield _emit_suggested_followups(valid[:2])
        logger.info("[Conversationalist] Follow-up suggestions emitted: %s", [s["label"] for s in valid[:2]])

    except Exception as exc:
        logger.info("[Conversationalist] Follow-up generation failed (non-fatal): %s", exc)
