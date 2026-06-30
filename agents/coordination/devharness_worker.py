"""
devharness_worker.py — shared DevHarness worker runner for Swarm workers.

This module is called from both:
  - coordination/executor.py  (_run_worker DevHarness branch, Swarm workers)
  - main.py                   (_run_subagent, Task subagents)

It generalises the logic from main.py::_run_subagent into a synchronous
wrapper that matches the phidata _run_worker contract:
  run_devharness_worker(session, worker_id, role, scope, prompt, all_tool_defs) -> str

The function updates WorkerState, writes to the session scratchpad, and
pushes agent_event + file_change dicts into session.file_change_queue so
the orchestrator's existing drain-and-yield pipeline surfaces them in the UI.

Workers are fully autonomous and do NOT escalate (they run on the
role-assigned model only).  Escalation is a user-facing harness concept; Swarm
workers are orchestrated by the coordinator.  Workers also cannot spawn Task
subagents (depth cap = 1, same rule as existing _run_subagent).
"""

from __future__ import annotations

import asyncio
import logging
import time

from logger_setup import setup_logger

from config import (
    ANALYST_MODEL, CODER_MODEL, DEVOPS_MODEL,
    RESEARCHER_MODEL, VERIFIER_MODEL, SWARM_ARCHITECT_MODEL,
)
from coordination.session import CoordinatorSession, WorkerState

logger = setup_logger("devharness_worker")

# Roles that can be run as DevHarness workers.  Phase A focuses on
# coder/devops/architect; researcher/analyst/verifier added in Phase C.
DEVHARNESS_ELIGIBLE_ROLES = frozenset({
    "architect", "coder", "devops", "researcher", "analyst", "verifier",
})

# Swarm architect is a design/planning role → reasoning model
# (SWARM_ARCHITECT_MODEL), decoupled from the code-solver ARCHITECT_MODEL the
# MarsRL chat path uses.  See config.py for the rationale.
_ROLE_MODELS: dict[str, str] = {
    "coder": CODER_MODEL,
    "architect": SWARM_ARCHITECT_MODEL,
    "devops": DEVOPS_MODEL,
    "researcher": RESEARCHER_MODEL,
    "analyst": ANALYST_MODEL,
    "verifier": VERIFIER_MODEL,
}

# Tool names allowed per role (subset of DEV_TOOL_DEFINITIONS + kb_search).
# Task is excluded for all roles — no recursive subagent spawning.
_ROLE_ALLOWED_TOOLS: dict[str, frozenset] = {
    "coder": frozenset({
        "read_file", "write_file", "edit_file", "list_directory",
        "glob", "grep", "run_command", "git", "TodoWrite",
        "web_search", "web_fetch", "kb_search",
    }),
    "architect": frozenset({
        "read_file", "write_file", "edit_file", "list_directory",
        "glob", "grep", "run_command", "git", "TodoWrite",
        "web_search", "web_fetch", "kb_search",
    }),
    "devops": frozenset({
        "read_file", "write_file", "edit_file", "list_directory",
        "glob", "grep", "run_command", "git", "TodoWrite",
        "web_search", "web_fetch",
    }),
    "researcher": frozenset({
        "read_file", "list_directory", "glob", "grep",
        "web_search", "web_fetch", "TodoWrite",
    }),
    "analyst": frozenset({
        "read_file", "list_directory", "glob", "grep", "TodoWrite",
    }),
    "verifier": frozenset({
        "read_file", "list_directory", "glob", "grep",
    }),
}

_ROLE_SYSTEM: dict[str, str] = {
    "coder": (
        "You are a coder in a multi-agent swarm working on a codebase task in /workspace. "
        "Use read_file/glob/grep to understand the code before changing it. "
        "Use edit_file for precise edits to existing files; reserve write_file for new files. "
        "Use run_command to run tests and verify your changes. "
        "Use kb_search to look up existing patterns and architectural decisions in the knowledge base. "
        "Use TodoWrite to plan multi-step work. "
        "End with a concise summary of all changes made."
    ),
    "architect": (
        "You are an architect in a multi-agent swarm working on a codebase task in /workspace. "
        "Design and implement solutions — explore structure with read_file/glob/grep, "
        "apply precise edits with edit_file, and look up prior art with kb_search. "
        "Use TodoWrite to plan multi-step work. "
        "End with a concise summary of all changes made and key design decisions."
    ),
    "devops": (
        "You are a devops engineer in a multi-agent swarm working in /workspace. "
        "Manage infrastructure, configuration, CI, and deployment tasks using "
        "read_file, edit_file, glob, grep, run_command, and git. "
        "End with a summary of all changes made and any commands that need to run in production."
    ),
    "researcher": (
        "You are a researcher in a multi-agent swarm. Investigate the given question thoroughly. "
        "Use web_search and web_fetch to find up-to-date information, and read_file/glob/grep "
        "to search the local codebase. "
        "Provide factual, well-structured findings with sources. State uncertainty explicitly."
    ),
    "analyst": (
        "You are a data analyst in a multi-agent swarm. Analyse the provided information "
        "and produce thorough, evidence-backed analysis. "
        "Use read_file and grep to examine relevant files. "
        "Structure your output with clear headings and supporting evidence."
    ),
    "verifier": (
        "You are a verifier with fresh eyes reviewing the work product against the given criteria. "
        "Check for correctness, completeness, and consistency. "
        "Use read_file/glob/grep to examine the actual code and files. "
        "Report issues clearly and give a PASS/FAIL verdict with reasoning."
    ),
}

_BRIEF_LEN = 80
_MAX_WORKER_ITERS = 16


def _brief(obj, n: int = _BRIEF_LEN) -> str:
    s = str(obj)
    return s if len(s) <= n else s[:n] + "…"


def _chunk_to_dict(ch) -> dict | None:
    """Convert a StreamChunk to the dict format the orchestrator SSE pipeline expects.

    Returns None for chunk types that should not be forwarded (content, tool_start, etc.).
    The returned dict is placed directly into session.file_change_queue and yielded
    by _drain_file_changes() into the SSE stream.
    """
    if ch.type == "file_change":
        return {"type": "file_change", "content": ch.data or {}}
    if ch.type == "agent_event":
        d: dict = {"type": "agent_event", "content": ch.content or ""}
        if ch.agent_name:
            d["agent_name"] = ch.agent_name
        if ch.event_type:
            d["event_type"] = ch.event_type
        return d
    if ch.type == "todo":
        return {"type": "todo", "content": ch.data or {"todos": []}}
    return None


def _exec_sandbox(tool_name: str, args: dict, session_queue) -> str:
    """Run a sandbox tool, route file_change events directly into the session queue.

    The file_change sink collects raw dicts ({"type":"file_change","content":{...}})
    and pushes them into session_queue so the orchestrator's drain-and-yield loop
    surfaces them in the UI while the worker is still running.
    """
    from tools.sandbox_ops import execute_tool as _sandbox_execute
    from tools.file_change_sink import set_file_change_sink
    collected: list[dict] = []
    set_file_change_sink(collected.append)
    try:
        result = _sandbox_execute(tool_name, args)
    finally:
        set_file_change_sink(None)
    for fc in collected:
        try:
            session_queue.put_nowait(fc)
        except Exception:
            pass
    return result


def _exec_mcp(session_id: str, dev_name: str, args: dict) -> str:
    """Execute a mounted MCP tool (web_search/web_fetch) under a minted ephemeral card."""
    _DEV_MCP = {
        "web_search": ("hive.browser.search", "browser_search"),
        "web_fetch": ("hive.browser.fetch", "browser_fetch"),
    }
    mapping = _DEV_MCP.get(dev_name)
    if not mapping:
        return f"Unknown MCP tool: {dev_name}"
    hive_name, _cap = mapping
    try:
        from security.token_issuer import EphemeralAgentCard, get_token_issuer
        from mcp.tool_hooks import ToolHookRegistry
        caps = sorted({c for (_, c) in _DEV_MCP.values()})
        card = EphemeralAgentCard(
            template_id="swarm_worker_dev", template_version="1.0",
            agent_name=f"SwarmWorker_{session_id}", activated_capabilities=caps,
            security_level="L2_USER", user_id=session_id, session_id=session_id, expiry_hours=2,
        )
        token = get_token_issuer().issue_token(card)
        reg = ToolHookRegistry()
        result = reg.execute(hive_name, args, f"Bearer {token}")
        texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        body = "\n".join(t for t in texts if t) or "(no output)"
        return ("Error: " + body) if result.get("isError") else body
    except Exception as e:
        logger.warning(f"[devharness_worker] MCP tool {dev_name} failed: {e}")
        return f"MCP tool error: {e}"


def _exec_kb_search(args: dict) -> str:
    from tools.kb_tool import kb_search
    return kb_search(args.get("query", ""), limit=args.get("limit", 5))


def _exec_todowrite(args: dict):
    from dev_harness.history import StreamChunk
    todos = args.get("todos", [])
    done = sum(1 for t in todos if t.get("status") == "completed")
    chunk = StreamChunk(type="todo", content="", data={"todos": todos})
    return f"Updated todo list ({done}/{len(todos)} complete).", [chunk]


async def _run_async(
    session_id: str,
    file_change_queue,
    role: str,
    system_prompt: str,
    model: str,
    tool_defs: list,
    prompt: str,
    pioneer: dict | None = None,
):
    """Async core: runs the DevHarness loop and returns (summary_text, [dict_events])."""
    from dev_harness.history import History, UserMessage, StreamChunk
    from dev_harness.loop import DevHarness
    from dev_harness.router import ModelRouter
    from providers.ollama_provider import OllamaProvider

    if pioneer:
        system_prompt = (
            f"You embody the spirit of {pioneer['full_name']} — {pioneer['motto']}.\n\n"
            + system_prompt
        )
    history = History(system=system_prompt, turns=[UserMessage(prompt)])
    primary = OllamaProvider(model=model)
    # Workers don't escalate — the coordinator assigns their model, not the harness.
    router = ModelRouter(primary=primary, escalation_targets=[], enabled=False)

    agent_name = f"swarm:{role}"
    emitted_dicts: list[dict] = [
        {"type": "agent_event",
         "content": f"Started [{role}]: {_brief(prompt, 120)}",
         "agent_name": agent_name,
         "event_type": "status"},
    ]
    parts: list[str] = []

    async def _exec(cid: str, tname: str, targs: dict):
        if tname == "TodoWrite":
            result, chunks = _exec_todowrite(targs)
            return result, chunks
        if tname == "kb_search":
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _exec_kb_search, targs)
        if tname in ("web_search", "web_fetch"):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, _exec_mcp, session_id, tname, targs
            )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, _exec_sandbox, tname, targs, file_change_queue
        )

    try:
        async for ch in DevHarness(max_iterations=_MAX_WORKER_ITERS).run(
            history, tool_defs, _exec, router
        ):
            if ch.type == "content":
                parts.append(ch.content)
            else:
                d = _chunk_to_dict(ch)
                if d is not None:
                    emitted_dicts.append(d)
    except Exception as e:
        logger.error(f"[devharness_worker] {role} worker failed: {e}", exc_info=True)
        emitted_dicts.append({
            "type": "agent_event",
            "content": f"Worker error: {e}",
            "agent_name": agent_name,
            "event_type": "error",
        })
        return f"Worker ({role}) failed: {e}", emitted_dicts

    summary = "".join(parts).strip() or "(worker produced no summary)"
    emitted_dicts.append({
        "type": "agent_event",
        "content": "Finished.",
        "agent_name": agent_name,
        "event_type": "status",
    })
    return summary, emitted_dicts


def run_devharness_worker(
    session: CoordinatorSession,
    worker_id: str,
    role: str,
    scope: str,
    prompt: str,
    all_tool_defs: list,
) -> str:
    """Synchronous worker runner — matches the phidata _run_worker return contract.

    Called from ThreadPoolExecutor threads (parallel workers) or the orchestrator
    main thread (sequential implementation workers).  Updates WorkerState, writes
    the result to the session scratchpad, and drains accumulated agent_event /
    file_change / todo dicts into session.file_change_queue for the SSE generator.
    """
    worker = session.workers[worker_id]
    worker.state = WorkerState.RUNNING
    worker.started_at = time.time()
    try:
        import swarm_run_store
        swarm_run_store.upsert_worker(
            session.coordination_id, worker_id, worker.role, worker.task,
            worker.phase, (worker.pioneer or {}).get("name"), status="running",
            started_at=worker.started_at,
        )
    except Exception:
        pass

    role_lower = role.lower()
    model = _ROLE_MODELS.get(role_lower, SWARM_ARCHITECT_MODEL)
    system_prompt = _ROLE_SYSTEM.get(role_lower, _ROLE_SYSTEM["coder"])
    allowed = _ROLE_ALLOWED_TOOLS.get(role_lower, _ROLE_ALLOWED_TOOLS["coder"])
    tool_defs = [t for t in all_tool_defs if t["function"]["name"] in allowed]

    try:
        pioneer_name = worker.pioneer.get("full_name", "") if worker.pioneer else ""
        logger.info(
            "[devharness_worker] %s (%s, %s) → %s",
            worker_id, role_lower, model, pioneer_name or "no pioneer",
        )
        if worker.cancel_flag.is_set():
            worker.state = WorkerState.CANCELLED
            return ""

        summary, event_dicts = asyncio.run(_run_async(
            session.session_id,
            session.file_change_queue,
            role_lower,
            system_prompt,
            model,
            tool_defs,
            prompt,
            pioneer=worker.pioneer,
        ))

        # Push non-file_change events (agent_event, todo) collected during the run.
        # file_change events were already pushed into the queue inside _exec_sandbox.
        for d in event_dicts:
            if d.get("type") != "file_change":
                try:
                    session.file_change_queue.put_nowait(d)
                except Exception:
                    pass

        worker.result = summary
        worker.state = WorkerState.COMPLETED
        worker.completed_at = time.time()
        try:
            swarm_run_store.upsert_worker(
                session.coordination_id, worker_id, worker.role, worker.task,
                worker.phase, (worker.pioneer or {}).get("name"), status="completed",
                output=summary, completed_at=worker.completed_at,
            )
        except Exception:
            pass

        safe_role = "".join(c if c.isalnum() or c in "_-" else "_" for c in role_lower)
        filename = f"{worker.phase}_{safe_role}_{worker_id}.md"
        session.write_to_scratchpad(filename, f"# {role} — {worker.task}\n\n{summary}")

        return summary

    except Exception as e:
        worker.state = WorkerState.FAILED
        worker.error = str(e)
        worker.completed_at = time.time()
        try:
            swarm_run_store.upsert_worker(
                session.coordination_id, worker_id, worker.role, worker.task,
                worker.phase, (worker.pioneer or {}).get("name"), status="failed",
                output=worker.error, completed_at=worker.completed_at,
            )
        except Exception:
            pass
        logger.error(
            f"[devharness_worker] worker {worker_id} ({role}) failed: {e}", exc_info=True
        )
        return f"ERROR: {e}"
