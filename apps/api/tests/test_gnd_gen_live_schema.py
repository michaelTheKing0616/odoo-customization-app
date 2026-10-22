"""GND-GEN: Draft Studio sees the live schema packet before a reply is admitted.

Fake schema client only — no live Odoo and no live model.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.ai_conversation.intent_gate import IntentAssessment
from app.ai_conversation.intent_llm import maybe_llm_refine_assessment
from app.ai_conversation.understand import build_understanding
from app.ai_schema_client import FakeSchemaClient
from app.live_schema_context import build_schema_packet, prepend_schema_packet
from app.llm_provider import MockLLMProvider
from app.routers.ai_studio import ground_studio_generate
from app.settings import settings
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
            }
        },
    )


def _connection(*, major: int = 19) -> SimpleNamespace:
    return SimpleNamespace(
        id="fixture-sale",
        server_version=f"{major}.0",
        odoo_major=major,
        installed_modules=[{"name": "sale", "state": "installed"}],
    )


def _sale_packet():
    return build_schema_packet(
        _connection(),
        models=["sale.order"],
        schema_client=_sale_client(),
        schema_graph=SchemaGraph(ReadPlane(_SaleViewTables())),
    )


class _TrackingProvider(MockLLMProvider):
    def __init__(self, json_response: str) -> None:
        super().__init__(json_response=json_response)
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, **kwargs):  # type: ignore[no-untyped-def]
        self.prompts.append(prompt)
        return super().generate_json(prompt, **kwargs)


@pytest.fixture
def _intent_llm_on(monkeypatch: pytest.MonkeyPatch):
    settings.ai_intent_llm = "on"
    yield
    settings.ai_intent_llm = "auto"


def test_sale_order_packet_prompt_drops_x_po_ref(
    monkeypatch: pytest.MonkeyPatch, _intent_llm_on
) -> None:
    packet = _sale_packet()
    assert "x_po_ref" not in packet.models["sale.order"].fields
    invented = json.dumps(
        {
            "title": "PO ref on quotations",
            "summary": "Add x_po_ref on sale.order after partner_id",
            "host_model": "sale.order",
            "inherit_existing": True,
            "needs_module": False,
            "constraints": [
                "On Sales (sale.order)",
                "Add x_po_ref",
                "Place after the customer",
            ],
            "out_of_scope": ["new home-screen app"],
            "confidence": "high",
        }
    )
    provider = _TrackingProvider(invented)
    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": provider,
    )
    grounded = ground_studio_generate(
        "Add a field after the customer on quotations",
        schema_packet=packet,
    )
    prompt = grounded["user_message"]
    assert "LIVE SCHEMA PACKET" in prompt
    assert "sale.order" in prompt
    assert "partner_id" in prompt
    assert "x_po_ref" not in prompt
    blob = json.dumps(grounded)
    assert "x_po_ref" not in blob
    assert grounded["placement_anchor"] == "partner_id"


def test_after_the_customer_uses_packet_form_order() -> None:
    packet = _sale_packet()
    assert packet.models["sale.order"].views["form"][0] == "partner_id"
    u = build_understanding(
        "add a field after the customer on quotations",
        schema_packet=packet,
    )
    assert u.to_dict().get("placement_anchor") == "partner_id"
    assert any("partner_id" in row for row in u.constraints)


def test_intent_host_outside_packet_is_discarded_not_new_app(
    monkeypatch: pytest.MonkeyPatch, _intent_llm_on
) -> None:
    packet = _sale_packet()
    assert "project.task" not in packet.models
    provider = _TrackingProvider(
        json.dumps(
            {
                "clear": True,
                "confidence": "high",
                "host_model": "project.task",
                "inherit_existing": True,
                "needs_module": False,
                "residual": "Tasks app",
                "rationale": "Invent a Tasks host that the packet does not have.",
            }
        )
    )
    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": provider,
    )
    assessment = IntentAssessment(
        clear=False,
        triggers=["low_ir_confidence"],
        ir_confidence="low",
        capability_path="residual_app",
    )
    refined = maybe_llm_refine_assessment(
        "Add a field after the customer on quotations",
        assessment,
        ranked=[],
        schema_packet=packet,
    )
    assert provider.prompts
    assert "LIVE SCHEMA PACKET" in provider.prompts[0]
    assert refined.llm_resolved is None or "host_model" not in (refined.llm_resolved or {})
    assert refined.capability_path != "residual_app" or refined.clear is False
    assert refined.clear is False
    assert any("not repaired into a new app" in note for note in refined.notes)
    assert any("project.task" in note for note in refined.notes)


def test_prepend_schema_packet_is_prefix() -> None:
    packet = _sale_packet()
    text = prepend_schema_packet("Operator brief:\nhello", packet)
    assert text.startswith("LIVE SCHEMA PACKET")
    assert text.index("LIVE SCHEMA PACKET") < text.index("Operator brief")
    assert "form order: partner_id, partner_invoice_id, date_order" in text
