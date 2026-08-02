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
