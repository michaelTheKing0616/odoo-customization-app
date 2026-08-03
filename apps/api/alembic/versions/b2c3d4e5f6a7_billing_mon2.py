"""billing entitlements and project lifecycle (MON-2)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-03 17:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_plans",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=120), nullable=True),
        sa.Column("paystack_plan_code", sa.String(length=120), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "plan_features",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=40), nullable=False),
        sa.Column("feature_key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["billing_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "feature_key", name="uq_plan_feature"),
    )
    op.create_index("ix_plan_features_plan_id", "plan_features", ["plan_id"])
    op.create_index("ix_plan_features_feature_key", "plan_features", ["feature_key"])

    op.create_table(
        "workspace_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=40), nullable=False, server_default="free_solo"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("processor", sa.String(length=20), nullable=True),
        sa.Column("external_customer_id", sa.String(length=120), nullable=True),
        sa.Column("external_subscription_id", sa.String(length=120), nullable=True),
        sa.Column("seat_quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("extra_project_slots", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["billing_plans.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index("ix_workspace_subscriptions_workspace_id", "workspace_subscriptions", ["workspace_id"], unique=True)

    op.create_table(
        "entitlement_overrides",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("feature_key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entitlement_overrides_workspace_id", "entitlement_overrides", ["workspace_id"])

    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("processor", sa.String(length=20), nullable=False),
        sa.Column("event_id", sa.String(length=200), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("processor", "event_id", name="uq_webhook_event"),
    )

    op.create_table(
        "project_passes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_passes_workspace_id", "project_passes", ["workspace_id"])

    op.add_column(
        "customization_projects",
        sa.Column("lifecycle_status", sa.String(length=20), nullable=False, server_default="active"),
    )


def downgrade() -> None:
    op.drop_column("customization_projects", "lifecycle_status")
    op.drop_index("ix_project_passes_workspace_id", "project_passes")
    op.drop_table("project_passes")
    op.drop_table("billing_webhook_events")
    op.drop_index("ix_entitlement_overrides_workspace_id", "entitlement_overrides")
    op.drop_table("entitlement_overrides")
    op.drop_index("ix_workspace_subscriptions_workspace_id", "workspace_subscriptions")
    op.drop_table("workspace_subscriptions")
    op.drop_index("ix_plan_features_feature_key", "plan_features")
    op.drop_index("ix_plan_features_plan_id", "plan_features")
    op.drop_table("plan_features")
    op.drop_table("billing_plans")
