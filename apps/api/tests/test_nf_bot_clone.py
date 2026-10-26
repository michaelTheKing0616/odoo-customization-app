"""BOT-CLONE-REHEARSAL unit + adversarial tests (fake Odoo over the guard.Rpc shape).

The prod-apply tests use the real KillSwitch/AuditLog/WriteGate on the test PG (54339).
"""

from __future__ import annotations

import copy as cp
import json
import time
from pathlib import Path
from typing import Any

import pytest

from app.bot_verify import targets as tg
from app.bots import guard as gd
from app.bots.audit import AuditLog
from app.bots.clone import fingerprint as fpm
from app.bots.clone import neutralize as nz
from app.bots.clone import rehearse as rh
from app.bots.clone import rpc_copy as rc
from app.bots.risk.rules import Refusal
from tests.test_nf_bot_kill_audit import ANCHOR, OWNER, _clean, engine, fake_owner  # noqa: F401

pytestmark = [pytest.mark.no_app_db]

PROD_URL, COPY_URL = "https://erp.acme.com", "https://acme-copy.odoo.com"


# ------------------------------------------------------------- fake odoo ---
_OPS = {
    "=": lambda x, v: x == v,
    "!=": lambda x, v: x != v,
    "in": lambda x, v: x in v,
    "not in": lambda x, v: x not in v,
    "not like": lambda x, v: not str(x or "").endswith(v.lstrip("%")),
}


def _match(rec: dict, dom: list) -> bool:
    return all(_OPS[op](rec.get(f, f == "active"), v) for f, op, v in dom)


class Db:
    def __init__(self, uuid: str = "u-1", cdate: str = "2026-01-01 00:00:00", **models: Any):
        self.m: dict[str, dict[int, dict]] = {
            "ir.config_parameter": {},
            "ir.mail_server": {1: {"name": "real", "smtp_host": "smtp.acme.com", "smtp_port": 587}},
            "ir.cron": {1: {"name": "mail queue"}, 2: {"name": "fetch"}},
            "mail.template": {1: {"mail_server_id": 1}},
            "payment.provider": {1: {"state": "enabled"}, 2: {"state": "test"}},
            "base.automation": {1: {"name": "webhook"}},
            "iap.account": {1: {"account_token": "secret-tok"}},
            "res.partner": {7: {"comment": "old", "write_date": "2026-10-25 10:00:00"}},
            "ir.model": {},
        }
        self.m.update(models)
        for name in list(self.m):
            self.m["ir.model"][len(self.m["ir.model"]) + 1] = {"model": name}
        self.set("database.uuid", uuid)
        self.set("database.create_date", cdate)
        self.ignore: set[tuple[str, str]] = set()  # (model, field) writes silently dropped
        self.writes: list[tuple] = []
        self.no_field: set[tuple[str, str]] = set()  # fields_get omits these

    def set(self, k: str, v: str) -> None:
        t = self.m["ir.config_parameter"]
        for r in t.values():
            if r["key"] == k:
                r["value"] = v
                return
        t[max(t, default=0) + 1] = {"key": k, "value": v}

    def drop_model(self, name: str) -> None:
        self.m.pop(name)
        self.m["ir.model"] = {i: r for i, r in self.m["ir.model"].items() if r["model"] != name}


class Rpc:
    def __init__(self, db: Db) -> None:
        self.db = db
        self.fail: str | None = None

    def __call__(self, model: str, method: str, args: Any, kw: Any = None) -> Any:
        if self.fail and self.fail in (model, method):
            raise RuntimeError("boom")
        t = self.db.m[model]
        if method == "fields_get":
            keys = {k for r in t.values() for k in r} | {
                r.field for r in nz.RULES if r.model == model
            }
            return {k: {} for k in keys if (model, k) not in self.db.no_field}
        if method in ("search", "search_count", "search_read"):
            ids = [i for i, r in t.items() if _match({"id": i, **r}, args[0])]
            if method == "search":
                return ids
            if method == "search_count":
                return len(ids)
            return [{"id": i, **cp.deepcopy(t[i])} for i in ids]
        if method == "write":
            self.db.writes.append((model, list(args[0]), dict(args[1])))
            for i in args[0]:
                for k, v in args[1].items():
                    if (model, k) not in self.db.ignore:
                        t[i][k] = v
            return True
        if method == "create":
            self.db.writes.append((model, "create", dict(args[0])))
            nid = max(t, default=0) + 1
            t[nid] = dict(args[0])
            return nid
        if method == "unlink":
            for i in args[0]:
                t.pop(i)
            return True
        raise AssertionError(method)


def ident(db: Db, url: str, name: str, major: int = 17) -> fpm.Identity:
    return fpm.read_identity(Rpc(db), url, name, major)


# ----------------------------------------------------------- AC1 route ---
def test_route_detect():
    assert rh.detect_route(hosting_hint="odoo.com", db_probe=lambda: True) == "A"
    assert rh.detect_route(hosting_hint="Odoo.sh", db_probe=lambda: True) == "A"
    assert rh.detect_route(hosting_hint=None, db_probe=lambda: True) == "B"
    assert rh.detect_route(hosting_hint=None, db_probe=lambda: False) == "A"
    assert rh.detect_route(hosting_hint=None, db_probe=None) == "A"

    def boom() -> bool:
        raise OSError

    assert rh.detect_route(hosting_hint="self", db_probe=boom) == "A"
    assert rh.detect_route(hosting_hint="self", db_probe=lambda: "yes") == "A"  # type: ignore[arg-type,return-value]


# ----------------------------------------------------- AC3 fingerprint ---
def test_fingerprint_components_and_host_normalisation():
    db = Db()
    base = ident(db, PROD_URL, "acme")
    assert ident(db, "HTTPS://ERP.Acme.com.:443/web", "acme").fingerprint == base.fingerprint
    assert ident(db, "http://erp.acme.com", "acme").fingerprint != base.fingerprint
    assert ident(db, PROD_URL, "acme", 18).fingerprint != base.fingerprint
    assert ident(db, PROD_URL, "acme2").fingerprint != base.fingerprint
    assert ident(Db(uuid="u-2"), PROD_URL, "acme").fingerprint != base.fingerprint
    assert ident(Db(cdate="2026-02-02 00:00:00"), PROD_URL, "acme").fingerprint != base.fingerprint


@pytest.mark.parametrize("bad", ["database.uuid", "database.create_date"])
def test_identity_missing_refused(bad):
    db = Db()
    db.set(bad, "")
    with pytest.raises(fpm.IdentityError, match="missing"):
        ident(db, PROD_URL, "acme")


def test_identity_ambiguous_and_bad_inputs_refused():
    db = Db()
    db.m["ir.config_parameter"][99] = {"key": "database.uuid", "value": "spoof"}
    with pytest.raises(fpm.IdentityError, match="ambiguous"):
        ident(db, PROD_URL, "acme")
    with pytest.raises(fpm.IdentityError, match="outside"):
        ident(Db(), PROD_URL, "acme", 16)
    with pytest.raises(fpm.IdentityError, match="bad url"):
        ident(Db(), "ftp://x", "acme")
    r = Rpc(Db())
    r.fail = "ir.config_parameter"
    with pytest.raises(fpm.IdentityError, match="unreadable"):
        fpm.read_identity(r, PROD_URL, "acme", 17)


def test_check_target_refusals():
    db = Db()
    prod = ident(db, PROD_URL, "acme")
    with pytest.raises(fpm.IdentityError, match="is the production"):
        fpm.check_target(prod, ident(db, "https://ERP.acme.com.", "acme"))
    with pytest.raises(fpm.IdentityError, match="same db name"):  # prod-looking alias
        fpm.check_target(prod, ident(db, COPY_URL, "acme"))
    with pytest.raises(fpm.IdentityError, match="Odoo 18"):
        fpm.check_target(prod, ident(db, COPY_URL, "acme-copy", 18))
    fpm.check_target(prod, ident(cp.deepcopy(db), COPY_URL, "acme-copy"))  # Online Duplicate ok


# ------------------------------------------------------ AC2 neutralize ---
def test_neutralize_all_items_and_idempotent():
    db = Db()
    r = Rpc(db)
    res = nz.neutralize_and_check(r)
    assert set(res) == set(nz.ITEMS) and res.pop("fetchmail") == "n/a"
    present = {r.key for r in nz.RULES if r.model in db.m}
    assert {k for k, v in res.items() if v == "n/a"} == {r.key for r in nz.RULES} - present - {
        "fetchmail"
    }
    assert {res[k] for k in present} == {"ok"}
    srv = db.m["ir.mail_server"]
    assert srv[1]["active"] is False and db.m["mail.template"][1]["mail_server_id"] is False
    assert [s for s in srv.values() if s.get("active", True)] == [srv[2]]
    assert srv[2]["smtp_host"] == "127.0.0.1" and srv[2]["smtp_port"] == nz.TRAP_PORT
    assert all(c["active"] is False for c in db.m["ir.cron"].values())
    assert db.m["payment.provider"][1]["state"] == "disabled"
    assert db.m["payment.provider"][2]["state"] == "test"
    assert db.m["iap.account"][1]["account_token"].endswith("+disabled")
    assert (
        nz.neutralize_and_check(r) == {**res, "fetchmail": "n/a"} and len(srv) == 2
    )  # one trap, not two


def test_optional_models_absent_are_na():
    db = Db()
    for m in ("payment.provider", "base.automation", "iap.account", "mail.template"):
        db.drop_model(m)
    res = nz.neutralize_and_check(Rpc(db))
    assert res["payment"] == res["automation"] == res["iap"] == res["fetchmail"] == "n/a"
    assert res["cron"] == res["mail_server"] == "ok"


@pytest.mark.parametrize(
    "model,field,item",
    [
        ("ir.mail_server", "active", "mail_server"),  # clone that still sends mail
        ("mail.template", "mail_server_id", "mail_template"),  # template pinned to real smtp
        ("ir.cron", "active", "cron"),
        ("payment.provider", "state", "payment"),
        ("base.automation", "active", "automation"),
        ("iap.account", "account_token", "iap"),
    ],
)
def test_write_silently_ignored_is_refused(model, field, item):
    db = Db()
    db.ignore.add((model, field))
    with pytest.raises(nz.NeutralizeError) as e:
        nz.neutralize_and_check(Rpc(db))
    assert item in e.value.failed


def test_mail_server_reenabled_after_neutralize_is_caught():
    db = Db()
    r = Rpc(db)
    nz.neutralize_and_check(r)
    db.m["ir.mail_server"][1]["active"] = True
    assert nz.check(r)["mail_server"] == "FAIL"
    db.m["ir.mail_server"][1]["active"] = False
    db.m["ir.mail_server"][2]["active"] = False  # no trap: Odoo would fall back to odoo.conf
    assert nz.check(r)["smtp_trap"] == "FAIL"


def test_unreadable_item_fails_closed():
    db = Db()
    r = Rpc(db)
    nz.neutralize(r)
    r.fail = "ir.cron"
    with pytest.raises(nz.NeutralizeError) as e:
        nz.assert_neutralized(r)
    assert e.value.failed["cron"].startswith("FAIL")


# ---------------------------------------------------- AC4 Route A copy ---
def _pair(**kw: Any) -> tuple[Db, Db]:
    prod = Db()
    copy = cp.deepcopy(prod)  # Online Duplicate: same uuid + create_date
    return prod, copy


def prep(prod: Db, copy: Db, copy_db: str = "acme-copy", copy_url: str = COPY_URL):
    return rc.prepare_copy(Rpc(prod), PROD_URL, "acme", Rpc(copy), copy_url, copy_db, 17)


def test_route_a_happy_marks_and_neutralizes_copy_only():
    prod, copy = _pair()
    before = cp.deepcopy(prod.m)
    rep = prep(prod, copy)
    assert prod.m == before and prod.writes == []  # prod untouched
    assert fpm.get_param(Rpc(copy), fpm.MARKER_KEY) == rep.nonce and len(rep.nonce) == 32
    assert set(rep.neutralized.values()) == {"ok", "n/a"} and rep.copy_age_s is not None
    rc.remove_marker(Rpc(copy))
    assert fpm.get_param(Rpc(copy), fpm.MARKER_KEY) is None


def test_copy_equals_prod_refused_without_writes():
    prod, _ = _pair()
    with pytest.raises(fpm.IdentityError, match="production"):
        rc.prepare_copy(Rpc(prod), PROD_URL, "acme", Rpc(prod), "https://erp.ACME.com.", "acme", 17)
    assert prod.writes == []


def test_alias_of_prod_detected_by_marker_and_cleaned():
    prod, _ = _pair()  # "copy" under another db label but the same storage
    with pytest.raises(fpm.IdentityError, match="appeared on production"):
        prep(prod, prod)
    assert fpm.get_param(Rpc(prod), fpm.MARKER_KEY) is None
    assert all(m != "ir.cron" for m, *_ in prod.writes)  # nothing neutralized on prod


def test_marker_already_on_prod_refused():
    prod, copy = _pair()
    prod.set(fpm.MARKER_KEY, "attacker")
    with pytest.raises(fpm.IdentityError, match="found on production"):
        prep(prod, copy)
    assert copy.writes == []


def test_marker_spoof_copy_that_drops_marker_refused():
    prod, copy = _pair()
    copy.ignore.add(("ir.config_parameter", "value"))
    copy.set(fpm.MARKER_KEY, "stale-nonce")  # pre-planted marker is not accepted
    with pytest.raises(fpm.IdentityError, match="read-back"):
        prep(prod, copy)


def test_copy_marker_tamper_after_prepare_refused_before_write(tmp_path):
    prod, copy = _pair()
    rep = prep(prod, copy)
    copy.set(fpm.MARKER_KEY, "other")
    with pytest.raises(rh.RehearsalRefused, match="marker"):
        _rehearse(tmp_path, prod, copy, rep)
    assert not any(m == "res.partner" for m, *_ in copy.writes)


def test_copy_not_neutralizable_refused():
    prod, copy = _pair()
    copy.ignore.add(("ir.cron", "active"))
    with pytest.raises(nz.NeutralizeError):
        prep(prod, copy)


def test_jsonrpc_refuses_forbidden_ports_and_has_no_xmlrpc():
    for port in (8069, 8073, 54329, 11434):
        with pytest.raises(rc.RpcError, match="refused"):
            rc.JsonRpc(f"http://127.0.0.1:{port}", "x", "a", "b")
    for m in ("rpc_copy", "rehearse", "neutralize", "fingerprint"):
        src = (Path(rh.__file__).parent / f"{m}.py").read_text()
        assert "xmlrpc" not in src.replace("No XML-RPC", "").replace("no XML-RPC", "")


# ------------------------------------------------------ AC5 rehearsal ---
VALUES = {"comment": "new"}


def _store(tmp_path: Path) -> rh.RehearsalStore:
    return rh.RehearsalStore(tmp_path / "r.jsonl")


def _rehearse(tmp_path, prod: Db, copy: Db, rep, walk=lambda r: True, values=None) -> Any:
    tgt = rh.Target("A", Rpc(copy), COPY_URL, "acme-copy", rep.neutralized, rep, Rpc(prod))
    return rh.rehearse(
        store=_store(tmp_path),
        prod_rpc=Rpc(prod),
        prod=ident(prod, PROD_URL, "acme"),
        target=tgt,
        task_id="t:partner",
        model="res.partner",
        ids=[7],
        values=values or VALUES,
        walkthrough=walk,
        hosting_hint="odoo.com",
    )


def _pick(tmp_path, prod: Db, values=None, n_ids=(7,), now=None, task="t:partner") -> Any:
    fp = ident(prod, PROD_URL, "acme").fingerprint
    v = values or VALUES
    recs, used = _store(tmp_path).records()
    return rh.pick(
        recs,
        used,
        prod_fp=fp,
        task_id=task,
        plan=gd.plan_hash("acme", task, "res.partner", v, list(n_ids)),
        n=len(n_ids),
        dhash=gd.diff_hash(v),
        shash=rh.state_hash(Rpc(prod), "res.partner", list(n_ids)),
        now=time.time() if now is None else now,
    )


def test_rehearsal_record_fields_and_pick_ok(tmp_path):
    prod, copy = _pair()
    rec = _rehearse(tmp_path, prod, copy, prep(prod, copy))
    assert rec.passed and rec.route == "A" and rec.target_db == "acme-copy"
    assert rec.target_fp != rec.prod_fp and "host" in rec.backup_note
    assert copy.m["res.partner"][7]["comment"] == "new"
    assert prod.m["res.partner"][7]["comment"] == "old"
    assert _pick(tmp_path, prod).id == rec.id


def test_missing_failed_stale_planchange_drift(tmp_path):
    prod, copy = _pair()
    with pytest.raises(rh.RehearsalRefused, match="no rehearsal"):
        _pick(tmp_path, prod)
    rep = prep(prod, copy)
    _rehearse(tmp_path, prod, copy, rep, walk=lambda r: False)
    with pytest.raises(rh.RehearsalRefused, match="did not pass"):
        _pick(tmp_path, prod)
    _rehearse(tmp_path, prod, copy, rep)
    _pick(tmp_path, prod)
    with pytest.raises(rh.RehearsalRefused, match="stale"):
        _pick(tmp_path, prod, now=time.time() + 25 * 3600)
    _pick(tmp_path, prod, now=time.time() + 23 * 3600)
    with pytest.raises(rh.RehearsalRefused, match="future"):
        _pick(tmp_path, prod, now=time.time() - 3600)
    with pytest.raises(rh.RehearsalRefused, match="plan changed"):
        _pick(tmp_path, prod, values={"comment": "evil"})
    prod.m["res.partner"][8] = {"comment": "x"}
    with pytest.raises(rh.RehearsalRefused, match="plan changed"):
        _pick(tmp_path, prod, n_ids=(7, 8))
    prod.m["res.partner"][7]["write_date"] = "2026-10-25 11:00:00"  # source changed
    with pytest.raises(rh.RehearsalRefused, match="changed since"):
        _pick(tmp_path, prod)


def test_walkthrough_exception_and_readback_mismatch_record_failed(tmp_path):
    prod, copy = _pair()
    rep = prep(prod, copy)

    def boom(r):
        raise RuntimeError

    assert not _rehearse(tmp_path, prod, copy, rep, walk=boom).passed
    copy.ignore.add(("res.partner", "comment"))
    rec = _rehearse(tmp_path, prod, copy, rep, values={"comment": "newer"})
    assert rec.readback_ok is False and not rec.passed


def test_rehearsal_refuses_production_target(tmp_path):
    prod, _ = _pair()
    rep = rc.CopyReport(ident(prod, PROD_URL, "acme"), ident(prod, PROD_URL, "acme"), "n")
    tgt = rh.Target("A", Rpc(prod), PROD_URL, "acme", {"x": "ok"}, rep, Rpc(prod))
    with pytest.raises(rh.RehearsalRefused, match="production"):
        rh.rehearse(
            store=_store(tmp_path),
            prod_rpc=Rpc(prod),
            prod=ident(prod, PROD_URL, "acme"),
            target=tgt,
            task_id="t",
            model="res.partner",
            ids=[7],
            values=VALUES,
            walkthrough=lambda r: True,
        )
    assert prod.writes == []


def test_route_b_target_must_be_clone_and_neutralized(tmp_path):
    prod, clone = _pair()
    clone.set("database.uuid", "u-new")
    base = dict(
        store=_store(tmp_path),
        prod_rpc=Rpc(prod),
        prod=ident(prod, PROD_URL, "acme"),
        task_id="t",
        model="res.partner",
        ids=[7],
        values=VALUES,
        walkthrough=lambda r: True,
    )
    with pytest.raises(rh.RehearsalRefused, match="ingenium_clone_"):
        rh.rehearse(target=rh.Target("B", Rpc(clone), PROD_URL, "acme_staging", {}), **base)
    name = rh.clone_name("acme", "p")
    with pytest.raises(rh.RehearsalRefused, match="not neutralized"):  # clone still sends mail
        rh.rehearse(target=rh.Target("B", Rpc(clone), PROD_URL, name, {}), **base)
    res = nz.neutralize_and_check(Rpc(clone))
    rec = rh.rehearse(target=rh.Target("B", Rpc(clone), PROD_URL, name, res), **base)
    assert rec.passed and rec.route == "B"


def test_store_chain_tamper_refuses(tmp_path):
    prod, copy = _pair()
    _rehearse(tmp_path, prod, copy, prep(prod, copy))
    p = tmp_path / "r.jsonl"
    row = json.loads(p.read_text())
    row["walkthrough_ok"] = True
    row["taken_at"] = time.time() + 10
    p.write_text(json.dumps(row) + "\n")
    with pytest.raises(rh.RehearsalRefused, match="chain"):
        _store(tmp_path).records()
    p.write_text("{not json\n")
    with pytest.raises(rh.RehearsalRefused, match="unreadable"):
        _store(tmp_path).records()


# --------------------------------------------------------- Route B clone ---
class Ops:
    def __init__(self, fail: str | None = None) -> None:
        self.dbs: set[str] = set()
        self.fs: set[str] = set()
        self.log: list[str] = []
        self.fail = fail

    def _f(self, step: str) -> None:
        self.log.append(step)
        if self.fail == step:
            raise RuntimeError(step)

    def sql(self, q: str, db: str = "postgres") -> str:
        if q.startswith("CREATE DATABASE"):
            self._f("create")
            self.dbs.add(q.split('"')[1])
        elif q.startswith("DROP DATABASE"):
            self.dbs.discard(q.split('"')[1])
            self.log.append("drop")
        else:
            self._f("uuid")
        return ""

    def dump_restore(self, src: str, dst: str) -> None:
        self._f("dump")

    def copy_filestore(self, src: str, dst: str) -> None:
        self._f("fs")
        self.fs.add(dst)

    def drop_filestore(self, dst: str) -> None:
        self.fs.discard(dst)

    def neutralize_cli(self, dst: str) -> None:
        self._f("neutralize")


def test_cloner_happy_and_idempotent_retry():
    ops = Ops()
    c = rh.Cloner(ops, approved=lambda s: False)
    name = c.make("ingenium_nf_src", "plan1")
    assert rh.CLONE_RX.match(name) and ops.dbs == {name} and ops.fs == {name}
    assert ops.log == ["drop", "create", "dump", "fs", "uuid", "neutralize"]
    assert c.make("ingenium_nf_src", "plan1") == name and ops.dbs == {name}  # dropped + rebuilt


@pytest.mark.parametrize("step", ["create", "dump", "fs", "uuid", "neutralize"])
def test_cloner_killed_midway_leaves_nothing(step):
    ops = Ops(fail=step)
    c = rh.Cloner(ops, approved=lambda s: False)
    with pytest.raises(rh.RehearsalRefused, match="clone failed"):
        c.make("ingenium_nf_src", "p")
    assert ops.dbs == set() and ops.fs == set()
    ops.fail = None
    assert c.make("ingenium_nf_src", "p") in ops.dbs


def test_cloner_non_disposable_needs_owner_approval():
    ops = Ops()
    with pytest.raises(rh.RehearsalRefused, match="owner approval"):
        rh.Cloner(ops, approved=lambda s: False).make("acme_prod", "p")

    def broken(s):
        raise OSError

    with pytest.raises(rh.RehearsalRefused, match="owner approval"):
        rh.Cloner(ops, approved=broken).make("acme_prod", "p")
    assert ops.log == []
    assert rh.Cloner(ops, approved=lambda s: s == "acme_prod").make("acme_prod", "p")
    for bad in ('x"; DROP DATABASE y; --', "", rh.clone_name("a", "b")):
        with pytest.raises(rh.RehearsalRefused, match="bad source"):
            rh.Cloner(ops, approved=lambda s: True).make(bad, "p")
    with pytest.raises(rh.RehearsalRefused, match="non-clone"):
        rh.Cloner(ops, approved=lambda s: True).drop("ingenium_nf_src")


def test_local_ops_forbidden_port():
    for port in (5433, 5436, 54329):
        with pytest.raises(rh.RehearsalRefused, match="forbidden"):
            rh.LocalOps("127.0.0.1", port, "u", "p", Path("/tmp"))


# ------------------------------------------------------ targets (AC3) ---
class _Store:
    def __init__(self) -> None:
        self.rows: list = []

    def record(self, *a: Any) -> None:
        self.rows.append(a)

    def approval(self, cid: Any) -> Any:
        return tg.WalkApproval(False, None, None)


def test_walk_target_consumes_fingerprint():
    tg.configure_audit_store(_Store())
    try:
        db = Db()
        url = "http://127.0.0.1:18117"
        clone = fpm.read_identity(Rpc(db), url, "ingenium_clone_abc", 17)
        prod = fpm.read_identity(Rpc(db), url, "ingenium_nf_bv_17", 17)
        kw = dict(url=url, db_name="ingenium_clone_abc", major=17)
        assert tg.resolve_target(**kw, identity=clone, prod_fingerprint=prod.fingerprint).kind
        with pytest.raises(tg.TargetNotAllowed, match="production"):
            tg.resolve_target(**kw, identity=clone, prod_fingerprint=clone.fingerprint)
        with pytest.raises(tg.TargetNotAllowed, match="without target identity"):
            tg.resolve_target(**kw, prod_fingerprint=prod.fingerprint)
        with pytest.raises(tg.TargetNotAllowed, match="does not match"):
            tg.resolve_target(**kw, identity=prod, prod_fingerprint="x")
        assert tg.resolve_target(**kw).kind == "disposable_clone"  # old callers unchanged
    finally:
        tg.configure_audit_store(None)


# ------------------------------------------- prod apply via real guard ---
@pytest.fixture
def gate(engine):  # noqa: F811
    _clean(engine)
    sw = gd.KillSwitch(engine, lambda scope: OWNER, grant_source=fake_owner)
    return gd.WriteGate(sw, AuditLog(engine, anchor=ANCHOR), lambda *a: True)


def _apply(gate, tmp_path, prod: Db, fp: str | None = None, values=None, spec_fp=None) -> Any:
    real = fp or ident(prod, PROD_URL, "acme").fingerprint
    spec = gd.RunSpec(
        db_fingerprint=spec_fp or fp or real,
        task_id="t:partner",
        actor="bot-1",
        risk_class="R1",
        rule_ids="RF-ANY",
        approval=gd.Approval(1),
        idempotency_key=f"k-{time.time_ns()}",
    )
    seen: list = []
    rep = rh.apply(
        gate,
        _store(tmp_path),
        spec,
        "res.partner",
        [7],
        values or VALUES,
        prod_rpc=Rpc(prod),
        prod_url=PROD_URL,
        prod_db="acme",
        major=17,
        approved_fp=fp or real,
        before_image=lambda ids: ("img", {}),
        readback=lambda ids: seen.append(ids) or True,
        undo=lambda img: True,
    )
    return rep, seen


def test_apply_requires_matching_rehearsal_single_use(gate, tmp_path):
    prod, copy = _pair()
    rep, seen = _apply(gate, tmp_path, prod)
    assert rep.refusal and "no rehearsal" in rep.refusal.reason and seen == []
    _rehearse(tmp_path, prod, copy, prep(prod, copy))
    rep, _ = _apply(gate, tmp_path, prod, values={"comment": "evil"})
    assert rep.refusal and "plan changed" in rep.refusal.reason
    rep, seen = _apply(gate, tmp_path, prod)
    assert rep.refusal is None and rep.written == 1 and seen and set(map(tuple, seen)) == {(7,)}
    rep, _ = _apply(gate, tmp_path, prod)  # stale rehearsal reuse
    assert rep.refusal and "already used" in rep.refusal.reason


def test_apply_swapped_fingerprint_rf_any(gate, tmp_path):
    prod, copy = _pair()
    _rehearse(tmp_path, prod, copy, prep(prod, copy))
    copy_fp = ident(copy, COPY_URL, "acme-copy").fingerprint
    rep, seen = _apply(gate, tmp_path, prod, fp=copy_fp)
    assert rep.refusal.rule == "RF-ANY" and rep.refusal.missing == "db-fingerprint"
    rep, _ = _apply(gate, tmp_path, prod, spec_fp="fp-other")
    assert rep.refusal.missing == "db-fingerprint" and seen == []
    real = ident(prod, PROD_URL, "acme").fingerprint
    prod.set("database.uuid", "")
    rep, _ = _apply(gate, tmp_path, prod, fp=real)
    assert rep.refusal.rule == "RF-ANY"


# ------------------------------------------- guarded execute_kw wrapper ---
def _client(db: Db, name: str, url: str) -> rc.JsonRpc:
    """Real JsonRpc with the transport swapped for the fake (no network)."""
    c = object.__new__(rc.JsonRpc)
    c.url, c.db, c.uid, c._pw, c.timeout = url, name, 2, "pw", 1
    fake = Rpc(db)
    c.sent = []

    def _rpc(service: str, method: str, args: list) -> Any:
        c.sent.append(args[4:6])
        return fake(args[3], args[4], args[5], args[6])

    c._rpc = _rpc
    return c


def test_wrapper_refuses_writes_without_proof_reads_ok():
    c = _client(Db(), "acme", PROD_URL)
    assert c("ir.cron", "search_count", [[]]) == 2
    for m, a in (("write", [[1], {"active": False}]), ("create", [{}]), ("unlink", [[1]])):
        with pytest.raises(rc.RpcError, match="no verified copy"):
            c("ir.cron", m, a)
    with pytest.raises(rc.RpcError, match="no verified copy"):
        c("ir.cron", "action_archive", [[1]])  # any non-read method counts as a write
    assert all(m in rc.READ_METHODS for m, _ in c.sent)


def test_wrapper_prod_looking_target_refused():
    prod_db = Db()
    prod = ident(prod_db, PROD_URL, "acme")
    c = _client(prod_db, "acme", "https://ERP.acme.com.")  # prod under a prod-looking URL
    rc.attach_proof(c, prod, prod, "n", verified=True)  # forged: copy fp == prod fp
    with pytest.raises(rc.RpcError, match="no verified copy"):
        c("ir.cron", "write", [[1], {"active": False}])
    other = ident(cp.deepcopy(prod_db), COPY_URL, "acme-copy")
    rc.attach_proof(c, prod, other, "n", verified=True)  # proof for another client
    with pytest.raises(rc.RpcError, match="not the proven copy"):
        c("ir.cron", "write", [[1], {"active": False}])
    assert prod_db.writes == []


def test_wrapper_missing_marker_only_nonce_write_allowed():
    prod_db, copy_db = _pair()
    prod = ident(prod_db, PROD_URL, "acme")
    c = _client(copy_db, "acme-copy", COPY_URL)
    copy = fpm.read_identity(c, COPY_URL, "acme-copy", 17)
    rc.attach_proof(c, prod, copy, "nonce1")  # pending, marker not yet verified
    with pytest.raises(rc.RpcError, match="marker not verified"):
        c("ir.cron", "write", [[1], {"active": False}])
    with pytest.raises(rc.RpcError, match="marker not verified"):
        c("ir.config_parameter", "create", [{"key": fpm.MARKER_KEY, "value": "other"}])
    with pytest.raises(rc.RpcError, match="marker not verified"):
        c("ir.config_parameter", "write", [[1], {"value": "nonce1"}])  # not the marker row
    fpm.set_param(c, fpm.MARKER_KEY, "nonce1")
    assert fpm.get_param(c, fpm.MARKER_KEY) == "nonce1"


def test_prepare_copy_through_real_clients_and_prod_never_written():
    prod_db, copy_db = _pair()
    p = _client(prod_db, "acme", PROD_URL)
    c = _client(copy_db, "acme-copy", COPY_URL)
    rep = rc.prepare_copy(p, PROD_URL, "acme", c, COPY_URL, "acme-copy", 17)
    assert c.proof.verified and rep.neutralized["cron"] == "ok" and prod_db.writes == []
    assert all(m in rc.READ_METHODS for m, _ in p.sent)
    alias = _client(prod_db, "acme-alias", COPY_URL)  # same storage, other label
    with pytest.raises(fpm.IdentityError, match="appeared on production"):
        rc.prepare_copy(p, PROD_URL, "acme", alias, COPY_URL, "acme-alias", 17)
    assert fpm.get_param(p, fpm.MARKER_KEY) is None
    assert {w[0] for w in prod_db.writes} == {"ir.config_parameter"}  # marker only, removed


def test_prove_clone():
    prod_db, clone_db = _pair()
    clone_db.set("database.uuid", "u-new")
    prod = ident(prod_db, PROD_URL, "acme")
    name = rh.clone_name("acme", "p")
    c = _client(clone_db, name, PROD_URL)
    rh.prove_clone(c, prod, PROD_URL, name)
    assert nz.neutralize_and_check(c)["cron"] == "ok"
    bad = _client(prod_db, "acme_staging", PROD_URL)
    with pytest.raises(rh.RehearsalRefused, match="proven ingenium_clone_"):
        rh.prove_clone(bad, prod, PROD_URL, "acme_staging")
    with pytest.raises(rc.RpcError):
        bad("ir.cron", "write", [[1], {"active": False}])


# ------------------------------ reviewer round 2: structural neutralize ---
INVENTORY = Path.home() / ".ingenium_nf/taxonomy/fields_inventory.csv"


def test_outbound_drift_every_model_neutralized_or_reviewed():
    """Every model the risk floors call sensitive, or with an outbound stem in any 17-20
    field, is neutralized by a rule or listed NOT_OUTBOUND with a reason."""
    import csv

    from app.bots.risk import rules as rr

    if not INVENTORY.exists():
        pytest.skip("fields_inventory.csv not on this machine")
    scope: dict[str, set[str]] = {m: set() for m in rr.SENSITIVE_MODELS}
    with INVENTORY.open() as fh:
        for row in csv.DictReader(fh):
            m, f = row["model"], row["field"]
            stored = row["store"] == "True" or m in rr.SENSITIVE_MODELS
            if stored and any(st in f.lower() for st in nz.OUTBOUND_STEMS):
                scope.setdefault(m, set()).add(f)
    ruled = {r.model for r in nz.RULES}
    missing = sorted(m for m in scope if m not in ruled and m not in nz.NOT_OUTBOUND)
    assert not missing, missing
    assert all(len(nz.NOT_OUTBOUND[m]) > 10 for m in nz.NOT_OUTBOUND)
    assert not ruled & set(nz.NOT_OUTBOUND)
    for st in ("environment", "edi_mode", "webhook_url"):  # mode/env fields: a rule, by field
        for m, fs in scope.items():
            for f in fs:
                if st in f and m not in nz.NOT_OUTBOUND and not f.startswith("log_"):
                    assert m in ruled, (m, f)


@pytest.mark.parametrize(
    "model,field,start,bad",
    [
        ("delivery.carrier", "prod_environment", True, lambda v: v is True),
        ("ir.actions.server", "webhook_url", "https://hooks.real", lambda v: "real" in str(v)),
        ("account_edi_proxy_client.user", "edi_mode", "prod", lambda v: v == "prod"),
        ("payment.token", "active", True, lambda v: v is True),
        ("auth.oauth.provider", "enabled", True, lambda v: v is True),
        ("pos.payment.method", "use_payment_terminal", "adyen", lambda v: bool(v)),
        ("res.company.ldap", "ldap_server", "ldap.acme.com", lambda v: "acme" in str(v)),
        ("res.users.settings", "google_calendar_rtoken", "rt", lambda v: bool(v)),
    ],
)
def test_outbound_rule_neutralized_and_read_back(model, field, start, bad):
    db = Db(**{model: {1: {field: start}}})
    res = nz.neutralize_and_check(Rpc(db))
    key = next(r.key for r in nz.RULES if r.model == model)
    assert res[key] == "ok" and not bad(db.m[model][1][field])
    db.ignore.add((model, field))
    db.m[model][1][field] = start
    with pytest.raises(nz.NeutralizeError) as e:  # silently ignored write = refused
        nz.neutralize_and_check(Rpc(db))
    assert key in e.value.failed


def test_push_devices_unlinked_and_read_back():
    db = Db(**{"mail.push.device": {1: {"endpoint": "https://push.example"}}})
    assert nz.neutralize_and_check(Rpc(db))["push_device"] == "ok"
    assert db.m["mail.push.device"] == {}


def test_write_error_on_one_rule_refuses_but_others_still_run():
    db = Db(**{"delivery.carrier": {1: {"prod_environment": True}}})
    r = Rpc(db)
    r.fail = "base.automation"
    with pytest.raises(nz.NeutralizeError) as e:
        nz.neutralize_and_check(r)
    assert (
        "automation" in e.value.failed and db.m["delivery.carrier"][1]["prod_environment"] is False
    )


def test_missing_field_is_na_not_ok():
    db = Db(**{"pos.payment.method": {1: {"name": "card"}}})
    db.no_field.add(("pos.payment.method", "use_payment_terminal"))
    assert nz.neutralize_and_check(Rpc(db))["pos_terminal"] == "n/a"


def _gate_with(gate, tmp_path, prod: Db):
    g = cp.copy(gate)
    g.rehearsals = rh.StoreRehearsals(_store(tmp_path), Rpc(prod), "acme")
    return g


def _direct(g, prod: Db, rid, risk="R1", values=None, ids=(7,), key=None):
    s = gd.RunSpec(
        ident(prod, PROD_URL, "acme").fingerprint,
        "t:partner",
        "bot-1",
        risk,
        "RF-ANY",
        gd.Approval(1),
        key or f"k-{time.time_ns()}",
        rehearsal_id=rid,
    )
    return g.run(
        s,
        "res.partner",
        list(ids),
        values or VALUES,
        before_image=lambda i: ("i", {}),
        readback=lambda i: True,
        undo=lambda i: True,
    )


def test_gate_run_itself_requires_matching_rehearsal(gate, tmp_path):
    prod, copy = _pair()
    rid = _rehearse(tmp_path, prod, copy, prep(prod, copy)).id
    g = _gate_with(gate, tmp_path, prod)
    assert "no rehearsal bound" in _direct(g, prod, None).refusal.reason
    assert "id unknown" in _direct(g, prod, "rh-forged").refusal.reason
    assert "plan changed" in _direct(g, prod, rid, values={"comment": "evil"}).refusal.reason
    assert "plan changed" in _direct(g, prod, rid, ids=(7, 8)).refusal.reason  # record set
    rep = _direct(g, prod, rid, key="k-same")
    assert rep.refusal is None and rep.written == 1
    assert _direct(g, prod, rid, key="k-same").status == "duplicate"  # same run may resume
    assert "already used" in _direct(g, prod, rid).refusal.reason


def test_gate_refusal_before_write_releases_rehearsal(gate, tmp_path):
    prod, copy = _pair()
    rid = _rehearse(tmp_path, prod, copy, prep(prod, copy)).id
    g = _gate_with(gate, tmp_path, prod)
    rep = _direct(g, prod, rid, risk="R3")  # reserved, then no grant -> refused
    assert rep.refusal and rep.refusal.rule == "RF-R3" and rep.written == 0
    assert _direct(g, prod, rid).refusal is None  # released: still usable once


def test_stale_rehearsal_refused_by_gate(gate, tmp_path):
    prod, copy = _pair()
    rid = _rehearse(tmp_path, prod, copy, prep(prod, copy)).id
    g = _gate_with(gate, tmp_path, prod)
    g.rehearsals.now = time.time() + rh.STALE_S + 60
    assert "stale" in _direct(g, prod, rid).refusal.reason


def test_grant_binds_rehearsal_id(gate):
    sw = gate.switch
    with pytest.raises(ValueError):
        sw.create_grant(OWNER, "fp", "p" * 64, 1, 2, "alice", "bot-1", rehearsal_id="")
    gid = sw.create_grant(OWNER, "fp", "p" * 64, 1, 2, "alice", "bot-1", rehearsal_id="rh-a")
    a = gd.Approval(2, "alice", gid)
    got = sw.open_job("fp", "p" * 64, 1, 2, gid, a, "bot-1", "rh-b")
    assert isinstance(got, Refusal) and "rehearsal" in got.reason
    got = sw.open_job("fp", "p" * 64, 1, 2, gid, a, "bot-1", "rh-a")
    assert not isinstance(got, Refusal)


def test_forged_or_mutated_proof_refused():
    c = _client(Db(), "acme", PROD_URL)
    c.attach_proof(rc.CopyProof("a", "other", "b", "acme", fpm.norm_host(PROD_URL), verified=True))
    with pytest.raises(rc.RpcError, match="not minted"):
        c("res.partner", "write", [[7], {"comment": "x"}])
    prod, copy = _pair()
    cc = _client(copy, "acme-copy", COPY_URL)
    p_id, c_id = ident(prod, PROD_URL, "acme"), ident(copy, COPY_URL, "acme-copy")
    rc.attach_proof(cc, p_id, c_id, "n1", verified=False)
    cc.proof.verified = True  # client flips the flag after minting
    with pytest.raises(rc.RpcError, match="not minted"):
        cc("res.partner", "write", [[7], {"comment": "x"}])
    rc.attach_proof(cc, p_id, c_id, "n1", verified=True)
    assert cc("res.partner", "write", [[7], {"comment": "x"}]) is True


def test_gate_run_on_prod_without_rehearsal_refused(gate):
    s = gd.RunSpec(
        "fp-x", "t:partner", "bot-1", "R1", "RF-ANY", gd.Approval(1), f"k-{time.time_ns()}"
    )
    rep = gate.run(
        s,
        "res.partner",
        [7],
        VALUES,
        before_image=lambda i: ("i", {}),
        readback=lambda i: True,
        undo=lambda i: True,
    )
    assert rep.refusal is not None
