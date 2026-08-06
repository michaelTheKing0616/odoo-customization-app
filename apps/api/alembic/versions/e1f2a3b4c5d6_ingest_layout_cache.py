"""ING-4: ingest_layout_cache for repeat supplier fingerprints

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-06 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("ingest_layout_cache"):
        return
    op.create_table(
        "ingest_layout_cache",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("doc_type", sa.String(length=32), nullable=False),
        sa.Column("headers_json", sa.Text(), nullable=True),
        sa.Column("mapping_json", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingest_layout_cache_fingerprint_doc",
        "ingest_layout_cache",
        ["source_fingerprint", "doc_type"],
    )


def downgrade() -> None:
    if not table_exists("ingest_layout_cache"):
        return
    op.drop_index("ix_ingest_layout_cache_fingerprint_doc", table_name="ingest_layout_cache")
    op.drop_table("ingest_layout_cache")
