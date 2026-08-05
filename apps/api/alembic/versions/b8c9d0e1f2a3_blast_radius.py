"""TRUST-3: blast-radius tables

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-03 23:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("connection_mutation_hourly"):
        op.create_table(
            "connection_mutation_hourly",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("connection_id", sa.String(length=36), nullable=False),
            sa.Column("hour_bucket", sa.DateTime(timezone=True), nullable=False),
            sa.Column("mutation_count", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["connection_id"], ["odoo_connections.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_connection_mutation_hourly_connection_id",
            "connection_mutation_hourly",
            ["connection_id"],
        )
        op.create_index(
            "ix_connection_mutation_hourly_hour_bucket",
            "connection_mutation_hourly",
            ["hour_bucket"],
        )
    if not table_exists("trust_anomaly_events"):
        op.create_table(
            "trust_anomaly_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("connection_id", sa.String(length=36), nullable=False),
            sa.Column("workspace_id", sa.String(length=36), nullable=True),
            sa.Column("mutation_count", sa.Integer(), nullable=False),
            sa.Column("threshold", sa.Integer(), nullable=False),
            sa.Column("hour_bucket", sa.DateTime(timezone=True), nullable=False),
            sa.Column("action", sa.String(length=40), nullable=False, server_default="writes_paused"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["connection_id"], ["odoo_connections.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_trust_anomaly_events_connection_id", "trust_anomaly_events", ["connection_id"]
        )
        op.create_index(
            "ix_trust_anomaly_events_workspace_id", "trust_anomaly_events", ["workspace_id"]
        )


def downgrade() -> None:
    if table_exists("trust_anomaly_events"):
        op.drop_index("ix_trust_anomaly_events_workspace_id", table_name="trust_anomaly_events")
        op.drop_index("ix_trust_anomaly_events_connection_id", table_name="trust_anomaly_events")
        op.drop_table("trust_anomaly_events")
    if table_exists("connection_mutation_hourly"):
        op.drop_index(
            "ix_connection_mutation_hourly_hour_bucket", table_name="connection_mutation_hourly"
        )
        op.drop_index(
            "ix_connection_mutation_hourly_connection_id", table_name="connection_mutation_hourly"
        )
        op.drop_table("connection_mutation_hourly")
