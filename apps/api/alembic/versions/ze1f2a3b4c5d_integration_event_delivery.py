"""integration_events delivery columns (ordering, retry time, last error, delivered)

Revision ID: ze1f2a3b4c5d
Revises: z6a7b8c9d0e1
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ze1f2a3b4c5d"
down_revision: Union[str, Sequence[str], None] = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: app startup (db.py) may already have added the columns on a running database.
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("integration_events")}
    for name, typ in (("ordering_key", sa.String(255)), ("next_attempt_at", sa.DateTime(timezone=True)),
                      ("last_error", sa.Text()), ("delivered_at", sa.DateTime(timezone=True))):
        if name not in cols:
            op.add_column("integration_events", sa.Column(name, typ, nullable=True))
    if "ix_integration_events_ordering_key" not in {i["name"] for i in insp.get_indexes("integration_events")}:
        op.create_index("ix_integration_events_ordering_key", "integration_events", ["ordering_key"])


def downgrade() -> None:
    op.drop_index("ix_integration_events_ordering_key", "integration_events")
    for c in ("delivered_at", "last_error", "next_attempt_at", "ordering_key"):
        op.drop_column("integration_events", c)
