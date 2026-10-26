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
    assert {"version-model", "version-field", "version-list", "version-attrs"} <= codes(rep)
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
    bomb = zbytes({"__manifest__.py": "{}", "big.txt": "0" * 3_000_000})
    assert (
        "too large" in ca.audit(bomb, version=17).error
        or "over-compressed" in ca.audit(bomb, version=17).error
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


def test_r2_b3_unresolvable_parent_downgraded():
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
    assert fu and all(f.severity == "low" for f in fu)


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
            "static/src/big.js": "x" * 3_000_000,
            "static/src/x.xml": "<t t-name='a'><div attrs=\"{'a': 1}\"/></t>",
            "i18n/fr.po": "y" * 3_000_000,
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
