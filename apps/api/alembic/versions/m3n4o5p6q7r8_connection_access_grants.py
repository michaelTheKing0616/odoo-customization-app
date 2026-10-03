"""Client approver grants — one connection, not a workspace role.

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-10-02 19:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, Sequence[str], None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("connection_access_grants"):
        return
    op.create_table(
        "connection_access_grants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("connection_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["odoo_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id", "user_id", name="uq_connection_grant_user"),
    )
    op.create_index("ix_connection_access_grants_workspace_id", "connection_access_grants", ["workspace_id"])
    op.create_index("ix_connection_access_grants_connection_id", "connection_access_grants", ["connection_id"])
    op.create_index("ix_connection_access_grants_user_id", "connection_access_grants", ["user_id"])


def downgrade() -> None:
    if not table_exists("connection_access_grants"):
        return
    op.drop_index("ix_connection_access_grants_user_id", table_name="connection_access_grants")
    op.drop_index("ix_connection_access_grants_connection_id", table_name="connection_access_grants")
    op.drop_index("ix_connection_access_grants_workspace_id", table_name="connection_access_grants")
    op.drop_table("connection_access_grants")
