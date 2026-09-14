"""Wave 15 GEN cards — deterministic generation fidelity fixes."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app.ai_critique import apply_critique_repairs
from app.ai_depth import (
    apply_deterministic_depth,
    classify_ambition,
    classify_ambition_with_notes,
    depth_gaps,
    seed_operational_loop_models,
)
from app.ai_domain_nouns import (
    domain_noun_coverage,
    expand_uncovered_noun_models,
    extract_prompt_nouns,
)
from app.ai_domain_coherence import rank_domain_packs
from app.ai_domain_packs import load_domain_pack, match_domain_pack, prune_extraneous_models
from app.ai_model_quality import (
    enforce_on_write_filter_domains,
    repair_draft_integrity,
    strip_internal_scaffold,
)
from app.ai_ollama import derive_draft_naming_from_prompt
from app.ai_reuse_planner import apply_reuse_plan, plan_reuse
from app.ai_selection import dedupe_selection_pairs, normalize_selection_field, parse_selection_literal, canonicalize_selection_pairs
from app.ai_draft_scorecard import draft_scorecard
from app.ai_stock_reuse import infer_stock_reuse
from app.ai_workflow import ensure_workflow_transitions_on_draft

FIXTURE = Path(__file__).parent / "fixtures" / "draft_supermarket_2026-08-05.json"
SUPERMARKET_PROMPT = "A large mega Super Market with multiple branches"
OIL_GAS_PROMPT = (
    "A large Oil and Gas drilling and refining company with multiple branches around the world"
)
LAW_PROMPT = "Comprehensive law firm matter management with hearings and billing"


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


def test_selection_dedupe_duplicate_cancelled() -> None:
    field = {
        "ttype": "selection",
        "name": "x_status",
        "selection": (
            "[('draft','Draft'),('cancelled','Cancelled'),('cancelled','Dup')]"
        ),
    }
    notes = normalize_selection_field(field, context="x_order.x_status")
    assert notes
    assert field["selection"].count("'cancelled'") == 1


def test_selection_dedupe_mixed_syntax() -> None:
    pairs = [("draft", "Draft"), ("open", "Open"), ("draft", "Draft again")]
    deduped, changed = dedupe_selection_pairs(pairs)
    assert changed
    assert deduped == [("draft", "Draft"), ("open", "Open")]


def test_canonicalize_title_case_and_antonym_swap() -> None:
    pairs, mapping, changed = canonicalize_selection_pairs(
        [("Draft", "Draft"), ("draft", "Draft"), ("open", "Open")]
    )
    assert changed
    assert mapping["Draft"] == "draft"
    assert pairs[0] == ("draft", "Draft")
    assert [k for k, _ in pairs] == ["draft", "open"]

    pairs2, _, changed2 = canonicalize_selection_pairs(
        [("active", "inactive"), ("draft", "Draft")]
    )
    assert changed2
    assert pairs2[0] == ("active", "Active")


def test_canonicalize_completed_folds_to_done() -> None:
    pairs, mapping, changed = canonicalize_selection_pairs(
        [("draft", "Draft"), ("completed", "Completed"), ("done", "Done")]
    )
    assert changed
    assert mapping["completed"] == "done"
    assert [k for k, _ in pairs] == ["draft", "done"]
    assert pairs[-1] == ("done", "Done")


def test_terminal_merge_preserves_flow_states() -> None:
    draft = _load_fixture()
    repair_draft_integrity(draft, ambition="standard")
    order = next(m for m in draft["models"] if m["model"] == "x_sales_order")
    sf = order["state_field"]
    states = sf.get("states") or []
    assert "draft" in states
    assert "confirmed" in states
    assert "delivered" in states
    assert sf.get("transitions")


def test_supermarket_fixture_roundtrip_integrity() -> None:
    draft = _load_fixture()
    notes = repair_draft_integrity(draft, ambition="standard")
    assert notes
    order = next(m for m in draft["models"] if m["model"] == "x_sales_order")
    status = next(f for f in order["fields"] if f["name"] == "x_status")
    assert status["selection"].count("'cancelled'") == 1
    assert order["state_field"]["transitions"]


def test_domain_noun_flags_branch_for_supermarket() -> None:
    draft = _load_fixture()
    items, uncovered, warnings = domain_noun_coverage(draft, SUPERMARKET_PROMPT)
    assert "branch" in uncovered
    assert any(i["id"] == "noun_uncovered:branch" and not i["ok"] for i in items)
    assert warnings


def test_domain_noun_no_false_positive_law_firm() -> None:
    draft = {
        "models": [
            {"model": "x_matter", "description": "Legal matter"},
            {"model": "x_hearing", "description": "Hearing"},
        ]
    }
    _items, uncovered, _w = domain_noun_coverage(draft, LAW_PROMPT)
    assert "branch" not in uncovered


def test_seed_labels_neutral_no_law_firm_lexicon() -> None:
    draft = {
        "models": [
            {
                "model": "x_sales_order",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                    {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
                ],
            }
        ],
        "_user_prompt": SUPERMARKET_PROMPT,
    }
    notes = seed_operational_loop_models(draft, "comprehensive", user_prompt=SUPERMARKET_PROMPT)
    assert notes
    seeded = [m for m in draft["models"] if m.get("source") == "depth_seed"]
    assert seeded
    for m in seeded:
        desc = str(m.get("description") or "").lower()
        assert "retainer" not in desc
        assert "appointment" not in desc
        assert "disbursement" not in desc


def test_seeded_only_depth_sets_flag() -> None:
    draft = {
        "models": [
            {
                "model": "x_sales_order",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_status", "ttype": "selection"},
                    {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
                ],
            }
        ],
        "_ambition": "comprehensive",
    }
    out, notes = apply_deterministic_depth(
        draft, "comprehensive", user_prompt=SUPERMARKET_PROMPT
    )
    depth = out.get("_depth") or {}
    assert depth.get("seeded") is True
    assert "depth_models" in (depth.get("gaps") or [])
    assert any("generic seeds" in n for n in notes)


def test_strip_internal_json_scaffold() -> None:
    draft = {"technical_name": "demo", "json": {"models": [{"model": "x_ex_job"}]}}
    notes = strip_internal_scaffold(draft)
    assert "json" not in draft
    assert notes


def test_derive_naming_from_supermarket_prompt() -> None:
    draft: dict[str, Any] = {"technical_name": "custom_app"}
    warnings = derive_draft_naming_from_prompt(draft, SUPERMARKET_PROMPT)
    assert draft["technical_name"] != "custom_app"
    assert "super" in draft["technical_name"] or "market" in draft["technical_name"]
    assert draft.get("display_name")
    assert warnings


def test_on_write_automation_requires_filter_domain() -> None:
    draft = _load_fixture()
    notes = enforce_on_write_filter_domains(draft)
    assert notes
    assert not any(a.get("name") == "Notify on order confirmation" for a in draft["automations"])


def test_critique_ready_consistency_when_empty() -> None:
    draft = {"models": [{"model": "x_thing", "fields": []}]}
    out, _notes = apply_critique_repairs(
        draft, {"ready": False, "checklist": [], "notes": []}
    )
    assert out["_critique"]["ready"] is True


def test_critique_not_ready_has_notes() -> None:
    draft = {"models": [{"model": "x_thing", "fields": []}]}
    out, _notes = apply_critique_repairs(
        draft,
        {"ready": False, "checklist": [{"id": "x", "ok": False}], "notes": []},
    )
    assert out["_critique"]["ready"] is False
    assert out["_critique"]["notes"]


def test_critique_notes_string_is_not_split_into_characters() -> None:
    draft = {"models": [{"model": "x_thing", "fields": []}]}
    out, _notes = apply_critique_repairs(
        draft,
        {
            "ready": False,
            "checklist": [{"id": "audit_trail", "ok": True}],
            "notes": "Missing fields include x_confirm_date.",
        },
    )
    assert out["_critique"]["notes"] == ["Missing fields include x_confirm_date."]
    out2, _ = apply_critique_repairs(
        draft,
        {
            "ready": False,
            "checklist": [{"id": "audit_trail", "ok": True}],
            "notes": list("Missing fields"),
        },
    )
    assert out2["_critique"]["notes"] == ["Missing fields"]


def test_workflow_empty_transitions_gets_chain() -> None:
    draft = copy.deepcopy(_load_fixture())
    for m in draft["models"]:
        if m.get("model") == "x_sales_order":
            m["state_field"] = {"field": "x_status", "states": [], "transitions": []}
    ensure_workflow_transitions_on_draft(draft)
    order = next(m for m in draft["models"] if m["model"] == "x_sales_order")
    assert order["state_field"]["transitions"]


def test_ambition_scales_mega_supermarket_to_comprehensive() -> None:
    amb, notes = classify_ambition_with_notes(SUPERMARKET_PROMPT)
    assert amb == "comprehensive"
    assert notes
    assert classify_ambition(SUPERMARKET_PROMPT) == "comprehensive"


def test_retail_supermarket_pack_matches_prompt() -> None:
    matched = match_domain_pack(SUPERMARKET_PROMPT)
    assert matched is not None
    pack_id, pack = matched
    assert pack_id == "retail_supermarket"
    models = {m.get("model"): m for m in pack.get("models") or [] if isinstance(m, dict)}
    assert "x_branch" in models
    assert pack.get("reuse_stock")
    branch_names = {f.get("name") for f in models["x_branch"].get("fields") or []}
    assert "x_address_id" in branch_names
    assert "x_country_id" in branch_names
    assert "x_address" not in branch_names
    assert "x_inventory_reason" in models
    assert "x_inventory_adjustment" in models
    adj_names = {f.get("name") for f in models["x_inventory_adjustment"].get("fields") or []}
    assert "x_reason_id" in adj_names
    assert "x_reason" not in adj_names
    order = models["x_store_order"]
    assert isinstance(order.get("state_field"), dict)
    assert "confirmed" in (order.get("state_field") or {}).get("states", [])


def test_oil_gas_pack_matches_drilling_prompt() -> None:
    matched = match_domain_pack(OIL_GAS_PROMPT)
    assert matched is not None
    pack_id, pack = matched
    assert pack_id == "oil_gas_operations"
    models = {m.get("model") for m in pack.get("models") or [] if isinstance(m, dict)}
    assert "x_og_facility" in models
    assert "x_og_work_order" in models
    assert "x_branch" not in models


def _run_senior_app_bar(draft: dict[str, Any], prompt: str) -> dict[str, Any]:
    from app.ai_odoo_app_bar import (
        apply_senior_sequence_prefixes,
        inject_chatter_on_forms,
        run_odoo_app_bar_pass,
    )
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    draft["_user_prompt"] = prompt
    draft.setdefault("_ambition", "comprehensive")
    run_post_critique_pipeline(draft, user_prompt=prompt)
    run_odoo_app_bar_pass(draft, user_prompt=prompt)
    run_production_shape_pass(draft)
    apply_senior_sequence_prefixes(draft)
    inject_chatter_on_forms(draft)
    return draft


def _assert_senior_document_floor(
    draft: dict[str, Any],
    *,
    workflow_model: str,
    site_model: str | None = None,
    expected_menu: str,
) -> None:
    """Odoo Apps-shaped floor: short menus, lines, search, chatter, stock links, automations."""
    models = {m["model"] for m in draft["models"]}
    assert f"{workflow_model}_line" in models
    menus = [
        str(m.get("name"))
        for m in (draft.get("menus") or [])
        if isinstance(m, dict) and m.get("action_xml_id")
    ]
    assert menus
    assert all("/" not in name for name in menus)
    assert expected_menu in menus
    search_models = {
        str(v.get("model"))
        for v in (draft.get("views") or [])
        if isinstance(v, dict) and v.get("type") == "search"
    }
    assert workflow_model in search_models
    if site_model:
        assert site_model in search_models
    assert len(draft.get("automations") or []) >= 1
    header = next(m for m in draft["models"] if m["model"] == workflow_model)
    child_o2m = {
        str(f.get("relation") or "")
        for f in (header.get("fields") or [])
        if isinstance(f, dict)
        and f.get("ttype") == "one2many"
        and str(f.get("relation") or "").startswith("x_")
    }
    btn_targets = {
        (str(b.get("on_model")), str(b.get("related_model")))
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    for child in child_o2m:
        assert (workflow_model, child) not in btn_targets
    form = next(
        v
        for v in draft["views"]
        if v.get("model") == workflow_model and v.get("type") == "form"
    )
    assert "<chatter" in str(form.get("arch") or "").lower()
    header = next(m for m in draft["models"] if m["model"] == workflow_model)
    names = {f.get("name") for f in header.get("fields") or []}
    assert "x_employee_id" in names
    assert "x_purchase_order_id" in names
    assert str(form.get("arch") or "").count('string="Cancel"') <= 1


def test_odoo_app_bar_raises_oil_gas_to_senior_floor() -> None:
    pack = load_domain_pack("oil_gas_operations")
    assert pack is not None
    draft = _run_senior_app_bar(copy.deepcopy(pack), OIL_GAS_PROMPT)
    _assert_senior_document_floor(
        draft,
        workflow_model="x_og_work_order",
        site_model="x_og_facility",
        expected_menu="Work Orders",
    )
    assert len(draft.get("automations") or []) >= 2
    header_stock = {
        str(b.get("related_model") or "")
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
        and b.get("on_model") == "x_og_work_order"
        and "." in str(b.get("related_model") or "")
    }
    assert header_stock & {"project.task", "purchase.order", "maintenance.request"}
    assert len(draft.get("smart_buttons") or []) >= 2
    assert "Facilities" in [
        str(m.get("name"))
        for m in (draft.get("menus") or [])
        if isinstance(m, dict) and m.get("action_xml_id")
    ] or any(
        "Facilit" in str(m.get("name") or "")
        for m in (draft.get("menus") or [])
        if isinstance(m, dict) and m.get("action_xml_id")
    )


def test_odoo_app_bar_raises_unpacked_domain_to_senior_floor() -> None:
    """Senior bar is shape-based — a foundry (no domain pack) must hit the same floor."""
    wo_status = (
        "[('draft', 'Draft'), ('planned', 'Planned'), ('in_progress', 'In progress'),"
        " ('done', 'Done'), ('cancelled', 'Cancelled')]"
    )
    draft = {
        "technical_name": "foundry_operations",
        "display_name": "Foundry Operations",
        "depends": ["base", "mail", "hr", "purchase", "stock"],
        "odoo_major": 19,
        "models": [
            {
                "model": "x_fdy_site",
                "description": "Pour site / furnace hall",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Site", "required": True},
                    {"name": "x_code", "ttype": "char", "string": "Code"},
                ],
            },
            {
                "model": "x_fdy_job",
                "description": "Melt / pour job with long slashy pack-style name",
                "mode": "new",
                "is_workflow": True,
                "state_field": {
                    "field": "x_status",
                    "states": ["draft", "planned", "in_progress", "done", "cancelled"],
                    "transitions": [
                        ["draft", "planned"],
                        ["planned", "in_progress"],
                        ["in_progress", "done"],
                        ["draft", "cancelled"],
                        ["planned", "cancelled"],
                        ["in_progress", "cancelled"],
                    ],
                    "statusbar_visible": ["draft", "planned", "in_progress", "done"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Job", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": wo_status,
                        "required": True,
                    },
                    {
                        "name": "x_site_id",
                        "ttype": "many2one",
                        "relation": "x_fdy_site",
                        "string": "Site",
                    },
                    {"name": "x_date_end", "ttype": "datetime", "string": "Due"},
                ],
            },
        ],
    }
    prompt = "A bronze foundry with melt jobs, furnace halls, and spare-part purchasing"
    shaped = _run_senior_app_bar(draft, prompt)
    _assert_senior_document_floor(
        shaped,
        workflow_model="x_fdy_job",
        site_model="x_fdy_site",
        expected_menu="Jobs",
    )


def test_app_bar_cleans_unpacked_music_dump() -> None:
    """LLM dump for an unknown vertical: drop phantom O2Ms, demote studio, short menus."""
    prompt = "A music production company with multiple recording studios and artistes"
    draft = {
        "technical_name": "a_music_production_compa",
        "display_name": "A Music Production Compa",
        "depends": ["base", "mail"],
        "models": [
            {
                "model": "x_project",
                "description": "X Project",
                "is_workflow": True,
                "state_field": {
                    "field": "x_status",
                    "states": ["draft", "open", "done"],
                    "transitions": [["draft", "open"], ["open", "done"]],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                    },
                    {
                        "name": "x_studio_id",
                        "ttype": "many2one",
                        "relation": "x_studio",
                    },
                    {
                        "name": "x_project_files",
                        "ttype": "one2many",
                        "relation": "x_project_file",
                    },
                    {
                        "name": "x_project_versions",
                        "ttype": "one2many",
                        "relation": "x_project_version",
                    },
                    {
                        "name": "x_project_versions",
                        "ttype": "one2many",
                        "relation": "x_project_version",
                    },
                ],
                "mixins": ["mail.thread", "mail.activity.mixin"],
            },
            {
                "model": "x_studio",
                "description": "Recording Studio Location And Equipment",
                "is_workflow": True,
                "state_field": {
                    "field": "x_status",
                    "states": ["draft", "open", "done"],
                    "transitions": [["draft", "open"], ["open", "done"]],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('active','Active'),('draft','Draft')]",
                    },
                ],
            },
            {
                "model": "x_session",
                "description": "X Session",
                "is_workflow": True,
                "state_field": {
                    "field": "x_status",
                    "states": ["draft", "open", "done"],
                    "transitions": [["draft", "open"], ["open", "done"]],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_project_id",
                        "ttype": "many2one",
                        "relation": "x_project",
                    },
                    {
                        "name": "x_studio_id",
                        "ttype": "many2one",
                        "relation": "x_studio",
                    },
                    {"name": "x_date_end", "ttype": "datetime"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                    },
                ],
                "mixins": ["mail.thread", "mail.activity.mixin"],
            },
        ],
    }
    from app.ai_ollama import derive_draft_naming_from_prompt

    derive_draft_naming_from_prompt(draft, prompt)
    assert "music" in draft["technical_name"]
    assert not draft["technical_name"].startswith("a_")
    assert not str(draft["display_name"]).startswith("A ")
    shaped = _run_senior_app_bar(draft, prompt)
    studio = next(m for m in shaped["models"] if m["model"] == "x_studio")
    assert studio.get("is_workflow") is False
    project = next(m for m in shaped["models"] if m["model"] == "x_project")
    fname_list = [f.get("name") for f in project["fields"]]
    assert "x_project_files" not in fname_list
    assert fname_list.count("x_project_versions") <= 1
    menus = [
        str(m.get("name"))
        for m in (shaped.get("menus") or [])
        if isinstance(m, dict) and m.get("action_xml_id")
    ]
    assert "Projects" in menus
    assert all(not n.startswith("X ") for n in menus)
    btn_targets = {
        (str(b.get("on_model")), str(b.get("related_model")))
        for b in (shaped.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    for model in shaped["models"]:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        for field in model.get("fields") or []:
            if (
                isinstance(field, dict)
                and field.get("ttype") == "one2many"
                and str(field.get("relation") or "").startswith("x_")
            ):
                assert (mid, str(field.get("relation"))) not in btn_targets


def test_artiste_noun_covered_by_x_artist() -> None:
    prompt = "A music production company with multiple recording studios and artistes"
    draft = {
        "models": [
            {
                "model": "x_artist",
                "description": "Artist",
                "fields": [{"name": "x_name", "ttype": "char", "string": "Name"}],
            },
            {
                "model": "x_studio",
                "description": "Studio",
                "fields": [{"name": "x_name", "ttype": "char", "string": "Name"}],
            },
        ]
    }
    _items, uncovered, _w = domain_noun_coverage(draft, prompt)
    assert "artiste" not in uncovered
    assert "recording" not in uncovered


def test_app_bar_prunes_generic_loop_on_music_prompt() -> None:
    """Unpacked music prompt must not ship a second CRM/billing/task app."""
    prompt = "A music production company with multiple recording studios and artistes"
    draft = {
        "technical_name": "music_production_recording_studios",
        "display_name": "Music Production Recording Studios",
        "depends": ["base", "mail", "contacts"],
        "groups": [
            {"id": "group_a_music_production_compa_user", "name": "Old User"},
            {"id": "group_music_production_recording_studios_user", "name": "New User"},
        ],
        "access_rules": [
            {
                "id": "access_x_project_user",
                "model": "model_x_project",
                "group": "group_a_music_production_compa_user",
                "perm_read": 1,
            }
        ],
        "automations": [
            {
                "name": "Artist to Active Status",
                "model": "x_artist",
                "trigger": "on_write",
                "filter_domain": "[]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Artist to Active Status"}
                ],
            }
        ],
        "models": [
            {
                "model": "x_project",
                "description": "X Project",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_studio_id",
                        "ttype": "many2one",
                        "relation": "x_studio",
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('recording','Recording'),('done','Done')]",
                    },
                    {"name": "x_end_date", "ttype": "date"},
                ],
            },
            {
                "model": "x_artist",
                "description": "X Artist",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_studio",
                "description": "X Studio",
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_manager_id",
                        "ttype": "many2one",
                        "relation": "x_staff",
                    },
                ],
            },
            {
                "model": "x_session",
                "description": "X Session",
                "is_workflow": False,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_artist_id",
                        "ttype": "many2one",
                        "relation": "x_artist",
                    },
                    {
                        "name": "x_studio_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                    {"name": "x_end_date", "ttype": "datetime"},
                ],
            },
            {
                "model": "x_task",
                "description": "X Task",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_deposit",
                "description": "X Deposit",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_party_link",
                "description": "X Party Link",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_document",
                "description": "X Document",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_bill",
                "description": "Bill",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {
                        "name": "x_bill_id",
                        "ttype": "many2one",
                        "relation": "account.move",
                    },
                    {
                        "name": "x_session_id",
                        "ttype": "many2one",
                        "relation": "x_session",
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('paid','Paid')]",
                    },
                ],
            },
            {
                "model": "x_staff",
                "description": "X Staff",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_fee",
                "description": "X Fee",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_expense",
                "description": "X Expense",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
        ],
    }
    from app.ai_draft_scorecard import draft_scorecard

    raw_sc = draft_scorecard(copy.deepcopy(draft), user_prompt=prompt)
    assert raw_sc["dimensions"]["hygiene"] < 10.0
    assert not any(
        str(f.get("element") or "") == "noun:artiste" for f in raw_sc.get("findings") or []
    )

    shaped = _run_senior_app_bar(draft, prompt)
    ids = {m["model"] for m in shaped["models"]}
    assert "x_deposit" not in ids
    assert "x_party_link" not in ids
    assert "x_bill" not in ids
    assert "x_task" not in ids
    assert "x_document" not in ids
    assert "x_staff" not in ids
    assert "x_fee" not in ids
    assert "x_expense" in ids
    assert "x_recording" in ids
    assert "x_equipment" in ids
    assert "x_rate" in ids
    non_line = {m for m in ids if str(m).startswith("x_") and not str(m).endswith("_line")}
    assert len(non_line) >= 10
    assert "x_project" in ids
    assert "x_artist" in ids
    assert "x_studio" in ids
    assert "x_session" in ids
    assert "x_session_line" in ids
    session = next(m for m in shaped["models"] if m["model"] == "x_session")
    assert session.get("is_workflow") is True
    studio_fk = next(
        f
        for f in session["fields"]
        if f.get("name") == "x_studio_id"
    )
    assert studio_fk.get("relation") == "x_studio"
    assert any(
        f.get("name") == "x_invoice_id" and f.get("relation") == "account.move"
        for f in session["fields"]
    )
    studio = next(m for m in shaped["models"] if m["model"] == "x_studio")
    assert not studio.get("is_workflow")
    mgr = next(
        (f for f in studio["fields"] if f.get("name") == "x_manager_id"),
        None,
    )
    if mgr:
        assert mgr.get("relation") != "x_staff"
    menus = [
        m
        for m in (shaped.get("menus") or [])
        if isinstance(m, dict) and m.get("action_xml_id")
    ]
    other_children = [
        str(m.get("name"))
        for m in menus
        if "menu_sub_other_" in str(m.get("parent_xml_id") or "")
    ]
    assert "Projects" not in other_children
    assert "Sessions" not in other_children
    assert "Artists" not in other_children
    assert "Studios" not in other_children
    group_ids = {
        str(g.get("id"))
        for g in (shaped.get("groups") or [])
        if isinstance(g, dict)
    }
    assert "group_music_production_recording_studios_user" in group_ids
    assert "group_a_music_production_compa_user" not in group_ids
    for rule in shaped.get("access_rules") or []:
        if isinstance(rule, dict) and rule.get("group"):
            assert "a_music_production_compa" not in str(rule.get("group"))
    hollow = [
        a
        for a in (shaped.get("automations") or [])
        if isinstance(a, dict)
        and str(a.get("filter_domain") or "").strip() in {"", "[]"}
        and a.get("name") == "Artist to Active Status"
    ]
    assert not hollow
    _items, uncovered, _w = domain_noun_coverage(shaped, prompt)
    assert "artiste" not in uncovered
    sc = draft_scorecard(shaped, user_prompt=prompt)
    assert not any(
        str(f.get("element") or "") == "noun:artiste" for f in sc.get("findings") or []
    )
    assert not any(
        "generic ops-loop" in str(f.get("detail") or "")
        for f in sc.get("findings") or []
    )
    root = next(
        (
            m
            for m in (shaped.get("menus") or [])
            if isinstance(m, dict) and not m.get("parent_xml_id") and not m.get("action_xml_id")
        ),
        None,
    )
    assert root is not None
    assert str(root.get("web_icon") or "").startswith("fa-music")


def test_domain_density_fills_music_vertical_without_generic_loop() -> None:
    from app.ai_domain_density import ensure_domain_density

    prompt = "A music production company with multiple recording studios and artistes"
    draft = {
        "_ambition": "comprehensive",
        "_user_prompt": prompt,
        "models": [
            {
                "model": "x_studio",
                "description": "Studio",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_artist",
                "description": "Artist",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_project",
                "description": "Project",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
            {
                "model": "x_session",
                "description": "Session",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
        ],
    }
    notes = ensure_domain_density(draft, user_prompt=prompt, ambition="comprehensive")
    assert notes
    ids = {m["model"] for m in draft["models"]}
    assert "x_recording" in ids
    assert "x_equipment" in ids
    assert "x_rate" in ids
    assert "x_agreement" in ids
    assert "x_expense" in ids
    assert "x_deposit" not in ids
    assert "x_party_link" not in ids
    assert "x_task" not in ids
    non_line = {m for m in ids if not str(m).endswith("_line")}
    assert len(non_line) >= 10
    assert any(m.get("source") == "domain_density" for m in draft["models"])


def test_domain_density_bootstraps_empty_music_draft_from_prompt() -> None:
    from app.ai_domain_density import ensure_domain_density

    prompt = "A music production company with multiple recording studios and artistes"
    draft: dict[str, Any] = {
        "_ambition": "comprehensive",
        "_user_prompt": prompt,
        "models": [],
    }
    notes = ensure_domain_density(draft, user_prompt=prompt, ambition="comprehensive")
    assert notes
    ids = {m["model"] for m in draft["models"]}
    assert "x_studio" in ids
    assert "x_artist" in ids
    assert "x_equipment" in ids
    assert len({m for m in ids if not str(m).endswith("_line")}) >= 8


def test_oil_gas_branches_prompt_does_not_match_retail() -> None:
    matched = match_domain_pack(OIL_GAS_PROMPT)
    assert matched is not None
    assert matched[0] != "retail_supermarket"


def test_prune_extraneous_models_strips_frankenstein_pollution() -> None:
    pack = load_domain_pack("retail_supermarket")
    assert pack is not None
    draft: dict[str, Any] = {
        "domain_pack": "retail_supermarket",
        "_user_prompt": OIL_GAS_PROMPT,
        "models": [
            {"model": "x_branch", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_store_order", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_matter", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_drilling_operation", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_bill", "fields": [{"name": "x_name", "ttype": "char"}]},
        ],
        "actions": [{"model": "x_matter", "technical_name": "action_matter"}],
    }
    notes = prune_extraneous_models(draft, pack)
    models = {m["model"] for m in draft["models"]}
    assert "x_matter" not in models
    assert "x_bill" not in models
    assert "x_branch" in models
    assert any("domain coherence" in n for n in notes)


def test_oil_gas_prompt_does_not_infer_law_firm_industry() -> None:
    from app.ai_domain_coherence import infer_prompt_industries

    hits = infer_prompt_industries(OIL_GAS_PROMPT)
    assert "law_firm" not in hits
    assert "oil_gas_operations" in hits


def test_novel_domain_does_not_force_retail_pack() -> None:
    prompt = "An aquaculture fishery hatchery with pond batches and feed schedules"
    matched = match_domain_pack(prompt)
    assert matched is None
    ranked = rank_domain_packs(prompt)
    assert ranked[0][1] < 0.10


def test_coerce_bare_string_selection() -> None:
    field = {
        "ttype": "selection",
        "name": "x_type",
        "selection": "['drilling', 'refining', 'production']",
    }
    normalize_selection_field(field, context="x_branch.x_type")
    pairs = parse_selection_literal(field["selection"])
    assert pairs == [
        ("drilling", "Drilling"),
        ("refining", "Refining"),
        ("production", "Production"),
    ]


def test_scorecard_penalizes_pack_mismatch() -> None:
    pack = load_domain_pack("retail_supermarket")
    assert pack is not None
    draft: dict[str, Any] = {
        "domain_pack": "retail_supermarket",
        "display_name": "Retail Supermarket",
        "_user_prompt": OIL_GAS_PROMPT,
        "depends": ["base", "contacts", "mail", "product", "hr"],
        "models": list(copy.deepcopy(pack.get("models") or []))[:3],
    }
    sc = draft_scorecard(draft, user_prompt=OIL_GAS_PROMPT)
    assert sc["dimensions"]["domain_fit"] <= 3.0
    assert sc["score_0_10"] <= 4.0


def test_depth_model_floor_excludes_depth_seed_only() -> None:
    draft = {
        "models": [
            {
                "model": f"x_event_{i}",
                "source": "depth_seed",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_date", "ttype": "date"},
                    {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
                    {"name": "x_notes", "ttype": "text"},
                ],
            }
            for i in range(6)
        ],
        "_ambition": "standard",
    }
    assert "depth_models" in depth_gaps(draft, "standard")


def test_noun_expand_adds_branch_model() -> None:
    draft = _load_fixture()
    notes = expand_uncovered_noun_models(draft, SUPERMARKET_PROMPT)
    assert notes
    assert any(m.get("model") == "x_branch" for m in draft["models"])


def test_infer_product_reuse_when_installed() -> None:
    decisions, _notes, _cat = infer_stock_reuse(
        SUPERMARKET_PROMPT,
        available_models=["product.template", "product.product", "res.partner"],
        installed_modules=["base", "product", "contacts"],
    )
    models = {d["model"] for d in decisions}
    assert "product.template" in models or "product.product" in models


def test_infer_product_absent_notes_custom() -> None:
    _decisions, notes, _cat = infer_stock_reuse(
        "Supermarket product catalog",
        available_models=["res.partner"],
        installed_modules=["base", "contacts"],
    )
    assert any("product" in n.lower() for n in notes)


def test_infer_product_installable_not_installed_offers_install() -> None:
    decisions, notes, _cat = infer_stock_reuse(
        "Supermarket product catalog",
        available_models=["res.partner"],
        installed_modules=["base", "contacts"],
    )
    installable = [d for d in decisions if d.get("source") == "installable"]
    assert installable
    assert any(d.get("model") in {"product.template", "product.product"} for d in installable)
    assert any("install and reuse" in n for n in notes)


def test_pack_product_template_wins_over_noun_inference() -> None:
    pack_stock = [
        {
            "model": "product.template",
            "modules": ["product"],
            "reason": "Product catalog (domain pack)",
            "forbid_parallel": ["x_product", "x_product_template"],
        }
    ]
    decisions, _notes, _cat = infer_stock_reuse(
        SUPERMARKET_PROMPT,
        available_models=["product.template", "product.product", "res.partner"],
        installed_modules=["base", "product", "contacts"],
        pack_reuse_stock=pack_stock,
    )
    pt = next((d for d in decisions if d.get("model") == "product.template"), None)
    assert pt is not None
    assert pt.get("source") == "pack_reuse_stock"
    assert pt.get("reason") == "Product catalog (domain pack)"


def test_rejected_models_skip_inference() -> None:
    decisions, notes, _cat = infer_stock_reuse(
        SUPERMARKET_PROMPT,
        available_models=["product.template", "res.partner"],
        installed_modules=["base", "product", "contacts"],
        rejected_models=["product.template"],
    )
    assert not any(d.get("model") == "product.template" for d in decisions)
    assert any("skipped product.template" in n for n in notes)


def test_plan_reuse_installable_decision() -> None:
    plan = plan_reuse(
        "Track employee expenses and reimbursements",
        available_models=["res.partner"],
        installed_modules=["base", "contacts"],
        operator_reuse=[],
    )
    installable = [d for d in plan.decisions if d.source == "installable"]
    assert installable
    expense = next(d for d in installable if d.model == "hr.expense")
    assert expense.required_module == "hr_expense"


def test_install_one_keeps_sibling_installables() -> None:
    """Confirming Install & reuse on one model must not drop other installables."""
    prior = plan_reuse(
        "supermarket products inventory purchase",
        available_models=["res.partner"],
        installed_modules=["base", "contacts"],
        operator_reuse=[],
    )
    prior_meta = [
        {
            "model": d.model,
            "reason": d.reason,
            "source": d.source,
            "confirmed": d.confirmed,
            "module": d.required_module,
            "link_only": d.link_only,
            "forbid_parallel": list(d.forbid_parallel),
        }
        for d in prior.decisions
    ]
    after = plan_reuse(
        "supermarket products inventory purchase",
        available_models=["res.partner"],
        installed_modules=["base", "contacts"],
        operator_reuse=["product.template"],
        prior_decisions=prior_meta,
    )
    pending = [
        d.model
        for d in after.decisions
        if d.source == "installable" and not d.confirmed
    ]
    assert "product.template" not in pending
    assert any(d.model == "product.template" and d.confirmed for d in after.decisions)
    assert "stock.warehouse" in pending or "purchase.order" in pending


def test_confirm_one_operator_model_keeps_pending_installables() -> None:
    """Wizard must send only clicked chips as operator_reuse — not plan.models."""
    prior = plan_reuse(
        "supermarket products inventory purchase",
        available_models=["res.partner"],
        installed_modules=["base", "contacts"],
        operator_reuse=[],
    )
    prior_meta = [
        {
            "model": d.model,
            "reason": d.reason,
            "source": d.source,
            "confirmed": d.confirmed,
            "module": d.required_module,
            "link_only": d.link_only,
            "forbid_parallel": list(d.forbid_parallel),
        }
        for d in prior.decisions
    ]
    pending_before = {
        d.model
        for d in prior.decisions
        if d.source == "installable" and not d.confirmed
    }
    assert len(pending_before) >= 2
    # Click one installable only (fixed UI). Dumping plan.models would confirm all.
    click = sorted(pending_before)[0]
    after = plan_reuse(
        "supermarket products inventory purchase",
        available_models=["res.partner"],
        installed_modules=["base", "contacts"],
        operator_reuse=[click],
        prior_decisions=prior_meta,
    )
    pending_after = {
        d.model
        for d in after.decisions
        if d.source == "installable" and not d.confirmed
    }
    assert click not in pending_after
    assert pending_before - {click} <= pending_after or len(pending_after) >= 1


def test_pack_reuse_stock_surfaces_in_plan() -> None:
    pack_stock = [
        {
            "model": "purchase.order",
            "modules": ["purchase"],
            "reason": "Supplier purchase orders (link-only)",
            "link_only": True,
        }
    ]
    plan = plan_reuse(
        SUPERMARKET_PROMPT,
        available_models=["purchase.order", "product.template", "res.partner"],
        installed_modules=["base", "product", "purchase", "contacts"],
        operator_reuse=[],
        pack_reuse_stock=pack_stock,
    )
    pack_rows = [d for d in plan.decisions if d.source == "pack_reuse_stock"]
    assert pack_rows
    assert any(d.model == "purchase.order" for d in pack_rows)
    assert not any(d.confirmed for d in pack_rows)

def test_confirmed_product_reuse_forbids_x_product() -> None:
    plan = plan_reuse(
        "Mega supermarket with product catalog and inventory",
        available_models=["product.product", "product.template", "res.partner"],
        installed_modules=["base", "product", "contacts"],
        operator_reuse=["product.product"],
    )
    assert "x_product" in plan.forbid_new_models
    draft = {
        "models": [
            {"model": "x_product", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_store_order", "fields": [{"name": "x_name", "ttype": "char"}]},
        ]
    }
    notes = apply_reuse_plan(draft, plan)
    assert notes
    assert not any(m.get("model") == "x_product" for m in draft["models"])


def test_invoice_inference_link_only() -> None:
    decisions, _notes, _cat = infer_stock_reuse(
        "Track customer invoices and billing",
        available_models=["account.move", "res.partner"],
        installed_modules=["base", "account", "contacts"],
    )
    inv = next((d for d in decisions if d["model"] == "account.move"), None)
    assert inv is not None
    assert inv.get("link_only") is True


def test_inferred_available_stock_forbids_parallel() -> None:
    """Stock on the instance is reused — do not wait for an operator confirm to drop clones."""
    plan = plan_reuse(
        "Mega grocery branches nationwide",
        available_models=["product.product", "res.partner"],
        installed_modules=["base", "product", "contacts"],
        operator_reuse=[],
    )
    inferred = [d for d in plan.decisions if d.source == "inferred"]
    assert inferred
    assert "product.product" in plan.models
    assert "x_product" in plan.forbid_new_models


def test_installable_missing_module_does_not_forbid() -> None:
    plan = plan_reuse(
        "Hospital with appointments and invoicing",
        available_models=["res.partner", "res.users", "res.company", "res.currency"],
        installed_modules=["base", "contacts", "mail"],
    )
    assert "account.move" not in plan.models
    assert "x_invoice" not in plan.forbid_new_models


def test_reapply_reuse_endpoint_collapses_parallel_without_llm() -> None:
    import os

    from fastapi.testclient import TestClient

    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
    )
    os.environ.setdefault("FERNET_KEY", "dev-only-test")
    os.environ.setdefault("AUTH_MODE", "off")

    from app.main import app

    draft = {
        "technical_name": "demo",
        "models": [
            {"model": "x_product", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_store_order", "fields": [{"name": "x_name", "ttype": "char"}]},
        ],
    }
    with TestClient(app) as client:
        res = client.post(
            "/api/ai/reapply-reuse",
            json={
                "prompt": "Mega supermarket with product catalog",
                "draft": draft,
                "reuse_models": ["product.product"],
                "rejected_reuse_models": [],
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    models = {m["model"] for m in body["draft"]["models"]}
    assert "x_product" not in models
    assert body["draft"]["reuse"]["plan"]["decisions"]
    assert isinstance(body["draft"].get("_scorecard"), dict)
    assert float(body["draft"]["_scorecard"].get("score_0_10") or 0) >= 0
    assert any(
        d.get("model") == "product.product" and d.get("confirmed")
        for d in body["draft"]["reuse"]["plan"]["decisions"]
    )
