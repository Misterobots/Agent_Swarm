"""
dev_projects/repo_context.py — build the repo_context dict coordinate_task()
expects, from a dev_projects row.

Factored out so POST /v1/tasks (main.py::create_task) and the chat-driven
project-picker resume (routing/gates.py's dev_project_picker handler) build
the IDENTICAL shape from the same project record, instead of two independently
maintained copies. Only meaningful for "git_url"-source projects — callers are
responsible for routing "live_repo" and "blank" sources differently (neither
needs a repo_context at all; see coordination/session_sandbox.py's modes).
"""
from __future__ import annotations


def build_repo_context(project: dict, branch: str | None = None) -> dict:
    """
    project: a dev_projects row (dict) with at least git_url/git_ref/id.
    branch: caller-supplied override (e.g. the composer's branch field);
    falls back to the project's own git_ref when not given.

    Returns {"git_url", "branch", "base_branch", "dev_project_id"} — the
    exact shape coordinate_task()'s Phase 0 workspace prep expects.
    """
    base_branch = project.get("git_ref") or "main"
    return {
        "git_url": project["git_url"],
        "branch": (branch or base_branch).strip(),
        "base_branch": base_branch,
        "dev_project_id": project["id"],
    }
