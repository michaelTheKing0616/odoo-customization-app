"""BOT-CODE-AUDIT-7: REVIEW-CODE-AUDIT-6 (H1-H17, M1-M6, L1-L3). Every item: the exact
probe, at least two variants, and a benign twin that must stay quiet."""

# ruff: noqa: E501
import pytest

from tests.test_nf_bot_code_audit_5 import codes, pyt  # noqa: F401


def hm(files):
    return {c for c in codes(files) if c[1] in ("high", "medium")}


def jsf(s):
    return {"static/src/a.js": s}


# ---------------------------------------------------------------- JS: H1-H7, M1
JS_C={
"h1":"export async function f(orm){\n  const ids = await orm.search('res.partner', []);\n  await orm.unlink('res.partner', ids);\n}\n",
"h1b":"export async function f(orm){\n  let ids; ids = await orm.search('res.partner', []);\n  await orm.call('res.partner','unlink',[ids]);\n}\n",
"h1c":"export async function f(orm){\n  const a = await orm.search('res.partner', []); const ids = a;\n  await orm.write('res.partner', ids, {active:false});\n}\n",
"h1neg":"export async function f(orm, sel){\n  const ids = await orm.search('res.partner', [['id','in',sel]]);\n  await orm.unlink('res.partner', ids);\n}\n",
"h2":"export async function f(orm){\n const rows = await orm.searchRead('res.partner', []);\n await orm.unlink('res.partner', rows.map(r => r.id));\n}\n",
"h2b":"export async function f(orm){\n const rows = await orm.call('res.partner','search_read',[], {domain:[]});\n const ids = rows.map(r=>r.id);\n await orm.write('res.partner', ids, {a:1});\n}\n",
"h2neg":"export async function f(orm){\n const rows = await orm.searchRead('res.partner', [['x','=',1]]);\n await orm.unlink('res.partner', rows.map(r => r.id));\n}\n",
"h3":"export async function f(rpc){\nawait rpc('/web/dataset/call_kw', {model:'res.partner', method:'unlink',\n  args:[await rpc('/web/dataset/call_kw', {model:'res.partner', method:'search', args:[[]], kwargs:{}})], kwargs:{}});\n}\n",
"h3b":"export async function f(rpc){\nconst ids = await rpc('/web/dataset/call_kw/res.partner/search', {model:'res.partner', method:'search', args:[], kwargs:{domain:[]}});\nawait rpc('/web/dataset/call_kw/res.partner/write', {model:'res.partner', method:'write', args:[ids, {active:false}], kwargs:{}});\n}\n",
"h3neg":"export async function f(rpc, id){\nawait rpc('/web/dataset/call_kw', {model:'res.partner', method:'unlink', args:[[id]], kwargs:{}});\n}\n",
"h4":"import {Component, xml} from '@odoo/owl';\nclass A extends Component {\n  static template = xml`<a t-att-href=\"'javascript:alert(1)'\">x</a>`;\n}\n",
"h4b":"import {Component, xml} from '@odoo/owl';\nclass A extends Component {\n  static template = xml`<iframe t-att-src=\"'javascript:alert(1)'\"/>`;\n}\n",
"h4c":"import {Component, xml} from '@odoo/owl';\nclass A extends Component {\n  static template = xml`<a href=\"javascript:alert(1)\">x</a>`;\n}\n",
"h4neg":"import {Component, xml} from '@odoo/owl';\nclass A extends Component {\n  static template = xml`<a t-att-href=\"'/web#action=1'\" href=\"/shop\"><img t-att-src=\"'data:image/png;base64,'+props.b\"/></a>`;\n}\n",
"h5":"import {Component, xml} from '@odoo/owl';\nclass A extends Component { static template = xml`<a t-att-href=\"'javascript:'+props.c\">x</a>`; }\n",
"h5b":"import {Component, xml} from '@odoo/owl';\nclass A extends Component { static template = xml`<a t-attf-href=\"javascript:{{props.c}}\">x</a>`; }\n",
"h5c":"import {Component, xml} from '@odoo/owl';\nclass A extends Component { static template = xml`<a t-att-href=\"' JavaScript:'+props.c\">x</a>`; }\n",
"h6":"import {Component, xml} from '@odoo/owl';\nclass A extends Component { static template = xml`<iframe t-att-srcdoc=\"props.html\"/>`; }\n",
"h6b":"import {Component, xml} from '@odoo/owl';\nclass A extends Component { static template = xml`<iframe t-att-srcdoc=\"state.a + props.b\"/>`; }\n",
"h6neg":"import {Component, xml} from '@odoo/owl';\nclass A extends Component { static template = xml`<iframe t-att-srcdoc=\"'<p>hi</p>'\"/>`; }\n",
"h7":"export function f(a, x){ a.href = 'javascript:' + x; }\n",
"h7b":"export function f(el, x){ el.setAttribute('href', 'javascript:' + x); }\n",
"h7c":"export function f(el, x){ el.src = `javascript:${x}`; }\n",
"h7neg":"export function f(a, x){ a.href = '/web#id=' + x; a.setAttribute('href', 'https://odoo.com'); }\n",
"m1":"const a = document.createElement('a');\na.setAttribute('href', 'javascript:alert(1)');\n",
"m1b":"const a = document.createElement('a');\na.href = 'javascript:void(alert(1))';\n",
"m1neg":"const a = document.createElement('a');\na.href = 'https://odoo.com';\n",
}

JS_EXPECT = {'h1': 'js-mass-change', 'h2': 'js-mass-change', 'h3': 'js-mass-change', 'h4': 'owl-js-url', 'h5': 'owl-js-url', 'h6': 'owl-srcdoc', 'h7': 'js-eval', 'm1': 'js-eval'}


@pytest.mark.parametrize("key", sorted(k for k in JS_C if not k.endswith("neg")))
def test_js_probe_and_variants_high(key):
    code = JS_EXPECT[key[:2]]
    assert (code, "high") in hm(jsf(JS_C[key])), key


@pytest.mark.parametrize("key", sorted(k for k in JS_C if k.endswith("neg")))
def test_js_benign_twin_quiet(key):
    c = hm(jsf(JS_C[key]))
    assert not {x for x in c if x[0] in ("js-mass-change", "owl-js-url", "owl-srcdoc", "js-eval")}, (key, c)


# ---------------------------------------------------------------- H8: record context privilege defaults
_AW = "<record id='a' model='ir.actions.act_window'><field name='name'>a</field><field name='res_model'>%s</field><field name='context'>%s</field></record>"
H8_POS = {
    "probe": _AW % ("res.users", "{'default_groups_id':[(4,ref('base.group_system'))]}"),
    "share": _AW % ("res.users", "{'default_share': False}"),
    "filter-users": "<record id='f' model='ir.filters'><field name='name'>f</field><field name='model_id'>res.groups</field><field name='context'>{\"default_users\": [(4, 2)]}</field></record>",
    "dict-call": _AW % ("res.users", "dict(default_groups_id=[(6,0,[1])])"),
}


@pytest.mark.parametrize("key", sorted(H8_POS))
def test_h8_record_context_privilege_default(key):
    assert ("context-privilege-default", "high") in codes({"views/v.xml": "<odoo>\n" + H8_POS[key] + "\n</odoo>\n"})


def test_h8_csv_act_window_context():
    csv = "id,name,res_model,context\na,a,res.users,\"{'default_groups_id': [(4, 1)]}\"\n"
    assert ("context-privilege-default", "high") in codes({"data/ir.actions.act_window.csv": csv})


def test_h8_stock_like_action_context_quiet():
    x = _AW % ("a.a", "{'default_partner_id': active_id, 'search_default_my': 1, 'default_login': 'x'}")
    assert not hm({"views/v.xml": "<odoo>\n" + x + "\n</odoo>\n"})


# ---------------------------------------------------------------- Python: H8 twin, H9-H17, M2, M3
PH = "import os, subprocess\nfrom odoo import models, fields, api, http\nfrom odoo.http import request\n"
def M(body): return "class A(models.Model):\n    _name='a.a'\n    def f(self):\n"+"\n".join("        "+l for l in body.split("\n"))+"\n"
def CT(dec, body): return "class C(http.Controller):\n    @http.route('/p', "+dec+")\n    def p(self, **kw):\n"+"\n".join("        "+l for l in body.split("\n"))+"\n"
PY_C = {
"h9":"from odoo.service import dispatch_rpc\nclass C(http.Controller):\n    @http.route('/j', type='json', auth='none')\n    def j(self, s, m, a):\n        return dispatch_rpc(s, m, a)\n",
"h9b":"from odoo.service import dispatch_rpc as d\nclass C(http.Controller):\n    @http.route('/j', type='json', auth='public')\n    def j(self, s, m, a):\n        return self._go(s, m, a)\n    def _go(self, s, m, a):\n        return d(s, m, a)\n",
"h9c":"import odoo\nclass C(http.Controller):\n    @http.route('/j', type='json', auth='none')\n    def j(self, *a):\n        return odoo.service.model.execute_kw(*a)\n",
"h9neg":"class C(http.Controller):\n    @http.route('/j', type='json', auth='user')\n    def j(self):\n        return request.env['a.a'].search_read([], ['name'])\n",
"h10":"class R(models.Model):\n    _inherit = 'ir.rule'\n    def _compute_domain(self, model_name, mode='read'):\n        return [(1, '=', 1)]\n",
"h10b":"class R(models.Model):\n    _inherit = ['ir.rule']\n    def _compute_domain(self, model_name, mode='read'):\n        super()._compute_domain(model_name, mode)\n        return []\n",
"h10c":"class R(models.Model):\n    _inherit = 'ir.model.access'\n    def check(self, model, mode='read', raise_exception=True):\n        return True\n",
"h10d":"class R(models.Model):\n    _inherit = 'ir.rule'\n    def _get_rules(self, model_name, mode='read'):\n        return self.browse()\n",
"h10neg":"class P(models.Model):\n    _inherit = 'res.partner'\n    def _compute_display_name(self):\n        return super()._compute_display_name()\n",
"h11":"class U(models.Model):\n    _inherit = 'res.users'\n    @api.model_create_multi\n    def create(self, vals_list):\n        for v in vals_list:\n            v['groups_id'] = [(6, 0, [self.env.ref('base.group_system').id])]\n        return super().create(vals_list)\n",
"h11b":"class U(models.Model):\n    _inherit = 'res.users'\n    def write(self, vals):\n        vals.update({'groups_id': [(4, 1)]})\n        return super().write(vals)\n",
"h11c":"class U(models.Model):\n    _inherit = 'res.users'\n    def write(self, vals):\n        return super().write(dict(vals, share=False))\n",
"h11d":"class G(models.Model):\n    _inherit = 'res.groups'\n    def write(self, vals):\n        vals['users'] = [(4, 2)]\n        return super().write(vals)\n",
"h11neg":"class U(models.Model):\n    _inherit = 'res.users'\n    @api.model_create_multi\n    def create(self, vals_list):\n        for v in vals_list:\n            v.setdefault('tz', 'UTC')\n            v['notification_type'] = 'inbox'\n        return super().create(vals_list)\n",
"h12":CT("auth='public'","return request.env['res.users'].sudo().browse(2).password"),
"h12b":CT("auth='public'","return request.env['res.users'].sudo().search([]).mapped('password')"),
"h12c":CT("auth='user'","rows = request.env['res.users'].sudo().read(['password','login'])\nreturn rows"),
"h12d":CT("auth='user'","keys = request.env['res.users.apikeys'].sudo().search_read([], ['name'])\nreturn request.make_json_response(keys)"),
"h12e":CT("auth='public'","u = request.env['res.users'].sudo().browse(2)\npw = u.password\nreturn {'p': pw}"),
"h12neg":CT("auth='public'","return {'name': request.env.user.name, 'login': request.env.user.login, 'csrf': request.csrf_token(), 'tok': request.env['sale.order'].sudo().browse(1).access_token}"),
"m3":CT("auth='user'","request.env['auth.totp.device'].sudo().search([]).unlink()\nreturn 'ok'"),
"h13":CT("auth='user'","request.session.update({'uid': 1})"),
"h13b":CT("auth='user'","request.session['uid'] = 1"),
"h13c":CT("auth='user'","s = request.session\ns['session_token'] = 'x'"),
"h13d":CT("auth='user'","request.session.update(uid=1, login='admin')"),
"h13e":CT("auth='user'","request.session.setdefault('uid', 1)"),
"h13neg":CT("auth='user'","request.session['debug'] = '1'\nrequest.session.update({'lang': 'fr_FR'})\nrequest.session.setdefault('website_id', 1)"),
"h14":"from odoo.tools import SQL\n" + M("self.env.cr.execute(SQL('UPDATE %s SET active=false', SQL.identifier('res_users')))"),
"h14b":"from odoo.tools import SQL\n" + M("t = SQL.identifier('res_groups_users_rel')\nself.env.cr.execute(SQL('DELETE FROM %s', t))"),
"h14c":"from psycopg2 import sql\n"+M("self.env.cr.execute(sql.SQL('UPDATE {} SET active=false').format(sql.Identifier('res_users')))"),
"h14neg":"from odoo.tools import SQL\n" + M("self.env.cr.execute(SQL('UPDATE %s SET x=1 WHERE id=%s', SQL.identifier(self._table), self.id))"),
"h15":M("self.env['res.partner'].search([]).mapped('user_ids').write({'groups_id': [(4, 1)]})"),
"h15b":M("self.partner_id.user_ids.write({'active': False})"),
"h15c":M("self.env['res.partner'].search([]).filtered(lambda p: p.x).mapped('user_ids').sudo().unlink()"),
"h15neg":M("self.env['sale.order'].search([]).mapped('order_line').write({'x': 1})"),
"h16":"class A(models.Model):\n    _inherit = 'res.partner'\n    pw = fields.Char(related='user_ids.password', store=True)\n",
"h16b":"class A(models.Model):\n    _inherit = 'res.partner'\n    pw = fields.Char(string='P', related='user_id.oauth_access_token')\n",
"h16c":"class A(models.Model):\n    _name = 'a.a'\n    k = fields.Char(related='user_id.totp_secret', readonly=True)\n",
"h16neg":"class A(models.Model):\n    _inherit = 'res.partner'\n    lg = fields.Char(related='user_ids.login')\n    em = fields.Char(related='parent_id.email', store=True)\n",
"h17":M("self.env['res.users'].new({'login': 'x', 'groups_id': [(4, 1)]})"),
"h17b":M("vals = {'login': 'x', 'share': False}\nself.env['res.users'].new(vals)"),
"h17c":M("self.env['res.users'].with_context(a=1).new(dict(login='x', groups_id=[(4, 1)]))"),
"h17neg":M("self.env['res.users'].new({'login': 'x', 'name': 'y'})"),
"m2":M("m = 'res' + '.' + 'users'\nself.env[m].sudo().search([]).write({'active': False})"),
"m2b":M("self.env['.'.join(['res', 'users'])].browse(1).write({'active': False})"),
"m2c":M("self.env[f'res.{\"groups\"}'].browse(1).unlink()"),
"m2neg":M("m = 'res' + '.partner'\nself.env[m].browse(1).write({'name': 'x'})"),
"h8py":M("return {'type': 'ir.actions.act_window', 'res_model': 'res.users', 'context': {'default_groups_id': [(4, 1)]}}"),
"h8py2":M("return self.env['res.users'].with_context(default_share=False).create({'login': 'x'})"),
}

PY_EXPECT = {'h9': 'rpc-proxy', 'h10': 'auth-override', 'h11': 'sensitive-override-write', 'h12': 'route-secret-read', 'm3': 'route-secret-read', 'h13': 'session-auth-write', 'h14': 'core-table-dml', 'h15': 'sensitive-model-write', 'h16': 'sensitive-field-exposure', 'h17': 'sensitive-model-write', 'm2': 'sensitive-model-write', 'h8': 'context-privilege-default'}


def _pyk(key):
    return "h8" if key.startswith("h8") else key[:3] if key[:3] in PY_EXPECT else key[:2]


def _pyfiles(key):
    return {"models/a.py": PH + PY_C[key]}


@pytest.mark.parametrize("key", sorted(k for k in PY_C if not k.endswith("neg")))
def test_py_probe_and_variants(key):
    code = PY_EXPECT[_pyk(key)]
    sev = "medium" if key == "m3" else "high"
    assert (code, sev) in codes(_pyfiles(key)), key


@pytest.mark.parametrize("key", sorted(k for k in PY_C if k.endswith("neg")))
def test_py_benign_twin_quiet(key):
    code = PY_EXPECT[_pyk(key)]
    c = {x for x in hm(_pyfiles(key)) if x[0] not in ("dangerous-import", "access-missing")}
    assert not c, (key, code, c)


def test_h10_super_with_literal_domain_is_high():
    assert ("auth-override", "high") in codes(_pyfiles("h10b"))


def test_h12_public_mapped_password_also_public_sudo():
    assert ("route-secret-read", "high") in codes(_pyfiles("h12b"))
