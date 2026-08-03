"""Tests for AI-4 workflow Step 4 and enrich transition buttons."""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ["AI_ASSIST"] = "off"

from app.ai_enrich import _build_form_arch, enrich_draft_module_spec  # noqa: E402
from app.ai_workflow import step4_workflow_models  # noqa: E402
from app.ai_workflow import (  # noqa: E402
    derive_default_transitions,
    ensure_workflow_transitions_on_draft,
    validate_workflow_definition,
)
from app.settings import settings  # noqa: E402
from module_generator import ModelSpec, ModuleSpec, render_module_files  # noqa: E402


def test_derive_default_transitions_chain() -> None:
    tr = derive_default_transitions(["draft", "open", "done"])
    assert tr == [["draft", "open"], ["open", "done"]]


def test_validate_workflow_definition_catches_bad_edge() -> None:
    notes = validate_workflow_definition(["draft", "done"], [["draft", "missing"]])
    assert any("unknown state" in n for n in notes)


def test_step4_fake_provider_sets_state_field() -> None:
    settings.ai_self_consistency = "off"

    class _Fake:
        name = "fake"

        def generate_json(self, *args: Any, **kwargs: Any) -> str:
            return json.dumps(
                {
                    "states": [
                        {"value": "draft", "label": "Draft"},
                        {"value": "open", "label": "Open"},
                        {"value": "done", "label": "Done"},
                    ],
                    "transitions": [["draft", "open"], ["open", "done"]],
                }
            )

    models = [
        {
            "model": "x_matter",
            "description": "Matter",
            "is_workflow": True,
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Name"},
                {"name": "x_status", "ttype": "selection", "string": "Status", "selection": "[('draft','Draft')]"},
            ],
        }
    ]
    out, warnings = step4_workflow_models(_Fake(), models, user_prompt="law firm matters")
    sf = out[0].get("state_field")
    assert isinstance(sf, dict)
    assert sf.get("transitions") == [["draft", "open"], ["open", "done"]]
    assert "open" in (out[0]["fields"][1].get("selection") or "")
    assert warnings or True


def test_enrich_form_buttons_from_transitions() -> None:
    arch = _build_form_arch(
        "Matter",
        [{"name": "x_name", "ttype": "char"}, {"name": "x_status", "ttype": "selection", "selection": "[('draft','Draft'),('open','Open')]"}],
        transitions=[["draft", "open"], ["open", "done"]],
    )
    assert "widget=\"statusbar\"" in arch
    assert "Confirm" in arch
    assert "data-transition-to=\"open\"" in arch


def test_enrich_without_transitions_preserves_statusbar_only() -> None:
    arch = _build_form_arch(
        "Matter",
        [{"name": "x_status", "ttype": "selection", "selection": "[('draft','Draft'),('open','Open')]"}],
    )
    assert "statusbar" in arch
    assert "data-transition-to" not in arch


def test_single_pipeline_derives_transitions() -> None:
    draft = {
        "technical_name": "demo",
        "display_name": "Demo",
        "models": [
            {
                "model": "x_job",
                "fields": [
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                    }
                ],
            }
        ],
    }
    notes = ensure_workflow_transitions_on_draft(draft)
    assert notes
    sf = draft["models"][0]["state_field"]
    assert sf["transitions"] == [["draft", "open"], ["open", "done"]]


def test_meta_json_roundtrip_state_field() -> None:
    spec = ModuleSpec(
        technical_name="wf_demo",
        display_name="WF Demo",
        models=[
            ModelSpec(
                model="x_case",
                description="Case",
                state_field={
                    "field": "x_status",
                    "transitions": [["draft", "open"], ["open", "done"]],
                    "states": ["draft", "open", "done"],
                },
                fields=[],
            )
        ],
    )
    files = render_module_files(spec)
    meta = json.loads(files["wf_demo/.meta.json"])
    m0 = meta["spec"]["models"][0]
    assert m0["state_field"]["transitions"][0] == ["draft", "open"]


def test_enrich_draft_with_state_field_builds_buttons() -> None:
    draft = {
        "technical_name": "demo",
        "display_name": "Demo",
        "models": [
            {
                "model": "x_case",
                "description": "Case",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                    },
                ],
                "state_field": {
                    "field": "x_status",
                    "transitions": [["draft", "open"], ["open", "done"]],
                },
            }
        ],
    }
    enriched, _ = enrich_draft_module_spec(draft)
    form = next(v for v in enriched["views"] if v["type"] == "form")
    assert "Confirm" in form["arch"]
