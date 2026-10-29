"""Round 9 GATE 1 live regression: a module data file that edits a stock record rule and a stock
access row is refused by the sandbox checks even with the audit bypassed (ODOO_LIVE=1 only)."""

from __future__ import annotations

import copy
import io
import os
import secrets
import zipfile

import pytest

from app.bots import code_audit as ca
from app.bots import module_test_gate as g
from app.bots import req2mod as rm

pytestmark = pytest.mark.skipif(
    os.environ.get("ODOO_LIVE") != "1" or os.environ.get("INGENIUM_LIVE_INFRA") != "1",
    reason="live Odoo sandbox: set ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1",
)
MOD = "x_gate_live"
EDIT = (
    b'<?xml version="1.0"?>\n<odoo>\n'
    b'<record id="base.res_partner_rule" model="ir.rule">\n'
    b"<field name=\"domain_force\">[(1, '=', 1)]</field>\n</record>\n"
    b'<record id="base.access_res_partner_group_user" model="ir.model.access">\n'
    b'<field name="perm_unlink" eval="True"/>\n</record>\n</odoo>\n'
)


@pytest.mark.parametrize("v", [17, 19])
def test_stock_rule_and_access_edit_refused(v, monkeypatch):
    from module_generator import build_module_zip

    from tests.test_nf_bot_req2mod import ASSETS, BASE

    monkeypatch.setenv(g.KEY_ENV, secrets.token_hex(32))
    r = rm.build(copy.deepcopy(ASSETS), version=v, installed_modules=BASE, technical_name=MOD)
    z = zipfile.ZipFile(io.BytesIO(build_module_zip(r.spec)))
    f = {n.split("/", 1)[1]: z.read(n) for n in z.namelist() if not n.endswith("/")}
    f["data/stock_edit.xml"] = EDIT
    m = f["__manifest__.py"].decode()
    q = next(q for q in ('"data": [', "'data': [") if q in m)
    f["__manifest__.py"] = m.replace(q, q + "\n        'data/stock_edit.xml',", 1).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zz:
        for p, b in f.items():
            zz.writestr(f"{MOD}/{p}", b)
    hi = ca.audit(buf.getvalue(), version=v, owned_names={MOD}).findings
    assert [x.severity for x in hi if x.code == "foreign-record-edit"] == [ca.HIGH, ca.HIGH]
    checks = {"audit": g.Check(g.PASS, "bypassed"), "upgrade": g.Check(g.NA, "fresh")}
    sb = g._Sandbox(g.DockerRunner(), v, MOD, os.path.realpath("/tmp"), g.STEP_TIMEOUT)
    try:
        sb.start()
        g._sandbox_checks(sb, f, None, v, checks, g.role_spec_from(r.spec, MOD))
    finally:
        sb.close()
    c = checks["install"]
    assert c.status == g.FAIL and "stock security edited" in c.detail
    assert "access row" in c.detail and "record rule" in c.detail
