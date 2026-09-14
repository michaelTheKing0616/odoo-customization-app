"""Conversational refinement — ai_sessions table

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-09-01 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, Sequence[str], None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("ai_sessions"):
        return
    op.create_table(
        "ai_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("connection_id", sa.String(length=36), nullable=True),
        sa.Column("feature", sa.String(length=32), nullable=False, server_default="studio"),
        sa.Column("prompt_original", sa.Text(), nullable=False),
        sa.Column("prompt_resolved", sa.Text(), nullable=False),
        sa.Column("conversation_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("artifact_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("resolved_answers_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("pending_clarification_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="clarifying"),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("draft_cache_id", sa.String(length=36), nullable=True),
        sa.Column("provider_used", sa.String(length=32), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("artifact_hash", sa.String(length=32), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["connection_id"], ["odoo_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_sessions_connection_id", "ai_sessions", ["connection_id"])
    op.create_index("ix_ai_sessions_job_id", "ai_sessions", ["job_id"])


def downgrade() -> None:
    if not table_exists("ai_sessions"):
        return
    op.drop_index("ix_ai_sessions_job_id", table_name="ai_sessions")
    op.drop_index("ix_ai_sessions_connection_id", table_name="ai_sessions")
    op.drop_table("ai_sessions")
