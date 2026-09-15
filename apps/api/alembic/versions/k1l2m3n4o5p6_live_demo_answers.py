"""Live Demo Co-Pilot Stage 1/2 answers

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-09-15 11:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, Sequence[str], None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("live_demo_answers"):
        return
    op.create_table(
        "live_demo_answers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("transcript_line_id", sa.String(length=36), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("speaker_name", sa.String(length=200), nullable=True),
        sa.Column("stage1_reason", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("stage1_score", sa.String(length=16), nullable=False, server_default="0"),
        sa.Column("bullets_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default="low"),
        sa.Column("confidence_flag", sa.Text(), nullable=True),
        sa.Column("grounded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("declined", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("citations_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("answer_markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column("model_used", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="ready"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["live_demo_copilot_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_live_demo_answers_session_id", "live_demo_answers", ["session_id"])
    op.create_index("ix_live_demo_answers_workspace_id", "live_demo_answers", ["workspace_id"])
    op.create_index("ix_live_demo_answers_transcript_line_id", "live_demo_answers", ["transcript_line_id"])


def downgrade() -> None:
    if not table_exists("live_demo_answers"):
        return
    op.drop_index("ix_live_demo_answers_transcript_line_id", table_name="live_demo_answers")
    op.drop_index("ix_live_demo_answers_workspace_id", table_name="live_demo_answers")
    op.drop_index("ix_live_demo_answers_session_id", table_name="live_demo_answers")
    op.drop_table("live_demo_answers")
