"""NF BV-STORE: verify_runs and verify_artifacts

Revision ID: 4b7e9c1d2a3f
Revises: b0a1c2d3e4f5
Create Date: 2026-10-23 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4b7e9c1d2a3f"
down_revision: str | Sequence[str] | None = "b0a1c2d3e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verify_runs",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("odoo_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("changeset_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("layers", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_verify_runs_connection_id", "verify_runs", ["connection_id"])
    op.create_index("ix_verify_runs_workspace_id", "verify_runs", ["workspace_id"])
    op.create_index("ix_verify_runs_connection_run", "verify_runs", ["connection_id", "run_id"])
    op.create_table(
        "verify_artifacts",
        sa.Column("artifact_id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("verify_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("connection_id", sa.String(36), nullable=False),
        sa.Column("blob_path", sa.String(), nullable=False),
        sa.Column(
            "content_type", sa.String(), nullable=False, server_default=sa.text("'image/png'")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verify_artifacts_connection_id", "verify_artifacts", ["connection_id"])
    op.create_index("ix_verify_artifacts_run_id", "verify_artifacts", ["run_id"])


def downgrade() -> None:
    op.drop_table("verify_artifacts")
    op.drop_table("verify_runs")
