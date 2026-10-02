"""Workspace path resolution for the file tools (plan D8(f) follow-up).

The bug was observed end to end: the admin instructions tell the model its sandbox is
`/workspace/`, the model passes that string back verbatim, and the old resolver joined it
*under* the sandbox root — so `list_dir("/workspace/")` listed `/workspace/workspace/`, a
directory that exists and is empty. The tool returned an honest empty string and the model
invented three entries to fill it.

Assertions use WORKSPACE_ROOT rather than a literal `/workspace` so the same file is true on
the Linux container and on a Windows host, where `Path("/workspace").resolve()` lands
somewhere else entirely.
"""
import os
import sys
from pathlib import Path

import pytest

_AGENTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")
if _AGENTS not in sys.path:
    sys.path.insert(0, _AGENTS)

from tools import file_ops
from tools.file_ops import WORKSPACE_ROOT, _resolve_in_workspace, list_dir


def test_the_sandbox_root_named_absolutely_is_the_root_and_not_a_nested_copy():
    # This is the exact call the model made. It used to resolve to <root>/workspace.
    assert _resolve_in_workspace("/workspace/") == WORKSPACE_ROOT
    assert _resolve_in_workspace("/workspace") == WORKSPACE_ROOT


def test_an_absolute_path_inside_the_sandbox_resolves_as_itself():
    assert _resolve_in_workspace("/workspace/agents") == WORKSPACE_ROOT / "agents"


def test_relative_paths_still_resolve_inside_the_sandbox():
    assert _resolve_in_workspace("agents") == WORKSPACE_ROOT / "agents"
    assert _resolve_in_workspace("./agents/main.py") == WORKSPACE_ROOT / "agents" / "main.py"
    assert _resolve_in_workspace(".") == WORKSPACE_ROOT


def test_traversal_out_of_the_sandbox_is_still_refused():
    for attempt in ("../outside", "agents/../../escape", "/etc/passwd", "/app/agents/main.py"):
        with pytest.raises(PermissionError):
            _resolve_in_workspace(attempt)


def test_a_symlink_style_absolute_path_cannot_escape_by_naming_the_root_prefix():
    # `<root>workspace/…` is a sibling of the sandbox whose name starts with the root's own
    # string; the guard is path-component based, so it must refuse rather than accept the prefix.
    sibling = WORKSPACE_ROOT.parent / "workspace-evil"
    with pytest.raises(PermissionError):
        _resolve_in_workspace(str(sibling / "agents"))


def test_an_empty_directory_says_so_in_words_instead_of_returning_blank(monkeypatch):
    # D8(f): a blank return is what a model narrated over.
    monkeypatch.setattr(file_ops.os, "listdir", lambda p: [])
    out = list_dir("/workspace/")

    assert "empty" in out
    assert out.strip() != ""


def test_a_populated_directory_is_still_a_plain_listing(monkeypatch):
    monkeypatch.setattr(file_ops.os, "listdir", lambda p: [".agents", ".claude", ".drift"])
    assert list_dir(".") == ".agents\n.claude\n.drift"


def test_a_traversal_attempt_reports_the_security_error_rather_than_raising_at_the_model(monkeypatch):
    # The tool is model-facing: it must answer with text, never propagate an exception into
    # the turn.
    out = list_dir("../etc")

    assert out.startswith("Security error listing directory")
