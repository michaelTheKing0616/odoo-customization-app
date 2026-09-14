"""Draft Studio pack-first seed + budgeted LLM enrich."""

from __future__ import annotations

import os
import time
from typing import Any

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ["AI_ASSIST"] = "off"

from app.ai_pipeline import seed_studio_draft  # noqa: E402


def test_seed_studio_draft_law_firm_includes_matter() -> None:
    draft = seed_studio_draft(
        "Law firm practice management in Lagos Nigeria with matters and retainers"
    )
    models = {m.get("model") for m in (draft.get("models") or []) if isinstance(m, dict)}
    assert "x_matter" in models
    assert "x_bill" not in models
    assert "x_attorney" not in models
    assert "hr" in (draft.get("depends") or [])
    assert draft.get("domain_pack")
    assert (draft.get("_llm_status") or {}).get("mode") == "pack_fallback"


def test_llm_draft_budget_returns_none_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_draft_jobs import _llm_draft_with_budget

    def _slow(*_a: Any, **_k: Any) -> tuple[dict[str, Any], str, list[str], list[dict[str, Any]]]:
        time.sleep(1.5)
        return {}, "", [], []

    monkeypatch.setattr("app.ai_draft_jobs.draft_module_from_prompt", _slow)
    out = _llm_draft_with_budget(
        timeout_s=0.05,
        progress=lambda *_a, **_k: None,
        kwargs={"prompt": "law firm"},
    )
    assert out is None


AOP_LEGAL_BRIEF = (
    "Adeyemi, Okonkwo & Partners law firm. Domain is Law Firm / Legal Practice, "
    "not restaurant or hotel. No third-party food marketplace. "
    "No shop-floor or kitchen hardware. Multi-company is not required. "
    "Sample clients: Northern Harvest Ltd; Rivers Marine Services."
)


def test_pack_seed_skips_llm_for_law_firm() -> None:
    from app.ai_draft_jobs import pack_seed_skips_llm

    seed = seed_studio_draft(AOP_LEGAL_BRIEF)
    assert seed.get("domain_pack") == "law_firm"
    assert pack_seed_skips_llm(seed) is True
    assert pack_seed_skips_llm({"models": [{"model": "x_foo"}]}) is False


def test_pack_seed_skips_llm_for_gold_pos_and_refuse() -> None:
    from app.ai_draft_jobs import pack_seed_skips_llm

    gold = seed_studio_draft("Create a POS receipt configurator [custom] app")
    assert gold.get("technical_name") == "pos_receipt_options"
    assert pack_seed_skips_llm(gold) is True
    refuse = seed_studio_draft("clone the GM POS receipt configurator from the apps store")
    assert pack_seed_skips_llm(refuse) is True
    stock = seed_studio_draft(
        "# Operator brief\n## Goal\nStand up Community POS.\n"
        "## Custom residual\nNone. Do not invent x_receipt.\n"
        "## Capability path\nstock_first\n"
    )
    assert pack_seed_skips_llm(stock) is True


SLA_INVOICE_FIELD_PROMPT = (
    "We're on Community Invoicing already. Finance asked for a single extra field "
    "on customer invoices: SLA due date and time, so they can filter "
    '"invoices that will miss SLA". Do not create a new Invoices app. '
    "Do not clone account.move. Just inherit the stock invoice. One company. "
    "We are in Kenya, KES. Cashiers and salespeople shouldn't see a new menu for this."
)


def test_sla_cashier_prompt_is_invoice_field_pack_not_restaurant() -> None:
    from app.ai_domain_packs import match_domain_pack
    from app.ai_draft_jobs import _finish_seed_draft, pack_seed_skips_llm
    from app.ai_generation_engine import classify_generation, is_component_grain_draft
    from app.ai_operator_brief import build_operator_brief
    from app.ai_senior_shape import infer_extension_fields

    assert match_domain_pack(SLA_INVOICE_FIELD_PROMPT) is None
    plan = classify_generation(SLA_INVOICE_FIELD_PROMPT)
    assert plan.capability == "residual_app"
    assert plan.grain == "field_pack"

    fields = infer_extension_fields(SLA_INVOICE_FIELD_PROMPT)
    names = [str(f.get("name")) for f in fields]
    assert names == ["x_sla_due"]
    assert fields[0].get("ttype") == "datetime"

    brief = build_operator_brief(SLA_INVOICE_FIELD_PROMPT)
    assert "country" not in brief.unknowns
    assert "currency" not in brief.unknowns
    assert not any(x.lower() == "create" for x in brief.out_of_scope)
    assert any("invoices app" in x.lower() or "account.move" in x.lower() for x in brief.out_of_scope)

    seed = seed_studio_draft(SLA_INVOICE_FIELD_PROMPT)
    assert seed.get("domain_pack") != "restaurant"
    assert seed.get("_pipeline") == "component_grain"
    assert pack_seed_skips_llm(seed) is True
    assert is_component_grain_draft(seed)
    models = [str(m.get("model")) for m in (seed.get("models") or []) if isinstance(m, dict)]
    assert models == ["account.move"]
    inherit = next(m for m in seed["models"] if m.get("model") == "account.move")
    assert inherit.get("mode") == "inherit"
    fnames = {str(f.get("name")) for f in inherit.get("fields") or []}
    assert "x_sla_due" in fnames
    assert "x_bill" not in models
    assert "x_restaurant" not in models
    assert not (seed.get("menus") or [])

    closed = _finish_seed_draft(SLA_INVOICE_FIELD_PROMPT, seed, [])
    closed_models = {
        str(m.get("model"))
        for m in (closed.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    assert closed_models == {"account.move"}
    assert closed.get("domain_pack") != "restaurant"
    assert not any(
        str(m.get("model") or "").startswith("x_")
        for m in (closed.get("models") or [])
        if isinstance(m, dict)
    )
    assert (closed.get("_architecture_plan") or {}).get("strategy") == "field_pack"


VISITOR_LOG_PROMPT = (
    "Front desk still uses a paper book. I want a simple visitor log in Odoo: "
    "visitor name, who they came to see (an employee), purpose, time in, time out, "
    "optional ID number. This is not CRM and not a second Contacts app — the host "
    "is an Employee, the visitor can just be a name unless they're already a contact. "
    "We're a 40-person office in Accra. Don't invent invoicing. Mail notifications "
    "if someone sits in reception more than two hours would be nice but only if "
    "that's safe no-code, not Python."
)


def test_visitor_log_prompt_is_not_hotel_pack() -> None:
    from app.ai_domain_packs import match_domain_pack
    from app.ai_draft_jobs import pack_seed_skips_llm
    from app.ai_generation_engine import classify_generation

    assert match_domain_pack(VISITOR_LOG_PROMPT) is None
    plan = classify_generation(VISITOR_LOG_PROMPT)
    assert plan.capability == "residual_app"
    assert plan.grain != "field_pack"

    seed = seed_studio_draft(VISITOR_LOG_PROMPT)
    assert seed.get("domain_pack") != "hotel"
    assert seed.get("_pipeline") != "pack_seed"
    assert pack_seed_skips_llm(seed) is False
    models = {
        str(m.get("model"))
        for m in (seed.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    assert "x_hotel" not in models
    assert "x_room" not in models
    assert "x_booking" not in models
    assert "x_bill" not in models
    assert "x_housekeeping_task" not in models


def test_finish_seed_draft_does_not_stamp_kitchen_on_law_firm() -> None:
    from app.ai_draft_jobs import _finish_seed_draft
    from app.ai_odoo_app_bar import _web_icon_for_prompt

    seed = seed_studio_draft(AOP_LEGAL_BRIEF)
    draft = _finish_seed_draft(AOP_LEGAL_BRIEF, seed, [])
    briefing = draft.get("_domain_briefing") or {}
    assert briefing.get("collocation_id") != "restaurant"
    assert briefing.get("collocation_id") != "farm"
    assert briefing.get("industry") == "legal practice"
    models = {m.get("model") for m in (draft.get("models") or []) if isinstance(m, dict)}
    assert "x_matter" in models
    assert "x_bill" not in models
    assert "x_attorney" not in models
    assert "x_equipment" not in models
    matter = next(m for m in draft["models"] if m.get("model") == "x_matter")
    emp = next(f for f in matter["fields"] if f.get("name") == "x_employee_id")
    assert emp.get("relation") == "hr.employee"
    sc = (draft.get("_scorecard") or {}).get("dimensions") or {}
    assert float(sc.get("domain_fit") or 0) >= 7.0
    assert not any(
        "uncovered prompt noun" in str(f.get("detail") or "")
        for f in (draft.get("_scorecard") or {}).get("findings") or []
    )
    icon = _web_icon_for_prompt(AOP_LEGAL_BRIEF, draft)
    assert icon.startswith("fa-balance-scale")
    assert "fa-bed" not in icon


def test_finish_stock_reuse_is_not_cert_gold() -> None:
    from app.ai_draft_jobs import _finish_seed_draft
    from app.ai_generation_engine import is_stock_reuse_draft
    from test_ai_generation_engine import POS_STOCK_FIRST

    seed = seed_studio_draft(POS_STOCK_FIRST)
    warnings: list[str] = []
    draft = _finish_seed_draft(POS_STOCK_FIRST, seed, warnings)
    assert is_stock_reuse_draft(draft)
    cert = draft.get("_certification") or {}
    assert cert.get("tier") == "ReviewRequired"
    assert "empty-spec" in str(cert.get("note") or "").lower() or "no custom residual" in str(
        cert.get("note") or ""
    ).lower()
    plan = draft.get("_architecture_plan") or {}
    assert plan.get("strategy") == "stock_reuse"
    assert (plan.get("surface_budget") or {}).get("new_models") == 0
    assert plan.get("ambiguities") == []
    llm = draft.get("_llm_status") or {}
    assert llm.get("reason") == "stock_reuse"
    assert llm.get("mode") != "pack_fallback"
    apps = (draft.get("_generation_engine") or {}).get("stock_apps") or []
    ids = {row.get("id") for row in apps if isinstance(row, dict)}
    labels = {row.get("label") for row in apps if isinstance(row, dict)}
    assert "point_of_sale" in ids
    assert "Point of Sale" in labels
    assert draft.get("_live_apply", {}).get("ready") is False
    assert not any("contract ready" in str(w) for w in warnings)


def test_stock_reuse_architecture_merge_drops_residual_budget() -> None:
    from app.ai_architecture_plan import stamp_architecture_plan
    from test_ai_generation_engine import POS_STOCK_FIRST

    seed = seed_studio_draft(POS_STOCK_FIRST)
    seed["_architecture_plan"] = {
        "strategy": "residual_app",
        "surface_budget": {"new_models": 8, "new_js": 0, "new_controllers": 0},
        "ambiguities": ["Prompt contains alternatives — confirm residual vs stock-first"],
    }
    plan = stamp_architecture_plan(seed, prompt=POS_STOCK_FIRST)
    assert plan["strategy"] == "stock_reuse"
    assert plan["surface_budget"]["new_models"] == 0
    assert plan["ambiguities"] == []
