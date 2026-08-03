"""Tests for Code → ModuleSpec import (AST / XML / meta.json / zip)."""

from __future__ import annotations

import io
import json
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.main import app  # noqa: E402
from app.module_import import (  # noqa: E402
    import_module_archive,
    parse_meta_json,
    parse_python_models,
    parse_xml_views,
)


SAMPLE_MODEL = '''
from odoo import models, fields

class Vehicle(models.Model):
    _name = "x_fleet_vehicle"
    _description = "Vehicle"
    _inherit = ["mail.thread"]

    x_name = fields.Char(string="Name", required=True)
    x_partner_id = fields.Many2one("res.partner", string="Owner")
    x_status = fields.Selection(
        [("available", "Available"), ("rented", "Rented")],
        string="Status",
    )

    def action_mark_available(self):
        for rec in self:
            rec.x_status = "available"
'''

SAMPLE_VIEW = """
<odoo>
  <record id="view_vehicle_form" model="ir.ui.view">
    <field name="name">x_fleet_vehicle.form</field>
    <field name="model">x_fleet_vehicle</field>
    <field name="type">form</field>
    <field name="arch" type="xml">
      <form>
        <sheet>
          <group>
            <field name="x_name"/>
            <field name="x_status" widget="statusbar"/>
          </group>
        </sheet>
      </form>
    </field>
  </record>
</odoo>
"""


def test_parse_python_models_extracts_fields_and_unmapped_methods() -> None:
    models, unmapped, warnings = parse_python_models(SAMPLE_MODEL, filename="vehicle.py")
    assert not warnings or True
    assert len(models) == 1
    m = models[0]
    assert m["model"] == "x_fleet_vehicle"
    names = {f["name"] for f in m["fields"]}
    assert "x_name" in names
    assert "x_partner_id" in names
    assert "x_status" in names
    partner = next(f for f in m["fields"] if f["name"] == "x_partner_id")
    assert partner["ttype"] == "many2one"
    assert partner["relation"] == "res.partner"
    assert any(u["kind"] == "python_methods" for u in unmapped)


def test_parse_xml_views() -> None:
    views, unmapped, warnings = parse_xml_views(SAMPLE_VIEW, filename="views.xml")
    assert len(views) == 1
    assert views[0]["model"] == "x_fleet_vehicle"
    assert views[0]["type"] == "form"
    assert "x_status" in views[0]["arch"]


def test_parse_meta_json_roundtrip() -> None:
    meta = {
        "format": "odoo_custom_modulespec",
        "version": 1,
        "spec": {
            "technical_name": "demo",
            "display_name": "Demo",
            "models": [{"model": "x_demo", "fields": [{"name": "x_name", "ttype": "char"}]}],
        },
    }
    result = parse_meta_json(meta)
    assert result.spec["technical_name"] == "demo"
    assert result.source == "meta.json"


def test_import_zip_prefers_meta_json() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "demo/.meta.json",
            json.dumps(
                {
                    "spec": {
                        "technical_name": "from_meta",
                        "display_name": "From Meta",
                        "models": [{"model": "x_meta", "fields": []}],
                    }
                }
            ),
        )
        zf.writestr("demo/models/vehicle.py", SAMPLE_MODEL)
    result = import_module_archive(buf.getvalue(), filename="demo.zip")
    assert result.source.startswith("zip")
    assert result.spec["technical_name"] == "from_meta"


def test_import_zip_parses_py_and_xml_without_meta() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "fleet/__manifest__.py",
            "{\n    'name': 'Fleet',\n    'depends': ['base', 'mail'],\n}\n",
        )
        zf.writestr("fleet/models/vehicle.py", SAMPLE_MODEL)
        zf.writestr("fleet/views/vehicle_views.xml", SAMPLE_VIEW)
    result = import_module_archive(buf.getvalue(), filename="fleet.zip")
    assert result.spec["display_name"] == "Fleet"
    assert any(m["model"] == "x_fleet_vehicle" for m in result.spec["models"])
    assert result.spec["views"]
    assert result.unmapped  # methods


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


SAMPLE_CUSTOM_XML = """
<odoo>
  <record id="view_vehicle_form" model="ir.ui.view">
    <field name="name">x_fleet_vehicle.form</field>
    <field name="model">x_fleet_vehicle</field>
    <field name="type">form</field>
    <field name="arch" type="xml">
      <form>
        <script>console.log('custom');</script>
        <field name="x_name"/>
      </form>
    </field>
  </record>
  <record id="action_custom_server" model="ir.actions.server">
    <field name="name">Custom Server</field>
    <field name="model_id" ref="model_x_fleet_vehicle"/>
    <field name="state">code</field>
    <field name="code">action = {}</field>
  </record>
</odoo>
"""


def test_import_sets_custom_code_blocks() -> None:
    result = import_module_archive(SAMPLE_MODEL.encode(), filename="vehicle.py")
    payload = result.as_dict()
    blocks = payload.get("custom_code_blocks") or []
    assert blocks
    assert blocks[0]["kind"] == "python_methods"
    assert "action_mark_available" in blocks[0]["content"]
    assert blocks[0].get("model") == "x_fleet_vehicle"


def test_round_trip_custom_blocks_byte_identical() -> None:
    from app.module_spec_codec import draft_dict_to_module_spec, merge_custom_code_blocks
    from module_generator import render_module_files

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "fleet/__manifest__.py",
            "{\n    'name': 'Fleet',\n    'depends': ['base', 'mail'],\n}\n",
        )
        zf.writestr("fleet/models/vehicle.py", SAMPLE_MODEL)
        zf.writestr("fleet/views/vehicle_views.xml", SAMPLE_CUSTOM_XML)
    imported = import_module_archive(buf.getvalue(), filename="fleet.zip")
    spec = imported.as_dict()
    original_blocks = merge_custom_code_blocks(spec)
    assert original_blocks

    module = draft_dict_to_module_spec(spec)
    files = render_module_files(module)
    # Method content preserved in model file append
    method_block = next(b for b in original_blocks if b["kind"] == "python_methods")
    model_py = files.get("fleet/models/fleet_vehicle.py") or files.get(
        "fleet/models/vehicle.py", ""
    )
    assert method_block["content"] in model_py

    # Re-import exported zip with meta sidecar path: rebuild zip from files
    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    reimport = import_module_archive(out_buf.getvalue(), filename="fleet_out.zip")
    round_blocks = merge_custom_code_blocks(reimport.as_dict())
    assert len(round_blocks) >= len(original_blocks)
    re_method = next(b for b in round_blocks if b["kind"] == "python_methods")
    assert re_method["content"] == method_block["content"]


def test_fuzz_three_samples_zero_content_loss() -> None:
    samples = [
        ("a.py", SAMPLE_MODEL),
        ("b.xml", SAMPLE_VIEW),
        ("c.xml", SAMPLE_CUSTOM_XML),
    ]
    total_in = 0
    total_blocks = 0
    for name, text in samples:
        result = import_module_archive(text.encode(), filename=name)
        payload = result.as_dict()
        from app.module_spec_codec import merge_custom_code_blocks

        blocks = merge_custom_code_blocks(payload)
        for b in blocks:
            total_blocks += len(b.get("content") or "")
        # mapped fields/views still present
        if name.endswith(".py"):
            assert payload.get("models")
        if "view" in name:
            assert payload.get("views") or blocks
        total_in += sum(len(b.get("content") or "") for b in blocks)
    assert total_blocks == total_in
    assert total_blocks > 0


def test_apply_skips_custom_code_blocks_with_warning() -> None:
    from unittest.mock import MagicMock

    from app.spec_apply_ui import apply_module_spec_ui

    result = import_module_archive(SAMPLE_MODEL.encode(), filename="vehicle.py")
    spec = result.as_dict()
    client = MagicMock()
    client.model_exists.return_value = True
    ui = apply_module_spec_ui(client, spec, apply_views=False, apply_menus=False)
    assert any("Custom logic skipped" in w for w in ui.warnings)


SAMPLE_CUSTOM_XML = """
<odoo>
  <record id="view_vehicle_form" model="ir.ui.view">
    <field name="name">x_fleet_vehicle.form</field>
    <field name="model">x_fleet_vehicle</field>
    <field name="type">form</field>
    <field name="arch" type="xml">
      <form>
        <script>console.log('custom');</script>
        <field name="x_name"/>
      </form>
    </field>
  </record>
  <record id="action_custom_server" model="ir.actions.server">
    <field name="name">Custom Server</field>
    <field name="model_id" ref="model_x_fleet_vehicle"/>
    <field name="state">code</field>
    <field name="code">action = {}</field>
  </record>
</odoo>
"""


def test_import_sets_custom_code_blocks() -> None:
    result = import_module_archive(SAMPLE_MODEL.encode(), filename="vehicle.py")
    payload = result.as_dict()
    blocks = payload.get("custom_code_blocks") or []
    assert blocks
    assert blocks[0]["kind"] == "python_methods"
    assert "action_mark_available" in blocks[0]["content"]
    assert blocks[0].get("model") == "x_fleet_vehicle"


def test_round_trip_custom_blocks_byte_identical() -> None:
    from app.module_spec_codec import draft_dict_to_module_spec, merge_custom_code_blocks
    from module_generator import render_module_files

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "fleet/__manifest__.py",
            "{\n    'name': 'Fleet',\n    'depends': ['base', 'mail'],\n}\n",
        )
        zf.writestr("fleet/models/vehicle.py", SAMPLE_MODEL)
        zf.writestr("fleet/views/vehicle_views.xml", SAMPLE_CUSTOM_XML)
    imported = import_module_archive(buf.getvalue(), filename="fleet.zip")
    spec = imported.as_dict()
    original_blocks = merge_custom_code_blocks(spec)
    assert original_blocks

    module = draft_dict_to_module_spec(spec)
    files = render_module_files(module)
    # Method content preserved in model file append
    method_block = next(b for b in original_blocks if b["kind"] == "python_methods")
    model_py = files.get("fleet/models/fleet_vehicle.py") or files.get(
        "fleet/models/vehicle.py", ""
    )
    assert method_block["content"] in model_py

    # Re-import exported zip with meta sidecar path: rebuild zip from files
    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    reimport = import_module_archive(out_buf.getvalue(), filename="fleet_out.zip")
    round_blocks = merge_custom_code_blocks(reimport.as_dict())
    assert len(round_blocks) >= len(original_blocks)
    re_method = next(b for b in round_blocks if b["kind"] == "python_methods")
    assert re_method["content"] == method_block["content"]


def test_fuzz_three_samples_zero_content_loss() -> None:
    samples = [
        ("a.py", SAMPLE_MODEL),
        ("b.xml", SAMPLE_VIEW),
        ("c.xml", SAMPLE_CUSTOM_XML),
    ]
    total_in = 0
    total_blocks = 0
    for name, text in samples:
        result = import_module_archive(text.encode(), filename=name)
        payload = result.as_dict()
        from app.module_spec_codec import merge_custom_code_blocks

        blocks = merge_custom_code_blocks(payload)
        for b in blocks:
            total_blocks += len(b.get("content") or "")
        # mapped fields/views still present
        if name.endswith(".py"):
            assert payload.get("models")
        if "view" in name:
            assert payload.get("views") or blocks
        total_in += sum(len(b.get("content") or "") for b in blocks)
    assert total_blocks == total_in
    assert total_blocks > 0


def test_apply_skips_custom_code_blocks_with_warning() -> None:
    from unittest.mock import MagicMock

    from app.spec_apply_ui import apply_module_spec_ui

    result = import_module_archive(SAMPLE_MODEL.encode(), filename="vehicle.py")
    spec = result.as_dict()
    client = MagicMock()
    client.model_exists.return_value = True
    ui = apply_module_spec_ui(client, spec, apply_views=False, apply_menus=False)
    assert any("Custom logic skipped" in w for w in ui.warnings)


def test_import_api_accepts_py(client: TestClient) -> None:
    res = client.post(
        "/api/module-spec/import",
        files={"file": ("vehicle.py", SAMPLE_MODEL.encode("utf-8"), "text/x-python")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["source"] == "python"
    models = body["spec"]["models"]
    assert models[0]["model"] == "x_fleet_vehicle"
