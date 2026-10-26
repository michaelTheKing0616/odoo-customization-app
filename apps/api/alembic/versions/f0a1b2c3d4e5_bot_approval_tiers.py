"""NF BOT-APPROVAL-TIERS: per-plan approval rows + approve/reject audit decisions

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-10-26 09:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "e9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = (
    "'intent','applied','refused','duplicate','killed','tripped','undone','undo_failed',"
    "'checkpoint'"
)

# Decided rows are frozen except the escalation path (approved -> pending/refused, grant
# dropped, tier never lower). Identity columns never change. The bot role can never make or
# change a decision, only escalate.
_IS_BOT_FN = """
CREATE OR REPLACE FUNCTION bot_is_bot() RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT current_user = 'bot_app' OR EXISTS (
    SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid
    JOIN pg_roles u ON u.oid = m.member WHERE r.rolname = 'bot_app' AND u.rolname = current_user)
$$;
"""

# Bot-role runtime guards. A job row is a live permission (open_job reuses it without a
# grant), so the bot may only insert one backed by a grant it just consumed for this exact
# job (level >= 2) or by an owner-written auto approval row (level 1), and may never revive
# a finished job. The bot may turn a kill switch on, never off.
_RUNTIME_FN = """
CREATE OR REPLACE FUNCTION bot_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT bot_is_bot() THEN RETURN NEW; END IF;
  IF TG_OP = 'UPDATE' THEN
    IF NEW.status IS DISTINCT FROM OLD.status AND OLD.status <> 'open' THEN
      RAISE EXCEPTION 'finished jobs are final';
    END IF;
    RETURN NEW;
  END IF;
  IF NEW.status <> 'open' THEN RAISE EXCEPTION 'the bot role inserts open jobs only'; END IF;
  IF NEW.level >= 2 THEN
    IF NOT EXISTS (SELECT 1 FROM bot_grant g WHERE g.id = NEW.grant_id AND g.job_id = NEW.id
        AND g.used_at IS NOT NULL AND g.db_fingerprint = NEW.db_fingerprint
        AND g.plan_hash = NEW.plan_hash AND g.n_records = NEW.n_records
        AND g.level >= NEW.level) THEN
      RAISE EXCEPTION 'job level needs the grant consumed for this job';
    END IF;
  ELSIF NOT EXISTS (SELECT 1 FROM bot_approval a WHERE a.db_fingerprint = NEW.db_fingerprint
        AND a.plan_hash = NEW.plan_hash AND a.n_records = NEW.n_records
        AND a.status = 'auto' AND a.tier = 1) THEN
    RAISE EXCEPTION 'a level-1 job needs an auto approval';
  END IF;
  RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION bot_kill_switch_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF bot_is_bot() THEN
    IF NOT NEW.is_on THEN RAISE EXCEPTION 'the bot role cannot turn a kill switch off'; END IF;
    IF TG_OP = 'UPDATE' AND NEW.scope IS DISTINCT FROM OLD.scope THEN
      RAISE EXCEPTION 'the bot role cannot move a kill switch';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION bot_grant_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF bot_is_bot() AND (OLD.used_at IS NOT NULL OR NEW.used_at IS NULL OR NEW.job_id IS NULL) THEN
    RAISE EXCEPTION 'the bot role may only consume an unused grant, once';
  END IF;
  RETURN NEW;
END $$;
"""

_TEMP_LOCKDOWN = """
DO $$ BEGIN
  EXECUTE format('GRANT TEMP ON DATABASE %I TO %I', current_database(), current_user);
  EXECUTE format('REVOKE TEMP ON DATABASE %I FROM PUBLIC', current_database());
  EXECUTE format('REVOKE TEMP, CREATE ON DATABASE %I FROM bot_app', current_database());
  EXECUTE format('ALTER ROLE bot_app IN DATABASE %I SET search_path = public, pg_temp',
                 current_database());
  -- no large-object creation for anyone but the migrating/API role (per-database ACL)
  EXECUTE format('GRANT EXECUTE ON FUNCTION pg_catalog.lo_create(oid),'
    ' pg_catalog.lo_creat(integer),'
    ' pg_catalog.lo_from_bytea(oid, bytea) TO %I', current_user);
  REVOKE EXECUTE ON FUNCTION pg_catalog.lo_create(oid), pg_catalog.lo_creat(integer),
    pg_catalog.lo_from_bytea(oid, bytea) FROM PUBLIC;
END $$;
"""
_TEMP_RESTORE = """
DO $$ BEGIN
  EXECUTE format('ALTER ROLE bot_app IN DATABASE %I RESET search_path', current_database());
  EXECUTE format('GRANT TEMP ON DATABASE %I TO PUBLIC', current_database());
  GRANT EXECUTE ON FUNCTION pg_catalog.lo_create(oid), pg_catalog.lo_creat(integer),
    pg_catalog.lo_from_bytea(oid, bytea) TO PUBLIC;
END $$;
"""

_GUARD_FN = """
CREATE OR REPLACE FUNCTION bot_approval_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE is_bot boolean := bot_is_bot();
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF is_bot AND NOT (NEW.status IN ('auto','pending','refused') AND NEW.grant_id IS NULL
       AND NEW.decided_by IS NULL AND NEW.decided_at IS NULL
       AND NEW.decided_facts_hash IS NULL) THEN
      RAISE EXCEPTION 'the bot role cannot insert a decided plan';
    END IF;
    RETURN NEW;
  END IF;
  IF NEW.id <> OLD.id OR NEW.plan_hash <> OLD.plan_hash
     OR NEW.db_fingerprint <> OLD.db_fingerprint OR NEW.connection_id <> OLD.connection_id
     OR NEW.requested_by <> OLD.requested_by OR NEW.n_records <> OLD.n_records
     OR NEW.task_id <> OLD.task_id THEN
    RAISE EXCEPTION 'bot_approval identity is immutable';
  END IF;
  IF OLD.status = 'rejected' THEN RAISE EXCEPTION 'rejected plans stay rejected'; END IF;
  IF OLD.tier IS NOT NULL AND NEW.tier IS NOT NULL AND NEW.tier < OLD.tier
     AND OLD.status <> 'refused' THEN
    RAISE EXCEPTION 'tiers only go up';
  END IF;
  IF OLD.status = 'approved' AND NOT (NEW.status IN ('pending','refused')
     AND NEW.grant_id IS NULL AND NEW.decided_facts_hash IS NULL) THEN
    RAISE EXCEPTION 'approved plans can only be escalated';
  END IF;
  IF NEW.status IN ('approved','rejected') AND NEW.status IS DISTINCT FROM OLD.status THEN
    IF is_bot THEN RAISE EXCEPTION 'the bot role cannot decide'; END IF;
    IF OLD.status <> 'pending' THEN RAISE EXCEPTION 'only pending plans can be decided'; END IF;
  END IF;
  IF is_bot AND NEW.status = 'auto' AND OLD.status <> 'refused' AND OLD.status <> 'auto' THEN
    RAISE EXCEPTION 'the bot role cannot relax a plan';
  END IF;
  RETURN NEW;
END $$;
"""


def upgrade() -> None:
    op.create_table(  # one server-classified plan; tier/N never come from the client
        "bot_approval",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("connection_id", sa.String(64), nullable=False),
        sa.Column("db_fingerprint", sa.String(200), nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("risk_class", sa.String(8), nullable=False),
        sa.Column("n_records", sa.Integer, nullable=False),
        sa.Column("tier", sa.Integer, nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("rehearsal_id", sa.String(64), nullable=True),
        sa.Column("requested_by", sa.String(200), nullable=False),
        sa.Column("decided_by", sa.String(200), nullable=True),
        sa.Column("grant_id", sa.String(32), nullable=True),
        sa.Column("card", sa.Text, nullable=False),
        sa.Column("facts_hash", sa.String(64), nullable=False),  # every tiering fact
        sa.Column("decided_facts_hash", sa.String(64), nullable=True),  # facts a person approved
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("db_fingerprint", "plan_hash", name="ux_bot_approval_plan"),
        sa.CheckConstraint(
            "status IN ('auto','pending','approved','rejected','refused') AND n_records > 0"
            " AND (tier IS NULL OR tier BETWEEN 1 AND 3)"
            " AND (status <> 'refused' OR tier IS NULL)"
            " AND (status NOT IN ('auto','pending','approved') OR tier IS NOT NULL)"
            " AND (status <> 'auto' OR tier = 1)"
            " AND (status <> 'approved' OR (grant_id IS NOT NULL"
            " AND decided_facts_hash = facts_hash))",
            name="ck_bot_approval",
        ),
    )
    op.create_index("ix_bot_approval_conn", "bot_approval", ["connection_id", "status"])
    op.execute("ALTER TABLE bot_audit DROP CONSTRAINT ck_bot_audit_decision")
    op.execute(
        "ALTER TABLE bot_audit ADD CONSTRAINT ck_bot_audit_decision"
        f" CHECK (decision IN ({_OLD},'approved','rejected'))"
    )
    op.execute(_IS_BOT_FN)
    op.execute(_GUARD_FN)
    op.execute(
        "CREATE TRIGGER bot_approval_guard BEFORE INSERT OR UPDATE ON bot_approval"
        " FOR EACH ROW EXECUTE FUNCTION bot_approval_guard()"
    )
    # bot role: no table-level UPDATE; only the columns the escalation path rewrites
    # approval rows are written only by the API/owner role; the bot reads them
    op.execute("GRANT SELECT ON bot_approval TO bot_app")
    op.execute(_RUNTIME_FN)
    op.execute(
        "CREATE TRIGGER bot_job_guard BEFORE INSERT OR UPDATE ON bot_job"
        " FOR EACH ROW EXECUTE FUNCTION bot_job_guard()"
    )
    op.execute(
        "CREATE TRIGGER bot_kill_switch_guard BEFORE INSERT OR UPDATE ON bot_kill_switch"
        " FOR EACH ROW EXECUTE FUNCTION bot_kill_switch_guard()"
    )
    # caps are owner-set only; the bot may change a job's status only
    op.execute("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON bot_cap_override FROM bot_app")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON bot_job FROM bot_app")
    op.execute("GRANT UPDATE (status) ON bot_job TO bot_app")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON bot_kill_switch FROM bot_app")
    op.execute("GRANT UPDATE (is_on, reason, set_by, set_at) ON bot_kill_switch TO bot_app")
    op.execute(
        "CREATE TRIGGER bot_grant_guard BEFORE UPDATE ON bot_grant"
        " FOR EACH ROW EXECUTE FUNCTION bot_grant_guard()"
    )
    # No temp-table shadows: a temp bot_* table would be read first by unqualified names.
    # TEMP leaves PUBLIC (so bot_app and its login members lose it); the migrating/API role
    # keeps it explicitly. pg_temp is also pinned last on the bot role's search_path.
    op.execute(_TEMP_LOCKDOWN)
    # grants are minted only by the API/owner role; the bot may only mark them used
    op.execute("REVOKE INSERT, DELETE, TRUNCATE ON bot_grant FROM bot_app")


def downgrade() -> None:
    op.execute(_TEMP_RESTORE)
    op.execute("DROP TRIGGER IF EXISTS bot_job_guard ON bot_job")
    op.execute("DROP TRIGGER IF EXISTS bot_kill_switch_guard ON bot_kill_switch")
    op.execute("DROP FUNCTION IF EXISTS bot_job_guard()")
    op.execute("DROP FUNCTION IF EXISTS bot_kill_switch_guard()")
    op.execute("DROP TRIGGER IF EXISTS bot_grant_guard ON bot_grant")
    op.execute("DROP FUNCTION IF EXISTS bot_grant_guard()")
    op.execute("GRANT UPDATE ON bot_kill_switch TO bot_app")
    op.execute("GRANT INSERT, UPDATE ON bot_cap_override, bot_job TO bot_app")
    op.execute("GRANT INSERT ON bot_grant TO bot_app")
    op.execute("ALTER TABLE bot_audit DROP CONSTRAINT ck_bot_audit_decision")
    op.execute(
        f"ALTER TABLE bot_audit ADD CONSTRAINT ck_bot_audit_decision CHECK (decision IN ({_OLD}))"
        " NOT VALID"
    )
    op.execute("DROP TRIGGER IF EXISTS bot_approval_guard ON bot_approval")
    op.execute("DROP FUNCTION IF EXISTS bot_approval_guard()")
    op.execute("DROP FUNCTION IF EXISTS bot_is_bot()")
    op.drop_index("ix_bot_approval_conn", table_name="bot_approval")
    op.drop_table("bot_approval")
