"""Domain-agnostic Draft Studio quality — Pay/QR host, reuse, MC, party, warehouse."""

from __future__ import annotations

from app.ai_capability_gaps import stamp_capability_gaps
from app.ai_capability_option_a_scaffold import host_model_from_draft, payment_link_python
from app.ai_draft_jobs import _finish_seed_draft
from app.ai_model_quality import repair_draft_integrity
from app.ai_pipeline import seed_studio_draft
from app.ai_post_critique import ensure_workflow_models_have_state_field
from app.ai_production_shape import run_production_shape_pass
from app.ai_reuse_planner import plan_reuse
from app.ai_static_odoo import analyze_python_ast
from app.ai_stock_catalog import infer_catalog_reuse, stock_entry
from app.ai_stock_reuse import infer_stock_reuse


AOP_QUALITY_BRIEF = (
    "Adeyemi, Okonkwo & Partners law firm. Domain is Law Firm / Legal Practice. "
    "Custom residual is the matter file. Quotations, sales orders, and customer "
    "invoices are stock Odoo documents. Lawyers are employees. "
    "Multi-company is not required; Lagos and Abuja are two offices of one company. "
    "Paystack: dynamic QR and card checkout on retainer invoices."
)

_FAKE_CATALOG = [
    stock_entry("account.move", "Journal Entry"),
    stock_entry("sale.order", "Sales Order"),
    stock_entry("hr.employee", "Employee"),
    stock_entry("calendar.event", "Event"),
    stock_entry("res.partner", "Contact"),
    stock_entry("stock.warehouse", "Warehouse"),
    stock_entry("stock.quant", "Quant"),
    stock_entry("iap.account", "IAP Account"),
]


def test_paystack_qr_hosts_account_move_not_calendar() -> None:
    seed = seed_studio_draft(AOP_QUALITY_BRIEF)
    seed["_user_prompt"] = AOP_QUALITY_BRIEF
    stamp_capability_gaps(seed, AOP_QUALITY_BRIEF)
    assert host_model_from_draft(seed, prompt=AOP_QUALITY_BRIEF) == "account.move"
    move = next(m for m in seed["models"] if m.get("model") == "account.move")
    names = {f.get("name") for f in (move.get("fields") or [])}
    assert "x_payment_url" in names
    assert "x_qr_payload" in names
    cal = next(m for m in seed["models"] if m.get("model") == "calendar.event")
    cal_names = {f.get("name") for f in (cal.get("fields") or [])}
    assert "x_payment_url" not in cal_names
    blobs = "\n".join(
        str(b.get("content") or "")
        for b in (seed.get("custom_code_blocks") or [])
        if isinstance(b, dict)
    )
    assert "account.report_invoice_document" in blobs
    assert "_inherit = 'calendar.event'" not in blobs
    assert "calendar_event_document_extras" not in blobs
    for v in seed.get("views") or []:
        if not isinstance(v, dict):
            continue
        arch = str(v.get("arch") or "")
        assert "x_payment_url" not in arch
        assert "x_qr_payload" not in arch


def test_justified_sudo_is_not_a_static_finding() -> None:
    code = payment_link_python("account.move")
    findings = analyze_python_ast(code, source_file="models/account_move_document_extras.py")
    assert not any(f.get("rule") == "sudo_call" for f in findings)
    unjustified = "self.env['res.partner'].sudo().search([])"
    hits = analyze_python_ast(unjustified, source_file="models/bad.py")
    assert any(f.get("rule") == "sudo_call" for f in hits)


def test_pack_seed_with_catalog_is_connection_grounded() -> None:
    seed = seed_studio_draft(AOP_QUALITY_BRIEF)
    available = [e["model"] for e in _FAKE_CATALOG]
    draft = _finish_seed_draft(
        AOP_QUALITY_BRIEF,
        seed,
        [],
        available_models=available,
        installed_modules=["account", "sale", "hr", "calendar", "stock"],
        stock_catalog=_FAKE_CATALOG,
    )
    plan = (draft.get("reuse") or {}).get("plan") or {}
    assert plan.get("source") == "connection"
    grounding = draft.get("_planner_grounding") or {}
    assert int(grounding.get("catalog_size") or 0) == len(_FAKE_CATALOG)


def test_stock_odoo_documents_does_not_infer_warehouse() -> None:
    prompt = (
        "Quotations, sales orders, and customer invoices are stock Odoo documents. "
        "Law firm matter file. Paystack retainers."
    )
    decisions, _notes, _cat = infer_stock_reuse(prompt)
    models = {d["model"] for d in decisions}
    assert "stock.warehouse" not in models
    assert "stock.quant" not in models
    hits = infer_catalog_reuse(
        prompt,
        _FAKE_CATALOG,
        available_models={e["model"] for e in _FAKE_CATALOG},
    )
    hit_models = {h["model"] for h in hits}
    assert "stock.warehouse" not in hit_models
    assert "stock.quant" not in hit_models
    assert "iap.account" not in hit_models


def test_inventory_brief_still_infers_warehouse() -> None:
    prompt = "Warehouse inventory, replenish from vendors, stock quants and pickings."
    decisions, _notes, _cat = infer_stock_reuse(prompt)
    models = {d["model"] for d in decisions}
    assert "stock.warehouse" in models
    hits = infer_catalog_reuse(
        prompt,
        _FAKE_CATALOG,
        available_models={e["model"] for e in _FAKE_CATALOG},
    )
    assert "stock.warehouse" in {h["model"] for h in hits}


def test_multi_company_false_does_not_emit_isolation_rules() -> None:
    seed = seed_studio_draft(AOP_QUALITY_BRIEF)
    seed["_user_prompt"] = AOP_QUALITY_BRIEF
    seed["multi_company"] = False
    run_production_shape_pass(seed)
    names = [str(r.get("name") or "") for r in (seed.get("record_rules") or [])]
    assert not any("Multi-company" in n for n in names)
    assert seed.get("multi_company") is False
    party = next(m for m in seed["models"] if m.get("model") == "x_matter_party")
    field_names = {f.get("name") for f in (party.get("fields") or [])}
    assert "x_company_id" in field_names  # optional tagging stays


def test_party_link_stays_demoted_after_quality_and_closer() -> None:
    seed = seed_studio_draft(AOP_QUALITY_BRIEF)
    seed["_user_prompt"] = AOP_QUALITY_BRIEF
    repair_draft_integrity(seed, ambition="comprehensive")
    ensure_workflow_models_have_state_field(seed)
    run_production_shape_pass(seed)
    party = next(m for m in seed["models"] if m.get("model") == "x_matter_party")
    assert party.get("is_workflow") is False
    names = {f.get("name") for f in (party.get("fields") or [])}
    assert "x_status" not in names
    assert not isinstance(party.get("state_field"), dict)
    assert not any(
        isinstance(v, dict)
        and v.get("model") == "x_matter_party"
        and v.get("type") == "kanban"
        for v in (seed.get("views") or [])
    )


def test_scorecard_does_not_require_rules_for_optional_company_field() -> None:
    from app.ai_draft_scorecard import draft_scorecard

    draft = {
        "technical_name": "law_firm_management",
        "depends": ["base"],
        "grain": "full_app",
        "multi_company": False,
        "models": [
            {
                "model": "x_matter",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "relation": "res.company",
                    },
                ],
            }
        ],
        "views": [],
        "menus": [],
        "access_rules": [
            {"model": "model_x_matter", "group": "base.group_user", "perm_read": 1}
        ],
        "_user_prompt": AOP_QUALITY_BRIEF,
        "_architecture_plan": {
            "strategy": "residual_app",
            "surface_budget": {"new_models": 8},
            "forbidden_clones": [],
        },
    }
    card = draft_scorecard(draft, user_prompt=AOP_QUALITY_BRIEF)
    elements = {
        f.get("element") for f in (card.get("findings") or []) if isinstance(f, dict)
    }
    assert "security_record_rule" not in elements


def test_plan_reuse_connection_source_when_catalog_passed() -> None:
    plan = plan_reuse(
        AOP_QUALITY_BRIEF,
        available_models=[e["model"] for e in _FAKE_CATALOG],
        installed_modules=["account", "sale", "hr"],
        stock_catalog=_FAKE_CATALOG,
    )
    assert plan.source == "connection"
    assert "stock.warehouse" not in {d.model for d in plan.decisions}


def test_pack_seed_skips_catalog_suggestion_dump() -> None:
    noisy = list(_FAKE_CATALOG) + [
        stock_entry(
            "account.analytic.line.calendar.employee",
            "Personal Filters on Employees for the Calendar view",
        ),
        stock_entry("crm.iap.lead.industry", "CRM IAP Lead Industry"),
    ]
    _decisions, _notes, suggestions = infer_stock_reuse(
        AOP_QUALITY_BRIEF,
        available_models=[e["model"] for e in noisy],
        installed_modules=["account", "crm"],
        pack_reuse_stock=[{"model": "res.partner", "modules": ["contacts"]}],
        stock_catalog=noisy,
    )
    assert suggestions == []


def test_catalog_infer_skips_iap_and_four_part_technical_names() -> None:
    noisy = list(_FAKE_CATALOG) + [
        stock_entry(
            "account.analytic.line.calendar.employee",
            "Personal Filters on Employees for the Calendar view",
        ),
        stock_entry("crm.iap.lead.industry", "CRM IAP Lead Industry"),
        stock_entry("account.reconcile.model.line", "Rules for the reconciliation model"),
    ]
    hits = infer_catalog_reuse(
        AOP_QUALITY_BRIEF + " account invoice payment calendar employee",
        noisy,
        available_models={e["model"] for e in noisy},
    )
    models = {h["model"] for h in hits}
    assert "account.analytic.line.calendar.employee" not in models
    assert "crm.iap.lead.industry" not in models
    assert "account.reconcile.model.line" not in models


def test_quality_closer_does_not_invent_stock_reverse_o2m_or_ops_status() -> None:
    from app.ai_odoo_app_bar import close_odoo_architecture, short_model_label
    from app.ai_presentation import group_menus_if_needed
    from app.ai_workflow_semantic import apply_semantic_transitions_to_model

    seed = seed_studio_draft(AOP_QUALITY_BRIEF)
    seed["_user_prompt"] = AOP_QUALITY_BRIEF
    repair_draft_integrity(seed, ambition="comprehensive")
    close_odoo_architecture(seed, user_prompt=AOP_QUALITY_BRIEF)
    run_production_shape_pass(seed)

    by_id = {m["model"]: m for m in seed["models"] if isinstance(m, dict)}
    matter_names = {f.get("name") for f in (by_id["x_matter"].get("fields") or [])}
    assert not any(
        isinstance(n, str) and "." in n for n in matter_names
    )
    sale = by_id["sale.order"]
    sale_names = {f.get("name") for f in (sale.get("fields") or [])}
    assert "x_matter_ids" not in sale_names
    assert "x_matter_id" in sale_names
    task = by_id["project.task"]
    task_names = {f.get("name") for f in (task.get("fields") or [])}
    assert "x_status" not in task_names
    line_names = {f.get("name") for f in (by_id["x_matter_line"].get("fields") or [])}
    assert "x_employee_id" in line_names
    assert "x_date" in line_names
    assert "x_status" in line_names
    assert "x_company_id" in line_names

    btns = seed.get("smart_buttons") or []
    labels = {str(b.get("label") or "") for b in btns if isinstance(b, dict)}
    assert "Sale.Orders" not in labels
    assert "Calendar.Events" not in labels
    assert "Sale Orders" not in labels
    assert "Account Moves" not in labels
    assert short_model_label("calendar.event", plural=True) == "Meetings"
    assert short_model_label("sale.order", plural=True) == "Quotations"
    assert short_model_label("account.move", plural=True) == "Invoices"
    header_btns = {
        str(b.get("related_model") or ""): str(b.get("label") or "")
        for b in btns
        if isinstance(b, dict) and b.get("on_model") == "x_matter"
    }
    assert header_btns.get("sale.order") == "Quotations"
    assert header_btns.get("account.move") == "Invoices"
    assert header_btns.get("calendar.event") == "Meetings"
    assert header_btns.get("project.task") == "Tasks"

    conflict = by_id["x_conflict_check"]
    apply_semantic_transitions_to_model(conflict)
    edges = {
        (str(a), str(b))
        for a, b in (conflict.get("state_field") or {}).get("transitions") or []
    }
    assert ("pending", "blocked") in edges
    assert ("cleared", "blocked") not in edges

    stock_o2m = {
        str(f.get("relation") or "")
        for f in (by_id["x_matter"].get("fields") or [])
        if isinstance(f, dict) and f.get("ttype") == "one2many"
    }
    assert not (stock_o2m & {"sale.order", "calendar.event", "account.move", "crm.lead"})
    form = next(
        v
        for v in (seed.get("views") or [])
        if isinstance(v, dict) and v.get("model") == "x_matter" and v.get("type") == "form"
    )
    arch = str(form.get("arch") or "")
    assert "<group string=\"Calendar Event\"></group>" not in arch
    assert "<group string=\"Sale Order\"></group>" not in arch
    btn_targets = {
        (str(b.get("on_model")), str(b.get("related_model")))
        for b in btns
        if isinstance(b, dict)
    }
    assert ("x_matter", "sale.order") in btn_targets
    assert ("x_matter", "calendar.event") in btn_targets
    assert ("x_matter", "x_matter_line") not in btn_targets
    assert ("x_matter", "x_matter_party") not in btn_targets
    assert ("x_matter", "x_conflict_check") not in btn_targets
    assert ("x_matter", "x_matter_document") not in btn_targets
    assert "x_lead_id" in matter_names
    assert "x_analytic_account_id" in matter_names
    assert 'name="x_lead_id"' not in arch
    assert 'name="x_sale_order_id"' not in arch
    assert 'name="x_invoice_id"' not in arch
    assert 'name="x_analytic_account_id"' in arch
    assert "x_hours" in arch
    assert "x_rate" in arch
    assert "x_amount" in arch
    billable = arch
    if "Billable" in arch:
        billable = arch.split("Billable", 1)[1]
        if "</page>" in billable:
            billable = billable.split("</page>", 1)[0]
    assert 'name="x_date"' in billable
    assert billable.find('name="x_hours"') < billable.find('name="x_code"')
    partner_related = {
        str(b.get("related_model") or "")
        for b in btns
        if isinstance(b, dict) and b.get("on_model") == "res.partner"
    }
    assert "x_matter" in partner_related
    assert "x_matter_party" not in partner_related
    assert "x_conflict_check" not in partner_related
    assert "x_matter_document" not in partner_related
    act_by = {
        str(a.get("technical_name") or ""): str(a.get("model") or "")
        for a in (seed.get("actions") or [])
        if isinstance(a, dict)
    }
    menu_models = {
        act_by.get(str(menu.get("action_xml_id") or ""), "")
        for menu in (seed.get("menus") or [])
        if isinstance(menu, dict)
    }
    assert "x_matter_line" not in menu_models
    assert "x_matter_party" not in menu_models
    line_help = next(
        (
            str(f.get("help") or "")
            for f in (by_id["x_matter_line"].get("fields") or [])
            if isinstance(f, dict) and f.get("name") == "x_code"
        ),
        "",
    )
    assert "MATTER2" not in line_help
    assert "ir.sequence" not in line_help.lower()
    seq_models = {
        str(s.get("model") or "")
        for s in (seed.get("sequences") or [])
        if isinstance(s, dict)
    }
    assert "x_matter_line" not in seq_models
    assert "x_project_id" not in matter_names
    assert arch.lower().count("<notebook") == 1
    assert '<group string="Parties"><notebook>' not in arch
    for fname in (
        "x_matter_party_ids",
        "x_matter_line_ids",
        "x_conflict_check_ids",
        "x_matter_document_ids",
    ):
        assert fname in arch

    menus = [m for m in (seed.get("menus") or []) if isinstance(m, dict)]
    assert not any(m.get("name") == "Other" for m in menus)
    grouped = {
        "menus": [
            {"name": "Law Firm", "xml_id": "root", "technical_name": "root"},
            {"name": "Matters", "action_xml_id": "a1", "parent_xml_id": "root"},
            {"name": "Parties", "action_xml_id": "a2", "parent_xml_id": "root"},
        ],
        "actions": [
            {"technical_name": "a1", "model": "x_matter"},
            {"technical_name": "a2", "model": "x_matter_party"},
        ],
    }
    group_menus_if_needed(grouped, threshold=1)
    assert not any(m.get("name") == "Other" for m in grouped["menus"])


def test_pack_seed_scorecard_is_not_capped_by_stock_fk_or_reset_to_draft() -> None:
    from app.ai_draft_scorecard import draft_scorecard
    from app.ai_draft_validators import run_draft_validators
    from app.ai_odoo_app_bar import close_odoo_architecture

    seed = seed_studio_draft(AOP_QUALITY_BRIEF)
    seed["_user_prompt"] = AOP_QUALITY_BRIEF
    repair_draft_integrity(seed, ambition="comprehensive")
    close_odoo_architecture(seed, user_prompt=AOP_QUALITY_BRIEF)
    run_production_shape_pass(seed)
    validators = run_draft_validators(seed)
    assert validators["all_green"] is True, validators
    card = draft_scorecard(seed, user_prompt=AOP_QUALITY_BRIEF)
    details = [str(f.get("detail") or "") for f in (card.get("findings") or [])]
    assert not any("duplicate parent" in d for d in details)
    assert not any("terminal state has outgoing edge" in d for d in details)
    assert card["score_0_10"] == 10.0
    assert card.get("validators", {}).get("all_green") is True
    from app.ai_rules import completeness_checklist

    items = {c["id"]: c for c in completeness_checklist(seed) if isinstance(c, dict)}
    assert items["has_views"]["ok"] is True
    detail = str(items["has_views"].get("detail") or "")
    assert "calendar.event" not in detail
    assert "sale.order" not in detail
    assert "hr.employee" not in detail


def test_scorecard_allows_blocked_reset_to_pending_not_closed_to_pending() -> None:
    from app.ai_draft_scorecard import _score_semantics

    def _conflict(transitions: list[list[str]]) -> dict:
        return {
            "models": [
                {
                    "model": "x_conflict_check",
                    "is_workflow": True,
                    "fields": [
                        {
                            "name": "x_status",
                            "ttype": "selection",
                            "selection": (
                                "[('pending','Pending'),('cleared','Cleared'),"
                                "('blocked','Blocked')]"
                            ),
                        }
                    ],
                    "state_field": {
                        "field": "x_status",
                        "states": ["pending", "cleared", "blocked"],
                        "statusbar_visible": ["pending", "cleared"],
                        "transitions": transitions,
                    },
                }
            ]
        }

    ok_score, ok_findings = _score_semantics(
        _conflict(
            [["pending", "cleared"], ["pending", "blocked"], ["blocked", "pending"]]
        )
    )
    assert not any("outgoing edge" in str(f.get("detail") or "") for f in ok_findings)
    assert ok_score >= 8.5

    bad_score, bad_findings = _score_semantics(
        _conflict([["pending", "cleared"], ["cleared", "pending"]])
    )
    assert any("outgoing edge" in str(f.get("detail") or "") for f in bad_findings)
    assert bad_score < ok_score


def test_confirm_one_inferred_keeps_sibling_pack_suggestions() -> None:
    prior_meta = [
        {
            "model": "project.task",
            "reason": "Internal deadlines",
            "source": "pack_reuse_stock",
            "confirmed": False,
            "link_only": True,
            "forbid_parallel": ["x_task"],
        },
        {
            "model": "account.analytic.line",
            "reason": "Billable hours",
            "source": "pack_reuse_stock",
            "confirmed": False,
            "link_only": True,
            "forbid_parallel": ["x_timesheet"],
        },
    ]
    after = plan_reuse(
        AOP_QUALITY_BRIEF,
        available_models=["res.partner"],
        installed_modules=["base", "contacts"],
        operator_reuse=["res.partner", "project.task"],
        pack_reuse_stock=[],
        prior_decisions=prior_meta,
    )
    pending = [
        d.model
        for d in after.decisions
        if d.source == "pack_reuse_stock" and not d.confirmed
    ]
    assert "project.task" not in pending
    assert "account.analytic.line" in pending


def test_collapse_unwraps_per_o2m_group_notebooks() -> None:
    from app.ai_enrich import collapse_header_o2ms_into_notebook

    draft = {
        "models": [
            {
                "model": "x_matter",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_party_ids",
                        "ttype": "one2many",
                        "relation": "x_matter_party",
                        "string": "Parties",
                    },
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_matter_line",
                        "string": "Billable time",
                    },
                ],
            },
            {
                "model": "x_matter_party",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_matter_id", "ttype": "many2one", "relation": "x_matter"},
                    {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
                    {"name": "x_role", "ttype": "char"},
                ],
            },
            {
                "model": "x_matter_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_matter_id", "ttype": "many2one", "relation": "x_matter"},
                    {"name": "x_hours", "ttype": "float"},
                    {"name": "x_amount", "ttype": "float"},
                ],
            },
        ],
        "views": [
            {
                "model": "x_matter",
                "type": "form",
                "arch": (
                    '<form string="Matter"><sheet>'
                    '<group string="Identity"><field name="x_name"/></group>'
                    '<group string="Parties"><notebook><page string="Parties">'
                    '<field name="x_party_ids"><list><field name="x_name"/></list></field>'
                    "</page></notebook></group>"
                    '<group string="Billable time"><notebook><page string="Billable time">'
                    '<field name="x_line_ids"><list><field name="x_name"/></list></field>'
                    "</page></notebook></group>"
                    "</sheet></form>"
                ),
            }
        ],
    }
    collapse_header_o2ms_into_notebook(draft)
    arch = str(draft["views"][0]["arch"])
    assert arch.lower().count("<notebook") == 1
    assert '<group string="Parties"><notebook>' not in arch
    assert 'page string="Parties"' in arch
    assert 'page string="Billable time"' in arch
    assert "x_partner_id" in arch
    assert "x_hours" in arch


def test_completeness_has_views_skips_inherit_hosts() -> None:
    from app.ai_rules import completeness_checklist

    items = {
        c["id"]: c
        for c in completeness_checklist(
            {
                "models": [
                    {
                        "model": "x_matter",
                        "mode": "new",
                        "fields": [{"name": "x_name", "ttype": "char"}],
                    },
                    {
                        "model": "calendar.event",
                        "mode": "inherit",
                        "fields": [
                            {
                                "name": "x_matter_id",
                                "ttype": "many2one",
                                "relation": "x_matter",
                            }
                        ],
                    },
                ],
                "views": [
                    {"model": "x_matter", "type": "list", "arch": "<list/>"},
                    {"model": "x_matter", "type": "form", "arch": "<form/>"},
                ],
                "menus": [{"name": "Matters"}],
            }
        )
        if isinstance(c, dict)
    }
    assert items["has_views"]["ok"] is True
    assert "calendar.event" not in str(items["has_views"].get("detail") or "")


def test_collapse_refreshes_thin_two_identity_column_lists() -> None:
    from app.ai_enrich import collapse_header_o2ms_into_notebook

    draft = {
        "models": [
            {
                "model": "x_job",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_job_line",
                        "string": "Lines",
                    },
                ],
            },
            {
                "model": "x_job_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_job_id", "ttype": "many2one", "relation": "x_job"},
                    {"name": "x_code", "ttype": "char"},
                    {
                        "name": "x_employee_id",
                        "ttype": "many2one",
                        "relation": "hr.employee",
                    },
                    {"name": "x_hours", "ttype": "float"},
                    {"name": "x_rate", "ttype": "float"},
                    {"name": "x_amount", "ttype": "float"},
                ],
            },
        ],
        "views": [
            {
                "model": "x_job",
                "type": "form",
                "arch": (
                    '<form string="Job"><sheet>'
                    '<group string="Identity"><field name="x_name"/></group>'
                    '<notebook><page string="Lines">'
                    '<field name="x_line_ids"><list>'
                    '<field name="x_code"/><field name="x_employee_id"/>'
                    '<field name="x_name"/>'
                    "</list></field></page></notebook>"
                    "</sheet></form>"
                ),
            }
        ],
    }
    collapse_header_o2ms_into_notebook(draft)
    arch = str(draft["views"][0]["arch"])
    assert "x_hours" in arch
    assert "x_rate" in arch
    assert "x_amount" in arch


def test_collapse_omits_related_stock_documents_from_header_form() -> None:
    from app.ai_enrich import collapse_header_o2ms_into_notebook

    draft = {
        "models": [
            {
                "model": "x_job",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_lead_id",
                        "ttype": "many2one",
                        "relation": "crm.lead",
                    },
                    {
                        "name": "x_analytic_account_id",
                        "ttype": "many2one",
                        "relation": "account.analytic.account",
                    },
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_job_line",
                    },
                ],
            },
            {
                "model": "x_job_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_job_id", "ttype": "many2one", "relation": "x_job"},
                ],
            },
        ],
        "views": [
            {
                "model": "x_job",
                "type": "form",
                "arch": (
                    '<form string="Job"><sheet>'
                    '<group string="Identity">'
                    '<field name="x_name"/><field name="x_lead_id"/>'
                    '<field name="x_analytic_account_id"/>'
                    "</group>"
                    '<notebook><page string="Lines">'
                    '<field name="x_line_ids"><list><field name="x_name"/></list></field>'
                    "</page></notebook></sheet></form>"
                ),
            }
        ],
    }
    collapse_header_o2ms_into_notebook(draft)
    arch = str(draft["views"][0]["arch"])
    assert 'name="x_lead_id"' not in arch
    assert 'name="x_analytic_account_id"' in arch
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_lead_id" in names


def test_stock_analytic_account_not_dropped_as_orphan() -> None:
    from app.ai_model_quality import repair_orphan_relations
    from app.ai_rules import check_referential_integrity

    draft = {
        "models": [
            {
                "model": "x_job",
                "fields": [
                    {
                        "name": "x_analytic_account_id",
                        "ttype": "many2one",
                        "relation": "account.analytic.account",
                    }
                ],
            }
        ],
    }
    repair_orphan_relations(draft)
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_analytic_account_id" in names
    assert not check_referential_integrity(draft)


def test_stock_relation_kept_without_reuse_list() -> None:
    from app.ai_model_quality import repair_orphan_relations

    draft = {
        "models": [
            {
                "model": "x_branch",
                "fields": [
                    {
                        "name": "x_warehouse_id",
                        "ttype": "many2one",
                        "relation": "stock.warehouse",
                    }
                ],
            }
        ],
    }
    repair_orphan_relations(draft)
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_warehouse_id" in names


def test_ensure_sequence_specs_skips_line_models() -> None:
    from app.ai_production_shape import ensure_sequence_specs

    draft = {
        "models": [
            {"model": "x_job", "fields": [{"name": "x_code", "ttype": "char"}]},
            {
                "model": "x_job_line",
                "fields": [
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "help": "Auto-numbered via ir.sequence (JOB/00001)",
                    }
                ],
            },
        ],
        "sequences": [
            {"model": "x_job_line", "prefix": "JOB/", "field": "x_code"},
        ],
    }
    ensure_sequence_specs(draft)
    models = {s["model"] for s in draft["sequences"]}
    assert "x_job" in models
    assert "x_job_line" not in models


def test_drop_invalid_skips_notebook_child_smart_buttons() -> None:
    from app.ai_odoo_app_bar import drop_invalid_smart_buttons

    draft = {
        "models": [
            {
                "model": "x_job",
                "fields": [
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_job_line",
                        "relation_field": "x_job_id",
                    },
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            },
            {
                "model": "x_job_line",
                "fields": [
                    {"name": "x_job_id", "ttype": "many2one", "relation": "x_job"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            },
            {
                "model": "sale.order",
                "mode": "inherit",
                "fields": [
                    {"name": "x_job_id", "ttype": "many2one", "relation": "x_job"},
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_job",
                "related_model": "x_job_line",
                "relation_field": "x_job_id",
            },
            {
                "on_model": "x_job",
                "related_model": "sale.order",
                "relation_field": "x_job_id",
            },
            {
                "on_model": "res.partner",
                "related_model": "x_job",
                "relation_field": "x_partner_id",
            },
            {
                "on_model": "res.partner",
                "related_model": "x_job_line",
                "relation_field": "x_partner_id",
            },
        ],
    }
    drop_invalid_smart_buttons(draft)
    targets = {
        (b["on_model"], b["related_model"]) for b in draft["smart_buttons"]
    }
    assert ("x_job", "x_job_line") not in targets
    assert ("x_job", "sale.order") in targets
    assert ("res.partner", "x_job") in targets
    assert ("res.partner", "x_job_line") not in targets


def test_line_parent_links_keep_work_date_not_header_geometry() -> None:
    from app.ai_post_critique import ensure_line_model_parent_links

    draft = {
        "models": [
            {
                "model": "x_job",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_open_date", "ttype": "date"},
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "relation": "res.company",
                    },
                ],
            },
            {
                "model": "x_job_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_job_id",
                        "ttype": "many2one",
                        "relation": "x_job",
                    },
                    {"name": "x_date", "ttype": "date"},
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "relation": "res.company",
                    },
                    {
                        "name": "x_from_branch_id",
                        "ttype": "many2one",
                        "relation": "x_branch",
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('billed','Billed')]",
                    },
                ],
            },
        ],
    }
    ensure_line_model_parent_links(draft)
    names = {f["name"] for f in draft["models"][1]["fields"]}
    assert "x_date" in names
    assert "x_company_id" in names
    assert "x_status" in names
    assert "x_from_branch_id" not in names


def test_embedded_line_columns_values_before_reference() -> None:
    from app.ai_enrich import _embedded_o2m_columns

    cols = _embedded_o2m_columns(
        {"relation": "x_job_line"},
        {
            "x_job_line": {
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_employee_id", "ttype": "many2one", "relation": "hr.employee"},
                    {"name": "x_code", "ttype": "char"},
                    {"name": "x_hours", "ttype": "float"},
                    {"name": "x_rate", "ttype": "float"},
                    {"name": "x_amount", "ttype": "float"},
                    {"name": "x_job_id", "ttype": "many2one", "relation": "x_job"},
                ]
            }
        },
    )
    assert cols.index("x_hours") < cols.index("x_code")
    assert cols.index("x_amount") < cols.index("x_code")
    assert "x_employee_id" in cols


def _line_billing_fields() -> list[dict]:
    return [
        {"name": "x_name", "ttype": "char", "string": "Narrative"},
        {
            "name": "x_job_id",
            "ttype": "many2one",
            "relation": "x_job",
            "string": "Job",
        },
        {"name": "x_hours", "ttype": "float", "string": "Hours"},
        {
            "name": "x_status",
            "ttype": "selection",
            "string": "Billing Status",
            "selection": "[('draft','Draft'),('billed','Billed')]",
        },
    ]


def test_line_form_arch_keeps_status_as_column_not_statusbar() -> None:
    from app.ai_enrich import _build_form_arch

    arch = _build_form_arch(
        "Job line",
        _line_billing_fields(),
        model_id="x_job_line",
    )
    assert 'widget="statusbar"' not in arch
    assert "<header>" not in arch.lower()
    assert "<chatter" not in arch.lower()
    assert 'name="x_status"' in arch


def test_line_models_are_not_mail_thread_documents() -> None:
    from app.ai_rules import apply_pattern_rules

    draft = {
        "technical_name": "job_ops",
        "display_name": "Job Ops",
        "models": [
            {
                "model": "x_job",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('open','Open')]",
                    },
                ],
            },
            {
                "model": "x_job_line",
                "mode": "new",
                "is_workflow": False,
                "mixins": [],
                "fields": _line_billing_fields(),
            },
        ],
    }
    apply_pattern_rules(draft)
    header = next(m for m in draft["models"] if m["model"] == "x_job")
    line = next(m for m in draft["models"] if m["model"] == "x_job_line")
    assert header.get("is_workflow") is True
    assert "mail.thread" in (header.get("mixins") or [])
    assert line.get("is_workflow") is not True
    assert "mail.thread" not in (line.get("mixins") or [])
    assert "mail.activity.mixin" not in (line.get("mixins") or [])


def test_closer_strips_line_form_statusbar_and_chatter() -> None:
    from app.ai_enrich import sync_form_archs_to_models
    from app.ai_odoo_app_bar import (
        close_odoo_architecture,
        demote_line_model_chrome,
        inject_chatter_on_forms,
        strip_register_form_headers,
    )

    dirty_arch = (
        '<form string="Job line">'
        '<header><field name="x_status" widget="statusbar"/></header>'
        "<sheet><group>"
        '<field name="x_name"/><field name="x_job_id"/>'
        '<field name="x_hours"/>'
        "</group></sheet><chatter/></form>"
    )
    draft = {
        "technical_name": "job_ops",
        "display_name": "Job Ops",
        "odoo_major": 19,
        "models": [
            {
                "model": "x_job",
                "description": "Job",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "relation": "x_job_line",
                        "relation_field": "x_job_id",
                    },
                ],
            },
            {
                "model": "x_job_line",
                "description": "Job line",
                "mode": "new",
                "is_workflow": False,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "fields": _line_billing_fields(),
            },
        ],
        "views": [
            {
                "name": "x_job_line.form",
                "model": "x_job_line",
                "type": "form",
                "arch": dirty_arch,
            }
        ],
    }
    demote_line_model_chrome(draft)
    sync_form_archs_to_models(draft)
    strip_register_form_headers(draft)
    inject_chatter_on_forms(draft)
    line = next(m for m in draft["models"] if m["model"] == "x_job_line")
    assert "mail.thread" not in (line.get("mixins") or [])
    form = next(
        v
        for v in draft["views"]
        if v.get("model") == "x_job_line" and v.get("type") == "form"
    )
    arch = str(form.get("arch") or "")
    assert 'widget="statusbar"' not in arch
    assert "<chatter" not in arch.lower()
    assert 'name="x_status"' in arch

    draft["views"][0]["arch"] = dirty_arch
    draft["models"][1]["mixins"] = ["mail.thread", "mail.activity.mixin"]
    close_odoo_architecture(draft, user_prompt="Job shop with billed time lines")
    form = next(
        v
        for v in draft["views"]
        if v.get("model") == "x_job_line" and v.get("type") == "form"
    )
    arch = str(form.get("arch") or "")
    assert 'widget="statusbar"' not in arch
    assert "<chatter" not in arch.lower()
    assert 'name="x_status"' in arch
    line = next(m for m in draft["models"] if m["model"] == "x_job_line")
    assert "mail.thread" not in (line.get("mixins") or [])

