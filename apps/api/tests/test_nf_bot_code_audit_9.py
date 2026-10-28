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


# CA13 H1: exact matches on non-unique fields (state/name/company_id/user_id) are now mass changes
# (see test_13); the benign twins use unique keys instead
@pytest.mark.parametrize("body", [
    "self.env['res.partner'].search([('id', '=', 5)]).unlink()",
    "self.env['res.partner'].search([('id', 'in', ids)]).unlink()",
    "self.env['res.partner'].search(['|', ('id', '=', 0), ('id', '=', 3)]).unlink()",
    "domain = []\ndomain.append(('id', '=', self.id))\nself.env['res.partner'].search(domain).unlink()",
    "self.env['res.partner'].search([('id', '!=', self.id), ('parent_id', '=', self.id)]).write({'active': False})",
    "self.env['res.partner'].search(expression.AND([[('id', '!=', 0)], [('id', 'in', self.ids)]])).unlink()",
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


# ---------------------------------------------------------------- JS helpers
def _js(body):
    return {"static/src/a.js": "export async function f(orm, rpc, env, axios) {\n" + body + "\n}\n"}


def _owl(src):
    return {"static/src/a.js": "import { Component, xml } from '@odoo/owl';\n" + src + "\n"}


# ---------------------------------------------------------------- H5 tautological JS domains
@pytest.mark.parametrize("body", [
    "await orm.unlink('res.partner', await orm.search('res.partner', [['id', '!=', 0]]));",  # review probe
    "await orm.unlink('res.partner', await orm.search('res.partner', [[1, '=', 1]]));",
    "await orm.unlink('res.partner', await orm.search('res.partner', ['|', ['id', '=', 0], ['id', '!=', 0]]));",
    "const D = [['create_date', '!=', false]]; await orm.write('res.partner', await orm.search('res.partner', D), {active: false});",
    "const all = () => [['id', '>', 0]]; await orm.unlink('res.partner', await orm.search('res.partner', all()));",
    "await orm.unlink('res.partner', await orm.search('res.partner', Domain.and([[], [['id', '!=', false]]]).toList()));",
])
def test_h5_js_tautology_mass_change(body):
    assert "high" in _sev(_js(body), "js-mass-change")


@pytest.mark.parametrize("body", [
    "await orm.unlink('res.partner', await orm.search('res.partner', [['state', '=', 'draft']]));",
    "await orm.unlink('res.partner', await orm.search('res.partner', ['|', ['id', '=', 0], ['name', '=', 'x']]));",
    "const d = []; d.push(['company_id', '=', 1]); await orm.unlink('res.partner', await orm.search('res.partner', d));",
    "await orm.unlink('res.partner', this.props.record.resIds);",  # stock list-view delete: selected ids
])
def test_h5_benign_silent(body):
    assert not _sev(_js(body), "js-mass-change")


# ---------------------------------------------------------------- H6 raw HTTP to ORM endpoints
BODY_W = "JSON.stringify({jsonrpc: '2.0', params: {model: 'res.users', method: 'write', args: [[2], {groups_id: [[4, 1]]}], kwargs: {}}})"
BODY_U = "JSON.stringify({params: {model: 'res.partner', method: 'unlink', args: [await orm.search('res.partner', [])], kwargs: {}}})"


@pytest.mark.parametrize("body,code", [
    (f"await fetch('/web/dataset/call_kw', {{method: 'POST', body: {BODY_W}}});", "js-sensitive-model"),  # review probe
    (f"const x = new XMLHttpRequest(); x.open('POST', '/web/dataset/call_kw'); x.send({BODY_U});", "js-mass-change"),
    (f"navigator.sendBeacon('/web/dataset/call_kw/res.users/write', {BODY_W});", "js-sensitive-model"),
    (f"await axios.post('/web/dataset/call_button', {BODY_W});", "js-sensitive-model"),
    ("await fetch('/jsonrpc', {method: 'POST', body: JSON.stringify({params: {service: 'object', method: 'execute' + '_kw',"
     " args: ['db', 2, 'pw', 'res.users', 'write', [[2], {groups_id: [[4, 1]]}]]}})});", "js-sensitive-model"),
])
def test_h6_raw_http_orm_high(body, code):
    assert "high" in _sev(_js(body), code)


def test_h6_runtime_body_flagged_medium():
    assert "medium" in _sev(_js("await fetch('/web/dataset/call_kw', {method: 'POST', body: makeBody()});"), "js-raw-orm-request")


@pytest.mark.parametrize("body", [
    # stock shapes: reading partners through call_kw, and fetches to non-ORM routes
    "await fetch('/web/dataset/call_kw', {method: 'POST', body: JSON.stringify({params: {model: 'res.partner', method: 'read', args: [[1], ['name']], kwargs: {}}})});",
    "await fetch('/web/image/res.partner/1/avatar_128');",
    "navigator.sendBeacon('/website/track', JSON.stringify({a: 1}));",
])
def test_h6_benign_silent(body):
    found = {c for c, s in codes(_js(body)) if s in ("high", "medium")}
    assert not found & {"js-sensitive-model", "js-mass-change", "js-raw-orm-request"}


# ---------------------------------------------------------------- H7 resolver beyond plain const
@pytest.mark.parametrize("body", [
    "const [ids] = [await orm.search('res.partner', [])]; await orm.unlink('res.partner', ids);",  # review probe
    "const {ids} = {ids: await orm.search('res.partner', [])}; await orm.unlink('res.partner', ids);",
    "const ids = await orm.search('res.partner', []); await orm.unlink('res.partner', [...ids]);",
    "const ids = await orm.search('res.partner', []); await orm.unlink('res.partner', cond ? ids : ids);",
    "let a, b; [a, b] = [await orm.search('res.partner', []), 1]; await orm.unlink('res.partner', a);",
    "const {ids: {list}} = {ids: {list: await orm.search('res.partner', [])}}; await orm.write('res.partner', list, {active: false});",
])
def test_h7_destructured_flows_high(body):
    assert "high" in _sev(_js(body), "js-mass-change")


@pytest.mark.parametrize("body", [
    "const [ids] = [await orm.search('res.partner', [['parent_id', '=', 7]])]; await orm.unlink('res.partner', ids);",
    "const {resIds} = this.props; await orm.unlink('res.partner', resIds);",
])
def test_h7_benign_silent(body):
    assert not _sev(_js(body), "js-mass-change")


# ---------------------------------------------------------------- M1 entity-encoded javascript: in OWL
@pytest.mark.parametrize("tpl", [
    "<a t-att-href=\"'java&#115;cript:alert(1)'\">x</a>",  # review probe
    "<a href=\"&#x6A;avascript&#58;alert(1)\">x</a>",
    "<a href=\"javascript&colon;alert(1)\">x</a>",
    "<a href=\"java&amp;#115;cript:alert(1)\">x</a>",
])
def test_m1_entity_js_url(tpl):
    assert _sev(_owl("class A extends Component { static template = xml`" + tpl + "`; }"), "owl-js-url") & {"medium", "high"}


def test_m1_benign_entities_silent():
    tpl = "<a href=\"/shop?a=1&amp;b=2\" t-att-title=\"'Tom &amp; Jerry'\">x</a>"
    assert not _sev(_owl("class A extends Component { static template = xml`" + tpl + "`; }"), "owl-js-url")


# ---------------------------------------------------------------- M2 static template = string variable
@pytest.mark.parametrize("src", [
    "const T = `<a href=\"javascript:alert(1)\">x</a>`; class A extends Component { static template = T; }",  # review probe
    "const T = '<a href=\"javascript:alert(1)\">x</a>'; class A extends Component { static template = T; }",
    "class A extends Component { static template = '<div>' + '<a href=\"javascript:alert(1)\">x</a></div>'; }",
    "class A extends Component {}\nA.template = `<iframe src=\"javascript:alert(1)\"/>`;",
])
def test_m2_string_template_analysed(src):
    assert "high" in _sev(_owl(src), "owl-js-url")


def test_m2_benign_template_name_silent():
    src = "const T = 'web.MyTemplate'; class A extends Component { static template = T; }\nclass B extends Component { static template = `<a href=\"/web\">x</a>`; }"
    assert not _sev(_owl(src), "owl-js-url")


# ---------------------------------------------------------------- M3 decoded request targets
@pytest.mark.parametrize("body", [
    "await fetch(atob('aHR0cHM6Ly9lLnYv'));",  # review probe: decodes to https://e.v/
    "await fetch(window.atob('aHR0cHM6Ly9lLnYv') + 'x');",
    "await fetch(decodeURIComponent('https%3A%2F%2Fe.v%2F'));",
])
def test_m3_decoded_external_request(body):
    # a deterministic decoder of a literal is the literal: graded like fetch('https://e.v/') (HIGH >= MEDIUM)
    assert _sev(_js(body), "js-external-request") & {"medium", "high"}


def test_m3_benign_decoded_local_silent():
    assert not _sev(_js("await fetch(atob('L3dlYi9pbWFnZQ=='));"), "js-external-request")  # '/web/image'


def test_h4_batched_search_is_bounded():
    # stock mail/models/mail_push.py: cron cleans one batch, not the table
    body = "recs = self.sudo().search_fetch([], ['payload'], limit=50)\nrecs.unlink()"
    assert not _sev(_m(body), "mass-change")
    assert _sev(_m("self.env['res.partner'].search([(1, '=', 1)], limit=None).unlink()"), "mass-change")
