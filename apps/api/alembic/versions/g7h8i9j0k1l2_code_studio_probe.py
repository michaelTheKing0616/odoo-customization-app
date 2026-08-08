"""Add code_studio_probe_json on odoo_connections

Revision ID: g7h8i9j0k1l2
Revises: f2a3b4c5d6e7
Create Date: 2026-08-08 15:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("odoo_connections")}
    if "code_studio_probe_json" not in cols:
        op.add_column(
            "odoo_connections",
            sa.Column("code_studio_probe_json", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("odoo_connections", "code_studio_probe_json")
