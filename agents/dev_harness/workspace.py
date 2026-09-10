"""Workspace-selection contract shared by ordinary Code turns.

The desktop sends an absolute selected project root as ``workspace_key``. It
must win over the server's live-repository fallback, otherwise a Code request
can silently operate on the Agent_Swarm checkout instead of the project the
user opened.
"""

from __future__ import annotations


def session_workspace_spec(workspace_key: str | None, project_source: str | None) -> tuple[str, str | None]:
    selected = str(workspace_key or "").strip()
    if selected:
        return "desktop_local", selected
    return ("live_repo" if project_source == "live_repo" else "ephemeral"), None
