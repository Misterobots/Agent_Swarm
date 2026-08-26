from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from dev_harness.approval_scope import rules_for_workspace, workspace_key


def test_workspace_identity_is_opaque_and_stable():
    assert workspace_key("C:/project") == workspace_key("C:/project")
    assert workspace_key("C:/project") != workspace_key("C:/other")
    assert "project" not in workspace_key("C:/project")


def test_approval_rules_do_not_cross_workspaces_or_legacy_shape():
    first = workspace_key("C:/first")
    second = workspace_key("C:/second")
    data = {
        "owner": {first: ["write_file"]},
        "legacy-owner": ["write_file"],
    }
    assert rules_for_workspace(data, "owner", first) == {"write_file"}
    assert rules_for_workspace(data, "owner", second) == set()
    assert rules_for_workspace(data, "legacy-owner", first) == set()
