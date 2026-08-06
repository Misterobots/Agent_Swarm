"""
tools/github_push_ops.py — backend-only git push + GitHub PR creation.

Never imported by agents/dev_harness/tool_defs.py and never registered in
TOOL_DISPATCH (agents/tools/sandbox_ops.py). Its only caller is the
POST /v1/tasks/{id}/push/confirm route handler in main.py — i.e. a human HTTP
request that has already passed owner-scoped auth, diff-approval, and a
single-use confirm-token check. This is the structural guarantee behind the
"extensive approval gates" requirement: a function that exists in neither
dispatch table is categorically unreachable from any LLM tool loop.

Runs the git side of the push INSIDE dev_sandbox (via docker exec), not in
agent_runtime's own process — that's the container with git + proven network
egress to arbitrary git remotes (workspace_ops.checkout_repo_branch and
dev_projects' git-clone path both already depend on exactly that egress).
Reconstructs the branch from the bundle bytes captured at task-completion
time (see workspace_ops.finalize_task_branch) rather than the live shared
/workspace, which may have moved on to a different task by the time a human
gets around to confirming — see swarm_run_repo_store's bundle_data column.

PR creation is a separate, pure-HTTPS call made directly from this process
(no git involved), using the same raw-urllib style as the existing GitHub
OAuth device-flow code — no new SDK dependency.
"""
from __future__ import annotations

import json
import logging
import re
import shlex
import urllib.error
import urllib.request

from dev_files.docker_exec import exec_in_sandbox

logger = logging.getLogger("agents.tools.github_push_ops")

# Same exec identity used throughout the sandbox tooling (tools/sandbox_ops.py,
# coordination/workspace_ops.py) — keeps everything dev-owned, not root-owned.
_SANDBOX_USER = "dev"


class GithubPushError(RuntimeError):
    """Raised when the push or PR-creation step fails."""


def _sh(cmd: str, timeout: int, input_bytes: bytes | None = None) -> tuple[int, str, str]:
    if input_bytes is not None:
        return exec_in_sandbox("sh", "-c", cmd, input_bytes=input_bytes, timeout=timeout, user=_SANDBOX_USER)
    return exec_in_sandbox("sh", "-c", cmd, timeout=timeout, user=_SANDBOX_USER)


def push_and_open_pr(
    *,
    coordination_id: str,
    bundle_data: bytes,
    local_branch: str,
    git_url: str,
    remote_branch: str,
    base_branch: str,
    pr_title: str,
    pr_body: str,
    token: str,
) -> dict:
    """
    Reconstruct `local_branch` from `bundle_data` in a disposable directory
    inside dev_sandbox, push it to `git_url` as `remote_branch`, and open a
    PR against `base_branch`.

    Returns {"pr_number": int, "pr_url": str}.
    Raises GithubPushError with a human-readable message on any failure.
    """
    if not bundle_data:
        raise GithubPushError("no bundle available for this task — nothing to push")
    if not local_branch or not remote_branch or not base_branch:
        raise GithubPushError("missing branch information for this task")

    work_dir = f"/tmp/push-{coordination_id}"
    bundle_path = f"{work_dir}/task.bundle"
    clone_dir = f"{work_dir}/repo"
    q_work = shlex.quote(work_dir)
    q_bundle = shlex.quote(bundle_path)
    q_clone = shlex.quote(clone_dir)
    q_branch = shlex.quote(local_branch)

    try:
        rc, out, err = _sh(f"rm -rf {q_work} && mkdir -p {q_work}", timeout=15)
        if rc != 0:
            raise GithubPushError(f"failed to prep push workdir: {(err or out).strip()[:500]}")

        rc, out, err = _sh(f"cat > {q_bundle}", timeout=30, input_bytes=bundle_data)
        if rc != 0:
            raise GithubPushError(f"failed to write bundle into sandbox: {(err or out).strip()[:500]}")

        rc, out, err = _sh(f"git clone --quiet {q_bundle} {q_clone} 2>&1", timeout=60)
        if rc != 0:
            raise GithubPushError(f"failed to reconstruct branch from bundle: {(err or out).strip()[:500]}")

        rc, out, err = _sh(f"cd {q_clone} && git checkout {q_branch} 2>&1", timeout=30)
        if rc != 0:
            raise GithubPushError(f"bundle did not contain branch {local_branch!r}: {(err or out).strip()[:500]}")

        # Ephemeral token-authenticated remote URL — passed inline on this one
        # push command only, never written to the clone's git config. The
        # whole clone is deleted in the `finally` block below regardless of
        # outcome, so nothing outlives this function call.
        push_url = git_url.replace("https://", f"https://x-access-token:{token}@", 1)
        q_push_url = shlex.quote(push_url)
        q_refspec = shlex.quote(f"{local_branch}:{remote_branch}")
        rc, out, err = _sh(f"cd {q_clone} && git push {q_push_url} {q_refspec} 2>&1", timeout=120)
        if rc != 0:
            safe_err = (err or out).replace(token, "***").strip()[:500]
            raise GithubPushError(f"git push failed: {safe_err}")
    finally:
        _sh(f"rm -rf {q_work}", timeout=15)  # best-effort cleanup regardless of outcome

    owner_repo = _parse_owner_repo(git_url)
    return _create_pull_request(owner_repo, remote_branch, base_branch, pr_title, pr_body, token)


def _parse_owner_repo(git_url: str) -> str:
    """'https://github.com/owner/repo.git' -> 'owner/repo'."""
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?/?$", git_url)
    if not m:
        raise GithubPushError(f"could not parse owner/repo from git_url: {git_url!r}")
    return f"{m.group(1)}/{m.group(2)}"


def _create_pull_request(owner_repo: str, head: str, base: str, title: str, body: str, token: str) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner_repo}/pulls",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        data=json.dumps({"title": title, "body": body, "head": head, "base": base}).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise GithubPushError(f"GitHub PR creation failed ({e.code}): {detail}")
    except Exception as e:
        raise GithubPushError(f"GitHub PR creation failed: {e}")
    return {"pr_number": data.get("number"), "pr_url": data.get("html_url")}
