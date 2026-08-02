"""Generation-path model quality (collapse hollow catalogs, rules present)."""

from __future__ import annotations

from app.ai_model_quality import (
    MODEL_CREATION_RULES,
    collapse_hollow_catalogs_to_selections,
    few_shot_exemplar_json,
    min_fields_for_ambition,
)
from app.ai_ollama import _SYSTEM_PROMPT


def test_system_prompt_prioritizes_model_creation_quality() -> None:
    assert "MODEL CREATION QUALITY" in _SYSTEM_PROMPT
    assert "hollow" in _SYSTEM_PROMPT.lower() or "NEVER create separate models" in MODEL_CREATION_RULES
    assert "selection" in MODEL_CREATION_RULES.lower()


def test_few_shot_exemplar_has_substantive_models() -> None:
    blob = few_shot_exemplar_json()
    assert "x_ex_job" in blob
    assert "RENAME" in blob
    assert min_fields_for_ambition("comprehensive", workflow=True) >= 7


def test_repair_orphan_resource_remaps_to_attorney() -> None:
    from app.ai_model_quality import repair_orphan_relations
    from app.ai_rules import check_referential_integrity

    draft = {
        "models": [
            {
                "model": "x_attorney",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_matter_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_resource_id",
                        "ttype": "many2one",
                        "relation": "x_resource",
                    },
                ],
            },
        ]
    }
    notes = repair_orphan_relations(draft)
    assert any("remapped" in n for n in notes)
    field = draft["models"][1]["fields"][1]
    assert field["relation"] == "x_attorney"
    assert not check_referential_integrity(draft)


def test_normalize_broken_smart_button_and_purge_ghost() -> None:
    from app.ai_model_quality import repair_draft_integrity

    draft = {
        "_ambition": "comprehensive",
        "models": [
            {
                "model": "x_matter",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                    {"name": "x_due_date", "ttype": "date"},
                ],
            },
            {
                "model": "x_matter_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                    {"name": "x_date", "ttype": "date"},
                ],
            },
            {
                "model": "x_task",
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
        "smart_buttons": [
            {
                "model": "x_matter",
                "button_name": "Add Matter Line",
                "relation_field": "x_matter_id",
            }
        ],
        "automations": [
            {
                "trigger": "on_create_or_write",
                "model": "x_matter",
                "action": "object_write",
                "fields": ["x_status"],
            }
        ],
        "actions": [
            {"name": "Ghost", "model": "x_specialty", "technical_name": "action_x_specialty"},
            {"name": "Matter", "model": "x_matter", "technical_name": "action_x_matter"},
        ],
        "menus": [
            {
                "name": "Specialty",
                "action_xml_id": "action_x_specialty",
                "technical_name": "menu_x_specialty",
            }
        ],
        "views": [{"name": "x_specialty.list", "model": "x_specialty", "type": "list"}],
    }
    notes = repair_draft_integrity(draft, ambition="comprehensive")
    assert any("normalized smart_button" in n for n in notes)
    assert draft["smart_buttons"][0]["on_model"] == "x_matter"
    assert draft["smart_buttons"][0]["related_model"] == "x_matter_line"
    assert not any(a.get("model") == "x_specialty" for a in draft["actions"])
    assert not any(m.get("technical_name") == "menu_x_specialty" for m in draft["menus"])
    # Incomplete automation without value dropped
    assert not any(
        a.get("action") == "object_write" for a in draft["automations"] if isinstance(a, dict)
    )
    # Workflows promoted toward floor
    workflows = sum(1 for m in draft["models"] if m.get("is_workflow") or any(
        isinstance(f, dict) and f.get("name") == "x_status" for f in (m.get("fields") or [])
    ))
    assert workflows >= 3


def test_collapse_hollow_catalogs_rewrites_parent_m2o() -> None:
    draft = {
        "models": [
            {
                "model": "x_case",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_type_id",
                        "ttype": "many2one",
                        "relation": "x_case_type",
                        "string": "Type",
                    },
                    {
                        "name": "x_tag_ids",
                        "ttype": "many2many",
                        "relation": "x_case_tag",
                        "string": "Tags",
                    },
                ],
            },
            {
                "model": "x_case_type",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_code", "ttype": "char"},
                ],
            },
            {
                "model": "x_case_tag",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_code", "ttype": "char"},
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_case_type",
                "related_model": "x_case",
                "relation_field": "x_type_id",
            }
        ],
    }
    notes = collapse_hollow_catalogs_to_selections(draft)
    assert notes
    models = {m["model"] for m in draft["models"]}
    assert "x_case_type" not in models
    assert "x_case_tag" not in models
    assert "x_case" in models
    case_fields = {f["name"]: f for f in draft["models"][0]["fields"]}
    assert case_fields["x_type"]["ttype"] == "selection"
    assert case_fields["x_tag_ids"]["ttype"] == "char"
    assert not any(b.get("on_model") == "x_case_type" for b in draft["smart_buttons"])


def test_dedupe_fields_and_infer_relations() -> None:
    from app.ai_model_quality import repair_draft_integrity

    draft = {
        "models": [
            {
                "model": "x_attorney",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_practice_area",
                        "ttype": "selection",
                        "selection": "[('a','A')]",
                    },
                    {
                        "name": "x_practice_area",
                        "ttype": "selection",
                        "selection": "[('a','A'),('b','B'),('c','C')]",
                        "required": True,
                    },
                ],
            },
            {
                "model": "x_bill",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_lines_ids", "ttype": "one2many", "string": "Lines"},
                ],
            },
            {
                "model": "x_matter_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_bill_id", "ttype": "many2one", "string": "Bill"},
                ],
            },
        ],
        "smart_buttons": [
            {
                "model_name": "x_bill",
                "button_name": "Open Lines",
                "action_type": "server_action",
                "icon": "fa-folder-open",
            }
        ],
    }
    notes = repair_draft_integrity(draft, ambition="standard")
    attorney = next(m for m in draft["models"] if m["model"] == "x_attorney")
    areas = [f for f in attorney["fields"] if f.get("name") == "x_practice_area"]
    assert len(areas) == 1
    assert "('c','C')" in str(areas[0].get("selection"))
    line = next(m for m in draft["models"] if m["model"] == "x_matter_line")
    bill_f = next(f for f in line["fields"] if f["name"] == "x_bill_id")
    assert bill_f["relation"] == "x_bill"
    bill = next(m for m in draft["models"] if m["model"] == "x_bill")
    o2m = next(f for f in bill["fields"] if f["name"] == "x_lines_ids")
    assert o2m["relation"] == "x_matter_line"
    assert o2m["relation_field"] == "x_bill_id"
    assert draft["smart_buttons"][0]["related_model"] == "x_matter_line"
    assert any("deduped duplicate field" in n for n in notes)


def test_collapse_hearing_event_duplicates() -> None:
    from app.ai_model_quality import collapse_duplicate_role_models

    draft = {
        "models": [
            {
                "model": "x_hearing",
                "fields": [
                    {"name": "x_name"},
                    {"name": "x_matter_id", "ttype": "many2one", "relation": "x_matter"},
                    {"name": "x_date"},
                ],
            },
            {
                "model": "x_event",
                "fields": [
                    {"name": "x_name"},
                    {"name": "x_matter_id", "ttype": "many2one", "relation": "x_matter"},
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_matter",
                "related_model": "x_event",
                "relation_field": "x_matter_id",
            }
        ],
    }
    notes = collapse_duplicate_role_models(draft)
    ids = {m["model"] for m in draft["models"]}
    assert "x_hearing" in ids
    assert "x_event" not in ids
    assert any("merged duplicate role" in n for n in notes)


def test_normalize_client_id_to_partner_and_rebuild_view() -> None:
    from app.ai_enrich import ensure_default_ui
    from app.ai_model_quality import repair_draft_integrity

    draft = {
        "technical_name": "law_firm_management",
        "display_name": "Law Firm Management",
        "models": [
            {
                "model": "x_matter",
                "is_workflow": True,
                "description": "Matter / Case",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection", "selection": "[('open','Open')]"},
                    {
                        "name": "x_client_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Client",
                    },
                ],
            },
            {
                "model": "x_event",
                "mode": "new",
                "description": "Event",
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
        "actions": [
            {
                "name": "Matter",
                "model": "x_matter",
                "technical_name": "action_x_matter",
                "view_mode": "list,form",
            }
        ],
        "menus": [
            {
                "name": "Root",
                "xml_id": "menu_root_law_firm_management",
                "technical_name": "root_law_firm_management",
            },
            {
                "name": "Matter",
                "action_xml_id": "action_x_matter",
                "parent_xml_id": "menu_root_law_firm_management",
                "technical_name": "menu_x_matter",
            },
        ],
        "views": [
            {
                "name": "x_matter.list",
                "model": "x_matter",
                "type": "list",
                "arch": '<list><field name="x_name"/><field name="x_client_id"/></list>',
            }
        ],
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "related_model": "x_matter",
                "relation_field": "x_client_id",
                "label": "Matters",
            }
        ],
        "access_rules": [],
    }
    notes = repair_draft_integrity(draft, ambition="standard")
    matter = next(m for m in draft["models"] if m["model"] == "x_matter")
    names = {f["name"] for f in matter["fields"]}
    assert "x_partner_id" in names
    assert "x_client_id" not in names
    assert draft["smart_buttons"][0]["relation_field"] == "x_partner_id"
    assert any("normalized partner" in n for n in notes)

    warnings = ensure_default_ui(draft)
    action_models = {a["model"] for a in draft["actions"]}
    assert "x_event" in action_models
    menu_actions = {m.get("action_xml_id") for m in draft["menus"]}
    assert "action_x_event" in menu_actions
    matter_view = next(v for v in draft["views"] if v["model"] == "x_matter")
    assert "x_partner_id" in matter_view["arch"]
    assert "x_client_id" not in matter_view["arch"]
    assert any("action(s) for seeded" in w or "menu(s) for seeded" in w for w in warnings)


def test_filter_redundant_missing_models_skips_second_invoice() -> None:
    from app.ai_model_quality import filter_redundant_missing_models

    draft = {
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
            },
            {
                "model": "x_bill",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
        ]
    }
    missing = [
        {"model": "x_invoice", "fields": [{"name": "x_name"}]},
        {"model": "x_client", "fields": [{"name": "x_name"}]},
        {
            "model": "x_hearing",
            "fields": [
                {"name": "x_name"},
                {"name": "x_matter_id", "ttype": "many2one", "relation": "x_matter"},
                {"name": "x_date", "ttype": "date"},
                {"name": "x_location", "ttype": "char"},
            ],
        },
    ]
    kept = filter_redundant_missing_models(draft, missing)
    ids = {m["model"] for m in kept}
    assert "x_hearing" in ids
    assert "x_invoice" not in ids
    assert "x_client" not in ids


def test_fill_o2m_relation_field_and_dedupe_duplicate_child() -> None:
    from app.ai_model_quality import repair_incomplete_relational_fields

    draft = {
        "models": [
            {
                "model": "x_matter",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_hearing_ids",
                        "ttype": "one2many",
                        "relation": "x_event",
                        "string": "Hearings",
                    },
                    {
                        "name": "x_event_ids",
                        "ttype": "one2many",
                        "relation": "x_event",
                        "string": "Events",
                    },
                ],
            },
            {
                "model": "x_event",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                ],
            },
        ]
    }
    notes = repair_incomplete_relational_fields(draft)
    matter = draft["models"][0]
    o2ms = [f for f in matter["fields"] if f.get("ttype") == "one2many"]
    assert len(o2ms) == 1
    assert o2ms[0]["relation_field"] == "x_matter_id"
    assert any("filled relation_field" in n or "duplicate O2M" in n for n in notes)


def test_scrub_bad_related_writes_and_dedupe_next_activity() -> None:
    from app.ai_model_quality import (
        dedupe_automation_safe_actions,
        scrub_invalid_related_writes,
    )

    draft = {
        "models": [
            {
                "model": "x_matter",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_hearing_ids",
                        "ttype": "one2many",
                        "relation": "x_event",
                        "relation_field": "x_matter_id",
                    },
                    {
                        "name": "x_attorney_id",
                        "ttype": "many2one",
                        "relation": "x_attorney",
                    },
                ],
            },
            {
                "model": "x_attorney",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_rate_id",
                        "ttype": "many2one",
                        "relation": "x_rate",
                    },
                ],
            },
            {
                "model": "x_rate",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_event",
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
                "name": "Flag overdue",
                "model": "x_matter",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Flag overdue"},
                    {"kind": "next_activity", "summary": "Overdue follow-up"},
                ],
            },
            {
                "name": "Bad hearing write",
                "model": "x_matter",
                "safe_actions": [
                    {
                        "kind": "related_write",
                        "relation_field": "x_hearing_ids",
                        "field": "x_status",
                        "value": "in_progress",
                    }
                ],
            },
            {
                "name": "Bad rate write",
                "model": "x_matter",
                "safe_actions": [
                    {
                        "kind": "related_write",
                        "relation_field": "x_attorney_id",
                        "field": "x_rate_id",
                        "value": "default",
                    }
                ],
            },
        ],
    }
    notes = scrub_invalid_related_writes(draft)
    notes.extend(dedupe_automation_safe_actions(draft))
    names = {a["name"] for a in draft["automations"]}
    assert "Bad hearing write" not in names
    assert "Bad rate write" not in names
    overdue = next(a for a in draft["automations"] if a["name"] == "Flag overdue")
    assert len(overdue["safe_actions"]) == 1
    assert any("dropped related_write" in n for n in notes)


def test_cap_partner_buttons_and_scrub_rnt_help() -> None:
    from app.ai_model_quality import (
        cap_partner_smart_buttons,
        scrub_exemplar_help_text,
    )

    draft = {
        "models": [
            {
                "model": "x_matter",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            },
            {
                "model": "x_bill",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            },
            {
                "model": "x_matter_line",
                "fields": [
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "help": "Sequence / reference code (e.g. RNT/00001) — wire ir.sequence later",
                    },
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            },
            {
                "model": "x_event",
                "source": "depth_seed",
                "fields": [
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    }
                ],
            },
            {
                "model": "x_task",
                "source": "depth_seed",
                "fields": [
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    }
                ],
            },
            {
                "model": "x_expense",
                "source": "depth_seed",
                "fields": [
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    }
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "related_model": mid,
                "relation_field": "x_partner_id",
                "label": mid,
            }
            for mid in (
                "x_matter",
                "x_bill",
                "x_matter_line",
                "x_event",
                "x_task",
                "x_expense",
            )
        ],
    }
    notes = scrub_exemplar_help_text(draft)
    notes.extend(cap_partner_smart_buttons(draft, max_partner=4))
    help_s = draft["models"][2]["fields"][0]["help"]
    assert "RNT" not in help_s
    assert "MAT" in help_s.upper() or "00001" in help_s
    partner = [b for b in draft["smart_buttons"] if b["on_model"] == "res.partner"]
    assert len(partner) == 4
    related = {b["related_model"] for b in partner}
    assert "x_matter" in related
    assert "x_bill" in related
    assert any("capped res.partner" in n for n in notes)


def test_ghost_hearing_auto_remap_and_parent_o2ms() -> None:
    from app.ai_model_quality import repair_draft_integrity

    draft = {
        "_ambition": "comprehensive",
        "models": [
            {
                "model": "x_matter",
                "is_workflow": True,
                "description": "Matter / Case",
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
                        "name": "x_hearing_ids",
                        "ttype": "one2many",
                        "relation": "x_event",
                        "relation_field": "x_matter_id",
                        "string": "Hearings",
                    },
                ],
            },
            {
                "model": "x_matter_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "help": "Wire ir.sequence (e.g. REC/00001)",
                    },
                ],
            },
            {
                "model": "x_bill",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('sent','Sent')]",
                    },
                ],
            },
            {
                "model": "x_event",
                "source": "depth_seed",
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
                "model": "x_task",
                "source": "depth_seed",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                    {"name": "x_date_deadline", "ttype": "date"},
                ],
            },
            {
                "model": "x_attorney",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_practice",
                        "ttype": "selection",
                        "selection": (
                            "[('general','General'),('specialty_a','Specialty A'),"
                            "('specialty_b','Specialty B'),('other','Other')]"
                        ),
                    },
                ],
            },
        ],
        "views": [
            {
                "name": "x_matter.form",
                "model": "x_matter",
                "type": "form",
                "arch": (
                    '<form><sheet><group string="Identity">'
                    '<field name="x_name"/></group></sheet></form>'
                ),
            }
        ],
        "automations": [
            {
                "name": "Update Matter Status on Hearing Completion",
                "model": "x_hearing",
                "trigger": "on_write",
                "safe_actions": [
                    {
                        "kind": "related_write",
                        "relation_field": "x_matter_id",
                        "field": "x_status",
                        "value": "completed",
                    }
                ],
                "source": "critique",
            },
            {
                "name": "Follow up on x_matter write",
                "model": "x_matter",
                "trigger": "on_write",
                "safe_actions": [{"kind": "next_activity", "summary": "Review"}],
                "source": "depth_seed",
            },
            {
                "name": "follow_up_matter",
                "model": "x_matter",
                "trigger": "on_write",
                "safe_actions": [{"kind": "next_activity", "summary": "Follow up"}],
                "source": "critique",
            },
        ],
        "smart_buttons": [],
    }
    notes = repair_draft_integrity(draft, ambition="comprehensive")
    auto_models = {a.get("model") for a in draft["automations"]}
    assert "x_hearing" not in auto_models
    # Invalid completed write should remove the remapped empty auto
    assert not any(
        "Hearing Completion" in str(a.get("name")) for a in draft["automations"]
    )
    followups = [
        a
        for a in draft["automations"]
        if a.get("model") == "x_matter"
        and all(
            isinstance(x, dict) and x.get("kind") == "next_activity"
            for x in (a.get("safe_actions") or [])
        )
        and "overdue" not in str(a.get("name") or "").lower()
    ]
    assert len(followups) == 1
    matter = next(m for m in draft["models"] if m["model"] == "x_matter")
    o2m_rels = {
        f["relation"]
        for f in matter["fields"]
        if f.get("ttype") == "one2many"
    }
    assert "x_event" in o2m_rels
    assert "x_task" in o2m_rels
    assert "x_bill" in o2m_rels or "x_matter_line" in o2m_rels
    line = next(m for m in draft["models"] if m["model"] == "x_matter_line")
    assert any(f.get("name") == "x_bill_id" for f in line["fields"])
    attorney = next(m for m in draft["models"] if m["model"] == "x_attorney")
    practice = next(f for f in attorney["fields"] if f["name"] == "x_practice")
    assert "specialty_a" not in practice["selection"]
    assert "litigation" in practice["selection"]
    task = next(m for m in draft["models"] if m["model"] == "x_task")
    assert any(f.get("name") == "x_status" for f in task["fields"])
    form = next(v for v in draft["views"] if v["name"] == "x_matter.form")
    assert "x_task_ids" in form["arch"] or "Task" in form["arch"]
    assert 'string="x_hearing_ids"' not in form["arch"]
    assert any("dropped automation" in n or "remapped automation" in n for n in notes)
