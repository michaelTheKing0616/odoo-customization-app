"""Stable unit tests for RAG retrieval + self-critique (no live model required)."""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ["AI_ASSIST"] = "off"

from app import ai_critique, ai_domain_packs, ai_rag  # noqa: E402
from app.ai_critique import apply_critique_repairs, run_self_critique  # noqa: E402
from app.ai_domain_packs import car_rental_pack, retrieve_domain_pack  # noqa: E402
from app.ai_enrich import enrich_draft_module_spec  # noqa: E402
from app.settings import settings  # noqa: E402


def test_rag_status_never_raises() -> None:
    status = ai_rag.rag_status()
    assert "rag_enabled" in status
    assert "detail" in status


def test_retrieve_with_rag_falls_back_to_regex(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.ai_rag = "auto"
    monkeypatch.setattr(ai_rag, "score_packs_with_embeddings", lambda *a, **k: None)
    hit = retrieve_domain_pack("car rental fleet management")
    assert hit is not None
    assert hit[0] == "car_rental"
    assert hit[2] == 1.0


def test_retrieve_with_rag_uses_embeddings_when_scored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.ai_rag = "on"
    settings.ai_rag_min_score = 0.3

    def fake_scores(prompt, packs):
        return [("clinic", 0.91), ("car_rental", 0.2), ("field_service", 0.1)]

    monkeypatch.setattr(ai_rag, "score_packs_with_embeddings", fake_scores)
    # Avoid regex short-circuit by using a vague prompt that won't hit car regex
    # but would have low Jaccard — embeddings should pick clinic
    pack_id, pack, score, method = ai_rag.retrieve_with_rag(
        "healthcare visit scheduling for patients",
        pack_loader=lambda: [
            ("car_rental", car_rental_pack()),
            ("clinic", ai_domain_packs.clinic_pack()),
            ("field_service", ai_domain_packs.field_service_pack()),
        ],
        jaccard_retrieve=ai_domain_packs.retrieve_domain_pack_lexical,
    )
    assert method == "embedding"
    assert pack_id == "clinic"
    assert score >= 0.9
    assert pack.get("domain_pack") == "clinic"


def test_apply_critique_repairs_adds_field_and_model() -> None:
    draft = {
        "technical_name": "demo",
        "display_name": "Demo",
        "models": [
            {
                "model": "x_demo",
                "description": "Demo",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                ],
            }
        ],
    }
    critique = {
        "ready": False,
        "missing_fields": [
            {
                "model": "x_demo",
                "name": "x_notes",
                "ttype": "text",
                "string": "Notes",
            }
        ],
        "missing_models": [
            {
                "model": "x_demo_line",
                "description": "Line",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                ],
            }
        ],
        "missing_automations": [
            {
                "name": "Notify on create",
                "model": "x_demo",
                "trigger": "on_create",
                "safe_actions": [{"kind": "next_activity", "summary": "New record"}],
            }
        ],
        "notes": ["thin draft"],
    }
    out, notes = apply_critique_repairs(draft, critique)
    assert any("x_demo.x_notes" in n for n in notes)
    assert any("x_demo_line" in n for n in notes)
    names = {f["name"] for f in out["models"][0]["fields"]}
    assert "x_notes" in names
    assert any(m["model"] == "x_demo_line" for m in out["models"])
    assert out["automations"][0]["name"] == "Notify on create"
    assert out["_critique"]["repairs"]


def test_run_self_critique_deterministic_when_llm_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.ai_critique = "on"
    monkeypatch.setattr(ai_critique, "get_llm_provider", lambda: None)
    draft, _ = enrich_draft_module_spec(
        {
            "technical_name": "thin",
            "display_name": "Thin",
            "models": [
                {
                    "model": "x_thin",
                    "description": "Thin",
                    "fields": [
                        {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    ],
                }
            ],
        }
    )
    out, warnings = run_self_critique(draft, user_prompt="thin app", repair=True)
    assert out.get("_completeness")
    assert any("deterministic" in w.lower() or "gaps" in w.lower() for w in warnings)


def test_run_self_critique_llm_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.ai_critique = "on"

    class Fake:
        name = "fake"

        def reachable(self, *, timeout_s: float = 2.0):
            return True, "ok"

        def generate_json(self, prompt, *, system=None, timeout_s=90.0):
            return json.dumps(
                {
                    "ready": False,
                    "missing_fields": [
                        {
                            "model": "x_thin",
                            "name": "x_status",
                            "ttype": "selection",
                            "string": "Status",
                            "selection": "[('draft','Draft'),('done','Done')]",
                        }
                    ],
                    "missing_models": [],
                    "missing_automations": [],
                    "notes": ["add status"],
                }
            )

    monkeypatch.setattr(ai_critique, "get_llm_provider", lambda: Fake())
    draft = {
        "technical_name": "thin",
        "display_name": "Thin",
        "models": [
            {
                "model": "x_thin",
                "description": "Thin",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                ],
            }
        ],
    }
    out, warnings = run_self_critique(draft, user_prompt="need status", repair=True)
    names = {f["name"] for f in out["models"][0]["fields"]}
    assert "x_status" in names
    assert any("critique: added field" in w for w in warnings)


def test_critique_rejects_non_x_field_names() -> None:
    draft = {
        "technical_name": "demo",
        "display_name": "Demo",
        "models": [
            {
                "model": "x_demo",
                "fields": [{"name": "x_name", "ttype": "char", "string": "Name"}],
            }
        ],
    }
    out, notes = apply_critique_repairs(
        draft,
        {
            "missing_fields": [
                {"model": "x_demo", "name": "evil_field", "ttype": "char", "string": "X"}
            ]
        },
    )
    assert notes == []
    assert all(f["name"].startswith("x_") for f in out["models"][0]["fields"])
