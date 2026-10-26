"""BOT-OWNED-CODE-CHANGE acceptance tests (pure; no Odoo, no DB)."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import pytest

from app.bots import owned_change as oc
from app.bots import tiers
from app.bots.owned_change import ChangeError, ChangeRequest, Edit

MOD = "ing_demo"
OWNED = {MOD}
MANIFEST = (
    "{'name': 'Demo', 'version': '17.0.1.0.0', 'license': 'LGPL-3', 'depends': ['base'],"
    " 'data': ['security/ir.model.access.csv', 'views/views.xml']}\n"
)
MODELS = """from odoo import fields, models


class Demo(models.Model):
    _name = "ing.demo"
    _description = "Demo"

    name = fields.Char()
    code = fields.Char()

    def label(self):
        return self.name or ""
"""
ACCESS = (
    "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n"
    "access_demo,demo,model_ing_demo,base.group_user,1,0,0,0\n"
)
VIEWS = """<odoo>
  <record id="view_demo_form" model="ir.ui.view">
    <field name="name">demo.form</field>
    <field name="model">ing.demo</field>
    <field name="arch" type="xml"><form><field name="name"/></form></field>
  </record>
</odoo>"""
FILES = {
    "__init__.py": "from . import models\n",
    "__manifest__.py": MANIFEST,
    "models/__init__.py": "from . import demo\n",
    "models/demo.py": MODELS,
    "security/ir.model.access.csv": ACCESS,
    "views/views.xml": VIEWS,
}


def tree(tmp: Path, files: dict[str, str] = FILES, name: str = MOD) -> Path:
    root = tmp / name
    for p, b in files.items():
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_text(b)
    return root


def raw(files: dict[str, str] = FILES) -> dict[str, bytes]:
    return {p: b.encode() for p, b in files.items()}


NEW_LABEL = """    def label(self):
        return (self.name or "").upper()
"""


def build(tmp: Path, *edits: Edit, **kw):
    return oc.build_change_set(
        tree(tmp),
        ChangeRequest(MOD, tuple(edits), kw.get("reason", "")),
        version=17,
        owned_names=OWNED,
    )


def test_ac1_symbol_change_yields_diff_hashes_audits(tmp_path):
    cs = build(tmp_path, Edit("models/demo.py", "replace_symbol", NEW_LABEL, "Demo.label"))
    assert '+        return (self.name or "").upper()' in cs.diff
    assert cs.base["models/demo.py"] == oc.sha(MODELS.encode())
    assert cs.after["models/demo.py"] != cs.base["models/demo.py"]
    assert set(cs.pre_counts) == {"high", "medium", "low", "info"} and cs.new_findings == []
    assert len(cs.id) == 64 and cs.approval_plan()["tier"] == "L3"


def test_ac1_xmlid_replace_and_file_kinds(tmp_path):
    rec = (
        VIEWS.split("\n", 1)[1]
        .rsplit("\n", 1)[0]
        .replace('name="name"/>', 'name="name"/><field name="code"/>')
    )
    cs = build(
        tmp_path,
        Edit("views/views.xml", "replace_xmlid", rec, "view_demo_form"),
        Edit("README.md", "add_file", "# Demo\n"),
    )
    assert cs.base["README.md"] is None and '<field name="code"/>' in cs.diff
    out = oc.apply_change_set(raw(), cs)
    assert out["README.md"] == b"# Demo\n" and b'name="code"' in out["views/views.xml"]


def test_ac2_new_high_finding_fails_closed(tmp_path):
    bad = """    def label(self):
        self.env.cr.execute("select * from x where n = '%s'" % self.name)
        return ""
"""
    with pytest.raises(ChangeError) as e:
        build(tmp_path, Edit("models/demo.py", "replace_symbol", bad, "Demo.label"))
    assert e.value.code == "audit-regression"


def test_ac2_preexisting_findings_do_not_block(tmp_path):
    files = dict(
        FILES, **{"models/demo.py": MODELS + "\n\ndef x(env):\n    return env['ing.demo'].sudo()\n"}
    )
    cs = oc.build_change_set(
        tree(tmp_path, files),
        ChangeRequest(MOD, (Edit("models/demo.py", "replace_symbol", NEW_LABEL, "Demo.label"),)),
        version=17,
        owned_names=OWNED,
    )
    assert cs.post_counts == cs.pre_counts


def test_ac3_foreign_module_refused(tmp_path):
    with pytest.raises(ChangeError) as e:
        oc.build_change_set(
            tree(tmp_path),
            ChangeRequest(MOD, (Edit("README.md", "add_file", "x\n"),)),
            version=17,
            owned_names={"other"},
        )
    assert e.value.code == "foreign"
    with pytest.raises(ChangeError):
        oc.build_change_set(
            tree(tmp_path),
            ChangeRequest(MOD, (Edit("README.md", "add_file", "x\n"),)),
            version=17,
            owned_names="ing_demo",
        )


def test_ac3_tree_name_mismatch_and_nested_module(tmp_path):
    with pytest.raises(ChangeError) as e:
        oc.build_change_set(
            tree(tmp_path, name="other"),
            ChangeRequest(MOD, (Edit("README.md", "add_file", "x\n"),)),
            version=17,
            owned_names=OWNED,
        )
    assert e.value.code == "outside-module"
    files = dict(FILES, **{"vendor/__manifest__.py": "{'name': 'v'}\n", "vendor/a.py": "x = 1\n"})
    with pytest.raises(ChangeError) as e:
        oc.build_change_set(
            tree(tmp_path / "n", files),
            ChangeRequest(MOD, (Edit("vendor/a.py", "replace_file", "x = 2\n"),)),
            version=17,
            owned_names=OWNED,
        )
    assert e.value.code == "outside-module"


@pytest.mark.parametrize(
    "path",
    ["../x.py", "/etc/x.py", "a\\b.py", "models/../../x.py", ".git/config", "a/./b.py", "bin.so"],
)
def test_ac3_path_escape_refused(tmp_path, path):
    with pytest.raises(ChangeError) as e:
        build(tmp_path, Edit(path, "add_file", "x = 1\n"))
    assert e.value.code in {"path-escape", "path-invalid"}


def test_ac3_symlink_in_tree_refused(tmp_path):
    root = tree(tmp_path)
    os.symlink("/etc/passwd", root / "models" / "evil.py")
    with pytest.raises(ChangeError) as e:
        oc.build_change_set(
            root,
            ChangeRequest(MOD, (Edit("README.md", "add_file", "x\n"),)),
            version=17,
            owned_names=OWNED,
        )
    assert e.value.code == "source-unsafe"


def test_ac4_idempotent(tmp_path):
    cs = build(tmp_path, Edit("models/demo.py", "replace_symbol", NEW_LABEL, "Demo.label"))
    once = oc.apply_change_set(raw(), cs)
    assert oc.apply_change_set(once, cs) == once


def test_ac5_round_trip_byte_exact(tmp_path):
    files = dict(FILES, **{"views/views.xml": VIEWS.rstrip("\n")})  # no trailing newline
    rec = VIEWS.split("\n", 1)[1].rsplit("\n", 1)[0].replace("demo.form", "demo.form2")
    cs = oc.build_change_set(
        tree(tmp_path, files),
        ChangeRequest(
            MOD,
            (
                Edit("views/views.xml", "replace_xmlid", rec, "view_demo_form"),
                Edit("models/demo.py", "replace_symbol", NEW_LABEL, "Demo.label"),
                Edit("README.md", "add_file", "no newline"),
                Edit("models/__init__.py", "replace_file", "from . import demo\n# keep\n"),
            ),
        ),
        version=17,
        owned_names=OWNED,
    )
    base = raw(files)
    fwd = oc.apply_change_set(base, cs)
    assert oc.apply_change_set(fwd, cs, reverse=True) == base
    assert oc.apply_change_set(base, cs, reverse=True) == base  # reverse idempotent
    assert "\\ No newline at end of file" in cs.diff


def test_ac5_delete_round_trip(tmp_path):
    files = dict(FILES, **{"README.md": "x\n"})
    cs = oc.build_change_set(
        tree(tmp_path, files),
        ChangeRequest(MOD, (Edit("README.md", "delete_file"),)),
        version=17,
        owned_names=OWNED,
    )
    fwd = oc.apply_change_set(raw(files), cs)
    assert "README.md" not in fwd and oc.apply_change_set(fwd, cs, reverse=True) == raw(files)


def test_ac6_stale_base_refused(tmp_path):
    cs = build(tmp_path, Edit("models/demo.py", "replace_symbol", NEW_LABEL, "Demo.label"))
    drift = raw()
    drift["models/demo.py"] += b"# drift\n"
    with pytest.raises(ChangeError) as e:
        oc.apply_change_set(drift, cs)
    assert e.value.code == "stale-base"
    cs.patches["models/demo.py"] = cs.patches["models/demo.py"].replace("upper", "lower")
    with pytest.raises(ChangeError):
        oc.apply_change_set(raw(), cs)  # tampered patch cannot reach the pinned hash


def test_ac7_bounds(tmp_path):
    with pytest.raises(ChangeError) as e:
        build(tmp_path, Edit("big.txt", "add_file", "x" * (oc.MAX_CONTENT + 1)))
    assert e.value.code == "bounds"
    many = tuple(Edit(f"f{i}.txt", "add_file", "x") for i in range(oc.MAX_EDITS + 1))
    with pytest.raises(ChangeError):
        build(tmp_path, *many)
    with pytest.raises(ChangeError):
        oc.build_change_set(tree(tmp_path), ChangeRequest(MOD, ()), version=17, owned_names=OWNED)


def test_ac8_hostile_and_malformed(tmp_path):
    cases = [
        (Edit("models/demo.py", "replace_symbol", "def (:\n", "Demo.label"), "syntax-invalid"),
        (Edit("models/demo.py", "replace_symbol", NEW_LABEL, "Nope.label"), "target-missing"),
        (Edit("models/demo.py", "replace_symbol", NEW_LABEL, "x;import os"), "target-invalid"),
        (Edit("models/demo.py", "replace_symbol", NEW_LABEL, "Demo.label\n"), "target-invalid"),
        (
            Edit(
                "views/views.xml",
                "replace_xmlid",
                '<!DOCTYPE x [<!ENTITY a "b">]><record id="view_demo_form"/>',
                "view_demo_form",
            ),
            None,
        ),
        (
            Edit("views/views.xml", "replace_xmlid", '<record id="other"/>', "view_demo_form"),
            "target-invalid",
        ),
        (Edit("models/demo.py", "add_file", "x"), "exists"),
        (Edit("nope.py", "replace_file", "x = 1\n"), "missing"),
        (Edit("__manifest__.py", "delete_file"), "protected"),
        (Edit("models/demo.py", "chmod", ""), "kind-invalid"),
        (Edit("a.txt", "add_file", "a\x00b"), "content-invalid"),
        (Edit("models/demo.py", "replace_file", MODELS), "no-op"),
    ]
    for edit, code in cases:
        with pytest.raises((ChangeError, ValueError)) as e:
            build(tmp_path / str(id(edit)), edit)
        if code:
            assert e.value.code == code, (edit, e.value)


def test_ac8_hostile_zip_refused():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{MOD}/__manifest__.py", MANIFEST)
        z.writestr("../evil.py", "x")
    with pytest.raises(ChangeError) as e:
        oc.build_change_set(
            buf.getvalue(),
            ChangeRequest(MOD, (Edit("a.txt", "add_file", "x"),)),
            version=17,
            owned_names=OWNED,
        )
    assert e.value.code == "source-unsafe"


def test_ac9_request_text_never_interpolated(tmp_path):
    reason = "__import__('os').system('id'); ${x} {0} %s"
    cs = build(
        tmp_path, Edit("models/demo.py", "replace_symbol", NEW_LABEL, "Demo.label"), reason=reason
    )
    assert "__import__" not in cs.diff and "__import__" not in cs.inverse_diff
    out = oc.apply_change_set(raw(), cs)
    assert all(b"__import__" not in b for b in out.values())


def test_ac10_pure_read_only_and_t3_unchanged(tmp_path):
    root = tree(tmp_path)
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    build(tmp_path, Edit("models/demo.py", "replace_symbol", NEW_LABEL, "Demo.label"))
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert tiers.tier_ready(tiers.T3) is False
