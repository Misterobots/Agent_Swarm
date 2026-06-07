"""Add entity graph — entities table, entity_relations table, entity_extracted flag.

Revision ID: 0003_entity_graph
Revises: 0002_add_unique_constraints
Create Date: 2026-06-06

Adds the structural layer for a proper entity-relationship knowledge graph
on top of the existing flat memory store:

  - memories.entity_extracted   bool flag so the extraction job is idempotent
  - mempalace.entities          named things found across memories
  - mempalace.entity_relations  typed edges between entities (uses, depends-on …)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_entity_graph"
down_revision: Union[str, None] = "0002_add_unique_constraints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Extraction-tracking flag on memories ───────────────────────────
    op.add_column(
        "memories",
        sa.Column("entity_extracted", sa.Boolean(), server_default="false", nullable=False),
        schema="mempalace",
    )
    # Composite index used by the extraction job's SELECT … WHERE NOT entity_extracted
    op.create_index(
        "ix_mem_entity_extracted",
        "memories",
        ["owner_id", "entity_extracted"],
        schema="mempalace",
    )

    # ── 2. entities table ─────────────────────────────────────────────────
    # Note: uniqueness is enforced on (owner_id, lower(label)) via a functional
    # unique index — not a table constraint — so ON CONFLICT clauses must use
    # Python-level dedup (SELECT-first) rather than the pg_insert upsert helper.
    op.execute("""
        CREATE TABLE mempalace.entities (
            id           UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
            label        VARCHAR(200) NOT NULL,
            entity_type  VARCHAR(50)  NOT NULL,
            description  TEXT,
            owner_id     VARCHAR(100),
            memory_count INTEGER NOT NULL DEFAULT 0,
            created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_entities_owner ON mempalace.entities (owner_id)")
    op.execute("""
        CREATE UNIQUE INDEX ix_entities_label_owner
            ON mempalace.entities (owner_id, lower(label))
    """)

    # ── 3. entity_relations table ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE mempalace.entity_relations (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id           UUID NOT NULL
                                    REFERENCES mempalace.entities (id) ON DELETE CASCADE,
            target_id           UUID NOT NULL
                                    REFERENCES mempalace.entities (id) ON DELETE CASCADE,
            relation_type       VARCHAR(100) NOT NULL,
            confidence          FLOAT  NOT NULL DEFAULT 1.0,
            evidence_memory_ids JSONB  NOT NULL DEFAULT '[]',
            owner_id            VARCHAR(100),
            created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            CONSTRAINT uq_entity_rel UNIQUE (source_id, target_id, relation_type)
        )
    """)
    op.execute("CREATE INDEX ix_entity_rel_source ON mempalace.entity_relations (source_id)")
    op.execute("CREATE INDEX ix_entity_rel_target ON mempalace.entity_relations (target_id)")
    op.execute("CREATE INDEX ix_entity_rel_owner  ON mempalace.entity_relations (owner_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mempalace.entity_relations")
    op.execute("DROP TABLE IF EXISTS mempalace.entities")
    op.drop_index("ix_mem_entity_extracted", table_name="memories", schema="mempalace")
    op.drop_column("memories", "entity_extracted", schema="mempalace")
