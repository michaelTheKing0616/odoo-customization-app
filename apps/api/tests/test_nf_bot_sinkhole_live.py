"""BOT-SINKHOLE live: Odoo 17 + 20 over JSON-RPC only (Odoo 20 has no XML-RPC).

Needs ODOO_LIVE=1 and the nf sandbox stacks (ports 18117 / 18120, DB ingenium_nf_bv_<v> with
crm + base_automation, admin/admin). A test-side writer seeds one automation rule that emails
on every lead write; the sinkhole must hold that email, restore the queue cron, and release
it exactly once.
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

from app.bots import sinkhole as sk
from tests.test_nf_bot_kill_audit import OWNER
from tests.test_nf_bot_sinkhole import Switch

ME = sk.SessionActor(OWNER, "live-session-0001")

LIVE = os.environ.get("ODOO_LIVE") == "1"
pytestmark = [pytest.mark.no_app_db, pytest.mark.skipif(not LIVE, reason="live: ODOO_LIVE=1")]
EVIDENCE = Path.home() / ".ingenium_nf" / "nfwt" / "BOT-SINKHOLE_live.txt"
PORTS = {17: 18117, 19: 18119, 20: 18120}


class Json:
    def __init__(self, v: int) -> None:
        self.url, self.db = f"http://127.0.0.1:{PORTS[v]}", f"ingenium_nf_bv_{v}"
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
            raise RuntimeError(out["error"].get("data", {}).get("message", "rpc error"))
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


def test_live_hold_restore_release_once(odoo) -> None:
    v, o = odoo
    seed = o  # test-side writer (the code under test writes only through _qwrite / quiet)
    tag = uuid.uuid4().hex[:8]
    mid = seed("ir.model", "search", [[("model", "=", "crm.lead")]])[0]
    tpl = seed(
        "mail.template",
        "create",
        [
            {
                "name": f"sink {tag}",
                "model_id": mid,
                "subject": "hello",
                "email_to": "x@example.invalid",
                "body_html": "<p>hi</p>",
            }
        ],
    )
    afields = seed("ir.actions.server", "fields_get", [], {"attributes": ["type"]})
    act = {"name": f"sink act {tag}", "model_id": mid, "state": "mail_post", "template_id": tpl}
    if "mail_post_method" in afields:
        act["mail_post_method"] = "email"
    rule = seed(
        "base.automation",
        "create",
        [{"name": f"sink rule {tag}", "model_id": mid, "trigger": "on_create_or_write"}],
    )
    act["base_automation_id"] = rule
    seed("ir.actions.server", "create", [act])
    lead = seed("crm.lead", "create", [{"name": f"sink lead {tag}"}])
    pid = seed("res.partner", "create", [{"name": f"sink f {tag}", "email": "f@example.invalid"}])
    seed("crm.lead", "message_subscribe", [[lead]], {"partner_ids": [pid]})
    sw = Switch()
    h = sk.Sinkhole(o, sw, f"live{v}", o.uid)
    try:
        s = h.scan("crm.lead", "write", {"name": "y"}, [lead])
        assert s.verdict == "ok" and any(c.kind == "hold" for c in s.channels), s
        t0 = time.time()
        assert h.open(s, 1) is None and h.paused
        crons = o("ir.cron", "read", [h.paused], {"fields": ["active"]})
        assert not any(c["active"] for c in crons)
        h.quiet(o)("crm.lead", "write", [[lead], {"name": f"sink lead {tag} 2"}], None)
        assert h.after_batch(), h.report
        rep = h.close()
        assert rep.clean and rep.crons_restored and len(rep.held_mail) >= 1
        mail = o("mail.mail", "read", [h.ledger.mail_ids], {"fields": ["state", "failure_reason"]})
        assert all(m["state"] == "cancel" for m in mail)
        assert all(
            c["active"]
            for c in o(
                "ir.cron", "read", [crons and [c["id"] for c in crons]], {"fields": ["active"]}
            )
        )
        first = h.decide(h.ledger, ME, False)
        assert first["done"] and not h.decide(h.ledger, ME, False)["done"]
        assert not o("ir.config_parameter", "search", [[("key", "=", sk.LEASE_KEY)]])
        # negative: the write runs WITHOUT the quiet flags; mail must still be held or caught
        h2 = sk.Sinkhole(o, sw, f"live{v}", o.uid)
        assert h2.open(h2.scan("crm.lead", "write", {}, [lead]), 1) is None
        o("crm.lead", "write", [[lead], {"name": f"sink lead {tag} 3"}])
        neg_ok = h2.after_batch()
        rep2 = h2.close()
        assert (neg_ok and rep2.held_mail) or rep2.escaped, rep2
        assert rep2.crons_restored or rep2.unheld
        neg = "held" if neg_ok else f"escaped-detected {rep2.escaped}"
        if not neg_ok:
            sw.on = None  # sandbox: the switch tripped as designed
        if h2._lease_id is None:
            h2.decide(h2.ledger, ME, False)
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        with EVIDENCE.open("a") as fh:
            fh.write(
                f"odoo {v}: held={len(rep.held_mail)} restored={rep.crons_restored} "
                f"discard_once=ok unflagged={neg} {time.time() - t0:.1f}s | {rep.text()}\n"
            )
    finally:
        seed("base.automation", "write", [[rule], {"active": False}])
