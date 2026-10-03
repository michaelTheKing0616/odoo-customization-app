"""Hash-chained product audit entries (tamper-evident).

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-10-02 20:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "n4o5p6q7r8s9"
down_revision: Union[str, Sequence[str], None] = "m3n4o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("audit_chain_entries"):
        return
    op.create_table(
        "audit_chain_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_chain_entries_entry_hash",
        "audit_chain_entries",
        ["entry_hash"],
        unique=True,
    )


def downgrade() -> None:
    if not table_exists("audit_chain_entries"):
        return
    op.drop_index("ix_audit_chain_entries_entry_hash", table_name="audit_chain_entries")
    op.drop_table("audit_chain_entries")
