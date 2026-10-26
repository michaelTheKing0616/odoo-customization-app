"""BOT-SNAPSHOT-PROOF live: Odoo 17 + 20 sandboxes, ingenium_nf_* / ingenium_scratch_* only.

Needs ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1. "prod" = ingenium_nf_clone_snapprod_<v> (template of
ingenium_nf_bv_<v>). Route A over JSON-RPC only (XML-RPC patched to raise): 60 partners,
batch-1 apply/undo/re-apply proof, then batch 2; injected concurrent edit -> trip + auto-undo.
Route B: pg_dump + filestore tar via docker exec, restore into ingenium_scratch_*, verify;
byte-flipped dump -> 'snapshot-proof' refusal.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from app.bots import before_image as bi
from app.bots import guard as gd
from app.bots import snapshot as sn
from app.bots.audit import AuditLog
from app.bots.clone import fingerprint as fpm
from tests.test_nf_bot_clone_live import (  # noqa: F401
    LIVE,
    DockerOps,
    _raw,
    _rpc,
    _template,
    _warm,
    no_xmlrpc,
)
from tests.test_nf_bot_kill_audit import (  # noqa: F401
    ANCHOR,
    OWNER,
    REH,
    _clean,
    engine,
    fake_owner,
)

pytestmark = [
    pytest.mark.no_app_db,
    pytest.mark.skipif(not LIVE, reason="live: set ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1"),
]
M = "res.partner"


def _gate(engine, w):  # noqa: F811
    _clean(engine)
    sw = gd.KillSwitch(engine, lambda s: OWNER, grant_source=fake_owner)
    return sw, gd.WriteGate(sw, AuditLog(engine, anchor=ANCHOR), w, REH)


def _spec(fp: str, key: str) -> gd.RunSpec:
    return gd.RunSpec(
        fp,
        "m:res.partner:change",
        "bot-1",
        "R1",
        "RF-ANY",
        gd.Approval(1),
        key,
        rehearsal_id="rh-live",
    )


@pytest.mark.parametrize("v", [17, 20])
def test_live_snapshot_proof(v, engine, no_xmlrpc, tmp_path, capsys):  # noqa: F811
    import nf_bv_seed as seed

    stack = seed._stack(v)
    if not seed.stack_running(v):
        pytest.skip(f"stack {v} down")
    src, prod_db = f"ingenium_nf_bv_{v}", f"ingenium_nf_clone_snapprod_{v}"
    assert prod_db.startswith("ingenium_nf_")
    ops = DockerOps(stack)
    try:
        _template(stack, src, prod_db)
        prod = _rpc(stack.url, prod_db)
        w = _raw(stack.url, prod_db, prod.uid)
        cat = w("res.partner.category", "create", [{"name": f"nf snap {v}"}])
        ids = [w(M, "create", [{"name": f"nf snap {i}", "ref": f"r{i}"}]) for i in range(60)]
        fp = fpm.read_identity(prod, stack.url, prod_db, v).fingerprint
        vals = {"ref": "snap-new", "category_id": [(6, 0, [cat])]}

        # Route A: proof on batch 1, then batch 2
        sw, g = _gate(engine, w)
        plan = gd.plan_hash(fp, "m:res.partner:change", M, vals, ids)
        ra = bi.RouteA(
            prod,
            w,
            bi.ImageStore(tmp_path / "bi"),
            plan=plan,
            model=M,
            ids=ids,
            values=vals,
            switch_check=lambda: sw.check(fp),
        )
        t0 = time.monotonic()
        rep = g.run(_spec(fp, f"live-{v}-a"), M, ids, vals, **ra.hooks())
        ta = time.monotonic() - t0
        assert rep.status == "done" and rep.written == 60 and bi.verify_proof(ra.proof, plan)
        got = prod(M, "read", [ids, ["ref", "category_id"]])
        assert all(r["ref"] == "snap-new" and r["category_id"] == [cat] for r in got)

        # irreversible field -> L3 path, no write
        with pytest.raises(bi.Irreversible):
            bi.RouteA(
                prod,
                w,
                bi.ImageStore(tmp_path / "bi"),
                plan=plan,
                model=M,
                ids=ids,
                values={"display_name": "x"},
                switch_check=lambda: None,
            )

        # injected concurrent edit during batch 1 -> trip + auto-undo; flagged record kept
        sw, g = _gate(engine, w)
        vals2 = {"ref": "snap-two"}
        plan2 = gd.plan_hash(fp, "m:res.partner:change", M, vals2, ids)

        ra2 = bi.RouteA(
            prod,
            w,
            bi.ImageStore(tmp_path / "bi"),
            plan=plan2,
            model=M,
            ids=ids,
            values=vals2,
            switch_check=lambda: sw.check(fp),
        )
        orig = ra2.readback

        def mismatch(c: Any) -> bool:
            orig(c)
            time.sleep(1.1)  # write_date has 1 s resolution
            w(M, "write", [[ids[3]], {"comment": "user edit"}])  # concurrent human edit
            return False  # injected readback mismatch

        ra2.readback = mismatch
        g2 = g
        rep2 = g2.run(_spec(fp, f"live-{v}-b"), M, ids, vals2, **ra2.hooks())
        assert rep2.status == "tripped" and sw.check(fp) is not None
        refs = {r["id"]: r["ref"] for r in prod(M, "read", [ids, ["ref"]])}
        assert all(refs[i] == "snap-new" for i in ids[:50] if i != ids[3])
        assert refs[ids[51]] == "snap-new"  # batch 2 never written
        assert str(ids[3]) in ra2.conflicts  # write_date moved: human review, not clobbered

        # Route B: dump + filestore, restore-verified on ingenium_scratch_*
        cops = sn.ContainerOps(stack.db_container, stack.odoo_container)
        t0 = time.monotonic()
        snap = sn.take(cops, prod_db, fp, tmp_path / "snap", ["res_partner"])
        assert sn.verify(cops, snap, fp) is None
        tb = time.monotonic() - t0
        b = bytearray(open(snap.dump, "rb").read())
        b[len(b) // 2] ^= 0xFF
        open(snap.dump, "wb").write(bytes(b))
        assert sn.verify(cops, snap, fp).missing == "snapshot-proof"
        left = ops.sql("SELECT count(*) FROM pg_database WHERE datname LIKE 'ingenium_scratch_%'")
        assert left.strip() == "0"
        with capsys.disabled():
            print(
                f"\nOdoo {v}: route A 60 rec (proof+2 batches) {ta:.1f}s; route B take+verify"
                f" {tb:.1f}s; counts {snap.counts}"
            )
    finally:
        ops.sql(f'DROP DATABASE IF EXISTS "{prod_db}" WITH (FORCE)')


@pytest.mark.parametrize("v", [17, 20])
def test_live_full_image_side_effects(v, no_xmlrpc, tmp_path, capsys):  # noqa: F811
    """Write overrides / stored computes change fields outside the plan: captured, surfaced,
    restored by undo, and the full-image proof is withheld (rehearsal stays required)."""
    import nf_bv_seed as seed

    stack = seed._stack(v)
    if not seed.stack_running(v):
        pytest.skip(f"stack {v} down")
    src, db = f"ingenium_nf_bv_{v}", f"ingenium_nf_clone_snapside_{v}"
    ops = DockerOps(stack)
    try:
        _template(stack, src, db)
        prod = _rpc(stack.url, db)
        w = _raw(stack.url, db, prod.uid)
        par = w(
            M,
            "create",
            [{"name": "nf parent", "is_company": True, "street": "Parent St 1", "city": "Pcity"}],
        )
        kids = [
            w(M, "create", [{"name": f"nf kid {i}", "street": f"Own {i}", "city": "Own"}])
            for i in range(5)
        ]

        def mk(vals: dict, ids: list) -> bi.RouteA:
            plan = gd.plan_hash("fp", "m:res.partner:change", M, vals, ids)
            return bi.RouteA(
                prod,
                w,
                bi.ImageStore(tmp_path / "bi"),
                plan=plan,
                model=M,
                ids=ids,
                values=vals,
                switch_check=lambda: None,
            )

        # 1) parent_id write: Odoo syncs the parent's address over street/city
        ra = mk({"parent_id": par}, kids)
        _, img = ra.before_image(kids)
        w(M, "write", [kids, {"parent_id": par}])
        synced = all(r["street"] == "Parent St 1" for r in prod(M, "read", [kids, ["street"]]))
        assert ra.readback(kids), ra.log  # proof: full-image undo + re-apply
        assert "commercial_partner_id" in ra.outside_plan  # stored compute, every version
        assert not synced or {"street", "city"} <= ra.outside_plan
        assert not ra.check("full-image-proof") and ra.check("batch1-undo-proof")
        print(f"\nOdoo {v}: parent_id side effects {sorted(ra.outside_plan)}")
        assert ra.undo(img), ra.log
        got = {r["id"]: r for r in prod(M, "read", [kids, ["street", "city", "parent_id"]])}
        assert all(
            got[k]["street"] == f"Own {i}" and got[k]["parent_id"] is False
            for i, k in enumerate(kids)
        )

        # 2) name write: stored compute (complete_name / commercial fields) changes too
        meta = prod(M, "fields_get", [["complete_name"]], {"attributes": ["store"]})
        if not meta.get("complete_name", {}).get("store"):
            pytest.skip("complete_name not stored on this version")
        ra2 = mk({"name": "nf renamed"}, kids[:2])
        _, img2 = ra2.before_image(kids[:2])
        w(M, "write", [kids[:2], {"name": "nf renamed"}])
        assert ra2.readback(kids[:2]), ra2.log
        assert "complete_name" in ra2.outside_plan
        assert ra2.undo(img2), ra2.log
        got = prod(M, "read", [kids[:2], ["name", "complete_name"]])
        assert [r["complete_name"] for r in got] == ["nf kid 0", "nf kid 1"]
    finally:
        ops.sql(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)')
