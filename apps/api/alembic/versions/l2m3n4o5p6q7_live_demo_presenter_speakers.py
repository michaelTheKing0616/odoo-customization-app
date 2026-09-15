"""Live Demo Co-Pilot presenter speaker ignore-list

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-09-15 12:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, Sequence[str], None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("live_demo_copilot_sessions"):
        return
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("live_demo_copilot_sessions")}
    if "presenter_speakers_json" in cols:
        return
    op.add_column(
        "live_demo_copilot_sessions",
        sa.Column("presenter_speakers_json", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    if not table_exists("live_demo_copilot_sessions"):
        return
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("live_demo_copilot_sessions")}
    if "presenter_speakers_json" not in cols:
        return
    op.drop_column("live_demo_copilot_sessions", "presenter_speakers_json")
