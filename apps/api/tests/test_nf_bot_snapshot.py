"""BOT-SNAPSHOT-PROOF: Route A before-image/undo proof through the real WriteGate, Route B
snapshot verify. Fake Odoo (JSON-RPC shaped calls); test PG 54339 for the gate/audit."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text

from app.bots import before_image as bi
from app.bots import guard as gd
from app.bots import snapshot as sn
from app.bots.audit import AuditLog
from app.bots.risk import rules as ru
from app.database_backup import pg_dump_argv
from tests.test_nf_bot_kill_audit import (  # noqa: F401
    ANCHOR,
    FP,
    OWNER,
    REH,
    _clean,
    engine,
    fake_owner,
)

pytestmark = pytest.mark.no_app_db
M = "res.partner"
META = {
    "ref": {"type": "char", "store": True},
    "color": {"type": "integer", "store": True},
    "category_id": {"type": "many2many", "store": True, "relation": "res.partner.category"},
    "parent_id": {"type": "many2one", "store": True, "relation": "res.partner"},
    "image_1920": {"type": "binary", "store": True},
    "display_name": {"type": "char", "store": True, "depends": ["name"], "readonly": True},
    "commercial_partner_id": {"type": "many2one", "store": True, "depends": ["parent_id"]},
    "country_code": {"type": "char", "related": "country_id.code", "store": False},
    "child_ids": {"type": "one2many", "store": True},
    "tz_offset": {"type": "char", "store": False},
    "credit_limit": {"type": "float", "store": True, "readonly": True},
    "street": {"type": "char", "store": True},
}


class Odoo:
    """Minimal res.partner over JSON-RPC-shaped calls. Quirks reproduce real undo traps."""

    def __init__(self, n: int = 120, quirks: set[str] | None = None) -> None:
        self.rows = {
            i: {
                "id": i,
                "ref": f"r{i}",
                "color": i % 5,
                "category_id": [1],
                "parent_id": False,
                "image_1920": "aGVsbG8=",
                "street": f"own{i}",
                "child_ids": [],
                "write_date": "0",
            }
            for i in range(1, n + 1)
        }
        self.quirks = quirks or set()
        self.clock = 0
        self.writes = 0
        self.fail_at: int | None = None
        self.on_write = None
        self.calls: list[str] = []

    def __call__(self, model: str, method: str, args: Any, kw: Any = None) -> Any:
        self.calls.append(method)
        if method == "fields_get":
            return {f: META[f] for f in (args[0] or META) if f in META}
        if method == "read":
            ids, fs = args
            bin_full = (kw or {}).get("context", {}).get("bin_size") is False
            out = []
            for i in ids:
                r = {f: self.rows[i].get(f) for f in fs}
                r["id"] = i
                if "image_1920" in fs and (not bin_full or "bin_size" in self.quirks):
                    r["image_1920"] = "8 bytes"
                if "parent_id" in fs and r["parent_id"]:
                    r["parent_id"] = [r["parent_id"], "P"]
                out.append(r)
            return out
        if method == "write":
            ids, vals = args
            for i in ids:
                self.writes += 1
                if self.fail_at is not None and self.writes >= self.fail_at:
                    raise ConnectionError("rpc dropped")
                for f, v in vals.items():
                    if f == "category_id":
                        if isinstance(v[0], list | tuple):
                            if "m2m_add_only" in self.quirks:
                                v = sorted(set(self.rows[i][f]) | set(v[0][2]))
                            else:
                                v = list(v[0][2])
                    self.rows[i][f] = v
                self.clock += 1
                self.rows[i]["write_date"] = str(self.clock)
                if "parent_sync" in self.quirks and vals.get("parent_id"):
                    self.rows[i]["street"] = "parent st"  # res.partner address sync (v17)
                if "o2m_side" in self.quirks and "ref" in vals:
                    self.rows[i]["child_ids"] = [999]  # stored side effect we cannot write
                if self.on_write:
                    self.on_write(i)
            return True
        raise AssertionError(method)


@pytest.fixture
def sw(engine):  # noqa: F811
    _clean(engine)
    return gd.KillSwitch(engine, lambda s: OWNER, grant_source=fake_owner), AuditLog(
        engine, anchor=ANCHOR
    )


def spec(key: str = "k1") -> gd.RunSpec:
    return gd.RunSpec(
        FP,
        "m:res.partner:change",
        "bot-1",
        "R1",
        "RF-ANY",
        gd.Approval(1),
        key,
        rehearsal_id="rh-1",
    )


def route(odoo: Odoo, tmp_path: Path, ids, values, **kw) -> bi.RouteA:
    kw.setdefault("switch_check", lambda: None)
    s = spec()
    plan = gd.plan_hash(s.db_fingerprint, s.task_id, M, values, list(ids))
    return bi.RouteA(
        odoo, odoo, bi.ImageStore(tmp_path / "bi"), plan=plan, model=M, ids=ids, values=values, **kw
    )


def run(sw, odoo, ra, ids, values, key="k1"):
    switch, audit = sw
    g = gd.WriteGate(switch, audit, odoo, REH)
    return g.run(spec(key), M, list(ids), values, **ra.hooks())


def rows(engine, decision=None):  # noqa: F811
    q = "SELECT decision, batch_no, before_image_ref FROM bot_audit ORDER BY id"
    with engine.connect() as c:
        out = c.execute(text(q)).all()
    return [r for r in out if decision is None or r[0] == decision]


V = {"ref": "new", "category_id": [(6, 0, [2, 3])]}


# ---------------------------------------------------------------- AC2 reversibility
@pytest.mark.parametrize(
    "f",
    [
        "display_name",
        "commercial_partner_id",
        "country_code",
        "child_ids",
        "tz_offset",
        "credit_limit",
        "nope",
    ],
)
def test_unrestorable_field_reclassified_irreversible(f, tmp_path):
    with pytest.raises(bi.Irreversible):
        route(Odoo(3), tmp_path, [1], {f: 1})


def test_reverse_op_table():
    assert bi.reverse_op("write") == "restore-values"
    assert bi.reverse_op("create", {"has_dependents": False}) == "unlink"
    assert bi.reverse_op("create", {"has_dependents": True}) == "archive"
    assert bi.reverse_op("archive") == "unarchive" and bi.reverse_op("unarchive") == "archive"
    assert bi.reverse_op("config_param", {"existed": False}) == "unlink"
    for k, ctx in [
        ("create", {}),
        ("post", {}),
        ("validate_stock", {}),
        ("send", {}),
        ("unlink", {}),
        ("merge", {}),
        ("uninstall", {}),
        ("lockout", {}),
        ("company_change", {}),
        ("whatever", {}),
    ]:
        with pytest.raises(bi.Irreversible):
            bi.reverse_op(k, ctx)


# ---------------------------------------------------------------- AC1/AC3/AC7 happy path
def test_run_proves_undo_on_batch1_then_finishes(sw, engine, tmp_path):  # noqa: F811
    o = Odoo(120)
    ids = list(range(1, 121))
    ra = route(o, tmp_path, ids, V)
    rep = run(sw, o, ra, ids, V)
    assert rep.status == "done" and rep.written == 120 and rep.batches == 3
    assert bi.verify_proof(ra.proof, ra.plan) and ra.undone == 0
    assert all(o.rows[i]["ref"] == "new" and o.rows[i]["category_id"] == [2, 3] for i in ids)
    intents = rows(engine, "intent")
    assert len(intents) == 3 and all(r[2].startswith("bi:") for r in intents)
    blob = (tmp_path / "bi" / f"{intents[0][2][3:].replace(':', '')}.json").read_bytes()
    img = json.loads(blob)
    assert len(img["rows"]) == 50 and img["rows"]["1"]["ref"] == "r1"
    full = {*META} - {"display_name", "country_code", "tz_offset"}  # all stored fields
    assert set(img["rows"]["1"]) == full | {"write_date", "write_uid"}
    assert ra.outside_plan == frozenset() and ra.full_image_ok
    assert any("proof ok 50" in x for x in ra.log)


def test_before_image_size_caps(tmp_path):
    ra = route(Odoo(60), tmp_path, list(range(1, 61)), V)
    with pytest.raises(bi.UndoRefused, match="1..50"):
        ra.before_image(list(range(1, 52)))
    with pytest.raises(bi.UndoRefused, match="outside the plan"):
        ra.before_image([999])


# ---------------------------------------------------------------- undo that doesn't restore
@pytest.mark.parametrize(
    "quirk,values",
    [
        ("m2m_add_only", {"category_id": [(6, 0, [2])]}),
        ("bin_size", {"image_1920": "bmV3"}),
    ],
)
def test_proof_catches_undo_that_does_not_restore(sw, engine, tmp_path, quirk, values):  # noqa: F811
    o = Odoo(80, {quirk})
    ids = list(range(1, 81))
    ra = route(o, tmp_path, ids, values)
    rep = run(sw, o, ra, ids, values)
    assert rep.status == "tripped" and rep.batches == 1 and ra.proof is None
    assert sw[0].check(FP) is not None  # kill switch tripped: rest of run refused
    assert all(o.rows[i]["write_date"] == "0" for i in range(51, 81))  # batch 2 never written
    assert rows(engine, "tripped")


def test_m2m_and_binary_restored_when_reversible(sw, tmp_path):
    o = Odoo(10)
    vals = {"category_id": [(6, 0, [4])], "image_1920": "bmV3", "parent_id": 3}
    ra = route(o, tmp_path, range(1, 11), vals)
    rep = run(sw, o, ra, range(1, 11), vals)
    assert rep.status == "done" and ra.proof is not None


def test_injected_readback_mismatch_on_batch1_auto_undoes(sw, engine, tmp_path):  # noqa: F811
    o = Odoo(60)
    ids = list(range(1, 61))
    ra = route(o, tmp_path, ids, V)
    o.on_write = lambda i: o.rows[i].update(ref="tampered") if i == 7 else None
    rep = run(sw, o, ra, ids, V)
    assert rep.status == "tripped" and sw[0].check(FP) is not None
    assert o.rows[1]["ref"] == "r1" and 7 in [int(k) for k in ra.conflicts]  # human flag
    assert [r[0] for r in rows(engine)][-2:] == ["tripped", "undo_failed"]


# ---------------------------------------------------------------- AC4 later batch
def test_later_batch_mismatch_stops_and_undoes_that_batch(sw, engine, tmp_path):  # noqa: F811
    o = Odoo(150)
    ids = list(range(1, 151))
    ra = route(o, tmp_path, ids, V)
    o.on_write = lambda i: o.rows[i].update(color=99) if i == 120 else None
    orig = ra.readback
    ra.readback = lambda c: orig(c) and not (120 in c and len(c) <= 50)  # chaos: batch 3 bad
    rep = run(sw, o, ra, ids, ra.hooks()["readback"] and V)
    assert rep.status == "tripped" and rep.batches == 3 and rep.written == 100
    # 120's color=99 re-fires on the reverse write: unrestorable outside-plan field, fail closed
    # unproven side effect: never restored (could be a person's edit), flagged for a human
    assert ra.undone == 49 and "color" in ra.conflicts["120"] and not ra.unrestorable
    assert all(o.rows[i]["ref"] == f"r{i}" for i in range(101, 151))
    assert all(o.rows[i]["ref"] == "new" for i in range(1, 101))
    assert [r[0] for r in rows(engine)][-2:] == ["tripped", "undo_failed"]


def test_no_proof_no_write_beyond_batch1(sw, tmp_path):
    o = Odoo(120)
    ids = list(range(1, 121))
    ra = route(o, tmp_path, ids, V)
    ra._prove = lambda chunk: True  # proof skipped (bug/forgery): proof stays None
    rep = run(sw, o, ra, ids, V)
    assert rep.status in ("partial", "refused") and rep.written == 50
    assert all(o.rows[i]["write_date"] == "0" for i in range(51, 121))


# ---------------------------------------------------------------- chaos: partial batch, resume
def test_partial_batch_failure_resume_idempotent(sw, tmp_path):
    o = Odoo(100)
    ids = list(range(1, 101))
    ra = route(o, tmp_path, ids, V)
    o.fail_at = 50 + 50 + 50 + 20  # batch1 apply+undo+reapply = 150 writes, then 20 into batch 2
    with pytest.raises(ConnectionError):
        run(sw, o, ra, ids, V)
    o.fail_at = None
    img = ra.last_image
    first = ra._undo_result(img)
    assert first.ok and len(first.restored) == 19 and len(first.already) == 31
    again = ra._undo_result(img)  # resume after a drop mid-undo: no-op
    assert again.ok and not again.restored and len(again.already) == 50


def test_rpc_drop_mid_undo_then_resume(tmp_path):
    o = Odoo(10)
    ra = route(o, tmp_path, range(1, 11), V)
    ref, img = ra.before_image(list(range(1, 11)))
    o(M, "write", [list(range(1, 11)), {"ref": "new", "category_id": [(6, 0, [2, 3])]}])
    assert ra.readback(list(range(1, 11))) is True  # proof also passes here
    o(M, "write", [list(range(1, 11)), {"ref": "new", "category_id": [(6, 0, [2, 3])]}])
    ra.applied_wd = {str(i): o.rows[i]["write_date"] for i in range(1, 11)}
    o.fail_at = o.writes + 4
    assert ra.undo(img) is False
    o.fail_at = None
    res = ra._undo_result(img)
    assert res.ok and len(res.already) == 3 and len(res.restored) == 7


# ---------------------------------------------------------------- AC5 concurrency
def _applied(tmp_path, n=10):
    o = Odoo(n)
    ids = list(range(1, n + 1))
    ra = route(o, tmp_path, ids, V)
    ref, img = ra.before_image(ids)
    o(M, "write", [ids, V])
    ra.applied_wd = {str(i): o.rows[i]["write_date"] for i in ids}
    return o, ra, img


def test_user_edit_other_field_after_apply_refuses_that_record(tmp_path):
    o, ra, img = _applied(tmp_path)
    o(M, "write", [[3], {"color": 4}])  # user edit: write_date moves
    res = ra._undo_result(img)
    assert "3" in res.conflicts and "since apply" in res.conflicts["3"]
    assert o.rows[3]["ref"] == "new" and o.rows[4]["ref"] == "r4"


def test_user_changed_same_field_meanwhile_refused(tmp_path):
    o, ra, img = _applied(tmp_path)
    o.rows[5]["ref"] = "user typed"  # same second: write_date unchanged
    res = ra._undo_result(img)
    assert res.conflicts["5"].startswith("values changed") and o.rows[5]["ref"] == "user typed"


# ---------------------------------------------------------------- tamper / stale / reuse
def test_before_image_tampered_refused(tmp_path):
    o, ra, img = _applied(tmp_path)
    p = tmp_path / "bi" / f"{img.ref[3:].replace(':', '')}.json"
    d = json.loads(p.read_text())
    d["rows"]["1"]["ref"] = "attacker"
    p.write_text(json.dumps(d))
    assert ra.undo(img) is False and o.rows[1]["ref"] == "new"
    with pytest.raises(bi.UndoRefused, match="tampered"):
        ra._undo_result(img)
    p.unlink()
    with pytest.raises(bi.UndoRefused, match="missing"):
        ra._undo_result(img)


def test_before_image_stale_refused(tmp_path):
    o, ra, img = _applied(tmp_path)
    ra.now = lambda: img.taken_at + bi.IMAGE_MAX_AGE_S + 1
    with pytest.raises(bi.UndoRefused, match="stale"):
        ra._undo_result(img)


def test_image_and_proof_not_reusable_across_plans(sw, tmp_path):
    o = Odoo(120)
    ids = list(range(1, 121))
    ra = route(o, tmp_path, ids, V)
    assert run(sw, o, ra, ids, V).status == "done"
    other = route(o, tmp_path, ids, {"ref": "x"})
    assert not bi.verify_proof(ra.proof, other.plan)
    with pytest.raises(bi.UndoRefused, match="another plan"):
        other._undo_result(ra.last_image)
    forged = bi.UndoProof(other.plan, ra.proof.ref, ra.proof.mac)
    assert not bi.verify_proof(forged, other.plan)
    other.proof, other.batches = ra.proof, 1
    with pytest.raises(bi.UndoRefused, match="not proven"):
        other.before_image(list(range(51, 60)))


# ---------------------------------------------------------------- rules wiring
def _decision():
    from app.bots.risk import classifier as cl

    return (
        cl.classify_task("m:res.partner:change", route="A", version=17)
        if hasattr(cl, "classify_task")
        else None
    )


def test_gate_with_proofs_needs_verifier():
    ctx = ru.GateCtx(route="A", version=17)
    names = ru.PROOF_CONTROLS | {"x"}
    kept = []

    def fake_gate(d, c):
        kept.append(c.proven)
        return ru.Allowed("t", 1)

    orig = ru._evaluate
    ru._evaluate = fake_gate
    try:
        ru.gate_with_proofs(None, ru.GateCtx("A", 17, proven=frozenset(names)), None)
        ru.gate_with_proofs(
            None, ru.GateCtx("A", 17, proven=frozenset(names)), lambda c: c == "before-image"
        )
        ru.gate_with_proofs(None, ru.GateCtx("A", 17, proven=frozenset(names)), lambda c: 1 / 0)
    finally:
        ru._evaluate = orig
    assert kept[0] == {"x"} and kept[1] == {"x", "before-image"} and kept[2] == {"x"}
    assert ctx.proven == frozenset()


# ---------------------------------------------------------------- Route B
class FakeOps:
    def __init__(self, tmp: Path) -> None:
        self.tmp, self.dbs = tmp, {"ingenium_nf_p": {"res_partner": 5, "ir_attachment": 2}}
        self.fail: str | None = None
        self.taken: set[str] = set()
        self.dropped: list[str] = []

    def dump(self, db, out):
        out.write_bytes(b"PGDMP" + json.dumps(self.dbs[db]).encode())
        if self.fail == "dump":
            raise RuntimeError("killed")

    def filestore_tar(self, db, out):
        import tarfile

        with tarfile.open(out, "w"):
            pass

    def restore(self, dump, scratch):
        if self.fail == "restore":
            raise RuntimeError("bad dump")
        data = json.loads(dump.read_bytes()[5:])
        if self.fail == "lossy":
            data["ir_attachment"] -= 1
        self.dbs[scratch] = data

    def counts(self, db, tables):
        return {t: self.dbs[db][t] for t in tables}

    def db_exists(self, name):
        if name not in self.taken and len(self.taken) < 2:
            self.taken.add(name)
            return True  # first two candidate names collide
        return name in self.dbs

    def drop(self, scratch):
        assert sn.SCRATCH_RX.match(scratch)
        self.dropped.append(scratch)
        self.dbs.pop(scratch, None)


def _snap(tmp_path, ops=None):
    ops = ops or FakeOps(tmp_path)
    return ops, sn.take(ops, "ingenium_nf_p", FP, tmp_path / "s", ["res_partner"])


def test_snapshot_take_and_verify(tmp_path):
    ops, s = _snap(tmp_path)
    assert s.id.startswith("snap:") and s.counts == {"ir_attachment": 2, "res_partner": 5}
    assert sn.verify(ops, s, FP) is None
    assert len(ops.dropped) == 1 and len(ops.taken) == 2  # collisions skipped, scratch dropped
    assert sn.load(Path(s.dump).with_suffix(".json")) == s
    assert sn.Verified(ops, s, FP)("snapshot-proof")


@pytest.mark.parametrize(
    "what", ["flip", "fs", "manifest", "fp", "stale", "lossy", "restore", "gone"]
)
def test_snapshot_refusals(tmp_path, what):
    import dataclasses

    ops, s = _snap(tmp_path)
    fp, now = FP, None
    if what == "flip":
        b = bytearray(Path(s.dump).read_bytes())
        b[3] ^= 1
        Path(s.dump).write_bytes(bytes(b))
    elif what == "fs":
        Path(s.filestore).write_bytes(b"x")
    elif what == "manifest":
        s = dataclasses.replace(s, counts={"ir_attachment": 0})
    elif what == "fp":
        fp = "0" * 64
    elif what == "stale":
        now = lambda: s.taken_at + sn.SNAPSHOT_MAX_AGE_S + 1  # noqa: E731
    elif what in ("lossy", "restore"):
        ops.fail = what
    elif what == "gone":
        Path(s.dump).unlink()
    r = sn.verify(ops, s, fp, **({"now": now} if now else {}))
    assert r is not None and r.missing == "snapshot-proof"
    assert not [d for d in ops.dbs if d.startswith("ingenium_scratch_")]  # always dropped
    if what != "stale":
        assert not sn.Verified(ops, s, fp)("snapshot-proof")


def test_dump_killed_or_disk_full_leaves_no_id(tmp_path):
    ops = FakeOps(tmp_path)
    ops.fail = "dump"
    with pytest.raises(sn.SnapshotError) as e:
        sn.take(ops, "ingenium_nf_p", FP, tmp_path / "s", [])
    assert e.value.refusal.missing == "snapshot-proof" and not list((tmp_path / "s").iterdir())
    with pytest.raises(sn.SnapshotError, match="disk"):
        sn.take(FakeOps(tmp_path), "ingenium_nf_p", FP, tmp_path / "s", [], min_free=1 << 62)


def test_pg_dump_argv_and_no_xmlrpc():
    assert pg_dump_argv("ingenium_nf_p")[:4] == ["pg_dump", "-U", "odoo", "-Fc"]
    for bad in ["x; rm -rf /", "-d", "", "a'b"]:
        with pytest.raises(ValueError):
            pg_dump_argv(bad)
    for f in ("before_image.py", "snapshot.py"):
        src = (Path(bi.__file__).parent / f).read_text()
        mods = {getattr(n, "module", None) for n in ast.walk(ast.parse(src))}
        names = {
            a.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Import) for a in n.names
        }
        assert not any("xmlrpc" in (m or "") for m in mods | names)


def test_legacy_name_trusting_gate_removed_and_names_refused():
    from app.bots.risk import classifier as cl

    assert not hasattr(ru, "gate")
    src = (Path(ru.__file__).parent).rglob("*.py")
    app = Path(ru.__file__).parents[2]
    hits = [
        p for p in app.rglob("*.py") if re.search(r"\brules\.gate\(|\bru\.gate\(", p.read_text())
    ]
    assert hits == [] and src
    proven = frozenset(ru.PROOF_CONTROLS | {"copy-rehearsal"})
    ctx = ru.GateCtx("A", 17, kill_switch=False, fingerprint_ok=True, proven=proven)
    seen = []
    orig = ru._evaluate
    ru._evaluate = lambda d, c: seen.append(c.proven) or ru.Allowed("t", 1)
    try:
        cl_check = cl.rules.gate_with_proofs
        cl_check(None, ctx, None)
        cl_check(None, ctx, lambda c: "yes")  # truthy non-True is not a proof
    finally:
        ru._evaluate = orig
    assert seen == [{"copy-rehearsal"}, {"copy-rehearsal"}]


def test_kill_switch_checked_before_every_undo_write(tmp_path):
    o, ra, img = _applied(tmp_path)
    unreadable = ru.Refusal("RF-ANY", "kill-switch-state", "unreadable")
    calls = []

    def chk():
        calls.append(1)
        return [None, gd.refusal_kill("x")][len(calls) % 2] if len(calls) < 3 else unreadable

    ra.switch_check = chk
    before = o.writes
    res = ra._undo_result(img)  # switch ON (gate tripped it) still restores; unreadable stops
    assert len(calls) == 10 and o.writes - before == 2 and len(res.restored) == 2
    assert sum(v == "kill switch" for v in res.conflicts.values()) == 8
    o2, ra2, _ = _applied(tmp_path / "f")
    ra2.switch_check = lambda: gd.refusal_kill("x")
    assert ra2._write_one(1, {"ref": "x"}) is False  # forward write needs a clear switch


# ---------------------------------------------------------------- full-image (review round 3)
P = {"parent_id": 7}


def test_side_effect_parent_sync_captured_restored_and_flagged(sw, tmp_path):
    o = Odoo(60, {"parent_sync"})
    ids = list(range(1, 61))
    ra = route(o, tmp_path, ids, P)
    assert not ra.check("batch1-undo-proof") and not ra.check("before-image")  # no proof yet
    ref, img = ra.before_image(ids[:50])
    o(M, "write", [ids[:50], P])
    assert ra.readback(ids[:50])  # proof: undo restored street too, then re-applied
    assert ra.outside_plan == {"street"} and ra.side_effects["street"] == 50
    assert ra.check("batch1-undo-proof") and not ra.check("full-image-proof")
    assert ra.undo(img) and all(o.rows[i]["street"] == f"own{i}" for i in ids[:50])
    assert all(o.rows[i]["parent_id"] is False for i in ids[:50])


def test_later_batch_new_side_effect_trips(tmp_path):
    o = Odoo(60)
    ra = route(o, tmp_path, list(range(1, 61)), {"ref": "new"})
    ra.before_image(list(range(1, 51)))
    o(M, "write", [list(range(1, 51)), {"ref": "new"}])
    assert ra.readback(list(range(1, 51))) and ra.full_image_ok
    ra.before_image([51])
    o(M, "write", [[51], {"ref": "new", "street": "elsewhere"}])  # unproven side effect
    assert ra.readback([51]) is False


def test_unrestorable_outside_plan_field_fails_closed(tmp_path):
    o = Odoo(5, {"o2m_side"})
    ra = route(o, tmp_path, [1, 2], {"ref": "new"})
    ra.before_image([1, 2])
    o(M, "write", [[1, 2], {"ref": "new"}])
    assert ra.readback([1, 2]) is False and ra.proof is None
    assert ra.unrestorable == {"child_ids"} and not ra.full_image_ok


def test_binary_side_field_hashed_and_restored(tmp_path):
    o = Odoo(3)
    ra = route(o, tmp_path, [1], {"ref": "new"})
    _, img = ra.before_image([1])
    assert img.rows["1"]["image_1920"].startswith("sha:")
    o(M, "write", [[1], {"ref": "new", "image_1920": "Ynll"}])
    ra.applied_wd.clear()
    ra.proven_side = frozenset({"image_1920"})  # side effect proven ours by the re-apply
    assert ra.undo(img) and o.rows[1]["image_1920"] == "aGVsbG8="


def test_image_files_0600_in_0700_dir(tmp_path):
    o = Odoo(3)
    ra = route(o, tmp_path, [1], {"ref": "new"})
    ref, _ = ra.before_image([1])
    d = tmp_path / "bi"
    assert d.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in d.iterdir())


def test_snapshot_manifest_signed(tmp_path):
    import dataclasses

    ops, s = _snap(tmp_path)
    assert s.mac and sn.verify(ops, s, FP) is None
    forged = dataclasses.replace(s, mac="0" * 64)
    assert sn.verify(ops, forged, FP).missing == "snapshot-proof"
    assert sn.verify(ops, dataclasses.replace(s, mac=""), FP).missing == "snapshot-proof"


# ------------------------------------------------- undo never reverts a person's edit


def _b(ra, o, chunk, vals):
    _, img = ra.before_image(chunk)
    o(M, "write", [list(chunk), vals])
    return img


def test_person_edit_outside_plan_between_image_and_readback_kept(tmp_path):
    o = Odoo(2)
    ra = route(o, tmp_path, [1, 2], {"ref": "new"})
    img = _b(ra, o, [1, 2], {"ref": "new"})
    o.rows[2]["street"] = "human edit"  # concurrent edit, not caused by our write
    assert ra.readback([1, 2]) is False and "street" in ra.conflicts["2"]
    ra.undo(img)
    assert o.rows[2]["street"] == "human edit" and o.rows[1]["ref"] == "r1"
    assert ra.proof is None and not ra.check("batch1-undo-proof")


def test_reproduced_side_effect_still_restored(tmp_path):
    o = Odoo(2, quirks={"parent_sync"})  # parent_id write re-syncs street (res.partner)
    ra = route(o, tmp_path, [1, 2], {"parent_id": 9})
    img = _b(ra, o, [1, 2], {"parent_id": 9})
    assert ra.readback([1, 2]) and ra.proven_side == {"street"}
    assert ra.undo(img) and o.rows[1]["street"] == "own1" and o.rows[2]["parent_id"] is False


def test_unproven_outside_change_not_restored_flagged(tmp_path):
    o = Odoo(3)
    ra = route(o, tmp_path, [1], {"ref": "new"})
    img = _b(ra, o, [1], {"ref": "new"})
    o.rows[1]["street"] = "someone"
    ra.applied.clear()
    ra.applied_wd.clear()
    assert ra.undo(img) is False and o.rows[1]["street"] == "someone"
    assert "street" in ra.conflicts["1"] and o.rows[1]["ref"] == "r1"


@pytest.mark.parametrize("approval,ok", [(1, False), (2, True)])
def test_opr_rechecked_every_batch(tmp_path, approval, ok):
    o = Odoo(60, quirks={"parent_sync"})
    ids = list(range(1, 61))
    ra = route(o, tmp_path, ids, {"parent_id": 9}, approval=approval)
    _b(ra, o, ids[:50], {"parent_id": 9})
    assert ra.readback(ids[:50])
    _b(ra, o, ids[50:], {"parent_id": 9})
    assert ra.readback(ids[50:]) is ok


def test_snapshot_files_0600(tmp_path):
    _, s = _snap(tmp_path)
    for p in (Path(s.dump), Path(s.filestore)):
        assert p.stat().st_mode & 0o777 == 0o600
