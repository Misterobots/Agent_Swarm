"""
GitHub Push Token Storage — fine-grained PAT for repo-write access (Phase C).

Structurally separate from github_oauth.py's swarm.github_oauth_tokens table:
that one stores a read:user OAuth token consumed as an LLM-provider identity
credential. This module stores a human-pasted fine-grained Personal Access
Token scoped (on GitHub's side) for repo write access, used only to push a
branch and open a pull request from a completed Task — never touched or
ALTERed on github_oauth.py's table, never imported by
agents/dev_harness/tool_defs.py, and never registered in TOOL_DISPATCH. Its
only callers are FastAPI route handlers in main.py, i.e. a human HTTP request
that has already passed owner-scoped auth (see the "Hard safety boundary" in
the Codex-task-composer plan: the LLM agent itself must never gain
push/clone/remote-capable git access).

Schema (auto-created on first use):
  swarm.github_push_tokens
    user_id            TEXT PRIMARY KEY   -- Authentik UID / username (owner_id)
    github_username    TEXT NOT NULL
    access_token       BYTEA NOT NULL     -- Fernet-encrypted
    created_at         TIMESTAMPTZ DEFAULT NOW()
    updated_at         TIMESTAMPTZ DEFAULT NOW()
    last_validated_at  TIMESTAMPTZ

Encryption reuses github_oauth.py's Fernet helpers (imported, not duplicated)
so TOKEN_ENCRYPTION_KEY handling — including its "insecure dev key" fallback
warning — lives in exactly one place.

Mirrors swarm_run_store.py's style: psycopg2 + _db() context manager,
idempotent init_table() (CREATE-only, never ALTER), fire-and-forget writes
that swallow+log rather than raise, owner-scoped reads that return safe
defaults on error.
"""

import logging
from contextlib import contextmanager

import psycopg2

from config import TEMPLATE_DB_URL
from github_oauth import _encrypt, _decrypt

logger = logging.getLogger("agents.github_push_tokens")


# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

@contextmanager
def _db():
    conn = psycopg2.connect(TEMPLATE_DB_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS swarm.github_push_tokens (
    user_id           TEXT PRIMARY KEY,
    github_username   TEXT NOT NULL,
    access_token      BYTEA NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_validated_at TIMESTAMPTZ
);
"""


def init_table() -> None:
    """Create swarm.github_push_tokens if absent. Idempotent; safe on startup.

    CREATE-only (never ALTER) — same posture as swarm_run_store — and never
    touches swarm.github_oauth_tokens.
    """
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
        logger.info("[GitHubPushTokens] Table swarm.github_push_tokens ready.")
    except Exception as e:
        logger.warning(f"[GitHubPushTokens] init_table failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Writes — fire-and-forget (never raise into the route handler)
# ---------------------------------------------------------------------------

def upsert_token(user_id: str, github_username: str, token: str) -> None:
    """Insert or replace the push-scoped PAT for an Authentik UID/username.

    Callers must live-validate the token (GET https://api.github.com/user)
    BEFORE calling this — it stores whatever it's given without re-checking.
    last_validated_at is stamped to NOW() since validation is assumed to have
    just succeeded. Fire-and-forget: swallows errors and logs, matching this
    codebase's store-module convention (swarm_run_store.py). Callers that
    need write confirmation should follow up with get_status().
    """
    if not user_id or not github_username or not token:
        return
    try:
        encrypted = _encrypt(token)
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO swarm.github_push_tokens
                        (user_id, github_username, access_token,
                         created_at, updated_at, last_validated_at)
                    VALUES (%s, %s, %s, NOW(), NOW(), NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        github_username   = EXCLUDED.github_username,
                        access_token      = EXCLUDED.access_token,
                        updated_at        = NOW(),
                        last_validated_at = NOW()
                    """,
                    (user_id, github_username, encrypted),
                )
        logger.info(f"[GitHubPushTokens] token upserted for user_id={user_id} username={github_username}")
    except Exception as e:
        logger.warning(f"[GitHubPushTokens] upsert_token failed (non-fatal) for user_id={user_id}: {e}")


def delete_token(user_id: str) -> bool:
    """Remove the stored push token for a user. Returns True if a row was deleted."""
    if not user_id:
        return False
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM swarm.github_push_tokens WHERE user_id = %s", (user_id,))
                deleted = cur.rowcount
        logger.info(f"[GitHubPushTokens] token deleted for user_id={user_id} (rows={deleted})")
        return deleted > 0
    except Exception as e:
        logger.warning(f"[GitHubPushTokens] delete_token failed for user_id={user_id}: {e}")
        return False


# ---------------------------------------------------------------------------
# Reads — owner-scoped; return safe defaults on error
# ---------------------------------------------------------------------------

def get_token(user_id: str) -> str | None:
    """Decrypt and return the stored push-scoped PAT for a user, or None.

    Never call this from an LLM-reachable code path — plaintext repo-write
    credential. Only push_and_open_pr-style backend-only modules (Phase D)
    and this module's own tests should ever call it.
    """
    if not user_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT access_token FROM swarm.github_push_tokens WHERE user_id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return _decrypt(bytes(row[0]))
    except Exception as e:
        logger.warning(f"[GitHubPushTokens] get_token failed for user_id={user_id}: {e}")
        return None


def get_status(user_id: str) -> dict | None:
    """Owner-scoped connection status. Never returns the token itself."""
    if not user_id:
        return None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT github_username FROM swarm.github_push_tokens WHERE user_id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {"github_username": row[0], "connected": True}
    except Exception as e:
        logger.warning(f"[GitHubPushTokens] get_status failed for user_id={user_id}: {e}")
        return None
