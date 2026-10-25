"""NF BOT-KILL-AUDIT: kill switches, cap overrides (tighten-only), append-only bot_audit

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-10-25 19:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: str | Sequence[str] | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "bot_kill_switch",
        sa.Column("scope", sa.String(128), primary_key=True),  # 'global' or a DB fingerprint
        sa.Column("is_on", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("set_by", sa.String(64), nullable=False),
        sa.Column("set_at", _TS, nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        "INSERT INTO bot_kill_switch (scope, is_on, reason, set_by) "
        "VALUES ('global', false, 'initial', 'migration')"
    )
    op.create_table(
        "bot_cap_override",
        sa.Column("db_fingerprint", sa.String(128), primary_key=True),
        sa.Column("batch_cap", sa.Integer(), nullable=False),
        sa.Column("run_cap", sa.Integer(), nullable=False),
        sa.Column("set_by", sa.String(64), nullable=False),
        sa.CheckConstraint("batch_cap BETWEEN 1 AND 50", name="ck_bot_cap_batch_tighten_only"),
        sa.CheckConstraint("run_cap BETWEEN 1 AND 500", name="ck_bot_cap_run_tighten_only"),
    )
    op.create_table(  # owner-issued, single-use approval bound to one exact plan
        "bot_grant",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("db_fingerprint", sa.String(128), nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("n_records", sa.Integer(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("approver_norm", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("expires_at", _TS, nullable=False),
        sa.Column("used_at", _TS, nullable=True),
        sa.Column("job_id", sa.String(64), nullable=True),
        sa.CheckConstraint("level BETWEEN 1 AND 3 AND n_records > 0", name="ck_bot_grant"),
    )
    op.create_table(  # server-issued job = one plan; N is the hard total
        "bot_job",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("db_fingerprint", sa.String(128), nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("n_records", sa.Integer(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("grant_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", _TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ux_bot_job_live_plan",
        "bot_job",
        ["db_fingerprint", "plan_hash"],
        unique=True,
        postgresql_where=sa.text("status IN ('open','done')"),
    )
    op.create_table(
        "bot_audit",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("at", _TS, nullable=False, server_default=sa.func.now()),
        sa.Column("db_fingerprint", sa.String(128), nullable=False),
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("approver", sa.String(64), nullable=True),
        sa.Column("approval_level", sa.SmallInteger(), nullable=False),
        sa.Column("risk_class", sa.String(8), nullable=False),
        sa.Column("rule_ids", sa.String(200), nullable=False),
        sa.Column("diff_hash", sa.String(64), nullable=False),
        sa.Column("blast_count", sa.Integer(), nullable=False),
        sa.Column("batch_no", sa.Integer(), nullable=False),
        sa.Column("caps_hit", sa.String(200), nullable=False),
        sa.Column("snapshot_id", sa.String(128), nullable=True),
        sa.Column("before_image_ref", sa.String(200), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("job_id", sa.String(64), nullable=False),
        sa.Column("n_records", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("row_hash", sa.String(64), nullable=False, unique=True),
        sa.CheckConstraint(
            "decision IN ('intent','applied','refused','duplicate','killed','tripped','undone',"
            "'undo_failed','checkpoint')",
            name="ck_bot_audit_decision",
        ),
    )
    op.create_index("ix_bot_audit_key", "bot_audit", ["idempotency_key"])
    op.create_index(
        "ux_bot_audit_one_intent",
        "bot_audit",
        ["db_fingerprint", "idempotency_key", "batch_no"],
        unique=True,
        postgresql_where=sa.text("decision = 'intent'"),
    )
    op.create_index(
        "ux_bot_audit_job_batch",
        "bot_audit",
        ["job_id", "batch_no"],
        unique=True,
        postgresql_where=sa.text("decision = 'intent' AND job_id <> '-'"),
    )
    op.execute(
        """
        CREATE FUNCTION bot_audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'bot_audit is append-only'; END $$;
        CREATE TRIGGER bot_audit_no_update BEFORE UPDATE OR DELETE ON bot_audit
            FOR EACH ROW EXECUTE FUNCTION bot_audit_append_only();
        CREATE TRIGGER bot_audit_no_truncate BEFORE TRUNCATE ON bot_audit
            FOR EACH STATEMENT EXECUTE FUNCTION bot_audit_append_only();
        REVOKE UPDATE, DELETE, TRUNCATE ON bot_audit FROM PUBLIC;
        """
    )
    # Role split: bot_audit + its trigger function belong to a NOLOGIN owner role, so the
    # app role (member of bot_app) can only INSERT/SELECT and cannot DISABLE TRIGGER.
    # Needs CREATEROLE (or superuser) for the migration user; see card caveats.
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='bot_audit_owner') THEN
            CREATE ROLE bot_audit_owner NOLOGIN; END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='bot_app') THEN
            CREATE ROLE bot_app NOLOGIN; END IF;
        END $$;
        ALTER TABLE bot_audit OWNER TO bot_audit_owner;
        ALTER FUNCTION bot_audit_append_only() OWNER TO bot_audit_owner;
        GRANT SELECT, INSERT ON bot_audit TO bot_app;
        GRANT USAGE, SELECT ON SEQUENCE bot_audit_id_seq TO bot_app;
        GRANT SELECT, INSERT, UPDATE ON bot_kill_switch, bot_cap_override, bot_job TO bot_app;
        GRANT SELECT, INSERT, UPDATE (used_at, job_id) ON bot_grant TO bot_app;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS bot_audit_no_truncate ON bot_audit")
    op.execute("DROP TRIGGER IF EXISTS bot_audit_no_update ON bot_audit")
    op.drop_index("ux_bot_audit_job_batch", table_name="bot_audit")
    op.drop_index("ux_bot_audit_one_intent", table_name="bot_audit")
    op.drop_index("ix_bot_audit_key", table_name="bot_audit")
    op.drop_table("bot_audit")
    op.execute("DROP FUNCTION IF EXISTS bot_audit_append_only()")
    op.drop_index("ux_bot_job_live_plan", table_name="bot_job")
    op.drop_table("bot_job")
    op.drop_table("bot_grant")
    op.drop_table("bot_cap_override")
    op.drop_table("bot_kill_switch")
