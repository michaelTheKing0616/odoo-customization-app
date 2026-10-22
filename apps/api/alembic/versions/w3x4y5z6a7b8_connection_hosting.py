"""connection hosting choice (online | odoo_sh | self_hosted)

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w3x4y5z6a7b8"
down_revision: Union[str, Sequence[str], None] = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("odoo_connections", sa.Column("hosting", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("odoo_connections", "hosting")
