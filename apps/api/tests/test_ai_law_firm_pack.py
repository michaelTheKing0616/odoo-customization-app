"""Law-firm pack retrieval + teaching scaffold (generation-path)."""

from __future__ import annotations

from app.ai_domain_pack_law_firm import law_firm_pack, scaffold_teaching_blob
from app.ai_domain_packs import merge_domain_pack, retrieve_domain_pack_lexical
from app.ai_model_quality import MODEL_CREATION_RULES, few_shot_exemplar_json


def test_law_firm_pack_uses_canonical_names() -> None:
    pack = law_firm_pack()
    ids = {m["model"] for m in pack["models"] if isinstance(m, dict)}
    assert "x_attorney" in ids
    assert "x_matter" in ids
    assert "x_matter_line" in ids
    assert "x_bill" in ids
    assert "x_deposit" in ids
    assert "x_compliance" in ids
    assert "x_matter_party" in ids
    assert "x_party" not in ids
    assert "x_lf_attorney" not in ids
    # Fee earner on time line points at attorney, not users
    line = next(m for m in pack["models"] if m["model"] == "x_matter_line")
    att = next(f for f in line["fields"] if f["name"] == "x_attorney_id")
    assert att["relation"] == "x_attorney"
    # Partner canon
    matter = next(m for m in pack["models"] if m["model"] == "x_matter")
    partner_fields = [
        f for f in matter["fields"] if f.get("relation") == "res.partner"
    ]
    assert partner_fields
    assert all(f.get("name") == "x_partner_id" for f in partner_fields)


def test_retrieve_law_firm_from_prompt() -> None:
    hit = retrieve_domain_pack_lexical(
        "Build a world-class law firm practice management app with matters and retainers"
    )
    assert hit is not None
    pack_id, pack, score = hit
    assert pack_id == "law_firm"
    assert score >= 0.99
    assert pack.get("domain_pack") == "law_firm"


def test_scaffold_teaching_blob_has_field_depth() -> None:
    blob = scaffold_teaching_blob(law_firm_pack())
    assert "EQUAL OR GREATER" in blob or "operational depth" in blob
    assert "x_matter" in blob
    assert "selection" in blob
    # Real practice keys in model data — not placeholder option keys as values
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
            },
            {
                "model": "x_attorney",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
        ]
    }
    merged, notes = merge_domain_pack(thin, law_firm_pack())
    matter = next(m for m in merged["models"] if m["model"] == "x_matter")
    names = {f.get("name") for f in matter["fields"]}
    assert "x_status" in names
    assert "x_attorney_id" in names or any(
        f.get("relation") == "x_attorney" for f in matter["fields"]
    )
    assert any("domain pack added field" in n for n in notes)
    assert "x_document" in {m["model"] for m in merged["models"]}


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
    assert any("generation gap" in w for w in warnings)

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
    assert att["relation"] == "x_attorney"
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
    assert any("fixed relation x_matter_line.x_attorney_id" in w for w in warnings)
    assert any("upgraded selection x_matter.x_status" in w for w in warnings)
    line = next(m for m in merged["models"] if m["model"] == "x_matter_line")
    assert next(f for f in line["fields"] if f["name"] == "x_attorney_id")[
        "relation"
    ] == "x_attorney"
    notes = repair_draft_integrity(merged, ambition="comprehensive")
    matter = next(m for m in merged["models"] if m["model"] == "x_matter")
    status = next(f for f in matter["fields"] if f["name"] == "x_status")
    assert "closed" in status["selection"]
    party = next(m for m in merged["models"] if m["model"] == "x_matter_party")
    assert party.get("is_workflow") is False
    doc = next(m for m in merged["models"] if m["model"] == "x_document")
    assert next(f for f in doc["fields"] if f["name"] == "x_name").get("required")
    auto = next(
        a
        for a in merged["automations"]
        if a.get("name") == "Activity before limitation date"
    )
    assert "closed" in str(auto.get("filter_domain") or "")
    assert "x_attorney" in {m["model"] for m in merged["models"]}
    assert "x_bill" in {m["model"] for m in merged["models"]}
    _ = notes


def test_creation_rules_and_few_shot_teach_excellence() -> None:
    assert "WORLD-CLASS OPS DEPTH" in MODEL_CREATION_RULES
    assert "specialty_a" in MODEL_CREATION_RULES or "placeholders" in MODEL_CREATION_RULES
    blob = few_shot_exemplar_json()
    assert "x_ex_party" in blob
    assert "x_ex_deposit" in blob
    assert "x_ex_event" in blob
    assert "held" in blob or "retainer" in blob.lower() or "Held" in blob
