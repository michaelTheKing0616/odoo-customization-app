"""CODE-AUDIT-11: REVIEW-CODE-AUDIT-8 (12H/5M/2L) closed by root-cause inversion: a sink is safe
only when its recordset / field / URL / SQL is provably bounded. Each finding: the review probe,
>=3 variants and a benign stock-like shape."""
import pytest

from tests.test_nf_bot_code_audit_5 import codes

PH = "from odoo import models, fields, api, http\nfrom odoo.http import request\nfrom odoo.osv import expression\nimport json\n"
MH = "class A(models.Model):\n    _name = 'a.a'\n    _description = 'a'\n\n    def f(self, ids=None):\n"


def _m(body, pre=""):
    return {"models/a.py": PH + pre + MH + "".join("        " + ln + "\n" for ln in body.split("\n"))}


def _sev(files, code):
    return {s for c, s in codes(files) if c == code}


P = "self.env['res.partner']"


# ---------------------------------------------------------------- H4 limit= does not bound
@pytest.mark.parametrize("body", [
    f"{P}.search([], limit=10**9).unlink()",  # review probe
    f"n = None\n{P}.search([], limit=n).unlink()",
    f"{P}.search([], limit={P}.search_count([])).unlink()",
    f"{P}.search([], 0, 10**9).unlink()",
    f"while True:\n    r = {P}.search([], limit=100)\n    if not r:\n        break\n    r.unlink()",
])
def test_h4_dynamic_limit_mass_change(body):
    assert "high" in _sev(_m(body), "mass-change")


# ---------------------------------------------------------------- H5 unprovable domains deny by default
@pytest.mark.parametrize("body", [
    f"{P}.search(json.loads('[]')).unlink()",  # review probe
    f"{P}.search(expression.TRUE_DOMAIN).unlink()",
    f"{P}.search(['!', ('id', '=', 0)]).unlink()",
    f"{P}.search(['|', ('active', '=', True), ('active', '=', False)]).unlink()",
    f"{P}.search([('name', '!=', 'zz-never')]).unlink()",
    f"{P}.search([('id', '=like', '%')]).unlink()",
    f"{P}.search([('display_name', 'ilike', '')]).unlink()",
    "self.env['account.move'].search([('state', 'in', ['draft', 'posted', 'cancel'])]).unlink()",
    f"{P}.search(['|', ('ref', '=', self.name), ('ref', '!=', self.name)]).unlink()",
    f"{P}.search(ids).unlink()",  # a parameter domain is unprovable
])
def test_h5_unprovable_domain_high(body):
    assert "high" in _sev(_m(body), "mass-change")


# ---------------------------------------------------------------- H6 derived recordsets inherit
@pytest.mark.parametrize("body", [
    f"{P}.search([]).filtered(lambda r: True).unlink()",  # review probe
    f"{P}.browse({P}._search([])).unlink()",
    f"{P}.browse([r['id'] for r in {P}.search_read([], ['id'])]).unlink()",
    f"{P}.search([('id', 'in', {P}._search([]))]).unlink()",
    f"{P}.sudo().search([]).mapped('child_ids').unlink()",
    f"{P}.search([])._write({{'active': False}})",
    f"recs = {P}.search([('id', '!=', 0)])\nfor r in recs:\n    r.unlink()",
    f"m = getattr({P}, 'unl' + 'ink')\nm({P}.search([]))",
])
def test_h6_derived_recordset_high(body):
    assert "high" in _sev(_m(body), "mass-change")


# ---------------------------------------------------------------- benign: provably bounded (stock shapes)
@pytest.mark.parametrize("body", [
    "self.unlink()",
    "self.filtered(lambda r: r.state == 'draft').write({'state': 'cancel'})",
    "self.env['mail.activity'].search([('res_model', '=', self._name), ('res_id', 'in', self.ids)]).unlink()",
    "domain = [('calendar_id', 'in', self.ids)]\ndomain = expression.AND([domain, [('x', '=', 1)]]) if ids else domain\n"
    "self.env['resource.calendar.leaves'].search(domain).write({'x': 2})",
    "m = self.env['discuss.channel.member'].search([('channel_id', '=', self.id), ('partner_id', '=', 1) if ids else ('guest_id', '=', 2)])\nm.unlink()",
    f"{P}.search([('id', '=', 3)], limit=1).unlink()",
    "self.env['account.move.line'].browse(ids).unlink()",
    "vals = {}\nfor r in self.env['x.y'].search_read([], ['a']):\n    vals.update(r)",
    "d = [('state', '=', 'confirmed'), ('bom_id', '=', self.id)]\nd.append(('product_id', '!=', 5))\nself.env['mrp.production'].search(d).write({'a': 1})",
])
def test_bounded_recordsets_silent(body):
    assert not _sev(_m(body), "mass-change")


# ---------------------------------------------------------------- H12 server action / cron
SA = ("<odoo><record id='s' model='ir.actions.server'><field name='name'>s</field><field name='model_id' ref='base.model_res_partner'/>"
      "<field name='state'>code</field><field name='code'>{}</field></record></odoo>")
MANV = "{'name':'x','version':'17.0.1.0.0','depends':['base'],'license':'LGPL-3','data':['views/v.xml']}"


@pytest.mark.parametrize("code", [
    "env['res.partner'].search([], limit=10**9).unlink()",  # review probe
    "model.search([('name','!=','zz')]).unlink()",
    "env['res.partner'].search(['!',('id','=',0)]).write({'active': False})",
    "for r in env['res.partner'].search([('id','&gt;',0)]):\n    r.unlink()",
])
def test_h12_server_mass_change_high(code):
    assert "high" in _sev({"views/v.xml": SA.format(code)}, "server-mass-change") or \
        "high" in {s for c, s in codes({"views/v.xml": SA.format(code)}, MANV) if c == "server-mass-change"}


def test_h12_bounded_server_action_silent():
    assert not {s for c, s in codes({"views/v.xml": SA.format("records.write({'active': False})")}, MANV) if c == "server-mass-change"}


# ---------------------------------------------------------------- H1/H2/H3 secret reads on public routes
RT = "class C(http.Controller):\n    @http.route('/p', auth='public')\n    def p(self, i=0, **kw):\n"
SU = "request.env['res.users'].sudo().browse(2)"


def _r(body, pre=""):
    return {"models/a.py": PH + pre + RT + "".join("        " + ln + "\n" for ln in body.split("\n"))}


@pytest.mark.parametrize("files", [
    _r(f"return [r['password'] for r in request.env['res.users'].sudo().search([('id', '=', 2)])]"),  # H1 probe
    _r(f"return str({SU}.__getitem__('password'))"),
    _r(f"out = []\nfor u in request.env['res.users'].sudo().search([('id', '=', 2)]):\n    out.append(u['api_key_ids'])\nreturn out"),
    _r(f"return {{u.login: u['totp_secret'] for u in {SU}}}"),
    _r(f"return {SU}.__dict__"),
])
def test_h1_container_secret_read_high(files):
    assert "high" in _sev(files, "route-secret-read")


@pytest.mark.parametrize("files", [
    _r(f"n = bytes.fromhex('70617373776f7264').decode()\nreturn getattr({SU}, n)"),  # H2 probe
    _r(f"return getattr({SU}, kw.get('f'))"),
    _r(f"import base64\nreturn getattr({SU}, base64.b64decode('cGFzc3dvcmQ=').decode())"),
    _r(f"return getattr({SU}, 'drowssap'[::-1])"),
])
def test_h2_runtime_field_name_high(files):
    assert "high" in _sev(files, "route-secret-read")


@pytest.mark.parametrize("files", [
    _r(f"return g({SU})", pre="g = lambda r: r.password\n"),  # H3 probes
    _r(f"return C2.g({SU})", pre="class C2:\n    @staticmethod\n    def g(r):\n        return r.password\n"),
    _r(f"return request.env['z.z'].g({SU})",
       pre="class Z(models.AbstractModel):\n    _name = 'z.z'\n    _description = 'z'\n\n    def g(self, r):\n        return r.password\n"),
    _r(f"return C2.g({SU})", pre="class C2:\n    @classmethod\n    def g(cls, r):\n        return {'k': r['api_key_ids']}\n"),
])
def test_h3_helper_kinds_high(files):
    assert "high" in _sev(files, "route-secret-read")


@pytest.mark.parametrize("files", [
    _r("p = request.env['res.partner'].sudo().browse(int(i))\nreturn {'name': p.name, 'city': getattr(p, 'city')}"),
    _r("return [{'name': u.name} for u in request.env['res.users'].sudo().search([('id', '=', 2)])]"),
    _r(f"return C2.g({SU})", pre="class C2:\n    @staticmethod\n    def g(r):\n        return r.name\n"),
    _r("return getattr(request, kw.get('f', 'session')) and 'ok'"),
])
def test_secret_benign_silent(files):
    assert not _sev(files, "route-secret-read")


# ---------------------------------------------------------------- H10 SQL normalised before DML check
@pytest.mark.parametrize("body", [
    "self.env.cr.execute('/*x*/UPDATE/**/res_users SET active=false')",  # review probe
    "self.env.cr.execute('WITH a AS (DELETE FROM res_users RETURNING 1) SELECT 1')",
    "t = 'res_' + 'users'\nself.env.cr.execute(f'UPDATE {t} SET active=false')",
    "self.env.cr.execute('-- c\\nUPDATE \"public\".\"res_users\" SET active=false')",
    "t = 'ir_config_parameter'\nself.env.cr.execute('DELETE FROM %s' % t)",
    "self.env.cr.execute('SELECT 1; INSERT INTO res_groups_users_rel VALUES (1, 2)')",
])
def test_h10_core_table_dml_high(body):
    assert "high" in _sev(_m(body), "core-table-dml")


@pytest.mark.parametrize("body", [
    "self.env.cr.execute('UPDATE a_a SET name = %s WHERE id = %s', ('x', 1))",
    "self.env.cr.execute('SELECT id FROM res_users WHERE login = %s', ('x',))",
    "self.env.cr.execute('WITH a AS (SELECT id FROM res_partner) UPDATE a_a SET name = 1')",
])
def test_h10_own_table_sql_silent(body):
    assert not _sev(_m(body), "core-table-dml")


# ---------------------------------------------------------------- H11 <function> destructive / unknown
def _x(body):
    man = {"name": "x", "version": "17.0.1.0.0", "depends": ["base"], "data": ["data/d.xml"], "license": "LGPL-3"}
    return {"__manifest__.py": repr(man), "models/a.py": PH + MH + "        return True\n",
            "data/d.xml": f"<odoo>{body}</odoo>"}


@pytest.mark.parametrize("body", [
    """<function model='res.partner' name='unlink' eval="[obj().env['res.partner'].search([]).ids]"/>""",  # probe
    """<function model='res.partner' name='write'><value model='res.partner' search='[]'/><value eval="{'active': False}"/></function>""",
    """<function model='product.product' name='action_archive'><value eval="obj().search([]).ids"/></function>""",
    """<function model='crm.lead' name='toggle_active' eval="[obj().env['crm.lead'].search([('name','!=','zz')]).ids]"/>""",
])
def test_h11_destructive_function_high(body):
    assert "high" in _sev(_x(body), "xml-function-destructive")


@pytest.mark.parametrize("body", [
    "<function model='res.partner' name='_do_magic' eval='[]'/>",
    "<function model='a.a' name='zz_unknown'/>",
    "<function model='product.product' name='_compute_x'/>",
])
def test_h11_unknown_function_medium(body):
    assert "medium" in _sev(_x(body), "xml-function-unknown")


@pytest.mark.parametrize("body", [
    "<function model='a.a' name='f'/>",  # defined in this module (audited)
    "<function model='res.partner' name='write'><value eval=\"[ref('base.main_partner')]\"/><value eval=\"{'name': 'x'}\"/></function>",
    "<function model='res.partner' name='search' eval='[[]]'/>",
])
def test_h11_benign_function(body):
    f = _x(body)
    assert not _sev(f, "xml-function-destructive") and not _sev(f, "xml-function-unknown")


# ---------------------------------------------------------------- M3 public-route IDOR on personal data / streams
def _pr(body):
    return {"controllers/c.py": PH + "class C(http.Controller):\n    @http.route('/x/<i>', auth='public')\n    def x(self, i):\n"
            + "".join("        " + ln + "\n" for ln in body.split("\n"))}


@pytest.mark.parametrize("body", [
    "return request.env['ir.binary']._get_stream_from(request.env['ir.attachment'].sudo().browse(int(i))).get_response()",  # probe
    "return request.env['mail.message'].sudo().browse(int(i)).body",
    "return str(request.env['res.partner'].sudo().browse(int(i)).read())",
    "p = request.env['res.partner'].sudo().browse(int(i))\nreturn p.email",
    "r = request.env['x.doc'].sudo().browse(int(i))\nreturn request.env['ir.binary']._record_to_stream(r, 'file').get_response()",
])
def test_m3_record_idor(body):
    assert _sev(_pr(body), "route-record-idor") | _sev(_pr(body), "route-attachment-idor")


@pytest.mark.parametrize("body", [
    "p = request.env['res.partner'].sudo().browse(int(i))\nif not p.exists():\n    return ''\nreturn 'ok'",
    "m = request.env['mail.message'].sudo().browse(int(i))\nm._document_check_access('read')\nreturn m.body",
    "return request.env['product.template'].sudo().browse(int(i)).name",
])
def test_m3_benign_silent(body):
    assert not _sev(_pr(body), "route-record-idor")


def test_m3_session_ownership_check_silent():
    b = "o = request.env['sale.order'].sudo().browse(int(i))\nassert o.id == request.session.get('sale_last_order_id')\nreturn o.name"
    assert not _sev(_pr(b), "route-record-idor")


# ---------------------------------------------------------------- H7 JS mass change: unbounded ids by default
def _js(src):
    return {"static/src/a.js": "/** @odoo-module */\n" + src}


O = "this.orm"


@pytest.mark.parametrize("src", [
    f"async function f() {{ const ids = await {O}.search('res.partner', JSON.parse('[]')); await {O}.unlink('res.partner', ids); }}",  # probe
    f"function f() {{ {O}.call('res.partner', 'search', [[]]).then(ids => {O}.unlink('res.partner', ids)); }}",
    f"async function f() {{ const o = {{}}; o.ids = await {O}.search('res.partner', []); await {O}.unlink('res.partner', o.ids); }}",
    f"async function f() {{ const a = []; a.push(...await {O}.search('res.partner', [])); await {O}.unlink('res.partner', a); }}",
    f"async function f() {{ const ids = await {O}.search('res.partner', []); for (const i of ids) await {O}.unlink('res.partner', [i]); }}",
    f"async function f() {{ const ids = await {O}.search('res.partner', []); await {O}.call('res.partner', 'action_archive', [ids]); }}",
    f"function f() {{ {O}.webSearchRead('res.partner', [], {{}}).then(r => {O}.unlink('res.partner', r.records.map(x => x.id))); }}",
    f"async function f() {{ const ids = await {O}.search('res.partner', [['name', '!=', 'zz']]); await {O}.unlink('res.partner', ids); }}",
])
def test_h7_js_mass_change_high(src):
    assert "high" in _sev(_js(src), "js-mass-change")


@pytest.mark.parametrize("src", [
    f"async function f(id) {{ const ids = await {O}.search('a.a', [['id', '=', id]]); await {O}.unlink('a.a', ids); }}",
    f"async function f(rec) {{ await {O}.write('a.a', [rec.resId], {{name: 'x'}}); }}",
    f"async function f(p) {{ const ids = await {O}.search('a.a', [['parent_id', '=', p], ['state', '!=', 'done']]); await {O}.unlink('a.a', ids); }}",
    f"async function f() {{ const r = await {O}.searchRead('a.a', [], ['name']); return r; }}",
])
def test_h7_js_bounded_silent(src):
    assert not _sev(_js(src), "js-mass-change")


def test_h7_view_state_domain_silent():
    src = f"class L {{ async del() {{ const ids = await {O}.search(this.resModel, this.domain, {{limit: 80}}); await {O}.unlink(this.resModel, ids); }} }}"
    assert not _sev(_js(src), "js-mass-change")


# ---------------------------------------------------------------- H8 fetch(Request) to call_kw / L2 form post
B = "JSON.stringify({jsonrpc: '2.0', params: {args: [[2], {groups_id: [[4, 1]]}], kwargs: {}}})"


@pytest.mark.parametrize("src", [
    f"fetch(new Request('/web/dataset/call_kw/res.users/write', {{method: 'POST', body: {B}}}));",  # probe
    f"const q = new Request('/web/dataset/call_kw/res.users/write', {{method: 'POST', body: {B}}}); fetch(q);",
    f"fetch(new Request('/web/dataset/call_kw', {{method: 'POST', body: JSON.stringify({{params: {{model: 'res.groups', method: 'write', args: [[1], {{}}]}}}})}}));",
    f"fetch('/web/dataset/call_kw/res.users/write', {{method: 'POST', body: {B}}});",
])
def test_h8_fetch_request_call_kw_high(src):
    assert "high" in _sev(_js(src), "js-sensitive-model")


def test_h8_benign_request_silent():
    src = "fetch(new Request('/my/route', {method: 'POST', body: JSON.stringify({a: 1})}));"
    assert not _sev(_js(src), "js-sensitive-model")


@pytest.mark.parametrize("src", [
    "const f = document.createElement('form'); f.action = '/web/dataset/call_kw/res.users/write'; f.method = 'post'; f.submit();",  # probe
    "const f = document.createElement('form'); f.setAttribute('action', '/web/dataset/call_kw'); f.submit();",
    "const b = document.createElement('button'); b.formAction = '/web/dataset/call_button'; b.click();",
])
def test_l2_form_to_orm_flagged(src):
    assert _sev(_js(src), "js-raw-orm-request")


def test_l2_benign_form_silent():
    src = "const f = document.createElement('form'); f.action = '/shop/cart/update'; f.submit();"
    assert not _sev(_js(src), "js-raw-orm-request")


# ---------------------------------------------------------------- H9 OWL javascript: with tab/entity/concat/state
def _owl(tpl, pre=""):  # tpl is raw template-literal source
    return _js("import { Component, xml, useState } from '@odoo/owl';\n" + pre + "class C extends Component {\n  static template = xml`" + tpl + "`;\n}\n")


@pytest.mark.parametrize("tpl,pre", [
    ("""<a t-att-href="'java&Tab;script:alert(1)'">x</a>""", ""),  # review probe
    ("""<a t-att-href="'java\\tscript:alert(1)'">x</a>""", ""),
    ("""<a t-att-href="'jav' + 'ascript:alert(1)'">x</a>""", ""),
    ("""<a t-attf-href="java{{'script'}}:alert(1)">x</a>""", ""),
    ("""<a t-att-href="state.url">x</a>""", "const S = { url: 'javascript:alert(1)' };\n"),
    ("""<a t-att-href="'java&#10;script:alert(1)'">x</a>""", ""),
])
def test_h9_owl_js_url_high(tpl, pre):
    assert "high" in _sev(_owl(tpl, pre), "owl-js-url")


@pytest.mark.parametrize("tpl", [
    """<a t-att-href="'/web#id=' + props.id">x</a>""",
    """<a t-attf-href="/shop/{{props.slug}}">x</a>""",
    """<a t-att-href="'https://www.odoo.com/' + 'help'">x</a>""",
])
def test_h9_benign_owl_url_silent(tpl):
    assert not _sev(_owl(tpl), "owl-js-url")


# ---------------------------------------------------------------- M2 external URL via runtime string ops
@pytest.mark.parametrize("src", [
    "fetch('/v.e//:sptth'.split('').reverse().join(''));",  # review probe shape
    "fetch(new URL('/x', 'https://e.v'));",
    "fetch(new URL('/x', 'https://e.v').href);",
    "fetch(['https://', 'e.v/'].concat(['x']).join(''));",
])
def test_m2_external_url_folded(src):
    assert _sev(_js(src), "js-external-request") & {"high", "medium"}


def test_m2_benign_local_url():
    assert not _sev(_js("fetch(new URL('/x', window.location.origin));"), "js-external-request")


# ---------------------------------------------------------------- M4 template from computed strings
@pytest.mark.parametrize("pre,val", [
    ("", """['<a href="javascript:alert(1)">', 'x</a>'].join('')"""),  # probe
    ("", """'<a href="java' + ['script', ':alert(1)">x</a>'].join('')"""),
    ("const T = ['<a href=\"javascript:alert(1)\">', 'x</a>'].join('');\n", "T"),
])
def test_m4_join_template_high(pre, val):
    src = "import { Component } from '@odoo/owl';\n" + pre + f"class C extends Component {{\n  static template = {val};\n}}\n"
    assert "high" in _sev(_js(src), "owl-js-url")


def test_m4_benign_template_name():
    src = "import { Component } from '@odoo/owl';\nclass C extends Component {\n  static template = ['web', 'Foo'].join('.');\n}\n"
    assert not _sev(_js(src), "owl-js-url")


# ---------------------------------------------------------------- L1 nested inline expressions fail closed
def _jsesc(t):
    return t.replace("\\", "\\\\").replace("`", "\\`")


def test_l1_nested_depth_fails_closed():
    l3 = "<i t-att-z=\\x22f(1)\\x22/>"  # quotes appear only once depth-2 source is cooked
    l2 = "<b t-att-y='xml`" + l3 + "`'/>"
    tpl = '<a t-att-x="xml`' + _jsesc(l2) + '`">x</a>'
    tpl = _jsesc(tpl)
    assert "medium" in _sev(_owl(tpl), "owl-expr-unaudited")


def test_l1_flat_expression_silent():
    assert not _sev(_owl("""<a t-on-click="() => this.go(1)">x</a>"""), "owl-expr-unaudited")


# ---------------------------------------------------------------- M1 data-file-unaudited only for real unknowns
from tests.test_nf_bot_code_audit_10 import PNG, JPG, _rec, _unaud  # noqa: E402


@pytest.mark.parametrize("ref,files", [
    ("x/static/img/table.png", {"static/img/table.png": PNG}),  # review: mrp/static/img/table.png in-module
    ("x/static/img/a.jpg", {"static/img/a.jpg": JPG}),
    ("static/img/table.png", {"static/img/table.png": PNG}),
])
def test_m1_type_matched_binary_silent(ref, files):
    assert not _unaud({"data/d.xml": _rec("image_1920", ref), **files})


@pytest.mark.parametrize("ref,files", [
    ("x/static/img/missing.png", {}),
    ("x/static/img/fake.png", {"static/img/fake.png": b"<html><script>x()</script>"}),
    ("other_mod/static/img/p.png", {}),
])
def test_m1_real_unknown_fires(ref, files):
    f = {"data/d.xml": _rec("image_1920", ref), **files}
    from tests.test_nf_bot_code_audit_10 import MANX
    assert "medium" in _unaud(f) or {s for c, s in codes(f, MANX)} & {"high", "medium"}
