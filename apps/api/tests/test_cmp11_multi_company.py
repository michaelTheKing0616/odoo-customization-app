"""CMP-11: multi-company pack + module spec record rules."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.module_spec_codec import draft_dict_to_module_spec, merge_module_spec_fragment
from app.multi_company_pack import (
    COMPANY_RULE_DOMAIN_MODULE,
    apply_multi_company_live,
    apply_multi_company_to_draft,
)
from module_generator import render_module_files


class _FakeClient:
    def __init__(self) -> None:
        self.fields: set[tuple[str, str]] = set()
        self.rules: list[dict[str, Any]] = []

    def field_exists(self, model: str, name: str) -> bool:
        return (model, name) in self.fields

    def create_field(self, request: Any) -> None:
        self.fields.add((request.model, request.name))

    def list_record_rules(self, *, model: str, limit: int = 50) -> list[Any]:
        return [
            SimpleNamespace(name=r["name"])
            for r in self.rules
            if r["model"] == model
        ]

    def create_record_rule(self, request: Any) -> None:
        self.rules.append({"model": request.model, "name": request.name})


def test_apply_multi_company_to_draft_adds_company_and_rule() -> None:
    draft = {
        "models": [
            {
                "model": "x_case",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char", "string": "Name"}],
            }
        ]
    }
    out = apply_multi_company_to_draft(draft)
    fields = out["models"][0]["fields"]
    assert any(f["name"] == "company_id" for f in fields)
    assert out["record_rules"]
    assert COMPANY_RULE_DOMAIN_MODULE in out["record_rules"][0]["domain_force"]


def test_draft_dict_to_module_spec_emits_record_rules_xml() -> None:
    draft = apply_multi_company_to_draft(
        {
            "technical_name": "mc_demo",
            "display_name": "MC Demo",
            "multi_company": True,
            "models": [
                {
                    "model": "x_case",
                    "mode": "new",
                    "fields": [{"name": "x_name", "ttype": "char", "string": "Name"}],
                }
            ],
        }
    )
    spec = draft_dict_to_module_spec(draft)
    files = render_module_files(spec)
    rules_xml = files["mc_demo/security/record_rules.xml"]
    assert "company_ids" in rules_xml
    assert "company_id" in rules_xml


def test_report_t_lang_emitted_in_qweb() -> None:
    draft = {
        "technical_name": "rep_lang",
        "display_name": "Report Lang",
        "models": [
            {
                "model": "x_inv",
                "fields": [{"name": "x_name", "ttype": "char", "string": "Name"}],
            }
        ],
        "reports": [
            {
                "name": "Invoice",
                "model": "x_inv",
                "body_html": "<p t-out='o.x_name'/>",
                "t_lang": "o.partner_id.lang",
            }
        ],
    }
    spec = draft_dict_to_module_spec(draft)
    files = render_module_files(spec)
    rep_xml = files["rep_lang/report/reports.xml"]
    assert 't-lang="o.partner_id.lang"' in rep_xml


def test_apply_multi_company_live_idempotent() -> None:
    client = _FakeClient()
    first = apply_multi_company_live(client, ["x_case"])
    second = apply_multi_company_live(client, ["x_case"])
    assert first["fields_created"] == 1
    assert first["rules_created"] == 1
    assert second["fields_created"] == 0
    assert second["rules_created"] == 0


def test_merge_documents_fragment_automation() -> None:
    from app.documents_connect import module_spec_fragment

    frag = module_spec_fragment(model="x_case", folder_id=12)
    merged = merge_module_spec_fragment({"technical_name": "t"}, frag)
    assert "documents" in merged["depends"]
    assert merged.get("documents_folder_id") == 12
    assert merged.get("automations")
