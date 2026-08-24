"""Postgres-backed regression coverage for durable parity state.

Run with AGNO_DB_URL set against an isolated test database. The tests are
skipped when that environment variable is absent so the normal unit suite
does not require infrastructure.
"""

from __future__ import annotations

import importlib
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("AGNO_DB_URL"), reason="AGNO_DB_URL is not configured"
)

from agents.coordination import workspace_lifecycle
from agents.dev_harness import approval_service


@pytest.fixture(scope="module", autouse=True)
def durable_tables():
    approval_service.init_table()
    workspace_lifecycle.init_table()
    yield
    with approval_service._db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM dev_approval_requests WHERE call_id LIKE 'codex-db-test-%'")
            cur.execute("DELETE FROM isolated_workspaces WHERE owner_id LIKE 'codex-db-test-%'")


def test_approval_lookup_survives_module_reload_and_duplicate_decision_is_idempotent():
    owner = "codex-db-test-" + uuid4().hex
    call_id = "codex-db-test-" + uuid4().hex
    created = approval_service.request_approval(
        owner_id=owner,
        call_id=call_id,
        tool_name="write_file",
        arguments={"path": "/workspace/a", "content": "redacted"},
    )
    assert created and created["call_id"] == call_id

    reloaded = importlib.reload(approval_service)
    persisted = reloaded.get_request(owner, call_id)
    assert persisted and persisted["decision"] is None

    approved = reloaded.decide(
        owner_id=owner, call_id=call_id, decision="approved", decided_by=owner
    )
    denied_retry = reloaded.decide(
        owner_id=owner, call_id=call_id, decision="denied", decided_by=owner
    )
    assert approved and approved["decision"] == "approved"
    assert denied_retry and denied_retry["decision"] == "approved"


def test_concurrent_approval_decisions_produce_one_durable_outcome():
    owner = "codex-db-test-" + uuid4().hex
    call_id = "codex-db-test-" + uuid4().hex
    assert approval_service.request_approval(
        owner_id=owner, call_id=call_id, tool_name="run_command", arguments={}
    )

    def decide_once():
        return approval_service.decide(
            owner_id=owner, call_id=call_id, decision="approved", decided_by=owner
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: decide_once(), range(2)))

    assert all(result and result["decision"] == "approved" for result in results)
    persisted = approval_service.get_request(owner, call_id)
    assert persisted and len(persisted["audit"]) == 1


def test_workspace_record_survives_module_reload_and_owner_scope_is_enforced():
    owner = "codex-db-test-" + uuid4().hex
    session = "codex-db-test-" + uuid4().hex
    created = workspace_lifecycle.create(owner_id=owner, session_id=session)
    assert created and created["lifecycle_status"] == "created"

    reloaded = importlib.reload(workspace_lifecycle)
    assert reloaded.get(worktree_id=created["worktree_id"], owner_id=owner)
    assert reloaded.get(worktree_id=created["worktree_id"], owner_id=owner + "-other") is None

    transitioned = reloaded.transition(
        worktree_id=created["worktree_id"], owner_id=owner, status="entered"
    )
    assert transitioned and transitioned["lifecycle_status"] == "entered"
