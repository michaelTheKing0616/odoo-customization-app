"""Persisted hash-bound plan cards.

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-10-02 21:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, Sequence[str], None] = "p6q7r8s9t0u1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("plan_cards"):
        return
    op.create_table(
        "plan_cards",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("connection_id", sa.String(length=36), nullable=False),
        sa.Column("requester_id", sa.String(length=36), nullable=False),
        sa.Column("plan_hash", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("card_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plan_cards_connection_id", "plan_cards", ["connection_id"])
    op.create_index("ix_plan_cards_plan_hash", "plan_cards", ["plan_hash"])


def downgrade() -> None:
    if not table_exists("plan_cards"):
        return
    op.drop_index("ix_plan_cards_plan_hash", table_name="plan_cards")
    op.drop_index("ix_plan_cards_connection_id", table_name="plan_cards")
    op.drop_table("plan_cards")
