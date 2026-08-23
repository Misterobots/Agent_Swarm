"""
coordination/task_queue.py — single-active-run lock for the shared "live_repo"
container mount (Agent_Swarm improving its own codebase).

Originally serialized ALL swarm task creation against one shared dev_sandbox
container (see dev_harness/SWARM_ON_DEVHARNESS.md — no per-task isolation).
Since the per-session-sandbox redesign, every task with a linked project gets
its OWN disposable container (coordination/session_sandbox.py, mode=
"ephemeral") with no shared resource left to protect — this lock is no longer
needed for those, and callers correctly skip it entirely for that mode.

One case still needs it: mode="live_repo" (the single distinguished project
where a session container deliberately bind-mounts the live Agent_Swarm repo,
Design Decision 3 of the plan). Multiple live_repo sessions each get their OWN
container, but all of them mount the SAME host path — two running
concurrently could still interleave `git checkout -B`/`add`/`commit` against
that shared tree. This module's job narrowed to exactly that one case: only
one live_repo-mode run may proceed at a time; everything else waits, visibly,
as status="queued" on the task board. A run resolving to mode="ephemeral" (or,
before a project is chosen at all) never calls try_acquire()/enqueue() and
dispatches immediately, always — there is nothing left for it to collide over.

Reuses utils.gpu_queue.get_redis_client() and its NX/EX mutex + JSON-list
queue idiom (see enqueue_large_request/dequeue_large_request in that module)
rather than a second locking primitive.

Simplification (documented, not silent): the lock key is global, not scoped
per host. If two independent agent_runtime deployments each had their own
live_repo project, this would over-serialize them. That's a safe failure mode
— worst case, an unrelated task waits longer than it needs to — and is
intentionally accepted rather than plumbing a host-scoped key through every
caller, since this is a single-host homelab today.

Dispatch args (the kwargs coordinate_task() needs to actually run a queued
task) are NOT persisted here — they live in an in-process registry in main.py
alongside the endpoint that creates them. A process restart loses queued
(not yet started) tasks' dispatch args; that's acceptable because the startup
reconciliation in swarm_run_store.reconcile_stale_runs() already marks any
'queued' row from before the restart as 'failed' — the same outcome as if it
had been silently dropped.

Both entry points that can resolve to live_repo mode now go through this lock:
POST /v1/tasks (main.py's create_task) and the chat-driven dev-project-picker
resume (routing/gates.py's dev_project_picker handler, reached via POST
/v1/chat/completions with swarm_mode=True). They use it differently, though —
worth knowing which one a given caller gets:

- The composer has a real background dispatcher (main.py's
  _dispatch_task_now/_advance_task_queue): a losing caller is recorded
  status="queued" and automatically dispatched the moment the lock frees up.
- The chat path has no equivalent — its generator IS the live SSE response the
  user is watching in real time, so there's nothing to hand a queued run off
  to later. A losing caller there is REJECTED outright (a clear "please wait
  and try again" chat message, run never starts) rather than silently queued.
  Same correctness guarantee (no two live_repo runs interleave git ops against
  the shared mount), different UX for the loser.
"""
import logging

from utils.gpu_queue import get_redis_client

logger = logging.getLogger("agents.coordination.task_queue")

LIVE_REPO_LOCK_KEY = "swarm:live_repo_lock"
LIVE_REPO_LOCK_TTL = 45 * 60  # seconds — safety valve so a crashed holder can't wedge the queue forever
QUEUED_RUNS_KEY = "swarm:queued_runs"


def try_acquire(coordination_id: str) -> bool:
    """Attempt to claim the live_repo mount for `coordination_id`. Returns True
    if acquired. Fail-open on Redis errors: returns True so a Redis outage
    degrades to "no queueing" (tasks run immediately, same as before this
    module existed) rather than wedging all task creation."""
    try:
        client = get_redis_client()
        return bool(client.set(LIVE_REPO_LOCK_KEY, coordination_id, nx=True, ex=LIVE_REPO_LOCK_TTL))
    except Exception as e:
        logger.warning(f"[TaskQueue] try_acquire failed (fail-open, treating as acquired): {e}")
        return True


def release(coordination_id: str) -> None:
    """Release the live_repo lock IF still held by `coordination_id` — never
    steals another holder's lock (mirrors gpu_queue.request_lock's lock_id
    ownership check before delete)."""
    try:
        client = get_redis_client()
        if client.get(LIVE_REPO_LOCK_KEY) == coordination_id:
            client.delete(LIVE_REPO_LOCK_KEY)
    except Exception as e:
        logger.warning(f"[TaskQueue] release failed (non-fatal): {e}")


def enqueue(coordination_id: str) -> int:
    """Append to the FIFO wait list. Returns 1-based queue position (0 on Redis failure)."""
    try:
        client = get_redis_client()
        client.rpush(QUEUED_RUNS_KEY, coordination_id)
        return client.llen(QUEUED_RUNS_KEY)
    except Exception as e:
        logger.warning(f"[TaskQueue] enqueue failed (non-fatal): {e}")
        return 0


def pop_next() -> str | None:
    """Pop the next queued coordination_id (FIFO), or None if the queue is empty/unreachable."""
    try:
        client = get_redis_client()
        return client.lpop(QUEUED_RUNS_KEY)
    except Exception as e:
        logger.warning(f"[TaskQueue] pop_next failed (non-fatal): {e}")
        return None


def clear_all() -> None:
    """Startup reconciliation: unconditionally clear the lock and wait list.
    Call once at boot, AFTER swarm_run_store.reconcile_stale_runs() has already
    marked any pre-restart 'running'/'queued' rows as 'failed' — by this point
    nothing legitimately holds the lock or belongs in the queue."""
    try:
        client = get_redis_client()
        client.delete(LIVE_REPO_LOCK_KEY)
        client.delete(QUEUED_RUNS_KEY)
    except Exception as e:
        logger.warning(f"[TaskQueue] clear_all failed (non-fatal): {e}")
