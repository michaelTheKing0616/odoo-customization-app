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


# ---------------------------------------------------------------- H4 tautological Python domains
ACL = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\na,a,model_a_a,base.group_user,1,1,1,1\n"


def _m(body, pre=""):
    return {"models/a.py": PH + pre + "class A(models.Model):\n    _name = 'a.a'\n    _description = 'a'\n\n    def f(self, ids=None):\n"
            + "".join("        " + ln + "\n" for ln in body.split("\n")), "security/ir.model.access.csv": ACL}


@pytest.mark.parametrize("body,pre", [
    ("self.env['res.partner'].search([['id', '!=', 0]]).write({'active': False})", ""),  # review probe
    ("self.env['res.partner'].search([(1, '=', 1)]).unlink()", ""),
    ("self.env['res.partner'].search([[1, '=', 1]]).unlink()", ""),
    ("self.env['res.partner'].search(['|', ('id', '=', 0), ('id', '!=', 0)]).unlink()", ""),
    ("self.env['res.partner'].search([('id', '>', 0)]).unlink()", ""),
    ("self.env['res.partner'].search([('create_date', '!=', False)]).write({'active': False})", ""),
    ("dom = [('id', '!=', False)]\nself.env['res.partner'].search(dom).unlink()", ""),
    ("self.env['res.partner'].search(ALL).unlink()", "ALL = [(1, '=', 1)]\n"),
    ("self.env['res.partner'].search(everything()).unlink()", "def everything():\n    return [('id', '>=', 1)]\n"),
    ("self.env['res.partner'].search(expression.AND([[], [('id', '!=', 0)]])).unlink()", "from odoo.osv import expression\n"),
    ("self.env['res.partner'].search([('active', 'in', [True, False])] + []).unlink()", ""),
])
def test_h4_tautology_domain_mass_change(body, pre):
    assert _sev(_m(body, pre), "mass-change")


@pytest.mark.parametrize("body", [
    "self.env['res.partner'].search([('state', '=', 'draft')]).unlink()",
    "self.env['res.partner'].search([('id', 'in', ids)]).unlink()",
    "self.env['res.partner'].search(['|', ('id', '=', 0), ('name', '=', 'x')]).unlink()",
    "domain = []\ndomain.append(('company_id', '=', self.env.company.id))\nself.env['res.partner'].search(domain).unlink()",
    "self.env['res.partner'].search([('id', '!=', self.id), ('parent_id', '=', self.id)]).write({'active': False})",
    "self.env['res.partner'].search(expression.AND([[('id', '!=', 0)], [('user_id', '=', self.env.uid)]])).unlink()",
])
def test_h4_benign_domain_silent(body):
    assert not _sev(_m(body, "from odoo.osv import expression\n"), "mass-change")


# ---------------------------------------------------------------- L1 str*int padding in SQL
@pytest.mark.parametrize("sql", [
    "'UPDATE res_users SET x=' + 'a' * 200000",  # review probe
    "'UPDATE res_users SET x=' + 200000 * 'a'",
    "'DELETE FROM ir_model_access WHERE ' + ' ' * 9999 + '1=1'",
])
def test_l1_padded_core_dml_high(sql):
    assert "high" in _sev(_m(f"self.env.cr.execute({sql})"), "core-table-dml")


def test_l1_benign_padding_silent():
    assert not _sev(_m("self.env.cr.execute('SELECT ' + '1,' * 3 + '1')"), "core-table-dml")
