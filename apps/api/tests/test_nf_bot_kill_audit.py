"""BOT-KILL-AUDIT: kill switch + write gate + append-only, hash-chained audit.
Own throwaway ingenium_wt_* DB on test PG, alembic-built."""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from app.bots import guard as gd
from app.bots.audit import AuditError, AuditLog, AuditRow, validate

pytestmark = [pytest.mark.no_app_db]

API = Path(__file__).resolve().parents[1]
PORT = os.environ.get("INGENIUM_TEST_PG_PORT", "54339")
HOST = f"127.0.0.1:{PORT}"
ADMIN = f"postgresql://ingenium:ingenium@{HOST}/ingenium_wt_admin"
DB = f"ingenium_wt_botkill_{uuid.uuid4().hex[:12]}"
URL = f"postgresql+psycopg://ingenium:ingenium@{HOST}/{DB}"
REV, DOWN, HEAD = "d8e9f0a1b2c3", "c7d8e9f0a1b2", "f0a1b2c3d4e5"
FP, FP2, OWNER = "fp-prod-a", "fp-prod-b", "owner-1"
H = "a" * 64
ANCHOR = Path(os.environ.get("TMPDIR", "/tmp")) / f"{DB}.anchor"
_GRANTS: dict[int, tuple[Any, str]] = {}


class _Rehearsed:
    """Test stand-in for rehearse.StoreRehearsals: any named rehearsal is fresh and matching
    (the clone suite exercises the real store)."""

    def reserve(self, spec, model, ids, values):
        return None if spec.rehearsal_id else gd.NO_REHEARSAL

    def release(self, spec):
        pass


REH = _Rehearsed()


def fake_owner(sw, a, db, plan, n, actor, rehearsal_id):
    """Test stand-in for the owner-authenticated approval UI: the human signs one Approval
    object once; presenting the same object again replays that one grant."""
    if a.grant_id:
        return a.grant_id
    if id(a) in _GRANTS:
        return _GRANTS[id(a)][1]
    if not a.approver:
        return None
    try:
        gid = sw.create_grant(
            OWNER, db, plan, n, a.level, a.approver, actor, rehearsal_id=rehearsal_id
        )
    except (PermissionError, ValueError):
        return None
    _GRANTS[id(a)] = (a, gid)
    return gid


def _alembic(*args: str) -> str:
    assert DB.startswith("ingenium_wt_") and PORT not in ("54329", "5433", "5436")
    out = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API,
        env={**os.environ, "DATABASE_URL": URL},
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout + out.stderr


@pytest.fixture(scope="module")
def engine():
    with psycopg.connect(ADMIN, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{DB}"')
    try:
        _alembic("upgrade", "head")
        eng = create_engine(URL, poolclass=NullPool)
        yield eng
        eng.dispose()
    finally:
        with psycopg.connect(ADMIN, autocommit=True) as c:
            c.execute(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')


def _clean(engine) -> None:
    """Harness-only reset as the superuser (the app role cannot do this)."""
    with engine.begin() as c:
        c.execute(text("ALTER TABLE bot_audit DISABLE TRIGGER bot_audit_no_update"))
        c.execute(text("DELETE FROM bot_audit"))
        c.execute(text("ALTER TABLE bot_audit ENABLE TRIGGER bot_audit_no_update"))
        for t in ("bot_job", "bot_grant", "bot_cap_override"):
            c.execute(text(f"DELETE FROM {t}"))
        c.execute(text("DELETE FROM bot_kill_switch WHERE scope <> 'global'"))
        c.execute(text("UPDATE bot_kill_switch SET is_on=false WHERE scope='global'"))
    ANCHOR.unlink(missing_ok=True)
    _GRANTS.clear()


@pytest.fixture
def env(engine):
    _clean(engine)
    sw = gd.KillSwitch(engine, lambda scope: OWNER, grant_source=fake_owner)
    return engine, sw, AuditLog(engine, anchor=ANCHOR)


class Rpc:
    def __init__(self, on_call=None) -> None:
        self.calls: list[tuple] = []
        self.on_call = on_call

    def __call__(self, model, method, args, kw=None) -> Any:
        self.calls.append((model, method, args))
        if self.on_call:
            self.on_call(len(self.calls))
        return True


def spec(key: str | None = None, level: int = 1, approver: str | None = None, **kw) -> gd.RunSpec:
    base = dict(
        db_fingerprint=FP,
        task_id="m:res.partner.category:change",
        actor="bot-1",
        risk_class="R1",
        rule_ids="RF-ANY",
        approval=gd.Approval(level, approver),
        idempotency_key=key or uuid.uuid4().hex,
        snapshot_id="snap-1",
        rehearsal_id="rh-1",
    )
    return gd.RunSpec(**{**base, **kw})


class Undo:
    def __init__(self, ok: bool = True) -> None:
        self.images: list[Any] = []
        self.ok = ok

    def __call__(self, image: Any) -> bool:
        self.images.append(image)
        return self.ok


def run(gate, s, ids, *, readback=lambda c: True, undo=None):
    return gate.run(
        s,
        "res.partner.category",
        ids,
        {"name": "x"},
        before_image=lambda c: (f"bi:{c[0]}-{c[-1]}", {"ids": list(c)}),
        readback=readback,
        undo=undo or Undo(),
    )


def rows(engine, key: str) -> list[dict]:
    with engine.connect() as c:
        return [
            dict(r)
            for r in c.execute(
                text("SELECT * FROM bot_audit WHERE idempotency_key=:k ORDER BY id"), {"k": key}
            ).mappings()
        ]


# --------------------------------------------------------------------------- AC1 / AC6
@pytest.mark.parametrize("scope", ["global", FP])
def test_ac1_switch_on_zero_writes(env, scope) -> None:
    engine, sw, log = env
    sw.turn_on(scope, "anyone", "drill")
    rpc = Rpc()
    s = spec()
    rep = run(gd.WriteGate(sw, log, rpc, REH), s, [1, 2, 3])
    assert rep.status == "refused" and rpc.calls == [] and rep.refusal.rule == "RF-ANY"
    with pytest.raises(PermissionError, match="kill switch"):
        gd.WriteGate(sw, log, rpc, REH).call(s, "res.partner", "action_x", [[1]])
    assert rpc.calls == [] and rows(engine, s.idempotency_key)[0]["decision"] == "refused"


def test_ac1_other_db_unaffected(env) -> None:
    _, sw, log = env
    sw.turn_on(FP2, "anyone", "drill")
    rpc = Rpc()
    assert run(gd.WriteGate(sw, log, rpc, REH), spec(), [1, 2]).status == "done"
    assert len(rpc.calls) == 2


def test_ac6_unreadable_or_missing_state_is_on(env) -> None:
    engine, _, log = env
    bad = gd.KillSwitch(create_engine("postgresql+psycopg://x:y@127.0.0.1:1/ingenium_none"), str)
    assert bad.check(FP).missing == "kill-switch-state"
    with engine.begin() as c:
        c.execute(text("DELETE FROM bot_kill_switch WHERE scope='global'"))
    try:
        sw = gd.KillSwitch(engine, lambda s: OWNER)
        rpc = Rpc()
        assert run(gd.WriteGate(sw, log, rpc, REH), spec(), [1]).status == "refused"
        assert rpc.calls == []
    finally:
        with engine.begin() as c:
            c.execute(
                text("INSERT INTO bot_kill_switch VALUES ('global', false, 'r', 'test', now())")
            )


# --------------------------------------------------------------------------- AC2 trip + undo
def test_ac2_readback_mismatch_trips_and_undoes(env) -> None:
    engine, sw, log = env
    u, s = Undo(), spec()
    rep = run(
        gd.WriteGate(sw, log, Rpc(), REH), s, list(range(1, 80)), readback=lambda c: False, undo=u
    )
    assert rep.status == "tripped" and rep.written == 0 and rep.batches == 1
    assert sw.check(FP) is not None and u.images == [{"ids": list(range(1, 51))}]
    assert [r["decision"] for r in rows(engine, s.idempotency_key)] == [
        "intent",
        "tripped",
        "undone",
    ]
    with pytest.raises(PermissionError):
        sw.turn_off(FP, "bot-1", "self-clear")  # the bot cannot clear its own trip
    sw.turn_off(FP, OWNER, "reviewed")
    assert sw.check(FP) is None


# --------------------------------------------------------------------------- AC3 row content
def test_ac3_row_fields(env) -> None:
    engine, sw, log = env
    s = spec(level=2, approver="alice", risk_class="R3")
    run(gd.WriteGate(sw, log, Rpc(), REH), s, [7, 8])
    r = rows(engine, s.idempotency_key)[0]
    assert (r["actor"], r["approver"], r["approval_level"], r["task_id"]) == (
        "bot-1",
        "alice",
        2,
        s.task_id,
    )
    assert re.fullmatch(r"[0-9a-f]{64}", r["diff_hash"]) and r["blast_count"] == 2
    assert (r["snapshot_id"], r["before_image_ref"], r["risk_class"]) == ("snap-1", "bi:7-8", "R3")
    assert {x["blast_count"] for x in rows(engine, s.idempotency_key)} == {2}


def _row(**kw) -> AuditRow:
    base = dict(
        db_fingerprint=FP,
        task_id="t",
        actor="a",
        approval_level=1,
        risk_class="R1",
        rule_ids="",
        diff_hash=H,
        blast_count=1,
        batch_no=1,
        idempotency_key="k",
        decision="intent",
        reason="r",
    )
    return AuditRow(**{**base, **kw})


@pytest.mark.parametrize(
    "kw",
    [
        {"reason": "password=hunter2"},
        {"reason": "api_key: abc"},
        {"task_id": "Bearer: xyz"},
        {"before_image_ref": "token=abc"},
        {"snapshot_id": "a b"},
        {"diff_hash": "not-a-hash"},
        {"risk_class": "R99"},
        {"approval_level": 7},
    ],
)
def test_ac3_rejects_secrets_and_bad_rows(env, kw) -> None:
    with pytest.raises(AuditError):
        validate(_row(**kw))
    with pytest.raises(AuditError):
        env[2].append(_row(**kw))


@pytest.mark.parametrize(
    "secret",
    [
        "password hunter2",
        "Password: hunter2",
        "pwd=x",
        "Bearer abc.def",
        "api key 123",
        "client_secret s3cr3t",
        "token abcdef",
        "ghp_abcdefghijklmnop",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.sig",
        "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo0123456789",
    ],
)
def test_finding4_secret_variants_rejected_and_redacted(secret) -> None:
    from app.bots.audit import REDACTED, redact

    with pytest.raises(AuditError):
        validate(_row(reason=f"note {secret} end"))
    out = redact(f"note {secret} end")
    assert REDACTED in out and validate(_row(reason=out)) is None


def test_finding4_catalogue_ids_with_model_names_allowed() -> None:
    validate(_row(task_id="m:payment.token:change", idempotency_key="k" * 64))


# --------------------------------------------------------------------------- AC4 append-only
@pytest.mark.parametrize(
    "sql",
    ["UPDATE bot_audit SET reason='x'", "DELETE FROM bot_audit", "TRUNCATE bot_audit"],
)
def test_ac4_append_only(env, sql) -> None:
    engine, _, log = env
    log.append(_row(idempotency_key=uuid.uuid4().hex))
    with pytest.raises(Exception, match="append-only"), engine.begin() as c:
        c.execute(text(sql))


def test_ac4_tampered_row_breaks_chain(env) -> None:
    engine, _, log = env
    for _ in range(3):
        log.append(_row(idempotency_key=uuid.uuid4().hex))
    assert log.verify_chain() == (True, None)
    with engine.begin() as c:  # attacker with DDL rights bypasses the trigger
        c.execute(text("ALTER TABLE bot_audit DISABLE TRIGGER bot_audit_no_update"))
        bad = c.execute(text("SELECT max(id) - 1 FROM bot_audit")).scalar()
        c.execute(text("UPDATE bot_audit SET approver='forged' WHERE id=:i"), {"i": bad})
        c.execute(text("ALTER TABLE bot_audit ENABLE TRIGGER bot_audit_no_update"))
    assert log.verify_chain() == (False, bad)


def test_finding3_tail_truncation_detected_by_anchor(env) -> None:
    engine, _, log = env
    for _ in range(3):
        log.append(_row(idempotency_key=uuid.uuid4().hex))
    with engine.begin() as c:
        c.execute(text("ALTER TABLE bot_audit DISABLE TRIGGER bot_audit_no_update"))
        c.execute(text("DELETE FROM bot_audit WHERE id=(SELECT max(id) FROM bot_audit)"))
        c.execute(text("ALTER TABLE bot_audit ENABLE TRIGGER bot_audit_no_update"))
    assert log.verify_chain() == (False, -1)  # chain itself is still internally valid


def test_finding3_anchor_unwritable_no_row_no_write(env, tmp_path) -> None:
    engine, sw, _ = env
    d = tmp_path / "ro"
    d.mkdir()
    d.chmod(0o500)
    rpc = Rpc()
    try:
        log = AuditLog(engine, anchor=d / "x" / "a.anchor")
        assert run(gd.WriteGate(sw, log, rpc, REH), spec(), [1]).status == "refused"
    finally:
        d.chmod(0o700)
    assert rpc.calls == []
    with engine.connect() as c:
        q = "SELECT count(*) FROM bot_audit WHERE decision='intent'"
        assert c.execute(text(q)).scalar() == 0


def test_finding3_app_role_cannot_alter_or_rewrite(env) -> None:
    engine = env[0]
    role, pw = f"ingenium_wt_botapp_{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD '{pw}' IN ROLE bot_app"))
    app = create_engine(f"postgresql+psycopg://{role}:{pw}@{HOST}/{DB}", poolclass=NullPool)
    try:
        log = AuditLog(app, anchor=ANCHOR)
        log.append(_row(idempotency_key=uuid.uuid4().hex))  # INSERT allowed
        for sql in (
            "ALTER TABLE bot_audit DISABLE TRIGGER bot_audit_no_update",
            "UPDATE bot_audit SET reason='x'",
            "DELETE FROM bot_audit",
            "TRUNCATE bot_audit",
            "DROP TRIGGER bot_audit_no_update ON bot_audit",
        ):
            with pytest.raises(DBAPIError), app.begin() as c:
                c.execute(text(sql))
        with app.connect() as c:
            assert c.execute(text("SELECT count(*) FROM bot_audit")).scalar() == 1
    finally:
        app.dispose()
        with engine.begin() as c:
            c.execute(text(f"DROP ROLE {role}"))


# --------------------------------------------------------------------------- AC5 idempotency
def test_ac5_same_key_twice_is_duplicate(env) -> None:
    engine, sw, log = env
    rpc, s = Rpc(), spec()
    assert run(gd.WriteGate(sw, log, rpc, REH), s, [1, 2]).status == "done"
    assert run(gd.WriteGate(sw, log, rpc, REH), s, [1, 2]).status == "duplicate"
    assert len(rpc.calls) == 2
    assert [r["decision"] for r in rows(engine, s.idempotency_key)] == [
        "intent",
        "applied",
        "checkpoint",
        "duplicate",
    ]


def test_chaos_concurrent_same_key_writes_once(env) -> None:
    engine, sw, log = env
    rpc, s = Rpc(), spec()
    out: list[str] = []
    ts = [
        threading.Thread(
            target=lambda: out.append(run(gd.WriteGate(sw, log, rpc, REH), s, [1]).status)
        )
        for _ in range(6)
    ]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(out) == ["done"] + ["duplicate"] * 5 and len(rpc.calls) == 1
    assert log.verify_chain()[0]


# --------------------------------------------------------------------------- kill races
def test_chaos_kill_between_batches(env) -> None:
    engine, sw, log = env
    rpc, s = Rpc(), spec()

    def rb(chunk) -> bool:
        sw.turn_on(FP, OWNER, "stop after batch 1")
        return True

    rep = run(gd.WriteGate(sw, log, rpc, REH), s, list(range(120)), readback=rb)
    assert (rep.status, rep.written, rep.batches, len(rpc.calls)) == ("partial", 50, 1, 50)
    assert rows(engine, s.idempotency_key)[-1]["decision"] == "killed"


def test_chaos_kill_in_flight_stops_and_undoes(env) -> None:
    engine, sw, log = env
    u, s = Undo(), spec()
    rpc = Rpc(on_call=lambda n: n == 3 and sw.turn_on(FP, "ops", "panic"))
    rep = run(gd.WriteGate(sw, log, rpc, REH), s, list(range(10)), undo=u)
    assert rep.status == "partial" and len(rpc.calls) == 3 and rep.written == 0
    assert u.images == [{"ids": list(range(10))}]
    assert [r["decision"] for r in rows(engine, s.idempotency_key)][-2:] == ["killed", "undone"]


def test_chaos_audit_drop_refuses_write(env) -> None:
    _, sw, _ = env

    class Dropped(AuditLog):
        def append(self, row):
            raise AuditError("audit write failed: OperationalError")

    rpc = Rpc()
    rep = run(gd.WriteGate(sw, Dropped(None), rpc, REH), spec(), [1, 2])
    assert rep.status == "refused" and rpc.calls == []
    assert sw.check(FP) is not None  # lost audit row trips the DB switch
    with pytest.raises(AuditError):  # fresh DB: the intent row itself cannot be written
        gd.WriteGate(sw, Dropped(None), rpc, REH).call(
            spec(db_fingerprint=FP2), "res.partner", "write", [[1], {}]
        )
    assert rpc.calls == []


def test_chaos_post_write_audit_loss_trips_switch(env) -> None:
    engine, sw, log = env

    class LoseApplied(AuditLog):
        def append(self, row):
            if row.decision == "applied":
                raise AuditError("lost")
            return super().append(row)

    run(gd.WriteGate(sw, LoseApplied(engine), Rpc(), REH), spec(), [1])
    assert sw.check(FP) is not None


# --------------------------------------------------------------------------- caps / approvals
def test_caps_batching_and_tighten_only(env) -> None:
    engine, sw, log = env
    rpc = Rpc()
    rep = run(gd.WriteGate(sw, log, rpc, REH), spec(), list(range(120)))
    assert (rep.batches, rep.written) == (3, 120)
    sw.set_caps(FP, OWNER, 10, 100)
    rep = run(gd.WriteGate(sw, log, Rpc(), REH), spec(), list(range(25)))
    assert rep.batches == 3
    for b, r in ((51, 500), (50, 501), (0, 10)):
        with pytest.raises(ValueError):
            sw.set_caps(FP, OWNER, b, r)
    with pytest.raises(PermissionError):
        sw.set_caps(FP, "bot-1", 5, 5)
    with pytest.raises(Exception, match="tighten_only"), engine.begin() as c:
        c.execute(
            text("UPDATE bot_cap_override SET batch_cap=500 WHERE db_fingerprint=:d"), {"d": FP}
        )


def test_caps_dedup_ids_cannot_inflate_or_dodge(env) -> None:
    _, sw, log = env
    rpc = Rpc()
    rep = run(gd.WriteGate(sw, log, rpc, REH), spec(), [1] * 600)
    assert rep.total == 1 and len(rpc.calls) == 1


@pytest.mark.parametrize(
    ("level", "approver", "ok"),
    [
        (1, None, False),
        (2, "alice", False),
        (3, None, False),
        (3, "bot-1", False),
        (3, "alice", True),
    ],
)
def test_run_cap_needs_l3_distinct_approver(env, level, approver, ok) -> None:
    engine, sw, log = env
    rpc, s = Rpc(), spec(level=level, approver=approver)
    rep = run(gd.WriteGate(sw, log, rpc, REH), s, list(range(501)))
    assert (rep.status == "done") is ok and (len(rpc.calls) == 501) is ok
    assert "run_cap" in rows(engine, s.idempotency_key)[0]["caps_hit"]


def test_risk_class_tier_enforced(env) -> None:
    _, sw, log = env
    rpc = Rpc()
    assert run(gd.WriteGate(sw, log, rpc, REH), spec(risk_class="R8"), [1]).status == "refused"
    ok = spec(risk_class="R8", level=3, approver="alice")
    assert run(gd.WriteGate(sw, log, rpc, REH), ok, [1]).status == "done"


# --------------------------------------------------------------------------- owner-only
def test_owner_only_controls(engine) -> None:
    sw = gd.KillSwitch(engine, lambda s: (_ for _ in ()).throw(RuntimeError("lookup down")))
    sw.turn_on(FP, "anyone", "on is always allowed")
    with pytest.raises(PermissionError):
        sw.turn_off(FP, OWNER, "lookup failure denies")
    with pytest.raises(PermissionError):
        gd.KillSwitch(engine, lambda s: None).turn_off(FP, "", "no owner")
    gd.KillSwitch(engine, lambda s: OWNER).turn_off(FP, OWNER, "ok")


RPC_COPY = API / "app" / "bots" / "clone" / "rpc_copy.py"
WRAPPER = "_guarded_execute_kw"


def test_rpc_copy_execute_kw_pinned_to_guarded_wrapper() -> None:
    """BOT-CLONE-REHEARSAL exemption: exactly one execute_kw, inside the wrapper, whose first
    statement is the copy-proof check; only rehearse.py imports rpc_copy under app/bots."""
    import ast

    tree = ast.parse(RPC_COPY.read_text())
    funcs = {n: f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) for n in [f.name]}
    hits = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and n.value == "execute_kw"]
    names = [n for n in ast.walk(tree) if isinstance(n, ast.Name | ast.Attribute)]
    assert not [n for n in names if getattr(n, "id", getattr(n, "attr", "")) == "execute_kw"]
    assert len(hits) == 1
    w = funcs[WRAPPER]
    assert hits[0] in list(ast.walk(w))
    first = (
        w.body[1]
        if isinstance(w.body[0], ast.Expr) and isinstance(w.body[0].value, ast.Constant)
        else w.body[0]
    )
    call = first.value
    assert isinstance(call, ast.Call) and call.func.attr == "_require_proof"
    assert [a.id for a in call.args] == ["model", "method", "args"]
    rq = funcs["_require_proof"]
    assert any(isinstance(n, ast.Raise) for n in ast.walk(rq))
    bots = API / "app" / "bots"
    for p in (API / "app").rglob("*.py"):  # all of app/, not only app/bots
        if p in (RPC_COPY, bots / "clone" / "rehearse.py"):
            continue
        t = ast.parse(p.read_text())
        mods = [m.module or "" for m in ast.walk(t) if isinstance(m, ast.ImportFrom)]
        mods += [a.name for m in ast.walk(t) if isinstance(m, ast.Import) for a in m.names]
        if p in (bots / "clone" / "fingerprint.py", bots / "clone" / "neutralize.py"):
            imp = [m for m in ast.walk(t) if isinstance(m, ast.ImportFrom)]
            imp = [m for m in imp if "rpc_copy" in (m.module or "")]
            assert imp and all([a.name for a in m.names] == ["rpc_write"] for m in imp), p
            mods = [m for m in mods if "rpc_copy" not in m]
        assert not [m for m in mods if "rpc_copy" in m], p
        used = {getattr(n, "attr", getattr(n, "id", "")) for n in ast.walk(t)}
        assert not used & {WRAPPER, "JsonRpc", "_PROOF_KEY", "_mac", "_require_proof"}, p
        if bots in p.parents:  # app/ outside bots has its own (non-prod-gated) RPC clients
            assert "execute_kw" not in used and "execute_kw" not in p.read_text(), p


BEFORE_IMAGE = API / "app" / "bots" / "before_image.py"
# Allow-list (round 9): an RPC-shaped call passes only with a LITERAL method from this set;
# any other name, or a method held in a variable, is flagged. RPC clients are also found by
# binding (import of an RPC library, construction of a client, transitively re-bound), by call
# shape ("model.name", "method", ...) under any callee, by RPC endpoint/payload literals and by
# HTTP sends whose URL is not a literal; the exempt files are pinned separately.
_RPC_READS = frozenset(
    {
        "read",
        "search",
        "onchange",  # computed in memory, never stored
        "search_read",
        "search_count",
        "search_fetch",
        "fields_get",
        "read_group",
        "name_search",
        "name_get",
        "check_access_rights",
        "check_access",
        "has_access",
        "default_get",
        "get_views",
        "load_views",
        "context_get",
        "get_metadata",
        "web_search_read",
        "web_read",
        "web_read_group",
        "exists",
    }
)
# callee names used for RPC clients taking (model, method, ...)
_RPC_CALLEES = frozenset({"rpc", "_rpc", "call", "_call", "call_kw", "read", "_r", "_dry"})
# names that are RPC entry points or write methods by themselves
_RPC_NAMES = frozenset(
    {"execute_kw", "call_kw", "execute", "write", "create", "unlink", "copy", "set_values"}
    | {"button_immediate_install", "button_immediate_upgrade", "button_immediate_uninstall"}
    | {"name_create", "action_post", "action_confirm", "toggle_active", "action_archive"}
)
# write method names flagged as a literal 2nd positional whatever the callee
_RPC_WRITES = frozenset(
    {"write", "create", "unlink", "execute", "set_values", "copy", "button_immediate_install"}
    | {"button_immediate_upgrade", "button_immediate_uninstall"}
)
# methods that write when called directly on a record/proxy, e.g. wiz.set_values()
_RPC_WRITE_ATTRS = frozenset(
    {"execute_kw", "call_kw", "set_values", "button_immediate_install", "button_immediate_upgrade"}
    | {"button_immediate_uninstall"}
)


_METHOD_RE = re.compile(r"_?[a-z][a-z0-9_]*")
_MODEL_RE = re.compile(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+)+")


def _is_read(a: ast.AST) -> bool:
    return isinstance(a, ast.Constant) and a.value in _RPC_READS


def _const_set(node: ast.AST | None, consts: dict[str, ast.AST]) -> set | None:
    """The string members of a literal set/list/tuple/frozenset(...) (or a module-level name
    bound to one); None when not statically known."""
    if isinstance(node, ast.Name):
        node = consts.get(node.id)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("frozenset", "set", "tuple")
        and len(node.args) == 1
    ):
        node = node.args[0]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        a, b = _const_set(node.left, consts), _const_set(node.right, consts)
        return None if a is None or b is None else a | b
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        vals = [e.value for e in node.elts if isinstance(e, ast.Constant)]
        return set(vals) if len(vals) == len(node.elts) else None
    return None


def _guarded_names(fn: ast.AST, consts: dict[str, ast.AST] | None = None) -> set[str]:
    """Names a function refuses unless allow-listed: `if v not in SET: raise ...`, where SET
    is statically known and holds read methods only (a set naming any write is no guard)."""
    out = set()
    for n in ast.walk(fn):
        t = n.test if isinstance(n, ast.If) else None
        if (
            isinstance(t, ast.Compare)
            and isinstance(t.left, ast.Name)
            and [type(o) for o in t.ops] == [ast.NotIn]
            and n.body
            and isinstance(n.body[0], ast.Raise)
        ):
            members = _const_set(t.comparators[0], consts or {})
            if members is not None and members <= _RPC_READS:
                out.add(t.left.id)
    return out


# modules whose import or construction makes an RPC client, under whatever name it is bound
_RPC_MODULES = ("xmlrpc", "odoorpc", "jsonrpc", "jsonrpclib", "odoo_rpc", "odoolib", "erppeek")
_RPC_CTORS = frozenset({"ServerProxy", "ODOO", "Client", "OdooClient", "Connection"})
_RPC_URL_MARKS = ("/jsonrpc", "/xmlrpc", "/web/dataset/call", "/json/2/", "execute_kw", "call_kw")
_HTTP_LIBS = frozenset({"requests", "httpx", "urllib", "urllib3", "http", "aiohttp"})
_HTTP_SENDS = frozenset({"post", "put", "patch", "request", "urlopen", "Request", "send"})


def _http_send(n: ast.Call, http: set[str]) -> bool:
    """requests/httpx/urllib send (post/put/patch/request/urlopen) whose URL is not a literal
    free of RPC paths: the endpoint is unknown, so it may be /jsonrpc or /xmlrpc."""
    f = n.func
    if not (isinstance(f, ast.Attribute) and f.attr in _HTTP_SENDS and _rooted_in(f, http)):
        return False
    url = n.args[0] if n.args else next((k.value for k in n.keywords if k.arg == "url"), None)
    if f.attr == "request" and len(n.args) >= 2:
        url = n.args[1]
    return not (isinstance(url, ast.Constant) and isinstance(url.value, str))


def _client_names(tree: ast.AST) -> set[str]:
    """Names bound to an RPC client: from an RPC module import, or assigned the result of an
    RPC client constructor (ServerProxy(...), odoorpc.ODOO(...), ...), transitively."""
    names: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] in _RPC_MODULES:
            names |= {a.asname or a.name for a in n.names}
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] in _RPC_MODULES:
                    names.add((a.asname or a.name).split(".")[0])
    changed = True
    while changed:
        changed = False
        for n in ast.walk(tree):
            if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                v = n.value
                base = v.func if isinstance(v, ast.Call) else v
                while isinstance(base, (ast.Attribute, ast.Call)):
                    if isinstance(base, ast.Attribute) and base.attr in _RPC_CTORS:
                        break
                    base = base.value if isinstance(base, ast.Attribute) else base.func
                hit = (isinstance(base, ast.Name) and base.id in names | _RPC_CTORS) or (
                    isinstance(base, ast.Attribute) and base.attr in _RPC_CTORS
                )
                if not hit:
                    continue
                tgts = n.targets if isinstance(n, ast.Assign) else [n.target]
                for t in tgts:
                    key = t.id if isinstance(t, ast.Name) else getattr(t, "attr", None)
                    if key and key not in names:
                        names.add(key)
                        changed = True
    return names


def _rooted_in(f: ast.AST, names: set[str]) -> bool:
    while isinstance(f, (ast.Attribute, ast.Call, ast.Subscript)):
        if isinstance(f, ast.Attribute) and f.attr in names:
            return True
        f = f.func if isinstance(f, ast.Call) else f.value
    return isinstance(f, ast.Name) and f.id in names


def _is_gate_call(f: ast.AST) -> bool:
    """x.gate.call(...): the guarded write path (guard.py), approval-checked and pinned."""
    return (
        isinstance(f, ast.Attribute)
        and f.attr == "call"
        and isinstance(f.value, ast.Attribute)
        and f.value.attr == "gate"
    )


def rpc_write_calls(src: str, passthrough: frozenset[str] = frozenset()) -> list[int]:
    """Lines of possible Odoo RPC writes (allow-list). Flagged:
    - any "execute_kw" / "call_kw" string literal, and execute_kw / call_kw / set_values /
      button_immediate_* called as a method;
    - getattr(x, "<rpc name>") with a literal RPC entry point or write method;
    - a call passing a literal RPC write name 2nd positional, whatever the callee;
    - an RPC-shaped call whose method is not a literal read method. RPC-shaped: XML-RPC
      object.execute(db, uid, pw, model, method, ...) (method 5th); a method= keyword; or a
      2nd positional on a known RPC callee name (rpc, call, read, _r, ...).
    A non-literal method passes only inside a function that first refuses it unless
    allow-listed (`if method not in READS: raise`), or in a function named in `passthrough`
    (pinned per file by the caller). x.gate.call(...) is the guarded path and not flagged.
    Path.unlink(), cursor.execute(sql) and file writes are not RPC-shaped."""
    tree = ast.parse(src)
    consts = {
        t.id: n.value
        for n in getattr(tree, "body", [])
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
    }
    clients = _client_names(tree)
    # plain record classes of this file (dataclass, no methods): constructing one is data
    records = {
        c.name
        for c in ast.walk(tree)
        if isinstance(c, ast.ClassDef)
        and any("dataclass" in ast.unparse(d) for d in c.decorator_list)
        and not any(isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) for b in c.body)
    }
    http = set(_HTTP_LIBS)
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                root = ((n.module or "") if isinstance(n, ast.ImportFrom) else a.name).split(".")[0]
                if root in _HTTP_LIBS:
                    http.add((a.asname or a.name).split(".")[0])
    for _ in range(3):  # sessions/clients bound from an HTTP library: s = requests.Session()
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
                if _rooted_in(n.value.func, http):
                    http |= {t.id for t in n.targets if isinstance(t, ast.Name)}
                    http |= {t.attr for t in n.targets if isinstance(t, ast.Attribute)}
    ctx: dict[int, tuple[str, set[str]]] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            g = _guarded_names(fn, consts)
            for n in ast.walk(fn):
                ctx[id(n)] = (fn.name, g)  # innermost wins: inner defs are walked later
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            mods = [n.module or ""] if isinstance(n, ast.ImportFrom) else [a.name for a in n.names]
            if any(m.split(".")[0] in _RPC_MODULES for m in mods):
                out.add(n.lineno)  # an RPC client library, whatever it is bound to
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if any(k in n.value for k in _RPC_URL_MARKS):
                out.add(n.lineno)  # RPC endpoint, e.g. requests.post(url + "/jsonrpc")
        if isinstance(n, ast.Dict) and any(
            isinstance(k, ast.Constant) and k.value == "jsonrpc" for k in n.keys
        ):
            out.add(n.lineno)  # a JSON-RPC envelope {"jsonrpc": "2.0", ...}
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        attr = f.attr if isinstance(f, ast.Attribute) else ""
        name = attr or (f.id if isinstance(f, ast.Name) else "")
        if attr in _RPC_WRITE_ATTRS:
            out.add(n.lineno)
            continue
        if name == "getattr" and len(n.args) >= 2:
            a = n.args[1]
            if isinstance(a, ast.Constant) and a.value in _RPC_NAMES:
                out.add(n.lineno)
            continue
        if _is_gate_call(f):
            continue
        if _http_send(n, http):
            out.add(n.lineno)
            continue
        if name in _RPC_CTORS or (clients and _rooted_in(f, clients)):
            out.add(n.lineno)  # constructing or calling an RPC client: by name or binding
            continue
        second = n.args[1] if len(n.args) >= 2 else None
        if isinstance(second, ast.Constant) and second.value in _RPC_WRITES:
            out.add(n.lineno)
            continue
        methods = [k.value for k in n.keywords if k.arg == "method"]
        if attr == "execute" and len(n.args) >= 5:
            methods.append(n.args[4])
        elif second is not None and name in _RPC_CALLEES:
            methods.append(second)
        elif (
            isinstance(second, ast.Constant)
            and isinstance(second.value, str)
            and _METHOD_RE.fullmatch(second.value)
            and name not in records
            and isinstance(n.args[0], ast.Constant)
            and isinstance(n.args[0].value, str)
            and _MODEL_RE.fullmatch(n.args[0].value)
        ):
            methods.append(second)  # (model, method, ...) call shape, under any callee name
        fname, guarded = ctx.get(id(n), ("", set()))
        for m in methods:
            if _is_read(m):
                continue
            if isinstance(m, ast.Name) and (m.id in guarded or fname in passthrough):
                continue
            if isinstance(m, ast.Attribute) and fname in passthrough:
                continue
            out.add(n.lineno)
    return sorted(out)


# Non-literal pass-throughs that are read-only by construction, pinned per file (see
# test_read_passthroughs_route_to_read_only_wrappers).
READ_PASSTHROUGH = {
    "configverify.py": frozenset({"_r"}),  # self.call = read_only(call)
    "walker.py": frozenset({"call"}),  # _Port.call -> self.read: df.ReadOnly
    "posting.py": frozenset({"plan"}),  # Step(method=op.method): op from OPS, walked via gate
}


def test_no_raw_rpc_writes_in_bots() -> None:
    bots = API / "app" / "bots"
    # each pinned separately (sinkhole.py: tests/test_nf_bot_sinkhole.py AST pin)
    exempt = {bots / "guard.py", RPC_COPY, BEFORE_IMAGE, bots / "sinkhole.py"}
    hits = [
        p
        for p in bots.rglob("*.py")
        if p not in exempt
        and rpc_write_calls(p.read_text(), READ_PASSTHROUGH.get(p.name, frozenset()))
    ]
    assert hits == []


def test_sandbox_harness_exempt_only_by_sha_pin() -> None:
    import hashlib

    from app.bots import module_test_gate as mtg

    root = API / "app" / "sandbox_harness"
    smoke = root / "smoke.py"
    assert hashlib.sha256(smoke.read_bytes()).hexdigest() == mtg.SMOKE_HARNESS_SHA256
    assert rpc_write_calls(smoke.read_text())  # it does call execute_kw: exempt by pin only
    hits = [p for p in root.rglob("*.py") if p != smoke and rpc_write_calls(p.read_text())]
    assert hits == []


def test_read_passthroughs_route_to_read_only_wrappers() -> None:
    bots = API / "app" / "bots"
    assert "self.call = read_only(call)" in (bots / "configverify.py").read_text()
    assert "def __init__(self, read: df.ReadOnly)" in (bots / "walker.py").read_text()
    post = (bots / "posting.py").read_text()
    assert 'wk.Step("call", op.model, ids, method=op.method)' in post
    assert "op = OPS.get(op_name)" in post
    # the pins are needed (each forwards a non-literal method) and nothing else is pinned
    for name, fns in READ_PASSTHROUGH.items():
        path = next(bots.rglob(name))
        assert rpc_write_calls(path.read_text()), name
        assert rpc_write_calls(path.read_text(), fns) == [], name


@pytest.mark.parametrize(
    "src",
    [
        "rpc('res.partner', 'message_post', [[1]])",  # not a known write: still not a read
        "rpc(model, method, [[1]])",  # non-literal method
        "call(m, 'action_confirm', [[1]])",
        "c(model=m, method=meth, args=[[1]])",
        "proxy.execute(db, uid, pw, 'res.partner', name, [1])",
        "s = 'execute_kw'",
        "f = getattr(proxy, 'execute_kw')",
        "getattr(rec, 'unlink')()",
        "x.call_kw(m, 'read', [])",
        "import xmlrpc.client as xc",
        "from odoorpc import ODOO as O",
        "p = ServerProxy(u)\nq = p\nq.anything(1, 2)",
        "import odoorpc\nc = odoorpc.ODOO('h')\nc.env",
        "lookup('res.partner', 'archive_all', [[1]])",  # any callee, (model, method) shape
        "requests.post(base + '/jsonrpc', json=b)",
        "import requests as r\nr.post(url, json=b)",  # endpoint unknown
        "import httpx\ns = httpx.Client()\ns.post(u, json=b)",
        "body = {'jsonrpc': '2.0', 'params': p}",
        "urllib.request.urlopen(req)",
        # a guard naming a write method is no guard
        "def f(m):\n    if m not in {'read', 'write'}:\n        raise E\n    rpc(x, m)",
        "W = frozenset({'read', 'unlink'})\n"
        "def f(m):\n    if m not in W:\n        raise E\n    rpc(x, m)",
        "def f(m, S):\n    if m not in S:\n        raise E\n    rpc(x, m)",  # unknown set
    ],
)
def test_rpc_allow_list_flags_unknown_and_non_literal(src) -> None:
    hits = rpc_write_calls(src)
    assert hits and (hits == [1] or "\n" in src), src


def test_rpc_allow_list_guarded_non_literal_passes() -> None:
    src = (
        "READS = frozenset({'read', 'search_read'})\n"
        "def ro(model, method, args):\n"
        "    if method not in READS:\n"
        "        raise PermissionError(method)\n"
        "    return rpc(model, method, args)\n"
    )
    assert rpc_write_calls(src) == []
    assert rpc_write_calls(src.replace("not in READS", "in READS")) == [5]
    assert rpc_write_calls("x.gate.call(s, m, 'write', [[1], {}])") == []
    assert rpc_write_calls("getattr(self, 'name')") == []


def test_rpc_write_detector_regression(tmp_path) -> None:
    assert rpc_write_calls("from pathlib import Path\nPath('x').unlink(missing_ok=True)") == []
    assert rpc_write_calls("open('f','w').write('x')") == []
    assert rpc_write_calls("rpc('res.partner', 'unlink', [[1]])") == [1]
    assert rpc_write_calls("x.execute_kw(db, 1, 'pw', 'm', 'read', [])") == [1]
    assert rpc_write_calls("self.write(self.model, 'write', [[1], {}], None)") == [1]
    assert rpc_write_calls("c(model=m, method='create', args=[{}])") == [1]
    bad = API / "app" / "bots" / "zz_regression_probe.py"
    try:
        bad.write_text("def f(rpc):\n    rpc('res.partner', 'unlink', [[1]])\n")
        with pytest.raises(AssertionError):
            test_no_raw_rpc_writes_in_bots()
    finally:
        bad.unlink()
    assert rpc_write_calls((API / "app" / "bots" / "snapshot.py").read_text()) == []


@pytest.mark.parametrize(
    "src",
    [
        "rpc('res.config.settings', 'execute', [[7]])",
        "rpc('res.config.settings', 'set_values', [[7]])",
        "rpc('ir.module.module', 'button_immediate_install', [[3]])",
        "c(model=m, method='execute', args=[[1]])",
        "c(model=m, method='button_immediate_install', args=[[1]])",
        "proxy.execute(db, uid, pw, 'res.partner', 'write', [1], {})",
        "proxy.execute(db, uid, pw, 'ir.module.module', 'button_immediate_install', [3])",
        "wiz.set_values()",
        "mod.button_immediate_install()",
        "x.execute_kw(db, 1, 'pw', 'm', 'search', [])",
    ],
)
def test_rpc_write_detector_catches_each_write_shape(src) -> None:
    assert rpc_write_calls(src) == [1], src


@pytest.mark.parametrize(
    "src",
    [
        "cur.execute('select 1')",
        "conn.execute(stmt, params)",
        "proxy.execute(db, uid, pw, 'res.partner', 'read', [1])",
        "rpc('res.partner', 'read', [[1]])",
        "c(model=m, method='search_read', args=[[]])",
        "Path('x').unlink()",
        "requests.get(u)",
        "requests.post('https://api.example.com/v1/x', json=b)",  # literal, non-RPC endpoint
        "import os\nos.write(1, b'')",
        "s = 'xmlrpc.client'",  # a module name as data, not an import
        "d = {'rpc': ('jsonrpc',)}",
        "lookup('res.partner', 'search_read', [[]])",
    ],
)
def test_rpc_write_detector_ignores_reads_and_sql(src) -> None:
    assert rpc_write_calls(src) == [], src


def test_before_image_writes_pinned_behind_gate_and_kill_switch() -> None:
    tree = ast.parse(BEFORE_IMAGE.read_text())
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    owner = {}
    for name, fn in fns.items():
        for line in rpc_write_calls(ast.unparse(fn)):
            owner.setdefault(name, []).append(line)
    assert set(owner) == {"_write_one"} and len(owner["_write_one"]) == 1
    body = [b for b in fns["_write_one"].body if not isinstance(b, ast.Expr)]
    first = body[0]
    assert isinstance(first, ast.If) and "self._halted(" in ast.unparse(first.test)

    def callers(target: str) -> dict[str, list[ast.AST]]:
        out: dict[str, list[ast.AST]] = {}
        for name, fn in fns.items():
            for n in ast.walk(fn):
                if isinstance(n, ast.Attribute) and n.attr == target and name != target:
                    out.setdefault(name, []).append(n)
        return out

    w = callers("_write_one")
    assert set(w) == {"_prove", "_undo_result"}
    for name in w:  # per record: every call sits inside a for loop
        loops = [n for n in ast.walk(fns[name]) if isinstance(n, ast.For)]
        inside = {id(x) for lp in loops for x in ast.walk(lp)}
        assert all(id(c) in inside for c in w[name])
    assert set(callers("_prove")) == {"readback"}
    assert set(callers("_undo_result")) == {"undo", "_prove"}
    hooks = ast.unparse(fns["hooks"])
    assert "self.readback" in hooks and "self.undo" in hooks
    bots = API / "app" / "bots"
    for p in (API / "app").rglob("*.py"):
        if p in (BEFORE_IMAGE, bots / "guard.py"):
            continue
        used = {n.attr for n in ast.walk(ast.parse(p.read_text())) if isinstance(n, ast.Attribute)}
        assert not used & {"_write_one", "_prove", "_undo_result"}, p
        if bots in p.parents:  # hooks reach guard only via hooks(); routers have unrelated .undo
            assert not used & {"readback", "undo"}, p


# --------------------------------------------------------------------------- AC7
def test_ac7_migration_round_trip(engine) -> None:
    assert re.search(rf"\b{HEAD}\b \(head\)", _alembic("heads"))
    _alembic("downgrade", DOWN)
    with engine.connect() as c:
        assert c.execute(text("SELECT to_regclass('bot_audit')")).scalar() is None
    _alembic("upgrade", "head")
    assert HEAD in _alembic("current")


# --------------------------------------------------------------------------- jobs (pacing)
def test_job_1200_approved_plan_completes_with_checkpoints(env) -> None:
    engine, sw, log = env
    rpc, s = Rpc(), spec(level=3, approver="alice")
    rep = run(gd.WriteGate(sw, log, rpc, REH), s, list(range(1200)))
    assert (rep.status, rep.written, rep.batches, rep.checkpoints) == ("done", 1200, 24, 3)
    assert len(rpc.calls) == 1200 and log.verify_chain() == (True, None)


def test_job_new_keys_cannot_exceed_or_extend_plan(env) -> None:
    _, sw, log = env
    rpc = Rpc()
    out = [
        run(gd.WriteGate(sw, log, rpc, REH), spec(), list(range(1, 401))).status for _ in range(3)
    ]
    assert out == ["done", "duplicate", "duplicate"] and len(rpc.calls) == 400


def test_job_new_plan_needs_new_grant_single_use(env) -> None:
    _, sw, log = env
    rpc, ids = Rpc(), list(range(600))
    a = gd.Approval(3, "alice")
    assert run(gd.WriteGate(sw, log, rpc, REH), spec(approval=a), ids).status == "done"
    bigger = [*ids, 600]  # a different plan presenting the same (used) grant
    assert run(gd.WriteGate(sw, log, rpc, REH), spec(approval=a), bigger).status == "refused"
    assert len(rpc.calls) == 600


def test_job_total_never_exceeds_n(env) -> None:
    engine, sw, log = env
    from app.bots.audit import CapError

    row = _row(job_id="j1", n_records=30, idempotency_key="a")
    assert log.claim(row, job_cap=50)
    with pytest.raises(CapError):
        log.claim(_row(job_id="j1", n_records=30, batch_no=2, idempotency_key="b"), job_cap=50)


@pytest.mark.parametrize("bad", ["n", "db", "level", "approver", "expired", "used"])
def test_grant_binding(env, bad) -> None:
    engine, sw, log = env
    ids = list(range(501))
    plan = gd.plan_hash(FP, spec().task_id, "res.partner.category", {"name": "x"}, ids)
    args = dict(
        owner=OWNER,
        db=FP,
        plan=plan,
        n_records=501,
        level=3,
        approver="alice",
        bot_actor="bot-1",
        rehearsal_id="rh-1",
    )
    args.update(
        {
            "n": {"n_records": 502},
            "db": {"db": FP2},
            "level": {"level": 2},
            "expired": {"ttl_s": -1},
        }.get(bad, {})
    )
    gid = sw.create_grant(**args)
    if bad == "used":
        with engine.begin() as c:
            c.execute(text("UPDATE bot_grant SET used_at=now() WHERE id=:g"), {"g": gid})
    who = "mallory" if bad == "approver" else "alice"
    rpc = Rpc()
    rep = run(gd.WriteGate(sw, log, rpc, REH), spec(approval=gd.Approval(3, who, gid)), ids)
    assert rep.status == "refused" and rpc.calls == []


def test_grant_only_by_owner_and_never_the_bot(env) -> None:
    _, sw, _ = env
    for who, approver in (("bot-1", "alice"), (OWNER, "\uff42\uff4f\uff54-1"), (OWNER, " Bot-1 ")):
        with pytest.raises(PermissionError):
            sw.create_grant(who, FP, H, 1, 3, approver, "bot-1", rehearsal_id="rh-1")


def test_checkpoint_failure_undoes_segment(env) -> None:
    _, sw, log = env
    u = Undo()
    rep = run(
        gd.WriteGate(sw, log, Rpc(), REH),
        spec(level=3, approver="alice"),
        list(range(600)),
        readback=lambda c: len(c) <= 50,
        undo=u,
    )
    assert rep.status == "tripped" and rep.checkpoints == 0 and len(u.images) == 10
    assert sw.check(FP) is not None


# --------------------------------------------------------------------------- reviewer kill1 probes


def go(gate, s, ids, readback=lambda c: True, undo=None):
    return gate.run(
        s,
        "res.partner.category",
        ids,
        {"name": "x"},
        before_image=lambda c: ("bi-1", list(c)),
        readback=readback,
        undo=undo or Undo(),
    )


def G(env, rpc=None):
    e, sw, al = env
    r = rpc or Rpc()
    return gd.WriteGate(sw, al, r, REH), r, sw, al, e


def cnt(e, where="true"):
    with e.connect() as c:
        return c.execute(text(f"SELECT count(*) FROM bot_audit WHERE {where}")).scalar()


# fail-closed
def test_rv1_p01_audit_unwritable_no_write(env):
    g, r, sw, al, e = G(env)

    class Bad(AuditLog):
        def append(self, row):
            raise AuditError("x")

    g.audit = Bad(e)
    rep = go(g, spec(), [1, 2])
    assert r.calls == [] and rep.status in ("refused", "partial")


def test_rv1_p02_call_audit_unwritable_no_write(env):
    g, r, sw, al, e = G(env)

    class Bad(AuditLog):
        def append(self, row):
            raise AuditError("x")

    g.audit = Bad(e)
    with pytest.raises(AuditError):
        g.call(spec(), "res.partner", "unlink", [[1]])
    assert r.calls == []


def test_rv1_p03_missing_global_row_on(env):
    g, r, sw, al, e = G(env)
    with e.begin() as c:
        c.execute(text("DELETE FROM bot_kill_switch"))
    try:
        assert sw.check(FP) is not None
    finally:
        with e.begin() as c:
            c.execute(
                text(
                    "INSERT INTO bot_kill_switch(scope,is_on,reason,set_by) VALUES('global',false,'r','t')"  # noqa: E501
                )
            )


def test_rv1_p04_global_null_like_on(env):
    g, r, sw, al, e = G(env)
    sw.turn_on("global", "anyone", "t")
    assert go(g, spec(), [1]).status == "refused" and r.calls == []


# kill races
def test_rv1_p05_kill_mid_batch_stops(env):
    e, sw, al = env
    r = Rpc(on_call=lambda n: n == 3 and sw.turn_on(FP, "ops", "stop"))
    g = gd.WriteGate(sw, al, r, REH)
    u = Undo()
    rep = go(g, spec(), list(range(1, 11)), undo=u)
    assert len(r.calls) == 3 and rep.status == "partial" and u.images


def test_rv1_p06_kill_between_batches(env):
    e, sw, al = env
    r = Rpc(on_call=lambda n: n == 50 and sw.turn_on("global", "ops", "s"))
    g = gd.WriteGate(sw, al, r, REH)
    rep = go(g, spec(), list(range(1, 120)))
    assert len(r.calls) == 50 and rep.written == 50


def test_rv1_p07_kill_other_db_no_effect(env):
    g, r, sw, al, e = G(env)
    sw.turn_on(FP2, "ops", "s")
    assert go(g, spec(), [1]).status == "done"


# tampering
def test_rv1_p08_non_owner_cannot_clear(env):
    e, sw, al = env
    sw.turn_on(FP, "ops", "s")
    with pytest.raises(PermissionError):
        sw.turn_off(FP, "bot-1", "x")
    assert sw.check(FP) is not None


def test_rv1_p09_owner_lookup_error_denies(env):
    e, sw, al = env
    s2 = gd.KillSwitch(e, lambda s: 1 / 0)
    with pytest.raises(PermissionError):
        s2.turn_off(FP, "owner-1", "x")


def test_rv1_p10_override_cannot_loosen(env):
    e, sw, al = env
    for b, r_ in ((51, 10), (10, 501), (0, 10)):
        with pytest.raises(ValueError):
            sw.set_caps(FP, OWNER, b, r_)


def test_rv1_p11_db_check_blocks_direct_loosen(env):
    e, sw, al = env
    with pytest.raises(DBAPIError), e.begin() as c:
        c.execute(text("INSERT INTO bot_cap_override VALUES('z',999,9999,'x')"))


def test_rv1_p12_approver_equals_actor_refused(env):
    g, r, sw, al, e = G(env)
    rep = go(g, spec(level=3, approver="bot-1", risk_class="R3"), [1])
    assert rep.status == "refused" and not r.calls


def test_rv1_p13_approver_case_variant_of_actor(env):
    g, r, sw, al, e = G(env)
    rep = go(g, spec(level=3, approver="BOT-1 ", risk_class="R3"), [1])
    assert rep.status == "refused", "approver identity compared by raw string only"


def test_rv1_p14_approval_replay_across_db(env):
    # Approval is not bound to a db/task/key: same object authorises any run
    g, r, sw, al, e = G(env)
    a = gd.Approval(3, "human-1")
    s1 = spec(risk_class="R3", approval=a)
    s2 = spec(risk_class="R3", approval=a, db_fingerprint=FP2)
    assert go(g, s1, [1]).status == "done"
    assert go(g, s2, [1]).status == "refused", "approval replayable across DBs/runs"


# caps
def test_rv1_p15_batch_cap_chunks(env):
    g, r, sw, al, e = G(env)
    rep = go(g, spec(), list(range(1, 121)))
    assert rep.batches == 3


def test_rv1_p16_override_tightens(env):
    g, r, sw, al, e = G(env)
    sw.set_caps(FP, OWNER, 5, 20)
    rep = go(g, spec(), list(range(1, 21)))
    assert rep.batches == 4


def test_rv1_p17_run_cap_over_needs_l3(env):
    g, r, sw, al, e = G(env)
    assert go(g, spec(), list(range(1, 502))).status == "refused" and not r.calls


def test_rv1_p18_split_runs_bypass_run_cap(env):
    g, r, sw, al, e = G(env)
    for _ in range(3):
        go(g, spec(), list(range(1, 401)))
    assert len(r.calls) <= 500, "run cap bypassed by splitting into new idempotency keys"


def test_rv1_p19_duplicate_ids_dedup(env):
    g, r, sw, al, e = G(env)
    rep = go(g, spec(), [1] * 600)
    assert rep.total == 1


def test_rv1_p20_retry_same_key_noop(env):
    g, r, sw, al, e = G(env)
    s = spec(key="k-" + uuid.uuid4().hex)
    go(g, s, [1, 2])
    n = len(r.calls)
    rep = go(g, s, [1, 2])
    assert rep.status == "duplicate" and len(r.calls) == n


def test_rv1_p21_concurrent_same_key_single_write(env):
    e, sw, al = env
    r = Rpc()
    g = gd.WriteGate(sw, al, r, REH)
    s = spec(key="c-" + uuid.uuid4().hex)
    ts = [threading.Thread(target=go, args=(g, s, [1, 2, 3])) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(r.calls) == 3


# chain / triggers
def test_rv1_p22_update_delete_truncate_blocked(env):
    e, sw, al = env
    go(gd.WriteGate(sw, al, Rpc(), REH), spec(), [1])
    for sql in ("UPDATE bot_audit SET reason='x'", "DELETE FROM bot_audit", "TRUNCATE bot_audit"):
        with pytest.raises(DBAPIError), e.begin() as c:
            c.execute(text(sql))


def test_rv1_p23_owner_can_disable_trigger_and_truncate_tail_undetected(env):
    e, sw, al = env
    go(gd.WriteGate(sw, al, Rpc(), REH), spec(), [1, 2])
    with e.connect() as c:
        own = c.execute(
            text("SELECT tableowner=current_user FROM pg_tables WHERE tablename='bot_audit'")
        ).scalar()
    assert not own, (
        "app role owns bot_audit: can DISABLE TRIGGER / drop tail rows; chain has no external anchor"  # noqa: E501
    )


def test_rv1_p24_verify_detects_middle_edit(env):
    e, sw, al = env
    go(gd.WriteGate(sw, al, Rpc(), REH), spec(), [1])

    def upd(v):
        with e.begin() as c:
            c.execute(text("ALTER TABLE bot_audit DISABLE TRIGGER bot_audit_no_update"))
            mid = c.execute(text("SELECT min(id) FROM bot_audit")).scalar()
            old = c.execute(text("SELECT reason FROM bot_audit WHERE id=:i"), {"i": mid}).scalar()
            c.execute(text("UPDATE bot_audit SET reason=:v WHERE id=:i"), {"i": mid, "v": v or old})
            c.execute(text("ALTER TABLE bot_audit ENABLE TRIGGER bot_audit_no_update"))
        return old

    old = upd("tamper")
    ok = al.verify_chain()[0]
    upd(old)
    assert ok is False and al.verify_chain()[0]


# audit content
def test_rv1_p25_secret_rejected(env):
    with pytest.raises(AuditError):
        validate(AuditRow("fp", "t", "a", 1, "R1", "x", H, 1, 0, "k", "intent", "api_key=abc"))


def test_rv1_p26_secret_no_separator(env):
    with pytest.raises(AuditError):
        validate(AuditRow("fp", "t", "a", 1, "R1", "x", H, 1, 0, "k", "intent", "password hunter2"))


def test_rv1_p27_mid_batch_applied_audit_fail_trips(env):
    e, sw, al = env
    r = Rpc()

    class Flaky(AuditLog):
        def append(self, row):
            if row.decision == "applied":
                raise AuditError("x")
            return super().append(row)

    g = gd.WriteGate(sw, Flaky(e), r, REH)
    go(g, spec(), list(range(1, 80)))
    assert len(r.calls) == 50 and sw.check(FP) is not None


def test_rv1_p28_idempotency_key_cross_tenant_collision(env):
    g, r, sw, al, e = G(env)
    k = "shared-" + uuid.uuid4().hex
    go(g, spec(key=k), [1])
    rep = go(g, spec(key=k, db_fingerprint=FP2), [1])
    assert rep.status == "done", "another DB's key blocks this DB (key not scoped by db)"


def test_rv1_p29_migration_down_up(engine):
    _alembic("downgrade", "c7d8e9f0a1b2")
    _alembic("upgrade", "head")
