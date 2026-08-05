"""TRUST-1: connection write_mode (observer default for new rows)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-03 22:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import column_exists

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not column_exists("odoo_connections", "write_mode"):
        op.add_column(
            "odoo_connections",
            sa.Column("write_mode", sa.String(length=20), nullable=False, server_default="standard"),
        )
        op.alter_column("odoo_connections", "write_mode", server_default="observer")


def downgrade() -> None:
    op.drop_column("odoo_connections", "write_mode")
