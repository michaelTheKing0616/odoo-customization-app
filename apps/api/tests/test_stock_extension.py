"""Stock-model extension from Overview: scaffold, zip layout, gates, access on built-in models."""

from __future__ import annotations

import base64
import io
import zipfile

import pytest
from fastapi import HTTPException

from app.code_studio_service import export_option_a_zip, stock_extension_scaffold
from app.spec_apply_ui import UiApplyResult, _apply_access_rules
from test_odoo20_access_write_path import RecordingClient

pytestmark = pytest.mark.no_app_db


def _zip(result: dict) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(base64.b64decode(result["content_base64"])))


def test_selection_options_extend_without_redefining_the_field() -> None:
    code = stock_extension_scaffold(model="res.partner", kind="selection_options", field_name="type",
                                    options=[{"value": "branch", "label": "Branch"}])
    compile(code, "ext", "exec")
    assert "_inherit = 'res.partner'" in code
    assert "selection_add=[('branch', 'Branch')]" in code and "ondelete={'branch': 'set null'}" in code
    assert "selection=[" not in code


@pytest.mark.parametrize("kind", ["computed_field", "behaviour"])
def test_other_scaffolds_compile_and_inherit(kind: str) -> None:
    code = stock_extension_scaffold(model="sale.order", kind=kind, field_name="score")
    compile(code, "ext", "exec")
    assert "_inherit = 'sale.order'" in code
    if kind == "computed_field":
        assert "x_score = fields.Char" in code


@pytest.mark.parametrize("bad", [
    {"model": "res.partner", "kind": "selection_options", "field_name": "type", "options": [{"value": "Bad Value"}]},
    {"model": "res.partner", "kind": "unknown"},
    {"model": "", "kind": "behaviour"},
])
def test_scaffold_refuses_incomplete_input_in_plain_words(bad: dict) -> None:
    with pytest.raises(ValueError):
        stock_extension_scaffold(**bad)


def test_extension_zip_imports_the_inherit_file_and_depends_on_the_owner() -> None:
    code = stock_extension_scaffold(model="res.partner", kind="behaviour")
    out = export_option_a_zip(name="Contacts extension", model="res.partner", code=code,
                              technical_name="res_partner_extension", depends=["base", "contacts", "Bad-Dep"],
                              as_extension=True)
    z = _zip(out)
    root = "res_partner_extension"
    assert z.read(f"{root}/__init__.py").decode().strip().endswith("from . import models")
    assert "from . import res_partner_extension" in z.read(f"{root}/models/__init__.py").decode()
    assert "_inherit = 'res.partner'" in z.read(f"{root}/models/res_partner_extension.py").decode()
    manifest = z.read(f"{root}/__manifest__.py").decode()
    assert "'contacts'" in manifest or '"contacts"' in manifest
    assert "Bad-Dep" not in manifest
    assert out["installed"] is False and out["promoted"] is False


def test_plain_option_a_zip_is_unchanged() -> None:
    out = export_option_a_zip(name="Snippet", model="res.partner", code="x = 1\n")
    assert any(n.endswith("code_studio_snippet.py") for n in _zip(out).namelist())


def test_scaffold_route_refuses_custom_models_and_reads_owner_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routers import code_studio as cs

    class Fake:
        def execute_kw(self, model, method, args, kwargs=None):
            assert (model, method) == ("ir.model", "search_read")
            return [{"modules": "base, contacts"}]

    monkeypatch.setattr(cs, "assert_developer_role", lambda auth: None)
    monkeypatch.setattr(cs, "assert_code_studio_entitlement", lambda db, auth: None)
    monkeypatch.setattr(cs, "_connection", lambda db, cid: object())
    monkeypatch.setattr(cs, "_client_or_502", lambda row: Fake())
    out = cs.code_studio_extension_scaffold(
        "c1", cs.ExtensionScaffoldBody(model="res.partner", kind="behaviour"), db=None, auth=None)
    assert out.depends == ["base", "contacts"] and out.technical_name == "res_partner_extension"
    with pytest.raises(HTTPException) as exc:
        cs.code_studio_extension_scaffold(
            "c1", cs.ExtensionScaffoldBody(model="x_job", kind="behaviour"), db=None, auth=None)
    assert exc.value.status_code == 400


def test_view_extension_gate_is_reported_to_overview() -> None:
    from app.routers.connections import _CHANGE_KEYS

    assert "xpath_inherit" in _CHANGE_KEYS


def test_built_in_field_edit_refusal_is_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from app.routers import builder

    class Fake:
        def get_field(self, fid):
            return SimpleNamespace(name="email", state="base")

    monkeypatch.setattr(builder, "_client", lambda cid, db: Fake())
    with pytest.raises(HTTPException) as exc:
        builder.update_field("c1", 5, builder.UpdateFieldBody(field_description="E-mail"), db=None)
    assert exc.value.status_code == 403
    assert "can't be changed in place" in exc.value.detail


@pytest.mark.parametrize("major", [19, 20])
def test_access_rule_on_a_built_in_model_applies(major: int) -> None:
    class Client(RecordingClient):
        def model_exists(self, model):
            return True

        def resolve_xml_id(self, ref):
            return 3

    client = Client(major)
    result = UiApplyResult()
    _apply_access_rules(client, {"models": [], "access_rules": [
        {"name": "partner_own", "model": "res.partner", "group": "base.group_user",
         "domain": "[('user_id','=',user.id)]", "perm_unlink": False}]}, result)
    assert not [w for w in result.warnings if "skipped" in w.lower() or "failed" in w.lower()], result.warnings
    assert result.access_rights_created + result.record_rules_created >= 1


def test_overlay_apply_twice_keeps_one_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.snapshots as snapshots
    from types import SimpleNamespace

    from app.routers import views

    frag = views._build_overlay_fragment(views.OverlayApplyBody(
        model="res.partner", view_type="form", operation="add_field",
        expr="(//field[@name='email'])[1]", add_field_name="x_tier", add_position="after"))
    primary = SimpleNamespace(id=1, arch="<form><field name='email'/><field name='email'/></form>")
    existing = SimpleNamespace(id=9, arch=frag.replace("\n", "\n  "))
    writes: list = []

    class Fake:
        def find_view(self, model, vt, primary_only=False):
            return primary

        def _find_view_by_exact_name(self, name):
            return existing

        def update_view_arch(self, vid, arch):
            writes.append(arch)
            return SimpleNamespace(id=vid)

    monkeypatch.setattr(views, "_client", lambda cid, db: Fake())
    monkeypatch.setattr(snapshots, "snapshot_view", lambda *a, **k: SimpleNamespace(id="s"))
    out = views.overlay_apply("c1", views.OverlayApplyBody(
        model="res.partner", view_type="form", operation="add_field",
        expr="(//field[@name='email'])[1]", add_field_name="x_tier", add_position="after"), db=None)
    assert out.view_id == 9 and writes == []


@pytest.mark.parametrize("major", [17, 18])
def test_extension_manifest_matches_the_target_odoo(major: int) -> None:
    out = export_option_a_zip(name="Ext", model="res.partner", code="x = 1\n", technical_name="ext_m",
                              as_extension=True, odoo_major=major)
    manifest = _zip(out).read("ext_m/__manifest__.py").decode()
    assert f"{major}.0.1.0.0" in manifest
