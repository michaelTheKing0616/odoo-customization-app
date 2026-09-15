"""Live Demo Co-Pilot durable sessions, consent audit, transcripts, webhook receipts

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-09-15 11:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import table_exists

revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, Sequence[str], None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("live_demo_copilot_sessions"):
        op.create_table(
            "live_demo_copilot_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("workspace_id", sa.String(length=36), nullable=True),
            sa.Column("connection_id", sa.String(length=36), nullable=True),
            sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("meeting_url", sa.Text(), nullable=False),
            sa.Column("meeting_url_hash", sa.String(length=64), nullable=False),
            sa.Column("bot_name", sa.String(length=120), nullable=False),
            sa.Column("disclosure_accepted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("disclosure_version", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("disclosure_accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attendees_notified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("retention_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("declined", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("attendee_bot_id", sa.String(length=80), nullable=True),
            sa.Column("bot_state", sa.String(length=40), nullable=False, server_default="idle"),
            sa.Column("mock_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("data_purged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["connection_id"], ["odoo_connections.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("attendee_bot_id"),
        )
        op.create_index("ix_live_demo_copilot_sessions_workspace_id", "live_demo_copilot_sessions", ["workspace_id"])
        op.create_index("ix_live_demo_copilot_sessions_connection_id", "live_demo_copilot_sessions", ["connection_id"])
        op.create_index("ix_live_demo_copilot_sessions_meeting_url_hash", "live_demo_copilot_sessions", ["meeting_url_hash"])
        op.create_index("ix_live_demo_copilot_sessions_attendee_bot_id", "live_demo_copilot_sessions", ["attendee_bot_id"])
        op.create_index("ix_live_demo_copilot_sessions_created_by_user_id", "live_demo_copilot_sessions", ["created_by_user_id"])

    if not table_exists("live_demo_consent_audit"):
        op.create_table(
            "live_demo_consent_audit",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("workspace_id", sa.String(length=36), nullable=True),
            sa.Column("actor_user_id", sa.String(length=36), nullable=True),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("disclosure_version", sa.String(length=64), nullable=False),
            sa.Column("attendees_notified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("retention_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("meeting_url_hash", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["live_demo_copilot_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_live_demo_consent_audit_session_id", "live_demo_consent_audit", ["session_id"])
        op.create_index("ix_live_demo_consent_audit_workspace_id", "live_demo_consent_audit", ["workspace_id"])

    if not table_exists("live_demo_transcript_lines"):
        op.create_table(
            "live_demo_transcript_lines",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("workspace_id", sa.String(length=36), nullable=True),
            sa.Column("speaker_name", sa.String(length=200), nullable=False),
            sa.Column("speaker_uuid", sa.String(length=80), nullable=True),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("timestamp_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["live_demo_copilot_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_live_demo_transcript_lines_session_id", "live_demo_transcript_lines", ["session_id"])
        op.create_index("ix_live_demo_transcript_lines_workspace_id", "live_demo_transcript_lines", ["workspace_id"])

    if not table_exists("live_demo_webhook_receipts"):
        op.create_table(
            "live_demo_webhook_receipts",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("payload_hash", sa.String(length=64), nullable=False),
            sa.Column("trigger", sa.String(length=64), nullable=False),
            sa.Column("bot_id", sa.String(length=80), nullable=True),
            sa.Column("session_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("payload_hash"),
        )
        op.create_index("ix_live_demo_webhook_receipts_payload_hash", "live_demo_webhook_receipts", ["payload_hash"])
        op.create_index("ix_live_demo_webhook_receipts_bot_id", "live_demo_webhook_receipts", ["bot_id"])
        op.create_index("ix_live_demo_webhook_receipts_session_id", "live_demo_webhook_receipts", ["session_id"])


def downgrade() -> None:
    for table, indexes in (
        ("live_demo_webhook_receipts", ["ix_live_demo_webhook_receipts_session_id", "ix_live_demo_webhook_receipts_bot_id", "ix_live_demo_webhook_receipts_payload_hash"]),
        ("live_demo_transcript_lines", ["ix_live_demo_transcript_lines_workspace_id", "ix_live_demo_transcript_lines_session_id"]),
        ("live_demo_consent_audit", ["ix_live_demo_consent_audit_workspace_id", "ix_live_demo_consent_audit_session_id"]),
        ("live_demo_copilot_sessions", [
            "ix_live_demo_copilot_sessions_created_by_user_id",
            "ix_live_demo_copilot_sessions_attendee_bot_id",
            "ix_live_demo_copilot_sessions_meeting_url_hash",
            "ix_live_demo_copilot_sessions_connection_id",
            "ix_live_demo_copilot_sessions_workspace_id",
        ]),
    ):
        if not table_exists(table):
            continue
        for ix in indexes:
            try:
                op.drop_index(ix, table_name=table)
            except Exception:
                pass
        op.drop_table(table)
