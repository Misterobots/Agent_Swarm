"""Unit tests for the DevHarness permission-mode contract."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

from dev_harness.permissions import EDIT_TOOLS, PermissionGate


def test_plan_mode_blocks_everything_except_read_and_planning_tools():
    gate = PermissionGate("plan")

    assert gate.check("read_file")[0] is True
    assert gate.check("TodoWrite")[0] is True
    assert gate.check("write_file")[0] is False
    assert gate.check("run_command")[0] is False
    assert gate.auto_approve("write_file") is False


def test_accept_edits_only_auto_approves_direct_file_edits():
    gate = PermissionGate("acceptEdits")

    assert EDIT_TOOLS == {"write_file", "edit_file"}
    assert gate.check("write_file")[0] is True
    assert gate.auto_approve("write_file") is True
    assert gate.auto_approve("edit_file") is True
    assert gate.auto_approve("run_command") is False
    assert gate.auto_approve("git") is False
    assert gate.auto_approve("Task") is False


def test_bypass_mode_auto_approves_tools_after_route_authorization():
    gate = PermissionGate("bypass")

    assert gate.bypass_mode is True
    assert gate.check("run_command")[0] is True
    assert gate.auto_approve("run_command") is True
    assert gate.auto_approve("Task") is True


def test_unknown_mode_is_safe_default():
    gate = PermissionGate("not-a-mode")

    assert gate.mode == "default"
    assert gate.bypass_mode is False
    assert gate.auto_approve("write_file") is False
