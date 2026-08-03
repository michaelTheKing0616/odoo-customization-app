"""CMP-1 manifest data-file ordering contract."""

from __future__ import annotations

import re

from module_generator import (
    FieldSpec,
    ModelSpec,
    ModuleSpec,
    PythonAutomationSpec,
    RecordRuleSpec,
    ReportSpec,
    ViewSpec,
    order_manifest_data_files,
    render_module_files,
)


def _manifest_data_paths(spec: ModuleSpec) -> list[str]:
    manifest = render_module_files(spec)[f"{spec.technical_name}/__manifest__.py"]
    match = re.search(r'"data":\s*\[(.*?)\]', manifest, re.S)
    assert match, "manifest data list not found"
    return re.findall(r'"([^"]+)"', match.group(1))


def test_order_manifest_data_files_python_mode_contract() -> None:
    paths = order_manifest_data_files(
        [
            "report/reports.xml",
            "views/menus.xml",
            "data/sequences.xml",
            "views/views.xml",
            "security/record_rules.xml",
            "data/automations.xml",
            "security/ir.model.access.csv",
        ],
        install_mode="python",
    )
    assert paths == [
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "data/sequences.xml",
        "data/automations.xml",
        "views/views.xml",
        "views/menus.xml",
        "report/reports.xml",
    ]


def test_order_manifest_data_files_data_mode_models_before_security() -> None:
    paths = order_manifest_data_files(
        [
            "views/views.xml",
            "security/ir.model.access.csv",
            "data/models.xml",
            "data/sequences.xml",
        ],
        install_mode="data",
    )
    assert paths[0] == "data/models.xml"
    assert paths[1] == "security/ir.model.access.csv"
    assert paths[2] == "data/sequences.xml"


def test_generated_manifest_includes_all_types_in_contract_order() -> None:
    spec = ModuleSpec(
        technical_name="cmp1_full",
        display_name="CMP1 Full",
        models=[
            ModelSpec(
                model="x_ticket",
                description="Ticket",
                is_workflow=True,
                state_field={"field": "x_status", "transitions": [["draft", "open"]]},
                fields=[
                    FieldSpec(name="x_name", ttype="char", string="Name", required=True),
                    FieldSpec(
                        name="x_status",
                        ttype="selection",
                        string="Status",
                        selection="[('draft','Draft'),('open','Open')]",
                    ),
                ],
            )
        ],
        views=[
            ViewSpec(
                name="x_ticket.form",
                model="x_ticket",
                type="form",
                arch='<form><sheet><group><field name="x_name"/></group></sheet></form>',
            )
        ],
        python_automations=[
            PythonAutomationSpec(
                name="On create",
                model="x_ticket",
                trigger="on_create",
                code="True",
            )
        ],
        record_rules=[
            RecordRuleSpec(
                name="Own",
                model_xml_id="model_x_ticket",
                domain_force="[('create_uid', '=', user.id)]",
            )
        ],
        reports=[
            ReportSpec(
                name="Ticket PDF",
                model="x_ticket",
                report_name="cmp1_full.report_ticket",
                template_xml_id="report_ticket_doc",
                body_html="<div><t t-esc='o.x_name'/></div>",
            )
        ],
    )
    spec.ensure_default_menus()
    paths = _manifest_data_paths(spec)
    assert paths[0].startswith("security/")
    seq_idx = paths.index("data/sequences.xml")
    views_idx = paths.index("views/views.xml")
    menus_idx = paths.index("views/menus.xml")
    reports_idx = paths.index("report/reports.xml")
    assert seq_idx < views_idx < menus_idx < reports_idx
    assert "data/automations.xml" in paths
    assert paths.index("data/automations.xml") < views_idx

    manifest = render_module_files(spec)["cmp1_full/__manifest__.py"]
    assert re.search(r'"security/ir\.model\.access\.csv"', manifest)
