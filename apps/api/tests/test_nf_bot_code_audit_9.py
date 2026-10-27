"""CODE-AUDIT-9: the 12 findings of REVIEW-CODE-AUDIT-7 (7 HIGH / 4 MEDIUM / 1 LOW).
Each: the review probe, >=2 variants, and a benign stock-like shape that must stay quiet."""
import pytest

from tests.test_nf_bot_code_audit_5 import codes

PH = "from odoo import models, fields, api, http\nfrom odoo.http import request\n"
RT = "class C(http.Controller):\n    @http.route('/p', auth='public')\n    def p(self, i=0, **kw):\n"
U = "request.env['res.users'].sudo().browse(2)"


def _r(body, pre=""):
    return {"models/a.py": PH + pre + RT + "".join("        " + ln + "\n" for ln in body.split("\n"))}


def _sev(files, code):
    return {s for c, s in codes(files) if c == code}


# ---------------------------------------------------------------- H3 helper-return secret read
@pytest.mark.parametrize("files", [
    _r(f"return g({U})", pre="def g(r):\n    return r.password\n"),  # review probe
    _r(f"return g({U})", pre="def g(r):\n    return r['password']\n"),
    _r(f"return h({U})", pre="def g(r):\n    return getattr(r, 'api_' + 'key')\ndef h(r):\n    return g(r)\n"),
])
def test_h3_helper_return_secret_high(files):
    assert "high" in _sev(files, "route-secret-read")


# ---------------------------------------------------------------- H1/H2 dynamic secret reads
@pytest.mark.parametrize("body", [
    f"return {U}['password']",
    f"fld = 'pass' + 'word'\nreturn {U}[fld]",
    f"return getattr({U}, 'pass' + 'word')",
    f"return {U}.read(['login', 'password'])[0].get('password')",
    f"return {U}.read(['password'])",
    "return request.env['res.users'].sudo().search([]).mapped('totp_secret')",
    f"u = {U}\nreturn u['api_key']",
])
def test_h1_h2_dynamic_secret_high(body):
    assert "high" in _sev(_r(body), "route-secret-read")


@pytest.mark.parametrize("body", [
    "return kw['password'] and kw.get('password')",  # auth_signup: the submitted form value, not a stored secret
    f"return {U}['login']",
    f"return getattr({U}, 'name')",
])
def test_h1_h2_benign_silent(body):
    assert not _sev(_r(body), "route-secret-read")


# ---------------------------------------------------------------- M4 attachment IDOR
@pytest.mark.parametrize("body", [
    "return request.env['ir.attachment'].sudo().browse(int(i)).raw",  # review probe
    "a = request.env['ir.attachment'].sudo().browse(int(i))\nreturn a.datas",
    "return request.env['ir.attachment'].sudo().search([('id', '=', int(i))]).read(['datas'])",
])
def test_m4_attachment_idor_medium(body):
    assert "medium" in _sev(_r(body), "route-attachment-idor")


@pytest.mark.parametrize("body", [
    # stock portal/mail shape: access_token checked with consteq
    "a = request.env['ir.attachment'].sudo().browse(int(i))\nif not consteq(a.access_token or '', kw.get('access_token', '')):\n    return ''\nreturn a.raw",
    "return request.env['ir.attachment'].browse(int(i)).raw",  # no sudo: ACLs apply
    "return request.env['ir.attachment'].sudo().browse(7).raw",  # fixed id
])
def test_m4_benign_silent(body):
    assert not _sev(_r(body), "route-attachment-idor")
