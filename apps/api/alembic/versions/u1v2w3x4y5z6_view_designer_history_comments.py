"""View Designer history versions and pinned comments (Builders stage 2a).

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-10-15 14:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, Sequence[str], None] = "t0u1v2w3x4y5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("view_layer_versions"):
        op.create_table(
            "view_layer_versions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("connection_id", sa.String(length=36), nullable=False),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("view_type", sa.String(length=16), nullable=False),
            sa.Column("layer_name", sa.String(length=255), nullable=False),
            sa.Column("layer_view_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(length=16), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=True),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("layer_arch", sa.Text(), nullable=True),
            sa.Column("layer_active", sa.Boolean(), nullable=False),
            sa.Column("combined_arch", sa.Text(), nullable=True),
            sa.Column("odoo_major", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_view_layer_versions_connection_id", "view_layer_versions", ["connection_id"])
        op.create_index("ix_view_layer_versions_layer_name", "view_layer_versions", ["layer_name"])
        op.create_index("ix_view_layer_versions_created_at", "view_layer_versions", ["created_at"])
    if not table_exists("view_comments"):
        op.create_table(
            "view_comments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("connection_id", sa.String(length=36), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("view_type", sa.String(length=16), nullable=False),
            sa.Column("node_id", sa.String(length=255), nullable=False),
            sa.Column("parent_id", sa.String(length=36), nullable=True),
            sa.Column("author", sa.String(length=120), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("resolved", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_view_comments_connection_id", "view_comments", ["connection_id"])
        op.create_index("ix_view_comments_parent_id", "view_comments", ["parent_id"])


def downgrade() -> None:
    if table_exists("view_comments"):
        op.drop_table("view_comments")
    if table_exists("view_layer_versions"):
        op.drop_table("view_layer_versions")
