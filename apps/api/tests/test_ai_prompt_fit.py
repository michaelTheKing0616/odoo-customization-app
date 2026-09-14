"""Golden prompt-fit: seed + _finish_seed_draft with AI off (the 503 path)."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ["AI_ASSIST"] = "off"

from app.ai_draft_jobs import _finish_seed_draft  # noqa: E402
from app.ai_pipeline import seed_studio_draft  # noqa: E402
from tests.test_ai_generation_engine import POS_STOCK_FIRST  # noqa: E402
from tests.test_ai_pack_disambiguation import VISITOR_LOG_PROMPT  # noqa: E402
from tests.test_ai_studio_seed import (  # noqa: E402
    AOP_LEGAL_BRIEF,
    SLA_INVOICE_FIELD_PROMPT,
)

HOTEL_COLLOCATES = (
    "Hotel PMS front desk check-in workflow with housekeeping for guest rooms"
)
CASHIERS_MENU = (
    "Cashiers shouldn't see a new menu. Just inherit the stock invoice with SLA due."
)


def _model_ids(draft: dict) -> set[str]:
    return {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def test_visitor_log_finish_is_register_not_workspace() -> None:
    from app.ai_document_shape import classify_document_shape
    from app.ai_generation_engine import classify_generation

    assert classify_generation(VISITOR_LOG_PROMPT).capability == "residual_app"
    assert classify_document_shape(VISITOR_LOG_PROMPT) == "register"

    seed = seed_studio_draft(VISITOR_LOG_PROMPT)
    closed = _finish_seed_draft(VISITOR_LOG_PROMPT, seed, [])
    models = _model_ids(closed)
    assert models == {"x_visitor_log"}
    assert not any(m.endswith("_party") or m.endswith("_line") for m in models)
    assert "crm.lead" not in models
    assert "account.move" not in models
    header = next(m for m in closed["models"] if m.get("model") == "x_visitor_log")
    fields = {str(f.get("name")): f for f in header.get("fields") or [] if isinstance(f, dict)}
    assert "x_name" in fields
    emp = next(
        f
        for f in fields.values()
        if f.get("relation") == "hr.employee" or "employee" in str(f.get("name") or "")
    )
    assert emp.get("ttype") == "many2one"
    assert any("purpose" in str(n) for n in fields)
    assert any("time_in" in str(n) or n == "x_time_in" for n in fields)
    assert any("time_out" in str(n) or n == "x_time_out" for n in fields)
    assert any("id" in str(n) and n != "x_name" for n in fields)
    partner = [f for f in fields.values() if f.get("relation") == "res.partner"]
    assert not partner or partner[0].get("required") is not True
    depends = {str(x) for x in (closed.get("depends") or [])}
    assert "hr" in depends
    assert "mail" in depends
    assert "crm" not in depends
    cert = (closed.get("_certification") or {}).get("tier")
    live_cert = ((closed.get("_live_apply") or {}).get("certification_tier"))
    assert cert not in {"Production", "Gold"}
    assert live_cert not in {"Production", "Gold"}
    display = str(closed.get("display_name") or "")
    assert "visitor" in display.lower() and "log" in display.lower()
    assert not display.lower().startswith("front desk")
    tech = str(closed.get("technical_name") or "")
    assert "visitor_log" in tech
    assert "front_desk" not in tech
    autos = closed.get("automations") or []
    assert any(
        isinstance(a, dict)
        and str(a.get("trigger") or "").startswith("on_time")
        and any(
            str(sa.get("kind")) == "next_activity"
            for sa in (a.get("safe_actions") or [])
            if isinstance(sa, dict)
        )
        for a in autos
    )
    assert (closed.get("_document_shape") or (closed.get("_architecture_plan") or {}).get("document_shape")) == "register"
    budget = ((closed.get("_architecture_plan") or {}).get("surface_budget") or {}).get("new_models")
    assert budget == 1
    assert header.get("is_workflow") is not True
    assert "x_status" not in fields
    assert "x_code" not in fields
    assert not any(
        isinstance(v, dict) and str(v.get("type") or "") == "kanban"
        for v in (closed.get("views") or [])
    )
    assert not any(
        isinstance(b, dict) and str(b.get("on_model") or "") == "res.partner"
        for b in (closed.get("smart_buttons") or [])
    )
    root_xml = [
        str(m.get("xml_id") or "")
        for m in (closed.get("menus") or [])
        if isinstance(m, dict) and not m.get("parent_xml_id")
    ]
    assert "menu_root_visitor_log" in root_xml
    hosts = {
        str(h)
        for h in ((closed.get("_architecture_plan") or {}).get("stock_hosts") or [])
    }
    assert "account.move" not in hosts
    assert "crm.lead" not in hosts
    live = closed.get("_live_apply") or {}
    assert not (live.get("option_a") or [])
    brief = closed.get("_operator_brief") or {}
    assert str(brief.get("country") or "") == "Ghana"
    card = closed.get("_scorecard") or {}
    assert float(card.get("score_0_10") or 0) >= 10.0
    dims = card.get("dimensions") or {}
    assert float(dims.get("domain_fit") or 0) >= 10.0


def test_sla_field_pack_finish_stays_account_move() -> None:
    from app.ai_document_shape import classify_document_shape

    assert classify_document_shape(SLA_INVOICE_FIELD_PROMPT) == "field_pack"
    seed = seed_studio_draft(SLA_INVOICE_FIELD_PROMPT)
    closed = _finish_seed_draft(SLA_INVOICE_FIELD_PROMPT, seed, [])
    assert closed.get("grain") == "field_pack"
    assert _model_ids(closed) == {"account.move"}
    assert closed.get("domain_pack") != "restaurant"


def test_stock_reuse_pos_finish_stays_empty() -> None:
    from app.ai_document_shape import classify_document_shape
    from app.ai_generation_engine import is_stock_reuse_draft

    assert classify_document_shape(POS_STOCK_FIRST) == "stock_reuse"
    seed = seed_studio_draft(POS_STOCK_FIRST)
    closed = _finish_seed_draft(POS_STOCK_FIRST, seed, [])
    assert is_stock_reuse_draft(closed)
    assert _model_ids(closed) == set()
    assert (closed.get("_architecture_plan") or {}).get("strategy") == "stock_reuse"


def test_hotel_collocates_still_matches_hotel_pack() -> None:
    from app.ai_document_shape import classify_document_shape
    from app.ai_domain_packs import match_domain_pack

    assert match_domain_pack(HOTEL_COLLOCATES) is not None
    assert match_domain_pack(HOTEL_COLLOCATES)[0] == "hotel"
    assert classify_document_shape(HOTEL_COLLOCATES) == "workspace"
    seed = seed_studio_draft(HOTEL_COLLOCATES)
    assert seed.get("domain_pack") == "hotel"
    closed = _finish_seed_draft(HOTEL_COLLOCATES, seed, [])
    assert closed.get("domain_pack") == "hotel"
    assert "x_hotel" in _model_ids(closed) or "x_room" in _model_ids(closed) or "x_booking" in _model_ids(closed)


def test_cashiers_shouldnt_see_menu_is_not_restaurant() -> None:
    from app.ai_domain_packs import match_domain_pack

    assert match_domain_pack(CASHIERS_MENU) is None
    seed = seed_studio_draft(SLA_INVOICE_FIELD_PROMPT)
    assert seed.get("domain_pack") != "restaurant"


def test_law_firm_pack_is_matter_not_visitor_register() -> None:
    from app.ai_document_shape import classify_document_shape

    assert classify_document_shape(AOP_LEGAL_BRIEF) == "workspace"
    seed = seed_studio_draft(AOP_LEGAL_BRIEF)
    closed = _finish_seed_draft(AOP_LEGAL_BRIEF, seed, [])
    models = _model_ids(closed)
    assert "x_matter" in models
    assert "x_visitor_log" not in models
    assert closed.get("domain_pack") == "law_firm"
    assert (closed.get("_document_shape") or "workspace") == "workspace"
