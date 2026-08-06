"""
coordination/task_queue.py — single-active-task queue for the shared DevHarness
sandbox.

dev_sandbox is one Docker container with one working tree (confirmed in
dev_harness/SWARM_ON_DEVHARNESS.md — all swarm workers run there, no per-task
isolation). Two tasks running concurrently against different repos would
stomp each other's checkout, so only one task may hold /workspace at a time;
everything else waits, visibly, as status="queued" on the task board.

Reuses utils.gpu_queue.get_redis_client() and its NX/EX mutex + JSON-list
queue idiom (see enqueue_large_request/dequeue_large_request in that module)
rather than a second locking primitive.

Simplification (documented, not silent): the lock key is global, not scoped
per dev_sandbox host. If two independent agent_runtime deployments each ran
their own dev_sandbox container, this would over-serialize them (each waiting
on the other's lock despite not actually sharing a container). That's a safe
failure mode — worst case, an unrelated task waits longer than it needs to —
and is intentionally accepted for v1 rather than plumbing a host-scoped key
through every caller.

Dispatch args (the kwargs coordinate_task() needs to actually run a queued
task) are NOT persisted here — they live in an in-process registry in main.py
alongside the endpoint that creates them. A process restart loses queued
(not yet started) tasks' dispatch args; that's acceptable because the startup
reconciliation in swarm_run_store.reconcile_stale_runs() already marks any
'queued' row from before the restart as 'failed' — the same outcome as if it
had been silently dropped.

KNOWN GAP (not silent — read this before relying on the guarantee above):
this lock is only acquired by POST /v1/tasks (main.py's create_task), the new
direct task-creation endpoint. The pre-existing chat-driven /swarm entry point
(handlers/coordinate.py -> coordinate_task(), reached via POST
/v1/chat/completions with swarm_mode=True) calls coordinate_task() directly
and does NOT go through try_acquire()/enqueue() at all. A chat-originated
/swarm run and a POST /v1/tasks run can therefore still race the shared
/workspace concurrently. This isn't new risk introduced by this module — the
shared sandbox had no isolation between concurrent runs before this queue
existed either — but it does mean the "only one task ever holds /workspace"
guarantee is currently scoped to POST /v1/tasks runs against each other, not
the whole coordinate_task() surface. Unifying the two would mean threading
the lock through handlers/coordinate.py's SSE-streaming call site too, which
is a materially different (synchronous/streaming, not fire-and-forget) shape
— left as unstarted future work, not attempted here.
"""
import logging

from utils.gpu_queue import get_redis_client

logger = logging.getLogger("agents.coordination.task_queue")

WORKSPACE_LOCK_KEY = "swarm:workspace_lock"
WORKSPACE_LOCK_TTL = 45 * 60  # seconds — safety valve so a crashed holder can't wedge the queue forever
QUEUED_RUNS_KEY = "swarm:queued_runs"


def try_acquire(coordination_id: str) -> bool:
    """Attempt to claim the shared sandbox for `coordination_id`. Returns True
    if acquired. Fail-open on Redis errors: returns True so a Redis outage
    degrades to "no queueing" (tasks run immediately, same as before this
    module existed) rather than wedging all task creation."""
    try:
        client = get_redis_client()
        return bool(client.set(WORKSPACE_LOCK_KEY, coordination_id, nx=True, ex=WORKSPACE_LOCK_TTL))
    except Exception as e:
        logger.warning(f"[TaskQueue] try_acquire failed (fail-open, treating as acquired): {e}")
        return True


def release(coordination_id: str) -> None:
    """Release the sandbox lock IF still held by `coordination_id` — never
    steals another holder's lock (mirrors gpu_queue.request_lock's lock_id
    ownership check before delete)."""
    try:
        client = get_redis_client()
        if client.get(WORKSPACE_LOCK_KEY) == coordination_id:
            client.delete(WORKSPACE_LOCK_KEY)
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
        client.delete(WORKSPACE_LOCK_KEY)
        client.delete(QUEUED_RUNS_KEY)
    except Exception as e:
        logger.warning(f"[TaskQueue] clear_all failed (non-fatal): {e}")
