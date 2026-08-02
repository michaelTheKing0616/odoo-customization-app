"""Domain-agnostic ModuleSpec depth floors (no LLM required)."""

from __future__ import annotations

from app.ai_depth import (
    apply_deterministic_depth,
    classify_ambition,
    compute_depth_metrics,
    depth_gaps,
    run_depth_pass,
    synthesize_smart_buttons_from_relations,
)


def test_classify_ambition_comprehensive() -> None:
    assert (
        classify_ambition(
            "I want a comprehensive Hospital Management app that perfectly models "
            "the internal workings of a modern world-class hospital"
        )
        == "comprehensive"
    )


def test_classify_ambition_thin() -> None:
    assert classify_ambition("simple todo list") == "thin"


def test_classify_ambition_standard_management() -> None:
    assert (
        classify_ambition("Build a fleet management system for our delivery vans")
        == "standard"
    )


def test_seed_fills_comprehensive_model_floor() -> None:
    draft = {
        "models": [
            {
                "model": "x_attorney",
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
                "model": "x_matter",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                    {
                        "name": "x_attorney_id",
                        "ttype": "many2one",
                        "relation": "x_attorney",
                    },
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
                ],
            },
            {
                "model": "x_bill",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "relation": "x_matter",
                    },
                    {"name": "x_amount", "ttype": "float"},
                ],
            },
            {
                "model": "x_client_contact",
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
                "model": "x_fee_schedule",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_attorney_id",
                        "ttype": "many2one",
                        "relation": "x_attorney",
                    },
                ],
            },
        ],
        "automations": [
            {
                "name": "Flag overdue",
                "model": "x_matter",
                "trigger": "on_time",
                "safe_actions": [
                    {"kind": "object_write", "field": "x_status", "value": "overdue"}
                ],
                "source": "rules_engine",
            }
        ],
        "smart_buttons": [],
    }
    out, notes = apply_deterministic_depth(draft, "comprehensive")
    ids = {m["model"] for m in out["models"]}
    assert "x_client_contact" not in ids
    assert "x_fee_schedule" not in ids
    assert "x_event" in ids or any("event" in i for i in ids)
    assert "x_task" in ids or any("task" in i for i in ids)
    assert not depth_gaps(out, "comprehensive") or "depth_models" not in depth_gaps(
        out, "comprehensive"
    )
    assert compute_depth_metrics(out)["model_count"] >= 10
    assert compute_depth_metrics(out)["automation_count"] >= 2
    assert any("seeded substantive" in n for n in notes)


def test_thin_hospitalish_draft_fails_comprehensive_depth() -> None:
    draft = {
        "_ambition": "comprehensive",
        "models": [
            {
                "model": "x_patient",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                ],
            },
            {
                "model": "x_appointment",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_patient_id",
                        "ttype": "many2one",
                        "relation": "x_patient",
                    },
                ],
            },
        ],
        "smart_buttons": [],
        "automations": [],
    }
    gaps = depth_gaps(draft, "comprehensive")
    assert "depth_models" in gaps
    assert "depth_smart_buttons" in gaps


def test_synthesize_smart_buttons_from_m2o_graph() -> None:
    draft = {
        "models": [
            {"model": "x_patient", "description": "Patient", "fields": [{"name": "x_name"}]},
            {
                "model": "x_appointment",
                "description": "Appointment",
                "fields": [
                    {"name": "x_name"},
                    {
                        "name": "x_patient_id",
                        "ttype": "many2one",
                        "relation": "x_patient",
                    },
                ],
            },
        ],
        "smart_buttons": [],
    }
    notes = synthesize_smart_buttons_from_relations(draft)
    assert notes
    assert draft["smart_buttons"][0]["on_model"] == "x_patient"
    assert draft["smart_buttons"][0]["relation_field"] == "x_patient_id"


def test_deterministic_depth_adds_currency_and_buttons() -> None:
    draft = {
        "_ambition": "standard",
        "models": [
            {
                "model": "x_order",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                    {"name": "x_amount", "ttype": "float"},
                ],
            },
            {
                "model": "x_order_line",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_order_id",
                        "ttype": "many2one",
                        "relation": "x_order",
                    },
                ],
            },
        ],
    }
    out, notes = apply_deterministic_depth(draft, "standard")
    order = next(m for m in out["models"] if m["model"] == "x_order")
    names = {f["name"] for f in order["fields"]}
    assert "x_currency_id" in names
    assert "x_code" in names
    assert out["smart_buttons"]
    assert out["_depth"]["metrics"]["smart_button_count"] >= 1
    assert any("depth:" in n for n in notes)


def test_hollow_catalog_models_do_not_count_toward_depth() -> None:
    draft = {
        "_ambition": "comprehensive",
        "models": [
            {
                "model": "x_case",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                    {
                        "name": "x_client_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            },
            # Hollow taxonomy padding (like the law-firm AI draft)
            *[
                {
                    "model": f"x_case_{s}",
                    "fields": [
                        {"name": "x_name", "ttype": "char"},
                        {"name": "x_code", "ttype": "char"},
                    ],
                }
                for s in ("type", "category", "tag", "stage", "priority")
            ],
        ],
        "smart_buttons": [],
        "automations": [],
    }
    m = compute_depth_metrics(draft)
    assert m["model_count_raw"] == 6
    assert m["hollow_model_count"] == 5
    assert m["model_count"] == 1
    assert "depth_models" in depth_gaps(draft, "comprehensive")


def test_strip_unsafe_code_automations() -> None:
    from app.ai_depth import apply_deterministic_depth

    draft = {
        "_ambition": "standard",
        "models": [
            {
                "model": "x_case",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                ],
            },
            {
                "model": "x_doc",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_case_id",
                        "ttype": "many2one",
                        "relation": "x_case",
                    },
                ],
            },
        ],
        "automations": [
            {
                "trigger": "on_write",
                "model": "x_case",
                "action": {
                    "state": "code",
                    "code": "python,\nself.env['mail.mail'].create({})",
                },
            },
            {
                "name": "Safe status bump",
                "model": "x_case",
                "trigger": "on_write",
                "safe_actions": [
                    {"kind": "object_write", "field": "x_status", "value": "open"}
                ],
            },
            {
                "name": "Empty critique stub",
                "model": "x_case",
                "trigger": "on_write",
                "safe_actions": [],
                "source": "critique",
            },
        ],
    }
    out, notes = apply_deterministic_depth(draft, "standard")
    assert len(out["automations"]) == 1
    assert out["automations"][0]["name"] == "Safe status bump"
    assert any("stripped unsafe" in n for n in notes)


def test_law_firm_gold_meets_comprehensive_depth() -> None:
    from app.ai_reference_law_firm import law_firm_gold_spec

    draft = law_firm_gold_spec()
    draft["_ambition"] = "comprehensive"
    out, _ = apply_deterministic_depth(draft, "comprehensive")
    assert out["_depth"]["ok"] is True
    assert out["_depth"]["metrics"]["model_count"] >= 10
    assert out["_depth"]["metrics"]["hollow_model_count"] == 0


def test_run_depth_pass_without_llm_sets_ambition() -> None:
    draft = {
        "models": [
            {
                "model": "x_a",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            }
        ]
    }
    out, warnings = run_depth_pass(
        draft,
        user_prompt="comprehensive warehouse management end-to-end",
        provider=None,
        expand_llm=False,
    )
    assert out["_ambition"] == "comprehensive"
    # Deterministic seed fills the model floor even without an LLM
    assert compute_depth_metrics(out)["model_count"] >= 10
    assert any("seeded substantive" in w for w in warnings)
    assert out["_depth"]["ok"] or "depth_models" not in out["_depth"]["gaps"]
