"""Drift guard: every privilege the bot runtime role holds on bot_* objects, read from the
live catalog (direct, PUBLIC and inherited grants all count via has_*_privilege), must be
on the reviewed allowlist below. A migration that widens bot_app fails here."""

from __future__ import annotations

from sqlalchemy import text

from tests.test_nf_bot_kill_audit import engine  # noqa: F401 - shared migrated DB

# (object, column or "*", privilege): reason
ALLOWLIST: dict[tuple[str, str, str], str] = {
    ("bot_approval", "*", "SELECT"): "reserve/grant_source read tiers; writes are owner-only",
    ("bot_audit", "*", "INSERT"): "runtime appends audit rows; append-only trigger, no UPDATE",
    ("bot_audit", "*", "SELECT"): "chain head lookup for hash-chained appends",
    ("bot_audit_id_seq", "*", "USAGE"): "nextval for audit ids (no setval: no UPDATE)",
    ("bot_audit_id_seq", "*", "SELECT"): "currval for audit ids",
    ("bot_cap_override", "*", "SELECT"): "runtime reads caps; only the owner sets them",
    ("bot_grant", "*", "SELECT"): "open_job checks a grant before consuming it",
    ("bot_grant", "used_at", "UPDATE"): "consume once; bot_grant_guard refuses re-use",
    ("bot_grant", "job_id", "UPDATE"): "bind to the consuming job; frozen after use",
    ("bot_job", "*", "INSERT"): "open_job; bot_job_guard needs a consumed grant or auto row",
    ("bot_job", "*", "SELECT"): "live-job reuse lookup",
    ("bot_job", "status", "UPDATE"): "set_job closes a job; finished jobs are final",
    ("bot_kill_switch", "*", "INSERT"): "trip a new scope ON; guard refuses OFF",
    ("bot_kill_switch", "*", "SELECT"): "check() reads switches",
    ("bot_kill_switch", "is_on", "UPDATE"): "trip ON via upsert; guard refuses ON->off",
    ("bot_kill_switch", "reason", "UPDATE"): "trip reason via upsert",
    ("bot_kill_switch", "set_by", "UPDATE"): "trip actor via upsert",
    ("bot_kill_switch", "set_at", "UPDATE"): "trip time via upsert; scope is not updatable",
}

_TABLE_PRIVS = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
_COL_PRIVS = ("SELECT", "INSERT", "UPDATE", "REFERENCES")


def actual(eng) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    with eng.connect() as c:
        tables = c.execute(text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
            " WHERE n.nspname = current_schema() AND c.relkind IN ('r','p','v','m','f')"
            " AND c.relname LIKE 'bot\\_%'"
        )).scalars().all()
        for t in tables:
            full = {p for p in _TABLE_PRIVS if c.execute(
                text("SELECT has_table_privilege('bot_app', :t, :p)"), {"t": t, "p": p}
            ).scalar()}
            out |= {(t, "*", p) for p in full}
            cols = c.execute(text(
                "SELECT attname FROM pg_attribute WHERE attrelid = CAST(:t AS regclass)"
                " AND attnum > 0 AND NOT attisdropped"), {"t": t}).scalars().all()
            for col in cols:
                for p in _COL_PRIVS:
                    if p not in full and c.execute(
                        text("SELECT has_column_privilege('bot_app', :t, :c, :p)"),
                        {"t": t, "c": col, "p": p},
                    ).scalar():
                        out.add((t, col, p))
        seqs = c.execute(text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
            " WHERE n.nspname = current_schema() AND c.relkind = 'S'"
            " AND c.relname LIKE 'bot\\_%'")).scalars().all()
        for s in seqs:
            for p in ("USAGE", "SELECT", "UPDATE"):
                if c.execute(text("SELECT has_sequence_privilege('bot_app', :s, :p)"),
                             {"s": s, "p": p}).scalar():
                    out.add((s, "*", p))
        for (r,) in c.execute(text(  # roles bot_app inherits from (any depth)
            "SELECT rolname FROM pg_roles WHERE rolname <> 'bot_app'"
            " AND pg_has_role('bot_app', oid, 'MEMBER')")):
            out.add(("role", r, "MEMBER"))
        for (o,) in c.execute(text(  # anything bot_app (or a role it is in) owns
            "SELECT c.relname FROM pg_class c WHERE c.relname LIKE 'bot\\_%'"
            " AND pg_has_role('bot_app', c.relowner, 'USAGE')")):
            out.add((o, "*", "OWNER"))
        for (f,) in c.execute(text(  # SECURITY DEFINER code bot_app can call
            "SELECT p.oid::regprocedure::text FROM pg_proc p JOIN pg_namespace n"
            " ON n.oid = p.pronamespace WHERE p.prosecdef AND n.nspname NOT IN"
            " ('pg_catalog','information_schema')"
            " AND has_function_privilege('bot_app', p.oid, 'EXECUTE')")):
            out.add(("function", f, "SECURITY DEFINER"))
        for (d,) in c.execute(text(  # default privileges that would widen future objects
            "SELECT d.defaclobjtype::text FROM pg_default_acl d, aclexplode(d.defaclacl) a"
            " WHERE a.grantee IN (0, (SELECT oid FROM pg_roles WHERE rolname='bot_app'))")):
            out.add(("default_acl", d, "DEFAULT"))
    return out


def test_bot_app_cannot_shadow_or_escape(engine) -> None:  # noqa: F811
    """No TEMP/CREATE on the database, pg_temp last on the role's search_path, no CREATE in
    public, no server-side large-object file I/O, and the API role still has TEMP."""
    with engine.connect() as c:
        q = lambda sql: c.execute(text(sql)).scalar()  # noqa: E731
        assert not q("SELECT has_database_privilege('bot_app', current_database(), 'TEMP')")
        assert not q("SELECT has_database_privilege('bot_app', current_database(), 'CREATE')")
        assert not q("SELECT has_schema_privilege('bot_app', 'public', 'CREATE')")
        assert q("SELECT has_database_privilege(current_user, current_database(), 'TEMP')")
        cfg = q(
            "SELECT s.setconfig FROM pg_db_role_setting s JOIN pg_database d"
            " ON d.oid = s.setdatabase WHERE d.datname = current_database()"
            " AND s.setrole = (SELECT oid FROM pg_roles WHERE rolname = 'bot_app')"
        )
        assert cfg == ["search_path=public, pg_temp"]
        for fn in ("lo_create(oid)", "lo_creat(integer)", "lo_from_bytea(oid,bytea)",
                   "lo_import(text)", "lo_import(text,oid)", "lo_export(oid,text)"):
            assert not q(f"SELECT has_function_privilege('bot_app', '{fn}', 'EXECUTE')"), fn
        attrs = c.execute(text(
            "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolreplication"
            " FROM pg_roles WHERE rolname = 'bot_app'")).one()
        assert not any(attrs)
        c.execute(text("CREATE TEMP TABLE zz_api_temp (x int)"))  # API flows keep TEMP


def test_bot_app_privileges_match_reviewed_allowlist(engine) -> None:  # noqa: F811
    got = actual(engine)
    extra = sorted(got - set(ALLOWLIST))
    missing = sorted(set(ALLOWLIST) - got)
    assert not extra, f"bot_app holds unreviewed privileges: {extra}"
    assert not missing, f"allowlist entries no longer granted (prune them): {missing}"
