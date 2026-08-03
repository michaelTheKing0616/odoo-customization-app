"""REM-1 — staged pipeline executes all LLM steps without NameError."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.ai_pipeline import run_staged_pipeline
from app.llm_provider import LLMProvider
from app.protected_modules import build_manifest, guardrail_prompt


class _RecordingProvider(LLMProvider):
    """Fake provider that returns valid JSON per step and records every call."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._n = 0

    @property
    def name(self) -> str:
        return "recording"

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        return True, "fake"

    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
        reasoning: bool = False,
        temperature: float | None = None,
        format_schema: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> str:
        sys_text = system or ""
        self.calls.append(
            {
                "system": sys_text,
                "prompt": prompt,
                "reasoning": reasoning,
                "temperature": temperature,
                "format_schema": format_schema,
            }
        )
        self._n += 1
        if "SUBSTANTIVE entities" in sys_text:
            return json.dumps(
                [
                    {
                        "name": "support_ticket",
                        "purpose": "customer support ticket with assignee",
                        "is_workflow": True,
                        "loop_role": "transaction",
                    }
                ]
            )
        if "JSON array of fields" in sys_text:
            return json.dumps(
                [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {"name": "x_code", "ttype": "char", "string": "Code"},
                    {"name": "x_status", "ttype": "selection", "selection": "[('open','Open'),('done','Done')]"},
                    {"name": "x_priority", "ttype": "selection", "selection": "[('low','Low'),('high','High')]"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                    {"name": "x_due_date", "ttype": "date", "string": "Due"},
                ]
            )
        if "relationship fixes" in sys_text:
            return json.dumps(
                [
                    {
                        "model": "x_support_ticket",
                        "field": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Customer",
                    }
                ]
            )
        if "workflow status states" in sys_text:
            return json.dumps(
                {
                    "states": [
                        {"value": "open", "label": "Open"},
                        {"value": "done", "label": "Done"},
                    ],
                    "transitions": [["open", "done"]],
                }
            )
        if "JSON array of automations" in sys_text:
            return json.dumps(
                [
                    {
                        "name": "Close ticket",
                        "model": "x_support_ticket",
                        "trigger": "on_write",
                        "filter_domain": "[]",
                        "safe_actions": [
                            {"kind": "object_write", "field": "x_status", "value": "done"}
                        ],
                    }
                ]
            )
        return "{}"

    def call_systems_with_guardrail(self) -> list[str]:
        return [c["system"] for c in self.calls if "PROTECTED MODULES" in c["system"]]


def test_staged_pipeline_runs_all_steps_with_guardrail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.ai_pipeline.retrieve_domain_pack",
        lambda *a, **k: None,
    )
    provider = _RecordingProvider()
    manifest = build_manifest(["account", "sale"], "test")
    guard = guardrail_prompt(manifest)

    draft, trace, warnings = run_staged_pipeline(
        "Build a support ticket tracker with workflow",
        provider=provider,
        protected_manifest=manifest,
    )

    assert draft.get("models")
    assert "step1:" in trace
    assert "step2:" in trace
    assert "step3:" in trace
    assert "step4:" in trace
    assert "step5:" in trace
    assert "step6:" in trace
    assert len(provider.calls) >= 5

    guarded = provider.call_systems_with_guardrail()
    assert len(guarded) >= 3
    for sys_text in guarded:
        assert "PROTECTED MODULES" in sys_text
        assert guard.strip() in sys_text or "accounting_core" in sys_text

    rel_calls = [c for c in provider.calls if "relationship fixes" in c["system"]]
    assert rel_calls
    assert rel_calls[0]["reasoning"] is True
    assert rel_calls[0]["temperature"] == pytest.approx(0.15)
    assert rel_calls[0]["format_schema"] is not None

    auto_calls = [c for c in provider.calls if "JSON array of automations" in c["system"]]
    assert auto_calls
    assert auto_calls[0]["reasoning"] is True
    assert auto_calls[0]["temperature"] == pytest.approx(0.6)
    assert auto_calls[0]["format_schema"] is not None

    wf_calls = [c for c in provider.calls if "workflow status states" in c["system"]]
    assert wf_calls
    assert wf_calls[0]["reasoning"] is True
    assert wf_calls[0]["format_schema"] is not None

    assert not any("NameError" in w for w in warnings)


def test_staged_run_artifact_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Gate artifact: record fixed staged run JSON under docs/research/."""
    monkeypatch.setattr(
        "app.ai_pipeline.retrieve_domain_pack",
        lambda *a, **k: None,
    )
    provider = _RecordingProvider()
    manifest = build_manifest(["account"], "artifact-test")
    draft, trace, warnings = run_staged_pipeline(
        "Simple task tracker",
        provider=provider,
        protected_manifest=manifest,
    )
    payload = {
        "prompt": "Simple task tracker",
        "trace": trace,
        "warnings": warnings,
        "model_count": len(draft.get("models") or []),
        "pipeline_mode": "staged",
        "guardrail_steps": len(provider.call_systems_with_guardrail()),
        "llm_calls": len(provider.calls),
    }
    out_dir = Path(__file__).resolve().parents[3] / "docs" / "research"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "staged_run_fixed_unit_test.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    assert out_path.is_file()
    assert payload["model_count"] >= 1
