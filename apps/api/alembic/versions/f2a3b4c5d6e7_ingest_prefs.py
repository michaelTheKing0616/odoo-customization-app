"""Add ingest_prefs_json on odoo_connections

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-06 23:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "odoo_connections",
        sa.Column("ingest_prefs_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("odoo_connections", "ingest_prefs_json")
