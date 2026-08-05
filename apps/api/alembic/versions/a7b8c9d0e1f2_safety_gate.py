"""TRUST-2: dry-run receipts + writes_paused kill switch

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-03 22:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import column_exists, table_exists

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not column_exists("odoo_connections", "writes_paused"):
        op.add_column(
            "odoo_connections",
            sa.Column("writes_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not column_exists("workspaces", "writes_paused"):
        op.add_column(
            "workspaces",
            sa.Column("writes_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not table_exists("dry_run_receipts"):
        op.create_table(
            "dry_run_receipts",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("connection_id", sa.String(length=36), nullable=False),
            sa.Column("operation", sa.String(length=200), nullable=False),
            sa.Column("params_hash", sa.String(length=64), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["connection_id"], ["odoo_connections.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
        op.create_index("ix_dry_run_receipts_connection_id", "dry_run_receipts", ["connection_id"])
        op.create_index("ix_dry_run_receipts_operation", "dry_run_receipts", ["operation"])
        op.create_index("ix_dry_run_receipts_token_hash", "dry_run_receipts", ["token_hash"])


def downgrade() -> None:
    if table_exists("dry_run_receipts"):
        op.drop_index("ix_dry_run_receipts_token_hash", table_name="dry_run_receipts")
        op.drop_index("ix_dry_run_receipts_operation", table_name="dry_run_receipts")
        op.drop_index("ix_dry_run_receipts_connection_id", table_name="dry_run_receipts")
        op.drop_table("dry_run_receipts")
    if column_exists("workspaces", "writes_paused"):
        op.drop_column("workspaces", "writes_paused")
    if column_exists("odoo_connections", "writes_paused"):
        op.drop_column("odoo_connections", "writes_paused")
