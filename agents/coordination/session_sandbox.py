"""
coordination/session_sandbox.py — per-session Docker container lifecycle.

Why this exists: a near-miss data-loss incident showed that the swarm's
previous shared `dev_sandbox` container is unsafe as a general mechanism.
`/workspace` inside `dev_sandbox` is bind-mounted to the LIVE Agent_Swarm
repo root (`../:/workspace` in execution_plane/docker-compose.yml), and a
"clear workspace before cloning a different repo" step
(workspace_ops.checkout_repo_branch) almost deleted the live repo through
that mount — a permission wall was the only thing that saved it, not any
structural guarantee. See Design Decision 2 of the per-session-sandbox plan.

The fix: every code-writing session gets its OWN disposable container
instead of sharing one, with NO bind mount to anything precious. This
module owns that container's lifecycle:

  - ensure_session_container()   — idempotent get-or-create
  - release_session_container()  — best-effort teardown, never raises
  - cleanup_orphans()             — startup reconciliation sweep

Two modes:

  - "ephemeral" (default): a freshly-run container from
    home-ai-lab/dev-sandbox:latest with ABSOLUTELY ZERO `volumes=`.
    Dockerfile.dev-sandbox already creates the `dev` user and `chown`s
    /workspace at build time, so a container instantiated from that image
    with no mounts has a writable, empty, correctly-owned /workspace living
    only in the container's own writable layer — there is structurally
    nothing for a future "clear workspace" bug to reach. This is the core
    safety property of this module; do not add a `volumes=` entry to the
    ephemeral path under any circumstance.

  - "live_repo" (the one distinguished exception — bind-mounts the live
    repo on purpose, for the single legitimate case of the swarm improving
    its own codebase, Design Decision 3 of the plan): the host mount source
    is introspected from agent_runtime's OWN /workspace mount at call time
    (_resolve_own_workspace_mount), never hardcoded. Callers resolve which
    mode to use from dev_projects.store.get_or_create_live_repo_project()'s
    `source` field — never guessed here. Because multiple live_repo sessions
    would each get their OWN container but still share the SAME host path,
    this module intentionally does NOT serialize them — that's
    coordination/task_queue.py's job (a Redis lock scoped to this mode only,
    since ephemeral sessions have nothing left to collide over).

Container identity resolution (which container a running tool call should
target) is a SEPARATE, already-implemented concern —
coordination/sandbox_identity.py's threading.local() mechanism, consulted
by tools/sandbox_ops.py and dev_files/docker_exec.py. This module only
creates/destroys the containers; wiring their names into that thread-local
so tool calls actually land inside them is coordination/orchestrator.py's
job. This module is intentionally standalone: nothing here is registered in
a tool dispatch table (same posture as tools/github_push_ops.py) — it is an
orchestration-layer primitive, never LLM-reachable.

Known limitation: ensure_session_container() attaches the new container to
every network the CALLING agent_runtime container is itself attached to
(see _resolve_own_networks), by passing the first as `network=` at create
time and best-effort `.connect()`-ing the rest afterward. If a later
compose change puts agent_runtime on additional networks whose names
change dynamically, this still works (nothing is hardcoded) — but the
best-effort `.connect()` calls for anything beyond the first network log a
warning and continue rather than failing the whole call, so a partially-
attached container is possible in principle. In practice agent_runtime is
only ever on one or two networks (see execution_plane/docker-compose.yml),
so this has not been a problem.

Usage (intended call shape for the next phase's implementer, and for
manual verification of this phase):

    from coordination.session_sandbox import (
        ensure_session_container,
        release_session_container,
        cleanup_orphans,
    )

    name, created = ensure_session_container("coord-test123")
    # -> ("dev-task-coord-test123", True); idempotent — a second call with
    #    the same coordination_id returns the same name (created=False)
    #    without creating anything new.
    #
    # Manual inspection at this point (see the plan's Verification section):
    #   docker inspect dev-task-coord-test123 --format '{{json .Mounts}}'  -> []
    #   docker exec dev-task-coord-test123 ls /                            -> stock tree, no repo files

    release_session_container("coord-test123")
    # -> stops + removes the container; safe to call even if it's already gone.

    # At app startup, after other reconciliation (swarm_run_store.reconcile_stale_runs(),
    # task_queue.clear_all()) has already run:
    n = cleanup_orphans()
    # -> force-removes any leftover dev-task-* containers from a crashed process,
    #    returns how many were reaped.
"""
from __future__ import annotations

import logging
import os
import socket

logger = logging.getLogger("agents.coordination.session_sandbox")

# Image every ephemeral session container is instantiated from. Built by
# execution_plane/Dockerfile.dev-sandbox; already creates user `dev` and
# chowns /workspace, so a freshly-run container needs no further setup.
SESSION_IMAGE = os.getenv("SESSION_SANDBOX_IMAGE", "home-ai-lab/dev-sandbox:latest")

# Labels used to identify session containers for orphan cleanup. The value
# is always the string "true" (Docker container labels are string:string).
SESSION_CONTAINER_LABEL = "agent_swarm.session_container"
COORDINATION_ID_LABEL = "agent_swarm.coordination_id"


def _container_name(coordination_id: str) -> str:
    return f"dev-task-{coordination_id}"


def _client_and_module():
    """Import the docker SDK and connect to the Docker Engine API.

    Mirrors dev_files/docker_exec.py::_get_container()'s error-handling
    convention: wrap ImportError with a clear message, raise RuntimeError
    (never let a raw docker/requests exception escape this module).
    Returns (docker_module, client) — callers need the module itself for
    docker.errors.NotFound.
    """
    try:
        import docker
    except ImportError:
        raise RuntimeError(
            "docker Python package not installed; add 'docker' to agent_runtime requirements."
        )
    try:
        client = docker.from_env()
    except Exception as exc:
        raise RuntimeError(f"Cannot connect to Docker daemon: {exc}") from exc
    return docker, client


def _resolve_self_container(client):
    """Return THIS agent_runtime container's own docker SDK Container object.

    Docker sets a container's hostname to its own short container ID by
    default, exposed to the process via the HOSTNAME env var (with
    socket.gethostname() as a fallback — same value in practice). Shared by
    every "introspect my own config rather than hardcode it" helper below.

    Raises RuntimeError if self-identification fails outright — there is no
    safe fallback to guess at here.
    """
    self_id = os.getenv("HOSTNAME") or socket.gethostname()
    if not self_id:
        raise RuntimeError(
            "Cannot determine this container's own id (HOSTNAME unset and "
            "socket.gethostname() empty)."
        )
    try:
        return client.containers.get(self_id)
    except Exception as exc:
        raise RuntimeError(f"Cannot introspect own container '{self_id}': {exc}") from exc


def _resolve_own_networks(client) -> list[str]:
    """Introspect the Docker network(s) THIS agent_runtime container is
    attached to, so a freshly-created session container lands somewhere it
    can actually be reached via container.exec_run(...).

    A bare client.containers.run() with no network= argument lands on
    Docker's default `bridge` network — not wherever agent_runtime itself
    is (compose gives it a project-scoped network whose name varies, e.g.
    `execution_plane_execution_net`). Hardcoding that name would break the
    moment the compose project name changes, so this resolves it live.

    Returns the list of attached network names (at least one).
    """
    self_container = _resolve_self_container(client)
    networks = list(
        self_container.attrs.get("NetworkSettings", {}).get("Networks", {}).keys()
    )
    if not networks:
        raise RuntimeError(
            "Own container reports no attached networks — cannot determine "
            "where to attach the session container."
        )
    return networks


def _resolve_own_workspace_mount(client) -> str:
    """Introspect the HOST (or WSL2-VM) path THIS agent_runtime container's own
    /workspace bind mount actually resolves to, so a live_repo session
    container can be given the identical mount without hardcoding a path that
    would break the moment the compose project's relative-path context moves.

    Returns the Source path of the Mount whose Destination is "/workspace".
    Raises RuntimeError if agent_runtime has no such mount (would mean this
    function was called in an environment that isn't actually the live-repo
    bind-mount setup this mode assumes).
    """
    self_container = _resolve_self_container(client)
    for mount in self_container.attrs.get("Mounts", []):
        if mount.get("Destination") == "/workspace":
            return mount["Source"]
    raise RuntimeError(
        "This agent_runtime container has no /workspace mount to mirror — "
        "live_repo mode assumes the same ../:/workspace bind this container "
        "itself runs with (see execution_plane/docker-compose.yml)."
    )


def ensure_session_container(coordination_id: str, mode: str = "ephemeral") -> tuple[str, bool]:
    """Idempotently ensure a per-session Docker container exists for
    `coordination_id`, and return (name, created).

    `created` is True only when this call actually provisioned a new
    container, False when an existing one was reused — callers that need to
    do one-time setup on a fresh container (e.g. cloning a repo into it)
    branch on this instead of re-doing that setup on every call. The
    composer/swarm path (orchestrator.py) ignores it: a coordination_id is
    always new there, so it's always True in practice.

    Idempotent by design: multiple workers within one swarm run (or,  for
    long-lived dev-mode chat, multiple turns of one conversation) share the
    same coordination_id/session key, and therefore the same container — if
    `dev-task-{coordination_id}` already exists, it is returned immediately
    with no new container created.

    mode="ephemeral" (default): creates a container from SESSION_IMAGE with
    NO host bind mounts at all — this is the core safety property (see
    module docstring). Attached to every network the calling agent_runtime
    container is itself on (see _resolve_own_networks), labeled for
    cleanup_orphans() to find later.

    mode="local": identical container shape to "ephemeral" (no volumes) —
    the only difference is what the CALLER does with it afterward.
    orchestrator.py's Phase 0 seeds a "local" container's /workspace from a
    blank dev project's persisted files (coordination/workspace_ops.
    checkout_local_project) instead of git-cloning a git_url into it. Kept as
    a distinct mode string (not reusing "ephemeral") so that distinction is
    explicit at the call site rather than inferred from repo_context shape.

    mode="live_repo": the ONE distinguished exception — bind-mounts the live
    Agent_Swarm repo on purpose, for the single legitimate case of the swarm
    improving its own codebase (Design Decision 3 of the plan). The host
    mount source is introspected from agent_runtime's OWN /workspace mount
    (see _resolve_own_workspace_mount), never hardcoded. Concurrency between
    multiple live_repo sessions is NOT this module's job — it's a Redis lock
    at the caller level (coordination/task_queue.py, scoped to this mode
    only), since two containers legitimately sharing one host path can still
    race each other on git operations even though each has its own container.

    Raises:
        ValueError    — empty coordination_id, or an unrecognized mode
        RuntimeError  — Docker unreachable, or container creation failed
    """
    if not coordination_id:
        raise ValueError("coordination_id must not be empty")
    if mode not in ("ephemeral", "local", "live_repo"):
        raise ValueError(f"Unknown session container mode: {mode!r}")

    name = _container_name(coordination_id)
    docker, client = _client_and_module()

    try:
        existing = client.containers.get(name)
        logger.info(f"[SessionSandbox] Reusing existing session container '{name}'.")
        return existing.name, False
    except docker.errors.NotFound:
        pass
    except Exception as exc:
        raise RuntimeError(
            f"Cannot check for existing session container '{name}': {exc}"
        ) from exc

    networks = _resolve_own_networks(client)
    primary_network, *extra_networks = networks

    run_kwargs = dict(
        image=SESSION_IMAGE,
        name=name,
        command=["tail", "-f", "/dev/null"],
        detach=True,
        user="dev",
        working_dir="/workspace",
        network=primary_network,
        labels={
            SESSION_CONTAINER_LABEL: "true",
            COORDINATION_ID_LABEL: coordination_id,
        },
    )

    if mode == "live_repo":
        host_workspace = _resolve_own_workspace_mount(client)
        run_kwargs["volumes"] = {host_workspace: {"bind": "/workspace", "mode": "rw"}}
        logger.info(
            f"[SessionSandbox] Creating live_repo session container '{name}' "
            f"(image={SESSION_IMAGE}, network={primary_network}, mount={host_workspace})."
        )
    else:
        # ephemeral/local: deliberately NO `volumes=` key at all — see module
        # docstring. Do not add one here under any circumstance.
        logger.info(
            f"[SessionSandbox] Creating {mode} session container '{name}' "
            f"(image={SESSION_IMAGE}, network={primary_network})."
        )

    try:
        container = client.containers.run(**run_kwargs)
    except Exception as exc:
        raise RuntimeError(f"Failed to create session container '{name}': {exc}") from exc

    for extra in extra_networks:
        try:
            client.networks.get(extra).connect(container)
        except Exception as exc:
            logger.warning(
                f"[SessionSandbox] Could not attach '{name}' to extra network "
                f"'{extra}' (continuing with '{primary_network}' only): {exc}"
            )

    return container.name, True


def release_session_container(coordination_id: str) -> None:
    """Best-effort stop+remove of a session container. NEVER raises —
    mirrors task_queue.py::release()'s "never blow up the caller" posture,
    since this typically runs in a `finally` block covering every return
    path of a swarm run.

    Safe to call even if the container was never created or is already
    gone. Tries a graceful stop(timeout=5) + remove() first; if that fails
    for any reason, falls back to remove(force=True).
    """
    if not coordination_id:
        return
    name = _container_name(coordination_id)

    try:
        docker, client = _client_and_module()
    except Exception as exc:
        logger.warning(
            f"[SessionSandbox] release_session_container: Docker unavailable, "
            f"could not release '{name}': {exc}"
        )
        return

    try:
        container = client.containers.get(name)
    except docker.errors.NotFound:
        return
    except Exception as exc:
        logger.warning(
            f"[SessionSandbox] release_session_container: could not look up '{name}': {exc}"
        )
        return

    try:
        container.stop(timeout=5)
        container.remove()
        logger.info(f"[SessionSandbox] Released session container '{name}'.")
        return
    except Exception as exc:
        logger.warning(
            f"[SessionSandbox] Graceful stop+remove failed for '{name}' ({exc}); "
            "forcing removal."
        )

    try:
        container.remove(force=True)
        logger.info(f"[SessionSandbox] Force-removed session container '{name}'.")
    except Exception as exc:
        logger.warning(f"[SessionSandbox] Force-remove also failed for '{name}': {exc}")


def cleanup_orphans() -> int:
    """Startup reconciliation: force-remove every leftover session
    container from a prior process's crash.

    Intended to be called once at app startup, AFTER other reconciliation
    steps (swarm_run_store.reconcile_stale_runs(), task_queue.clear_all())
    have already run — mirrors reconcile_stale_runs()'s framing: by the
    time this runs, nothing should legitimately hold a session container,
    so everything found here is treated as a leak, not a live session.

    Fail-open like the rest of this module's startup-adjacent helpers:
    returns 0 (logs a warning, does not raise) if Docker is unreachable.

    Returns the number of containers removed. Logs a warning when > 0,
    since every one found is evidence of an unclean shutdown.
    """
    try:
        docker, client = _client_and_module()
    except Exception as exc:
        logger.warning(f"[SessionSandbox] cleanup_orphans: Docker unavailable, skipping: {exc}")
        return 0

    try:
        orphans = client.containers.list(
            all=True, filters={"label": f"{SESSION_CONTAINER_LABEL}=true"}
        )
    except Exception as exc:
        logger.warning(f"[SessionSandbox] cleanup_orphans: could not list containers: {exc}")
        return 0

    removed = 0
    for container in orphans:
        try:
            container.remove(force=True)
            removed += 1
        except Exception as exc:
            logger.warning(
                f"[SessionSandbox] cleanup_orphans: could not remove '{container.name}': {exc}"
            )

    if removed:
        logger.warning(
            f"[SessionSandbox] cleanup_orphans reaped {removed} leftover session "
            "container(s) at startup — each one indicates a prior process crashed "
            "without release_session_container() running (e.g. a mid-run "
            "agent_runtime restart)."
        )
    return removed
