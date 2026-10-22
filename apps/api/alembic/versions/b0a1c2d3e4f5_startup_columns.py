"""columns and tables previously added only by startup ALTERs

Revision ID: b0a1c2d3e4f5
Revises: ze1f2a3b4c5d
Create Date: 2026-10-22 04:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import column_exists, table_exists

revision: str = "b0a1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "ze1f2a3b4c5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Unique constraints duplicated by a unique index, or absent from the ORM.
# Models with unique=True, index=True compile to one unique index.
_REDUNDANT_UNIQUES: tuple[tuple[str, str, list[str]], ...] = (
    ("users", "users_email_key", ["email"]),
    ("workspaces", "workspaces_slug_key", ["slug"]),
    ("workspace_invitations", "workspace_invitations_token_hash_key", ["token_hash"]),
    ("user_sessions", "user_sessions_token_hash_key", ["token_hash"]),
    ("password_resets", "password_resets_token_hash_key", ["token_hash"]),
    ("email_verifications", "email_verifications_token_hash_key", ["token_hash"]),
    ("workspace_subscriptions", "workspace_subscriptions_workspace_id_key", ["workspace_id"]),
    ("dry_run_receipts", "dry_run_receipts_token_hash_key", ["token_hash"]),
    (
        "live_demo_copilot_sessions",
        "live_demo_copilot_sessions_attendee_bot_id_key",
        ["attendee_bot_id"],
    ),
    (
        "live_demo_webhook_receipts",
        "live_demo_webhook_receipts_payload_hash_key",
        ["payload_hash"],
    ),
    ("oauth_pending_states", "oauth_pending_states_state_hash_key", ["state_hash"]),
    ("oauth_totp_pending", "oauth_totp_pending_token_hash_key", ["token_hash"]),
    ("bridge_connections", "uq_bridge_connection_display", ["workspace_id", "display_name"]),
    (
        "integration_events",
        "uq_integration_event_idempotency",
        ["connection_id", "idempotency_key"],
    ),
)

# These indexes were created non-unique beside a unique constraint.
_MAKE_UNIQUE_INDEXES: tuple[tuple[str, str, list[str]], ...] = (
    ("dry_run_receipts", "ix_dry_run_receipts_token_hash", ["token_hash"]),
    (
        "live_demo_copilot_sessions",
        "ix_live_demo_copilot_sessions_attendee_bot_id",
        ["attendee_bot_id"],
    ),
    (
        "live_demo_webhook_receipts",
        "ix_live_demo_webhook_receipts_payload_hash",
        ["payload_hash"],
    ),
    ("oauth_pending_states", "ix_oauth_pending_states_state_hash", ["state_hash"]),
    ("oauth_totp_pending", "ix_oauth_totp_pending_token_hash", ["token_hash"]),
)


def _unique_names(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_unique_constraints(table)}


def _drop_unique(table: str, name: str) -> None:
    if table_exists(table) and name in _unique_names(table):
        op.drop_constraint(name, table, type_="unique")


def _add_unique(table: str, name: str, columns: list[str]) -> None:
    if table_exists(table) and name not in _unique_names(table):
        op.create_unique_constraint(name, table, columns)


def _index(table: str, name: str) -> dict | None:
    insp = sa.inspect(op.get_bind())
    return next((ix for ix in insp.get_indexes(table) if ix["name"] == name), None)


def _drop_index(table: str, name: str) -> None:
    if table_exists(table) and _index(table, name) is not None:
        op.drop_index(name, table_name=table)


def _ensure_index(table: str, name: str, columns: list[str], *, unique: bool) -> None:
    if not table_exists(table):
        return
    found = _index(table, name)
    same_columns = list(found.get("column_names") or []) == columns if found else False
    if found is not None and bool(found.get("unique")) == unique and same_columns:
        return
    if found is not None:
        op.drop_index(name, table_name=table)
    op.create_index(name, table, columns, unique=unique)


def _add_column(table: str, name: str, column: sa.Column) -> None:
    if table_exists(table) and not column_exists(table, name):
        op.add_column(table, column)


def _create_saved_scripts() -> None:
    if table_exists("saved_scripts"):
        _ensure_index(
            "saved_scripts",
            "ix_saved_scripts_workspace_id",
            ["workspace_id"],
            unique=False,
        )
        return
    op.create_table(
        "saved_scripts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("script_content", sa.Text(), nullable=False),
        sa.Column("shared", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=36), nullable=True),
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
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_scripts_workspace_id", "saved_scripts", ["workspace_id"])


def _create_script_runs() -> None:
    if table_exists("script_runs"):
        _add_column(
            "script_runs",
            "snapshot_id",
            sa.Column("snapshot_id", sa.String(length=36), nullable=True),
        )
        _ensure_index("script_runs", "ix_script_runs_workspace_id", ["workspace_id"], unique=False)
        _ensure_index(
            "script_runs",
            "ix_script_runs_connection_id",
            ["connection_id"],
            unique=False,
        )
        _ensure_index("script_runs", "ix_script_runs_job_id", ["job_id"], unique=False)
        return
    op.create_table(
        "script_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("connection_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("saved_script_id", sa.String(length=36), nullable=True),
        sa.Column("script_content", sa.Text(), nullable=False),
        sa.Column("script_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("write_counts_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("snapshot_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["connection_id"], ["odoo_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_script_runs_workspace_id", "script_runs", ["workspace_id"])
    op.create_index("ix_script_runs_connection_id", "script_runs", ["connection_id"])
    op.create_index("ix_script_runs_job_id", "script_runs", ["job_id"])


def _create_connection_production_readiness() -> None:
    if table_exists("connection_production_readiness"):
        return
    op.create_table(
        "connection_production_readiness",
        sa.Column("connection_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_drill_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_drill_id", sa.String(length=36), nullable=True),
        sa.Column("least_privilege_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("backup_artifact_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_write_ack_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["connection_id"], ["odoo_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("connection_id"),
    )


def _align_ingest_indexes() -> None:
    _drop_index("ingest_layout_cache", "ix_ingest_layout_cache_fingerprint_doc")
    _ensure_index(
        "ingest_layout_cache",
        "ix_ingest_layout_cache_source_fingerprint",
        ["source_fingerprint"],
        unique=False,
    )
    _ensure_index(
        "ingest_layout_cache",
        "ix_ingest_layout_cache_doc_type",
        ["doc_type"],
        unique=False,
    )


def _restore_ingest_indexes() -> None:
    _drop_index("ingest_layout_cache", "ix_ingest_layout_cache_source_fingerprint")
    _drop_index("ingest_layout_cache", "ix_ingest_layout_cache_doc_type")
    _ensure_index(
        "ingest_layout_cache",
        "ix_ingest_layout_cache_fingerprint_doc",
        ["source_fingerprint", "doc_type"],
        unique=False,
    )


def upgrade() -> None:
    _create_saved_scripts()
    _create_script_runs()
    _create_connection_production_readiness()
    _add_column("audit_logs", "detail_json", sa.Column("detail_json", sa.Text(), nullable=True))
    _add_column(
        "workspaces",
        "beta_partner",
        sa.Column("beta_partner", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for table, name, _columns in _REDUNDANT_UNIQUES:
        _drop_unique(table, name)
    for table, name, columns in _MAKE_UNIQUE_INDEXES:
        _ensure_index(table, name, columns, unique=True)
    _align_ingest_indexes()


def downgrade() -> None:
    _restore_ingest_indexes()
    for table, name, columns in _MAKE_UNIQUE_INDEXES:
        _ensure_index(table, name, columns, unique=False)
    for table, name, columns in _REDUNDANT_UNIQUES:
        _add_unique(table, name, columns)
    if column_exists("workspaces", "beta_partner"):
        op.drop_column("workspaces", "beta_partner")
    if column_exists("audit_logs", "detail_json"):
        op.drop_column("audit_logs", "detail_json")
    if table_exists("connection_production_readiness"):
        op.drop_table("connection_production_readiness")
    if table_exists("script_runs"):
        _drop_index("script_runs", "ix_script_runs_job_id")
        _drop_index("script_runs", "ix_script_runs_connection_id")
        _drop_index("script_runs", "ix_script_runs_workspace_id")
        op.drop_table("script_runs")
    if table_exists("saved_scripts"):
        _drop_index("saved_scripts", "ix_saved_scripts_workspace_id")
        op.drop_table("saved_scripts")
