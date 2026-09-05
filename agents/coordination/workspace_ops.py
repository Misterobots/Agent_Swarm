"""
coordination/workspace_ops.py — backend-only sandbox repo checkout.

Runs git clone/checkout directly against a per-session container's /workspace
(coordination/session_sandbox.py) — one specific repo + branch, resolved by
the caller before this runs. Callers: coordination/orchestrator.py's
coordinate_task() (Phase 0, the "New Task" composer / chat swarm path),
main.py's _dev_harness_stream() and terminal_ws() (dev-mode chat and the dev
terminal, each on first use of a freshly-created session container).

Every caller invokes checkout_repo_branch() ONLY immediately after
session_sandbox.ensure_session_container() reports a NEWLY created container
— see that function's docstring. /workspace is therefore always empty when
this runs; checkout_repo_branch() enforces that as a hard precondition rather
than assuming it (see its own docstring for why).

Deliberately NOT registered as an agent tool: this module is never imported by
dev_harness/tool_defs.py and never added to TOOL_DISPATCH in tools/sandbox_ops.py.
Its git commands (clone/checkout) are outside sandbox_ops._GIT_ALLOW by
design — the LLM agent must never gain push/clone/remote-capable git access.
"""
from __future__ import annotations

import logging
import shlex

from dev_files.docker_exec import exec_in_sandbox, WORKSPACE_ROOT, SANDBOX_CONTAINER

logger = logging.getLogger("agents.coordination.workspace_ops")

# Same exec identity tools/sandbox_ops.py uses for the agent-facing git tool —
# keeping files dev-owned (not root-owned) so DevHarness workers (which also
# exec as "dev") can read/write them without a UID mismatch.
_SANDBOX_USER = "dev"


class WorkspacePrepError(RuntimeError):
    """Raised when the sandbox checkout for a repo/branch fails."""


def create_workspace(*, owner_id: str, session_id: str, task_id: str | None = None,
                     repository_ref: str | None = None, branch: str | None = None,
                     base_branch: str | None = None) -> dict:
    from coordination.workspace_lifecycle import create
    return create(owner_id=owner_id, session_id=session_id, task_id=task_id,
                  repository_ref=repository_ref, branch=branch, base_branch=base_branch)


def enter_workspace(*, worktree_id: str, owner_id: str) -> dict:
    from coordination.workspace_lifecycle import transition
    row = transition(worktree_id=worktree_id, owner_id=owner_id, status="entered")
    if not row:
        raise WorkspacePrepError("workspace not found or owned by another owner")
    return row


def workspace_status(*, worktree_id: str, owner_id: str) -> dict | None:
    from coordination.workspace_lifecycle import get
    return get(worktree_id=worktree_id, owner_id=owner_id)


def exit_workspace(*, worktree_id: str, owner_id: str, cleaned: bool = False) -> dict:
    from coordination.workspace_lifecycle import transition
    row = transition(worktree_id=worktree_id, owner_id=owner_id,
                     status="cleaned" if cleaned else "exited")
    if not row:
        raise WorkspacePrepError("workspace not found or owned by another owner")
    return row


def _sh(cmd: str, timeout: int) -> tuple[int, str, str]:
    return exec_in_sandbox("sh", "-c", cmd, timeout=timeout, user=_SANDBOX_USER)


def checkout_repo_branch(git_url: str, branch: str, base_branch: str = "main") -> dict:
    """
    Clone `git_url` into an EMPTY session container's /workspace and check out
    `branch` (created from origin/`base_branch` if `branch` doesn't exist on
    the remote).

    Hard precondition, enforced (not assumed): /workspace must already be
    empty. Every caller invokes this immediately after
    session_sandbox.ensure_session_container() creates a fresh container, so
    that's always true in practice — a prior version of this function instead
    handled a non-empty /workspace by clearing it before re-cloning, and
    because /workspace inside the old shared dev_sandbox container was
    bind-mounted to the LIVE Agent_Swarm repo, that clear step nearly deleted
    the live repo through the mount (the incident that motivated the whole
    per-session-sandbox redesign — see Design Decision 7 of that plan).
    Leaving the old clear-and-reclone logic in place as defensive code that
    should never trigger was rejected on purpose: if the "always fresh"
    invariant is ever violated by a future bug, this fails loudly instead of
    silently destroying whatever was already there.

    Returns {"git_url", "branch", "base_branch"} on success.
    Raises WorkspacePrepError with a human-readable message on failure.
    """
    if not git_url or not (git_url.startswith("https://") or git_url.startswith("http://")):
        raise WorkspacePrepError("git_url must use https:// scheme")
    if not branch or branch.startswith("-"):
        raise WorkspacePrepError(f"invalid branch name: {branch!r}")
    if not base_branch or base_branch.startswith("-"):
        raise WorkspacePrepError(f"invalid base_branch name: {base_branch!r}")

    q_url = shlex.quote(git_url)
    q_branch = shlex.quote(branch)
    q_base = shlex.quote(base_branch)
    root = WORKSPACE_ROOT

    rc, out, err = _sh(f"find {root} -mindepth 1 -maxdepth 1 2>&1 | head -1", timeout=10)
    if out.strip():
        raise WorkspacePrepError(
            f"{root} is not empty (expected a fresh session container) — refusing to touch it. "
            f"This should be impossible; investigate session_sandbox provisioning for this run."
        )

    rc, out, err = _sh(f"git clone {q_url} {root} 2>&1", timeout=180)
    if rc != 0:
        raise WorkspacePrepError(f"git clone failed: {(err or out).strip()[:500]}")

    # Checkout the target branch — DWIM-creates a local tracking branch if it
    # already exists on origin; otherwise branch fresh off origin/base_branch;
    # final fallback branches off current HEAD if base_branch isn't found either.
    rc, out, err = _sh(
        f"cd {root} && "
        f"(git checkout {q_branch} 2>&1 || "
        f" git checkout -b {q_branch} origin/{q_base} 2>&1 || "
        f" git checkout -b {q_branch} 2>&1)",
        timeout=30,
    )
    if rc != 0:
        raise WorkspacePrepError(f"git checkout failed for branch {branch!r}: {(err or out).strip()[:500]}")

    rc, out, _err = _sh(f"cd {root} && git rev-parse --abbrev-ref HEAD", timeout=10)
    landed_branch = out.strip()
    if landed_branch != branch:
        raise WorkspacePrepError(f"checkout landed on {landed_branch!r}, expected {branch!r}")

    logger.info(f"[workspace_ops] {root} ready: {git_url} @ {branch}")
    return {"git_url": git_url, "branch": branch, "base_branch": base_branch}


def checkout_local_project(source_path: str) -> dict:
    """
    Seed an EMPTY session container's /workspace from a "blank" (local, no
    git_url) dev project's persisted files, tar'd out of the shared
    dev_sandbox container — where dev_projects/routes.py's
    provision_project_dir() git-inits and stores them — and untar'd into the
    current session container.

    There's no shared filesystem between the shared dev_sandbox and a
    per-task ephemeral container, so this moves bytes through the host
    process the same way finalize_task_branch() (below) and
    tools/github_push_ops.py already do for a git bundle: tar/base64 out,
    base64/untar in. Same technique, applied to a plain directory instead of
    a git bundle.

    Same hard "target /workspace must be empty" precondition as
    checkout_repo_branch() above — see that function's docstring for why
    it's enforced rather than assumed.

    Raises WorkspacePrepError on failure.
    """
    root = WORKSPACE_ROOT

    rc, out, err = _sh(f"find {root} -mindepth 1 -maxdepth 1 2>&1 | head -1", timeout=10)
    if out.strip():
        raise WorkspacePrepError(
            f"{root} is not empty (expected a fresh session container) — refusing to touch it. "
            f"This should be impossible; investigate session_sandbox provisioning for this run."
        )

    q_src = shlex.quote(source_path)
    # Explicit container_name bypasses the thread-local session-container
    # resolution — by this point it's already pointing at the NEW ephemeral
    # container, but this read must target the shared dev_sandbox instead.
    rc, tar_b64, err = exec_in_sandbox(
        "sh", "-c", f"tar -C {q_src} -cf - . | base64 -w0",
        timeout=60, container_name=SANDBOX_CONTAINER,
    )
    if rc != 0:
        raise WorkspacePrepError(f"failed to read local project at {source_path!r}: {(err or tar_b64).strip()[:500]}")
    if not tar_b64.strip():
        raise WorkspacePrepError(f"local project at {source_path!r} produced no data to check out")

    import base64 as _base64
    tar_bytes = _base64.b64decode(tar_b64.strip())

    # Untar into the current (new ephemeral) session container's /workspace —
    # no container_name override here, so this targets whatever's current.
    rc, out, err = exec_in_sandbox(
        "sh", "-c", f"tar -C {shlex.quote(root)} -xf -",
        input_bytes=tar_bytes, timeout=60, user=_SANDBOX_USER,
    )
    if rc != 0:
        raise WorkspacePrepError(f"failed to check out local project into {root}: {(err or out).strip()[:500]}")

    logger.info(f"[workspace_ops] {root} ready: local project from {source_path}")
    return {"source_path": source_path}


# Bundle size cap — protects the swarm_run_repo BYTEA column and keeps the
# later push/confirm reconstruction fast. A task whose diff genuinely exceeds
# this (e.g. an accidentally-committed dependency tree) should be caught by
# review before it ever reaches push anyway.
MAX_BUNDLE_BYTES = 8 * 1024 * 1024


def finalize_task_branch(coordination_id: str) -> tuple[str, bytes]:
    """
    Commit whatever is dirty in the shared sandbox /workspace onto a fresh
    local branch named memex/<coordination_id>, then export that branch as a
    self-contained git bundle.

    Must be called BEFORE Phase B's workspace lock is released — otherwise a
    subsequent task could repoint /workspace at a different repo before this
    runs, silently bundling the wrong tree. The bundle exists precisely so
    the LATER push/confirm step (which may happen minutes or hours after this
    call, once a human reviews and approves) never depends on /workspace's
    state at that later time.

    Returns (local_branch, bundle_bytes). Raises WorkspacePrepError on failure.
    """
    root = WORKSPACE_ROOT
    local_branch = f"memex/{coordination_id}"
    q_branch = shlex.quote(local_branch)

    rc, _out, _err = _sh(f"cd {root} && git rev-parse --is-inside-work-tree >/dev/null 2>&1", timeout=10)
    if rc != 0:
        raise WorkspacePrepError(f"{root} is not a git repo — nothing to finalize")

    # -B (not -b): always (re)create at current HEAD, so a retry after a
    # transient failure doesn't collide with a branch this call left behind.
    rc, out, err = _sh(
        f"cd {root} && git checkout -B {q_branch} 2>&1 "
        f"&& git add -A 2>&1 "
        f"&& (git diff --cached --quiet || git commit -m 'Memex task {coordination_id}' 2>&1)",
        timeout=60,
    )
    if rc != 0:
        raise WorkspacePrepError(f"failed to finalize branch {local_branch!r}: {(err or out).strip()[:500]}")

    bundle_path = f"/tmp/{coordination_id}.bundle"
    q_bundle = shlex.quote(bundle_path)
    rc, out, err = _sh(f"cd {root} && git bundle create {q_bundle} {q_branch} 2>&1", timeout=60)
    if rc != 0:
        raise WorkspacePrepError(f"git bundle create failed: {(err or out).strip()[:500]}")

    rc, size_out, _err = _sh(f"wc -c < {q_bundle}", timeout=10)
    try:
        bundle_size = int(size_out.strip())
    except ValueError:
        bundle_size = 0
    if rc == 0 and bundle_size > MAX_BUNDLE_BYTES:
        _sh(f"rm -f {q_bundle}", timeout=10)
        raise WorkspacePrepError(
            f"bundle too large ({bundle_size} bytes > {MAX_BUNDLE_BYTES} limit) — "
            f"push isn't available for this task"
        )

    rc, b64_out, err = _sh(f"base64 -w0 {q_bundle}", timeout=30)
    _sh(f"rm -f {q_bundle}", timeout=10)  # best-effort cleanup regardless of outcome
    if rc != 0:
        raise WorkspacePrepError(f"failed to read bundle: {(err or b64_out).strip()[:500]}")

    import base64 as _base64
    bundle_bytes = _base64.b64decode(b64_out.strip())
    logger.info(f"[workspace_ops] Bundled {local_branch} ({len(bundle_bytes)} bytes)")
    return local_branch, bundle_bytes
