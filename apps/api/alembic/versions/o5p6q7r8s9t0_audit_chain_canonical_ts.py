"""Audit chain canonical UTC timestamp for hash verification.

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-10-02 21:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import column_exists

revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, Sequence[str], None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not column_exists("audit_chain_entries", "canonical_ts"):
        op.add_column(
            "audit_chain_entries",
            sa.Column("canonical_ts", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    if column_exists("audit_chain_entries", "canonical_ts"):
        op.drop_column("audit_chain_entries", "canonical_ts")
