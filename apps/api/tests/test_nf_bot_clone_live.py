"""BOT-CLONE-REHEARSAL live: Odoo 17/19/20 sandbox stacks (18117-18120), ingenium_nf_* only.

Needs ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1. Per major: "prod" = ingenium_nf_clone_prod_<v>
(template of ingenium_nf_bv_<v>); Route A copy = template of prod (keeps database.uuid,
like Online Duplicate), reached by JSON-RPC only; Route B = pg_dump|pg_restore clone +
filestore + ``odoo neutralize``. XML-RPC is patched to raise for every rehearsal call.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import xmlrpc.client
from pathlib import Path
from typing import Any

import pytest

from app.bots import guard as gd
from app.bots.audit import AuditLog
from app.bots.clone import fingerprint as fpm
from app.bots.clone import neutralize as nz
from app.bots.clone import rehearse as rh
from app.bots.clone import rpc_copy as rc
from tests.test_nf_bot_kill_audit import ANCHOR, OWNER, _clean, engine, fake_owner  # noqa: F401

sys.path.insert(0, str(Path(__file__).parent / "live"))

LIVE = os.environ.get("ODOO_LIVE") == "1" and os.environ.get("INGENIUM_LIVE_INFRA") == "1"
pytestmark = [
    pytest.mark.no_app_db,
    pytest.mark.skipif(not LIVE, reason="live: set ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1"),
]
OUT = Path.home() / ".ingenium_nf" / "nfwt"


def _docker(*a: str) -> str:
    cp = subprocess.run(["docker", *a], capture_output=True, text=True, timeout=900, check=False)
    if cp.returncode != 0:
        raise RuntimeError(f"docker {a[:3]} rc={cp.returncode}: {cp.stderr[-300:]}")
    return cp.stdout


class DockerOps:
    def __init__(self, stack: Any, fail: str | None = None) -> None:
        self.s, self.fail = stack, fail

    def sql(self, q: str, db: str = "postgres") -> str:
        return _docker(
            "exec",
            self.s.db_container,
            "psql",
            "-U",
            "odoo",
            "-d",
            db,
            "-v",
            "ON_ERROR_STOP=1",
            "-tAc",
            q,
        )

    def dump_restore(self, src: str, dst: str) -> None:
        sh = f"pg_dump -U odoo -Fc {src} | pg_restore -U odoo --no-owner --exit-on-error -d {dst}"
        _docker("exec", self.s.db_container, "sh", "-c", sh)

    def copy_filestore(self, src: str, dst: str) -> None:
        fs = "/var/lib/odoo/filestore"
        _docker(
            "exec",
            self.s.odoo_container,
            "sh",
            "-c",
            f"[ ! -d {fs}/{src} ] || cp -r {fs}/{src} {fs}/{dst}",
        )

    def drop_filestore(self, dst: str) -> None:
        assert rh.CLONE_RX.match(dst)
        _docker("exec", self.s.odoo_container, "rm", "-rf", f"/var/lib/odoo/filestore/{dst}")

    def neutralize_cli(self, dst: str) -> None:
        if self.fail == "neutralize":
            raise RuntimeError("killed")
        _docker(
            "exec",
            self.s.odoo_container,
            "odoo",
            "neutralize",
            "--db_host=db",
            "-r",
            "odoo",
            "-w",
            "odoo",
            "-d",
            dst,
        )


def _template(stack: Any, src: str, dst: str) -> None:
    assert dst.startswith("ingenium_nf_clone_")
    ops = DockerOps(stack)
    ops.sql(f'DROP DATABASE IF EXISTS "{dst}" WITH (FORCE)')
    for i in range(10):  # Odoo may reconnect to src between terminate and CREATE
        ops.sql(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
            f" WHERE datname = '{src}' AND pid <> pg_backend_pid()"
        )
        try:
            ops.sql(f'CREATE DATABASE "{dst}" TEMPLATE "{src}"')
            return
        except RuntimeError:
            if i == 9:
                raise
            time.sleep(1)


def _warm(rpc: Any) -> None:
    """Pooled connections to a template source were terminated: wait for the registry."""
    for _ in range(60):
        try:
            rpc(
                "ir.config_parameter",
                "search_read",
                [[("key", "=", "database.uuid")]],
                {"fields": ["value"]},
            )
            return
        except Exception:  # noqa: BLE001
            time.sleep(1)
    raise TimeoutError("source not back")


def _rpc(url: str, db: str) -> rc.JsonRpc:
    for _ in range(60):
        try:
            r = rc.JsonRpc(url, db, "admin", "admin")
            r("ir.config_parameter", "search_count", [[]])
            return r
        except Exception:  # noqa: BLE001 - registry warming up
            time.sleep(2)
    raise TimeoutError(db)


def _raw(url: str, db: str, uid: int) -> Any:
    """Test-only prod writer for WriteGate (app/bots JsonRpc refuses unproven writes)."""
    import json
    import urllib.request

    def call(model: str, method: str, args: Any, kw: Any = None) -> Any:
        params = {"service": "object", "method": "execute_kw"}
        params["args"] = [db, uid, "admin", model, method, list(args), kw or {}]
        body = json.dumps({"jsonrpc": "2.0", "method": "call", "id": 1, "params": params})
        req = urllib.request.Request(
            f"{url}/jsonrpc", body.encode(), {"Content-Type": "application/json"}
        )
        out = json.loads(urllib.request.urlopen(req, timeout=60).read())
        assert not out.get("error"), out.get("error")
        return out["result"]

    return call


@pytest.fixture
def gate(engine):  # noqa: F811
    _clean(engine)
    sw = gd.KillSwitch(engine, lambda scope: OWNER, grant_source=fake_owner)
    return lambda rpc: gd.WriteGate(sw, AuditLog(engine, anchor=ANCHOR), rpc)


@pytest.fixture
def no_xmlrpc(monkeypatch):
    def deny(*a: Any, **k: Any) -> Any:
        raise AssertionError("XML-RPC used")

    monkeypatch.setattr(xmlrpc.client, "ServerProxy", deny)


@pytest.mark.parametrize("v", [17, 19, 20])
def test_live_route_a_and_b(v, gate, no_xmlrpc, tmp_path):
    import nf_bv_seed as seed

    stack = seed._stack(v)
    if not seed.stack_running(v):
        pytest.skip(f"stack {v} down")
    src, prod_db, copy_db = (
        f"ingenium_nf_bv_{v}",
        f"ingenium_nf_clone_prod_{v}",
        f"ingenium_nf_clone_copy_{v}",
    )
    url = stack.url
    made: list[str] = []
    table: list[str] = [f"# Odoo {v}"]
    cl = rh.Cloner(DockerOps(stack), approved=lambda s: False)
    try:
        _template(stack, src, prod_db)
        made.append(prod_db)
        prod = _rpc(url, prod_db)
        pw = _raw(url, prod_db, prod.uid)  # test-side setup writes on "prod"
        pid = pw("res.partner", "create", [{"name": "NF clone probe", "ref": "old"}])
        crons0 = prod("ir.cron", "search_count", [[("active", "=", True)]])
        _template(stack, prod_db, copy_db)
        made.append(copy_db)
        _warm(prod)
        copy = _rpc(url, copy_db)
        pid_ident = fpm.read_identity(prod, url, prod_db, v)
        assert fpm.read_identity(copy, url, copy_db, v).uuid == pid_ident.uuid  # like Duplicate

        # Route A guard table
        with pytest.raises(fpm.IdentityError, match="production"):
            rc.prepare_copy(prod, url, prod_db, prod, url.upper(), prod_db, v)
        table.append("A copy==prod: refused")
        fpm.set_param(pw, fpm.MARKER_KEY, "planted")
        with pytest.raises(fpm.IdentityError, match="found on production"):
            rc.prepare_copy(prod, url, prod_db, copy, url, copy_db, v)
        fpm.set_param(pw, fpm.MARKER_KEY, None)
        table.append("A marker on prod: refused")
        rep = rc.prepare_copy(prod, url, prod_db, copy, url, copy_db, v)
        assert fpm.get_param(prod, fpm.MARKER_KEY) is None
        assert prod("ir.cron", "search_count", [[("active", "=", True)]]) == crons0 > 0
        table.append(f"A copy neutralized: {rep.neutralized}")
        store = rh.RehearsalStore(tmp_path / "r.jsonl")
        vals = {"ref": f"rehearsed {v}"}
        tgt = rh.Target("A", copy, url, copy_db, rep.neutralized, rep, prod)
        rec = rh.rehearse(
            store=store,
            prod_rpc=prod,
            prod=pid_ident,
            target=tgt,
            task_id="t:p",
            model="res.partner",
            ids=[pid],
            values=vals,
            walkthrough=lambda r: True,
        )
        assert rec.passed and rec.route == "A"
        assert prod("res.partner", "read", [[pid], ["ref"]])[0]["ref"] == "old"

        def run(values: dict, key: str) -> Any:
            spec = gd.RunSpec(
                pid_ident.fingerprint, "t:p", "bot-1", "R1", "RF-ANY", gd.Approval(1), key
            )
            return rh.apply(
                gate(pw),
                store,
                spec,
                "res.partner",
                [pid],
                values,
                prod_rpc=prod,
                prod_url=url,
                prod_db=prod_db,
                major=v,
                approved_fp=pid_ident.fingerprint,
                before_image=lambda ids: ("img", prod("res.partner", "read", [ids, ["ref"]])),
                readback=lambda ids: True,
                undo=lambda img: True,
            )

        bad = run({"ref": "changed"}, f"k1{v}{time.time_ns()}")
        assert bad.refusal and "plan changed" in bad.refusal.reason
        ok = run(vals, f"k2{v}{time.time_ns()}")
        assert ok.refusal is None and ok.written == 1
        again = run(vals, f"k3{v}{time.time_ns()}")
        assert again.refusal and "already used" in again.refusal.reason
        table.append("A plan changed / reuse: refused; matching rehearsal: applied")
        rc.remove_marker(copy)

        # Route B neutralize table
        dead = rh.Cloner(DockerOps(stack, fail="neutralize"), approved=lambda s: False)
        with pytest.raises(rh.RehearsalRefused, match="clone failed"):
            dead.make(prod_db, rec.plan_hash)
        assert (
            DockerOps(stack)
            .sql(
                "SELECT 1 FROM pg_database WHERE datname = "
                f"'{rh.clone_name(prod_db, rec.plan_hash)}'"
            )
            .strip()
            == ""
        )
        table.append("B killed midway: leftover dropped")
        name = cl.make(prod_db, rec.plan_hash)
        made.append(name)
        assert cl.make(prod_db, rec.plan_hash) == name  # idempotent retry
        crpc = _rpc(url, name)
        with pytest.raises(rc.RpcError, match="no verified copy"):  # unproven clone client
            crpc("ir.cron", "write", [[1], {"active": False}], None)
        rh.prove_clone(crpc, pid_ident, url, name)
        before = nz.check(crpc)
        res = nz.neutralize_and_check(crpc)
        table.append(f"B after odoo neutralize: {before}")
        table.append(f"B after RPC neutralize+trap: {res}")
        cid = fpm.read_identity(crpc, url, name, v)
        assert cid.uuid != pid_ident.uuid and cid.fingerprint != pid_ident.fingerprint
        recb = rh.rehearse(
            store=store,
            prod_rpc=prod,
            prod=pid_ident,
            target=rh.Target("B", crpc, url, name, res),
            task_id="t:p2",
            model="res.partner",
            ids=[pid],
            values={"ref": "b"},
            walkthrough=lambda r: True,
        )
        assert recb.passed and recb.route == "B"
        table.append("B rehearsal: passed")
    finally:
        for d in made:
            if rh.CLONE_RX.match(d):
                cl.drop(d)
            else:
                DockerOps(stack).sql(f'DROP DATABASE IF EXISTS "{d}" WITH (FORCE)')
        (OUT / f"clone_live_{v}.txt").write_text("\n".join(table) + "\n")
