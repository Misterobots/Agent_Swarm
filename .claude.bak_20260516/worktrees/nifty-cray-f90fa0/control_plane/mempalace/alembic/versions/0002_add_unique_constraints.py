"""add unique constraints for snapshots and team_memories

Revision ID: 0002_add_unique_constraints
Revises: 0001_baseline
Create Date: 2026-05-08

Closes the race conditions in save_snapshot and store_team_memory by
enforcing uniqueness at the database level. Includes a defensive dedupe
step in case the pre-fix code already produced duplicate rows on the
live DB — keeps the row with the highest id per group.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_add_unique_constraints"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dedupe agent_snapshots — keep highest id per (agent_id, owner_id, version).
    # IS NOT DISTINCT FROM handles NULL owner_id correctly.
    op.execute("""
        DELETE FROM mempalace.agent_snapshots a
        USING mempalace.agent_snapshots b
        WHERE a.agent_id IS NOT DISTINCT FROM b.agent_id
          AND a.owner_id IS NOT DISTINCT FROM b.owner_id
          AND a.version = b.version
          AND a.id < b.id
    """)
    op.create_unique_constraint(
        "uq_snap_agent_owner_version",
        "agent_snapshots",
        ["agent_id", "owner_id", "version"],
        schema="mempalace",
    )

    # Dedupe team_memories — keep highest id per (team_id, key).
    op.execute("""
        DELETE FROM mempalace.team_memories a
        USING mempalace.team_memories b
        WHERE a.team_id = b.team_id
          AND a.key = b.key
          AND a.id < b.id
    """)
    op.create_unique_constraint(
        "uq_team_mem_team_key",
        "team_memories",
        ["team_id", "key"],
        schema="mempalace",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_team_mem_team_key", "team_memories", schema="mempalace", type_="unique"
    )
    op.drop_constraint(
        "uq_snap_agent_owner_version",
        "agent_snapshots",
        schema="mempalace",
        type_="unique",
    )
