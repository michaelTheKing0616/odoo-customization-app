"""WAL journal, before-images, and one apply lock per Odoo database.

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-10-03 21:40:00.000000

The executor still journals in process. This revision only declares the
tables. It is not applied by the test suite.

WAL kinds: INTENT, BEFORE, RESULT, COMPENSATE, ERROR.
Before-image retention is 30 days, 90 days when risk is R3. The writer
sets retain_until. This migration does not insert rows.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "s9t0u1v2w3x4"
down_revision: Union[str, Sequence[str], None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("journal_entry"):
        op.create_table(
            "journal_entry",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("odoo_database", sa.String(length=200), nullable=False),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("op_index", sa.Integer(), nullable=True),
            sa.Column("op_type", sa.String(length=80), nullable=True),
            sa.Column("plan_hash", sa.String(length=16), nullable=True),
            sa.Column("mode", sa.String(length=1), nullable=True),
            sa.Column("run_status", sa.String(length=32), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_journal_entry_run_id", "journal_entry", ["run_id"])
        op.create_index("ix_journal_entry_odoo_database", "journal_entry", ["odoo_database"])
        op.create_index("ix_journal_entry_heartbeat_at", "journal_entry", ["heartbeat_at"])

    if not table_exists("before_image"):
        op.create_table(
            "before_image",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("journal_entry_id", sa.String(length=36), nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("op_index", sa.Integer(), nullable=False),
            sa.Column("risk", sa.String(length=8), nullable=False),
            sa.Column("snapshot_json", sa.Text(), nullable=False),
            sa.Column("retain_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entry.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_before_image_run_id", "before_image", ["run_id"])
        op.create_index("ix_before_image_journal_entry_id", "before_image", ["journal_entry_id"])

    if not table_exists("apply_database_lock"):
        op.create_table(
            "apply_database_lock",
            sa.Column("odoo_database", sa.String(length=200), nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("acquired_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("odoo_database"),
        )


def downgrade() -> None:
    if table_exists("apply_database_lock"):
        op.drop_table("apply_database_lock")
    if table_exists("before_image"):
        op.drop_index("ix_before_image_journal_entry_id", table_name="before_image")
        op.drop_index("ix_before_image_run_id", table_name="before_image")
        op.drop_table("before_image")
    if table_exists("journal_entry"):
        op.drop_index("ix_journal_entry_heartbeat_at", table_name="journal_entry")
        op.drop_index("ix_journal_entry_odoo_database", table_name="journal_entry")
        op.drop_index("ix_journal_entry_run_id", table_name="journal_entry")
        op.drop_table("journal_entry")
