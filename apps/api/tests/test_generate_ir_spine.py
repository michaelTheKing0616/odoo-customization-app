"""GenerateIR spine + IR trace + craft opt-in (handoff 2026-09-22)."""

from __future__ import annotations

from app.ai_generate_ir import (
    Proposal,
    build_ir,
    merge_proposals,
    proposal_allowed,
    stamp_generate_ir,
)
from app.ai_ir_trace import draft_ir_snapshot, ir_trace_enabled, trace_ir


def test_build_ir_stamps_draft() -> None:
    draft = {
        "display_name": "Maintenance Tickets",
        "technical_name": "x_maintenance_tickets",
        "grain": "full_app",
        "_user_prompt": "checklist lines and parts used, Draft→Done",
        "_understanding": {
            "must_do": [
                {"label": "State (Draft / Done)"},
                {"label": "O2M Checklist"},
                {"label": "O2M Parts used"},
            ]
        },
        "models": [
            {
                "model": "x_maintenance_tickets",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_checklist_ids",
                        "ttype": "one2many",
                        "relation": "x_checklist_line",
                    },
                ],
            }
        ],
    }
    ir = stamp_generate_ir(draft)
    assert draft["_generate_ir"]["display_name"] == "Maintenance Tickets"
    assert ir.o2ms and ir.o2ms[0]["name"] == "x_checklist_ids"
    assert "checklist" in " ".join(ir.cues.get("tokens") or [])


def test_merge_rejects_uncued_company() -> None:
    draft = {
        "models": [{"model": "x_ticket", "mode": "new", "fields": []}],
        "_understanding": {"must_do": ["State Draft→Done"]},
    }
    ir = build_ir(draft)
    prop = Proposal(
        kind="m2o",
        name="x_company_id",
        payload={"model": "x_ticket", "ttype": "many2one", "relation": "res.company"},
        source_cue=None,
        proposer="ai_depth",
    )
    ok, reason = proposal_allowed(prop, ir=ir)
    assert ok is False
    assert reason == "no_cue_or_craft"
    merge_proposals(ir, [prop], draft=draft)
    assert ir.rejected_proposals
    assert "x_company_id" not in {
        f.get("name") for f in ir.fields_by_model.get("x_ticket") or []
    }


def test_merge_allows_approved_craft_company() -> None:
    draft = {
        "models": [{"model": "x_ticket", "mode": "new", "fields": []}],
        "_approved_craft": {"company_scoping": True, "allow": ["x_company_id"]},
        "_understanding": {"must_do": []},
    }
    ir = build_ir(draft)
    prop = Proposal(
        kind="m2o",
        name="x_company_id",
        payload={
            "model": "x_ticket",
            "ttype": "many2one",
            "relation": "res.company",
            "craft_key": "company_scoping",
        },
        proposer="ai_depth",
    )
    merge_proposals(ir, [prop], draft=draft)
    names = {f.get("name") for f in ir.fields_by_model["x_ticket"]}
    assert "x_company_id" in names


def test_currency_ensurer_skips_without_money_cue() -> None:
    from app.ai_depth import _ensure_currency_on_amounts

    draft = {
        "_user_prompt": "Build Maintenance tickets: checklist and parts, Draft→Done",
        "models": [
            {
                "model": "x_ticket",
                "fields": [
                    {"name": "x_amount", "ttype": "float", "string": "Amount"},
                ],
            }
        ],
    }
    notes = _ensure_currency_on_amounts(draft)
    assert notes == []
    assert "x_currency_id" not in {
        f.get("name") for f in draft["models"][0]["fields"]
    }


def test_currency_ensurer_admits_with_money_slots_craft() -> None:
    """PR-C gate: money_slots=True admits currency when brief has no money cue."""
    from app.ai_depth import _ensure_currency_on_amounts

    draft = {
        "_user_prompt": "Build Maintenance tickets: checklist and parts, Draft→Done",
        "_approved_craft": {"money_slots": True},
        "models": [
            {
                "model": "x_ticket",
                "fields": [
                    {"name": "x_amount", "ttype": "float", "string": "Amount"},
                ],
            }
        ],
    }
    notes = _ensure_currency_on_amounts(draft)
    assert any("admitted" in n for n in notes)
    assert "x_currency_id" in {
        f.get("name") for f in draft["models"][0]["fields"]
    }


def test_seed_operational_loop_opt_in() -> None:
    from app.ai_depth import seed_operational_loop_models

    draft = {
        "grain": "full_app",
        "_user_prompt": "Maintenance tickets checklist parts",
        "models": [
            {
                "model": "x_maintenance_tickets",
                "description": "Maintenance Tickets",
                "mode": "new",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
    }
    notes = seed_operational_loop_models(draft, "comprehensive", user_prompt=draft["_user_prompt"])
    assert notes == []
    assert not any(
        isinstance(m, dict) and m.get("source") == "depth_seed"
        for m in draft["models"]
    )


def test_header_line_blocked_when_checklist_cued() -> None:
    from app.ai_odoo_app_bar import ensure_header_line_models

    draft = {
        "_user_prompt": (
            "Build Maintenance tickets: checklist lines with done flags, "
            "parts used (product + qty), state Draft→Done"
        ),
        "models": [
            {
                "model": "x_maintenance_tickets",
                "description": "Maintenance Tickets",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                ],
            }
        ],
    }
    notes = ensure_header_line_models(draft)
    assert notes == []
    assert not any(
        str(m.get("model") or "").endswith("_line") for m in draft["models"]
    )


def test_admit_and_apply_writes_craft_company() -> None:
    from app.ai_generate_ir import Proposal, admit_and_apply

    draft = {
        "models": [{"model": "x_ticket", "mode": "new", "fields": []}],
        "_approved_craft": {"company_scoping": True},
        "_understanding": {"must_do": []},
    }
    prop = Proposal(
        kind="m2o",
        name="x_company_id",
        payload={
            "model": "x_ticket",
            "ttype": "many2one",
            "relation": "res.company",
            "string": "Company",
            "craft_key": "company_scoping",
        },
        proposer="test",
    )
    ir, notes = admit_and_apply(draft, [prop])
    assert any("admitted" in n for n in notes)
    names = {f.get("name") for f in draft["models"][0]["fields"]}
    assert "x_company_id" in names
    assert ir.admitted


def test_admit_rejects_uncued_company_no_draft_write() -> None:
    from app.ai_generate_ir import Proposal, admit_and_apply

    draft = {
        "models": [{"model": "x_ticket", "mode": "new", "fields": []}],
        "_understanding": {"must_do": ["State Draft→Done"]},
        "_user_prompt": "checklist parts Draft→Done",
    }
    prop = Proposal(
        kind="m2o",
        name="x_company_id",
        payload={
            "model": "x_ticket",
            "ttype": "many2one",
            "relation": "res.company",
            "craft_key": "company_scoping",
        },
        proposer="test",
    )
    ir, _ = admit_and_apply(draft, [prop])
    assert ir.rejected_proposals
    assert draft["models"][0]["fields"] == []


def test_ir_trace_snapshot_shape() -> None:
    snap = draft_ir_snapshot(
        {
            "models": [
                {
                    "model": "x_a",
                    "fields": [{"name": "x_name", "ttype": "char"}],
                }
            ],
            "menus": [{"name": "A"}],
            "depends": ["base"],
        }
    )
    assert snap["models"][0]["model"] == "x_a"
    assert ir_trace_enabled() is False or isinstance(ir_trace_enabled(), bool)
    # When disabled, trace_ir still returns None but must not raise.
    assert trace_ir({"models": []}, stage="unit_test") is None


def test_enforce_purges_uncued_company_and_coerces_datetime() -> None:
    from app.ai_generate_ir_enforce import enforce_closed_generate_ir

    draft = {
        "_user_prompt": "Build tickets with checklist and parts, Draft→Done",
        "grain": "full_app",
        "models": [
            {
                "model": "x_tickets",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "relation": "res.company",
                    },
                    {
                        "name": "x_due",
                        "ttype": "datetime",
                        "string": "Due date",
                    },
                ],
            }
        ],
        "menus": [],
        "actions": [],
    }
    notes = enforce_closed_generate_ir(draft)
    names = {f.get("name") for f in draft["models"][0]["fields"]}
    assert "x_company_id" not in names
    due = next(f for f in draft["models"][0]["fields"] if f.get("name") == "x_due")
    assert due["ttype"] == "date"
    assert draft.get("_generate_ir_closure", {}).get("ok") is True or notes


def test_stock_inherit_bridge_admits_not_direct_mutate() -> None:
    from app.ai_odoo_app_bar import ensure_stock_inherit_bridges

    draft = {
        "_user_prompt": (
            "Work orders with smart button Quotations on sale.order "
            "and Related Sales Order link"
        ),
        "grain": "full_app",
        "depends": ["sale"],
        "models": [
            {
                "model": "x_work_order",
                "mode": "new",
                "is_workflow": True,
                "description": "Work Order",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "smart_buttons": [],
        "reuse": {"models": ["sale.order"]},
    }
    notes = ensure_stock_inherit_bridges(draft)
    sale = next((m for m in draft["models"] if m.get("model") == "sale.order"), None)
    # Either admitted inherit or gated off — never silent direct invent without IR.
    ir = draft.get("_generate_ir") or {}
    if sale is not None:
        assert any(
            str(r.get("name")) in {"sale.order", "x_work_order_id", "Quotations"}
            or "sale" in str(r.get("name") or "").lower()
            for r in (ir.get("admitted") or [])
        ), (notes, ir.get("admitted"), ir.get("rejected_proposals"))
        assert sale.get("mode") == "inherit"


def test_enrich_boundary_coerces_uncued_datetime() -> None:
    from app.ai_enrich import coerce_uncued_datetime_fields

    draft = {
        "_user_prompt": "Visitor log with visit date",
        "models": [
            {
                "model": "x_visitor",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_visit",
                        "ttype": "datetime",
                        "string": "Visit date",
                    },
                    {
                        "name": "x_slot",
                        "ttype": "datetime",
                        "string": "Scheduled slot",
                    },
                ],
            }
        ],
    }
    notes = coerce_uncued_datetime_fields(draft)
    by = {f["name"]: f for f in draft["models"][0]["fields"]}
    assert by["x_visit"]["ttype"] == "date"
    assert by["x_slot"]["ttype"] == "datetime"  # time cue in label
    assert any("x_visit" in n for n in notes)


def test_notebook_collapse_prefers_generate_ir_o2ms() -> None:
    from app.ai_enrich import collapse_header_o2ms_into_notebook

    draft = {
        "models": [
            {
                "model": "x_wo",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_checklist_ids",
                        "ttype": "one2many",
                        "relation": "x_wo_checklist_line",
                        "string": "Checklist",
                    },
                    {
                        "name": "x_orphan_ids",
                        "ttype": "one2many",
                        "relation": "x_wo_orphan",
                        "string": "Orphan",
                    },
                ],
            },
            {
                "model": "x_wo_checklist_line",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_wo_orphan",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
        ],
        "views": [
            {
                "model": "x_wo",
                "type": "form",
                "arch": (
                    "<form><sheet>"
                    '<group><field name="x_name"/>'
                    '<field name="x_checklist_ids"/>'
                    '<field name="x_orphan_ids"/>'
                    "</group></sheet></form>"
                ),
            }
        ],
        "_generate_ir": {
            "o2ms": [
                {
                    "name": "x_checklist_ids",
                    "on_model": "x_wo",
                    "relation": "x_wo_checklist_line",
                }
            ],
            "models": [{"model": "x_wo"}],
        },
    }
    collapse_header_o2ms_into_notebook(draft)
    arch = draft["views"][0]["arch"]
    assert "x_checklist_ids" in arch
    assert "notebook" in arch
    # Orphan O2M not admitted — must not get a notebook page (may linger in group).
    assert arch.count("<page") == 1


def test_seed_operational_via_propose_when_craft() -> None:
    from app.ai_depth import seed_operational_loop_models

    draft = {
        "grain": "full_app",
        "_user_prompt": "Law firm with party expense rate task and billing",
        "_approved_craft": {"depth_seeds": True},
        "models": [
            {
                "model": "x_matter",
                "description": "Matter",
                "mode": "new",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                ],
            }
        ],
    }
    notes = seed_operational_loop_models(
        draft, "comprehensive", user_prompt=draft["_user_prompt"]
    )
    seeded = [
        m
        for m in draft["models"]
        if isinstance(m, dict) and m.get("source") == "depth_seed"
    ]
    assert seeded, f"expected admitted depth_seed models; notes={notes}"
    ir = draft.get("_generate_ir") or {}
    admitted = {str(r.get("name")) for r in (ir.get("admitted") or [])}
    assert any(m["model"] in admitted for m in seeded)


def test_wire_stock_proposes_not_direct_mutate_without_cue() -> None:
    from app.ai_odoo_app_bar import wire_stock_apps_from_depends

    draft = {
        "_user_prompt": "Work orders online-honest on stock moves",
        "depends": ["purchase", "hr"],
        "models": [
            {
                "model": "x_work_order",
                "is_workflow": True,
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
    }
    wire_stock_apps_from_depends(draft)
    names = {f.get("name") for f in draft["models"][0]["fields"]}
    assert "x_purchase_order_id" not in names  # no PO cue — reject
    assert "x_employee_id" in names  # hr depend is a legal cue → admit


def test_purge_removes_uncued_company_spray() -> None:
    from app.ai_generate_ir_enforce import purge_unadmitted_spray
    from app.ai_odoo_app_bar import _scrub_mutate_enabled

    assert _scrub_mutate_enabled() is False
    draft = {
        "_user_prompt": "thin tickets Draft→Done",
        "_ambition": "thin",
        "_document_shape": "register",
        "grain": "full_app",
        "models": [
            {
                "model": "x_tickets",
                "mode": "new",
                "fields": [
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "relation": "res.company",
                    }
                ],
            }
        ],
        "_generate_ir": {"admitted": []},
    }
    notes = purge_unadmitted_spray(draft)
    assert notes
    assert draft["models"][0]["fields"] == []


def test_datetime_craft_upgrades_bare_date() -> None:
    from app.ai_field_ir import infer_date_or_datetime

    assert infer_date_or_datetime("Due date") == "date"
    draft = {"_approved_craft": {"datetime_over_date": True}}
    assert infer_date_or_datetime("Due date", draft=draft) == "datetime"


def test_menus_pruned_to_approved_models() -> None:
    from app.ai_generate_ir_enforce import prune_menus_to_approved_models

    draft = {
        "_ambition": "thin",
        "grain": "full_app",
        "display_name": "Tickets",
        "models": [
            {"model": "x_tickets", "mode": "new", "fields": []},
            {"model": "x_tickets_line", "mode": "new", "fields": []},
        ],
        "actions": [
            {"technical_name": "act_tickets", "model": "x_tickets"},
            {"technical_name": "act_line", "model": "x_tickets_line"},
        ],
        "menus": [
            {"name": "Tickets", "parent_xml_id": None, "action_xml_id": None},
            {"name": "All", "parent_xml_id": "root", "action_xml_id": "act_tickets"},
            {"name": "Lines", "parent_xml_id": "root", "action_xml_id": "act_line"},
            {"name": "Extra Root", "parent_xml_id": None, "action_xml_id": None},
        ],
    }
    notes = prune_menus_to_approved_models(draft)
    assert notes
    acts = {m.get("action_xml_id") for m in draft["menus"]}
    assert "act_line" not in acts
    roots = [
        m
        for m in draft["menus"]
        if isinstance(m, dict) and not m.get("parent_xml_id") and not m.get("action_xml_id")
    ]
    assert len(roots) == 1


def test_schema_verified_reuse_partner_m2o_with_cue() -> None:
    from app.ai_generate_ir import Proposal, admit_and_apply
    from app.ai_schema_client import FakeSchemaClient

    fake = FakeSchemaClient(
        models={"res.partner", "x_ticket"},
        fields={
            "x_ticket": {},
            "res.partner": {"name": {"ttype": "char", "readonly": False}},
        },
    )
    draft = {
        "_user_prompt": "Tickets with optional res.partner contact link",
        "_schema_client": fake,
        "models": [
            {
                "model": "x_ticket",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
    }
    ir, notes = admit_and_apply(
        draft,
        [
            Proposal(
                kind="m2o",
                name="x_partner_id",
                payload={
                    "model": "x_ticket",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "string": "Contact",
                },
                source_cue="res.partner",
                proposer="test",
            )
        ],
        schema_client=fake,
    )
    assert any(r.get("admit_reason") == "schema_verified_reuse" for r in ir.admitted)
    names = {f.get("name") for f in draft["models"][0]["fields"]}
    assert "x_partner_id" in names
    assert notes


def test_schema_verified_reuse_rejects_without_cue() -> None:
    from app.ai_generate_ir import Proposal, admit_and_apply
    from app.ai_schema_client import FakeSchemaClient

    fake = FakeSchemaClient(
        models={"res.partner", "x_ticket"},
        fields={"x_ticket": {}, "res.partner": {}},
    )
    draft = {
        "_user_prompt": "Thin tickets Draft→Done only",
        "_schema_client": fake,
        "models": [
            {
                "model": "x_ticket",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
    }
    ir, _notes = admit_and_apply(
        draft,
        [
            Proposal(
                kind="m2o",
                name="x_partner_id",
                payload={
                    "model": "x_ticket",
                    "ttype": "many2one",
                    "relation": "res.partner",
                },
                source_cue=None,
                proposer="test",
            )
        ],
        schema_client=fake,
    )
    assert all(r.get("name") != "x_partner_id" for r in ir.admitted)
    assert any(
        r.get("name") == "x_partner_id" and r.get("reject_reason") == "no_cue_or_craft"
        for r in ir.rejected_proposals
    )


def test_named_rate_line_invent_rejected_without_o2m_cue() -> None:
    """Historical live failure: maintenance/service lexical ≠ invent Rate Line O2M."""
    from app.ai_generate_ir import Proposal, admit_and_apply

    draft = {
        "_user_prompt": (
            "Build Maintenance tickets for a service desk: "
            "State Draft→Done; Online-honest on stock moves."
        ),
        "models": [
            {
                "model": "x_maintenance_tickets",
                "mode": "new",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "_understanding": {
            "constraint_ast": {"fields": [], "o2ms": [], "states": ["draft", "done"]}
        },
    }
    ir, _notes = admit_and_apply(
        draft,
        [
            Proposal(
                kind="o2m",
                name="x_rate_line_ids",
                payload={
                    "model": "x_maintenance_tickets",
                    "ttype": "one2many",
                    "relation": "x_maintenance_tickets_line",
                    "relation_field": "x_maintenance_tickets_id",
                    "string": "Rate Line",
                    "line_model": {
                        "model": "x_maintenance_tickets_line",
                        "description": "Rate Line",
                        "mode": "new",
                        "fields": [
                            {"name": "x_name", "ttype": "char"},
                            {
                                "name": "x_maintenance_tickets_id",
                                "ttype": "many2one",
                                "relation": "x_maintenance_tickets",
                            },
                        ],
                    },
                },
                source_cue="service",
                proposer="test.rate_line_regress",
            )
        ],
    )
    assert any(
        r.get("name") == "x_rate_line_ids"
        and r.get("reject_reason") == "uncued_line_invent"
        for r in ir.rejected_proposals
    ), ir.rejected_proposals
    assert not any(
        m.get("model") == "x_maintenance_tickets_line" for m in draft["models"]
    )
