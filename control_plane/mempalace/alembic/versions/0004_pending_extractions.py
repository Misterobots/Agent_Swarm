"""Add pending_extractions — decouple queue-for-later from LLM extraction.

Revision ID: 0004_pending_extractions
Revises: 0003_entity_graph
Create Date: 2026-07-06

Callers previously POSTed raw conversation text straight to /v1/extract, which
synchronously ran a heavy 14B LLM extraction call. That caused severe GPU
contention against the shared Ollama instance used for real-time chat.

This migration adds mempalace.pending_extractions, a cheap holding table:
callers now queue conversation text instantly (no LLM/embedding calls), and a
separate batch job (twice-daily, off-peak) drains the queue through the
existing extract_memories()/embed_texts() pipeline.

  - mempalace.pending_extractions   queued conversations awaiting extraction
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_pending_extractions"
down_revision: Union[str, None] = "0003_entity_graph"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE mempalace.pending_extractions (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation   TEXT NOT NULL,
            owner_id       VARCHAR(100) NOT NULL,
            agent_id       VARCHAR(100),
            team_id        VARCHAR(100),
            source_device  VARCHAR(100),
            created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            processed_at   TIMESTAMP WITH TIME ZONE
        )
    """)
    # Queries constantly filter WHERE owner_id = X AND processed_at IS NULL —
    # both the queue-search fallback and the nightly batch job hit this.
    op.execute("""
        CREATE INDEX ix_pending_extractions_owner_processed
            ON mempalace.pending_extractions (owner_id, processed_at)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mempalace.pending_extractions")
