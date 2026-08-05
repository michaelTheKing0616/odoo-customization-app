"""GEN2: ai_draft_cache table for recoverable AI drafts

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-05 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("ai_draft_cache"):
        return
    op.create_table(
        "ai_draft_cache",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("connection_id", sa.String(length=36), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("draft_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("domain_pack", sa.String(length=64), nullable=True),
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
    op.create_index("ix_ai_draft_cache_connection_id", "ai_draft_cache", ["connection_id"])
    op.create_index("ix_ai_draft_cache_prompt_hash", "ai_draft_cache", ["prompt_hash"])


def downgrade() -> None:
    if not table_exists("ai_draft_cache"):
        return
    op.drop_index("ix_ai_draft_cache_prompt_hash", table_name="ai_draft_cache")
    op.drop_index("ix_ai_draft_cache_connection_id", table_name="ai_draft_cache")
    op.drop_table("ai_draft_cache")
