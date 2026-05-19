"""baseline schema — captures the state created by Base.metadata.create_all

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-08

For databases that already have these tables (i.e. anything created by the
pre-Alembic init_db), run `alembic stamp 0001_baseline` once to mark this
revision as applied without re-running it. Fresh databases will execute it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.String(50), nullable=False),
        sa.Column("domain", sa.String(100)),
        sa.Column("agent_id", sa.String(100)),
        sa.Column("team_id", sa.String(100)),
        sa.Column("owner_id", sa.String(100)),
        sa.Column("embedding", Vector(768)),
        sa.Column("metadata", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("access_count", sa.Integer(), server_default="0"),
        sa.Column("relevance_decay", sa.Float(), server_default="1.0"),
        schema="mempalace",
    )
    op.create_index(
        "ix_mem_embedding",
        "memories",
        ["embedding"],
        schema="mempalace",
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_mem_owner_type", "memories", ["owner_id", "memory_type"], schema="mempalace"
    )
    op.create_index("ix_mem_team", "memories", ["team_id"], schema="mempalace")

    op.create_table(
        "agent_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("owner_id", sa.String(100)),
        sa.Column("snapshot_data", JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="mempalace",
    )
    op.create_index(
        "ix_snap_agent_owner", "agent_snapshots", ["agent_id", "owner_id"], schema="mempalace"
    )

    op.create_table(
        "team_memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", sa.String(100), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768)),
        sa.Column("author_agent", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="mempalace",
    )
    op.create_index("ix_team_mem_team", "team_memories", ["team_id"], schema="mempalace")

    op.create_table(
        "memory_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("memory_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("previous_content", sa.Text()),
        sa.Column("new_content", sa.Text()),
        sa.Column("changed_fields", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="mempalace",
    )
    op.create_index(
        "ix_audit_memory_id", "memory_audit_log", ["memory_id"], schema="mempalace"
    )

    op.create_table(
        "extraction_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.String(100), nullable=False),
        sa.Column("agent_id", sa.String(100)),
        sa.Column("memories_stored", sa.Integer(), server_default="0"),
        sa.Column("conversation_length", sa.Integer(), server_default="0"),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="mempalace",
    )
    op.create_index("ix_extract_log_owner", "extraction_log", ["owner_id"], schema="mempalace")
    op.create_index(
        "ix_extract_log_attempted_at", "extraction_log", ["attempted_at"], schema="mempalace"
    )


def downgrade() -> None:
    op.drop_table("extraction_log", schema="mempalace")
    op.drop_table("memory_audit_log", schema="mempalace")
    op.drop_table("team_memories", schema="mempalace")
    op.drop_table("agent_snapshots", schema="mempalace")
    op.drop_table("memories", schema="mempalace")
