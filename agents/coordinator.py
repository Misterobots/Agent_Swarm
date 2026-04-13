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
from utils.gpu_queue import request_lock, get_best_host_for_model

logger = setup_logger("Coordinator")

# --- Scratchpad Root ---
SCRATCHPAD_ROOT = Path(__file__).parent / "scratchpad"


class WorkerState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerInfo:
    """Tracks a single worker's lifecycle."""

    def __init__(self, worker_id: str, role: str, task: str, phase: str):
        self.worker_id = worker_id
        self.role = role
        self.task = task
        self.phase = phase
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
        self.workers[worker_id] = WorkerInfo(worker_id, role, task, phase)
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
    decompose_model = os.getenv("COORDINATOR_MODEL", "qwen3:14b")
    host = get_best_host_for_model(decompose_model)

    system_prompt = (
        "You are a task decomposition engine. Given a complex task, break it into phases.\n"
        "Output ONLY valid JSON with this structure:\n"
        "{\n"
        '  "summary": "One-sentence summary of the task",\n'
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
        "- 2-5 research tasks, 1-4 implementation tasks, 1-3 verification criteria"
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


def _synthesize_findings(findings: str, original_task: str) -> str:
    """
    LLM synthesis step: Read all research findings and produce an implementation plan.
    This is the ONLY step where the coordinator delegates understanding to the LLM.
    """
    synth_model = os.getenv("COORDINATOR_MODEL", "qwen3:14b")
    host = get_best_host_for_model(synth_model)

    system_prompt = (
        "You are a technical lead synthesizing research findings into an implementation plan.\n"
        "Rules:\n"
        "- Read ALL findings carefully\n"
        "- Identify key insights, constraints, and dependencies\n"
        "- Produce a clear, actionable implementation plan\n"
        "- Note any conflicts or gaps in the research\n"
        "- Be specific about file paths, function names, and technical details"
    )

    prompt = (
        f"Original Task: {original_task}\n\n"
        f"Research Findings:\n{findings}\n\n"
        "Synthesize these findings into a concrete implementation plan."
    )

    try:
        resp = requests.post(
            f"{host}/api/generate",
            json={
                "model": synth_model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {"temperature": 0.4, "num_predict": 2048},
            },
            timeout=120,
        )

        if resp.status_code == 200:
            return resp.json().get("response", "Synthesis failed — no response from model.")
    except Exception as e:
        logger.error(f"[Coordinator] Synthesis failed: {e}")

    return f"Synthesis failed. Raw findings:\n{findings}"


# ---------------------------------------------------------------------------
# Worker execution
# ---------------------------------------------------------------------------

def _run_worker(session: CoordinatorSession, worker_id: str, agent: Agent, prompt: str) -> str:
    """
    Execute a single worker agent synchronously.
    Called from thread pool for parallel execution.
    """
    worker = session.workers[worker_id]
    worker.state = WorkerState.RUNNING
    worker.started_at = time.time()

    try:
        if worker.cancel_flag.is_set():
            worker.state = WorkerState.CANCELLED
            return ""

        with request_lock(context="text"):
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


def _get_agent_for_role(role: str, session_id: str = None) -> Agent:
    """
    Factory: Map coordinator roles to existing Agent_Swarm team agents.
    """
    role_lower = role.lower()
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    if role_lower in ("architect", "coder", "devops"):
        from architect_agent import get_architect_agent
        return get_architect_agent(session_id=session_id)

    elif role_lower == "analyst":
        host = get_best_host_for_model(ARCHITECT_MODEL)
        return Agent(
            name="Data Analyst Worker",
            model=Ollama(id=ARCHITECT_MODEL, host=host, client_kwargs={"timeout": 300.0}),
            instructions=["You are a data analyst. Provide thorough analysis with supporting evidence."],
            show_tool_calls=False,
        )

    elif role_lower == "researcher":
        host = get_best_host_for_model(ARCHITECT_MODEL)
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
        host = get_best_host_for_model(ARCHITECT_MODEL)
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
        # Default: architect agent
        from architect_agent import get_architect_agent
        return get_architect_agent(session_id=session_id)


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
) -> Generator[dict, None, None]:
    """
    Main coordinator generator. Yields status/progress/response dicts
    matching the chat_swarm() yield contract.

    Phases:
        1. Decompose (LLM) — break task into subtasks
        2. Research (parallel workers) — investigate unknowns
        3. Synthesize (LLM) — merge findings into plan
        4. Implement (workers) — execute the plan
        5. Verify (fresh worker) — check results
    """
    session = CoordinatorSession(session_id, owner_id)
    logger.info(
        f"[Coordinator] Starting coordination {session.coordination_id} "
        f"for session {session_id}"
    )

    try:
        # === PHASE 1: DECOMPOSE ===
        yield {"type": "status", "content": "🧩 Coordinator: Decomposing task..."}
        yield {"type": "thought", "content": "→ Phase 1/5: Task Decomposition (LLM)"}

        plan = _decompose_task(user_input, history_context)
        summary = plan.get("summary", user_input[:200])
        research_tasks = plan.get("research_tasks", [])
        impl_tasks = plan.get("implementation_tasks", [])
        verification_criteria = plan.get("verification_criteria", [])

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
                    agent = _get_agent_for_role(role, session_id=session_id)

                    # Build worker prompt with context
                    worker_prompt = (
                        f"[Research Task {i+1}/{len(research_tasks)}]\n{task_text}"
                    )
                    if extracted_context:
                        worker_prompt += f"\n\n[Available Context]:\n{extracted_context}"

                    future = pool.submit(
                        _run_worker, session, worker_id, agent, worker_prompt
                    )
                    futures[future] = (worker_id, role, task_text)
                    yield {
                        "type": "log",
                        "content": (
                            f"[Coordinator] Spawned worker {worker_id} ({role}): "
                            f"{task_text[:80]}..."
                        ),
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
                        yield {
                            "type": "message",
                            "content": f"✅ Research worker **{role}** completed\n\n",
                        }
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

        # === PHASE 3: SYNTHESIZE (LLM) ===
        yield {"type": "status", "content": "🧠 Coordinator: Synthesizing research findings..."}
        yield {"type": "thought", "content": "→ Phase 3/5: Synthesis (LLM — reading all findings)"}

        all_findings = session.get_all_scratchpad_content()
        with request_lock(context="text"):
            synthesis = _synthesize_findings(all_findings, user_input)
        session.write_to_scratchpad("01_synthesis.md", f"# Synthesis\n\n{synthesis}")

        yield {"type": "message", "content": f"**🧠 Synthesis Complete**\n\n{synthesis}\n\n"}
        yield {"type": "log", "content": f"[Coordinator] Synthesis: {len(synthesis)} chars"}

        # === PHASE 4: IMPLEMENTATION (serial) ===
        yield {
            "type": "status",
            "content": f"🔨 Coordinator: Executing {len(impl_tasks)} implementation tasks...",
        }
        yield {
            "type": "thought",
            "content": f"→ Phase 4/5: Implementation ({len(impl_tasks)} tasks, serial)",
        }

        impl_results = {}
        for i, task_def in enumerate(impl_tasks):
            role = task_def.get("role", "architect")
            task_text = task_def.get("task", "")

            worker_id = session.register_worker(role, task_text, "implementation")
            agent = _get_agent_for_role(role, session_id=session_id)

            # Implementation workers get the synthesis as context
            impl_prompt = (
                f"[Implementation Task {i+1}/{len(impl_tasks)}]\n"
                f"{task_text}\n\n"
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

            result = _run_worker(session, worker_id, agent, impl_prompt)
            impl_results[worker_id] = result

            worker = session.workers[worker_id]
            elapsed = (
                (worker.completed_at or time.time())
                - (worker.started_at or time.time())
            )

            if worker.state == WorkerState.COMPLETED:
                yield {
                    "type": "message",
                    "content": f"✅ Implementation step {i+1} completed ({elapsed:.1f}s)\n\n",
                }
            else:
                yield {
                    "type": "message",
                    "content": (
                        f"⚠️ Implementation step {i+1} failed: {worker.error}\n\n"
                    ),
                }

        # === PHASE 5: VERIFICATION ===
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
        verifier = _get_agent_for_role("verifier")
        verify_result = _run_worker(session, verify_worker_id, verifier, verify_prompt)

        session.write_to_scratchpad(
            "99_verification.md", f"# Verification\n\n{verify_result}"
        )

        yield {"type": "message", "content": f"**🔍 Verification**\n\n{verify_result}\n\n"}

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

        yield {"type": "response", "content": synthesis}

        logger.info(
            f"[Coordinator] Coordination {session.coordination_id} complete: "
            f"{completed}/{total_workers} workers, {total_time:.1f}s"
        )

    except Exception as e:
        logger.error(f"[Coordinator] Coordination failed: {e}", exc_info=True)
        yield {"type": "error", "content": f"Coordination failed: {e}"}
