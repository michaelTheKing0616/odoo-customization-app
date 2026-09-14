"""Law-firm pack — stock-first matter file (generation-path)."""

from __future__ import annotations

from app.ai_domain_pack_law_firm import law_firm_pack, scaffold_teaching_blob
from app.ai_domain_packs import merge_domain_pack, retrieve_domain_pack_lexical
from app.ai_model_quality import MODEL_CREATION_RULES, few_shot_exemplar_json


_CUSTOM = {
    "x_matter",
    "x_matter_party",
    "x_matter_line",
    "x_conflict_check",
    "x_matter_document",
}
_INHERIT = {
    "calendar.event",
    "hr.employee",
    "sale.order",
    "account.move",
    "crm.lead",
    "project.task",
}


def test_law_firm_pack_is_stock_first_matter_file() -> None:
    pack = law_firm_pack()
    ids = {m["model"] for m in pack["models"] if isinstance(m, dict)}
    assert ids == _CUSTOM | _INHERIT
    assert "x_attorney" not in ids
    assert "x_bill" not in ids
    assert "x_deposit" not in ids
    assert "x_task" not in ids
    assert "x_event" not in ids
    assert "x_document" not in ids
    assert "sale" in pack["depends"]
    assert "account" in pack["depends"]
    assert "hr" in pack["depends"]
    assert pack.get("multi_company") is False
    matter = next(m for m in pack["models"] if m["model"] == "x_matter")
    emp = next(f for f in matter["fields"] if f["name"] == "x_employee_id")
    assert emp["relation"] == "hr.employee"
    partner = next(f for f in matter["fields"] if f["name"] == "x_partner_id")
    assert partner["relation"] == "res.partner"
    invoice = next(f for f in matter["fields"] if f["name"] == "x_invoice_id")
    assert invoice["relation"] == "account.move"
    status = next(f for f in matter["fields"] if f["name"] == "x_status")
    assert "intake" in status["selection"]
    assert "billed" in status["selection"]
    assert "closed" in status["selection"]
    assert "discovery" not in status["selection"]
    line = next(m for m in pack["models"] if m["model"] == "x_matter_line")
    fee = next(f for f in line["fields"] if f["name"] == "x_employee_id")
    assert fee["relation"] == "hr.employee"
    forbidden = {row["model"] for row in pack["reuse_stock"]}
    assert "account.move" in forbidden
    assert "hr.employee" in forbidden
    so = next(m for m in pack["models"] if m["model"] == "sale.order")
    assert so.get("mode") == "inherit"
    assert any(f.get("name") == "x_matter_id" for f in so["fields"])
    buttons = {
        (b.get("on_model"), b.get("related_model"), b.get("relation_field"))
        for b in pack["smart_buttons"]
    }
    assert ("x_matter", "sale.order", "x_matter_id") in buttons
    assert ("x_matter", "x_conflict_check", "x_matter_id") not in buttons
    assert ("x_matter", "x_matter_line", "x_matter_id") not in buttons
    menus = {m.get("name") for m in pack["menus"]}
    assert {"Matters", "Parties", "Time", "Conflicts", "Documents"} <= menus


def test_retrieve_law_firm_from_prompt() -> None:
    hit = retrieve_domain_pack_lexical(
        "Build a world-class law firm practice management app with matters and retainers"
    )
    assert hit is not None
    pack_id, pack, score = hit
    assert pack_id == "law_firm"
    assert score >= 0.08
    assert (pack.get("_retrieval") or {}).get("method") == "regex"
    assert pack.get("domain_pack") == "law_firm"


def test_scaffold_teaching_blob_has_field_depth() -> None:
    blob = scaffold_teaching_blob(law_firm_pack())
    assert "stock" in blob.lower() or "hr.employee" in blob
    assert "x_matter" in blob
    assert "x_conflict_check" in blob
    assert "x_matter_document" in blob
    assert "selection" in blob
    assert "x_attorney" not in blob or "Do NOT add x_attorney" in blob
    assert "('litigation'" in blob or "litigation" in blob
    assert "('specialty_a'" not in blob


def test_merge_deepens_thin_llm_matter() -> None:
    thin = {
        "models": [
            {
                "model": "x_matter",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            }
        ]
    }
    merged, notes = merge_domain_pack(thin, law_firm_pack())
    matter = next(m for m in merged["models"] if m["model"] == "x_matter")
    names = {f.get("name") for f in matter["fields"]}
    assert "x_status" in names
    assert "x_employee_id" in names
    emp = next(f for f in matter["fields"] if f["name"] == "x_employee_id")
    assert emp["relation"] == "hr.employee"
    assert any("domain pack added field" in n for n in notes)
    ids = {m["model"] for m in merged["models"]}
    assert "x_matter_party" in ids
    assert "x_bill" not in ids
    assert "x_attorney" not in ids


def test_staff_remap_party_demote_and_selection_upgrade() -> None:
    from app.ai_domain_packs import law_firm_pack, merge_domain_pack
    from app.ai_model_quality import repair_draft_integrity

    thin = {
        "models": [
            {
                "model": "x_matter",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('intake','Intake'),('open','Open'),('trial','Trial')]"
                        ),
                    },
                ],
            }
        ]
    }
    merged, warnings = merge_domain_pack(thin, law_firm_pack())
    assert any("upgraded selection x_matter.x_status" in w for w in warnings)
    assert any("domain pack added model x_matter_party" in w for w in warnings)

    draft = {
        "models": [
            {
                "model": "x_attorney",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_user_id",
                        "ttype": "many2one",
                        "relation": "res.users",
                    },
                ],
            },
            {
                "model": "x_matter",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('intake','Intake'),('open','Open'),"
                            "('closed','Closed')]"
                        ),
                    },
                ],
            },
            {
                "model": "x_matter_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_attorney_id",
                        "ttype": "many2one",
                        "relation": "res.users",
                        "string": "Fee Earner",
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                ],
            },
            {
                "model": "x_matter_party",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('draft','Draft'),('open','Open'),"
                            "('done','Done'),('cancelled','Cancelled')]"
                        ),
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                ],
            },
            {
                "model": "x_document",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                ],
            },
        ],
        "automations": [
            {
                "name": "Activity before limitation date",
                "model": "x_matter",
                "filter_domain": "[('x_status', 'not in', ['closed'])]",
                "safe_actions": [{"kind": "next_activity", "summary": "Limitation"}],
            }
        ],
        "views": [
            {
                "name": "x_matter_party.kanban",
                "model": "x_matter_party",
                "type": "kanban",
                "arch": "<kanban/>",
            }
        ],
        "actions": [
            {
                "model": "x_matter_party",
                "view_mode": "list,kanban,form",
                "technical_name": "action_x_matter_party",
            }
        ],
    }
    notes = repair_draft_integrity(draft, ambition="comprehensive")
    line = next(m for m in draft["models"] if m["model"] == "x_matter_line")
    att = next(f for f in line["fields"] if f["name"] == "x_attorney_id")
    assert att["relation"] in {"x_attorney", "hr.employee"}
    party = next(m for m in draft["models"] if m["model"] == "x_matter_party")
    assert party.get("is_workflow") is False
    assert not any(
        v.get("type") == "kanban" and v.get("model") == "x_matter_party"
        for v in draft["views"]
    )
    doc = next(m for m in draft["models"] if m["model"] == "x_document")
    assert next(f for f in doc["fields"] if f["name"] == "x_name").get("required")
    auto = draft["automations"][0]
    # closed is valid on this matter — domain kept
    assert "closed" in str(auto.get("filter_domain") or "")
    assert any("remapped" in n for n in notes)
    assert any("demoted link" in n for n in notes)


def test_merge_fixes_users_fee_earner_and_terminal_status() -> None:
    from app.ai_domain_packs import law_firm_pack, merge_domain_pack
    from app.ai_model_quality import repair_draft_integrity

    draft = {
        "models": [
            {
                "model": "x_matter",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('intake','Intake'),('open','Open'),"
                            "('discovery','Discovery'),('trial','Trial')]"
                        ),
                        "required": True,
                    },
                ],
            },
            {
                "model": "x_matter_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_attorney_id",
                        "ttype": "many2one",
                        "relation": "res.users",
                        "string": "Fee Earner",
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                ],
            },
            {
                "model": "x_event",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_attorney_id",
                        "ttype": "many2one",
                        "relation": "res.users",
                        "string": "Appearing Counsel",
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                ],
            },
            {
                "model": "x_document",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                ],
            },
            {
                "model": "x_matter_party",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('draft','Draft'),('open','Open'),"
                            "('done','Done'),('cancelled','Cancelled')]"
                        ),
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                ],
            },
        ],
        "automations": [
            {
                "name": "Activity before limitation date",
                "model": "x_matter",
                "filter_domain": "[('x_status', 'not in', ['closed'])]",
                "safe_actions": [{"kind": "next_activity", "summary": "Limitation"}],
            }
        ],
        "views": [],
        "actions": [],
    }
    merged, warnings = merge_domain_pack(draft, law_firm_pack())
    assert any("upgraded selection x_matter.x_status" in w for w in warnings)
    line = next(m for m in merged["models"] if m["model"] == "x_matter_line")
    names = {f.get("name") for f in line["fields"]}
    assert "x_employee_id" in names
    emp = next(f for f in line["fields"] if f["name"] == "x_employee_id")
    assert emp["relation"] == "hr.employee"
    notes = repair_draft_integrity(merged, ambition="comprehensive")
    matter = next(m for m in merged["models"] if m["model"] == "x_matter")
    status = next(f for f in matter["fields"] if f["name"] == "x_status")
    assert "closed" in status["selection"]
    assert "billed" in status["selection"]
    party = next(m for m in merged["models"] if m["model"] == "x_matter_party")
    assert party.get("is_workflow") is False
    ids = {m["model"] for m in merged["models"]}
    assert "x_attorney" not in ids
    assert "x_bill" not in ids
    _ = notes, warnings


def test_reenrich_does_not_reworkflow_matter_party() -> None:
    """Post-critique enrich+rules must not re-promote party links to workflow/kanban."""
    from app.ai_enrich import enrich_draft_module_spec
    from app.ai_model_quality import repair_draft_integrity
    from app.ai_rules import validate_and_enrich_draft

    draft = {
        "technical_name": "law_firm",
        "display_name": "Law Firm",
        "models": [
            {
                "model": "x_matter",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('intake','Intake'),('open','Open'),('closed','Closed')]"
                        ),
                    },
                ],
            },
            {
                "model": "x_matter_party",
                "is_workflow": True,
                "description": "Matter Party / Role",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('draft','Draft'),('open','Open'),"
                            "('done','Done'),('cancelled','Cancelled')]"
                        ),
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                ],
            },
        ],
        "views": [
            {
                "name": "x_matter_party.kanban",
                "model": "x_matter_party",
                "type": "kanban",
                "arch": "<kanban/>",
            }
        ],
        "actions": [
            {
                "name": "Matter Party / Role",
                "model": "x_matter_party",
                "view_mode": "list,kanban,form",
            }
        ],
    }
    repair_draft_integrity(draft)
    draft, enrich_w = enrich_draft_module_spec(draft)
    draft, rule_w, _ = validate_and_enrich_draft(draft)
    repair_draft_integrity(draft)

    party = next(m for m in draft["models"] if m["model"] == "x_matter_party")
    assert party.get("is_workflow") is False
    assert not any(
        v.get("type") == "kanban" and v.get("model") == "x_matter_party"
        for v in draft.get("views") or []
    )
    action = next(a for a in draft["actions"] if a.get("model") == "x_matter_party")
    assert "kanban" not in str(action.get("view_mode") or "")
    _ = enrich_w, rule_w


def test_merge_prefers_pack_lifecycle_over_longer_llm_status() -> None:
    """LLM discovery/trial must not beat pack intake → open → billed → closed."""
    from app.ai_domain_packs import law_firm_pack, merge_domain_pack

    draft = {
        "models": [
            {
                "model": "x_matter",
                "is_workflow": True,
                "description": "Case record",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('intake','Intake'),('conflict_check','Conflict check'),"
                            "('open','Open'),('discovery','Discovery'),('trial','Trial'),"
                            "('settlement','Settlement'),('closed','Closed'),"
                            "('on_hold','On hold')]"
                        ),
                    },
                    {
                        "name": "x_attorney_id",
                        "ttype": "many2one",
                        "relation": "x_attorney",
                    },
                ],
                "state_field": {
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
                    "transitions": [["open", "intake"]],
                },
            }
        ]
    }
    merged, warnings = merge_domain_pack(draft, law_firm_pack())
    matter = next(m for m in merged["models"] if m["model"] == "x_matter")
    status = next(f for f in matter["fields"] if f["name"] == "x_status")
    assert "billed" in str(status.get("selection") or "")
    assert "discovery" not in str(status.get("selection") or "")
    assert matter.get("state_field", {}).get("states") == [
        "intake",
        "open",
        "billed",
        "on_hold",
        "closed",
    ]
    assert any(f.get("name") == "x_employee_id" for f in matter["fields"])
    assert any("upgraded selection x_matter.x_status" in w for w in warnings)
    assert any("restored state_field x_matter" in w for w in warnings)


def test_seed_core_scaffold_does_not_inject_parallel_billing() -> None:
    """Law-firm pack residual is matter/party/line — not a second invoice app."""
    from app.ai_domain_packs import law_firm_pack, merge_domain_pack
    from app.ai_model_quality import seed_missing_core_scaffold_models

    pack = law_firm_pack()
    draft: dict = {
        "models": [
            {
                "model": "x_matter",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ]
    }
    draft, seed_notes = seed_missing_core_scaffold_models(draft, pack)
    assert not any("x_bill" in n for n in seed_notes)
    assert not any("x_attorney" in n for n in seed_notes)
    merged, warnings = merge_domain_pack(draft, pack)
    core_gaps = [
        w
        for w in warnings
        if "generation gap" in w.lower()
        and any(k in w.lower() for k in ("attorney", "bill", "compliance", "deposit", "trust"))
    ]
    assert core_gaps == []
    ids = {m["model"] for m in merged["models"]}
    assert ids >= {"x_matter", "x_matter_party", "x_matter_line", "x_conflict_check", "x_matter_document"}
    assert "sale.order" in ids
    assert "x_bill" not in ids
    assert "x_attorney" not in ids


def test_creation_rules_and_few_shot_teach_excellence() -> None:
    assert "WORLD-CLASS OPS DEPTH" in MODEL_CREATION_RULES
    assert "specialty_a" in MODEL_CREATION_RULES or "placeholders" in MODEL_CREATION_RULES
    blob = few_shot_exemplar_json()
    assert "x_ex_party" in blob
    assert "x_ex_deposit" in blob
    assert "x_ex_event" in blob
    assert "held" in blob or "retainer" in blob.lower() or "Held" in blob
