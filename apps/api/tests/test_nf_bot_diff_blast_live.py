"""BOT-DIFF-BLAST live: Odoo 17 + 20 over JSON-RPC only (Odoo 20 has no XML-RPC).

Needs ODOO_LIVE=1. Stacks: NF2_LIVE_URL_<v> (default http://127.0.0.1:182<v>, ports
18217-18220 only), DB ingenium_nf2_blast_<v> with ``account`` installed, admin/admin.
Fixtures are seeded by a test-side writer; the code under test only reads.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.bots import blast as bl
from app.bots import diff as df
from app.bots.risk import rules

LIVE = os.environ.get("ODOO_LIVE") == "1"
pytestmark = [pytest.mark.no_app_db, pytest.mark.skipif(not LIVE, reason="live: ODOO_LIVE=1")]
EVIDENCE = Path.home() / ".ingenium_nf" / "nfwt" / "BOT-DIFF-BLAST_live.txt"


class Json:
    def __init__(self, v: int) -> None:
        self.url = os.environ.get(f"NF2_LIVE_URL_{v}", f"http://127.0.0.1:182{v}")
        port = int(self.url.rsplit(":", 1)[1])
        assert 18217 <= port <= 18220, "nf2 live ports only"
        self.db = f"ingenium_nf2_blast_{v}"
        self.uid = self._call("common", "login", [self.db, "admin", "admin"])
        assert self.uid

    def _call(self, service: str, method: str, args: list) -> Any:
        body = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": 1,
            "params": {"service": service, "method": method, "args": args},
        }
        req = urllib.request.Request(
            f"{self.url}/jsonrpc", json.dumps(body).encode(), {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 - local sandbox
            out = json.loads(r.read())
        if "error" in out:
            raise RuntimeError(out["error"].get("data", {}).get("name", "rpc error"))
        return out["result"]

    def __call__(self, model, method, args, kw=None) -> Any:
        return self._call(
            "object",
            "execute_kw",
            [self.db, self.uid, "admin", model, method, list(args), kw or {}],
        )


@pytest.fixture(scope="module", params=[17, 20])
def odoo(request):
    return request.param, Json(request.param)


def _seed(o: Json) -> dict[str, int]:
    tag = uuid.uuid4().hex[:6]
    a = o("res.partner", "create", [{"name": f"nf2 A {tag}", "is_company": True}])
    b = o(
        "res.partner",
        "create",
        [{"name": f"nf2 B {tag}", "parent_id": a, "email": "b@example.com"}],
    )
    num = (
        "account_number"
        if "account_number" in o("res.partner.bank", "fields_get", [], {"attributes": ["type"]})
        else "acc_number"
    )  # Odoo 20 renamed it
    bank = o("res.partner.bank", "create", [{num: f"NF2{tag}", "partner_id": b}])
    return {"a": a, "b": b, "bank": bank}


def test_live_diff_readback_and_stale(odoo) -> None:
    v, o = odoo
    ids = _seed(o)
    vals = {"email": "new@example.com"}
    d = df.build_diff(o, "res.partner", [ids["b"]], vals)
    assert [(e.field, e.old, e.new) for e in d.entries] == [
        ("email", "b@example.com", "new@example.com")
    ]
    p = bl.preview(
        o, "res.partner", [ids["b"]], vals, op="write", cls="R1", subkind=None, route="A"
    )
    rb = df.readback(o, d, vals)
    assert rb([ids["b"]]) is False
    time.sleep(1.1)  # write_date has 1 s precision
    o("res.partner", "write", [[ids["b"]], {"name": "edited by someone"}])  # unplanned field
    again = bl.preview(
        o, "res.partner", [ids["b"]], vals, op="write", cls="R1", subkind=None, route="A"
    )
    assert again.payload_hash != p.payload_hash  # stale approval detectable
    o("res.partner", "write", [[ids["b"]], vals])
    assert rb([ids["b"]]) is True


def test_live_blast_partner_cascade_and_move_restrict(odoo) -> None:
    v, o = odoo
    ids = _seed(o)
    b = bl.build_blast(o, "res.partner", [ids["a"]], "unlink")
    assert not isinstance(b, rules.Refusal), b
    p = b.payload()
    par = o(
        "ir.model.fields",
        "search_read",
        [[("model", "=", "res.partner"), ("name", "=", "parent_id")]],
        {"fields": ["on_delete"]},
    )[0]["on_delete"]
    if par == "cascade":
        assert {ids["a"], ids["b"]} <= set(p["ids"]["res.partner"])
    else:
        assert p["nulled"].get("res.partner.parent_id", 0) >= 1
    bb = bl.build_blast(o, "res.partner", [ids["b"]], "unlink").payload()
    assert ids["bank"] in bb["ids"].get("res.partner.bank", [])
    assert p["low_count"]  # res.partner is mail.thread
    assert any(bl.RULE_HIDE in r for r in p["low_count"])  # partner multi-company ir.rule
    assert p["versions"]["res.partner"][0][0] == ids["a"]
    od = o(
        "ir.model.fields",
        "search_read",
        [[("model", "=", "account.move"), ("name", "=", "partner_id")]],
        {"fields": ["on_delete"]},
    )[0]["on_delete"]
    journal = o("account.journal", "search", [[("type", "=", "general")]], {"limit": 1})
    o(
        "account.move",
        "create",
        [{"partner_id": ids["b"], "journal_id": journal[0], "move_type": "entry"}],
    )
    r = bl.preview(
        o, "res.partner", [ids["a"]], None, op="unlink", cls="R6", subkind="delete", route="A"
    )
    if od == "restrict":
        assert isinstance(r, rules.Refusal) and "restrict" in r.reason
        assert "account.move." in r.reason
    else:
        assert not isinstance(r, rules.Refusal) and r.tier.tier == 3
    w = bl.preview(
        o,
        "res.partner",
        [ids["a"], ids["b"]],
        {"comment": "x"},
        op="write",
        cls="R1",
        subkind=None,
        route="A",
    )
    with EVIDENCE.open("a") as fh:
        fh.write(
            f"odoo{v} unlink A: per_model={p['per_model']} nulled={p['nulled']} "
            f"links={p['links']} companies={p['companies']} users={p['users']} "
            f"total={p['total']} | unlink B: {bb['per_model']} | move.partner_id on_delete={od} -> "
            f"{getattr(r, 'reason', 'counted')} | write 2: tier L{w.tier.tier}\n"
        )


def test_live_access_error_is_rf_r6(odoo) -> None:
    v, o = odoo
    login = f"nf2_portal_{uuid.uuid4().hex[:6]}"
    o(
        "res.users",
        "create",
        [
            {
                "name": login,
                "login": login,
                "password": login,
                "groups_id" if v < 19 else "group_ids": [
                    (
                        6,
                        0,
                        [o("ir.model.data", "check_object_reference", ["base", "group_portal"])[1]],
                    )
                ],
            }
        ],
    )
    low = Json.__new__(Json)
    low.url, low.db = o.url, o.db
    low.uid = low._call("common", "login", [low.db, login, login])
    low_call = lambda m, meth, a, k=None: low._call(  # noqa: E731
        "object", "execute_kw", [low.db, low.uid, login, m, meth, list(a), k or {}]
    )
    r = bl.build_blast(low_call, "res.partner", [1], "unlink")
    assert isinstance(r, rules.Refusal) and r.rule == "RF-R6"
