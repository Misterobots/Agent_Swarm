"""Worker execution — run_worker, agent factory, JWT child card derivation."""

import os
import time

from phi.agent import Agent, RunResponse
from phi.model.ollama import Ollama

from config import ARCHITECT_MODEL
from logger_setup import setup_logger
from utils.gpu_queue import get_swarm_worker_host
from coordination.session import CoordinatorSession, WorkerState

logger = setup_logger("Lamport")

try:
    from security.token_issuer import (
        EphemeralAgentCard, get_token_issuer, get_token_validator, derive_child_card,
    )
    from security.execution_context import set_current_token, get_current_token
    _JWT_AVAILABLE = True
except ImportError:
    _JWT_AVAILABLE = False

_ROLE_CAPS: dict[str, list[str]] = {
    "architect": ["file_read", "file_write", "terminal_exec", "terminal_read", "model_generate", "git_read", "git_write"],
    "coder": ["file_read", "file_write", "terminal_exec", "terminal_read", "model_generate", "git_read"],
    "devops": ["file_read", "file_write", "terminal_exec", "terminal_read", "api_call", "resource_access"],
    "analyst": ["model_generate", "api_call", "file_read"],
    "researcher": ["model_generate", "api_call", "file_read"],
    "verifier": ["model_generate", "file_read"],
}


def _run_worker(
    session: CoordinatorSession,
    worker_id: str,
    agent: Agent,
    prompt: str,
    child_token: str | None = None,
) -> str:
    """
    Execute a single worker agent synchronously.
    Called from thread pool for parallel execution.
    """
    worker = session.workers[worker_id]
    worker.state = WorkerState.RUNNING
    worker.started_at = time.time()

    if child_token and _JWT_AVAILABLE:
        set_current_token(child_token)

    # Register a file_change sink so write_file() emits activity chips into the
    # SSE stream.  The sink is thread-local; the main generator drains the queue.
    try:
        from tools.file_ops import set_file_change_sink
        set_file_change_sink(session.file_change_queue.put_nowait)
    except Exception:
        pass

    try:
        if worker.cancel_flag.is_set():
            worker.state = WorkerState.CANCELLED
            return ""

        response: RunResponse = agent.run(prompt)

        _raw = response.content if response and response.content else "No output"
        # response.content can be a dict when the model returns valid JSON (phidata auto-parses
        # it even without json_mode=True).  Downstream code (synthesizer, team store, scratchpad)
        # all expect a plain string, so coerce here at the source.
        if isinstance(_raw, (dict, list)):
            import json as _json
            result = _json.dumps(_raw, indent=2, ensure_ascii=False)
        elif not isinstance(_raw, str):
            result = str(_raw)
        else:
            result = _raw
        worker.result = result
        worker.state = WorkerState.COMPLETED
        worker.completed_at = time.time()

        safe_role = "".join(c if c.isalnum() or c in "_-" else "_" for c in worker.role.lower())
        filename = f"{worker.phase}_{safe_role}_{worker_id}.md"
        session.write_to_scratchpad(
            filename,
            f"# {worker.role} — {worker.task}\n\n{result}",
        )

        return result
    except Exception as e:
        worker.state = WorkerState.FAILED
        worker.error = str(e)
        worker.completed_at = time.time()
        logger.error(f"[Coordinator] Worker {worker_id} ({worker.role}) failed: {e}")
        return f"ERROR: {e}"
    finally:
        # Always clear the thread-local sink so stale callbacks don't leak into
        # any future work that reuses this thread from the pool.
        try:
            from tools.file_ops import set_file_change_sink
            set_file_change_sink(None)
        except Exception:
            pass


def _get_agent_for_role(role: str, session_id: str = None, scope: str = "unknown") -> Agent:
    """
    Factory: map coordinator roles to Agent_Swarm team agents.

    When scope=='codebase', architect/coder/devops use Leibniz (file system tools).
    For external/research scope they use a plain LLM agent.
    """
    role_lower = role.lower()
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    if role_lower in ("architect", "coder", "devops"):
        if scope == "codebase":
            from leibniz_agent import get_architect_agent
            return get_architect_agent(session_id=session_id)
        else:
            host = get_swarm_worker_host(ARCHITECT_MODEL)
            return Agent(
                name=f"{role.title()} Worker",
                model=Ollama(id=ARCHITECT_MODEL, host=host, client_kwargs={"timeout": 300.0}),
                instructions=[
                    f"You are a {role_lower} expert. Analyse the problem and produce a clear, actionable plan.",
                    "Do NOT attempt to access files or execute commands.",
                    "Focus on research-quality output: recommendations, step-by-step plans, and rationale.",
                ],
                show_tool_calls=False,
            )

    elif role_lower == "analyst":
        host = get_swarm_worker_host(ARCHITECT_MODEL)
        return Agent(
            name="Data Analyst Worker",
            model=Ollama(id=ARCHITECT_MODEL, host=host, client_kwargs={"timeout": 300.0}),
            instructions=["You are a data analyst. Provide thorough analysis with supporting evidence."],
            show_tool_calls=False,
        )

    elif role_lower == "researcher":
        host = get_swarm_worker_host(ARCHITECT_MODEL)
        return Agent(
            name="Research Worker",
            model=Ollama(id=ARCHITECT_MODEL, host=host, client_kwargs={"timeout": 300.0}),
            instructions=[
                "You are a research worker. Investigate the given question thoroughly.",
                "Provide factual, well-structured findings.",
                "Include specific details: file paths, function names, version numbers.",
                "If you are unsure about something, say so explicitly.",
            ],
            show_tool_calls=False,
        )

    elif role_lower == "verifier":
        host = get_swarm_worker_host(ARCHITECT_MODEL)
        return Agent(
            name="Verification Worker",
            model=Ollama(id=ARCHITECT_MODEL, host=host, client_kwargs={"timeout": 300.0}),
            instructions=[
                "You are a verification worker with fresh eyes.",
                "Review the work product against the verification criteria.",
                "Check for correctness, completeness, and consistency.",
                "Report any issues found and give a PASS/FAIL verdict with reasoning.",
            ],
            show_tool_calls=False,
        )

    else:
        from leibniz_agent import get_architect_agent
        return get_architect_agent(session_id=session_id)


def _derive_worker_token(parent_token: str | None, role: str, task_description: str) -> str | None:
    """Derive a child JWT-ACE token for a coordinator worker."""
    if not _JWT_AVAILABLE or not parent_token:
        return None
    try:
        validator = get_token_validator()
        parent_card = validator.validate_token(parent_token)
        caps = _ROLE_CAPS.get(role.lower(), ["model_generate", "file_read"])
        child_card = derive_child_card(
            parent_card,
            child_template_id=f"coordinator_worker_{role.lower()}",
            child_agent_name=f"Worker:{role}",
            child_capabilities=caps,
            child_security_level="L2_USER",
            task_description=task_description,
        )
        issuer = get_token_issuer()
        return issuer.issue_token(child_card)
    except Exception as e:
        logger.warning(f"[Coordinator] Child card derivation failed (non-fatal): {e}")
        return None
