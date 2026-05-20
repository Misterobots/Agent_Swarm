"""
Goals audit — plan validation and completion gate.
"""
from __future__ import annotations

from typing import Literal


EvidenceType = Literal["command_output", "file_ref", "test_result", "note"]


def validate_plan(steps: list[dict]) -> None:
    """Raise if more than one step is in_progress (spec §9)."""
    in_progress = [s for s in steps if s["status"] == "in_progress"]
    if len(in_progress) > 1:
        raise ValueError(
            f"Plan invalid: at most one step can be in_progress, got {len(in_progress)}"
        )


def can_complete_goal(
    checks: list[dict],
    evidence: list[dict],
) -> dict:
    """
    Return {ok: bool, missing: list[str]}.

    Each check must be a dict:
        { "requirement": str, "required_evidence_types": list[EvidenceType] }
    """
    missing = []
    for check in checks:
        req = check["requirement"]
        required_types = check.get("required_evidence_types", [])
        has_all = all(
            any(
                e["requirement"] == req and e["evidence_type"] == et
                for e in evidence
            )
            for et in required_types
        )
        if not has_all:
            missing.append(req)

    return {"ok": len(missing) == 0, "missing": missing}
