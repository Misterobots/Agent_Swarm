"""
Lamport Coordinator — thin entry point.

Implementation lives in agents/coordination/:
  pioneers.py    — worker persona pool and perspective taxonomy
  session.py     — WorkerState, WorkerInfo, CoordinatorSession
  palace.py      — MemPalace HTTP client (team store + project registry)
  decomposer.py  — _decompose_task, _decompose_task_perspectives
  synthesizer.py — _synthesize_findings, _synthesize_perspective_matrix, _generate_followups
  executor.py    — _run_worker, _get_agent_for_role, _derive_worker_token
  orchestrator.py — coordinate_task, coordinate_project_onboarding
"""

from coordination.session import WorkerState, WorkerInfo, CoordinatorSession
from coordination.palace import _team_store, _team_clear
from coordination.orchestrator import coordinate_task, coordinate_project_onboarding

__all__ = [
    "WorkerState",
    "WorkerInfo",
    "CoordinatorSession",
    "_team_store",
    "_team_clear",
    "coordinate_task",
    "coordinate_project_onboarding",
]
