"""
GitHub OAuth Token Storage — Phase 1C
Handles per-user GitHub OAuth token CRUD with Fernet encryption at rest.

Schema (auto-created on first use):
  swarm.github_oauth_tokens
    user_id        TEXT PRIMARY KEY   -- Authentik UID
    github_username TEXT NOT NULL
    access_token   BYTEA NOT NULL     -- Fernet-encrypted
    scopes         TEXT
    created_at     TIMESTAMPTZ DEFAULT NOW()
    updated_at     TIMESTAMPTZ DEFAULT NOW()
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("github_oauth")

# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------

def _get_fernet():
    """Return a Fernet instance using TOKEN_ENCRYPTION_KEY from env."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise RuntimeError(
            "The 'cryptography' package is required. Install: pip install cryptography"
        )
    key = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        # Generate a stable dev key derived from a constant — insecure but non-crashing
        import base64, hashlib
        raw = hashlib.sha256(b"dev-github-oauth-key-not-for-prod").digest()
        key = base64.urlsafe_b64encode(raw).decode()
        logger.warning("TOKEN_ENCRYPTION_KEY not set — using insecure dev key")
    return Fernet(key.encode() if isinstance(key, str) else key)


def _encrypt(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode())


def _decrypt(ciphertext: bytes) -> str:
    return _get_fernet().decrypt(ciphertext).decode()


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS swarm.github_oauth_tokens (
    user_id         TEXT PRIMARY KEY,
    github_username TEXT NOT NULL,
    access_token    BYTEA NOT NULL,
    scopes          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def _get_conn():
    import psycopg2
    from config import TEMPLATE_DB_URL
    conn = psycopg2.connect(TEMPLATE_DB_URL)
    # Ensure table exists
    cur = conn.cursor()
    cur.execute(_DDL)
    conn.commit()
    cur.close()
    return conn


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class GitHubToken:
    user_id: str
    github_username: str
    scopes: str
    created_at: datetime
    updated_at: datetime
    # Access token is never exposed directly — use get_plaintext_token()
    _encrypted: bytes = b""

    def get_plaintext_token(self) -> str:
        return _decrypt(self._encrypted)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def upsert_token(user_id: str, github_username: str, access_token: str, scopes: str = "") -> None:
    """Insert or replace a GitHub token for the given Authentik UID."""
    encrypted = _encrypt(access_token)
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO swarm.github_oauth_tokens
                (user_id, github_username, access_token, scopes, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                github_username = EXCLUDED.github_username,
                access_token    = EXCLUDED.access_token,
                scopes          = EXCLUDED.scopes,
                updated_at      = NOW()
            """,
            (user_id, github_username, encrypted, scopes),
        )
        conn.commit()
        cur.close()
        logger.info(f"github_oauth: token upserted for user_id={user_id} username={github_username}")
    except Exception as e:
        conn.rollback()
        logger.error(f"github_oauth: upsert failed for user_id={user_id}: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def get_token(user_id: str) -> Optional[GitHubToken]:
    """Retrieve the stored token record for a user, or None if not connected."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, github_username, access_token, scopes, created_at, updated_at "
            "FROM swarm.github_oauth_tokens WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        return GitHubToken(
            user_id=row[0],
            github_username=row[1],
            scopes=row[3] or "",
            created_at=row[4],
            updated_at=row[5],
            _encrypted=bytes(row[2]),
        )
    except Exception as e:
        logger.error(f"github_oauth: get_token failed for user_id={user_id}: {e}", exc_info=True)
        return None


def delete_token(user_id: str) -> bool:
    """Remove the stored token for a user. Returns True if a row was deleted."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM swarm.github_oauth_tokens WHERE user_id = %s", (user_id,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"github_oauth: token deleted for user_id={user_id} (rows={deleted})")
        return deleted > 0
    except Exception as e:
        logger.error(f"github_oauth: delete failed for user_id={user_id}: {e}", exc_info=True)
        return False
