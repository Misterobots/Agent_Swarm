"""Owner/workspace scoping primitives for DevHarness approval state."""
from __future__ import annotations

import hashlib
from typing import Any


def workspace_key(value: str | None) -> str:
    """Return a stable opaque key without persisting a raw filesystem path."""
    normalized = str(value or "default-workspace").strip() or "default-workspace"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def rules_for_workspace(data: dict[str, Any], owner_id: str,
                       workspace: str) -> set[str]:
    """Read only the owner's rules for one already-normalized workspace key."""
    owner_rules = data.get(owner_id, {})
    if not isinstance(owner_rules, dict):
        return set()
    rules = owner_rules.get(workspace, [])
    return set(rules) if isinstance(rules, list) else set()
