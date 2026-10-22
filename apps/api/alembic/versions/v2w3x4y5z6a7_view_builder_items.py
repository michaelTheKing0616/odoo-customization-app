"""View Designer stage 2b: reusable sections and upgrade-guard baselines.

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-10-15 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "v2w3x4y5z6a7"
down_revision: Union[str, Sequence[str], None] = "u1v2w3x4y5z6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("view_builder_items"):
        op.create_table(
            "view_builder_items",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("connection_id", sa.String(length=36), nullable=False),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_view_builder_items_connection_id", "view_builder_items", ["connection_id"])
        op.create_index("ix_view_builder_items_kind", "view_builder_items", ["kind"])


def downgrade() -> None:
    if table_exists("view_builder_items"):
        op.drop_index("ix_view_builder_items_kind", table_name="view_builder_items")
        op.drop_index("ix_view_builder_items_connection_id", table_name="view_builder_items")
        op.drop_table("view_builder_items")
