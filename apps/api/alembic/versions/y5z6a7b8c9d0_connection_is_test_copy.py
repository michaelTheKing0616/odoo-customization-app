"""connection is_test_copy flag (None = never set)

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y5z6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "x4y5z6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("odoo_connections", sa.Column("is_test_copy", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("odoo_connections", "is_test_copy")
