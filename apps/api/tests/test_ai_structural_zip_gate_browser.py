"""T4-BROWSER: Stage F browser agent catches a view-arch class Python-only checks miss."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.ai_structural_zip_gate import structural_zip_gate

_MODULE = "x_ticket_browser"
_DEFECT = "view_arch_unparseable"
_RATE_PATH = (
    Path(__file__).resolve().parents[2]
    / "web"
    / "src"
    / "testing"
    / "browserAgent"
    / "false_positive_rate.json"
)

_PY = (
    "from odoo import fields, models\n\n"
    "class Ticket(models.Model):\n"
    "    _name = 'x_ticket'\n"
    "    _description = 'Ticket'\n"
    "    name = fields.Char(required=True)\n"
)
_ACL = (
    "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n"
    "access_x_ticket,x_ticket,model_x_ticket,base.group_user,1,1,1,1\n"
)
_MANIFEST = "{'name': 'Tickets', 'version': '1.0'}\n"
_CLEAN_ARCH = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    "<odoo>\n"
    '  <record id="view_x_ticket_form" model="ir.ui.view">\n'
    '    <field name="name">x.ticket.form</field>\n'
    '    <field name="model">x_ticket</field>\n'
    '    <field name="arch" type="xml">\n'
    '      <form string="Ticket">\n'
    "        <sheet><group><field name=\"name\"/></group></sheet>\n"
    "      </form>\n"
    "    </field>\n"
    "  </record>\n"
    "</odoo>\n"
)
# Unclosed <field name="name"> — valid Python + ACL; regex field-name check still
# sees name= and does not report view_field_undefined.
_DIRTY_ARCH = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    "<odoo>\n"
    '  <record id="view_x_ticket_form" model="ir.ui.view">\n'
    '    <field name="name">x.ticket.form</field>\n'
    '    <field name="model">x_ticket</field>\n'
    '    <field name="arch" type="xml">\n'
    '      <form string="Ticket">\n'
    "        <sheet><group><field name=\"name\">\n"
    "      </form>\n"
    "    </field>\n"
    "  </record>\n"
    "</odoo>\n"
)


def _files(arch: str) -> dict[str, str]:
    return {
        f"{_MODULE}/__manifest__.py": _MANIFEST,
        f"{_MODULE}/models/ticket.py": _PY,
        f"{_MODULE}/security/ir.model.access.csv": _ACL,
        f"{_MODULE}/views/ticket_views.xml": arch,
    }


def test_browser_agent_runs_inside_stage_f() -> None:
    gate = structural_zip_gate(files=_files(_CLEAN_ARCH))
    assert "browser_agent" in gate
    assert gate["browser_agent"]["ran"] is True


def test_browser_agent_catches_unparseable_arch_python_checks_miss() -> None:
    gate = structural_zip_gate(files=_files(_DIRTY_ARCH))
    assert gate["ok"] is False
    assert not any("syntax" in f for f in gate["findings"])
    assert not any("ir.model.access" in f for f in gate["findings"])
    assert not any("view_field_undefined" in f for f in gate["findings"])
    assert any(_DEFECT in f for f in gate["findings"])
    caught = gate["browser_agent"]["caught"]
    assert caught, gate["browser_agent"]
    assert caught[0]["module"] == _MODULE
    assert caught[0]["defect"] == _DEFECT
    if shutil.which("node"):
        assert gate["browser_agent"]["invoked_web_agent"] is True
        web_caught = gate["browser_agent"].get("web_agent_caught") or []
        assert any(row.get("defect") == _DEFECT for row in web_caught), web_caught


def test_clean_fixture_is_not_reported_as_that_defect() -> None:
    gate = structural_zip_gate(files=_files(_CLEAN_ARCH))
    assert gate["ok"] is True, gate["findings"]
    report = gate["browser_agent"]
    assert report["views_checked"] >= 1
    assert report["caught"] == []
    assert not any(_DEFECT in f for f in gate["findings"])
    false_positives = len(report["findings"])
    rate = false_positives / report["views_checked"]
    assert rate == report["false_positive_rate"]
    assert rate == 0.0
    measured = {
        "fixture": "x_ticket_browser clean form",
        "module": report["module"],
        "views_checked": report["views_checked"],
        "false_positives": false_positives,
        "false_positive_rate": rate,
        "measured_from": "clean fixture via structural_zip_gate",
        "defect_class_not_raised": _DEFECT,
    }
    written = json.loads(_RATE_PATH.read_text(encoding="utf-8"))
    assert written == measured
