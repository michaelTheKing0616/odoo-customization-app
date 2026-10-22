"""GND-EXPERT: Expert cites the live schema packet when a connection exists."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai_schema_client import FakeSchemaClient
from app.expert.ask import ask_expert
from app.expert.live_schema_ask import resolve_expert_schema_packet
from app.live_schema_context import build_schema_packet
from app.llm_provider import LLMProvider
from odoo_client.read_plane import ReadPlane
from odoo_client.schema_graph import SchemaGraph

pytestmark = pytest.mark.no_app_db

_FORM_ARCH = (
    "<form><sheet><group>"
    '<field name="partner_id"/>'
    '<field name="date_order"/>'
    "</group></sheet></form>"
)


class _SaleViewTables:
    def __call__(self, model: str, method: str, args: list, kwargs: dict):
        if method != "get_view" or model != "sale.order":
            raise AssertionError((model, method))
        view_type = str(kwargs.get("view_type") or "form")
        if view_type == "form":
            return {"arch": _FORM_ARCH}
        return {"arch": f"<{view_type}/>"}


def _sale_client(*, extra_fields: dict[str, dict] | None = None) -> FakeSchemaClient:
    fields = {
        "partner_id": {
            "type": "many2one",
            "ttype": "many2one",
            "relation": "res.partner",
            "required": True,
        },
        "date_order": {"type": "datetime", "ttype": "datetime"},
        "name": {"type": "char", "ttype": "char"},
    }
    if extra_fields:
        fields.update(extra_fields)
    return FakeSchemaClient(
        models={"sale.order", "res.partner"},
        fields={"sale.order": fields, "res.partner": {"name": {"type": "char", "ttype": "char"}}},
    )


def _connection(*, major: int = 19) -> SimpleNamespace:
    return SimpleNamespace(
        id="fixture-sale",
        server_version=f"{major}.0",
        odoo_major=major,
        odoo_version=f"{major}.0",
        installed_modules=[{"name": "sale", "state": "installed"}],
    )


def _graph() -> SchemaGraph:
    return SchemaGraph(ReadPlane(_SaleViewTables()))


class _FakeDb:
    pass


class _FakeLLM(LLMProvider):
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.prompts: list[str] = []

    @property
    def name(self) -> str:
        return "fake-llm"

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        return True, "ok"

    def generate_json(self, prompt: str, **kwargs: Any) -> str:
        self.prompts.append(prompt)
        return json.dumps(self._payload)


def test_field_answer_cites_live_schema_packet(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _sale_client()
    conn = _connection()
    state = resolve_expert_schema_packet(
        conn,
        question="What type is partner_id on sale.order on this instance?",
        schema_client=client,
        schema_graph=_graph(),
    )
    assert state is not None
    assert "partner_id" in state.packet.models["sale.order"].fields

    monkeypatch.setattr(
        "app.odoo_service.get_connection_or_404",
        lambda _db, _cid: conn,
    )
    monkeypatch.setattr(
        "app.expert.ask.manifest_for_connection",
        lambda _row: {"version": "19.0"},
    )
    monkeypatch.setattr(
        "app.expert.ask.assemble_context",
        lambda *a, **k: __import__(
            "app.expert.grounding", fromlist=["GroundingBundle"]
        ).GroundingBundle(retrieval_version="19.0"),
    )

    result = ask_expert(
        _FakeDb(),
        question="What type is partner_id on sale.order on this instance?",
        connection_id="fixture-sale",
        schema_client=client,
        schema_graph=_graph(),
        provider=_FakeLLM({}),
    )
    assert result.grounded is True
    assert result.declined is False
    assert "partner_id" in result.answer_markdown
    assert "LIVE SCHEMA PACKET" in result.answer_markdown
    assert any(c.breadcrumb == "LIVE SCHEMA PACKET" for c in result.citations)


def test_second_read_before_field_absent_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _sale_client()
    conn = _connection()
    build_calls: list[list[str]] = []
    real_build = build_schema_packet

    def _track_build(connection, *, models, **kwargs):
        build_calls.append(list(models))
        return real_build(connection, models=models, **kwargs)

    monkeypatch.setattr("app.expert.live_schema_ask.build_schema_packet", _track_build)

    state = resolve_expert_schema_packet(
        conn,
        question="Does sale.order have x_po_ref on this connection?",
        schema_client=client,
        schema_graph=_graph(),
    )
    assert state is not None
    assert state.read_passes == 2
    assert len(build_calls) >= 2
    assert "x_po_ref" not in state.packet.models.get("sale.order", {}).fields

    monkeypatch.setattr("app.odoo_service.get_connection_or_404", lambda _db, _cid: conn)
    monkeypatch.setattr("app.expert.ask.manifest_for_connection", lambda _row: {"version": "19.0"})
    monkeypatch.setattr(
        "app.expert.ask.assemble_context",
        lambda *a, **k: __import__(
            "app.expert.grounding", fromlist=["GroundingBundle"]
        ).GroundingBundle(retrieval_version="19.0"),
    )

    result = ask_expert(
        _FakeDb(),
        question="Does sale.order have x_po_ref on this connection?",
        connection_id="fixture-sale",
        schema_client=client,
        schema_graph=_graph(),
        provider=_FakeLLM({}),
    )
    assert "schema_packet_reads:2" in result.caution_flags
    assert "LIVE SCHEMA PACKET" in result.answer_markdown
    assert result.declined is False
    assert "x_po_ref" in result.answer_markdown


def test_declines_when_no_field_and_no_host_model(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeSchemaClient(
        models={"sale.order"},
        fields={"sale.order": {"name": {"type": "char", "ttype": "char"}}},
    )
    conn = _connection()
    state = resolve_expert_schema_packet(
        conn,
        question="What type is x_po_ref on project.task on this database?",
        schema_client=client,
    )
    assert state is not None
    assert state.read_passes == 2

    monkeypatch.setattr("app.odoo_service.get_connection_or_404", lambda _db, _cid: conn)
    monkeypatch.setattr("app.expert.ask.manifest_for_connection", lambda _row: {"version": "19.0"})
    monkeypatch.setattr(
        "app.expert.ask.assemble_context",
        lambda *a, **k: __import__(
            "app.expert.grounding", fromlist=["GroundingBundle"]
        ).GroundingBundle(retrieval_version="19.0"),
    )

    result = ask_expert(
        _FakeDb(),
        question="What type is x_po_ref on project.task on this database?",
        connection_id="fixture-sale",
        schema_client=client,
        provider=_FakeLLM({}),
    )
    assert result.declined is True
    assert "LIVE SCHEMA PACKET" in result.answer_markdown
    assert "schema_packet_reads:2" in result.caution_flags


def test_retrieval_cannot_introduce_field_not_in_packet(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.expert.grounding import GroundingBundle
    from app.expert.retrieval import RetrievedChunk

    client = _sale_client()
    conn = _connection()
    chunk = RetrievedChunk(
        chunk_id="bad-chunk",
        source="odoo_docs",
        version="19.0",
        breadcrumb="Docs",
        text="You can set x_from_docs on sale.order for PO tracking.",
        score=0.9,
        method="test",
    )

    monkeypatch.setattr("app.odoo_service.get_connection_or_404", lambda _db, _cid: conn)
    monkeypatch.setattr("app.expert.ask.manifest_for_connection", lambda _row: {"version": "19.0"})
    monkeypatch.setattr("app.expert.ask.retrieve_expert_chunks", lambda *a, **k: [chunk])
    monkeypatch.setattr("app.expert.ask.passes_generation_threshold", lambda *a, **k: True)
    monkeypatch.setattr(
        "app.expert.ask.assemble_context",
        lambda *a, **k: GroundingBundle(retrieval_version="19.0"),
    )
    monkeypatch.setattr("app.expert.ask.classify_expert_intent", lambda *a, **k: False)
    monkeypatch.setattr("app.expert.ask.answer_matches_question", lambda *a, **k: True)

    llm = _FakeLLM(
        {
            "answer_markdown": (
                "Add x_from_docs on sale.order next to partner_id [1]."
            ),
            "citation_ids": [1],
        }
    )

    result = ask_expert(
        _FakeDb(),
        question="How do I track PO numbers on quotations?",
        connection_id="fixture-sale",
        schema_client=client,
        schema_graph=_graph(),
        provider=llm,
    )
    assert "x_from_docs" not in result.answer_markdown
    assert llm.prompts
    assert "LIVE SCHEMA PACKET" in llm.prompts[0]
