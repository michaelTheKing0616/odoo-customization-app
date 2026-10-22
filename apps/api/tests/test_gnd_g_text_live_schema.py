"""GND-G-TEXT: display text names only live structure (narratives, refine reply).

Fake LLM and fixture schema client only — no live Odoo, no live model, no app DB.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai_schema_client import FakeSchemaClient
from app.expert import narrative
from app.expert.draft_review import DraftReviewFinding
from app.expert.retrieval import RetrievedChunk
from app.live_schema_context import build_schema_packet, unknown_technical_names
from app.routers import ai_studio

pytestmark = pytest.mark.no_app_db


def _sale_packet():
    client = FakeSchemaClient(
        models={"sale.order"},
        fields={
            "sale.order": {
                "partner_id": {"type": "many2one", "ttype": "many2one", "relation": "res.partner"},
                "client_order_ref": {"type": "char", "ttype": "char"},
            }
        },
    )
    return build_schema_packet(
        SimpleNamespace(id="fixture", server_version="19.0", odoo_major=19),
        models=["sale.order"],
        schema_client=client,
    )


class _FakeLLM:
    def __init__(self, *, json_payload: dict[str, Any] | None = None, text: str = "") -> None:
        self.json_payload = json_payload or {}
        self.text = text
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, **_kwargs: Any) -> str:
        self.prompts.append(prompt)
        return json.dumps(self.json_payload)

    def generate_text(self, prompt: str, **_kwargs: Any) -> str:
        self.prompts.append(prompt)
        return self.text


# --- shared name check ---------------------------------------------------------------


def test_unknown_names_respect_packet_allowed_and_skip_abbreviations() -> None:
    packet = _sale_packet()
    text = "Set client_order_ref on sale.order, e.g. like x_po_ref on sale.order.extra."
    assert unknown_technical_names(text, packet) == ["x_po_ref", "sale.order.extra"]
    assert unknown_technical_names(text, packet, allowed=["x_po_ref", "sale.order.extra"]) == []
    assert unknown_technical_names("Plain words only.", None) == []
    assert unknown_technical_names("Uses partner_id.", None) == ["partner_id"]


# --- expert/narrative.generate_finding_narratives -------------------------------------


def _finding(priority: int) -> DraftReviewFinding:
    return DraftReviewFinding(
        priority=priority,
        element="x_rental",
        summary="Missing list view",
        detail="Model x_rental has no list view.",
        deterministic=True,
    )


def _wire_narrative(monkeypatch: pytest.MonkeyPatch, llm: _FakeLLM) -> None:
    chunk = RetrievedChunk(
        chunk_id="c1",
        source="odoo-docs",
        version="19.0",
        breadcrumb="Views",
        text="Every model needs a list view.",
        score=0.9,
        method="fixture",
    )
    monkeypatch.setattr(narrative, "expert_assist_enabled", lambda: True)
    monkeypatch.setattr(narrative, "retrieve_expert_chunks", lambda *_a, **_k: [chunk])
    monkeypatch.setattr(narrative, "get_llm_provider", lambda: llm)


def test_narrative_naming_a_field_outside_the_packet_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = _FakeLLM(
        json_payload={
            "narratives": [
                {
                    "priority": 1,
                    "paragraph": (
                        "Add x_rental to a list view showing x_po_ref from sale.order [1]."
                    ),
                    "citation_ids": [1],
                },
                {
                    "priority": 2,
                    "paragraph": "A list view on x_rental near partner_id helps operators [1].",
                    "citation_ids": [1],
                },
            ]
        }
    )
    _wire_narrative(monkeypatch, llm)

    out = narrative.generate_finding_narratives(
        object(), [_finding(1), _finding(2)], schema_packet=_sale_packet()
    )

    by_priority = {n.priority: n for n in out}
    assert "x_po_ref" not in by_priority[1].paragraph
    assert by_priority[1].paragraph == narrative._fallback_paragraph(_finding(1))
    assert "partner_id" in by_priority[2].paragraph
    assert by_priority[2].citations
    assert "LIVE SCHEMA PACKET" in llm.prompts[0]
    assert "field client_order_ref" in llm.prompts[0]


def test_narrative_without_a_packet_keeps_only_the_findings_own_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = _FakeLLM(
        json_payload={
            "narratives": [
                {
                    "priority": 1,
                    "paragraph": "Model x_rental should list partner_id [1].",
                    "citation_ids": [1],
                },
                {
                    "priority": 2,
                    "paragraph": "Model x_rental needs a list view [1].",
                    "citation_ids": [1],
                },
            ]
        }
    )
    _wire_narrative(monkeypatch, llm)

    out = narrative.generate_finding_narratives(object(), [_finding(1), _finding(2)])

    by_priority = {n.priority: n for n in out}
    assert by_priority[1].paragraph == narrative._fallback_paragraph(_finding(1))
    assert by_priority[2].paragraph.startswith("Model x_rental needs a list view")
    assert "server_version=" not in llm.prompts[0]


# --- routers/ai_studio.refine_session_route --------------------------------------------

_DRAFT = {
    "models": [
        {
            "model": "x_rental",
            "name": "Rental",
            "fields": [{"name": "x_deposit", "string": "Deposit", "type": "float"}],
        }
    ]
}
_RESULT = {
    "ok": True,
    "draft": _DRAFT,
    "patch_summary": "Made Deposit required.",
    "highlighted_field_ids": ["x_rental.x_deposit"],
}


def _wire_refine(monkeypatch: pytest.MonkeyPatch, llm: _FakeLLM, packet: Any) -> None:
    row = SimpleNamespace(
        id="s1",
        artifact_json=json.dumps(_DRAFT),
        connection_id=7,
        prompt_resolved="Car rental with deposit",
        prompt_original="Car rental with deposit",
    )
    monkeypatch.setattr(ai_studio, "get_session", lambda _db, _sid: row)
    monkeypatch.setattr(ai_studio, "log_session_metrics", lambda *_a, **_k: None)
    monkeypatch.setattr(ai_studio, "append_turn", lambda *_a, **_k: None)
    monkeypatch.setattr(ai_studio, "update_session", lambda *_a, **_k: None)
    monkeypatch.setattr(ai_studio, "session_to_dict", lambda _row: {"id": "s1"})
    monkeypatch.setattr(ai_studio, "get_llm_provider_for_tier", lambda _tier: llm)
    monkeypatch.setattr(ai_studio, "_studio_schema_packet", lambda *_a, **_k: packet)
    monkeypatch.setattr(ai_studio, "apply_refinement", lambda *_a, **_k: dict(_RESULT))
    import app.odoo_service as odoo_service

    monkeypatch.setattr(odoo_service, "get_connection_or_404", lambda _db, _cid: object())


def _refine() -> dict[str, Any]:
    return ai_studio.refine_session_route(
        "s1", ai_studio.RefineIn(instruction="make the deposit field required"), db=None
    )


def test_refine_reply_naming_a_field_outside_packet_and_patch_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = _FakeLLM(text="Done: x_deposit is required and x_po_ref was added on sale.order.")
    _wire_refine(monkeypatch, llm, _sale_packet())

    out = _refine()

    assert out["ok"] is True
    assert out["assistant_reply"] == "Made Deposit required."
    assert "LIVE SCHEMA PACKET" in llm.prompts[0]


def test_refine_reply_naming_only_patch_and_packet_names_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = "Done: x_deposit on x_rental is now required, like partner_id on sale.order."
    _wire_refine(monkeypatch, _FakeLLM(text=reply), _sale_packet())

    assert _refine()["assistant_reply"] == reply


def test_refine_reply_without_a_packet_may_only_repeat_the_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_refine(monkeypatch, _FakeLLM(text="Done: partner_id is now required."), None)

    assert _refine()["assistant_reply"] == "Made Deposit required."
