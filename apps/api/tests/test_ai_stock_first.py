"""Stock-first residual contract — packs optional, every domain."""

from __future__ import annotations

from app.ai_depth import depth_gaps
from app.ai_pipeline import seed_unpacked_draft
from app.ai_reuse_planner import plan_reuse
from app.ai_stock_first import (
    extract_explicit_residuals,
    is_reuse_rich,
    normalize_residual_leaf,
)
from app.job_autopilot.planner import build_job_packet


INSURANCE_PROMPT = (
    "Insurance brokerage. Custom residual is the policy file. "
    "Quotations, customer invoices, and staff. "
    "Do not invent a parallel invoice or a second CRM."
)

VET_PROMPT = (
    "Small-animal veterinarian. Custom residual is the visit document. "
    "Appointments use Calendar. Invoicing is stock Accounting. "
    "Doctors are employees."
)


def test_explicit_residual_normalizes_file_suffix() -> None:
    assert normalize_residual_leaf("matter file only") == "matter"
    assert normalize_residual_leaf("policy document") == "policy"
    assert normalize_residual_leaf("invoice file") == ""
    found = extract_explicit_residuals(
        "Custom residual is the policy file. Do not invent a parallel invoice."
    )
    assert found == [
        (
            "policy",
            "x_policy",
            "Policy document — stock Community apps do not replace this residual.",
        )
    ]


def test_unpacked_insurance_brief_is_stock_first_without_a_pack() -> None:
    from app.ai_domain_briefing import build_domain_briefing
    from app.ai_domain_packs import match_domain_pack

    assert match_domain_pack(INSURANCE_PROMPT) is None
    draft = seed_unpacked_draft(
        INSURANCE_PROMPT,
        briefing=build_domain_briefing(INSURANCE_PROMPT),
        ambition="comprehensive",
    )
    ids = {m["model"] for m in draft["models"] if isinstance(m, dict)}
    assert "x_policy" in ids
    assert "x_bill" not in ids
    assert "x_invoice" not in ids
    assert "x_attorney" not in ids
    assert "x_client" not in ids
    assert "x_task" not in ids
    assert "x_event" not in ids
    assert is_reuse_rich(draft)
    reuse = (draft.get("reuse") or {}).get("plan") or {}
    models = set(reuse.get("models") or [])
    assert "account.move" in models
    assert "sale.order" in models
    assert "hr.employee" in models
    assert "depth_models" not in depth_gaps(draft, "comprehensive")
    assert "x_policy_party" in ids
    assert "x_policy_line" in ids
    assert "sale.order" in ids
    so = next(m for m in draft["models"] if m["model"] == "sale.order")
    assert so.get("mode") == "inherit"
    assert any(f.get("name") == "x_policy_id" for f in so.get("fields") or [])
    policy = next(m for m in draft["models"] if m["model"] == "x_policy")
    rels = {f.get("relation") for f in (policy.get("fields") or [])}
    assert "res.partner" in rels
    assert "hr.employee" in rels


def test_unpacked_vet_visit_does_not_clone_calendar_or_invoices() -> None:
    from app.ai_domain_briefing import build_domain_briefing
    from app.ai_domain_packs import match_domain_pack

    assert match_domain_pack(VET_PROMPT) is None
    draft = seed_unpacked_draft(
        VET_PROMPT,
        briefing=build_domain_briefing(VET_PROMPT),
        ambition="comprehensive",
    )
    ids = {m["model"] for m in draft["models"] if isinstance(m, dict)}
    assert "x_visit" in ids
    assert "x_session" not in ids
    assert "x_booking" not in ids
    assert "x_event" not in ids
    assert "x_bill" not in ids
    assert "x_doctor" not in ids
    visit = next(m for m in draft["models"] if m["model"] == "x_visit")
    rels = {f.get("relation") for f in (visit.get("fields") or [])}
    assert "hr.employee" in rels


def test_autopilot_reads_explicit_residual_without_a_needle() -> None:
    packet = build_job_packet(
        "Architecture studio. Custom residual is the project file. "
        "Quotations and invoices are stock Odoo. Staff are employees.",
        use_llm=False,
    )
    assert any(r.model == "x_project" for r in packet.custom_residuals)
    assert not any(r.model == "x_invoice" for r in packet.custom_residuals)


def test_reuse_plan_teaches_stock_not_attorney_clone() -> None:
    plan = plan_reuse(INSURANCE_PROMPT)
    blob = plan.prompt_block()
    assert "hr.employee" in blob
    assert "x_attorney" in blob
    assert "matter, attorney" not in blob


AOP_ENRICH_PROMPT = (
    "Adeyemi, Okonkwo & Partners law firm. Domain is Law Firm / Legal Practice. "
    "Custom residual is the matter file. Quotations and customer invoices are stock. "
    "Lawyers are employees. Sample clients: Northern Harvest Ltd; Rivers Marine Services."
)


def _clone_dump_models() -> list[dict]:
    return [
        {"model": mid, "fields": [{"name": "x_name", "ttype": "char", "required": True}]}
        for mid in (
            "x_attorney",
            "x_matter",
            "x_matter_party",
            "x_matter_line",
            "x_expense",
            "x_task",
            "x_event",
            "x_document",
            "x_compliance",
            "x_bill",
            "x_payment",
            "x_deposit",
            "x_bill_line",
        )
    ]


def test_clip_enrichment_keeps_law_firm_residual_only() -> None:
    from app.ai_enrich_jobs import finalize_enriched_draft
    from app.ai_pipeline import seed_studio_draft

    seed = seed_studio_draft(AOP_ENRICH_PROMPT)
    dump = {
        **seed,
        "models": _clone_dump_models(),
        "_pack_model_ids": [
            "x_attorney",
            "x_matter",
            "x_bill",
            "x_task",
            "x_event",
        ],
        "_domain_briefing": {
            "industry": "farm / agriculture",
            "collocation_id": "farm",
            "source": "collocation",
            "equipment_types": [["tractor", "Tractor"]],
        },
        "_llm_status": {"mode": "llm_full", "completed_steps": ["quality", "depth", "critique"]},
        "multi_company": True,
        "depends": ["base", "contacts", "mail"],
    }
    finalize_enriched_draft(dump, prompt=AOP_ENRICH_PROMPT, warnings=[])
    ids = {m["model"] for m in dump["models"] if isinstance(m, dict)}
    assert "x_matter" in ids
    assert "x_matter_party" in ids
    assert "x_matter_line" in ids
    assert "x_conflict_check" in ids
    assert "x_matter_document" in ids
    assert "sale.order" in ids
    assert "x_attorney" not in ids
    assert "x_bill" not in ids
    assert "x_task" not in ids
    assert "x_event" not in ids
    assert "x_payment" not in ids
    assert "hr" in (dump.get("depends") or [])
    assert "account" in (dump.get("depends") or [])
    briefing = dump.get("_domain_briefing") or {}
    assert briefing.get("collocation_id") != "farm"
    assert briefing.get("industry") == "legal practice"
    assert dump.get("multi_company") is False
    pack_ids = set(dump.get("_pack_model_ids") or [])
    assert {
        "x_matter",
        "x_matter_party",
        "x_matter_line",
        "x_conflict_check",
        "x_matter_document",
        "sale.order",
        "hr.employee",
    } <= pack_ids
    assert "x_attorney" not in pack_ids
    assert "x_bill" not in pack_ids
    matter = next(m for m in dump["models"] if m["model"] == "x_matter")
    status = next(f for f in matter["fields"] if f["name"] == "x_status")
    assert "billed" in str(status.get("selection") or "")
    assert "discovery" not in str(status.get("selection") or "")
    assert any(
        isinstance(f, dict) and f.get("name") == "x_employee_id" and f.get("relation") == "hr.employee"
        for f in matter["fields"]
    )


def _aop_studio_clone_dump() -> dict:
    """07:42 Draft Studio shape: pack_seed + LLM clones + farm briefing + 10.0 lie."""
    models = _clone_dump_models()
    for model in models:
        if model["model"] != "x_matter":
            continue
        model["is_workflow"] = True
        model["fields"].extend(
            [
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "selection": (
                        "[('intake','Intake'),('conflict_check','Conflict check'),"
                        "('open','Open'),('discovery','Discovery'),('trial','Trial'),"
                        "('settlement','Settlement'),('closed','Closed'),('on_hold','On hold')]"
                    ),
                    "required": True,
                    "default": "intake",
                },
                {
                    "name": "x_attorney_id",
                    "ttype": "many2one",
                    "string": "Responsible Attorney",
                    "relation": "x_attorney",
                    "required": True,
                },
            ]
        )
        model["state_field"] = {
            "field": "x_status",
            "states": [
                "intake",
                "conflict_check",
                "open",
                "discovery",
                "trial",
                "settlement",
                "closed",
                "on_hold",
            ],
            "transitions": [["open", "intake"], ["intake", "conflict_check"]],
        }
    return {
        "technical_name": "law_firm_management",
        "display_name": "Law Firm Management",
        "domain_pack": "law_firm",
        "depends": ["base", "contacts", "mail"],
        "multi_company": True,
        "models": models,
        "_user_prompt": (
            AOP_ENRICH_PROMPT
            + " Custom residual is the matter file only. "
            "Do not invent a parallel invoice or client model."
        ),
        "_pipeline": "pack_seed",
        "_llm_status": {
            "mode": "llm_full",
            "completed_steps": ["quality", "depth", "critique"],
        },
        "_domain_briefing": {
            "industry": "farm / agriculture",
            "collocation_id": "farm",
            "source": "collocation",
            "equipment_types": [["tractor", "Tractor"]],
        },
        "_critique": {
            "ready": True,
            "notes": list("Missing fields such as x_confirm_date in x_matter."),
            "checklist": [{"id": "audit_trail", "ok": True, "note": "ok"}],
            "repairs": [],
            "suggestions": [],
        },
        "custom_code_blocks": [
            {
                "model": "x_bill",
                "kind": "python",
                "content": "pass",
                "source_file": "models/x_bill.py",
            }
        ],
    }


def test_scorecard_rejects_law_firm_clone_dump() -> None:
    from app.ai_draft_scorecard import draft_scorecard
    from app.ai_stock_first import list_stock_clone_models

    dump = _aop_studio_clone_dump()
    clones = list_stock_clone_models(dump)
    assert "x_attorney" in clones
    assert "x_bill" in clones
    assert "x_payment" in clones
    assert "x_deposit" in clones
    card = draft_scorecard(dump, user_prompt=dump["_user_prompt"])
    assert card["score_0_10"] <= 5.0
    assert card["dimensions"]["domain_fit"] < 10.0
    details = " ".join(str(f.get("detail") or "") for f in card["findings"])
    assert "stock clone" in details
    assert "x_bill" in {f.get("element") for f in card["findings"]}


def test_expert_review_repairs_law_firm_clone_dump() -> None:
    from app.expert.draft_review import review_draft

    dump = _aop_studio_clone_dump()
    result = review_draft(dump, user_prompt=dump["_user_prompt"], apply_fixes=True)
    assert result.draft is not None
    ids = {m["model"] for m in result.draft["models"] if isinstance(m, dict)}
    assert ids >= {"x_matter", "x_matter_party", "x_matter_line", "x_conflict_check", "x_matter_document"}
    assert "sale.order" in ids
    assert "calendar.event" in ids
    assert "x_attorney" not in ids
    assert "x_bill" not in ids
    assert "x_task" not in ids
    assert "x_event" not in ids
    assert "x_payment" not in ids
    assert "x_deposit" not in ids
    assert "hr" in (result.draft.get("depends") or [])
    assert "account" in (result.draft.get("depends") or [])
    assert result.draft.get("multi_company") is False
    briefing = result.draft.get("_domain_briefing") or {}
    assert briefing.get("collocation_id") != "farm"
    matter = next(m for m in result.draft["models"] if m["model"] == "x_matter")
    status = next(f for f in matter["fields"] if f["name"] == "x_status")
    assert "billed" in str(status.get("selection") or "")
    assert "discovery" not in str(status.get("selection") or "")
    assert any(
        isinstance(f, dict)
        and f.get("name") == "x_employee_id"
        and f.get("relation") == "hr.employee"
        for f in matter["fields"]
    )
    notes = (result.draft.get("_critique") or {}).get("notes") or []
    assert not (
        notes and all(isinstance(n, str) and len(n) == 1 for n in notes)
    )
    code_models = {
        b.get("model")
        for b in (result.draft.get("custom_code_blocks") or [])
        if isinstance(b, dict)
    }
    assert "x_bill" not in code_models
    assert result.score_before <= 5.0
    assert result.score_after is not None
    assert result.score_after >= 8.0
    cert = result.draft.get("_certification") if isinstance(result.draft.get("_certification"), dict) else {}
    # Expert verdict is JSON closer hygiene — not Certification. Clone dump must not stay clones.
    assert result.verdict in {"ready", "needs_work"}
    assert str(cert.get("tier") or "") not in {"Gold"}


def test_clip_keeps_hotel_pack_bill() -> None:
    from app.ai_domain_pack_hotel import hotel_pack
    from app.ai_stock_first import clip_to_stock_first_floor

    pack = hotel_pack()
    pack["models"] = list(pack["models"]) + [
        {
            "model": "x_attorney",
            "fields": [{"name": "x_name", "ttype": "char", "required": True}],
        }
    ]
    pack["_user_prompt"] = "Boutique hotel with room bookings and guest folios."
    notes = clip_to_stock_first_floor(pack, user_prompt=pack["_user_prompt"])
    ids = {m["model"] for m in pack["models"] if isinstance(m, dict)}
    assert "x_bill" in ids
    assert "x_attorney" not in ids
    assert any("clipped" in n for n in notes)
