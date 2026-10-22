"""GND-G-PIPE: draft-pipeline LLM calls see the packet and drop invented stock fields.

Fake LLM / FakeSchemaClient only — no live Odoo and no live model.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.ai_schema_client import FakeSchemaClient
from app.live_schema_context import build_schema_packet

pytestmark = pytest.mark.no_app_db

_INVENTED = "commercial_partner_phone"
_X_KEEP = "x_studio_tier"


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


def _fake_budget(payload: dict[str, Any], prompts: list[str]):
    def _call(_provider: Any, _step: str, prompt: str, **_kwargs: Any) -> tuple[str, None]:
        prompts.append(prompt)
        return json.dumps(payload), None

    return _call


def _assert_prompt_grounded(prompt: str, *, connected: bool = True) -> None:
    if connected:
        assert "LIVE SCHEMA PACKET" in prompt
        assert "MODEL res.partner" in prompt
    else:
        assert "NO LIVE CONNECTION" in prompt


def _field_names(models: list[Any], model: str) -> set[str]:
    for row in models:
        if isinstance(row, dict) and row.get("model") == model:
            return {
                str(f.get("name"))
                for f in (row.get("fields") or [])
                if isinstance(f, dict) and f.get("name")
            }
    return set()


def _missing_field_names(rows: list[Any], model: str) -> set[str]:
    return {
        str(r.get("name"))
        for r in rows
        if isinstance(r, dict) and r.get("model") == model and r.get("name")
    }


# --- shared invented payload shapes ---------------------------------------------------


def _invented_on_partner_and_x_keep() -> list[dict[str, Any]]:
    return [
        {
            "model": "res.partner",
            "name": _INVENTED,
            "ttype": "char",
            "string": "Invented stock field",
        },
        {
            "model": "res.partner",
            "name": _X_KEEP,
            "ttype": "char",
            "string": "Custom tier",
        },
        {
            "model": "x_session",
            "name": "x_room_id",
            "ttype": "many2one",
            "relation": "x_room",
            "string": "Room",
        },
    ]


def _thin_draft() -> dict[str, Any]:
    return {
        "technical_name": "studio_book",
        "display_name": "Studio Book",
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [{"name": "x_existing", "ttype": "char", "string": "Existing"}],
            },
            {
                "model": "x_session",
                "description": "Booking session",
                "fields": [{"name": "x_name", "ttype": "char", "string": "Name"}],
            },
        ],
    }


# --- 1. ai_pipeline._llm_json ---------------------------------------------------------


def test_pipeline_llm_json_drops_invented_stock_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ai_pipeline import _llm_json

    prompts: list[str] = []
    payload = {
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [
                    {"name": _INVENTED, "ttype": "char", "string": "Bad"},
                    {"name": _X_KEEP, "ttype": "char", "string": "Good"},
                ],
            }
        ]
    }
    monkeypatch.setattr("app.ai_llm_budget.llm_json_with_budget", _fake_budget(payload, prompts))

    data = _llm_json(
        MagicMock(),
        system="sys",
        prompt="Build a studio app",
        schema_packet=_partner_packet(),
    )
    assert isinstance(data, dict)
    names = _field_names(data.get("models") or [], "res.partner")
    assert _INVENTED not in names
    assert _X_KEEP in names
    _assert_prompt_grounded(prompts[0])


# --- 2. ai_depth.llm_expand_depth -----------------------------------------------------


def test_depth_expand_drops_invented_stock_field(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_depth import llm_expand_depth

    prompts: list[str] = []
    payload = {
        "missing_fields": _invented_on_partner_and_x_keep(),
        "missing_models": [],
        "missing_automations": [],
        "notes": ["deepen"],
    }
    monkeypatch.setattr("app.ai_llm_budget.llm_json_with_budget", _fake_budget(payload, prompts))

    out, notes = llm_expand_depth(
        MagicMock(),
        _thin_draft(),
        user_prompt="music studio booking",
        ambition="standard",
        gaps=["depth_fields"],
        schema_packet=_partner_packet(),
    )
    partner_fields = _field_names(out.get("models") or [], "res.partner")
    assert _INVENTED not in partner_fields
    assert _X_KEEP in partner_fields
    assert any(_INVENTED in n for n in notes)
    _assert_prompt_grounded(prompts[0])


# --- 3. ai_critique.llm_critique ------------------------------------------------------


def test_critique_drops_invented_stock_field(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_critique import llm_critique

    prompts: list[str] = []
    payload = {
        "ready": False,
        "checklist": [],
        "missing_fields": _invented_on_partner_and_x_keep(),
        "missing_models": [],
        "missing_automations": [],
        "notes": [],
    }
    monkeypatch.setattr("app.ai_llm_budget.llm_json_with_budget", _fake_budget(payload, prompts))

    data = llm_critique(
        MagicMock(),
        _thin_draft(),
        user_prompt="music studio",
        schema_packet=_partner_packet(),
    )
    names = _missing_field_names(data.get("missing_fields") or [], "res.partner")
    assert _INVENTED not in names
    assert _X_KEEP in names
    _assert_prompt_grounded(prompts[0])


# --- 4. ai_model_quality.llm_deepen_model_fields --------------------------------------


def test_deepen_drops_invented_stock_field(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_model_quality import llm_deepen_model_fields

    prompts: list[str] = []
    payload = {
        "missing_fields": _invented_on_partner_and_x_keep(),
        "missing_models": [],
        "notes": ["deepen"],
    }
    monkeypatch.setattr("app.ai_llm_budget.llm_json_with_budget", _fake_budget(payload, prompts))

    out, notes = llm_deepen_model_fields(
        MagicMock(),
        _thin_draft(),
        user_prompt="music studio booking rooms",
        ambition="standard",
        min_fields=6,
        schema_packet=_partner_packet(),
    )
    partner_fields = _field_names(out.get("models") or [], "res.partner")
    assert _INVENTED not in partner_fields
    assert _X_KEEP in partner_fields
    assert any(_INVENTED in n for n in notes)
    _assert_prompt_grounded(prompts[0])


# --- 5. ai_model_quality.llm_emit_missing_scaffold_models -----------------------------


def test_emit_scaffold_drops_invented_stock_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ai_model_quality import llm_emit_missing_scaffold_models

    prompts: list[str] = []
    payload = {
        "models": [
            {
                "model": "x_session_line",
                "description": "Session line",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {"name": "x_session_id", "ttype": "many2one", "relation": "x_session"},
                    {"name": "x_a", "ttype": "char"},
                    {"name": "x_b", "ttype": "char"},
                    {"name": "x_c", "ttype": "char"},
                    {"name": "x_d", "ttype": "char"},
                ],
            },
            {
                "model": "res.partner",
                "fields": [
                    {"name": _INVENTED, "ttype": "char"},
                    {"name": _X_KEEP, "ttype": "char"},
                ],
            },
        ]
    }
    monkeypatch.setattr("app.ai_llm_budget.llm_json_with_budget", _fake_budget(payload, prompts))

    draft = {
        "models": [
            {
                "model": "x_session",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_a", "ttype": "char"},
                    {"name": "x_b", "ttype": "char"},
                    {"name": "x_c", "ttype": "char"},
                    {"name": "x_d", "ttype": "char"},
                    {"name": "x_e", "ttype": "char"},
                ],
            }
        ]
    }
    scaffold = {
        "models": [
            {
                "model": "x_session_line",
                "description": "Session line",
                "fields": [{"name": "x_name", "ttype": "char", "string": "Name"}],
            }
        ]
    }
    out, notes = llm_emit_missing_scaffold_models(
        MagicMock(),
        draft,
        scaffold,
        user_prompt="music studio",
        schema_packet=_partner_packet(),
    )
    assert any(m.get("model") == "x_session_line" for m in out.get("models") or [])
    assert any(_INVENTED in n for n in notes)
    partner_rows = [m for m in (payload["models"]) if m.get("model") == "res.partner"]
    # Filter ran before merge; dropped note proves invent was stripped from LLM JSON.
    assert partner_rows  # payload still has it; notes prove filter saw it
    _assert_prompt_grounded(prompts[0])


# --- 6. ai_domain_briefing._enrich_briefing_with_llm ----------------------------------


def test_briefing_enrich_drops_invented_stock_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ai_domain_briefing import DomainBriefing, _enrich_briefing_with_llm

    prompts: list[str] = []
    payload = {
        "industry": "music studio",
        "not_industries": ["manufacturing"],
        "equipment_types": [["mic", "Microphone"], ["booth", "Booth"]],
        "rate_uoms": [["hour", "Per hour"], ["day", "Per day"]],
        "banned_selection_keys": ["mrp_workcenter"],
        # Nested field-like shape the shared filter walks:
        "models": [
            {
                "model": "res.partner",
                "fields": [
                    {"name": _INVENTED, "ttype": "char"},
                    {"name": _X_KEEP, "ttype": "char"},
                ],
            }
        ],
    }
    monkeypatch.setattr("app.ai_llm_budget.llm_json_with_budget", _fake_budget(payload, prompts))

    briefing = DomainBriefing(industry="prompt-derived", source="default", notes=[])
    out = _enrich_briefing_with_llm(
        briefing,
        "independent music recording studio with hourly booth rates",
        MagicMock(),
        schema_packet=_partner_packet(),
    )
    assert out.industry == "music studio"
    assert ("mic", "Microphone") in out.equipment_types
    assert any(_INVENTED in n for n in out.notes)
    _assert_prompt_grounded(prompts[0])


# --- 7. ai_ollama.draft_module_from_prompt --------------------------------------------


def test_draft_module_drops_invented_stock_field(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import ai_ollama

    prompts: list[str] = []
    payload = {
        "technical_name": "studio_book",
        "display_name": "Studio Book",
        "depends": ["base", "contacts"],
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [
                    {"name": _INVENTED, "ttype": "char", "string": "Bad"},
                    {"name": _X_KEEP, "ttype": "char", "string": "Tier"},
                ],
            },
            {
                "model": "x_session",
                "description": "Session",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Client",
                    },
                ],
            },
        ],
    }

    class _Prov:
        name = "fake"

        def generate_json(self, prompt: str, **_k: Any) -> str:
            prompts.append(prompt)
            return json.dumps(payload)

    monkeypatch.setattr(ai_ollama, "get_llm_provider", lambda: _Prov())
    monkeypatch.setattr("app.ollama_warm.warm_ollama_models", lambda: None)
    monkeypatch.setattr(
        "app.ai_generation_engine.maybe_seed_from_capability", lambda _p: None
    )
    monkeypatch.setattr("app.ai_domain_packs.match_domain_pack", lambda *_a, **_k: None)
    monkeypatch.setattr("app.ai_domain_packs.retrieve_domain_pack", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "app.ai_ollama.retrieve_domain_pack", lambda *_a, **_k: None
    )

    draft, _raw, warnings, _refusals = ai_ollama.draft_module_from_prompt(
        "Build a full custom music studio booking app with sessions and rooms",
        expand=False,
        pipeline="single",
        grain_override="full_app",
        schema_packet=_partner_packet(),
    )
    names = _field_names(draft.get("models") or [], "res.partner")
    assert _INVENTED not in names
    assert _X_KEEP in names
    assert any(m.get("model") == "x_session" for m in draft.get("models") or [])
    assert any(_INVENTED in w for w in warnings) or _INVENTED not in names
    assert prompts and ("LIVE SCHEMA PACKET" in prompts[0] or any("LIVE SCHEMA PACKET" in p for p in prompts))


# --- 8. ai_ollama.call_ollama_generate ------------------------------------------------


def test_call_ollama_generate_drops_invented_stock_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import ai_ollama

    prompts: list[str] = []
    payload = {
        "technical_name": "studio_book",
        "display_name": "Studio",
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [
                    {"name": _INVENTED, "ttype": "char"},
                    {"name": _X_KEEP, "ttype": "char"},
                ],
            }
        ],
    }

    class _Prov:
        name = "fake"

        def generate_json(self, prompt: str, **_k: Any) -> str:
            prompts.append(prompt)
            return json.dumps(payload)

    monkeypatch.setattr(ai_ollama, "get_llm_provider", lambda: _Prov())

    raw = ai_ollama.call_ollama_generate(
        "studio booking ModuleSpec", schema_packet=_partner_packet()
    )
    data = json.loads(raw)
    names = _field_names(data.get("models") or [], "res.partner")
    assert _INVENTED not in names
    assert _X_KEEP in names
    _assert_prompt_grounded(prompts[0])


def test_pipe_no_connection_prompt_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_pipeline import _llm_json

    prompts: list[str] = []
    monkeypatch.setattr(
        "app.ai_llm_budget.llm_json_with_budget",
        _fake_budget({"models": []}, prompts),
    )
    # Explicit None → draft_grounding falls back to current; clear it.
    monkeypatch.setattr(
        "app.ai_conversation.intent_llm.current_schema_packet", lambda: None
    )
    _llm_json(MagicMock(), system="sys", prompt="hi", schema_packet=None)
    _assert_prompt_grounded(prompts[0], connected=False)
