"""BOT-CODE-AUDIT-5: regression probes for REVIEW-CODE-AUDIT-4 (H1-H15, M1-M8, L1-L4, goal 5).

Every class has a positive probe (must yield the expected code at the expected severity) and a
negative probe (the benign twin must not).
"""

# ruff: noqa: E501
import io
import zipfile

import pytest

from app.bots import code_audit as ca

MAN = "{'name':'x','version':'17.0.1.0.0','depends':['base','web','mail','website'],'license':'LGPL-3','data':['views/v.xml'],'assets':{'web.assets_backend':['x/static/src/**/*']}}"
H = "import os, subprocess, functools, operator, importlib\nfrom odoo import models, http\nfrom odoo.http import request\n"


def run(files, man=MAN):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        if "__manifest__.py" not in files:
            z.writestr("x/__manifest__.py", man)
        z.writestr("x/__init__.py", b"from . import models\n")
        z.writestr("x/models/__init__.py", b"from . import a\n")
        for k, v in files.items():
            z.writestr("x/" + k, v.encode() if isinstance(v, str) else v)
    r = ca.audit(b.getvalue(), version=17)
    assert r.ok, r.error
    return r


def codes(files, man=MAN):
    r = run(files, man)
    return {(f.code, f.severity) for f in r.findings if f.file in files}


def py(body):
    return {
        "models/a.py": H
        + "class A(models.Model):\n    _name='a.a'\n    def f(self, n):\n"
        + "\n".join("        " + ln for ln in body.split("\n"))
        + "\n"
    }


def pyt(src):
    return {"models/a.py": H + src}


def X(b):
    return {"views/v.xml": "<odoo>\n" + b + "\n</odoo>\n"}


def J(s, n="static/src/a.js"):
    return {n: s}


# (name, files, expected (code, severity) present, negative twin files, code that must be absent at HIGH/MEDIUM)
CASES = [
    # H3 hooks / migrations
    (
        "h3-uninstall-hook",
        {"hooks.py": "def uninstall_hook(env):\n    env['res.partner'].search([]).unlink()\n"},
        ("mass-change", "high"),
        {
            "hooks.py": "def uninstall_hook(env):\n    env['res.partner'].search([('x_tag','=',1)]).unlink()\n"
        },
        "mass-change",
    ),
    (
        "h3-migration-delete",
        {
            "migrations/17.0.2/pre-migrate.py": "def migrate(cr,v):\n    cr.execute('DELETE FROM res_users')\n"
        },
        ("mass-raw-dml", "high"),
        {
            "migrations/17.0.2/pre-migrate.py": "def migrate(cr,v):\n    cr.execute('DELETE FROM x_tmp WHERE id < 10')\n"
        },
        "mass-raw-dml",
    ),
    (
        "h3-hook-loop",
        {
            "hooks.py": "def post_init_hook(env):\n    for r in env['res.partner'].search([]):\n        r.unlink()\n"
        },
        ("mass-change", "high"),
        {
            "hooks.py": "def post_init_hook(env):\n    for r in env['res.partner'].search([('x','=',1)]):\n        r.unlink()\n"
        },
        "mass-change",
    ),
    # H2 auth bypass
    (
        "h2-override-cred",
        pyt(
            "class U(models.Model):\n    _inherit='res.users'\n    def _check_credentials(self, *a, **k):\n        return {'uid':self.id}\n"
        ),
        ("auth-override", "high"),
        pyt(
            "class U(models.Model):\n    _inherit='res.users'\n    def _other(self, *a, **k):\n        return {'uid':self.id}\n"
        ),
        "auth-override",
    ),
    (
        "h2-override-access",
        pyt(
            "class P(models.Model):\n    _inherit='res.partner'\n    def check_access_rights(self,*a,**k): return True\n"
        ),
        ("auth-override", "high"),
        pyt(
            "class P(models.Model):\n    _inherit='res.partner'\n    def check_rights_label(self,*a,**k): return True\n"
        ),
        "auth-override",
    ),
    (
        "h2-monkeypatch",
        pyt(
            "from odoo.addons.base.models.res_users import Users\nUsers._check_credentials=lambda *a,**k: None\n"
        ),
        ("auth-override", "high"),
        pyt("from odoo.addons.base.models.res_users import Users\nUsers._x_label='y'\n"),
        "auth-override",
    ),
    (
        "h2-setattr",
        pyt(
            "import odoo\nsetattr(odoo.addons.base.models.res_users.Users,'_check_credentials',lambda *a,**k:None)\n"
        ),
        ("auth-override", "high"),
        pyt(
            "class P(models.Model):\n    _inherit='res.partner'\n    def f(self, n, v):\n        setattr(self, n, v)\n"
        ),
        "auth-override",
    ),
    (
        "h2-auth-none-read",
        pyt(
            "class C(http.Controller):\n    @http.route('/a',auth='none',csrf=False)\n    def a(self,**kw):\n        return request.env['res.users'].sudo().search([]).read(['login','password'])\n"
        ),
        ("public-sudo-access", "high"),
        pyt(
            "class C(http.Controller):\n    @http.route('/a',auth='user')\n    def a(self,**kw):\n        return request.env['res.users'].sudo().search([]).read(['login','password'])\n"
        ),
        "public-sudo-access",
    ),
    (
        "h2-public-write",
        pyt(
            "class C(http.Controller):\n    @http.route('/a',auth='public',type='json')\n    def a(self,id,vals):\n        request.env['res.partner'].sudo().browse(id).write(vals)\n"
        ),
        ("public-sudo-access", "high"),
        pyt(
            "class C(http.Controller):\n    @http.route('/a',auth='public',type='json')\n    def a(self,id,vals):\n        request.env['res.partner'].sudo().browse(1).write({'x': 1})\n"
        ),
        "public-sudo-access",
    ),
    # goal 5 / M4 / H1 python resolution
    (
        "g5-getattr-module",
        py("getattr(os,n)('id')"),
        ("dynamic-dispatch", "high"),
        pyt("from odoo import fields\ndef f(t):\n    return getattr(fields, t)\n"),
        "dynamic-dispatch",
    ),
    (
        "m4-attrgetter-dotted",
        pyt("import operator\noperator.attrgetter('path.os.system')(os)('id')\n"),
        ("dangerous-call", "high"),
        pyt("import operator\noperator.attrgetter('path.sep')(os)\n"),
        "dangerous-call",
    ),
    (
        "h1-methodcaller-alias",
        py("mc=operator.methodcaller\nmc('system','id')(os)"),
        ("dangerous-call", "high"),
        py("mc=operator.methodcaller\nmc('upper')('a')"),
        "dangerous-call",
    ),
    (
        "h1-reduce-getattr",
        py("functools.reduce(getattr,['system'],os)('id')"),
        ("dangerous-call", "high"),
        py("functools.reduce(lambda a,b:a+b,[1,2],0)"),
        "dangerous-call",
    ),
    (
        "h1-dunder-call",
        py("os.system.__call__('id')"),
        ("dangerous-call", "high"),
        py("str.__call__"),
        "dangerous-call",
    ),
]


@pytest.mark.parametrize("name,pos,exp,neg,code", CASES, ids=[c[0] for c in CASES])
def test_probe_positive_and_negative(name, pos, exp, neg, code):
    got = codes(pos)
    assert exp in got, (name, got)
    bad = {c for c in codes(neg) if c[0] == code and c[1] in ("high", "medium")}
    assert not bad, (name, bad)


def SA(body):
    return X(
        "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='model_id' ref='base.model_res_partner'/>"
        + body
        + "</record>"
    )


XML_CASES = [
    # H4 server action value / fields_lines / webhook / cron loop
    (
        "h4-value-equation",
        SA(
            "<field name='state'>object_write</field><field name='evaluation_type'>equation</field><field name='value'>env['res.users'].sudo().search([]).unlink()</field>"
        ),
        ("server-mass-change", "high"),
        SA(
            "<field name='state'>object_write</field><field name='evaluation_type'>value</field><field name='value'>Hello world</field>"
        ),
        "server-mass-change",
    ),
    (
        "h4-fields-lines",
        SA(
            "<field name='state'>object_write</field><field name='fields_lines' eval=\"[(0,0,{'evaluation_type':'equation','value':'env.cr.execute(\\'drop table x\\')'})]\"/>"
        ),
        ("server-raw-dml", "high"),
        SA(
            "<field name='state'>object_write</field><field name='fields_lines' eval=\"[(0,0,{'evaluation_type':'value','value':'x'})]\"/>"
        ),
        "server-raw-dml",
    ),
    (
        "h4-webhook",
        SA("<field name='state'>webhook</field><field name='webhook_url'>https://e.v/h</field>"),
        ("server-webhook", "high"),
        SA("<field name='state'>code</field><field name='code'>records.write({'x': 1})</field>"),
        "server-webhook",
    ),
    (
        "h4-cron-loop",
        X(
            "<record id='c' model='ir.cron'><field name='name'>c</field><field name='model_id' ref='base.model_res_partner'/><field name='state'>code</field><field name='code'>for r in model.search([]): r.unlink()</field></record>"
        ),
        ("server-mass-change", "high"),
        X(
            "<record id='c' model='ir.cron'><field name='name'>c</field><field name='model_id' ref='base.model_res_partner'/><field name='state'>code</field><field name='code'>for r in model.search([('x','=',1)]): r.unlink()</field></record>"
        ),
        "server-mass-change",
    ),
    # H5 expression fields
    (
        "h5-field-compute",
        X(
            "<record id='f' model='ir.model.fields'><field name='name'>x_c</field><field name='model_id' ref='base.model_res_partner'/><field name='compute'>for r in self: r.env.cr.execute('drop table x')</field></record>"
        ),
        ("server-raw-dml", "high"),
        X(
            "<record id='f' model='ir.model.fields'><field name='name'>x_c</field><field name='model_id' ref='base.model_res_partner'/><field name='compute'>for r in self: r['x_c'] = r.name</field></record>"
        ),
        "server-raw-dml",
    ),
    (
        "h5-field-related-password",
        X(
            "<record id='f' model='ir.model.fields'><field name='name'>x_c</field><field name='model_id' ref='base.model_res_users'/><field name='related'>password</field></record>"
        ),
        ("sensitive-field-exposure", "high"),
        X(
            "<record id='f' model='ir.model.fields'><field name='name'>x_c</field><field name='model_id' ref='base.model_res_users'/><field name='related'>partner_id.name</field></record>"
        ),
        "sensitive-field-exposure",
    ),
    (
        "h5-report-name",
        X(
            "<record id='r' model='ir.actions.report'><field name='name'>r</field><field name='model'>res.partner</field><field name='report_name'>x.r</field><field name='print_report_name'>object.env.cr.execute('drop table x')</field></record>"
        ),
        ("unsafe-expression", "high"),
        X(
            "<record id='r' model='ir.actions.report'><field name='name'>r</field><field name='model'>res.partner</field><field name='report_name'>x.r</field><field name='print_report_name'>'Partner - %s' % object.name</field></record>"
        ),
        "unsafe-expression",
    ),
    # H6 privilege data
    (
        "h6-group-implies-system",
        X(
            "<record id='g' model='res.groups'><field name='name'>g</field><field name='implied_ids' eval=\"[(4,ref('base.group_system'))]\"/></record>"
        ),
        ("privilege-grant", "high"),
        X(
            "<record id='g' model='res.groups'><field name='name'>g</field><field name='implied_ids' eval=\"[(4,ref('base.group_user'))]\"/></record>"
        ),
        "privilege-grant",
    ),
    (
        "h6-user-password",
        X(
            "<record id='u' model='res.users'><field name='login'>z</field><field name='password'>z</field></record>"
        ),
        ("user-credential-data", "high"),
        X(
            "<record id='u' model='res.users'><field name='login'>z</field><field name='name'>z</field></record>"
        ),
        "user-credential-data",
    ),
    (
        "h6-access-xml-global",
        X(
            "<record id='ac' model='ir.model.access'><field name='name'>a</field><field name='model_id' ref='base.model_res_partner'/><field name='perm_unlink' eval='1'/></record>"
        ),
        ("access-global-write", "high"),
        X(
            "<record id='ac' model='ir.model.access'><field name='name'>a</field><field name='model_id' ref='base.model_res_partner'/><field name='group_id' ref='base.group_user'/><field name='perm_unlink' eval='1'/></record>"
        ),
        "access-global-write",
    ),
    (
        "h6-rule-open",
        X(
            "<record id='r' model='ir.rule'><field name='name'>r</field><field name='model_id' ref='base.model_res_users'/><field name='domain_force'>[(1,'=',1)]</field><field name='global' eval='True'/></record>"
        ),
        ("rule-open-domain", "high"),
        X(
            "<record id='r' model='ir.rule'><field name='name'>r</field><field name='model_id' ref='base.model_res_users'/><field name='domain_force'>[('id','=',user.id)]</field><field name='global' eval='True'/></record>"
        ),
        "rule-open-domain",
    ),
    # H7 csv
    (
        "h7-csv-users",
        {"data/res.users.csv": "id,login,groups_id/id\nu1,z,base.group_system\n"},
        ("privilege-grant", "high"),
        {"data/res.users.csv": "id,login,groups_id/id\nu1,z,base.group_user\n"},
        "privilege-grant",
    ),
    (
        "h7-csv-server",
        {
            "data/ir.actions.server.csv": "id,name,model_id/id,state,code\ns,s,base.model_res_partner,code,model.search([]).unlink()\n"
        },
        ("server-mass-change", "high"),
        {
            "data/ir.actions.server.csv": "id,name,model_id/id,state,code\ns,s,base.model_res_partner,code,records.write({'x': 1})\n"
        },
        "server-mass-change",
    ),
    (
        "h7-csv-config",
        {"data/ir.config_parameter.csv": "id,key,value\np,auth_signup.invitation_scope,b2c\n"},
        ("config-parameter-record", "high"),
        {"data/res.partner.csv": "id,name\np,Acme\n"},
        "config-parameter-record",
    ),
    (
        "h7-csv-rule",
        {
            "security/ir.rule.csv": "id,name,model_id:id,domain_force\nr,r,base.model_res_users,\"[(1,'=',1)]\"\n"
        },
        ("rule-open-domain", "high"),
        {
            "security/ir.rule.csv": "id,name,model_id:id,domain_force,groups/id\nr,r,base.model_res_users,\"[('id','=',user.id)]\",base.group_user\n"
        },
        "rule-open-domain",
    ),
    # H8 stored web content
    (
        "h8-website-page-arch",
        X(
            "<record id='w' model='website.page'><field name='url'>/x</field><field name='arch'>&lt;t t-raw='request.params[\"q\"]'/&gt;</field></record>"
        ),
        ("template-script", "high"),
        X(
            "<record id='w' model='website.page'><field name='url'>/x</field><field name='arch'>&lt;div&gt;&lt;t t-out='website.name'/&gt;&lt;/div&gt;</field></record>"
        ),
        "template-script",
    ),
    (
        "h8-asset-external",
        X(
            "<record id='a' model='ir.asset'><field name='name'>a</field><field name='bundle'>web.assets_backend</field><field name='path'>https://e.v/x.js</field></record>"
        ),
        ("asset-external", "high"),
        X(
            "<record id='a' model='ir.asset'><field name='name'>a</field><field name='bundle'>web.assets_backend</field><field name='path'>x/static/src/a.js</field></record>"
        ),
        "asset-external",
    ),
    (
        "h8-attachment-js",
        X(
            "<record id='a' model='ir.attachment'><field name='name'>a.js</field><field name='datas'>ZXZhbCgnMScp</field><field name='mimetype'>text/javascript</field></record>"
        ),
        ("attachment-active-content", "high"),
        X(
            "<record id='a' model='ir.attachment'><field name='name'>a.txt</field><field name='datas'>aGVsbG8=</field><field name='mimetype'>text/plain</field></record>"
        ),
        "attachment-active-content",
    ),
    # M8 delete, M5 button, misc
    (
        "m8-delete-all-core",
        X("<delete model='res.partner' search=\"[]\"/>"),
        ("xml-delete", "high"),
        X("<delete model='x.thing' id='x.rec1'/>"),
        "xml-delete",
    ),
    (
        "m5-public-unlink-button",
        X(
            "<record id='v' model='ir.ui.view'><field name='name'>v</field><field name='model'>res.users</field><field name='arch' type='xml'><form><button name='unlink' type='object' groups='base.group_public'/></form></field></record>"
        ),
        ("public-button", "high"),
        X(
            "<record id='v' model='ir.ui.view'><field name='name'>v</field><field name='model'>res.users</field><field name='arch' type='xml'><form><button name='unlink' type='object' groups='base.group_system'/></form></field></record>"
        ),
        "public-button",
    ),
    (
        "x-search-attr",
        X(
            "<record id='p' model='res.partner'><field name='parent_id' search=\"[('id','=',__import__('os').system('id'))]\"/></record>"
        ),
        ("unsafe-expression", "high"),
        X(
            "<record id='p' model='res.partner'><field name='parent_id' search=\"[('name','=','Acme')]\"/></record>"
        ),
        "unsafe-expression",
    ),
]


@pytest.mark.parametrize("name,pos,exp,neg,code", XML_CASES, ids=[c[0] for c in XML_CASES])
def test_xml_probe_positive_and_negative(name, pos, exp, neg, code):
    test_probe_positive_and_negative(name, pos, exp, neg, code)
