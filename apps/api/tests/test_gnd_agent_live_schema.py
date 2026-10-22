"""GND-AGENT: bot inspection tools read the same packet / SchemaGraph.

FakeSchemaClient + fixture graph only — no live Odoo and no live model.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.agent_runtime.runtime import AgentRuntime
from app.ai_schema_client import FakeSchemaClient
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
    """In-memory get_view slice. Not a live database."""

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
                    "readonly": False,
                    "store": True,
                    "groups": "",
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
            },
        },
        methods={"sale.order": {"action_confirm"}},
    )


def _connection(*, major: int = 19) -> SimpleNamespace:
    return SimpleNamespace(
        id="fixture-sale",
        server_version=f"{major}.0",
        odoo_major=major,
        installed_modules=[{"name": "sale", "state": "installed"}],
    )


def _graph() -> SchemaGraph:
    return SchemaGraph(ReadPlane(_SaleViewTables()))


def _packet_and_graph(*, major: int = 19):
    graph = _graph()
    packet = build_schema_packet(
        _connection(major=major),
        models=["sale.order"],
        schema_client=_sale_client(),
        schema_graph=graph,
    )
    return packet, graph


def _unwrap(result: dict) -> dict:
    assert result["instruction"] is None
    return json.loads(result["untrusted_data"])


def _discover_runtime(*, packet=None, schema_graph=None) -> tuple[AgentRuntime, object]:
    runtime = AgentRuntime(schema_packet=packet, schema_graph=schema_graph)
    state = runtime.start()
    runtime.complete_phase(state, "DISCOVER")
    return runtime, state


def test_describe_model_fields_are_subset_of_packet() -> None:
    packet, graph = _packet_and_graph()
    runtime, state = _discover_runtime(packet=packet, schema_graph=graph)
    body = _unwrap(runtime.call_tool(state, "describe_model", {"model": "sale.order"}))
    assert body["found"] is True
    assert body["model"] == "sale.order"
    packet_fields = packet.models["sale.order"].fields
    assert {row["name"] for row in body["fields"]} <= set(packet_fields)
    for row in body["fields"]:
        expected = packet_fields[row["name"]]
        assert row["type"] == expected.type
        assert row["relation"] == expected.relation
        assert row["required"] == expected.required
        assert row["readonly"] == expected.readonly
        assert row["store"] == expected.store
        assert row["groups"] == expected.groups


def test_describe_model_never_invents_field_absent_from_packet() -> None:
    packet, graph = _packet_and_graph()
    assert "x_not_on_sale" not in packet.models["sale.order"].fields
    runtime, state = _discover_runtime(packet=packet, schema_graph=graph)
    body = _unwrap(runtime.call_tool(state, "describe_model", {"model": "sale.order"}))
    names = {row["name"] for row in body["fields"]}
    assert "x_not_on_sale" not in names
    miss = _unwrap(runtime.call_tool(state, "describe_model", {"model": "project.task"}))
    assert miss["found"] is False
    assert miss["fields"] == []


def test_describe_model_without_packet_is_honest_empty() -> None:
    runtime, state = _discover_runtime()
    body = _unwrap(runtime.call_tool(state, "describe_model", {"model": "sale.order"}))
    assert body["fields"] == []
    assert body["found"] is False


def test_describe_field_is_packet_subset() -> None:
    packet, graph = _packet_and_graph()
    runtime, state = _discover_runtime(packet=packet, schema_graph=graph)
    hit = _unwrap(
        runtime.call_tool(state, "describe_field", {"model": "sale.order", "field": "partner_id"})
    )
    assert hit["found"] is True
    assert hit["meta"]["name"] == "partner_id"
    assert hit["meta"]["type"] == packet.models["sale.order"].fields["partner_id"].type
    miss = _unwrap(
        runtime.call_tool(state, "describe_field", {"model": "sale.order", "field": "x_missing"})
    )
    assert miss["found"] is False
    assert miss["meta"] is None


def test_view_test_xpath_uses_combined_arch_from_same_graph() -> None:
    packet, graph = _packet_and_graph()
    arch = graph.combined_arch("sale.order", "form")
    assert 'name="partner_id"' in arch
    assert arch == _FORM_ARCH
    runtime, state = _discover_runtime(packet=packet, schema_graph=graph)
    hit = _unwrap(
        runtime.call_tool(
            state,
            "view_test_xpath",
            {
                "model": "sale.order",
                "view_type": "form",
                "xpath": "field[@name='partner_id']",
            },
        )
    )
    assert hit["arch_source"] == "combined_arch"
    assert hit["matched"] is True
    assert hit["count"] == 1
    miss = _unwrap(
        runtime.call_tool(
            state,
            "view_test_xpath",
            {
                "model": "sale.order",
                "view_type": "form",
                "xpath": "field[@name='x_not_in_arch']",
            },
        )
    )
    assert miss["arch_source"] == "combined_arch"
    assert miss["matched"] is False
    assert miss["count"] == 0


def test_view_test_xpath_does_not_invent_for_model_outside_packet() -> None:
    packet, graph = _packet_and_graph()
    assert "project.task" not in packet.models
    runtime, state = _discover_runtime(packet=packet, schema_graph=graph)
    body = _unwrap(
        runtime.call_tool(
            state,
            "view_test_xpath",
            {
                "model": "project.task",
                "xpath": "field[@name='name']",
            },
        )
    )
    assert body["matched"] is False
    assert body["count"] == 0


def test_view_get_arch_matches_graph_combined_arch() -> None:
    packet, graph = _packet_and_graph()
    runtime, state = _discover_runtime(packet=packet, schema_graph=graph)
    body = _unwrap(
        runtime.call_tool(state, "view_get", {"model": "sale.order", "view_type": "form"})
    )
    assert body["found"] is True
    assert body["arch_source"] == "combined_arch"
    assert body["arch"] == graph.combined_arch("sale.order", "form")
    assert body["field_order"] == list(packet.models["sale.order"].views["form"])


def test_results_stay_wrapped_as_untrusted_data() -> None:
    packet, graph = _packet_and_graph()
    runtime, state = _discover_runtime(packet=packet, schema_graph=graph)
    for name, args in (
        ("describe_model", {"model": "sale.order"}),
        ("describe_field", {"model": "sale.order", "field": "name"}),
        ("view_get", {"model": "sale.order", "view_type": "form"}),
        ("view_test_xpath", {"model": "sale.order", "xpath": "field[@name='name']"}),
    ):
        result = runtime.call_tool(state, name, args)
        assert set(result) == {
            "name",
            "evidence_id",
            "tainted",
            "untrusted_data",
            "instruction",
        }
        assert result["instruction"] is None
        assert result["name"] == name
