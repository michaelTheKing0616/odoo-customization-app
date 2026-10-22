"""connection group label (agency grouping)

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "x4y5z6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("odoo_connections", sa.Column("group_label", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("odoo_connections", "group_label")
