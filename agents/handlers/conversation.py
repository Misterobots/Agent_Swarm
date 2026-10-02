"""handlers/conversation.py — CONVERSATION intent handler (3-tier access control)."""

import json
import logging
import re

import requests

from phi.agent import Agent

from providers.model_client import ProviderNotServed, is_honourable_pick, model_client, provider_of

from metrics import AGENT_STATE, WORKFLOW_STEPS
from utils.gpu_queue import request_lock, get_best_host_for_model, pre_lock_status_events
from handlers.base import (
    _emit_stream_mode, _emit_turn_metadata, _score_trace, _langfuse_span,
    _emit_suggested_followups, tool_events_from_chunk,
)

logger = logging.getLogger("Router")


def handle_conversation(user_input: str, ctx: dict):
    """Generator — the Memex conversationalist, with 3-tier access control.

    "Hive Mind" was the name this agent introduced itself by. The owner's ruling on
    2026-09-29 is that the assistant is Memex; the name stays here rather than being read
    from config because a turn has to say who is answering even when the store cannot be
    reached. `Hive Mind Architect` in handlers/architect.py is a *role* and was left alone.
    """
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

    yield _emit_turn_metadata(turn_id, "Memex", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    yield {"type": "status", "content": "💬 Memex: Thinking..."}
    AGENT_STATE.labels(agent_name="Conversationalist").set(2)

    # Model resolution. Three cases, in this order:
    #
    # 1. fast_mode (the "hive-fast" sentinel) forces the small ROUTER_MODEL — already
    #    hot in VRAM from the intent classifier. No GPU eviction, fastest path.
    # 2. The client named a model, and that name is honoured. It used to be refused
    #    outright, because the frontend also sends UI *tier* names like "Home-AI-Swarm"
    #    that are not Ollama identifiers — but discarding every named model to guard
    #    against the tier case is what made the picker decide nothing on a local turn
    #    while a gateway turn honoured it. Two meanings for one control. The tier names
    #    are a short closed list, so `is_honourable_pick` separates the two cases.
    #    (Owner's ruling 2026-09-29: honour the pick, per session — plan D8(d), D9.)
    # 3. Nothing honourable was named: the template registry decides, default qwen3:8b.
    requested_model = (ctx.get("model") or "").strip()
    if fast_mode:
        CONV_MODEL = os.getenv("ROUTER_MODEL", "qwen3:8b")
        yield {"type": "thought", "content": f"→ Hive Fast: conversation on {CONV_MODEL} (router model, already hot)"}
    elif is_honourable_pick(requested_model):
        CONV_MODEL = requested_model
    else:
        CONV_MODEL = _resolve_model_for_intent(
            "CONVERSATION",
            os.getenv("CONV_MODEL", os.getenv("PRIMARY_MODEL", "qwen3:8b")),
        )
        if requested_model:
            # A name was sent and is being set aside. Said rather than done quietly —
            # silently substituting the model is the behaviour this block used to have
            # on every single turn.
            yield {
                "type": "thought",
                "content": f"→ {requested_model} is a UI tier name, not a model; answering on {CONV_MODEL}",
            }

    # Who serves the id is decided in one place, before any Ollama-specific option is
    # computed. Doing it in the other order is what made a gateway tag look like a local
    # model: `get_best_host_for_model` will happily name a machine that has never heard
    # of the id it was asked about.
    _provider_backed = provider_of(CONV_MODEL, owner_id) is not None
    _model_options: dict = {}
    if not _provider_backed:
        _model_options = get_ollama_options(CONV_MODEL)
        try:
            from providers.qwen_context import resolve_qwen_context
            _context = resolve_qwen_context(
                CONV_MODEL,
                ctx.get("context_profile"),
                task_mode="project" if dev_mode else "chat",
            )
            if _context.effective_tokens:
                _model_options["num_ctx"] = _context.effective_tokens
        except (ImportError, ValueError):
            pass

    try:
        MODEL_CLIENT = model_client(CONV_MODEL, uid=owner_id, options=_model_options or None)
    except ProviderNotServed as exc:
        # Refused by name rather than answered by whatever else is warm. A key lookup
        # that fails is also the one case where printing `exc` could not leak anything:
        # the exception text names the provider, never the credential.
        yield {"type": "log", "content": f"[Conversationalist] {exc}"}
        yield {"type": "error", "content": str(exc)}
        AGENT_STATE.labels(agent_name="Conversationalist").set(1)
        return

    # The follow-up generator below runs on ROUTER_MODEL, not on the conversation model,
    # so its host has to be resolved from the model it actually uses. It was resolved
    # from CONV_MODEL, which only looked correct while every model was an Ollama tag.
    OLLAMA_HOST = get_best_host_for_model(os.getenv("ROUTER_MODEL", "qwen3:8b"))

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
            "You are Memex, the AI assistant for the Agent Swarm infrastructure.\n\n"
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
            "You are Memex, a friendly AI coding assistant.\n\n"
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
            "You are Memex, a friendly AI assistant.\n\n"
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
        name="Memex",
        # Built by providers.model_client, which is the only thing that decides whether an
        # id is served by a GPU in this room or by a provider key the runtime holds. The
        # Agent itself is unchanged — same storage, history, tools and instructions — which
        # is the whole point: a gateway model gets the assistant, not a bare completion.
        model=MODEL_CLIENT,
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
    # Owned per turn: the Agent re-yields its accumulated tool list on every step, so these
    # are what stop one call being announced to the desktop twice.
    _seen_tool_starts = set()
    _seen_tool_results = set()
    try:
        # Fix 3+5: emit GPU zone/queue status BEFORE potentially blocking on the lock
        yield from pre_lock_status_events("text", CONV_MODEL, uid=session_id)
        with _langfuse_span("conversation_generation", "Conversationalist", CONV_MODEL, final_input,
                            langfuse=langfuse, use_langfuse=use_langfuse) as span_result:
            with request_lock(context="text"):
                # The flag belongs on the *call*, not the Agent. `run()` takes its own
                # `stream_intermediate_steps` (default False) and `_run` assigns it over the
                # instance attribute before anything is yielded, so a constructor value is
                # silently discarded — measured, not inferred: with it set on the Agent only,
                # a turn on `qwen/qwen3.8-27b` ran `list_dir` (the answer carried the real
                # directory entries) and surfaced zero tool events.
                # With it on the call, every step shares this one stream, which is why the
                # loop below routes on event name rather than on the presence of content.
                response_stream = conversationalist.run(final_input, stream=True,
                                                         stream_intermediate_steps=True)
                for chunk in response_stream:
                    # `stream_intermediate_steps` shares this stream with the Agent's own
                    # step markers, so the event name — not the presence of content — has
                    # to decide what counts as the answer. "Run started" and "Updating
                    # memory" carry literal labels, and the closing run_completed carries
                    # the *entire* answer again; reading content alone would splice all
                    # three into the reply.
                    event = getattr(chunk, "event", None) or "RunResponse"
                    if event in ("ToolCallStarted", "ToolCallCompleted"):
                        for tool_event in tool_events_from_chunk(chunk, _seen_tool_starts, _seen_tool_results):
                            yield tool_event
                        continue
                    if event != "RunResponse":
                        continue
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
