"""Postgres-backed regression coverage for workspace lifecycle state."""

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


@pytest.fixture(scope="module", autouse=True)
def durable_tables():
    workspace_lifecycle.init_table()
    yield
    with workspace_lifecycle._db() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM isolated_workspaces WHERE owner_id LIKE 'codex-lifecycle-test-%'"
        )


def _ids():
    return (
        "codex-lifecycle-test-" + uuid4().hex,
        "codex-lifecycle-test-" + uuid4().hex,
    )


def test_record_survives_reload_and_enforces_owner_scope():
    owner, session = _ids()
    created = workspace_lifecycle.create(owner_id=owner, session_id=session)
    assert created and created["lifecycle_status"] == "created"

    reloaded = importlib.reload(workspace_lifecycle)
    assert reloaded.get(worktree_id=created["worktree_id"], owner_id=owner)
    assert reloaded.get(
        worktree_id=created["worktree_id"], owner_id=owner + "-other"
    ) is None

    entered = reloaded.transition(
        worktree_id=created["worktree_id"], owner_id=owner, status="entered"
    )
    assert entered and entered["lifecycle_status"] == "entered"
    assert reloaded.transition(
        worktree_id=created["worktree_id"], owner_id=owner, status="created"
    ) is None


def test_concurrent_transition_has_one_durable_winner():
    owner, session = _ids()
    created = workspace_lifecycle.create(owner_id=owner, session_id=session)
    assert created

    def enter_once():
        return workspace_lifecycle.transition(
            worktree_id=created["worktree_id"], owner_id=owner, status="entered"
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: enter_once(), range(2)))

    assert sum(result is not None for result in results) == 1
    persisted = workspace_lifecycle.get(
        worktree_id=created["worktree_id"], owner_id=owner
    )
    assert persisted and persisted["lifecycle_status"] == "entered"


def test_expired_active_record_is_marked_abandoned():
    owner, session = _ids()
    created = workspace_lifecycle.create(
        owner_id=owner, session_id=session, lease_seconds=60
    )
    assert created
    abandoned = workspace_lifecycle.reap_abandoned(now=created["lease_until"] + 1)
    assert created["worktree_id"] in abandoned
    persisted = workspace_lifecycle.get(
        worktree_id=created["worktree_id"], owner_id=owner
    )
    assert persisted and persisted["lifecycle_status"] == "abandoned"
