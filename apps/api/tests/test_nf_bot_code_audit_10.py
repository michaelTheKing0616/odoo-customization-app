"""CODE-AUDIT-10: no *-unaudited on stock. Each root cause gets the stock probe, variants,
and hostile input that must still fail closed."""
import pytest

from tests.test_nf_bot_code_audit_5 import MAN, codes

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
MANX = MAN.replace("'data':[", "'data':['data/d.xml',")


def _rec(field, ref):
    return ("<odoo><record id='e' model='res.partner'><field name='name'>e</field>"
            f"<field name='{field}' type='base64' file='{ref}'/></record></odoo>")


def _unaud(files):
    return {s for c, s in codes(files, MANX) if c == "data-file-unaudited"}


# ---------------------------------------------------------------- (A) file= images skipped from the inventory
@pytest.mark.parametrize("files", [
    {"data/d.xml": _rec("image_1920", "x/static/img/a.jpg"), "static/img/a.jpg": JPG},  # stock hr probe
    {"data/d.xml": _rec("image_1920", "x/static/src/img/bot.png"), "static/src/img/bot.png": PNG},  # stock mail
    {"data/d.xml": _rec("step_image", "x/static/img/p.png"), "static/img/p.png": PNG},
])
def test_own_inert_image_audited(files):
    assert not _unaud(files)


@pytest.mark.parametrize("files", [
    {"data/d.xml": _rec("image_1920", "x/static/img/a.png"), "static/img/a.png": b"<script>alert(1)</script>"},  # not a PNG
    {"data/d.xml": _rec("image_1920", "x/static/img/missing.png")},
    {"data/d.xml": _rec("image_1920", "other/static/img/a.png")},  # foreign addon not available (zip upload)
])
def test_unprovable_file_ref_fails_closed(files):
    assert "medium" in _unaud(files)


def test_sibling_addon_image_resolved(tmp_path):
    from app.bots import code_audit as ca
    root = tmp_path / "src"
    (root / "odoo" / "addons" / "base" / "static" / "img").mkdir(parents=True)
    (root / "odoo" / "addons" / "base" / "__manifest__.py").write_text("{'name': 'base'}")
    (root / "odoo" / "addons" / "base" / "static" / "img" / "p.png").write_bytes(PNG)
    (root / "odoo" / "addons" / "base" / "static" / "img" / "bad.png").write_bytes(b"<html>")
    m = root / "addons" / "x"
    (m / "data").mkdir(parents=True)
    (m / "__manifest__.py").write_text("{'name':'x','version':'17.0.1.0.0','depends':['base'],'license':'LGPL-3','data':['data/d.xml','data/e.xml']}")
    (m / "__init__.py").write_text("")
    (m / "data" / "d.xml").write_text(_rec("step_image", "base/static/img/p.png"))  # stock account probe
    (m / "data" / "e.xml").write_text(_rec("step_image", "base/static/img/bad.png").replace("id='e'", "id='f'"))
    r = ca.audit(m, version=17)
    got = {(f.file, f.code) for f in r.findings if f.code == "data-file-unaudited"}
    assert got == {("data/e.xml", "data-file-unaudited")}


def test_svg_file_ref_is_audited_as_active_content():
    files = {"data/d.xml": _rec("image_1920", "x/static/img/a.svg"), "static/img/a.svg": b"<svg onload='x()'/>"}
    assert any(s in ("high", "medium") for c, s in codes(files, MANX) if c != "data-file-unaudited")


# ---------------------------------------------------------------- (B) JSON script types parsed as JSON
def _html(typ, body):
    return {"static/t/index.html": f'<html><head><script type="{typ}">{body}</script></head><body></body></html>'}


def _sev(files, code):
    return {s for c, s in codes(files) if c == code}


@pytest.mark.parametrize("typ,body", [
    ("importmap", '{"imports": {"@odoo/hoot": "/web/static/lib/hoot/hoot.js",\n "@odoo/owl": "../owl.js"}}'),  # stock hoot
    ("application/json", '{"a": [1, "https://x.example/"]}'),  # inert data block
    ("application/ld+json", '{"@context": "https://schema.org"}'),
])
def test_json_script_audited(typ, body):
    f = _html(typ, body)
    assert not _sev(f, "web-unaudited") and not _sev(f, "markup-external-resource")


@pytest.mark.parametrize("typ,body", [
    ("importmap", '{"imports": {"@odoo/owl": "https://evil.example/owl.js"}}'),
    ("importmap", '{"scopes": {"/": {"a": "//evil.example/a.js"}}}'),
    ("importmap", '{"imports": {"a": "data:text/javascript,alert(1)"}}'),
])
def test_remote_importmap_high(typ, body):
    assert "high" in _sev(_html(typ, body), "markup-external-resource")


@pytest.mark.parametrize("typ", ["importmap", "application/json", "speculationrules"])
def test_invalid_json_script_fails_closed(typ):
    assert "high" in _sev(_html(typ, "{imports: alert(1)}"), "web-unaudited")


def test_qweb_importmap_graded():
    f = {"views/v.xml": '<odoo><template id="t"><script type="importmap">{"imports":{"a":"//e.example/a.js"}}</script></template></odoo>'}
    assert "high" in _sev(f, "markup-external-resource")


# ---------------------------------------------------------------- (C) OWL template expressions
def _owl(src):
    return {"static/src/a.js": "import { Component, xml } from '@odoo/owl';\n" + src + "\n"}


@pytest.mark.parametrize("tpl", [
    '<div t-attf-class="o-${X.name} {{ state.on and \'on\' }}"/>',  # stock hoot_side_bar: outer ${} in xml``
    '<button t-on-click="delete"/>',  # stock website edit_menu
    '<button t-on-click="default"/><i t-att-class="new"/>',
])
def test_owl_expr_audited(tpl):
    assert not _sev(_owl("const X = {name: 'a'};\nclass A extends Component { static template = xml`" + tpl + "`; }"), "owl-expr-unaudited")


@pytest.mark.parametrize("tpl", ['<b t-on-click="a ) ) +"/>', '<b t-att-x="delete delete"/>'])
def test_unparsable_owl_expr_fails_closed(tpl):
    assert _sev(_owl("class A extends Component { static template = xml`" + tpl + "`; }"), "owl-expr-unaudited")
