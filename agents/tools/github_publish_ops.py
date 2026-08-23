"""
tools/github_publish_ops.py — "Publish to GitHub" for a blank (local, git-
inited) dev project: create the remote repo, push the live working tree.

Sibling to tools/github_push_ops.py, not an extension of it — that module
pushes a *reconstructed bundle of a finished task's branch* inside a
disposable ephemeral-container clone. This one pushes the *live* working tree
that already sits in the shared dev_sandbox at the project's own persisted
path (dev_projects/store.py's `path` column, provisioned + git-inited by
dev_files/docker_exec.provision_project_dir). Same auth pattern
(token embedded inline in the push URL, never written to git config) and same
"never imported by tool_defs.py / never in TOOL_DISPATCH" unreachable-from-LLM
posture — this module's only caller is main.py's publish route handler, a
human HTTP request that has already passed owner-scoped auth and the
project_has_content() gate.

Explicit container_name=SANDBOX_CONTAINER on every exec_in_sandbox call here
(not exec_in_project, which resolves via sandbox_identity's thread-local) —
this always targets the ONE shared dev_sandbox regardless of whatever a
request-handling thread's thread-local sandbox_identity state happens to be.
"""
from __future__ import annotations

import json
import logging
import shlex
import urllib.error
import urllib.request

from dev_files.docker_exec import exec_in_sandbox, WORKSPACE_ROOT, SANDBOX_CONTAINER

logger = logging.getLogger("agents.tools.github_publish_ops")

_SANDBOX_USER = "root"  # matches provision_project_dir — project files are root-owned in dev_sandbox


class GithubPublishError(RuntimeError):
    """Raised when repo creation or the push step fails. Message is safe to show the user."""


def create_github_repo(token: str, name: str, private: bool) -> dict:
    """
    POST https://api.github.com/user/repos — create a new (empty) repo owned
    by the token's user.

    Returns {"html_url", "clone_url", "full_name"}.
    Raises GithubPublishError — 422 (name already exists / invalid) surfaces
    with GitHub's own message so the user can pick a different name.
    """
    req = urllib.request.Request(
        "https://api.github.com/user/repos",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        data=json.dumps({"name": name, "private": private}).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise GithubPublishError(f"GitHub repo creation failed ({e.code}): {detail}")
    except Exception as e:
        raise GithubPublishError(f"GitHub repo creation failed: {e}")

    clone_url = data.get("clone_url")
    html_url = data.get("html_url")
    full_name = data.get("full_name")
    if not clone_url or not html_url:
        raise GithubPublishError("GitHub API returned an unexpected response creating the repo")
    return {"html_url": html_url, "clone_url": clone_url, "full_name": full_name}


def push_project_to_remote(uid: str, project_id: str, remote_url: str, branch: str, token: str) -> None:
    """
    Push the project's current /workspace/<uid>/<project_id> working tree (in
    the shared dev_sandbox) to `remote_url` as `branch`.

    Auth: the token is embedded ONLY in the one-off URL passed directly to
    `git push` — never `git remote add`'d with credentials in it, since unlike
    github_push_ops.py's disposable ephemeral clone, this directory is
    long-lived and its .git/config would keep the token on disk indefinitely.
    A plain (no-credential) "origin" remote is added afterward instead, for
    any future git operation against this project.

    Raises GithubPublishError on failure.
    """
    project_dir = f"{WORKSPACE_ROOT}/{uid}/{project_id}"
    q_dir = shlex.quote(project_dir)
    q_branch = shlex.quote(branch)

    push_url = remote_url.replace("https://", f"https://x-access-token:{token}@", 1)
    q_push_url = shlex.quote(push_url)

    rc, out, err = exec_in_sandbox(
        "sh", "-c", f"cd {q_dir} && git push {q_push_url} {q_branch}:{q_branch} 2>&1",
        timeout=120, user=_SANDBOX_USER, container_name=SANDBOX_CONTAINER,
    )
    if rc != 0:
        safe_err = (err or out).replace(token, "***").strip()[:500]
        raise GithubPublishError(f"git push failed: {safe_err}")

    q_remote_url = shlex.quote(remote_url)
    rc, out, err = exec_in_sandbox(
        "sh", "-c",
        f"cd {q_dir} && (git remote remove origin 2>/dev/null; git remote add origin {q_remote_url})",
        timeout=15, user=_SANDBOX_USER, container_name=SANDBOX_CONTAINER,
    )
    if rc != 0:
        # Non-fatal — the push already succeeded, this is just local remote
        # bookkeeping for future convenience. Log it, don't fail the publish.
        logger.warning(
            "Push succeeded but failed to set origin remote for %s: %s",
            project_dir, (err or out).strip(),
        )
