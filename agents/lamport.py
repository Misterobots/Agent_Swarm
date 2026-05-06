"""
Coordinator Mode — Multi-Worker Orchestration System

Phase 1 Integration: Hybrid Python mechanics + LLM synthesis

Architecture:
    User Task → Decompose (LLM) → Research Workers (parallel)
    → Synthesis (LLM) → Implementation Workers (serial)
    → Verification Worker → Final Response

Based on OpenClaude's coordinatorMode pattern, adapted for Agent_Swarm's
streaming generator architecture and Phi-Agent team system.
"""

import os
import json
import time
import threading
import uuid
from pathlib import Path
from typing import Generator, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

import requests
from phi.agent import Agent, RunResponse
from phi.model.ollama import Ollama

from logger_setup import setup_logger
from config import AGNO_DB_URL, ARCHITECT_MODEL
from utils.gpu_queue import request_lock, get_best_host_for_model, get_swarm_worker_host

logger = setup_logger("Lamport")

# --- JWT-ACE child card derivation (graceful fallback if unavailable) ---
try:
    from security.token_issuer import (
        EphemeralAgentCard, get_token_issuer, get_token_validator, derive_child_card,
    )
    from security.execution_context import set_current_token, get_current_token
    _JWT_AVAILABLE = True
except ImportError:
    _JWT_AVAILABLE = False

# --- MemPalace team memory (graceful fallback if unavailable) ---
def _team_store(team_id: str, key: str, value: str, author: str = "lamport"):
    try:
        from mempalace_client import mempalace
        mempalace.team_store(team_id, key, value, author_agent=author)
    except Exception as e:
        logger.debug(f"[Coordinator] Team memory store failed (non-fatal): {e}")


def _team_clear(team_id: str):
    try:
        from mempalace_client import mempalace
        mempalace.team_clear(team_id)
    except Exception as e:
        logger.debug(f"[Coordinator] Team memory clear failed (non-fatal): {e}")


# --- MemPalace user palace: per-user project registry ---
def _palace_project_lookup(owner_id: str, query: str, limit: int = 3) -> list[dict]:
    """Search the user's 'projects' room in their palace wing for matching projects."""
    if not owner_id:
        return []
    try:
        from mempalace_client import mempalace
        results = mempalace.search(query, agent_id=owner_id, domain="projects", limit=limit)
        return results or []
    except Exception as e:
        logger.debug(f"[Coordinator] Palace project lookup failed (non-fatal): {e}")
        return []


def _palace_project_save(owner_id: str, slug: str, url: str, description: str, path: str = None) -> None:
    """Record a completed project in the user's palace wing under room 'projects'."""
    if not owner_id:
        return
    try:
        from datetime import datetime as _dt
        from mempalace_client import mempalace
        content = (
            f"PROJECT: {slug}\n"
            f"URL: {url}\n"
            f"PATH: {path or f'user_projects/{slug}/index.html'}\n"
            f"DESCRIPTION: {description}\n"
            f"STATUS: active\n"
            f"BUILT: {_dt.now().strftime('%Y-%m-%d')}\n"
        )
        mempalace.store(
            content,
            memory_type="episodic",
            domain="projects",
            agent_id=owner_id,
        )
        logger.info(f"[Coordinator] Saved project '{slug}' to palace wing for '{owner_id}'")
    except Exception as e:
        logger.debug(f"[Coordinator] Palace project save failed (non-fatal): {e}")


# --- Scratchpad Root ---
SCRATCHPAD_ROOT = Path(__file__).parent / "scratchpad"

# ---------------------------------------------------------------------------
# Pioneer persona pool — display names for ephemeral Lamport workers
# Each role has a ranked pool; workers pick the first name not already in use.
# ---------------------------------------------------------------------------
WORKER_PIONEERS: dict[str, list[dict]] = {
    "researcher": [
        {"name": "Shannon",  "full_name": "Claude Shannon",     "motto": "Information is the resolution of uncertainty."},
        {"name": "Minsky",   "full_name": "Marvin Minsky",      "motto": "Minds are what brains do."},
        {"name": "Johnson",  "full_name": "Katherine Johnson",  "motto": "Like what you do, and then you will do your best."},
    ],
    "architect": [
        {"name": "Babbage",  "full_name": "Charles Babbage",    "motto": "Errors using inadequate data are far less than those using no data at all."},
        {"name": "Dijkstra", "full_name": "Edsger Dijkstra",    "motto": "Simplicity is a prerequisite for reliability."},
        {"name": "Hamilton", "full_name": "Margaret Hamilton",  "motto": "There was no choice but to be pioneers."},
    ],
    "coder": [
        {"name": "Knuth",    "full_name": "Donald Knuth",      "motto": "Programs are meant to be read by humans."},
        {"name": "Lovelace", "full_name": "Ada Lovelace",       "motto": "The Analytical Engine weaves algebraic patterns just as the Jacquard loom weaves flowers."},
        {"name": "Ritchie",  "full_name": "Dennis Ritchie",     "motto": "UNIX is basically a simple operating system, but you have to be a genius to understand the simplicity."},
    ],
    "devops": [
        {"name": "Cerf",     "full_name": "Vint Cerf",         "motto": "The internet is a reflection of our society."},
        {"name": "Torvalds", "full_name": "Linus Torvalds",    "motto": "Talk is cheap. Show me the code."},
        {"name": "Perlman",  "full_name": "Radia Perlman",     "motto": "The world would be a better place if more engineers cared about the broader context of their work."},
    ],
    "analyst": [
        {"name": "Codd",     "full_name": "Edgar Codd",         "motto": "Data is a precious thing and will last longer than the systems themselves."},
        {"name": "Hopper",   "full_name": "Grace Hopper",        "motto": "The most dangerous phrase in the language is: we've always done it this way."},
        {"name": "Boole",    "full_name": "George Boole",        "motto": "No matter how correct a mathematical theorem may appear, it may be disproved by a single contradiction."},
    ],
    "verifier": [
        {"name": "Hoare",  "full_name": "Tony Hoare",        "motto": "There are two ways to write error-free programs; only the third works."},
        {"name": "Turing", "full_name": "Alan Turing",       "motto": "We can only see a short distance ahead, but we can see plenty there that needs to be done."},
        {"name": "Liskov", "full_name": "Barbara Liskov",    "motto": "Abstraction is the key to simplicity."},
    ],
}

def _pioneer_for_role(role: str) -> dict:
    """Return the primary pioneer persona dict for a given worker role (no dedup)."""
    pool = WORKER_PIONEERS.get(role.lower())
    if pool:
        return pool[0]
    return {"name": role.title(), "full_name": role.title(), "motto": ""}


def _pick_unique_pioneer(role: str, used_names: set[str]) -> dict:
    """Pick the first pioneer from the pool whose name is not in used_names."""
    pool = WORKER_PIONEERS.get(role.lower(), [])
    for candidate in pool:
        if candidate["name"] not in used_names:
            return candidate
    # All names in pool are taken — append a numeric suffix to the first entry
    base = pool[0] if pool else {"name": role.title(), "full_name": role.title(), "motto": ""}
    suffix = len([n for n in used_names if n.startswith(base["name"])]) + 1
    return {**base, "name": f"{base['name']}-{suffix}", "full_name": f"{base['full_name']} ({suffix})"}


class WorkerState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerInfo:
    """Tracks a single worker's lifecycle."""

    def __init__(self, worker_id: str, role: str, task: str, phase: str, pioneer: dict | None = None):
        self.worker_id = worker_id
        self.role = role
        self.task = task
        self.phase = phase
        self.pioneer: dict = pioneer or _pioneer_for_role(role)
        self.state = WorkerState.PENDING
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.cancel_flag = threading.Event()

    def cancel(self):
        self.cancel_flag.set()
        self.state = WorkerState.CANCELLED


class CoordinatorSession:
    """Manages a single coordination session with scratchpad and worker registry."""

    def __init__(self, session_id: str, owner_id: str = None):
        self.session_id = session_id
        self.owner_id = owner_id
        self.coordination_id = f"coord-{uuid.uuid4().hex[:8]}"
        self.workers: dict[str, WorkerInfo] = {}
        self.scratchpad_dir = SCRATCHPAD_ROOT / session_id / self.coordination_id
        self.scratchpad_dir.mkdir(parents=True, exist_ok=True)
        self.created_at = time.time()

    def register_worker(self, role: str, task: str, phase: str) -> str:
        worker_id = f"w-{uuid.uuid4().hex[:6]}"
        used_names = {w.pioneer["name"] for w in self.workers.values()}
        pioneer = _pick_unique_pioneer(role, used_names)
        self.workers[worker_id] = WorkerInfo(worker_id, role, task, phase, pioneer=pioneer)
        return worker_id

    def write_to_scratchpad(self, filename: str, content: str):
        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        (self.scratchpad_dir / safe_name).write_text(content, encoding="utf-8")

    def read_from_scratchpad(self, filename: str) -> Optional[str]:
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        path = self.scratchpad_dir / safe_name
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def list_scratchpad(self) -> list[str]:
        if not self.scratchpad_dir.exists():
            return []
        return [f.name for f in self.scratchpad_dir.iterdir() if f.is_file()]

    def get_all_scratchpad_content(self) -> str:
        if not self.scratchpad_dir.exists():
            return ""
        parts = []
        for f in sorted(self.scratchpad_dir.iterdir()):
            if f.is_file():
                parts.append(f"=== {f.name} ===\n{f.read_text(encoding='utf-8')}")
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# LLM helpers (the only two places the coordinator calls an LLM directly)
# ---------------------------------------------------------------------------

def _decompose_task(user_input: str, history_context: str = "") -> dict:
    """
    Use LLM to decompose a complex task into subtasks.
    Returns dict with research_tasks, implementation_tasks, verification_criteria.
    """
    decompose_model = os.getenv("COORDINATOR_MODEL", "qwen3.6:27b")
    host = get_swarm_worker_host(decompose_model)

    system_prompt = (
        "You are a task decomposition engine. Given a complex task, break it into phases.\n"
        "Output ONLY valid JSON with this structure:\n"
        "{\n"
        '  "summary": "One-sentence summary of the task",\n'
        '  "scope": "codebase|external|unknown",\n'
        '  "project_type": "existing|new|unknown",\n'
        '  "clarification_needed": false,\n'
        '  "clarification_question": null,\n'
        '  "research_tasks": [\n'
        '    {"role": "researcher|architect|analyst", "task": "specific research question"}\n'
        "  ],\n"
        '  "implementation_tasks": [\n'
        '    {"role": "architect|coder|devops", "task": "specific implementation step"}\n'
        "  ],\n"
        '  "verification_criteria": ["criterion 1", "criterion 2"]\n'
        "}\n\n"
        "Rules:\n"
        "- research_tasks run in PARALLEL\n"
        "- implementation_tasks run SERIALLY\n"
        "- Keep tasks focused and actionable\n"
        "- Use role names: researcher, architect, coder, devops, analyst\n"
        "- 2-5 research tasks, 1-4 implementation tasks, 1-3 verification criteria\n\n"
        "SCOPE RULES:\n"
        "- scope='codebase': task involves writing, reading, or modifying code in an existing or new project\n"
        "- scope='external': task involves research, explanation, analysis, or web lookups with no code changes\n"
        "- scope='unknown': cannot determine without more information\n"
        "- project_type='existing': working with/inside an existing codebase\n"
        "- project_type='new': creating a brand new project/app from scratch\n"
        "- project_type='unknown': cannot determine (use only when scope='codebase')\n\n"
        "AMBIGUITY CHECK: Before decomposing, evaluate whether the task has enough context to\n"
        "produce a correct and useful plan. If a single critical piece of information is missing\n"
        "that would fundamentally change the research approach (e.g. target platform, language,\n"
        "intended audience, desired outcome), set clarification_needed=true and provide a single,\n"
        "specific clarification_question. Only set this when truly necessary — most tasks should\n"
        "proceed. Default: clarification_needed=false, clarification_question=null."
    )

    prompt = f"{history_context}\n\nTask to decompose:\n{user_input}" if history_context else user_input

    try:
        resp = requests.post(
            f"{host}/api/generate",
            json={
                "model": decompose_model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.3, "num_predict": 1024},
            },
            timeout=60,
        )

        if resp.status_code == 200:
            raw = resp.json().get("response", "{}")
            parsed = json.loads(raw)
            # Validate structure — ensure required keys exist
            if "research_tasks" not in parsed or not parsed["research_tasks"]:
                parsed["research_tasks"] = [{"role": "researcher", "task": user_input}]
            if "implementation_tasks" not in parsed or not parsed["implementation_tasks"]:
                parsed["implementation_tasks"] = [{"role": "architect", "task": user_input}]
            if "verification_criteria" not in parsed or not parsed["verification_criteria"]:
                parsed["verification_criteria"] = ["Task completed correctly"]

            # --- Scope override: creation/build requests must always be codebase ---
            _BUILD_KEYWORDS = (
                "build", "make", "create", "develop", "implement", "write", "code",
                "generate a game", "generate a web", "generate an app",
                "a game", "a web app", "a website", "an app", "a tool",
            )
            _input_lower = user_input.lower()
            if parsed.get("scope") != "codebase" and any(kw in _input_lower for kw in _BUILD_KEYWORDS):
                logger.info(
                    f"[Coordinator] Scope override: '{parsed.get('scope')}' → 'codebase' "
                    f"(detected build intent in user request)"
                )
                parsed["scope"] = "codebase"
                if parsed.get("project_type") not in ("existing", "new"):
                    parsed["project_type"] = "new"

            return parsed
    except Exception as e:
        logger.error(f"[Coordinator] Task decomposition failed: {e}")

    # Fallback: single research + single implementation
    return {
        "summary": user_input[:200],
        "research_tasks": [{"role": "researcher", "task": user_input}],
        "implementation_tasks": [{"role": "architect", "task": user_input}],
        "verification_criteria": ["Task completed correctly"],
    }


def _synthesize_findings(findings: str, original_task: str) -> dict:
    """
    LLM synthesis step: Read all research findings and produce an implementation plan.
    Returns a dict: {"plan": str, "confidence": float, "ambiguity": float}

    confidence  — 0.0–1.0, how complete and correct the plan is
    ambiguity   — 0.0–1.0, how much unclear information remains (lower is better)
    """
    synth_model = os.getenv("COORDINATOR_MODEL", "qwen3.6:27b")
    host = get_swarm_worker_host(synth_model)

    system_prompt = (
        "You are a technical lead synthesizing research findings into an implementation plan.\n"
        "Rules:\n"
        "- Read ALL findings carefully\n"
        "- Identify key insights, constraints, and dependencies\n"
        "- Produce a clear, actionable implementation plan\n"
        "- Note any conflicts or gaps in the research\n"
        "- Be specific about file paths, function names, and technical details\n\n"
        "IMPORTANT: At the very end of your response, on its own line, output a JSON block:\n"
        '{"confidence": 0.92, "ambiguity": 0.03, "ambiguous_points": ["brief point 1", "brief point 2"]}\n'
        "confidence: 0.0–1.0 — how confident you are this plan is complete and correct\n"
        "ambiguity:  0.0–1.0 — how much unclear information remains (0 = none, 1 = all unclear)\n"
        "ambiguous_points: list of short strings describing EXACTLY what is unclear or under-specified (empty list if nothing is ambiguous)"
    )

    try:
        # Truncate findings to ~24k chars to stay within 32k context window
        MAX_FINDINGS_CHARS = 24000
        if len(findings) > MAX_FINDINGS_CHARS:
            findings = findings[:MAX_FINDINGS_CHARS] + "\n\n[...truncated for context window...]"

        prompt = (
            f"Original Task: {original_task}\n\n"
            f"Research Findings:\n{findings}\n\n"
            "Synthesize these findings into a concrete implementation plan."
        )

        resp = requests.post(
            f"{host}/api/generate",
            json={
                "model": synth_model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {"temperature": 0.4, "num_predict": 8192, "num_ctx": 32768},
            },
            timeout=240,
        )
        logger.info(f"[Coordinator] Synthesis HTTP {resp.status_code}, response_len={len(resp.text)}")

        if resp.status_code == 200:
            resp_json = resp.json()
            raw_text = resp_json.get("response", "")
            if not raw_text:
                logger.warning(f"[Coordinator] Synthesis empty response. done_reason={resp_json.get('done_reason')} eval_count={resp_json.get('eval_count')}")
            # Strip markdown code fences that models sometimes wrap JSON in
            import re as _re
            clean_text = _re.sub(r"```(?:json)?", "", raw_text, flags=_re.IGNORECASE).replace("```", "")
            # Parse the trailing confidence/ambiguity JSON block — handles multiline and single-line
            confidence = 0.80
            ambiguity = 0.15
            ambiguous_points = []
            plan_text = raw_text
            scores = None
            # Strategy 1: find last '{' and parse forward (handles multiline JSON)
            last_brace = clean_text.rfind("{")
            if last_brace != -1:
                try:
                    decoder = json.JSONDecoder()
                    candidate = clean_text[last_brace:].strip()
                    parsed, end_pos = decoder.raw_decode(candidate)
                    if "confidence" in parsed:
                        scores = parsed
                        # Remove the JSON block from plan_text regardless of position
                        # (model sometimes puts the JSON block at the start, not the end)
                        json_start = raw_text.rfind("{")
                        json_end = json_start + end_pos
                        text_before = raw_text[:json_start].rstrip()
                        text_after = raw_text[json_end:].strip()
                        plan_text = text_before if text_before else text_after
                except (json.JSONDecodeError, ValueError):
                    pass
            # Strategy 2 (fallback): scan reversed lines for single-line JSON
            if scores is None:
                lines = raw_text.strip().splitlines()
                for line in reversed(lines):
                    stripped = line.strip()
                    if stripped.startswith("{") and "confidence" in stripped:
                        try:
                            scores = json.loads(stripped)
                            text_before = raw_text[: raw_text.rfind(stripped)].rstrip()
                            text_after = raw_text[raw_text.rfind(stripped) + len(stripped):].strip()
                            plan_text = text_before if text_before else text_after
                        except (json.JSONDecodeError, ValueError):
                            pass
                        break
            if scores:
                confidence = float(scores.get("confidence", 0.80))
                ambiguity = float(scores.get("ambiguity", 0.15))
                ambiguous_points = scores.get("ambiguous_points", [])
                if not isinstance(ambiguous_points, list):
                    ambiguous_points = []
                logger.info(f"[Coordinator] Synthesis JSON parsed: confidence={confidence:.0%} ambiguity={ambiguity:.0%} points={ambiguous_points}")
            else:
                logger.warning(f"[Coordinator] Could not parse synthesis JSON block from response tail: {raw_text[-200:]!r}")
            if not plan_text:
                # Model returned a response but plan text was empty after JSON extraction.
                # (Commonly: thinking model used full num_predict budget on <think> tokens,
                # or placed the JSON first leaving nothing before it.)
                plan_text = "Synthesis failed — no response from model."
                # Override confidence so the outer retry loop triggers instead of
                # proceeding with an empty/failed plan.
                confidence = 0.0
                ambiguity = 1.0
                logger.warning(
                    "[Coordinator] Synthesis plan_text empty after JSON extraction — "
                    f"forcing confidence=0.0 to trigger retry. raw_text len={len(raw_text)}, "
                    f"scores={scores}"
                )
            return {"plan": plan_text, "confidence": confidence, "ambiguity": ambiguity, "ambiguous_points": ambiguous_points}
    except Exception as e:
        logger.error(f"[Coordinator] Synthesis failed: {e}")

    return {
        "plan": f"Synthesis failed. Raw findings:\n{findings}",
        "confidence": 0.50,
        "ambiguity": 0.50,
        "ambiguous_points": [],
    }


def _generate_followups(synthesis: str, impl_tasks: list) -> str:
    """
    Build a short 'What next?' section appended to the final synthesis.
    Suggestions are contextual based on what the coordinator produced.
    """
    code_roles = {"coder", "devops", "architect"}
    has_code = any(t.get("role", "") in code_roles for t in impl_tasks)

    suggestions = []
    if has_code:
        suggestions.append(
            "**🛠 Build it** — Ask me to implement a specific step from the plan above"
        )
        suggestions.append(
            "**🚀 DevOps** — Deploy and test this in the dev environment"
        )
    else:
        suggestions.append(
            "**📝 Draft it** — Have me write up a detailed spec or document for this plan"
        )
    suggestions.append("**🔍 Dig deeper** — Ask me to expand on any specific section")
    suggestions.append("**🔄 Alternative** — Explore a completely different approach")

    lines = [
        "\n---",
        "**💡 What would you like to do next?**",
    ]
    for s in suggestions[:3]:
        lines.append(f"- {s}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Worker execution
# ---------------------------------------------------------------------------

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

    If a *child_token* is provided (derived from the coordinator's session card),
    it is set as the current execution-context token for this thread.
    """
    worker = session.workers[worker_id]
    worker.state = WorkerState.RUNNING
    worker.started_at = time.time()

    # Set child JWT for this worker thread
    if child_token and _JWT_AVAILABLE:
        set_current_token(child_token)

    try:
        if worker.cancel_flag.is_set():
            worker.state = WorkerState.CANCELLED
            return ""

        # Note: no GPU lock here — workers run in parallel across multiple Ollama hosts
        # (distributed by get_swarm_worker_host round-robin). The GPU lock would serialize
        # all workers onto a single slot and cause timeouts with 4+ concurrent workers.
        response: RunResponse = agent.run(prompt)

        result = response.content if response and response.content else "No output"
        worker.result = result
        worker.state = WorkerState.COMPLETED
        worker.completed_at = time.time()

        # Write to scratchpad
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


def _get_agent_for_role(role: str, session_id: str = None, scope: str = "unknown") -> Agent:
    """
    Factory: Map coordinator roles to existing Agent_Swarm team agents.

    When scope=='codebase', architect/coder/devops roles use Leibniz (which has
    file system tools).  For external/research scope they use a plain LLM agent
    so we don't attempt live file edits against the research output.
    """
    role_lower = role.lower()
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    if role_lower in ("architect", "coder", "devops"):
        if scope == "codebase":
            from leibniz_agent import get_architect_agent
            return get_architect_agent(session_id=session_id)
        else:
            # external/unknown scope — use a plain planning agent, no file tools
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
        # Default: leibniz agent
        from leibniz_agent import get_architect_agent
        return get_architect_agent(session_id=session_id)


# Role → capability mapping for child card derivation.
_ROLE_CAPS: dict[str, list[str]] = {
    "architect": ["file_read", "file_write", "terminal_exec", "terminal_read", "model_generate", "git_read", "git_write"],
    "coder": ["file_read", "file_write", "terminal_exec", "terminal_read", "model_generate", "git_read"],
    "devops": ["file_read", "file_write", "terminal_exec", "terminal_read", "api_call", "resource_access"],
    "analyst": ["model_generate", "api_call", "file_read"],
    "researcher": ["model_generate", "api_call", "file_read"],
    "verifier": ["model_generate", "file_read"],
}


def _derive_worker_token(
    parent_token: str | None,
    role: str,
    task_description: str,
) -> str | None:
    """Derive a child JWT-ACE token for a coordinator worker.

    Returns the signed child JWT string, or None if JWT is unavailable.
    """
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


# ---------------------------------------------------------------------------
# Project onboarding flow — multi-step clarification sequence
# ---------------------------------------------------------------------------

def coordinate_project_onboarding(
    original_prompt: str,
    session_id: str = "default_session",
    owner_id: str = None,
) -> Generator[dict, None, None]:
    """
    Multi-step onboarding flow for brand-new projects.
    Emits a sequence of clarification_card events and on completion
    creates a workspace/<project-name>/ directory.
    """
    try:
        from brooks import save_pending_context as _save_ctx
        _save_ctx(
            {
                "type": "project_onboarding_step_1",
                "original_prompt": original_prompt,
            },
            session_id=session_id,
            owner_id=owner_id,
        )
    except Exception as _e:
        logger.warning(f"[Onboarding] Could not save step 1 context: {_e}")

    yield {
        "type": "clarification_card",
        "clarification": {
            "question": "What would you like to call this project, and what type is it?",
            "context": f"Let's set up your new project: *{original_prompt[:120]}*",
            "options": [
                {"label": "Web App", "value": "type:web", "description": "Next.js / React"},
                {"label": "API / Backend", "value": "type:api", "description": "FastAPI / Node"},
                {"label": "CLI Tool", "value": "type:cli", "description": "Python / Bash"},
                {"label": "Library / Package", "value": "type:lib", "description": "Reusable module"},
            ],
            "allow_freetext": True,
            "card_type": "onboarding",
        },
    }


# ---------------------------------------------------------------------------
# Main orchestration generator
# ---------------------------------------------------------------------------

def coordinate_task(
    user_input: str,
    session_id: str = "default_session",
    owner_id: str = None,
    history_context: str = "",
    extracted_context: str = "",
    ace_token: str = None,
    template_metadata: dict = None,
    ultraplan_mode: bool = False,
    dev_mode: bool = False,
    plan_mode: bool = False,
) -> Generator[dict, None, None]:
    """
    Main coordinator generator. Yields status/progress/response dicts
    matching the chat_swarm() yield contract.

    Phases:
        1. Decompose (LLM) — break task into subtasks
        2. Research (parallel workers) — investigate unknowns
        3. Synthesize (LLM) — merge findings into plan, score confidence
        4. Implement (workers) — execute the plan
           • plan_mode=False + scope='codebase': Leibniz runs with real tools
           • plan_mode=True or scope!='codebase': written plan only
        5. Verify (fresh worker) — check results

    plan_mode: when True, skip actual execution even for codebase tasks.
    """
    session = CoordinatorSession(session_id, owner_id)
    logger.info(
        f"[Coordinator] Starting coordination {session.coordination_id} "
        f"for session {session_id}"
    )

    try:
        # === PHASE 1: DECOMPOSE ===
        yield {"type": "swarm_phase", "phase_num": 1, "phase_name": "Decompose", "total_phases": 5}
        yield {"type": "status", "content": "🧩 Coordinator: Decomposing task..."}
        yield {"type": "thought", "content": "→ Phase 1/5: Task Decomposition (LLM)"}

        plan = _decompose_task(user_input, history_context)
        summary = plan.get("summary", user_input[:200])
        research_tasks = plan.get("research_tasks", [])
        impl_tasks = plan.get("implementation_tasks", [])
        verification_criteria = plan.get("verification_criteria", [])
        scope = plan.get("scope", "unknown")
        project_type = plan.get("project_type", "unknown")

        # --- AMBIGUITY GATE: ask before spending worker budget ---
        if plan.get("clarification_needed", False):
            question = plan.get(
                "clarification_question",
                "Could you provide more context about what you're trying to achieve?",
            )
            logger.info(f"[Coordinator] Clarification needed: {question}")
            try:
                from brooks import save_pending_context as _save_ctx
                _save_ctx(
                    {"type": "swarm_clarification", "prompt": user_input, "question": question},
                    session_id=session_id,
                    owner_id=owner_id,
                )
            except Exception as _e:
                logger.warning(f"[Coordinator] Could not save clarification context: {_e}")
            yield {
                "type": "clarification_card",
                "clarification": {
                    "question": question,
                    "context": "I need a little more information before assembling the research team.",
                    "options": [],
                    "allow_freetext": True,
                    "card_type": "ambiguity",
                },
            }
            return

        # --- DEV PROJECT GATE: detect new codebase tasks and route to onboarding ---
        # Skip in dev_mode — church.py already asked the routing question and re-invoked
        # coordinate_task with dev_mode=True after the user answered, so firing again
        # would create an infinite clarification loop.
        if scope == "codebase" and project_type in ("new", "unknown") and not dev_mode:
            logger.info(f"[Coordinator] Codebase task detected (project_type={project_type}), asking for project routing.")
            try:
                from brooks import save_pending_context as _save_ctx
                _save_ctx(
                    {"type": "dev_project_clarification", "prompt": user_input, "summary": summary},
                    session_id=session_id,
                    owner_id=owner_id,
                )
            except Exception as _e:
                logger.warning(f"[Coordinator] Could not save dev project context: {_e}")
            yield {
                "type": "clarification_card",
                "clarification": {
                    "question": "Is this for an existing project or a new one?",
                    "context": f"I detected a coding task: *{summary}*",
                    "options": [
                        {
                            "label": "Existing project",
                            "value": "existing_project",
                            "description": "I'll work within your current codebase",
                        },
                        {
                            "label": "New project",
                            "value": "new_project",
                            "description": "Walk me through setup",
                            "redirect": None,
                        },
                        {
                            "label": "Just plan it",
                            "value": "plan_only",
                            "description": "Research and plan, no files changed",
                        },
                    ],
                    "allow_freetext": False,
                    "card_type": "dev_project",
                },
            }
            return

        yield {
            "type": "log",
            "content": (
                f"[Coordinator] Decomposed into {len(research_tasks)} research "
                f"+ {len(impl_tasks)} implementation tasks"
            ),
        }
        yield {"type": "message", "content": f"**📋 Task Plan: {summary}**\n\n"}

        # Show plan
        if research_tasks:
            task_list = "\n".join(
                f"  {i+1}. **{t['role']}** — {t['task']}"
                for i, t in enumerate(research_tasks)
            )
            yield {
                "type": "message",
                "content": (
                    f"**🔬 Research Phase** ({len(research_tasks)} workers, parallel):\n"
                    f"{task_list}\n\n"
                ),
            }
        if impl_tasks:
            task_list = "\n".join(
                f"  {i+1}. **{t['role']}** — {t['task']}"
                for i, t in enumerate(impl_tasks)
            )
            yield {
                "type": "message",
                "content": (
                    f"**🔨 Implementation Phase** ({len(impl_tasks)} tasks):\n"
                    f"{task_list}\n\n"
                ),
            }

        # Save plan to scratchpad
        session.write_to_scratchpad("00_plan.json", json.dumps(plan, indent=2))

        # === PHASE 2: RESEARCH (parallel) ===
        yield {"type": "swarm_phase", "phase_num": 2, "phase_name": "Research", "total_phases": 5}
        yield {
            "type": "status",
            "content": f"🔬 Coordinator: Launching {len(research_tasks)} research workers...",
        }
        yield {
            "type": "thought",
            "content": f"→ Phase 2/5: Research ({len(research_tasks)} parallel workers)",
        }

        research_results = {}
        if research_tasks:
            # Cap at 3 concurrent workers to prevent GPU contention
            max_workers = min(len(research_tasks), 3)

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {}
                for i, task_def in enumerate(research_tasks):
                    role = task_def.get("role", "researcher")
                    task_text = task_def.get("task", "")

                    worker_id = session.register_worker(role, task_text, "research")
                    agent = _get_agent_for_role(role, session_id=session_id, scope=scope)

                    # Derive a child JWT card for this worker
                    child_token = _derive_worker_token(ace_token, role, task_text)

                    # Build worker prompt with context
                    worker_prompt = (
                        f"[Research Task {i+1}/{len(research_tasks)}]\n{task_text}"
                    )
                    if extracted_context:
                        worker_prompt += f"\n\n[Available Context]:\n{extracted_context}"

                    future = pool.submit(
                        _run_worker, session, worker_id, agent, worker_prompt,
                        child_token=child_token,
                    )
                    futures[future] = (worker_id, role, task_text)
                    pioneer = session.workers[worker_id].pioneer
                    yield {
                        "type": "swarm_worker_created",
                        "worker_id": worker_id,
                        "role": role,
                        "pioneer_name": pioneer["name"],
                        "pioneer_full_name": pioneer["full_name"],
                        "pioneer_motto": pioneer["motto"],
                        "task": task_text,
                        "phase": "research",
                        "content": f"Spawned {pioneer['name']} ({role})",
                    }
                    yield {
                        "type": "log",
                        "content": (
                            f"[Coordinator] Spawned worker {worker_id} ({role}) → {pioneer['name']}: "
                            f"{task_text[:80]}..."
                        ),
                    }

                # Emit initial task list snapshot (all workers queued)
                yield {
                    "type": "swarm_task_list",
                    "workers": [
                        {
                            "worker_id": w.worker_id,
                            "pioneer_name": w.pioneer["name"],
                            "role": w.role,
                            "task": w.task,
                            "state": w.state.value,
                        }
                        for w in session.workers.values()
                        if w.phase == "research"
                    ],
                    "content": "Research workers queued",
                }

                # Collect results as they complete
                for future in as_completed(futures):
                    worker_id, role, task_text = futures[future]
                    try:
                        result = future.result(timeout=180)
                        research_results[worker_id] = result
                        worker = session.workers[worker_id]
                        elapsed = (
                            (worker.completed_at or time.time())
                            - (worker.started_at or time.time())
                        )
                        yield {
                            "type": "log",
                            "content": (
                                f"[Coordinator] Worker {worker_id} ({role}) "
                                f"completed in {elapsed:.1f}s"
                            ),
                        }
                        pioneer = worker.pioneer
                        yield {
                            "type": "message",
                            "content": f"✅ **{pioneer['name']}** ({role}) completed\n\n",
                        }
                        # Emit updated task list snapshot after each completion
                        yield {
                            "type": "swarm_task_list",
                            "workers": [
                                {
                                    "worker_id": w.worker_id,
                                    "pioneer_name": w.pioneer["name"],
                                    "pioneer_full_name": w.pioneer["full_name"],
                                    "pioneer_motto": w.pioneer["motto"],
                                    "role": w.role,
                                    "task": w.task,
                                    "state": w.state.value,
                                    "output": (research_results.get(w.worker_id, "") or "")[:600],
                                }
                                for w in session.workers.values()
                                if w.phase == "research"
                            ],
                            "content": f"{pioneer['name']} completed",
                        }
                        # Store worker finding in team memory
                        _team_store(
                            session.coordination_id,
                            f"research_{role}_{worker_id}",
                            result[:2000] if result else "",
                            author=role,
                        )
                    except Exception as e:
                        yield {
                            "type": "log",
                            "content": (
                                f"[Coordinator] Worker {worker_id} ({role}) failed: {e}"
                            ),
                        }
                        yield {
                            "type": "message",
                            "content": f"⚠️ Research worker **{role}** failed: {e}\n\n",
                        }
                        # Emit updated snapshot on failure too
                        yield {
                            "type": "swarm_task_list",
                            "workers": [
                                {
                                    "worker_id": w.worker_id,
                                    "pioneer_name": w.pioneer["name"],
                                    "pioneer_full_name": w.pioneer["full_name"],
                                    "pioneer_motto": w.pioneer["motto"],
                                    "role": w.role,
                                    "task": w.task,
                                    "state": w.state.value,
                                    "output": (research_results.get(w.worker_id, "") or "")[:600],
                                }
                                for w in session.workers.values()
                                if w.phase == "research"
                            ],
                            "content": f"{role} failed",
                        }

        # === PHASE 3: SYNTHESIZE (LLM) ===
        yield {"type": "swarm_phase", "phase_num": 3, "phase_name": "Synthesize", "total_phases": 5}
        yield {"type": "status", "content": "🧠 Coordinator: Synthesizing research findings..."}
        yield {"type": "thought", "content": "→ Phase 3/5: Synthesis (LLM — reading all findings)"}

        all_findings = session.get_all_scratchpad_content()
        max_synth_passes = 3
        synthesis = ""
        synth_confidence = 0.80
        synth_ambiguity = 0.20
        synth_ambiguous_points = []

        for synth_pass in range(1, max_synth_passes + 1):
            with request_lock(context="text"):
                synth_result = _synthesize_findings(all_findings, user_input)
            synthesis = synth_result["plan"]
            synth_confidence = synth_result["confidence"]
            synth_ambiguity = synth_result["ambiguity"]
            synth_ambiguous_points = synth_result.get("ambiguous_points", [])

            # Safety-net: if plan is the error fallback string or suspiciously short,
            # force failure regardless of reported confidence so we always retry.
            _MIN_SYNTHESIS_LEN = 300
            if len(synthesis) < _MIN_SYNTHESIS_LEN or synthesis.startswith("Synthesis failed"):
                yield {
                    "type": "log",
                    "content": (
                        f"[Coordinator] Synthesis pass {synth_pass} produced only "
                        f"{len(synthesis)} chars — treating as failure and retrying."
                    ),
                }
                synth_confidence = 0.0
                synth_ambiguity = 1.0

            # Threshold: 90% first pass, 95% on subsequent passes
            required_confidence = 0.90 if synth_pass == 1 else 0.95
            yield {
                "type": "log",
                "content": (
                    f"[Coordinator] Synthesis pass {synth_pass}/{max_synth_passes}: "
                    f"confidence={synth_confidence:.0%}, ambiguity={synth_ambiguity:.0%} "
                    f"(need ≥{required_confidence:.0%} confidence, ≤5% ambiguity)"
                ),
            }

            if synth_confidence >= required_confidence and synth_ambiguity <= 0.05:
                break

            if synth_pass >= max_synth_passes:
                # Hit iteration limit without meeting thresholds — ask for guidance
                logger.warning(
                    f"[Coordinator] Synthesis thresholds not met after {max_synth_passes} passes "
                    f"(confidence={synth_confidence:.0%}, ambiguity={synth_ambiguity:.0%}). "
                    "Requesting clarification."
                )
                try:
                    from brooks import save_pending_context as _save_ctx
                    _save_ctx(
                        {"type": "swarm_clarification", "prompt": user_input, "question":
                         f"I've analysed the task but my confidence is only {synth_confidence:.0%} "
                         f"with {synth_ambiguity:.0%} ambiguity remaining. What additional detail "
                         "or constraint would help me proceed with confidence?"},
                        session_id=session_id,
                        owner_id=owner_id,
                    )
                except Exception as _e:
                    logger.warning(f"[Coordinator] Could not save clarification context: {_e}")

                # Build a specific question from the ambiguous points the LLM identified
                if synth_ambiguous_points:
                    _points_text = "\n".join(f"• {p}" for p in synth_ambiguous_points[:4])
                    _clarif_question = (
                        f"The swarm completed research but hit {synth_ambiguity:.0%} ambiguity "
                        f"(confidence {synth_confidence:.0%}, need ≥95%). These points need clarification:\n\n"
                        f"{_points_text}\n\nPlease clarify any of the above to proceed."
                    )
                    _clarif_context = f"Ambiguity remaining: {synth_ambiguity:.0%}"
                    _clarif_options = [{"label": p[:60], "value": p[:60]} for p in synth_ambiguous_points[:4]]
                else:
                    _clarif_question = (
                        f"Research complete but confidence is {synth_confidence:.0%} (need ≥95%). "
                        "Please provide additional detail or constraints to help proceed."
                    )
                    _clarif_context = f"Ambiguity remaining: {synth_ambiguity:.0%}"
                    _clarif_options = []

                yield {
                    "type": "clarification_card",
                    "clarification": {
                        "question": _clarif_question,
                        "context": _clarif_context,
                        "options": _clarif_options,
                        "allow_freetext": True,
                        "card_type": "ambiguity",
                    },
                }
                return
            # else: loop and try synthesis again (findings unchanged but model temperature
            # varies slightly, sometimes yielding higher-confidence output)

        session.write_to_scratchpad("01_synthesis.md", f"# Synthesis\n\n{synthesis}")

        # Persist synthesis to team memory for cross-coordination recall
        _team_store(session.coordination_id, "synthesis", synthesis)

        yield {"type": "message", "content": "**🧠 Synthesis Complete** ✓\n\n"}
        yield {"type": "log", "content": f"[Coordinator] Synthesis: {len(synthesis)} chars, confidence={synth_confidence:.0%}"}

        # === PHASE 4: IMPLEMENTATION (serial) ===
        yield {"type": "swarm_phase", "phase_num": 4, "phase_name": "Implement", "total_phases": 5}

        # Execution mode: use Leibniz with real tools for codebase tasks unless
        # plan_mode or ultraplan_mode is explicitly requested.
        execute_code = (not plan_mode) and (not ultraplan_mode) and (scope == "codebase")

        # --- Palace Project Lookup: check if user already has a matching project ---
        _existing_project_context = ""
        if execute_code and owner_id:
            _palace_hits = _palace_project_lookup(owner_id, user_input, limit=3)
            if _palace_hits:
                _best = _palace_hits[0]
                _hit_content = _best.get("content", "") or _best.get("document", "")
                if _hit_content and "PROJECT:" in _hit_content:
                    _existing_project_context = (
                        f"\n\n[MEMORY PALACE — EXISTING PROJECT FOUND FOR THIS USER]:\n"
                        f"{_hit_content}\n"
                        f"CRITICAL: Read the existing file first using read_file(), then update "
                        f"it in place using write_file(). Do NOT call build_web_app() — that "
                        f"creates a new project at a new path and discards the user's work.\n"
                    )
                    yield {
                        "type": "log",
                        "content": (
                            f"[Coordinator] Palace: existing project found for '{owner_id}' — "
                            f"injecting context into coder prompt"
                        ),
                    }
                    yield {
                        "type": "thought",
                        "content": "→ Memory Palace: Existing project detected — coder will read-then-update",
                    }

        yield {
            "type": "status",
            "content": (
                f"{'⚡ Executing' if execute_code else '📝 Planning'}: "
                f"{len(impl_tasks)} implementation task(s)..."
            ),
        }
        yield {
            "type": "thought",
            "content": (
                f"→ Phase 4/5: Implementation ({len(impl_tasks)} tasks, serial) — "
                f"{'EXECUTION MODE' if execute_code else 'PLAN MODE'}"
            ),
        }
        if execute_code:
            yield {
                "type": "log",
                "content": "[Coordinator] Execution mode active — Leibniz will write files and run tools.",
            }

        impl_results = {}
        for i, task_def in enumerate(impl_tasks):
            role = task_def.get("role", "architect")
            task_text = task_def.get("task", "")

            worker_id = session.register_worker(role, task_text, "implementation")
            try:
                if execute_code and role in ("architect", "coder", "devops"):
                    # Use Leibniz — it has write_file, run_command, build_web_app etc.
                    from leibniz_agent import get_architect_agent
                    agent = get_architect_agent(session_id=session_id)
                else:
                    agent = _get_agent_for_role(role, session_id=session_id, scope=scope)
            except Exception as _agent_err:
                logger.warning(
                    f"[Coordinator] Agent init failed for role '{role}' (falling back to simple agent): {_agent_err}"
                )
                _fb_host = get_swarm_worker_host(ARCHITECT_MODEL)
                from agno.agent import Agent as _Agent
                from agno.models.ollama import Ollama as _Ollama
                agent = _Agent(
                    name=f"{role.capitalize()} Worker",
                    model=_Ollama(id=ARCHITECT_MODEL, host=_fb_host, client_kwargs={"timeout": 300.0}),
                    instructions=[
                        f"You are a {role} worker producing a detailed plan.",
                        "Produce written plans, designs, and documentation only.",
                        "Do NOT execute commands, SSH to servers, or make live connections.",
                    ],
                    show_tool_calls=False,
                )
            _impl_pioneer = session.workers[worker_id].pioneer
            yield {
                "type": "swarm_worker_created",
                "worker_id": worker_id,
                "role": role,
                "pioneer_name": _impl_pioneer["name"],
                "pioneer_full_name": _impl_pioneer["full_name"],
                "pioneer_motto": _impl_pioneer["motto"],
                "task": task_text,
                "phase": "implementation",
                "content": f"Spawned {_impl_pioneer['name']} ({role})",
            }

            if execute_code and role in ("architect", "coder", "devops"):
                # Execution prompt: agent has tools, tell it to use them
                impl_prompt = (
                    f"[Implementation Task {i+1}/{len(impl_tasks)}]\n"
                    f"{task_text}\n\n"
                    f"You have access to tools: build_web_app, get_project_template, write_file, "
                    f"read_file, list_dir, run_command.\n"
                    f"EXECUTE this task — write actual code and files. "
                    f"For web apps, use build_web_app(project_name, html_content) to create the "
                    f"project and get a live URL. Use get_project_template(type) to start from a "
                    f"scaffold (available types: game, dashboard, landing).\n\n"
                    f"CRITICAL — TEMPLATE CUSTOMIZATION: If you use get_project_template(), you MUST "
                    f"replace ALL placeholder content before calling build_web_app(). The template is "
                    f"a structural scaffold only. Replace every generic name, location, description, "
                    f"game objective, and placeholder comment with rich, specific content for THIS "
                    f"exact project. Never leave 'Starting Point', 'Central Hub', 'GAME TEMPLATE', "
                    f"'replace this section', or any other template placeholder in the final HTML.\n\n"
                    f"[Implementation Plan from Synthesis]:\n{synthesis}\n\n"
                    f"{_existing_project_context}"
                )
            else:
                # Plan-only: document the approach but do not execute
                impl_prompt = (
                    f"[Implementation Task {i+1}/{len(impl_tasks)}]\n"
                    f"{task_text}\n\n"
                    f"IMPORTANT: Produce a detailed written plan, design, or documentation for this "
                    f"task. Do NOT execute commands, SSH to servers, or make live connections.\n\n"
                    f"[Synthesis / Implementation Plan]:\n{synthesis}\n\n"
                )
            if extracted_context:
                impl_prompt += f"[Original Context]:\n{extracted_context}"

            yield {
                "type": "log",
                "content": (
                    f"[Coordinator] Running implementation worker {worker_id} ({role}): "
                    f"{task_text[:80]}..."
                ),
            }

            result = _run_worker(
                session, worker_id, agent, impl_prompt,
                child_token=_derive_worker_token(ace_token, role, task_text),
            )
            impl_results[worker_id] = result

            worker = session.workers[worker_id]
            elapsed = (
                (worker.completed_at or time.time())
                - (worker.started_at or time.time())
            )

            _done_pioneer = worker.pioneer
            if worker.state == WorkerState.COMPLETED:
                yield {
                    "type": "message",
                    "content": f"✅ **{_done_pioneer['name']}** — step {i+1} completed ({elapsed:.1f}s)\n\n",
                }
            else:
                yield {
                    "type": "message",
                    "content": (
                        f"⚠️ **{_done_pioneer['name']}** — step {i+1} failed: {worker.error}\n\n"
                    ),
                }
            # Emit implementation task list snapshot
            yield {
                "type": "swarm_task_list",
                "workers": [
                    {
                        "worker_id": w.worker_id,
                        "pioneer_name": w.pioneer["name"],
                        "role": w.role,
                        "task": w.task,
                        "state": w.state.value,
                    }
                    for w in session.workers.values()
                    if w.phase == "implementation"
                ],
                "content": f"Implementation step {i+1} done",
            }

        # After all implementation tasks: scan for web app URLs and push to preview pane
        if execute_code:
            import re as _re
            _url_pattern = _re.compile(
                r"PROJECT_URL:\s*(https?://[^\s\n\"'<>]+)"
            )
            _preview_url = None
            for _worker_result in impl_results.values():
                _match = _url_pattern.search(_worker_result or "")
                if _match:
                    _preview_url = _match.group(1).rstrip("/") + "/"
                    break  # Only emit once even if multiple workers built apps

            # Fallback: web_builder writes the last deployed URL to a temp file
            # so we can reliably pick it up even when the LLM paraphrases the
            # tool result in its response text (response.content is LLM text only).
            if not _preview_url:
                try:
                    import pathlib as _pl
                    _tmp = _pl.Path("/tmp/web_builder_last_url.txt")
                    if _tmp.exists():
                        _candidate = _tmp.read_text(encoding="utf-8").strip()
                        if _candidate.startswith("http"):
                            _preview_url = _candidate.rstrip("/") + "/"
                            _tmp.unlink(missing_ok=True)  # consume so it doesn't leak to next request
                except Exception:
                    pass

            if _preview_url:
                yield {
                    "type": "set_preview_url",
                    "url": _preview_url,
                    "content": "",
                }
                yield {
                    "type": "message",
                    "content": (
                        f"**🌐 Live Preview:** [{_preview_url}]({_preview_url})\n\n"
                        f"The project is now running — check the Preview pane.\n\n"
                    ),
                }

                # Save project to the user's palace wing so future swarm runs can iterate
                if owner_id:
                    import re as _re
                    _slug_match = _re.search(r"/projects/([^/?\s]+)", _preview_url)
                    if _slug_match:
                        _project_slug = _slug_match.group(1).rstrip("/")
                        _project_desc = user_input[:400]
                        _palace_project_save(
                            owner_id=owner_id,
                            slug=_project_slug,
                            url=_preview_url,
                            description=_project_desc,
                            path=f"user_projects/{_project_slug}/index.html",
                        )

        # === PHASE 5: VERIFICATION ===
        yield {"type": "swarm_phase", "phase_num": 5, "phase_name": "Verify", "total_phases": 5}
        yield {"type": "status", "content": "🔍 Coordinator: Verification in progress..."}
        yield {"type": "thought", "content": "→ Phase 5/5: Verification (fresh-eyes worker)"}

        all_work = session.get_all_scratchpad_content()
        criteria_text = "\n".join(f"- {c}" for c in verification_criteria)

        verify_prompt = (
            f"[Verification Task]\n"
            f"Review all work done for this task and verify against the criteria.\n\n"
            f"Original Task: {user_input}\n\n"
            f"Verification Criteria:\n{criteria_text}\n\n"
            f"Work Product:\n{all_work}"
        )

        verify_worker_id = session.register_worker(
            "verifier", "Final verification", "verification"
        )
        _verify_pioneer = session.workers[verify_worker_id].pioneer
        yield {
            "type": "swarm_worker_created",
            "worker_id": verify_worker_id,
            "role": "verifier",
            "pioneer_name": _verify_pioneer["name"],
            "pioneer_full_name": _verify_pioneer["full_name"],
            "pioneer_motto": _verify_pioneer["motto"],
            "task": "Final verification",
            "phase": "verification",
            "content": f"Spawned {_verify_pioneer['name']} (verifier)",
        }
        verifier = _get_agent_for_role("verifier")
        verify_result = _run_worker(
            session, verify_worker_id, verifier, verify_prompt,
            child_token=_derive_worker_token(ace_token, "verifier", "Final verification"),
        )

        session.write_to_scratchpad(
            "99_verification.md", f"# Verification\n\n{verify_result}"
        )

        # Emit task list update so the UI reflects the verifier's final state
        verify_worker = session.workers[verify_worker_id]
        yield {
            "type": "swarm_task_list",
            "workers": [
                {
                    "worker_id": verify_worker.worker_id,
                    "pioneer_name": _verify_pioneer["name"],
                    "pioneer_full_name": _verify_pioneer["full_name"],
                    "pioneer_motto": _verify_pioneer["motto"],
                    "role": verify_worker.role,
                    "task": verify_worker.task,
                    "state": verify_worker.state.value,
                }
            ],
            "content": "Verification complete",
        }

        yield {"type": "message", "content": f"**🔍 Verification**\n\n{verify_result}\n\n"}

        # --- Auto-retry: if verification failed because execution was skipped (plan-only),
        # re-run Phase 4 in execution mode so the code actually gets written. ---
        _verify_lower = verify_result.lower()
        _is_fail = any(kw in _verify_lower for kw in ("fail", "not complete", "no code", "no implementation", "planning document", "no actual"))
        if _is_fail and not execute_code and scope == "codebase":
            logger.warning("[Coordinator] Verification FAIL on plan-only run — auto-retrying in execution mode")
            yield {
                "type": "thought",
                "content": "→ Auto-retry: verification caught plan-only result, re-running with code execution enabled",
            }
            yield {"type": "status", "content": "⚡ Auto-correcting: running implementation in execution mode..."}
            execute_code = True  # Force execution mode for retry
            for i, task_def in enumerate(impl_tasks):
                task_text = task_def.get("task", "")
                role = task_def.get("role", "architect")
                retry_prompt = (
                    f"[Implementation Task {i+1}/{len(impl_tasks)} — EXECUTION REQUIRED]\n"
                    f"{task_text}\n\n"
                    f"You MUST write actual code and create files. Use build_web_app(project_name, html_content) "
                    f"to create a live web project. Do NOT just plan or describe — WRITE THE CODE NOW.\n\n"
                    f"[Implementation Plan from Synthesis]:\n{synthesis}\n\n"
                    f"{_existing_project_context}"
                )
                retry_worker_id = session.register_worker(role, task_text, "implementation")
                retry_agent = _get_agent_for_role(role, session_id=session_id, scope="codebase")
                retry_result = _run_worker(
                    session, retry_worker_id, retry_agent, retry_prompt,
                    child_token=_derive_worker_token(ace_token, role, task_text),
                )
                yield {
                    "type": "message",
                    "content": f"✅ Retry: {role} completed — {retry_result[:200]}...\n\n" if len(retry_result) > 200 else f"✅ Retry: {role} completed\n\n",
                }
                impl_results[f"retry_w-{retry_worker_id}"] = retry_result

            # Check for new preview URL after retry
            _retry_url_pattern = re.compile(r"PROJECT_URL:\s*(https?://[^\s\n\"'<>]+)")
            for _res in impl_results.values():
                _m = _retry_url_pattern.search(_res or "")
                if _m:
                    _preview_url = _m.group(1).rstrip("/") + "/"
                    yield {"type": "set_preview_url", "url": _preview_url, "content": ""}
                    yield {"type": "message", "content": f"**🌐 Live Preview:** [{_preview_url}]({_preview_url})\n\n"}
                    if owner_id:
                        import re as _re2
                        _sm = _re2.search(r"/projects/([^/?\s]+)", _preview_url)
                        if _sm:
                            _palace_project_save(owner_id, _sm.group(1).rstrip("/"), _preview_url, user_input[:400])
                    break
            if not _preview_url:
                try:
                    import pathlib as _pl2
                    _tmp2 = _pl2.Path("/tmp/web_builder_last_url.txt")
                    if _tmp2.exists():
                        _c2 = _tmp2.read_text(encoding="utf-8").strip()
                        if _c2.startswith("http"):
                            _preview_url = _c2.rstrip("/") + "/"
                            _tmp2.unlink(missing_ok=True)
                            yield {"type": "set_preview_url", "url": _preview_url, "content": ""}
                            yield {"type": "message", "content": f"**🌐 Live Preview:** [{_preview_url}]({_preview_url})\n\n"}
                            if owner_id:
                                import re as _re3
                                _sm3 = _re3.search(r"/projects/([^/?\s]+)", _preview_url)
                                if _sm3:
                                    _palace_project_save(owner_id, _sm3.group(1).rstrip("/"), _preview_url, user_input[:400])
                except Exception:
                    pass

        # Store verification in team memory
        _team_store(session.coordination_id, "verification", verify_result, author="verifier")

        # === FINAL SUMMARY ===
        total_workers = len(session.workers)
        completed = sum(
            1 for w in session.workers.values() if w.state == WorkerState.COMPLETED
        )
        failed = sum(
            1 for w in session.workers.values() if w.state == WorkerState.FAILED
        )
        total_time = time.time() - session.created_at

        yield {
            "type": "message",
            "content": (
                f"---\n"
                f"**📊 Coordination Summary**\n"
                f"- Workers spawned: {total_workers}\n"
                f"- Completed: {completed} | Failed: {failed}\n"
                f"- Total time: {total_time:.1f}s\n"
                f"- Scratchpad: {len(session.list_scratchpad())} files\n"
            ),
        }

        followup_section = _generate_followups(synthesis, impl_tasks)
        yield {"type": "response", "content": f"{synthesis}{followup_section}"}

        logger.info(
            f"[Coordinator] Coordination {session.coordination_id} complete: "
            f"{completed}/{total_workers} workers, {total_time:.1f}s"
        )

    except Exception as e:
        logger.error(f"[Coordinator] Coordination failed: {e}", exc_info=True)
        yield {"type": "error", "content": f"Coordination failed: {e}"}
