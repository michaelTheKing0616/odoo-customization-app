"""user display_name ('What should we call you?')

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "y5z6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "display_name")
