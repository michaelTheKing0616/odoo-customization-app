"""GND-AUTO: Autopilot, ingest, and workflow drop names outside the packet.

Fixture schema client only — no live Odoo and no live model.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai_schema_client import FakeSchemaClient
from app.ai_workflow import ensure_workflow_transitions_on_draft, step4_workflow_models
from app.ingest.classify import classify_structured, classify_upload
from app.job_autopilot.packet import CustomResidual
from app.job_autopilot.planner import (
    build_job_packet,
    build_job_packet_for_connection,
    filter_job_packet_to_schema,
)
from app.live_schema_context import build_schema_packet
from odoo_client.read_plane import ReadPlane
from odoo_client.schema_graph import SchemaGraph

pytestmark = pytest.mark.no_app_db

_FORM_ARCH = (
    "<form><sheet><group>"
    '<field name="partner_id"/>'
    '<field name="partner_invoice_id"/>'
    '<field name="date_order"/>'
    "</group></sheet></form>"
)
_LIST_ARCH = '<list><field name="name"/><field name="partner_id"/></list>'
_SEARCH_ARCH = '<search><field name="name"/><field name="partner_id"/></search>'


class _SaleViewTables:
    def __call__(self, model: str, method: str, args: list, kwargs: dict):
        if method != "get_view" or model != "sale.order":
            raise AssertionError((model, method))
        view_type = str(kwargs.get("view_type") or "form")
        arches = {"form": _FORM_ARCH, "list": _LIST_ARCH, "search": _SEARCH_ARCH}
        return {"arch": arches.get(view_type, "<form/>")}


def _sale_client() -> FakeSchemaClient:
    return FakeSchemaClient(
        models={"sale.order", "res.partner"},
        fields={
            "sale.order": {
                "partner_id": {
                    "type": "many2one",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "required": True,
                },
                "partner_invoice_id": {
                    "type": "many2one",
                    "ttype": "many2one",
                    "relation": "res.partner",
                },
                "date_order": {"type": "datetime", "ttype": "datetime"},
                "name": {"type": "char", "ttype": "char"},
            },
            "res.partner": {
                "name": {"type": "char", "ttype": "char"},
                "email": {"type": "char", "ttype": "char"},
            },
        },
        methods={"sale.order": {"action_confirm", "formatted_read_group"}},
    )


def _connection(*, major: int = 19) -> SimpleNamespace:
    return SimpleNamespace(
        id="fixture-sale",
        server_version=f"{major}.0",
        odoo_major=major,
        installed_modules=[{"name": "sale", "state": "installed"}],
    )


def _sale_packet(*, major: int = 19, models: list[str] | None = None):
    return build_schema_packet(
        _connection(major=major),
        models=models or ["sale.order"],
        schema_client=_sale_client(),
        schema_graph=SchemaGraph(ReadPlane(_SaleViewTables())),
    )


def _planner_derived_blob(job: Any) -> str:
    dumped = job.model_dump()
    dumped.pop("prompt", None)
    return json.dumps(dumped)


class _FakeWorkflowProvider:
    name = "fake"

    def generate_json(self, *args: Any, **kwargs: Any) -> str:
        return json.dumps(
            {
                "states": [
                    {"value": "draft", "label": "Draft"},
                    {"value": "done", "label": "Done"},
                ],
                "transitions": [["draft", "done"]],
                "methods": ["action_confirm", "formatted_read_group"],
            }
        )


def test_route_entry_drops_model_outside_packet_without_passing_schema_packet() -> None:
    """Production entry used by the autopilot route. No schema_packet= kwarg."""
    job = build_job_packet_for_connection(
        "Quotations and invoices for a trading company.",
        _connection(major=17),
        use_llm=False,
        planned_models=["sale.order", "project.task"],
        planned_methods=["action_confirm", "formatted_read_group"],
        schema_client=_sale_client(),
        schema_graph=SchemaGraph(ReadPlane(_SaleViewTables())),
    )
    assert job.operator_brief.get("schema_models") == ["sale.order"]
    assert "project.task" not in {r.model for r in job.custom_residuals}
    blob = _planner_derived_blob(job)
    assert "project.task" not in blob


def test_planner_drops_model_outside_packet_before_sandbox_apply() -> None:
    packet = _sale_packet(major=17)
    assert "project.task" not in packet.models
    job = build_job_packet(
        "Quotations and invoices for a trading company.",
        use_llm=False,
        schema_packet=packet,
        planned_models=["sale.order", "project.task"],
        planned_methods=["action_confirm", "formatted_read_group"],
    )
    assert job.operator_brief.get("schema_models") == ["sale.order"]
    assert "project.task" not in {r.model for r in job.custom_residuals}
    blob = _planner_derived_blob(job)
    assert "project.task" not in blob


def test_planner_version_mismatched_method_does_not_leave() -> None:
    packet = _sale_packet(major=17)
    assert "formatted_read_group" not in packet.models["sale.order"].methods
    assert "action_confirm" in packet.models["sale.order"].methods
    job = build_job_packet(
        "Use formatted_read_group on quotations.",
        use_llm=False,
        schema_packet=packet,
        planned_methods=["action_confirm", "formatted_read_group"],
    )
    assert job.operator_brief.get("schema_methods") == ["action_confirm"]
    blob = _planner_derived_blob(job)
    assert "formatted_read_group" not in blob
    assert "action_confirm" in (job.operator_brief.get("schema_methods") or [])


def test_planner_filters_injected_residual_before_apply() -> None:
    packet = _sale_packet(major=17)
    job = build_job_packet("Quotations and invoices.", use_llm=False)
    job.custom_residuals.append(
        CustomResidual(key="task", model="project.task", reason="invented host")
    )
    filtered = filter_job_packet_to_schema(
        job,
        packet,
        planned_models=["project.task"],
        planned_methods=["formatted_read_group"],
    )
    assert all(r.model != "project.task" for r in filtered.custom_residuals)
    assert "project.task" not in (filtered.operator_brief.get("schema_models") or [])
    assert "formatted_read_group" not in (filtered.operator_brief.get("schema_methods") or [])


def test_classify_drops_model_outside_packet() -> None:
    packet = _sale_packet(major=19)
    assert "hr.employee" not in packet.models
    result = classify_structured(
        filename="staff.csv",
        headers=["employee", "department", "manager", "hire", "role"],
        schema_packet=packet,
    )
    assert result.doc_type == "other"
    assert result.needs_user_confirm is True
    assert any("hr.employee" in row for row in result.signals)


def test_classify_keeps_model_in_packet() -> None:
    packet = _sale_packet(major=19, models=["sale.order", "res.partner"])
    result = classify_upload(
        filename="customers.csv",
        headers=["name", "email", "phone", "customer_id"],
        schema_packet=packet,
    )
    assert result.doc_type == "customer_list"
    assert result.needs_user_confirm is False


def test_workflow_drops_model_and_method_outside_packet() -> None:
    packet = _sale_packet(major=17)
    models = [
        {
            "model": "project.task",
            "description": "Task",
            "is_workflow": True,
            "methods": ["action_confirm", "formatted_read_group"],
            "fields": [
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "selection": "[('draft','Draft'),('done','Done')]",
                }
            ],
        },
        {
            "model": "sale.order",
            "methods": ["action_confirm", "formatted_read_group"],
            "fields": [{"name": "name", "ttype": "char"}],
        },
    ]
    out, warnings = step4_workflow_models(
        _FakeWorkflowProvider(),
        models,
        user_prompt="Tasks plus confirm",
        schema_packet=packet,
    )
    assert all(row.get("model") != "project.task" for row in out)
    assert any("project.task" in row for row in warnings)
    sale = next(row for row in out if row.get("model") == "sale.order")
    assert sale.get("methods") == ["action_confirm"]
    assert "formatted_read_group" not in json.dumps(out)


def test_workflow_draft_drops_stock_model_outside_packet() -> None:
    packet = _sale_packet(major=17)
    draft = {
        "technical_name": "demo",
        "display_name": "Demo",
        "models": [
            {
                "model": "project.task",
                "methods": ["formatted_read_group"],
                "fields": [
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                    }
                ],
            },
            {
                "model": "x_job",
                "fields": [
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                    }
                ],
            },
        ],
    }
    notes = ensure_workflow_transitions_on_draft(draft, schema_packet=packet)
    models = [row.get("model") for row in draft["models"]]
    assert "project.task" not in models
    assert "x_job" in models
    assert any("project.task" in row for row in notes)
    assert "formatted_read_group" not in json.dumps(draft["models"])
