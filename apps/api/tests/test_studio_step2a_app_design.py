"""Step 2A: the LLM designs the full app; guardrails validate and repair it.

Fake LLM only. Uses the operator's Customer Health brief fixture.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.ai_conversation.app_design import (  # noqa: E402
    AppDesign,
    outline_from_brief,
    validate_and_repair,
)
from app.ai_conversation.grounding import (  # noqa: E402
    StudioGrounding,
    reset_grounding,
    set_grounding,
)
from app.ai_conversation.intent_llm import (  # noqa: E402
    reset_intent_llm_override,
    set_intent_llm_override,
)

BRIEF = (Path(__file__).parent / "fixtures" / "customer_health_brief.md").read_text()
GROUNDING = StudioGrounding(
    edition="enterprise",
    hosting="online",
    server_version="18.0+e",
    apps_installed=("CRM", "Sales", "Invoicing", "Project"),
    apps_missing=("Helpdesk",),
)


def _f(name: str, ttype: str = "char", string: str = "", **kw: Any) -> dict[str, Any]:
    return {
        "name": name,
        "type": ttype,
        "string": string or name[2:].replace("_", " ").title(),
        **kw,
    }


GOOD_DESIGN: dict[str, Any] = {
    "app_name": "Customer Health & Retention Intelligence",
    "purpose": "Score B2B customer health and act before churn.",
    "new_models": [
        {
            "name": "x_health_score",
            "label": "Customer Health Score",
            "why": "Current score per customer.",
            "views": ["kanban", "list", "form", "graph"],
            "fields": [
                _f("x_partner_id", "many2one", "Customer", relation="res.partner", required=True),
                _f("x_score", "float", "Score"),
                _f(
                    "x_health_status",
                    "selection",
                    "Health Status",
                    selection=["Healthy", "Stable", "At Risk", "Critical"],
                ),
                _f(
                    "x_history_ids",
                    "one2many",
                    "History",
                    relation="x_health_score_history",
                    inverse_name="x_health_score_id",
                ),
            ],
        },
        {
            "name": "x_health_score_history",
            "label": "Health Score History",
            "fields": [
                _f("x_health_score_id", "many2one", "Health Score", relation="x_health_score"),
                _f("x_partner_id", "many2one", "Customer", relation="res.partner"),
                _f("x_score", "float"),
                _f("x_previous_score", "float"),
                _f("x_factors", "text", "Major Factors"),
            ],
        },
        {
            "name": "x_health_rule",
            "label": "Health Score Rule",
            "is_config": True,
            "fields": [
                _f("x_operator", "selection", "Operator", selection=[">", "<", "="]),
                _f("x_threshold", "float"),
                _f("x_points", "integer"),
                _f("x_active", "boolean", "Active"),
            ],
        },
        {
            "name": "x_customer_risk",
            "label": "Customer Risk",
            "views": ["list", "kanban", "form"],
            "fields": [
                _f("x_partner_id", "many2one", "Customer", relation="res.partner"),
                _f(
                    "x_risk_type",
                    "selection",
                    "Risk Type",
                    selection=["Churn", "Payment", "Renewal"],
                ),
                _f(
                    "x_severity",
                    "selection",
                    "Severity",
                    selection=["Low", "Medium", "High", "Critical"],
                ),
                _f(
                    "x_state",
                    "selection",
                    "Status",
                    selection=["Open", "Monitoring", "Resolved", "Dismissed"],
                ),
                _f("x_owner_id", "many2one", "Owner", relation="res.users"),
            ],
        },
        {
            "name": "x_success_plan",
            "label": "Customer Success Plan",
            "fields": [
                _f("x_partner_id", "many2one", "Customer", relation="res.partner"),
                _f(
                    "x_milestone_ids",
                    "one2many",
                    "Milestones",
                    relation="x_success_milestone",
                    inverse_name="x_plan_id",
                ),
                _f("x_project_id", "many2one", "Project", relation="project.project"),
            ],
        },
        {
            "name": "x_success_milestone",
            "label": "Success Plan Milestone",
            "fields": [
                _f("x_plan_id", "many2one", "Plan", relation="x_success_plan"),
                _f("x_target_date", "date", "Target Date"),
                _f("x_done", "boolean", "Done"),
            ],
        },
        {
            "name": "x_renewal",
            "label": "Renewal",
            "fields": [
                _f("x_partner_id", "many2one", "Customer", relation="res.partner"),
                _f("x_sale_order_id", "many2one", "Subscription", relation="sale.order"),
                _f("x_renewal_date", "date", "Renewal Date"),
                _f("x_contract_value", "monetary", "Contract Value"),
                _f("x_ticket_id", "many2one", "Critical Ticket", relation="helpdesk.ticket"),
            ],
        },
        {
            "name": "x_expansion_recommendation",
            "label": "Expansion Recommendation",
            "fields": [
                _f("x_partner_id", "many2one", "Customer", relation="res.partner"),
                _f("x_lead_id", "many2one", "CRM Opportunity", relation="crm.lead"),
                _f("x_reason", "text", "Why"),
            ],
        },
        {
            "name": "x_health_config",
            "label": "Health Configuration",
            "is_config": True,
            "fields": [
                _f(
                    "x_frequency",
                    "selection",
                    "Calculation Frequency",
                    selection=["Daily", "Weekly"],
                ),
                _f("x_renewal_warning_days", "integer", "Renewal Warning (days)"),
            ],
        },
    ],
    "stock_extensions": [
        {
            "model": "res.partner",
            "reason": "Current health on the contact form.",
            "fields": [
                _f("x_health_score", "float", "Health Score"),
                _f(
                    "x_health_status",
                    "selection",
                    "Health Status",
                    selection=["Healthy", "Stable", "At Risk", "Critical"],
                ),
                _f("x_risk_ids", "one2many", "Risks", relation="x_customer_risk"),
            ],
        },
    ],
    "integrations": [
        {"app": "CRM", "module": "crm", "models": ["crm.lead"], "required": False},
        {"app": "Sales", "module": "sale", "models": ["sale.order"], "required": False},
        {"app": "Invoicing", "module": "account", "models": ["account.move"], "required": False},
        {"app": "Helpdesk", "module": "helpdesk", "models": ["helpdesk.ticket"], "required": True},
        {"app": "Project", "module": "project", "models": ["project.project"], "required": False},
    ],
    "security_groups": [
        {"name": "CS User", "access": {"x_customer_risk": "rwc", "x_health_score": "r"}},
        {"name": "CS Manager", "implied": ["CS User"]},
        {"name": "Sales Manager"},
        {"name": "Admin", "implied": ["CS Manager"]},
    ],
    "python_needed": [
        {"label": "Computed health score", "kind": "computed", "models": ["x_health_score"]},
        {"label": "Rules engine evaluation", "kind": "rules", "models": ["x_health_rule"]},
        {"label": "Nightly recompute cron", "kind": "cron"},
    ],
}

_OPTION_A_RUNGS = [
    {"rung": "metadata", "mechanism": "fields", "sufficient": False, "why": "Stored fields cannot compute this by themselves."},
    {"rung": "stock_automation", "mechanism": "automated action", "sufficient": False, "why": "Needs custom Python logic across records."},
]

GOOD_CONTRACT = {
    "requirements": [
        {
            "kind": "python",
            "subject": "Computed health score",
            "decision": "option_a",
            "evidence": "The score should be configurable and calculated from multiple signals, such as:",
            "why_metadata_cannot_do_it": "The score combines multiple changing business signals.",
            "metadata_alternative": "A manually entered score",
            "trigger": "computation",
            "rungs": _OPTION_A_RUNGS,
            "confidence": "high",
        },
        {
            "kind": "python",
            "subject": "Rules engine evaluation",
            "decision": "option_a",
            "evidence": "Create a no-code rules configuration interface.",
            "why_metadata_cannot_do_it": "The rules must evaluate multiple configurable conditions.",
            "metadata_alternative": "A fixed selection field",
            "trigger": "computation",
            "rungs": _OPTION_A_RUNGS,
            "confidence": "high",
        },
        {
            "kind": "python",
            "subject": "Nightly recompute cron",
            "decision": "option_a",
            "evidence": "Scheduled actions cannot create duplicate records.",
            "why_metadata_cannot_do_it": "The requirement requires scheduled processing with idempotency.",
            "metadata_alternative": "A person manually starts each recompute",
            "trigger": "time",
            "rungs": _OPTION_A_RUNGS,
            "confidence": "medium",
        },
    ]
}

BAD_DESIGN: dict[str, Any] = {
    "app_name": "Health",
    "new_models": [
        {
            "name": "customer_risk",
            "label": "Customer Risk",
            "fields": [
                {
                    "name": "partner",
                    "type": "many2one",
                    "string": "Customer",
                    "relation": "res.partner",
                },
                {"name": "x_level", "type": "selection", "string": "Severity", "selection": []},
                {
                    "name": "x_ghost_id",
                    "type": "many2one",
                    "string": "Ghost",
                    "relation": "x_does_not_exist",
                },
                {
                    "name": "x_plan_ids",
                    "type": "one2many",
                    "string": "Plans",
                    "relation": "x_success_plan",
                },
            ],
        },
        {
            "name": "x_customer",
            "label": "Customer",
            "fields": [
                {"name": "x_segment", "type": "char", "string": "Segment"},
            ],
        },
        {
            "name": "x_success_plan",
            "label": "Success Plan",
            "fields": [
                {
                    "name": "x_customer_ref",
                    "type": "many2one",
                    "string": "Customer",
                    "relation": "x_customer",
                },
            ],
        },
    ],
}


class _FakeProvider:
    name = "gemini"
    model = "gemini-2.5-flash"

    def __init__(
        self,
        design: dict[str, Any] | None = None,
        *,
        fail: Exception | None = None,
        repair: dict[str, Any] | None = None,
    ) -> None:
        self.design, self.fail, self.repair = design, fail, repair
        self.calls: list[dict[str, Any]] = []

    def generate_json(self, prompt: str, *, system: str = "", **kwargs: Any) -> str:
        self.calls.append({"prompt": prompt, "system": system, **kwargs})
        if system.startswith(("You extract material requirements", "You turn an App Studio brief")):
            return json.dumps(GOOD_CONTRACT)
        if system.startswith("You verify one narrow claim"):
            items = json.loads(prompt)
            return json.dumps(
                {"verdicts": [{"id": i["id"], "verdict": "supports"} for i in items if isinstance(i, dict)]}
            )
        if system.startswith("You independently review"):
            return json.dumps({"findings": []})
        if system.startswith("You design"):
            if self.fail is not None:
                raise self.fail
            if "REPAIR PASS" in prompt and self.repair is not None:
                return json.dumps(self.repair)
            return json.dumps(self.design or {})
        return json.dumps(
            {"title": "Health Monitor", "constraints": ["Health score per customer (0 to 100)"]}
        )


@pytest.fixture
def grounded(monkeypatch: pytest.MonkeyPatch):
    import app.llm_provider as lp
    from app.ai_conversation.understand import clear_enrich_cache

    clear_enrich_cache()
    holder: dict[str, Any] = {}
    monkeypatch.setattr(lp, "get_llm_provider_for_tier", lambda tier: holder.get("p"))
    g_token = set_grounding(GROUNDING)
    i_token = set_intent_llm_override(True)
    yield holder
    reset_intent_llm_override(i_token)
    reset_grounding(g_token)
    clear_enrich_cache()


def _diagnose(prompt: str = BRIEF) -> dict[str, Any]:
    from app.ai_conversation.understand import build_understanding, diagnosis_clarification

    return diagnosis_clarification(build_understanding(prompt))


def test_good_llm_design_drives_diagnosis(grounded) -> None:
    provider = grounded["p"] = _FakeProvider(GOOD_DESIGN)
    clar = _diagnose()
    design = clar["app_design"]
    names = [m["name"] for m in design["new_models"]]
    assert len(names) >= 6
    for want in (
        "x_health_score",
        "x_health_score_history",
        "x_health_rule",
        "x_customer_risk",
        "x_success_plan",
        "x_success_milestone",
        "x_renewal",
        "x_expansion_recommendation",
        "x_health_config",
    ):
        assert want in names
    assert design["source"] == "llm", design["repair_issues"]
    assert [e["model"] for e in design["stock_extensions"]] == ["res.partner"]
    integ = {i["module"]: i for i in design["integrations"]}
    assert {"crm", "sale", "account", "helpdesk", "project"} <= set(integ)
    assert integ["helpdesk"]["status"] == "deferred" and integ["helpdesk"]["required"] is False
    assert (
        integ["helpdesk"]["installed"] is False and "Install Helpdesk" in integ["helpdesk"]["note"]
    )
    assert integ["crm"]["status"] == "available"
    # helpdesk.ticket link on the renewal waits for the optional integration
    renewal = next(m for m in design["new_models"] if m["name"] == "x_renewal")
    assert "x_ticket_id" not in [f["name"] for f in renewal["fields"]]
    groups = {g["name"]: g for g in design["security_groups"]}
    assert set(groups) == {"CS User", "CS Manager", "Sales Manager", "Admin"}
    assert groups["CS Manager"]["implied"] == ["CS User"]
    assert all(any(n in g["access"] for g in groups.values()) for n in names)
    # Online: Python pieces go to the Option A lane
    assert design["python_needed"]
    code = [p for p in design["python_needed"] if p["delivery_lane"] != "online_scheduled_action"]
    assert code
    # Scheduled jobs are built on Online as scheduled actions (no module).
    assert all("scheduled action" in p["delivery_lane_copy"] for p in design["python_needed"] if p not in code)
    for piece in code:
        assert piece["delivery_lane"] == "module_sh_or_self"
        assert piece["artifact_kind"] == "option_a_module"
        assert piece["online_blocked"] == "true" and "custom-code path" in piece["lane_note"]
    u = clar["understanding"]
    rows = "\n".join(u["constraints"])
    # Must do is plain words: record labels, never technical names.
    assert "New record: Customer Risk" in rows and "x_" not in rows and "res.partner" not in rows
    assert "Add to Contacts" in rows
    assert u["host_model"] == "res.partner" and u["inherit_existing"] is False
    assert u["title"] == "Customer Health & Retention Intelligence"
    assert clar["llm_outcome"]["design"]["status"] == "called"
    design_calls = [c for c in provider.calls if c["system"].startswith("You design")]
    assert len(design_calls) == 1  # no structural issues -> no repair round
    first = design_calls[0]
    assert "## 15. Health Score History" in first["prompt"]  # full brief, not bullets
    assert "hosted on Odoo Online" in first["prompt"] and "Helpdesk" in first["prompt"]
    assert "Odoo Online cannot install custom Python" in first["system"]
    assert first["timeout_s"] > 20.0
    assert any(c["system"].startswith("You turn an App Studio brief") for c in provider.calls)
    assert any(c["system"].startswith("You independently review") for c in provider.calls)


def test_bad_design_is_repaired_not_replaced() -> None:
    design, issues = validate_and_repair(AppDesign.from_dict(BAD_DESIGN), GROUNDING, prompt=BRIEF)
    names = [m.name for m in design.new_models]
    assert names == ["x_customer_risk", "x_success_plan"]  # x_ prefix added, partner copy folded
    assert any("x_customer duplicates res.partner" in i for i in issues)
    assert any("x_does_not_exist" in i for i in issues)
    assert any("selection has no options" in i for i in issues)
    assert any("must start with x_" in i for i in issues)
    risk = next(m for m in design.new_models if m.name == "x_customer_risk")
    fields = {f.name: f for f in risk.fields}
    assert "x_ghost_id" not in fields and "x_partner_id" in fields
    assert fields["x_level"].selection and fields["x_level"].selection[0][1] == "Low"
    plan = next(m for m in design.new_models if m.name == "x_success_plan")
    pf = {f.name: f for f in plan.fields}
    assert pf["x_customer_ref_id"].relation == "res.partner"  # remapped from dropped x_customer
    assert fields["x_plan_ids"].inverse_name in pf
    assert pf[fields["x_plan_ids"].inverse_name].relation == "x_customer_risk"
    ext = {e.model: e for e in design.stock_extensions}
    assert "x_segment" in [f.name for f in ext["res.partner"].fields]


def test_bad_llm_design_gets_one_repair_round(grounded) -> None:
    provider = grounded["p"] = _FakeProvider(BAD_DESIGN, repair=BAD_DESIGN)
    clar = _diagnose()
    design = clar["app_design"]
    calls = [c for c in provider.calls if c["system"].startswith("You design")]
    assert len(calls) == 2 and "REPAIR PASS" in calls[1]["prompt"]
    assert design["llm_outcome"]["repair_status"] == "called"
    assert design["repair_issues"]
    # A 2-model design for a 15-section brief is not allowed to shrink it:
    # the repaired design keeps its models and gains the sections it missed.
    names = [m["name"] for m in design["new_models"]]
    assert len(names) >= 5 and design["source"].startswith("llm")
    assert names[:2] == ["x_customer_risk", "x_success_plan"]
    assert "x_customer" not in names and "x_health_score_history" in names
    assert any("sections the design missed" in n for n in design["notes"])


def test_llm_timeout_falls_back_to_section_outline(grounded) -> None:
    from app.llm_provider import LLMError

    grounded["p"] = _FakeProvider(fail=LLMError("Gemini request timed out after 60s"))
    clar = _diagnose()
    design = clar["app_design"]
    names = [m["name"] for m in design["new_models"]]
    assert len(names) >= 5, names
    assert design["source"] == "outline"
    assert design["llm_outcome"]["status"] == "timed_out"
    assert "x_customer_risk" in names and "x_health_score_history" in names
    risk = next(m for m in design["new_models"] if m["name"] == "x_customer_risk")
    rf = {f["name"]: f for f in risk["fields"]}
    assert rf["x_customer_id"]["relation"] == "res.partner"
    assert [o[1] for o in rf["x_status"]["selection"]] == [
        "Open",
        "Monitoring",
        "Resolved",
        "Dismissed",
    ]
    assert {g["name"] for g in design["security_groups"]} >= {
        "Customer Success User",
        "Administrator",
    }
    rows = [r for r in clar["understanding"]["constraints"] if r.startswith("New record")]
    assert len(rows) >= 5


def test_outline_parses_markdown_sections_without_llm() -> None:
    design = outline_from_brief(BRIEF, app_name="Customer Health & Retention Intelligence")
    assert len(design.new_models) >= 5
    assert all(m.name.startswith("x_") for m in design.new_models)


def test_short_brief_unchanged(grounded) -> None:
    provider = grounded["p"] = _FakeProvider(GOOD_DESIGN)
    clar = _diagnose("Add a Priority field on sales orders.")
    assert clar["app_design"] is None
    assert not [c for c in provider.calls if c["system"].startswith("You design")]
    assert clar["understanding"]["app_design"] is None


def test_design_shape_budget() -> None:
    from app.ai_document_shape import classify_document_shape, shape_budget

    draft = {"_app_design": {"new_models": [{"name": f"x_m{i}"} for i in range(9)]}}
    assert classify_document_shape("Build an app.", draft) == "workspace"
    assert shape_budget("workspace", design_n=9) == 9
    assert shape_budget("workspace", design_n=20) == 12
    assert shape_budget("register") == 1
