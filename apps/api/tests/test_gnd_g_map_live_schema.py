"""GND-G-MAP: import column mapping keeps only fields in the live packet.

Fake LLM and fixture schema client only — no live Odoo and no live model.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai_schema_client import FakeSchemaClient
from app.ingest import map_columns
from app.ingest.map_columns import enhance_mapping_with_llm
from app.live_schema_context import build_schema_packet

pytestmark = pytest.mark.no_app_db

_HEADERS = ["Kunde Name", "Mail Adresse", "Telefon Nr"]
_ROWS = [{"Kunde Name": "Ada", "Mail Adresse": "ada@example.com", "Telefon Nr": "123"}]


class _FakeLLM:
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, **_kwargs: Any) -> str:
        self.prompts.append(prompt)
        return json.dumps({"mapping": self.mapping})


def _partner_packet():
    client = FakeSchemaClient(
        models={"res.partner"},
        fields={
            "res.partner": {
                "name": {"type": "char", "ttype": "char"},
                "email": {"type": "char", "ttype": "char"},
                "phone": {"type": "char", "ttype": "char"},
            }
        },
    )
    return build_schema_packet(
        SimpleNamespace(id="fixture", server_version="19.0", odoo_major=19),
        models=["res.partner"],
        schema_client=client,
    )


def _use_llm(monkeypatch: pytest.MonkeyPatch, llm: _FakeLLM | None) -> None:
    monkeypatch.setattr(map_columns, "get_llm_provider", lambda: llm)


def test_invented_field_is_dropped_and_column_left_unmapped_with_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = _FakeLLM(
        {"Kunde Name": "name", "Mail Adresse": "email", "Telefon Nr": "x_phone_invented"}
    )
    _use_llm(monkeypatch, llm)

    mapping, warnings = enhance_mapping_with_llm(
        None,
        model="res.partner",
        headers=_HEADERS,
        rows=_ROWS,
        mapping={},
        schema_packet=_partner_packet(),
    )

    assert mapping == {"Kunde Name": "name", "Mail Adresse": "email"}
    assert "Telefon Nr" not in mapping
    assert any(
        "Telefon Nr" in w and "x_phone_invented" in w and "left unmapped" in w for w in warnings
    )
    assert len(llm.prompts) == 1
    assert "LIVE SCHEMA PACKET" in llm.prompts[0]
    assert "field email type=char" in llm.prompts[0]


def test_existing_mapping_is_not_overwritten_by_an_invented_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_llm(monkeypatch, _FakeLLM({"Kunde Name": "partner_name_typo"}))

    mapping, warnings = enhance_mapping_with_llm(
        None,
        model="res.partner",
        headers=_HEADERS,
        rows=_ROWS,
        mapping={"Mail Adresse": "email"},
        schema_packet=_partner_packet(),
    )

    assert mapping == {"Mail Adresse": "email"}
    assert any("partner_name_typo" in w for w in warnings)
    assert "low alias coverage; LLM column map unavailable" in warnings


def test_no_client_does_not_call_the_llm_and_columns_stay_unmapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = _FakeLLM({"Kunde Name": "name"})
    _use_llm(monkeypatch, llm)

    mapping, warnings = enhance_mapping_with_llm(
        None, model="res.partner", headers=_HEADERS, rows=_ROWS, mapping={}
    )

    assert mapping == {}
    assert llm.prompts == []
    assert "low alias coverage; LLM column map unavailable" in warnings


def test_empty_live_field_list_does_not_call_the_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = _FakeLLM({"Kunde Name": "name"})
    _use_llm(monkeypatch, llm)
    client = SimpleNamespace(model_exists=lambda _m: True, list_fields=lambda _m: [])

    mapping, warnings = enhance_mapping_with_llm(
        client, model="res.partner", headers=_HEADERS, rows=_ROWS, mapping={}
    )

    assert mapping == {}
    assert llm.prompts == []
    assert "low alias coverage; LLM column map unavailable" in warnings


def test_model_missing_on_the_connection_does_not_call_the_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = _FakeLLM({"Kunde Name": "name"})
    _use_llm(monkeypatch, llm)
    client = SimpleNamespace(model_exists=lambda _m: False, list_fields=lambda _m: [])

    mapping, _warnings = enhance_mapping_with_llm(
        client, model="x_not_installed", headers=_HEADERS, rows=_ROWS, mapping={}
    )

    assert mapping == {}
    assert llm.prompts == []


def test_live_client_packet_feeds_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = _FakeLLM({"Mail Adresse": "email", "Kunde Name": "x_made_up"})
    _use_llm(monkeypatch, llm)
    rows = [SimpleNamespace(name="name", ttype="char"), SimpleNamespace(name="email", ttype="char")]
    client = SimpleNamespace(model_exists=lambda m: m == "res.partner", list_fields=lambda _m: rows)

    mapping, warnings = enhance_mapping_with_llm(
        client, model="res.partner", headers=_HEADERS, rows=_ROWS, mapping={}
    )

    assert mapping == {"Mail Adresse": "email"}
    assert any("x_made_up" in w for w in warnings)
    assert "MODEL res.partner" in llm.prompts[0]
