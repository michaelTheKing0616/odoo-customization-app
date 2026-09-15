"""Live Demo Co-Pilot ops fields (leave/purge status)

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-09-15 11:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import column_exists, table_exists

revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, Sequence[str], None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("live_demo_copilot_sessions"):
        return
    if not column_exists("live_demo_copilot_sessions", "leave_purge_status"):
        op.add_column(
            "live_demo_copilot_sessions",
            sa.Column("leave_purge_status", sa.String(length=24), nullable=False, server_default="idle"),
        )
    if not column_exists("live_demo_copilot_sessions", "last_ops_error"):
        op.add_column(
            "live_demo_copilot_sessions",
            sa.Column("last_ops_error", sa.Text(), nullable=True),
        )
    if not column_exists("live_demo_copilot_sessions", "leave_purge_job_id"):
        op.add_column(
            "live_demo_copilot_sessions",
            sa.Column("leave_purge_job_id", sa.String(length=36), nullable=True),
        )


def downgrade() -> None:
    if not table_exists("live_demo_copilot_sessions"):
        return
    for col in ("leave_purge_job_id", "last_ops_error", "leave_purge_status"):
        if column_exists("live_demo_copilot_sessions", col):
            op.drop_column("live_demo_copilot_sessions", col)
