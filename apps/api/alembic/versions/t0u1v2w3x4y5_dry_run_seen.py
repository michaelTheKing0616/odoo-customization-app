"""Shared structural dry-run ledger (TTL 1 hour).

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-10-04 05:20:00.000000

Declares ``dry_run_seen`` so two API workers can agree on a dry-run hash.
This revision is not applied by the test suite. Tests create the table
through SQLAlchemy on a local engine.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "t0u1v2w3x4y5"
down_revision: Union[str, Sequence[str], None] = "s9t0u1v2w3x4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("dry_run_seen"):
        return
    op.create_table(
        "dry_run_seen",
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("digest"),
    )
    op.create_index("ix_dry_run_seen_expires_at", "dry_run_seen", ["expires_at"])


def downgrade() -> None:
    if not table_exists("dry_run_seen"):
        return
    op.drop_index("ix_dry_run_seen_expires_at", table_name="dry_run_seen")
    op.drop_table("dry_run_seen")
