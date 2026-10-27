"""BOT-CODE-AUDIT: read-only module audit. Never imports/executes the audited code."""

from __future__ import annotations

import ast
import copy
import io
import os
import stat
import sys
import zipfile
from pathlib import Path

import pytest
from module_generator import build_module_zip

from app.bots import code_audit as ca
from app.bots import req2mod as rm
from app.bots import tiers as tt

MANIFEST = (
    "{'name': 'Demo', 'version': '17.0.1.0.0', 'depends': ['base', 'mail'], 'license': 'LGPL-3',"
    " 'data': ['security/ir.model.access.csv', 'views/views.xml']}"
)
MODELS = """
from odoo import fields, models


class Thing(models.Model):
    _name = "x.thing"
    _description = "Thing"
    name = fields.Char()
    code = fields.Char()
    company_id = fields.Many2one("res.company")
    owner_id = fields.Many2one("res.users", default=lambda s: s.env["res.users"].sudo().search([]))

    def run(self, val):
        self.env.cr.execute("SELECT 1 FROM x_thing WHERE code = '%s'" % val)
        self.env.cr.execute("SELECT 1")
        for rec in self:
            rec.env["x.thing"].search([("code", "=", rec.code)])
        eval(val)
        return self.sudo()


class Other(models.Model):
    _name = "x.other"
    _description = "Other"
    label = fields.Char()


class PartnerExt(models.Model):
    _inherit = "res.partner"
    x_flag = fields.Boolean()


class Gone(models.Model):
    _inherit = "no.such.model"
"""
VIEWS = """<?xml version="1.0"?>
<odoo>
  <record id="view_thing_form" model="ir.ui.view">
    <field name="model">x.thing</field>
    <field name="arch" type="xml">
      <list><field name="code" attrs="{'invisible': [('name','=',False)]}"/>
      <field name="ghost"/></list>
    </field>
  </record>
  <record id="view_partner" model="ir.ui.view">
    <field name="model">res.partner</field>
    <field name="arch" type="xml"><form><field name="not_a_stock_field"/></form></field>
  </record>
  <record id="act" model="ir.actions.act_window">
    <field name="domain">[('id', 'in', __import__('os').listdir('/'))]</field>
  </record>
  <menuitem id="menu_x" action="demo.missing_action"/>
  <template id="tpl"><div t-raw="doc.note"/></template>
</odoo>
"""
ACCESS = (
    "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n"
    "access_thing,thing,model_x_thing,,1,1,1,1\n"
)
TREE = {
    "__manifest__.py": MANIFEST,
    "__init__.py": "from . import models\n",
    "models/thing.py": MODELS,
    "views/views.xml": VIEWS,
    "security/ir.model.access.csv": ACCESS,
}


def zbytes(files, root="demo", mode=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items():
            zi = zipfile.ZipInfo(f"{root}/{k}" if root else k)
            if mode:
                zi.external_attr = mode << 16
            z.writestr(zi, v)
    return buf.getvalue()


def codes(r):
    return {f.code for f in r.findings}


@pytest.fixture(scope="module")
def rep():
    r = ca.audit(zbytes(TREE), version=17)
    assert r.ok, r.error
    return r


# AC1 structured findings: severity, code, file:line, message, fix hint; sorted by severity
def test_findings_structured(rep):
    assert rep.module == "demo" and rep.findings
    for f in rep.findings:
        assert f.severity in ("high", "medium", "low", "info") and f.code and f.message and f.fix
    sev = [ca._SEV_RANK[f.severity] for f in rep.findings]
    assert sev == sorted(sev)
    sql = next(f for f in rep.findings if f.code == "sql-injection")
    assert sql.file == "models/thing.py" and sql.line == 14
    assert rep.counts["high"] >= 5


# AC2 security: missing access, global write, missing multi-company rule
def test_security_findings(rep):
    assert {"access-missing", "access-global-write", "rule-missing-company"} <= codes(rep)
    miss = [f.message for f in rep.findings if f.code == "access-missing"]
    assert any("x.other" in m for m in miss) and not any("x.thing" in m for m in miss)


# AC3 unsafe code and expressions
def test_unsafe_code_findings(rep):
    assert {
        "sql-injection",
        "raw-sql",
        "eval-exec",
        "sudo",
        "unsafe-default",
        "unsafe-expression",
        "qweb-t-raw",
    } <= codes(rep)


# AC4 upgrade hazards: undefined xmlids / fields
def test_upgrade_hazards(rep):
    assert {"xmlid-undefined", "field-undefined"} <= codes(rep)
    assert any("demo.missing_action" in f.message for f in rep.findings)
    assert any("x.thing.ghost" in f.message for f in rep.findings)


# AC5 version compatibility (versioncaps + series-specific syntax)
def test_version_findings(rep):
    assert {"version-model", "field-undefined", "version-list", "version-attrs"} <= codes(rep)
    assert any(
        f.severity == "high" and "res.partner.not_a_stock_field" in f.message for f in rep.findings
    )
    r20 = ca.audit(zbytes(TREE), version=20)
    assert "version-manifest" in codes(r20) and "version-list" not in codes(r20)
    t = dict(
        TREE, **{"views/views.xml": VIEWS.replace("<list>", "<tree>").replace("</list>", "</tree>")}
    )
    assert "version-tree" in codes(ca.audit(zbytes(t), version=18))


# AC6 performance smells
def test_performance_findings(rep):
    assert {"query-in-loop", "missing-index"} <= codes(rep)


# AC7 ownership: decided by caller registry only; foreign is audit-only
def test_ownership(rep):
    assert rep.owned is False and rep.editable is False
    assert all(f.fix.startswith(ca.FOREIGN_HINT) for f in rep.findings)
    own = ca.audit(zbytes(TREE), version=17, owned_names={"demo"})
    assert own.owned and own.editable and not own.findings[0].fix.startswith(ca.FOREIGN_HINT)
    spoof = dict(TREE, **{"__manifest__.py": MANIFEST[:-1] + ", 'author': 'Ingenium'}"})
    r = ca.audit(zbytes(spoof), version=17)
    assert not r.owned and "ownership-claimed" in codes(r)
    assert not ca.audit(zbytes(TREE), version=17, owned_names="demo").owned


# AC8 hostile input: never imported or executed; bounded; zip-slip and symlink safe
def test_never_executes(tmp_path, monkeypatch):
    marker = tmp_path / "pwned"
    evil = f"open({str(marker)!r}, 'w').write('x')\nimport os\nos.system('touch {marker}')\n"
    files = dict(TREE, **{"__init__.py": evil, "models/thing.py": evil, "__manifest__.py": evil})
    mods = set(sys.modules)
    r = ca.audit(zbytes(files), version=17)
    assert r.ok and not marker.exists()
    assert "manifest-invalid" in codes(r)
    assert not {m for m in set(sys.modules) - mods if "demo" in m}


@pytest.mark.parametrize(
    "files,root,mode,needle",
    [
        ({"../../etc/x.py": "x"}, "", None, "unsafe path"),
        ({"/abs.py": "x"}, "", None, "unsafe path"),
        ({"a\\..\\b.py": "x"}, "", None, "unsafe path"),
        ({"link": "/etc/passwd"}, "demo", stat.S_IFLNK | 0o777, "symlink"),
        ({"/".join(["d"] * 20) + "/x.py": "x"}, "", None, "unsafe path"),
    ],
)
def test_hostile_archives_refused(files, root, mode, needle):
    r = ca.audit(zbytes(files, root=root, mode=mode), version=17, module_name="demo")
    assert not r.ok and needle in r.error and not r.findings


def test_zip_bomb_and_limits(monkeypatch):
    bomb = zbytes({"__manifest__.py": "{}", "big.py": "#" * 3_000_000})
    r = ca.audit(bomb, version=17)
    # one oversized file is reported HIGH unaudited; the rest of the module is still audited
    assert "over-compressed" in r.error or (
        r.ok
        and ("high", "file-unaudited", "big.py")
        in {(f.severity, f.code, f.file) for f in r.findings}
    )
    monkeypatch.setattr(ca, "MAX_RATIO", 1_000_000)
    monkeypatch.setattr(ca, "MAX_FILE", 10_000_000)
    monkeypatch.setattr(ca, "MAX_TOTAL", 1000)
    assert "too large" in ca.audit(bomb, version=17).error
    monkeypatch.setattr(ca, "MAX_FILES", 2)
    assert "too many" in ca.audit(zbytes(TREE), version=17).error
    assert "not a valid zip" in ca.audit(b"PK\x03\x04junk", version=17).error
    assert ca.audit("text", version=17).ok is False
    assert ca.audit(zbytes(TREE), version=16).ok is False


def test_directory_source_symlink_refused(tmp_path):
    root = tmp_path / "demo"
    for k, v in TREE.items():
        p = root / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(v)
    r = ca.audit(root, version=17)
    assert r.ok and r.module == "demo" and "access-missing" in codes(r)
    os.symlink("/etc/passwd", root / "models" / "leak.py")
    r = ca.audit(root, version=17)
    assert not r.ok and "symlink" in r.error


def test_malformed_files_become_findings():
    files = dict(TREE)
    files["models/bad.py"] = "def x(:\n"
    files["views/bad.xml"] = "<odoo><record"
    files["views/xxe.xml"] = (
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><odoo>&e;</odoo>'
    )
    files["views/lol.xml"] = (
        '<!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><odoo>&b;</odoo>'
    )
    files["security/ir.model.access.csv"] = b"\xff\xfe\x00bad"
    files["models/deep.py"] = "x = " + "(" * 5000 + ")" * 5000 + "\n"
    r = ca.audit(zbytes(files), version=17)
    assert r.ok
    bad = {f.file for f in r.findings if f.code == "parse-error"}
    assert {
        "models/bad.py",
        "views/bad.xml",
        "views/xxe.xml",
        "views/lol.xml",
        "security/ir.model.access.csv",
        "models/deep.py",
    } <= bad
    assert not any("root:" in f.message for f in r.findings)


# AC9 read-only and no T3 switch; generated (owned) modules audit without high findings
def test_read_only_and_t3_unchanged():
    src = Path(ca.__file__).read_text()
    tree = ast.parse(src)
    mods = {getattr(n, "module", "") or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(
        m.startswith(
            (
                "odoo_client",
                "app.changeset",
                "xmlrpc",
                "httpx",
                "requests",
                "subprocess",
                "importlib",
            )
        )
        for m in mods
    )
    assert "execute_kw" not in src and "exec_module" not in src
    assert tt.tier_ready(tt.T3) is False


@pytest.mark.parametrize("v", [17, 18, 19])
def test_req2mod_output_has_no_high_findings(v):
    from tests.test_nf_bot_req2mod import REQUESTS

    r = rm.build(
        copy.deepcopy(REQUESTS),
        version=v,
        installed_modules=["base", "mail"],
        technical_name="x_requests_app",
    )
    a = ca.audit(build_module_zip(r.spec, odoo_major=v), version=v, owned_names={"x_requests_app"})
    assert a.ok and a.owned, a.error
    assert [f for f in a.findings if f.severity == "high"] == []


# ---------------------------------------------------------------- review round 2


def _tree(**over):
    return {k: v for k, v in dict(TREE, **over).items() if v is not None}


def test_r2_b1_module_dir_never_in_files_and_refused(tmp_path):
    files, top = ca.load_tree(zbytes(TREE))
    assert top == "demo" and ".module_dir" not in files
    for z in (
        zbytes(_tree(**{".module_dir": "base"}), root="evil"),
        zbytes({".module_dir": "x"}, root=""),
    ):
        r = ca.audit(z, version=17)
        assert not r.ok and ".module_dir" in r.error
    root = tmp_path / "evil"
    root.mkdir()
    (root / ".module_dir").write_text("base")
    assert not ca.audit(root, version=17).ok


@pytest.mark.parametrize(
    "code",
    [
        "import os\nos.system('id')\n",
        "import subprocess\nsubprocess.run(['id'])\n",
        "x = getattr(__builtins__, 'ev' + 'al')\n",
        "import builtins\nbuiltins.eval('1')\n",
        "import importlib\nimportlib.import_module('os')\n",
        "__import__('os')\n",
        "import os\nos.popen('id')\n",
    ],
)
def test_r2_b2_dangerous_python_calls(code):
    r = ca.audit(zbytes(_tree(**{"__init__.py": "from . import models\n" + code})), version=17)
    assert any(f.code == "dangerous-call" and f.severity == "high" for f in r.findings), code


def test_r2_b2_open_and_imports_flagged():
    r = ca.audit(
        zbytes(_tree(**{"__init__.py": "import pickle\nopen('/etc/passwd')\n"})), version=17
    )
    assert {"file-access", "dangerous-import"} <= codes(r)


def test_r2_b2_access_file_not_in_manifest_data():
    man = MANIFEST.replace("'security/ir.model.access.csv', ", "")
    r = ca.audit(zbytes(_tree(**{"__manifest__.py": man})), version=17)
    miss = [f.message for f in r.findings if f.code == "access-missing"]
    assert any("x.thing" in m for m in miss)


def test_r2_b3_inherits_and_nested_and_auto_xmlid():
    model = (
        "from odoo import fields, models\n\n\nclass Doc(models.Model):\n"
        "    _name = 'x.doc'\n    _description = 'd'\n"
        "    _inherits = {'ir.attachment': 'ir_attachment_id'}\n"
        "    ir_attachment_id = fields.Many2one('ir.attachment', required=True)\n"
        "    line_ids = fields.One2many('x.thing', 'id')\n"
    )
    view = (
        "<odoo><record id='v_doc' model='ir.ui.view'><field name='model'>x.doc</field>"
        "<field name='arch' type='xml'><form><field name='mimetype'/>"
        "<field name='line_ids'><tree><field name='only_on_comodel'/></tree></field>"
        "</form></field></record>"
        "<record id='a' model='ir.actions.act_window'><field name='res_model'>x.doc</field>"
        "<field name='binding_model_id' ref='model_x_doc'/></record></odoo>"
    )
    r = ca.audit(zbytes(_tree(**{"models/doc.py": model, "views/doc.xml": view})), version=17)
    bad = [f for f in r.findings if f.severity == "high" and f.file == "views/doc.xml"]
    assert bad == [], bad


def test_r2_b3_unresolvable_parent_is_medium():
    model = (
        "from odoo import models\n\n\nclass D(models.Model):\n"
        "    _name = 'x.d'\n    _inherit = ['zz.unknown.mixin']\n"
    )
    view = (
        "<odoo><record id='v_d' model='ir.ui.view'><field name='model'>x.d</field>"
        "<field name='arch' type='xml'><form><field name='nope'/></form></field></record></odoo>"
    )
    r = ca.audit(zbytes(_tree(**{"models/d.py": model, "views/d.xml": view})), version=17)
    fu = [f for f in r.findings if f.code == "field-undefined" and "x.d" in f.message]
    assert fu and all(f.severity == "medium" for f in fu)


def test_r2_b3_abstract_no_access_needed():
    model = (
        "from odoo import models\n\n\nclass R(models.AbstractModel):\n"
        "    _name = 'report.x.r'\n    _description = 'r'\n"
    )
    r = ca.audit(zbytes(_tree(**{"models/r.py": model})), version=17)
    assert not any("report.x.r" in f.message for f in r.findings if f.code == "access-missing")


def test_r2_b3_missing_index_capped_and_deduped():
    fields_ = "".join(f"    f{i} = fields.Char()\n" for i in range(40))
    search = "".join(
        f"        self.search([('f{i}', '=', 1)])\n        self.search([('f{i}', '=', 2)])\n"
        for i in range(40)
    )
    model = (
        "from odoo import fields, models\n\n\nclass B(models.Model):\n    _name = 'x.big'\n"
        f"    _description = 'b'\n{fields_}\n    def go(self):\n{search}"
    )
    r = ca.audit(zbytes(_tree(**{"models/big.py": model})), version=17)
    idx = [(f.message) for f in r.findings if f.code == "missing-index"]
    assert 0 < len(idx) <= ca.MAX_INDEX_FINDINGS and len(idx) == len(set(idx))


@pytest.mark.parametrize(
    "q,high",
    [
        ("self._cr.execute('SELECT 1 FROM %s' % self._table)", False),
        ("self._cr.execute('SELECT * FROM t WHERE id = %s', (x,))", False),
        ("self._cr.execute(f'SELECT {self._table}.id FROM {self._table}')", False),
        ("self._cr.execute('SELECT ' + col + ' FROM t')", True),
        ("self._cr.execute(f'SELECT * FROM t WHERE n = {name}')", True),
        ("self._cr.execute('SELECT %s FROM t' % col, (x,))", True),
        ("self._cr.execute('SELECT {} FROM t'.format(col))", True),
    ],
)
def test_r2_b3_sql_injection_only_variable_built(q, high):
    model = (
        "from odoo import models\n\n\nclass S(models.Model):\n    _inherit = 'res.partner'\n\n"
        f"    def go(self, x, col, name):\n        {q}\n"
    )
    r = ca.audit(zbytes(_tree(**{"models/s.py": model})), version=17)
    got = any(
        f.code == "sql-injection" and f.severity == "high" and f.file == "models/s.py"
        for f in r.findings
    )
    assert got is high


def test_r2_b3_tests_dir_capped_low_and_static_skipped():
    files = _tree(
        **{
            "tests/test_x.py": "def t(cr, c):\n    cr.execute('SELECT ' + c)\n",
            "static/img/big.png": b"\x89PNG\r\n\x1a\n" + b"x" * 3_000_000,
            "static/src/x.xml": "<t t-name='a'><div attrs=\"{'a': 1}\"/></t>",
            "i18n/fr.po": 'msgid "Save"\nmsgstr "Enregistrer"\n',
        }
    )
    r = ca.audit(zbytes(files), version=17)
    assert r.ok, r.error
    assert all(f.severity == "low" for f in r.findings if f.file.startswith("tests/"))
    assert not any(f.file.startswith(("static/", "i18n/")) for f in r.findings)


@pytest.mark.parametrize("v", [17.0, "17", True, 17.5, None])
def test_r2_b4_version_exact_int(v):
    r = ca.audit(zbytes(TREE), version=v)
    assert not r.ok and "version" in r.error


def test_r2_b5_memory_and_recursion_per_file(monkeypatch):
    real = ca._audit_py

    def boom(c, path, body):
        if path == "models/thing.py":
            raise MemoryError
        if path == "__init__.py":
            raise RecursionError
        return real(c, path, body)

    monkeypatch.setattr(ca, "_audit_py", boom)
    r = ca.audit(zbytes(TREE), version=17)
    assert r.ok
    pe = {f.file for f in r.findings if f.code == "parse-error"}
    assert {"models/thing.py", "__init__.py"} <= pe


# ---------------------------------------------------------------- round 3


def _hi(r, code=None):
    return [f for f in r.findings if f.severity == "high" and (code is None or f.code == code)]


@pytest.mark.parametrize(
    "src",
    [
        "from os import system\nsystem(x)\n",
        "import os as o\no.system(x)\n",
        "from subprocess import run as r\nr(['id'])\n",
        "import importlib as il\nil.import_module(x)\n",
        "from builtins import eval as e\ne(x)\n",
        "from shutil import rmtree\nrmtree(x)\n",
        "import socket as s\ns.create_connection((h, 1))\n",
        "from ctypes import CDLL\nCDLL(x)\n",
        "from pickle import loads\nloads(x)\n",
        "import marshal as m\nm.loads(x)\n",
        "import yaml\nyaml.load(x)\n",
        "from yaml import load\nload(x)\n",
        "import os.path as p\nimport os as q\nq.popen(x)\n",
        "from os import path\nimport os\ngetattr(os, name)(x)\n",
    ],
)
def test_r3_alias_danger(src):
    r = ca.audit(zbytes(_tree(**{"models/evil.py": src})), version=17)
    assert _hi(r, "dangerous-call"), [f.code for f in r.findings]


def test_r3_alias_no_false_positive():
    src = "from os import path\nimport json\npath.join('a', 'b')\njson.loads(x)\n"
    r = ca.audit(zbytes(_tree(**{"models/ok.py": src})), version=17)
    assert not _hi(r, "dangerous-call")


@pytest.mark.parametrize("p", ["static/src/x.py", "i18n/x.py", "static/lib/deep/y.py"])
def test_r3_py_under_asset_dirs_audited(p):
    r = ca.audit(zbytes(_tree(**{p: "import os\nos.system('id')\n"})), version=17)
    assert any(f.file == p and f.code == "dangerous-call" for f in _hi(r))


def test_r3_tests_imported_by_prod_not_capped():
    evil = "import os\nos.system('id')\n"
    base = {"tests/__init__.py": "", "tests/evil.py": evil}
    capped = ca.audit(zbytes(_tree(**base)), version=17)
    assert all(
        f.severity == "low"
        for f in capped.findings
        if f.file.startswith("tests/") and f.code != "test-tamper"  # r7: shape is HIGH
    )
    for init in (
        "from . import models\nfrom .tests import evil\n",
        "from . import models\nfrom . import tests\n",
        "from . import models\nfrom odoo.addons.demo.tests import evil\n",
    ):
        files = _tree(**{**base, "__init__.py": init, "tests/__init__.py": "from . import evil\n"})
        r = ca.audit(zbytes(files), version=17, module_name="demo")
        assert any(f.file == "tests/evil.py" for f in _hi(r)), init


def test_r3_tests_listed_in_manifest_not_capped():
    files = _tree(**{"tests/evil.xml": "<odoo><template id='t'><div t-raw='x'/></template></odoo>"})
    m = files["__manifest__.py"]
    files["__manifest__.py"] = m.replace("'data': [", "'data': ['tests/evil.xml', ")
    assert files["__manifest__.py"] != m
    r = ca.audit(zbytes(files), version=17)
    assert any(f.file == "tests/evil.xml" for f in _hi(r))


INHERIT_SALE = """<odoo><record id="v_so" model="ir.ui.view">
<field name="name">so.x</field><field name="model">sale.order</field>
<field name="inherit_id" ref="sale.view_order_form"/>
<field name="arch" type="xml">
<xpath expr="//field[@name='partner_id']" position="after"><field name="x_nonexistent_zz"/>
<field name="partner_shipping_id"/></xpath>
<field name="note" position="before"><field name="x_other_zz"/></field>
</field></record></odoo>"""


@pytest.mark.parametrize("v", [17, 18, 19, 20])
def test_r3_field_undefined_in_inheriting_view(v):
    files = _tree(**{"views/so.xml": INHERIT_SALE})
    files["__manifest__.py"] = files["__manifest__.py"].replace(
        "'depends': [", "'depends': ['sale', "
    )
    r = ca.audit(zbytes(files), version=v)
    msgs = [f.message for f in _hi(r) if f.file == "views/so.xml"]
    assert any("x_nonexistent_zz" in m for m in msgs) and any("x_other_zz" in m for m in msgs)
    assert not any("partner_shipping_id" in m for m in msgs)


def test_r3_unresolvable_model_is_medium():
    view = INHERIT_SALE.replace("sale.order", "zz.unknown.model")
    r = ca.audit(zbytes(_tree(**{"views/so.xml": view})), version=17)
    fu = [f for f in r.findings if f.code == "field-unresolved"]
    assert fu and all(f.severity == "medium" for f in fu)
    nomodel = INHERIT_SALE.replace('<field name="model">sale.order</field>', "")
    r = ca.audit(zbytes(_tree(**{"views/so.xml": nomodel})), version=17)
    assert any(f.code == "field-unresolved" and f.severity == "medium" for f in r.findings)


@pytest.mark.parametrize(
    "attr",
    [
        "t-out=\"doc.sudo().write({'a': 1})\"",
        "t-esc=\"doc.env['res.users'].sudo().search([]).password\"",
        't-att-title="user.api_key"',
    ],
)
def test_r3_qweb_orm_call(attr):
    xml = f"<odoo><template id='t'><div {attr}/></template></odoo>"
    r = ca.audit(zbytes(_tree(**{"views/t.xml": xml})), version=17)
    assert any(f.code == "qweb-orm-call" and f.severity in ("medium", "high") for f in r.findings)


@pytest.mark.parametrize(
    "body",
    [
        "q = 'SELECT * FROM t WHERE n = %s' % name\n        self.env.cr.execute(q)\n",
        "q = f'SELECT * FROM t WHERE n = {name}'\n        self.env.cr.execute(q)\n",
        "q = 'SELECT {}'.format(name)\n        self.env.cr.execute(q)\n",
        "q = 'SELECT ' + name\n        self.env.cr.execute(q)\n",
        "q = 'SELECT 1'\n        q += name\n        self.env.cr.execute(q)\n",
    ],
)
def test_r3_sql_injection_via_local(body):
    src = f"class X:\n    def m(self, name):\n        {body}"
    r = ca.audit(zbytes(_tree(**{"models/sql.py": src})), version=17)
    assert _hi(r, "sql-injection"), [f.code for f in r.findings]


def test_r3_sql_local_safe_not_flagged():
    src = (
        "class X:\n    def m(self, name):\n"
        "        q = 'SELECT * FROM t WHERE n = %s'\n        self.env.cr.execute(q, (name,))\n"
    )
    r = ca.audit(zbytes(_tree(**{"models/sql.py": src})), version=17)
    assert not [f for f in _hi(r, "sql-injection") if f.file == "models/sql.py"]


def test_r3_owl_templates_scanned():
    xml = (
        "<templates><t t-name='a'><div t-raw='props.html'/>"
        "<span t-out='markup(props.x)'/></t></templates>"
    )
    r = ca.audit(zbytes(_tree(**{"static/src/a.xml": xml})), version=17)
    codes_ = {f.code for f in r.findings if f.file == "static/src/a.xml"}
    assert {"qweb-t-raw", "unsafe-markup"} <= codes_


# ---- round 4: SQL reassignment / join / SQL(), star imports, outbound network
MAN = b"{'name': 'x', 'depends': ['base'], 'license': 'LGPL-3'}"


def _sev(code_text, path="models/m.py"):
    fs = {"__manifest__.py": MAN, "__init__.py": b"", path: code_text.encode()}
    r = ca.audit(zbytes(fs, root="x_m"), version=17, owned_names={"x_m"})
    return {(f.severity, f.code) for f in r.findings if f.file.endswith(path.rsplit("/", 1)[-1])}


@pytest.mark.parametrize(
    "src",
    [
        "def f(cr, name):\n    q = 'SELECT 1 WHERE a='\n    q = q + name\n    cr.execute(q)\n",
        "def f(cr, n):\n    q = 'S'\n    q = q + 'x'\n    q = q + n\n    cr.execute(q)\n",
        "def f(cr, name):\n    cr.execute(' '.join(['SELECT', name]))\n",
        "def f(cr, name):\n    cr.execute(', '.join(name))\n",
        "from odoo.tools import SQL\ndef f(cr, name):\n    cr.execute(SQL('SELECT ' + name))\n",
        "from odoo.tools import SQL\ndef f(cr, n):\n    cr.execute(SQL(f'SELECT {n}'))\n",
    ],
)
def test_r4_dynamic_sql_flagged(src):
    assert ("high", "sql-injection") in _sev(src)


@pytest.mark.parametrize(
    "src",
    [
        "def f(cr):\n    q = 'SELECT 1 '\n    q = q + 'FROM t'\n    cr.execute(q)\n",
        "def f(cr):\n    cr.execute(' '.join(['SELECT', '1']))\n",
        "from odoo.tools import SQL\ndef f(cr, name):\n    cr.execute(SQL('SELECT %s', name))\n",
    ],
)
def test_r4_literal_sql_not_injection(src):
    assert ("high", "sql-injection") not in _sev(src)


@pytest.mark.parametrize("mod", ["os", "subprocess", "builtins", "shutil", "socket", "ctypes"])
def test_r4_star_import_from_risky_module_high(mod):
    assert ("high", "dangerous-import") in _sev(f"from {mod} import *\ndef f(x):\n    system(x)\n")


@pytest.mark.parametrize(
    "src,path,sev",
    [
        ("import requests\n", "models/m.py", "low"),
        ("import requests\n", "__init__.py", "medium"),
        ("from urllib import request\n", "__init__.py", "medium"),
        ("import http.client\n", "hooks.py", "medium"),
        ("import urllib.request\n", "models/m.py", "low"),
    ],
)
def test_r4_outbound_network_flagged(src, path, sev):
    assert (sev, "outbound-network") in _sev(src, path)


# ---------------------------------------------------------------- round 5
R5_SQL = [
    "self.env.cr.execute(\"COPY t FROM PROGRAM 'id'\")",
    "self.env.cr.execute('ALTER DATABASE x SET search_path = evil, public')",
    "self.env.cr.execute('ALTER ROLE odoo SET work_mem = 1')",
    "self.env.cr.execute('ALTER SYSTEM SET x = 1')",
    "self.env.cr.execute('CREATE SCHEMA evil')",
    "self.env.cr.execute('SET search_path TO evil, public')",
    "self.env.cr.copy_expert(\"COPY t TO PROGRAM 'sh'\", f)",
]


@pytest.mark.parametrize("line", R5_SQL)
def test_r5_constant_dangerous_sql_high(line) -> None:
    rep = _r5(f"        {line}\n")
    assert any(f.code == "sql-dangerous" and f.severity == ca.HIGH for f in rep.findings), line


@pytest.mark.parametrize(
    "line",
    [
        "self.env.cr.copy_expert('COPY ' + name + ' TO STDOUT', f)",
        "execute_values(self.env.cr, 'INSERT INTO ' + name + ' VALUES %s', rows)",
    ],
)
def test_r5_variable_sql_in_copy_and_execute_values(line) -> None:
    rep = _r5(f"        name = self.x\n        {line}\n")
    assert any(f.code == "sql-injection" and f.severity == ca.HIGH for f in rep.findings), line


def test_r5_plain_select_not_dangerous() -> None:
    rep = _r5("        self.env.cr.execute('SELECT id FROM res_partner WHERE id = %s', (1,))\n")
    assert not any(f.code in ("sql-dangerous", "sql-injection") for f in rep.findings)


def test_r5_net_in_hook_function_is_medium() -> None:
    body = "import requests\n\n\ndef post_init_hook(env):\n    requests.get('http://x')\n"
    rep = _r5_files({"models/setup.py": body})
    f = [x for x in rep.findings if x.code == "outbound-network"]
    assert f and f[0].severity == ca.MEDIUM


@pytest.mark.parametrize(
    "body",
    [
        "from odoo.tests.result import OdooTestResult\n"
        "OdooTestResult.addFailure = lambda *a: None\n",
        "import unittest\nunittest.TestResult.addError = lambda *a: None\n",
        "def f(r):\n    r.addFailure = None\n",
    ],
)
def test_r5_test_runner_tamper_is_high(body) -> None:
    rep = _r5_files({"tests/__init__.py": body})
    assert any(f.code == "test-tamper" and f.severity == ca.HIGH for f in rep.findings)


def _r5_files(extra: dict) -> ca.Report:
    files = {
        "__manifest__.py": b"{'name': 'x_r5', 'version': '17.0.1.0.0', 'depends': ['base'],"
        b" 'license': 'LGPL-3', 'data': []}",
        "__init__.py": b"from . import models\n",
        "models/__init__.py": b"",
    }
    files |= {k: v.encode() for k, v in extra.items()}
    return ca.audit(zbytes(files, root="x_r5"), version=17)


def _r5(method_body: str) -> ca.Report:
    src = (
        "from odoo import models\nfrom psycopg2.extras import execute_values\n\n\n"
        "class X(models.Model):\n    _inherit = 'res.partner'\n\n"
        "    def go(self, f=None, rows=()):\n" + method_body
    )
    return _r5_files({"models/x.py": src})


@pytest.mark.parametrize("v", [17, 18, 19])
def test_clean_req2mod_module_audits_clean_at_its_own_version(v):
    """Regression for the round 5 report: the clean generated module has no HIGH/MEDIUM finding."""
    import copy

    from module_generator import build_module_zip
    from test_nf_bot_req2mod import ASSETS, BASE

    from app.bots import req2mod as rm

    r = rm.build(copy.deepcopy(ASSETS), version=v, installed_modules=BASE, technical_name="x_clean")
    rep = ca.audit(build_module_zip(r.spec), version=v, owned_names={"x_clean"})
    bad = [(f.severity, f.code) for f in rep.findings if f.severity in (ca.HIGH, ca.MEDIUM)]
    assert bad == []
    if v != 17:
        wrong = ca.audit(build_module_zip(r.spec), version=17, owned_names={"x_clean"})
        assert {f.code for f in wrong.findings} & {"version-list", "version-manifest"}


R6_TAMPER = [
    "from odoo.tests.common import TransactionCase as T\nT.assertEqual = lambda *a, **k: None\n",
    "from odoo.tests import common\ncommon.TransactionCase.assertTrue = lambda *a: None\n",
    "from odoo.tests.common import TransactionCase\n"
    "setattr(TransactionCase, 'assertTrue', print)\n",
    "from odoo.tests.common import TransactionCase\nfor n in dir(TransactionCase):\n"
    "    setattr(TransactionCase, n, None)\n",
    "from unittest import mock\n"
    "mock.patch('odoo.tests.common.TransactionCase.assertEqual').start()\n",
    "from unittest import mock\nfrom odoo.tests.common import TransactionCase as T\n"
    "mock.patch.object(T, 'assertEqual').start()\n",
    "import unittest\nunittest.TestCase.failureException = Exception\n",
    "from odoo.tests.common import TransactionCase as T\nT.run = lambda *a: None\n",
    "import sys\nsys.modules['odoo.tests.result'] = object()\n",
    "import sys\nsys.modules.update({})\n",
    "import os\nfor f in os.listdir('/var/tmp'):\n    pass\n",
    "import os\nfd = os.open('/var/tmp/r/x.xml', 1)\nos.write(fd, b'x')\n",
    "from pathlib import Path\nPath(p).write_text('ok')\n",
    "from pathlib import Path\nlist(Path(d).glob('*.xml'))\n",
    "import glob\nglob.glob(p)\n",
    "x = open(p, 'w')\n",
    "import threading\nthreading.Thread(target=f).start()\n",
    "s = '/proc/self/environ'\n",
]


@pytest.mark.parametrize("src", R6_TAMPER)
def test_r6_result_forging_is_high_test_tamper(src):
    for path in ("models/m.py", "tests/test_x.py"):
        r = _r5_files({path: src})
        hits = [f for f in r.findings if f.code == "test-tamper"]
        assert hits and all(f.severity == ca.HIGH for f in hits), (path, src)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE FUNCTION f() RETURNS int LANGUAGE sql SECURITY DEFINER AS 'select 1'",
        "SET ROLE postgres",
        "SET SESSION AUTHORIZATION postgres",
        "CREATE EVENT TRIGGER t ON ddl_command_start EXECUTE FUNCTION f()",
        "GRANT ALL ON ALL TABLES IN SCHEMA public TO PUBLIC",
        "CREATE ROLE r",
    ],
)
def test_r6_privilege_sql_is_high(sql):
    src = f"def hook(env):\n    env.cr.execute({sql!r})\n"
    r = _r5_files({"models/m.py": src})
    assert any(f.code == "sql-dangerous" and f.severity == ca.HIGH for f in r.findings), sql


def test_r6_ordinary_code_not_flagged():
    src = (
        "from odoo import models, fields\n\n\nclass X(models.Model):\n"
        "    _inherit = 'res.partner'\n"
        "    failed = fields.Boolean()\n\n    def go(self):\n        for r in self:\n"
        "            r.failed = True\n            setattr(r, 'name', 'x')\n"
        "        with open(__file__) as fh:\n            return fh.read()\n"
    )
    assert "test-tamper" not in codes(_r5_files({"models/m.py": src}))


R7_TAMPER = [
    *(
        f"from odoo.tests.common import TransactionCase\nclass T(TransactionCase):\n"
        f"    def {m}(self, *a):\n        return None\n"
        for m in sorted(ca._CASE_DEF)
    ),
    "import sys\nf = sys._getframe(1)\n",
    "from sys import _getframe as g\ng(2)\n",
    "import inspect as i\ni.stack()\n",
    "import inspect\ninspect.currentframe()\n",
    "import inspect\ninspect.getouterframes(None)\n",
    "import gc\ngc.get_objects()\n",
    "import atexit\natexit.register(print)\n",
    "import sys\nsys.settrace(None)\n",
    "import sys\nsys.setprofile(None)\n",
    "import os\nos.register_at_fork(after_in_child=print)\n",
    "import multiprocessing\n",
]


@pytest.mark.parametrize("src", R7_TAMPER)
def test_r7_runner_hooks_and_introspection_are_high(src):
    for path in ("models/m.py", "tests/test_x.py"):
        r = _r5_files({path: src})
        hits = [f for f in r.findings if f.code == "test-tamper"]
        assert hits and all(f.severity == ca.HIGH for f in hits), (path, src)


@pytest.mark.parametrize(
    "files",
    [
        {"tests/sub/test_x.py": "x = 1\n"},
        {"tests/helpers.py": "x = 1\n"},
        {"tests/__init__.py": "import os\n"},
        {"tests/__init__.py": "from . import test_a as b\n"},
        {"tests/__init__.py": "from . import test_a\nx = 1\n"},
    ],
)
def test_r7_test_files_fixed_shape(files):
    # owned (generated) modules: the gate's test layout is enforced HIGH
    base = {
        "__manifest__.py": b"{'name': 'x_r5', 'version': '17.0.1.0.0', 'depends': ['base'],"
        b" 'license': 'LGPL-3', 'data': []}",
        "__init__.py": b"from . import models\n",
        "models/__init__.py": b"",
    } | {k: v.encode() for k, v in files.items()}
    r = ca.audit(zbytes(base, root="x_r5"), version=17, owned_names=["x_r5"])
    assert any(f.code == "test-tamper" and f.severity == ca.HIGH for f in r.findings), files
    # foreign modules: a layout note only (M5 noise), never silent
    r = _r5_files(files)
    assert any(f.code in ("test-layout", "test-tamper") for f in r.findings), files


def test_r7_plain_test_shape_is_clean():
    r = _r5_files(
        {
            "tests/__init__.py": "from . import test_a\n",
            "tests/test_a.py": "from odoo.tests.common import TransactionCase\n\n\n"
            "class TestA(TransactionCase):\n    def setUp(self):\n        super().setUp()\n\n"
            "    def test_a(self):\n        self.assertTrue(True)\n",
        }
    )
    assert not [f for f in r.findings if f.code == "test-tamper"]


# ---- round 9 GATE 1: a module must not rewrite another module's security records by xml id

_FX = (
    '<?xml version="1.0"?>\n<odoo>\n<record id="{rid}" model="{model}">\n'
    '<field name="name">x</field>\n</record>\n</odoo>\n'
)


@pytest.mark.parametrize(
    "model",
    ["ir.rule", "ir.model.access", "res.groups", "res.users", "ir.config_parameter", "ir.cron"],
)
def test_foreign_xmlid_on_guarded_model_is_high(model):
    t = dict(TREE, **{"data/x.xml": _FX.format(rid="base.some_record", model=model)})
    f = [x for x in ca.audit(zbytes(t), version=17).findings if x.code == "foreign-record-edit"]
    assert f and f[0].severity == ca.HIGH


@pytest.mark.parametrize(
    "rid, model",
    [("demo.my_rule", "ir.rule"), ("my_rule", "ir.rule"), ("base.main_partner", "res.partner")],
)
def test_own_or_unguarded_xmlid_not_flagged(rid, model):
    t = dict(TREE, **{"data/x.xml": _FX.format(rid=rid, model=model)})
    assert "foreign-record-edit" not in codes(ca.audit(zbytes(t), version=17))


def test_foreign_row_in_guarded_csv_is_high():
    t = dict(TREE, **{"data/ir.rule.csv": "id,name\nbase.res_partner_rule,x\n"})
    assert "foreign-record-edit" in codes(ca.audit(zbytes(t), version=17))
    t = dict(TREE, **{"data/ir.rule.csv": "id,name\nmy_rule,x\n"})
    assert "foreign-record-edit" not in codes(ca.audit(zbytes(t), version=17))


# ---------------------------------------------------------------- BOT-CODE-AUDIT-2 web layer


def _web(files, **kw):
    return ca.audit(zbytes(_tree(**files)), version=17, **kw)


def _codes(r, file=None):
    return {f.code for f in r.findings if file is None or f.file == file}


def test_web_oversized_js_fails_closed():
    r = _web({"static/src/big.js": "x" * 3_000_000, "static/src/b.js": "eval(x)\n"})
    got = {(f.code, f.file, f.severity) for f in r.findings}
    # the oversized file is HIGH unaudited and every other file is still audited
    assert r.ok and ("file-unaudited", "static/src/big.js", "high") in got
    assert ("js-eval", "static/src/b.js", "high") in got


@pytest.mark.parametrize(
    "src,code,line",
    [
        ("const a = 1;\neval(x);\n", "js-eval", 2),
        ("el.innerHTML = v;\n", "js-html-sink", 1),
        ("fetch('https://evil.example/x');\n", "js-external-request", 1),
        ("navigator.serviceWorker.register('/sw.js');\n", "js-service-worker", 1),
        ("localStorage.setItem('token', t);\n", "js-token-storage", 1),
    ],
)
def test_web_js_shapes(src, code, line):
    r = _web({"static/src/a.js": src})
    assert r.ok, r.error
    hit = [f for f in r.findings if f.code == code]
    assert hit and hit[0].line == line and hit[0].file == "static/src/a.js"


@pytest.mark.parametrize(
    "src",
    [
        "const a = 1;\nconsole.log(a);\n",
        "el.textContent = v;\n",
        "fetch('/web/dataset/call_kw');\n",
        "localStorage.setItem('theme', 'dark');\n",
    ],
)
def test_web_js_negative(src):
    r = _web({"static/src/a.js": src})
    assert r.ok and not _codes(r, "static/src/a.js"), r.findings


@pytest.mark.parametrize(
    "path,src,code",
    [
        ("static/src/a.css", "@import url(https://evil.example/x.css);\n", "css-external-import"),
        ("static/src/a.scss", "a { b: url(https://cdn.example/f.woff); }\n", "css-external-url"),
        ("static/src/a.less", "a { b: expression(alert(1)); }\n", "css-expression"),
    ],
)
def test_web_css_shapes(path, src, code):
    r = _web({path: src})
    assert code in _codes(r, path), r.findings


def test_web_css_negative():
    r = _web({"static/src/a.scss": "$c: red;\na { color: $c; b: url('/m/static/x.png'); }\n"})
    assert r.ok and not _codes(r, "static/src/a.scss")


def test_web_parse_error_unaudited():
    r = _web({"static/src/a.js": "function (\n"})
    f = [f for f in r.findings if f.code == "web-unaudited"]
    assert f and f[0].severity == "high" and "Cannot parse, unaudited" in f[0].message


def test_web_no_parser_type_unaudited():
    r = _web(
        {
            "static/src/a.ts": "let a: number = 1;\n",
            "static/src/b.sass": "a\n  b: c\n",
            "static/src/c.d.ts": "declare const a: number;\n",
            "static/src/d.styl": "a\n  b c\n",
            "static/src/e.jsx": "eval(x)\n",
        }
    )
    sev = {f.file: f.severity for f in r.findings if f.code == "web-unaudited"}
    # .ts/.tsx/.jsx (sucrase) and .sass (line-preserving rewrite) are parsed and audited
    assert sev == {
        "static/src/d.styl": "high",
    }
    assert ("js-eval", "high") in {
        (f.code, f.severity) for f in r.findings if f.file.endswith("e.jsx")
    }


@pytest.mark.parametrize(
    "el",
    [
        "<script>\nvar a = \"<t t-esc='v'/>\";\n</script>",
        "<script>\nvar a = 'x\\' <t t-esc=\"v\"/>';\n</script>",
    ],
)
def test_xml_script_output_in_string_is_low(el):
    src = f"<odoo>\n<template id='a'>\n{el}\n</template>\n</odoo>\n"
    assert [g[0] for g in _xml(src) if g[0] == "qweb-script-injection"] == ["qweb-script-injection"]
    r = ca.audit(zbytes(_tree(**{"views/t.xml": src})), version=17)
    assert {f.severity for f in r.findings if f.code == "qweb-script-injection"} == {"low"}


@pytest.mark.parametrize(
    "attr,val",
    [
        ("HELPER_SHA256", "0" * 64),
        ("LOCK_SHA256", "0" * 64),
        ("MODULES_SHA256", "0" * 64),
        ("NODE_MIN_MAJOR", 999),
    ],
)
def test_web_helper_unavailable_fails_closed(monkeypatch, attr, val):
    from app.bots import code_audit_web as w

    monkeypatch.setattr(w, attr, val)
    r = _web({"static/src/a.js": "const a = 1;\n", "static/src/b.css": "a{}\n"})
    assert r.ok
    for p in ("static/src/a.js", "static/src/b.css"):
        hit = [f for f in r.findings if f.file == p]
        assert [f.code for f in hit] == ["web-unaudited"] and hit[0].severity == "high"


def test_web_node_missing_fails_closed(monkeypatch):
    from app.bots import code_audit_web as w

    monkeypatch.setattr(w, "_node", lambda: None)
    r = _web({"static/src/a.js": "const a = 1;\n"})
    assert "web-unaudited" in _codes(r, "static/src/a.js")


# ---------------------------------------------------------------- BOT-CODE-AUDIT-2 python flow


def _py(src, path="models/x.py"):
    r = ca.audit(zbytes(_tree(**{path: src})), version=17)
    assert r.ok, r.error
    return [(f.code, f.line, f.severity) for f in r.findings if f.file == path]


@pytest.mark.parametrize(
    "src,line",
    [
        ("import os as o\no.system('x')\n", 2),
        ("from os import system as s\ns('x')\n", 2),
        ("import os\ns = os\nf = s.system\nf('x')\n", 4),
        ("import os\ngetattr(os, 'system')('x')\n", 2),
        ("import importlib\nm = importlib.import_module('subprocess')\nm.run(['x'])\n", 3),
        ("m = __import__('os')\nm.system('x')\n", 2),
        ("import sys\nsys.modules['os'].system('x')\n", 2),
        ("try:\n    import subprocess as sp\nexcept ImportError:\n    sp = None\nsp.run('x')\n", 5),
        ("if True:\n    from os import popen\npopen('x')\n", 3),
        ("from os import *\nsystem('x')\n", 2),
        ("import os.path as p\nimport shutil as sh\nsh.rmtree(p.join('a'))\n", 3),
    ],
)
def test_flow_alias_shapes(src, line):
    got = _py(src)
    assert ("dangerous-call", line, "high") in got, got


@pytest.mark.parametrize(
    "src",
    [
        "import os.path\nos.path.join('a', 'b')\n",
        "from odoo import api as a\na.model\n",
        "def system(x):\n    return x\nsystem('x')\n",
        "import json as j\nj.dumps({})\n",
        "x = getattr(self, 'name')\n",
    ],
)
def test_flow_alias_negative(src):
    assert not [g for g in _py(src) if g[0] == "dangerous-call"]


def test_flow_dynamic_module_attr_flagged():
    got = _py("import odoo.tools as t\ndef f(n):\n    return getattr(t, n)()\n")
    assert ("dynamic-dispatch", 3, "low") in got


CTRL = "from odoo import http\nfrom odoo.http import request\nfrom markupsafe import Markup\n"


@pytest.mark.parametrize(
    "body,code,line",
    [
        ("@http.route('/a')\ndef a(self, q):\n    return Markup(q)\n", "tainted-markup", 6),
        (
            "@http.route('/a')\ndef a(self, **kw):\n    s = '<b>%s</b>' % kw.get('q')\n"
            "    return Markup(s)\n",
            "tainted-markup",
            7,
        ),
        (
            "def a(self):\n    q = request.params['q']\n    self.env.cr.execute(q)\n",
            "tainted-sql",
            6,
        ),
        (
            "def a(self):\n    v = request.httprequest.args.get('x')\n"
            "    self.env.cr.execute('SELECT ' + v)\n",
            "sql-injection",
            6,
        ),
        ("def a(self):\n    return Markup(self.description)\n", "tainted-markup", 5),
        (
            "def a(self):\n    for r in self:\n        h = f'<p>{r.note}</p>'\n"
            "        yield Markup(h)\n",
            "tainted-markup",
            7,
        ),
        (
            "@http.route('/a')\ndef a(self, expr):\n"
            "    from odoo.tools.safe_eval import safe_eval\n"
            "    return safe_eval(expr)\n",
            "tainted-eval",
            7,
        ),
        (
            "@http.route('/a')\ndef a(self, q):\n    return request.make_response('<p>' + q)\n",
            "tainted-response",
            6,
        ),
        (
            "import werkzeug\n@http.route('/a')\ndef a(self, url):\n"
            "    return werkzeug.utils.redirect(url)\n",
            "open-redirect",
            7,
        ),
        (
            "@http.route('/a')\ndef a(self, url):\n    return request.redirect(url, local=False)\n",
            "open-redirect",
            6,
        ),
    ],
)
def test_flow_taint_shapes(body, code, line):
    got = _py(CTRL + body, "controllers/main.py")
    assert any(g[0] == code and g[1] == line for g in got), got


@pytest.mark.parametrize(
    "body",
    [
        "@http.route('/a')\ndef a(self, q):\n    return Markup('<b>%s</b>') % q\n",
        "@http.route('/a')\ndef a(self, q):\n    return Markup(escape(q))\n",
        "@http.route('/a')\ndef a(self, q):\n"
        "    self.env.cr.execute('SELECT 1 WHERE a = %s', [q])\n",
        "@http.route('/a')\ndef a(self, q):\n    return request.redirect(q)\n",
        "@http.route('/a')\ndef a(self, i):\n    return request.make_response(self._pdf(int(i)))\n",
        "def a(self):\n    return Markup(self.amount_total)\n",
        "def a(self, q):\n    return Markup(q)\n",
    ],
)
def test_flow_taint_negative(body):
    got = _py(CTRL + body, "controllers/main.py")
    assert not [g for g in got if g[0].startswith("tainted") or g[0] == "open-redirect"], got


@pytest.mark.parametrize(
    "src,code,line",
    [
        ("def f(self, ids):\n    for i in ids:\n        self.browse(i).name\n", "query-in-loop", 3),
        (
            "def f(self, ids):\n    return [self.search([('id', '=', i)]) for i in ids]\n",
            "query-in-loop",
            2,
        ),
        (
            "def f(self):\n    return self.mapped(lambda r: r.env['x'].search_count([]))\n",
            "query-in-loop",
            2,
        ),
        ("def f(self, vals):\n    for v in vals:\n        self.create(v)\n", "orm-in-loop", 3),
        (
            "def _h(self):\n    return self.env['x'].search([])\n"
            "def _g(self):\n    return self._h()\n"
            "def f(self):\n    for r in self:\n        r._g()\n",
            "query-in-loop-helper",
            7,
        ),
        ("def f(self):\n    for r in self:\n        r.sudo().partner_id.name\n", "n-plus-one", 3),
        ("def f(self, ids):\n    while ids:\n        self.browse(ids.pop())\n", "query-in-loop", 3),
    ],
)
def test_flow_loop_shapes(src, code, line):
    got = _py(src)
    assert any(g[0] == code and g[1] == line for g in got), got


@pytest.mark.parametrize(
    "src",
    [
        "def f(self):\n    for r in self.search([]):\n        r.name\n",
        "def f(self):\n    return [r.partner_id.name for r in self.search([])]\n",
        "def f(self):\n    for r in self:\n        r.partner_id.name\n",
        "def f(self):\n    for r in self:\n        r.with_company(r.company_id).x = 1\n",
        "def f(self):\n    recs = self.search([])\n    for r in recs:\n        pass\n",
    ],
)
def test_flow_loop_negative(src):
    got = _py(src)
    assert not [g for g in got if "loop" in g[0] or g[0] == "n-plus-one"], got


# ---------------------------------------------------------------- BOT-CODE-AUDIT-2 xml lines/OWL


def _xml(src, path="views/v.xml"):
    r = ca.audit(zbytes(_tree(**{path: src})), version=17)
    assert r.ok, r.error
    return [(f.code, f.line, f.severity) for f in r.findings if f.file == path]


def test_xml_exact_lines_multiline_attr_and_siblings():
    src = (
        "<odoo>\n"
        "  <template id='a'>\n"
        "    <div\n"
        "       class='x'\n"
        "       t-raw='v'/>\n"
        "    <span t-raw='a'/><span t-raw='b'/>\n"
        "    <p class='t-raw=' t-esc='1'/><p t-raw='c'/>\n"
        "  </template>\n"
        "</odoo>\n"
    )
    lines = sorted(g[1] for g in _xml(src) if g[0] == "qweb-t-raw")
    assert lines == [5, 6, 6, 7]


def test_xml_exact_line_code_field_body():
    src = (
        "<odoo>\n<record id='c' model='ir.actions.server'>\n"
        "  <field name='code'><![CDATA[\n\n    x = 1\n\n    __import__('os')\n]]></field>\n"
        "</record>\n</odoo>\n"
    )
    assert ("unsafe-expression", 7, "high") in _xml(src)


def test_xml_same_needle_twice_gets_second_line():
    src = (
        "<odoo>\n<template id='a'>\n<t t-esc='1'/>\n</template>\n"
        "<template id='b'>\n<div t-raw='x'/>\n</template>\n</odoo>\n"
    )
    assert [g[1] for g in _xml(src) if g[0] == "qweb-t-raw"] == [6]


@pytest.mark.parametrize(
    "el,code,line",
    [
        ("<a href='javascript:alert(1)'/>", "qweb-js-url", 3),
        ("<a href='  JaVa&#x09;Script:x'/>", "qweb-js-url", 3),
        ("<a t-att-href=\"'javascript:' + x\"/>", "qweb-js-url", 3),
        ("<script src='https://evil.example/x.js'/>", "qweb-external-resource", 3),
        ("<iframe src='//evil.example/'/>", "qweb-external-resource", 3),
        ("<link rel='stylesheet' href='https://cdn.example/x.css'/>", "qweb-external-resource", 3),
        ("<script t-att-src='url'/>", "qweb-dynamic-resource", 3),
        ("<div t-out='Markup(x)'/>", "unsafe-markup", 3),
        ("<script>\nvar a = 1;\neval(a);\n</script>", "js-eval", 5),
    ],
)
def test_xml_owl_shapes(el, code, line):
    src = f"<odoo>\n<template id='a'>\n{el}\n</template>\n</odoo>\n"
    got = _xml(src)
    assert (code, line) in [(g[0], g[1]) for g in got], got


@pytest.mark.parametrize(
    "el",
    [
        "<a href='/web#action=1'/>",
        "<a t-att-href='record.url'/>",
        "<script src='/web/static/x.js'/>",
        "<link rel='icon' href='https://x.example/i.png'/>",
        "<script type='application/json'>{\"a\": 1}</script>",
        "<script>\nvar a = 1;\n</script>",
        "<div t-out='x'/>",
    ],
)
def test_xml_owl_negative(el):
    src = f"<odoo>\n<template id='a'>\n{el}\n</template>\n</odoo>\n"
    bad = {"qweb-js-url", "qweb-external-resource", "qweb-dynamic-resource", "unsafe-markup"}
    got = _xml(src)
    assert not [g for g in got if g[0] in bad or g[0].startswith(("js-", "web-"))], got


def test_xml_static_owl_template_lines():
    src = "<templates>\n<t t-name='x'>\n  <div t-out='markup(v)'/>\n</t>\n</templates>\n"
    assert ("unsafe-markup", 3) in [(g[0], g[1]) for g in _xml(src, "static/src/x.xml")]


def test_xml_lxml_missing_fails_closed(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "lxml", None)
    got = _xml("<odoo/>\n")
    assert ("xml-unaudited", 0, "high") in got


@pytest.mark.parametrize(
    "src",
    [
        "<!DOCTYPE x [<!ENTITY a 'b'>]><odoo>&a;</odoo>",
        "<odoo>" + " " * 5000 + "<!ENTITY a 'b'></odoo>",
    ],
)
def test_xml_dtd_still_refused(src):
    assert "parse-error" in [g[0] for g in _xml(src)]


def test_xml_inline_script_with_qweb_output_parses_and_keeps_lines():
    src = (
        "<odoo>\n<template id='a'>\n<script>\n"
        "  var s = {csrf: \"<t t-esc='request.csrf_token(None)'/>\"};\n"
        "  var d = <t t-out='json.dumps(x)'/>;\n"
        "  eval(d);\n</script>\n</template>\n</odoo>\n"
    )
    got = _xml(src)
    assert ("js-eval", 6) in [(g[0], g[1]) for g in got], got
    assert not [g for g in got if g[0] == "web-unaudited"]


@pytest.mark.parametrize(
    "src,hit",
    [
        ("localStorage.setItem('menus_version', session.registry_hash);\n", False),
        ("localStorage.setItem('author', name);\n", False),
        ("localStorage.setItem('k', session.access_token);\n", True),
        ("sessionStorage.setItem('auth_token', t);\n", True),
    ],
)
def test_web_token_storage_precision(src, hit):
    r = _web({"static/src/a.js": src})
    assert ("js-token-storage" in _codes(r, "static/src/a.js")) is hit


@pytest.mark.parametrize(
    "body,code,line",
    [
        (
            "def wrap(x):\n    return '<b>' + x + '</b>'\n"
            "@http.route('/a')\ndef a(self, q):\n    return Markup(wrap(q))\n",
            "tainted-markup",
            8,
        ),
        (
            "def w1(x):\n    return x.strip()\ndef w2(y):\n    return w1(y)\n"
            "@http.route('/a')\ndef a(self, q):\n    self.env.cr.execute(w2(q))\n",
            "tainted-sql",
            10,
        ),
        (
            "@http.route('/a')\ndef a(self, action, rid):\n"
            "    rec = request.env['res.partner'].browse(int(rid))\n"
            "    return getattr(rec, action)()\n",
            "tainted-dispatch",
            7,
        ),
        (
            "@http.route('/a')\ndef a(self, model):\n    return request.env[model].search([])\n",
            "tainted-model",
            6,
        ),
        (
            "@http.route('/a')\ndef a(self, m):\n    return request.env[m].sudo().search([])\n",
            "tainted-model",
            6,
        ),
    ],
)
def test_flow_taint_interprocedural_and_dispatch(body, code, line):
    got = _py(CTRL + body, "controllers/main.py")
    assert any(g[0] == code and g[1] == line for g in got), got


@pytest.mark.parametrize(
    "body",
    [
        "def fixed(x):\n    return 'SELECT 1'\n"
        "@http.route('/a')\ndef a(self, q):\n    self.env.cr.execute(fixed(q))\n",
        "@http.route('/a')\ndef a(self, rid):\n"
        "    return getattr(request.env['x'].browse(int(rid)), 'action_view')()\n",
        "@http.route('/a')\ndef a(self, q):\n    return request.env['res.partner'].search([])\n",
    ],
)
def test_flow_taint_interprocedural_negative(body):
    got = _py(CTRL + body, "controllers/main.py")
    assert not [g for g in got if g[0].startswith("tainted")], got


@pytest.mark.parametrize(
    "el,code,line",
    [
        ("<script>\nvar a = <t t-out='user_value'/>;\n</script>", "qweb-script-injection", 4),
        ("<div style='background: url(https://x.example/a.png)'/>", "css-external-url", 3),
        ("<div t-attf-style='width: expression(alert(1))'/>", "css-expression", 3),
    ],
)
def test_xml_script_context_and_style(el, code, line):
    src = f"<odoo>\n<template id='a'>\n{el}\n</template>\n</odoo>\n"
    assert (code, line) in [(g[0], g[1]) for g in _xml(src)]


@pytest.mark.parametrize(
    "el",
    [
        "<script>\nvar a = <t t-out='json.dumps(v)'/>;\n</script>",
        "<div style='background: url(/web/static/a.png)'/>",
    ],
)
def test_xml_script_context_and_style_negative(el):
    src = f"<odoo>\n<template id='a'>\n{el}\n</template>\n</odoo>\n"
    bad = {"qweb-script-injection", "css-external-url", "css-expression"}
    assert not [g for g in _xml(src) if g[0] in bad]


def test_flow_tainted_model_severity():
    low = _py(
        CTRL + "@http.route('/a')\ndef a(self, m):\n    request.env[m].search([])\n",
        "controllers/main.py",
    )
    high = _py(
        CTRL + "@http.route('/a')\ndef a(self, m):\n    request.env[m].sudo().search([])\n",
        "controllers/main.py",
    )
    assert ("tainted-model", 6, "low") in low and ("tainted-model", 6, "high") in high
