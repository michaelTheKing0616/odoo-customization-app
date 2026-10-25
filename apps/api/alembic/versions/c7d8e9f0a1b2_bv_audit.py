"""NF BV-AUDIT: verify_audit and verify_walk_approvals

Revision ID: c7d8e9f0a1b2
Revises: 4b7e9c1d2a3f
Create Date: 2026-10-24 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: str | Sequence[str] | None = "4b7e9c1d2a3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verify_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.String(36), nullable=True),
        sa.Column("db_name", sa.String(80), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verify_audit_connection_id", "verify_audit", ["connection_id"])
    op.create_table(
        "verify_walk_approvals",
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("odoo_connections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "walkthrough_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("owner_id", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("verify_walk_approvals")
    op.drop_index("ix_verify_audit_connection_id", table_name="verify_audit")
    op.drop_table("verify_audit")
