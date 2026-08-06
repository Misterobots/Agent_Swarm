"""
coordination/workspace_ops.py — backend-only sandbox repo checkout.

Runs git clone/fetch/checkout directly against dev_sandbox's shared root
/workspace, for tasks created via the "New Task" composer (a specific repo +
branch chosen up front) rather than the chat-driven swarm flow, which just
operates on whatever /workspace already contains.

Deliberately NOT registered as an agent tool: this module is never imported by
dev_harness/tool_defs.py and never added to TOOL_DISPATCH in tools/sandbox_ops.py.
Its git commands (clone/fetch/checkout) are outside sandbox_ops._GIT_ALLOW by
design — the LLM agent must never gain push/clone/remote-capable git access.
Its only caller is coordination/orchestrator.py's coordinate_task(), itself
only reachable from a route handler that has already resolved an owner.
"""
from __future__ import annotations

import logging
import shlex

from dev_files.docker_exec import exec_in_sandbox, WORKSPACE_ROOT

logger = logging.getLogger("agents.coordination.workspace_ops")

# Same exec identity tools/sandbox_ops.py uses for the agent-facing git tool —
# keeping files dev-owned (not root-owned) so DevHarness workers (which also
# exec as "dev") can read/write them without a UID mismatch.
_SANDBOX_USER = "dev"


class WorkspacePrepError(RuntimeError):
    """Raised when the sandbox checkout for a repo/branch fails."""


def _sh(cmd: str, timeout: int) -> tuple[int, str, str]:
    return exec_in_sandbox("sh", "-c", cmd, timeout=timeout, user=_SANDBOX_USER)


def checkout_repo_branch(git_url: str, branch: str, base_branch: str = "main") -> dict:
    """
    Ensure dev_sandbox's shared /workspace has `git_url` checked out on `branch`
    (created from origin/`base_branch` if `branch` doesn't exist on the remote).

    Safe to call only while Phase B's single-active-task lock is held — this
    wipes and re-clones /workspace when switching to a different repo, which
    would corrupt a concurrently-running task's working tree otherwise.

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

    rc, out, _err = _sh(
        f"cd {root} && git rev-parse --is-inside-work-tree >/dev/null 2>&1 "
        f"&& git remote get-url origin 2>/dev/null || true",
        timeout=10,
    )
    current_remote = out.strip()

    if current_remote != git_url:
        logger.info(
            f"[workspace_ops] Repo switch ({current_remote!r} -> {git_url!r}) — "
            f"clearing and re-cloning {root}"
        )
        rc, out, err = _sh(f"find {root} -mindepth 1 -delete", timeout=30)
        if rc != 0:
            raise WorkspacePrepError(f"failed to clear sandbox workspace: {(err or out).strip()[:500]}")
        rc, out, err = _sh(f"git clone {q_url} {root} 2>&1", timeout=180)
        if rc != 0:
            raise WorkspacePrepError(f"git clone failed: {(err or out).strip()[:500]}")
    else:
        rc, out, err = _sh(f"cd {root} && git fetch origin 2>&1", timeout=120)
        if rc != 0:
            raise WorkspacePrepError(f"git fetch failed: {(err or out).strip()[:500]}")

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
