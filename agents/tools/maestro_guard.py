"""
maestro_guard.py — MAESTRO Layer-6 tool guardrail.

Single source of truth for files that agents must never write, shared by
tools/file_ops (host fs) and tools/sandbox_ops (Docker dev sandbox) so the dev
harness and the swarm enforce the same blacklist.
"""

from __future__ import annotations

# Suffix-matched: any path ending in one of these is blocked.
PROTECTED_FILES = [".env", "docker-compose.yml", "agents/security_agent.py"]


def is_protected_path(path: str) -> bool:
    """True if `path` targets a MAESTRO-protected file."""
    clean = path.lstrip("/").replace("\\", "/")
    return any(clean.endswith(f) for f in PROTECTED_FILES)
