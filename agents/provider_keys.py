"""
Per-User Provider API Key Storage — Connected Accounts

Allows each user to store their own API keys for external LLM providers
(Anthropic, Google/Gemini, etc.). Keys are Fernet-encrypted at rest.

GitHub tokens are handled separately by github_oauth.py (OAuth device flow).

Schema (auto-created on first use):
  swarm.provider_api_keys
    user_id      TEXT NOT NULL   -- Authentik UID
    provider     TEXT NOT NULL   -- 'anthropic' | 'google' | ...
    api_key      BYTEA NOT NULL  -- Fernet-encrypted
    label        TEXT             -- user-chosen display label
    created_at   TIMESTAMPTZ DEFAULT NOW()
    updated_at   TIMESTAMPTZ DEFAULT NOW()
    PRIMARY KEY (user_id, provider)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger("provider_keys")

# ---------------------------------------------------------------------------
# Supported providers (extend this as new providers are added)
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, dict] = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "models": [
            {"id": "claude-opus-4-20250514",      "label": "Claude Opus 4",   "context": 200_000},
            {"id": "claude-sonnet-4-6-20250514",   "label": "Claude Sonnet 4.6", "context": 200_000},
            {"id": "claude-haiku-3-5-20241022",    "label": "Claude Haiku 3.5",  "context": 200_000},
        ],
        "validate_url": "https://api.anthropic.com/v1/messages",
        "key_prefix": "sk-ant-",
    },
    "google": {
        "label": "Google (Gemini)",
        "models": [
            {"id": "gemini-3.1-pro-preview",    "label": "Gemini 3.1 Pro Preview",    "context": 1_048_576},
            {"id": "gemini-3-pro-preview",       "label": "Gemini 3 Pro Preview",       "context": 1_048_576},
            {"id": "gemini-3-flash-preview",     "label": "Gemini 3 Flash Preview",     "context": 1_048_576},
            {"id": "gemini-3.1-flash-lite",      "label": "Gemini 3.1 Flash Lite",      "context": 1_048_576},
            {"id": "gemini-2.5-pro",             "label": "Gemini 2.5 Pro",             "context": 1_048_576},
            {"id": "gemini-2.5-flash",           "label": "Gemini 2.5 Flash",           "context": 1_048_576},
            {"id": "gemini-2.5-flash-lite",      "label": "Gemini 2.5 Flash-Lite",      "context": 1_048_576},
            {"id": "gemini-2.0-flash",           "label": "Gemini 2.0 Flash",           "context": 1_048_576},
        ],
        "validate_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "key_prefix": "AI",
    },
    "nvidia": {
        "label": "NVIDIA NIM",
        "models": [
            {"id": "nvidia/llama-3.1-nemotron-70b-instruct",  "label": "Nemotron 70B",        "context": 131_072},
            {"id": "nvidia/llama-3.3-nemotron-super-49b-v1",  "label": "Nemotron Super 49B",  "context": 131_072},
            {"id": "nvidia/llama-3.1-nemotron-nano-8b-v1",    "label": "Nemotron Nano 8B",    "context": 131_072},
            {"id": "nvidia/mistral-nemo-12b-instruct",         "label": "Mistral NeMo 12B",    "context": 128_000},
            {"id": "nvidia/llama-3.2-nv-embedqa-1b-v2",       "label": "Llama 3.2 Embed 1B",  "context": 8_192},
            {"id": "nvidia/deepseek-r1",                       "label": "DeepSeek R1 (NIM)",   "context": 128_000},
        ],
        "validate_url": "https://integrate.api.nvidia.com/v1/models",
        "key_prefix": "nvapi-",
    },
}


# ---------------------------------------------------------------------------
# Encryption (reuses the same Fernet key as github_oauth)
# ---------------------------------------------------------------------------

def _get_fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise RuntimeError("The 'cryptography' package is required. Install: pip install cryptography")
    key = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    if not key:
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

_DDL_TABLE = """
CREATE TABLE IF NOT EXISTS swarm.provider_api_keys (
    user_id     TEXT NOT NULL,
    provider    TEXT NOT NULL,
    api_key     BYTEA NOT NULL,
    label       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# Remove duplicate (user_id, provider) rows, keeping the one with the highest
# ctid (most recently inserted). Must run before the unique index is created.
_DDL_DEDUP = """
DELETE FROM swarm.provider_api_keys a
USING swarm.provider_api_keys b
WHERE a.ctid < b.ctid
  AND a.user_id  = b.user_id
  AND a.provider = b.provider;
"""

# Migration: give key_id a default so INSERTs that omit it don't fail.
# gen_random_uuid() is available in pgvector/pg15 via the pgcrypto / uuid-ossp extension.
_DDL_KEY_ID_DEFAULT = """
DO $$
BEGIN
    ALTER TABLE swarm.provider_api_keys
        ALTER COLUMN key_id SET DEFAULT gen_random_uuid()::text;
EXCEPTION WHEN others THEN
    NULL;  -- column may already have a default; ignore
END $$;
"""

# Idempotent unique index — safe to run on tables created before the PRIMARY KEY
# clause was added and on freshly-created tables alike.
_DDL_UNIQUE = """
CREATE UNIQUE INDEX IF NOT EXISTS provider_api_keys_user_provider_idx
    ON swarm.provider_api_keys(user_id, provider);
"""


def _get_conn():
    import psycopg2
    from config import TEMPLATE_DB_URL
    conn = psycopg2.connect(TEMPLATE_DB_URL)
    cur = conn.cursor()
    cur.execute(_DDL_TABLE)
    cur.execute(_DDL_DEDUP)
    cur.execute(_DDL_KEY_ID_DEFAULT)
    cur.execute(_DDL_UNIQUE)
    conn.commit()
    cur.close()
    return conn


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class ProviderKey:
    user_id: str
    provider: str
    label: str
    created_at: datetime
    updated_at: datetime
    _encrypted: bytes = b""

    def get_api_key(self) -> str:
        return _decrypt(self._encrypted)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def upsert_key(user_id: str, provider: str, api_key: str, label: str = "") -> None:
    """Store or update an API key for a provider."""
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}. Supported: {list(PROVIDERS.keys())}")
    encrypted = _encrypt(api_key)
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO swarm.provider_api_keys
                (user_id, provider, api_key, label, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (user_id, provider) DO UPDATE SET
                api_key    = EXCLUDED.api_key,
                label      = EXCLUDED.label,
                updated_at = NOW()
            """,
            (user_id, provider, encrypted, label),
        )
        conn.commit()
        cur.close()
        logger.info(f"provider_keys: upserted {provider} key for user_id={user_id}")
    except Exception as e:
        conn.rollback()
        logger.error(f"provider_keys: upsert failed for user_id={user_id} provider={provider}: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def get_key(user_id: str, provider: str) -> Optional[ProviderKey]:
    """Retrieve the stored key for a user+provider, or None."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, provider, api_key, label, created_at, updated_at "
            "FROM swarm.provider_api_keys WHERE user_id = %s AND provider = %s",
            (user_id, provider),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        return ProviderKey(
            user_id=row[0],
            provider=row[1],
            label=row[3] or "",
            created_at=row[4],
            updated_at=row[5],
            _encrypted=bytes(row[2]),
        )
    except Exception as e:
        logger.error(f"provider_keys: get_key failed for user_id={user_id} provider={provider}: {e}", exc_info=True)
        return None


def list_connected(user_id: str) -> list[dict]:
    """Return a list of providers the user has connected (without exposing keys)."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT provider, label, created_at FROM swarm.provider_api_keys WHERE user_id = %s",
            (user_id,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {"provider": r[0], "label": r[1] or PROVIDERS.get(r[0], {}).get("label", r[0]), "connected_at": r[2].isoformat() if r[2] else None}
            for r in rows
        ]
    except Exception as e:
        logger.error(f"provider_keys: list_connected failed for user_id={user_id}: {e}", exc_info=True)
        return []


def delete_key(user_id: str, provider: str) -> bool:
    """Remove a stored key. Returns True if a row was deleted."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM swarm.provider_api_keys WHERE user_id = %s AND provider = %s",
            (user_id, provider),
        )
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"provider_keys: deleted {provider} for user_id={user_id} (rows={deleted})")
        return deleted > 0
    except Exception as e:
        logger.error(f"provider_keys: delete failed for user_id={user_id} provider={provider}: {e}", exc_info=True)
        return False


def get_user_anthropic_key(user_id: str) -> Optional[str]:
    """Convenience: return the user's Anthropic API key plaintext, or None."""
    record = get_key(user_id, "anthropic")
    return record.get_api_key() if record else None
