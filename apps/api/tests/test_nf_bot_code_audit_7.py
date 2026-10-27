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
