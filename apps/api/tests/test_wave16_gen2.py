"""Wave 16 GEN2 — LLM reliability + semantic fidelity."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.ai_depth import (
    ensure_country_on_branch_for_global_prompt,
    ensure_min_automations,
)
from app.ai_enrich import (
    _build_form_arch,
    drop_redundant_role_name_fields,
    ensure_default_ui,
)
from app.ai_ollama import derive_draft_naming_from_prompt
from app.ai_model_quality import drop_redundant_role_name_fields as drop_role_names_draft
from app.ai_llm_status import (
    banner_for_mode,
    finalize_llm_status,
    sanitize_draft_payload,
    validate_draft_response_shape,
)
from app.ai_reuse_planner import plan_reuse
from app.ai_stock_catalog import infer_catalog_reuse, stock_entry
from app.ai_stock_reuse import infer_stock_reuse
from app.ai_workflow_semantic import apply_semantic_workflow_pass, synthesize_semantic_transitions, classify_state
from app.ai_rules import validate_and_enrich_draft
from app.llm_provider import LLMError, generate_json_with_timeout_retry

FIXTURE2 = Path(__file__).parent / "fixtures" / "draft_supermarket2_2026-08-05.json"
FIXTURE3 = Path(__file__).parent / "fixtures" / "draft_supermarket3_2026-08-06.json"
FIXTURE4 = Path(__file__).parent / "fixtures" / "draft_supermarket4_2026-08-06.json"
FIXTURE5 = Path(__file__).parent / "fixtures" / "draft_supermarket5_2026-08-07.json"
FIXTURE6 = Path(__file__).parent / "fixtures" / "draft_supermarket6_2026-08-08.json"
LAW_FIRM_GOLD = Path(__file__).resolve().parents[3] / "docs" / "reference" / "law_firm_modulespec_gold.json"
SUPERMARKET_PROMPT = "A large mega Super Market with multiple branches"
SUPERMARKET3_PROMPT = "A large, mega super market with multiple branches around the world"


def _load_fixture2() -> dict[str, Any]:
    return json.loads(FIXTURE2.read_text())


def _load_fixture3() -> dict[str, Any]:
    return json.loads(FIXTURE3.read_text())


def _load_fixture4() -> dict[str, Any]:
    return json.loads(FIXTURE4.read_text())


def _load_fixture5() -> dict[str, Any]:
    return json.loads(FIXTURE5.read_text())


def _load_fixture6() -> dict[str, Any]:
    return json.loads(FIXTURE6.read_text())


def _load_law_firm_gold() -> dict[str, Any]:
    return json.loads(LAW_FIRM_GOLD.read_text())


def test_sanitize_removes_top_level_error() -> None:
    draft = {"error": "Invalid JSON", "models": []}
    clean = sanitize_draft_payload(draft)
    assert "error" not in clean
    assert clean["models"] == []


def test_semantic_transitions_terminals_have_no_outgoing() -> None:
    keys = ["draft", "confirmed", "delivered", "cancelled"]
    transitions, visible = synthesize_semantic_transitions(keys)
    terminal = {"delivered", "cancelled"}
    for a, _b in transitions:
        assert a not in terminal
    assert "delivered" in visible
    assert "cancelled" not in visible


def test_supermarket2_fixture_semantic_pass() -> None:
    draft = _load_fixture2()
    notes = apply_semantic_workflow_pass(draft)
    assert notes
    order = next(m for m in draft["models"] if m["model"] == "x_sales_order")
    tr = order["state_field"]["transitions"]
    assert not any(a == "delivered" for a, _ in tr)
    party = next(m for m in draft["models"] if m["model"] == "x_party_role")
    assert "state_field" not in party


def test_pack_reuse_stock_link_only_propagation() -> None:
    pack_stock = [
        {"model": "purchase.order", "modules": ["purchase"], "link_only": True},
        {"model": "stock.warehouse", "modules": ["stock"], "link_only": True},
    ]
    plan = plan_reuse(
        SUPERMARKET_PROMPT,
        available_models=["purchase.order", "stock.warehouse", "res.partner"],
        installed_modules=["base", "purchase", "stock", "contacts"],
        pack_reuse_stock=pack_stock,
    )
    by_model = {d.model: d for d in plan.decisions}
    assert by_model["purchase.order"].link_only is True
    assert by_model["stock.warehouse"].link_only is True


def test_catalog_noise_not_in_plan_decisions() -> None:
    rows = [
        stock_entry("report.account.report_invoice", "Invoice report"),
        stock_entry("res.role", "Role"),
        stock_entry("crm.lead", "Lead"),
    ]
    decisions, _notes, catalog = infer_stock_reuse(
        "CRM leads for supermarket promotions",
        available_models=[r["model"] for r in rows],
        stock_catalog=rows,
    )
    assert not any(str(d.get("model", "")).startswith("report.") for d in decisions)
    assert any(c.get("model") == "crm.lead" for c in catalog)


def test_infer_catalog_excludes_report_models() -> None:
    rows = [stock_entry("report.account.report_invoice_with_payments", "Invoice")]
    hits = infer_catalog_reuse(
        SUPERMARKET_PROMPT,
        rows,
        available_models={"report.account.report_invoice_with_payments"},
    )
    assert hits == []


def test_access_rules_user_no_unlink() -> None:
    draft = {
        "technical_name": "demo_shop",
        "display_name": "Demo Shop",
        "models": [{"model": "x_item", "description": "Item", "fields": []}],
    }
    out, _notes, _errs = validate_and_enrich_draft(draft)
    rules = out.get("access_rules") or []
    user_rules = [r for r in rules if str(r.get("id", "")).endswith("_user")]
    assert user_rules
    assert all(r.get("perm_unlink") == 0 for r in user_rules)
    mgr_rules = [r for r in rules if str(r.get("id", "")).endswith("_manager")]
    assert mgr_rules


def test_banner_modes() -> None:
    assert "timed out" in (banner_for_mode("llm_partial") or "")
    assert "template" in (banner_for_mode("pack_fallback") or "")
    assert banner_for_mode("seed_fallback", seeded=False) is None


def test_timeout_retry_downshift(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = MagicMock()
    provider.generate_json.side_effect = [
        LLMError("Ollama request timed out"),
        '{"ok": true}',
    ]
    monkeypatch.setattr("app.llm_provider.resolve_bulk_model", lambda: "qwen3:14b")
    raw = generate_json_with_timeout_retry(provider, "test prompt", timeout_s=30.0)
    assert raw == '{"ok": true}'
    assert provider.generate_json.call_count == 2


def test_llm_status_never_error_in_success_response() -> None:
    draft = _load_fixture2()
    clean = sanitize_draft_payload(draft)
    assert "error" not in clean
    assert clean.get("_llm_status", {}).get("mode") == "pack_fallback"


def test_hub_anchor_seeds_optional_fk() -> None:
    from app.ai_depth import seed_operational_loop_models

    draft = {
        "technical_name": "demo_shop",
        "models": [
            {
                "model": "x_branch",
                "description": "Branch",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_sales_order",
                "description": "Sales order",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_branch_id", "ttype": "many2one", "relation": "x_branch"},
                ],
            },
            {
                "model": "x_branch_transfer",
                "description": "Transfer",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_branch_id", "ttype": "many2one", "relation": "x_branch"},
                ],
            },
        ],
    }
    seed_operational_loop_models(
        draft, "comprehensive", user_prompt=SUPERMARKET_PROMPT
    )
    event = next((m for m in draft["models"] if m["model"] == "x_event"), None)
    assert event is not None
    branch_fk = next(f for f in event["fields"] if f.get("relation") == "x_branch")
    assert branch_fk.get("required") is False


def test_vocab_scrub_bans_law_firm_terms_on_retail() -> None:
    from app.ai_vocab_scrub import derive_domain_prefix, scrub_draft_vocabulary

    draft = {
        "models": [
            {
                "model": "x_order",
                "description": "Retainer deposit for matter hearing",
                "fields": [{"name": "x_name", "string": "Matter name", "ttype": "char"}],
            }
        ]
    }
    pack = {"vocab": {"deposit": "Supplier deposit", "compliance": "Food safety check"}}
    notes = scrub_draft_vocabulary(draft, pack=pack)
    assert notes
    assert "retainer" not in draft["models"][0]["description"].lower()
    assert "matter" not in draft["models"][0]["description"].lower()
    prefix = derive_domain_prefix(
        "A large mega Super Market with multiple branches", pack=pack
    )
    assert prefix != "Super"
    assert "Super" in prefix or "Market" in prefix


def test_law_firm_semantic_transitions_no_regression() -> None:
    """Matter-style status keys: closed is terminal — no forward chain from it."""
    keys = [
        "intake",
        "conflict_check",
        "open",
        "discovery",
        "trial",
        "settlement",
        "closed",
        "on_hold",
    ]
    transitions, visible = synthesize_semantic_transitions(keys)
    assert "closed" in visible
    assert not any(a == "closed" for a, _b in transitions)
    assert any(a == "on_hold" and b == "closed" for a, b in transitions)
    for a, _b in transitions:
        assert classify_state(a) == "active"


def test_line_total_compute_suggestion() -> None:
    from app.ai_presentation import suggest_line_total_compute

    draft = {
        "models": [
            {
                "model": "x_sales_order_line",
                "fields": [
                    {"name": "x_qty", "ttype": "float"},
                    {"name": "x_price", "ttype": "float"},
                    {"name": "x_subtotal", "ttype": "float"},
                ],
            }
        ]
    }
    notes = suggest_line_total_compute(draft)
    assert notes
    assert draft.get("_compute_suggestions")


def test_root_menu_visible_to_user_group() -> None:
    draft = {
        "technical_name": "demo_shop",
        "display_name": "Demo Shop",
        "models": [{"model": "x_item", "description": "Item", "fields": []}],
        "menus": [{"name": "Demo Shop", "sequence": 10, "technical_name": "root_demo_shop"}],
    }
    out, _warnings, _errs = validate_and_enrich_draft(draft)
    root = next(m for m in out["menus"] if not m.get("parent_xml_id"))
    assert "group_demo_shop_user" in (root.get("groups") or [])


def test_module_zip_root_menu_has_groups() -> None:
    from app.module_spec_codec import export_draft_module_zip

    draft = {
        "technical_name": "demo_shop",
        "display_name": "Demo Shop",
        "models": [{"model": "x_item", "description": "Item", "fields": []}],
        "menus": [
            {
                "name": "Demo Shop",
                "sequence": 10,
                "technical_name": "root_demo_shop",
                "groups": ["group_demo_shop_user"],
            }
        ],
        "groups": [
            {"id": "group_demo_shop_user", "name": "Demo Shop User"},
            {"id": "group_demo_shop_manager", "name": "Demo Shop Manager", "implied_ids": ["group_demo_shop_user"]},
        ],
        "access_rules": [
            {
                "id": "access_x_item_user",
                "name": "Item user",
                "model": "model_x_item",
                "group": "group_demo_shop_user",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 0,
            }
        ],
    }
    import io
    import zipfile

    blob = export_draft_module_zip(draft)
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        menus_xml = zf.read("demo_shop/views/menus.xml").decode()
        groups_xml = zf.read("demo_shop/security/groups.xml").decode()
    assert "demo_shop.group_demo_shop_user" in menus_xml
    assert "group_demo_shop_user" in groups_xml


def test_enrich_job_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_enrich_jobs import enqueue_enrich_job
    from app.db import SessionLocal

    captured: dict[str, object] = {}

    def fake_enqueue(job_id: str, fn: object) -> None:
        captured["job_id"] = job_id
        captured["fn"] = fn

    monkeypatch.setattr("app.ai_enrich_jobs.enqueue", fake_enqueue)
    db = SessionLocal()
    try:
        job_id = enqueue_enrich_job(
            db,
            connection_id=None,
            prompt="test prompt",
            draft={"models": [], "technical_name": "t"},
            failed_steps=["quality"],
        )
        assert job_id
        assert captured.get("job_id") == job_id
    finally:
        db.close()


def test_enqueue_draft_job_skips_odoo_client_deepcopy(monkeypatch: pytest.MonkeyPatch) -> None:
    import xmlrpc.client
    from unittest.mock import patch

    from app.ai_draft_jobs import enqueue_draft_job
    from app.db import SessionLocal

    rpc_client = xmlrpc.client.ServerProxy("http://127.0.0.1:9999", allow_none=True)
    captured: dict[str, object] = {}

    def fake_enqueue(job_id: str, fn: object) -> None:
        captured["job_id"] = job_id
        captured["fn"] = fn

    monkeypatch.setattr("app.ai_draft_jobs.enqueue", fake_enqueue)
    db = SessionLocal()
    try:
        job_id = enqueue_draft_job(
            db,
            connection_id=None,
            body_kwargs={
                "prompt": "Simple task tracker",
                "available_models": None,
                "installed_modules": None,
                "stock_catalog": None,
                "reuse_models": None,
                "rejected_reuse_models": None,
                "reuse_views": None,
                "reuse_actions": None,
                "expand": True,
                "pipeline": None,
                "protected_manifest": None,
                "odoo_version": None,
                "grain_override": None,
                "gallery_id": None,
                "host_model_override": None,
                "connect_points_override": None,
                "client": rpc_client,
                "connection_id": None,
            },
        )
        assert job_id
        assert captured.get("job_id") == job_id
        with patch("app.ai_draft_jobs._resolve_odoo_client", return_value=None), patch(
            "app.ai_draft_jobs.run_draft_job_body",
            return_value={"ok": True, "draft": {}},
        ) as run_body:
            fn = captured["fn"]
            assert callable(fn)
            fn()
            run_body.assert_called_once()
            assert run_body.call_args.kwargs["client"] is None
    finally:
        db.close()


def test_llm_timeout_falls_back_to_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_ollama import draft_module_from_prompt
    from app.llm_provider import LLMError

    class _TimeoutProvider:
        def generate_json(self, *args: object, **kwargs: object) -> str:
            raise LLMError("Ollama request timed out")

    monkeypatch.setattr("app.ai_ollama.get_llm_provider", lambda: _TimeoutProvider())
    draft, _raw, warnings, _refusals = draft_module_from_prompt(
        SUPERMARKET_PROMPT,
        reuse_models=["res.partner"],
        expand=False,
    )
    assert draft.get("domain_pack") == "retail_supermarket" or any(
        "domain pack" in w.lower() for w in warnings
    )
    assert draft.get("_llm_status", {}).get("mode") == "pack_fallback"
    assert "error" not in draft


def test_supermarket3_fixture_has_root_model_leak_before_sanitize() -> None:
    raw = _load_fixture3()
    assert raw.get("model") == "x_branch"
    assert isinstance(raw.get("models"), list)
    assert raw.get("fields")


def test_validate_draft_response_shape_strips_supermarket3_leak() -> None:
    raw = _load_fixture3()
    clean, warnings = validate_draft_response_shape(raw)
    assert "model" not in clean
    assert "fields" not in clean or "fields" in (clean.get("models") or [{}])[0]
    assert not any(k in clean for k in ("is_workflow", "state_field"))
    assert any("stripped model-level root keys" in w for w in warnings)
    meta = clean.get("_meta") or {}
    assert meta.get("smart_button_count") == len(clean.get("smart_buttons") or [])


def test_sanitize_draft_payload_strips_root_model_key_named_test() -> None:
    draft = {
        "model": "x_branch",
        "fields": [{"name": "x_name", "ttype": "char"}],
        "technical_name": "t",
        "display_name": "T",
        "models": [{"model": "x_branch", "fields": [{"name": "x_name", "ttype": "char"}]}],
    }
    clean = sanitize_draft_payload(draft)
    assert "model" not in clean
    assert "error" not in clean


def test_finalize_llm_status_populates_completed_steps() -> None:
    draft = {
        "models": [{"model": "x_a", "fields": []}],
        "_llm_status": {
            "mode": "llm_partial",
            "failed_steps": ["quality"],
            "completed_steps": [],
            "step": 0,
            "step_label": "Retrieving domain context",
            "step_total": 7,
        },
    }
    finalize_llm_status(draft, mode="llm_partial")
    status = draft["_llm_status"]
    assert status["step"] == 6
    assert status["step_label"] == "Finalizing draft"
    assert len(status["completed_steps"]) >= 6
    assert "Retrieving domain context" in status["completed_steps"]


def test_form_arch_statusbar_uses_state_field_visible_list() -> None:
    fields = [
        {"name": "x_name", "ttype": "char"},
        {
            "name": "x_status",
            "ttype": "selection",
            "selection": "[('draft','Draft'),('done','Done'),('cancelled','Cancelled')]",
        },
    ]
    arch = _build_form_arch(
        "Order",
        fields,
        statusbar_visible=["draft", "done"],
    )
    assert 'statusbar_visible="draft,done"' in arch
    assert "cancelled" not in arch.split("statusbar_visible")[1].split('"')[1]


def test_form_arch_splits_large_field_groups() -> None:
    fields = [{"name": "x_name", "ttype": "char"}]
    for i in range(12):
        fields.append({"name": f"x_detail_{i}", "ttype": "char", "string": f"Detail {i}"})
    fields.extend(
        [
            {"name": "x_phone", "ttype": "char", "string": "Phone"},
            {"name": "x_email", "ttype": "char", "string": "Email"},
            {"name": "x_address", "ttype": "char", "string": "Address"},
            {"name": "x_city", "ttype": "char", "string": "City"},
        ]
    )
    arch = _build_form_arch("Branch", fields)
    assert arch.count('group string="Contact"') >= 1
    assert arch.count('group string="Location"') >= 1
    assert 'group string="Details"' in arch


def test_drop_redundant_manager_name_when_manager_id_exists() -> None:
    fields = [
        {"name": "x_name", "ttype": "char"},
        {"name": "x_manager_id", "ttype": "many2one", "relation": "hr.employee"},
        {"name": "x_manager_name", "ttype": "char", "string": "Manager Name"},
        {"name": "x_phone", "ttype": "char"},
    ]
    pruned = drop_redundant_role_name_fields(fields)
    names = {f["name"] for f in pruned}
    assert "x_manager_id" in names
    assert "x_manager_name" not in names


def test_drop_redundant_role_name_fields_on_draft_and_views() -> None:
    draft = {
        "models": [
            {
                "model": "x_branch",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_manager_id", "ttype": "many2one", "relation": "hr.employee"},
                    {"name": "x_manager_name", "ttype": "char"},
                ],
            }
        ],
        "views": [
            {
                "model": "x_branch",
                "type": "form",
                "arch": '<form><field name="x_manager_name"/><field name="x_manager_id"/></form>',
            }
        ],
    }
    notes = drop_role_names_draft(draft)
    assert notes
    branch_fields = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_manager_name" not in branch_fields
    assert "x_manager_name" not in draft["views"][0]["arch"]


def test_global_prompt_adds_country_on_branch() -> None:
    draft = {
        "models": [
            {
                "model": "x_branch",
                "description": "Branch / Store location",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ]
    }
    notes = ensure_country_on_branch_for_global_prompt(draft, SUPERMARKET3_PROMPT)
    assert notes
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_country_id" in names
    country = next(f for f in draft["models"][0]["fields"] if f["name"] == "x_country_id")
    assert country["relation"] == "res.country"


def test_technical_name_drops_stop_words_around_world() -> None:
    draft: dict[str, Any] = {"technical_name": "custom_app"}
    derive_draft_naming_from_prompt(draft, SUPERMARKET3_PROMPT)
    slug = draft["technical_name"]
    assert "around" not in slug
    assert "world" not in slug
    assert "the" not in slug.split("_")


def test_comprehensive_automation_prefers_workflow_over_on_create() -> None:
    draft = {
        "models": [
            {
                "model": "x_store_order",
                "description": "Store order",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('delivered','Delivered'),('cancelled','Cancelled')]",
                    },
                ],
                "state_field": {
                    "field": "x_status",
                    "statusbar_visible": ["draft", "delivered"],
                },
            }
        ],
        "automations": [],
    }
    notes = ensure_min_automations(draft, "comprehensive")
    assert notes
    triggers = [a.get("trigger") for a in draft["automations"]]
    assert "on_write" in triggers
    workflow_auto = next(a for a in draft["automations"] if a.get("trigger") == "on_write")
    assert workflow_auto.get("filter_domain")
    assert "delivered" in str(workflow_auto.get("filter_domain"))


def test_supermarket3_fixture_form_rebuild_drops_manager_name() -> None:
    draft = _load_fixture3()
    draft.pop("model", None)
    for key in ("fields", "automations", "smart_buttons", "is_workflow", "state_field"):
        draft.pop(key, None)
    ensure_default_ui(draft)
    branch = next(m for m in draft["models"] if m["model"] == "x_branch")
    assert "x_manager_name" not in {f["name"] for f in branch["fields"]}
    form = next(v for v in draft["views"] if v["model"] == "x_branch" and v["type"] == "form")
    assert "x_manager_name" not in form["arch"]
    assert 'group string="Contact"' in form["arch"] or 'group string="Location"' in form["arch"]


def test_finalize_critique_removes_ghost_repairs_from_fixture4() -> None:
    from app.ai_critique import finalize_critique_block

    draft = _load_fixture4()
    repairs_before = list((draft.get("_critique") or {}).get("repairs") or [])
    assert any("x_warehouse_id" in r for r in repairs_before)
    finalize_critique_block(draft)
    crit = draft["_critique"]
    repairs = crit.get("repairs") or []
    suggestions = crit.get("suggestions") or []
    for repair in repairs:
        if repair.startswith("critique: added field"):
            _, rest = repair.split("added field ", 1)
            mid, fname = rest.split(".", 1)
            model = next(m for m in draft["models"] if m["model"] == mid)
            assert fname in {f["name"] for f in model["fields"]}
        elif repair.startswith("critique: added automation"):
            name = repair.split("added automation ", 1)[1]
            assert name in {a.get("name") for a in draft.get("automations") or []}
    assert any("unapplied" in s and "x_warehouse_id" in s for s in suggestions)


def test_supermarket4_fixture_sync_form_includes_enrichment_fields() -> None:
    from app.ai_enrich import sync_form_archs_to_models

    draft = _load_fixture4()
    sync_form_archs_to_models(draft)
    branch = next(m for m in draft["models"] if m["model"] == "x_branch")
    stored = {
        f["name"]
        for f in branch["fields"]
        if f.get("ttype") not in {"one2many", "many2many"}
    }
    form = next(v for v in draft["views"] if v["model"] == "x_branch" and v["type"] == "form")
    arch_names = set(re.findall(r'name="(x_[^"]+)"', form["arch"]))
    assert stored <= arch_names
    assert "x_timezone" in arch_names
    assert 'group string="Contact"' in form["arch"] or 'group string="Details"' in form["arch"]


def test_supermarket4_fixture_statusbar_hides_cancelled_on_pack_views() -> None:
    from app.ai_enrich import sync_form_archs_to_models

    draft = _load_fixture4()
    apply_semantic_workflow_pass(draft)
    sync_form_archs_to_models(draft)
    for mid in ("x_store_order", "x_promotion", "x_branch_transfer"):
        model = next(m for m in draft["models"] if m["model"] == mid)
        visible = model["state_field"]["statusbar_visible"]
        assert "cancelled" not in visible
        form = next(v for v in draft["views"] if v["model"] == mid and v["type"] == "form")
        sb = re.search(r'statusbar_visible="([^"]+)"', form["arch"])
        assert sb is not None
        assert "cancelled" not in sb.group(1)


def test_reuse_stock_warehouse_field_not_dropped_as_orphan() -> None:
    from app.ai_model_quality import repair_orphan_relations

    draft = {
        "reuse": {"models": ["stock.warehouse"]},
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


def test_vocab_scrub_no_expense_slash_expense_duplicate() -> None:
    from app.ai_vocab_scrub import scrub_text

    out, changed = scrub_text("Disbursement / expense tracking", {})
    assert changed
    assert "expense / expense" not in out.lower()
    assert "expense" in out.lower()


def test_vocab_scrub_collapses_expenses_and_expenses() -> None:
    from app.ai_vocab_scrub import scrub_text

    out, changed = scrub_text("Store expenses and expenses", {})
    assert changed
    assert out.lower() == "store expenses"


# --- GEN2-10 / GEN2-11 / GEN2-12 ---


def test_fixture5_post_critique_scaffolds_critique_models() -> None:
    import copy

    from app.ai_post_critique import run_post_critique_pipeline

    draft = copy.deepcopy(_load_fixture5())
    run_post_critique_pipeline(draft, user_prompt=SUPERMARKET3_PROMPT)
    models = {m["model"] for m in draft["models"]}
    actions = {a.get("model") for a in draft.get("actions") or []}
    for mid in (
        "x_branch_transfer_line",
        "x_compliance_check",
        "x_event_registration",
        "x_inventory_adjustment",
    ):
        assert mid in models
        assert mid in actions
    views = {}
    for v in draft.get("views") or []:
        views.setdefault(v["model"], set()).add(v.get("type"))
    for mid in (
        "x_branch_transfer_line",
        "x_compliance_check",
        "x_event_registration",
        "x_inventory_adjustment",
    ):
        assert "form" in views.get(mid, set())
        assert views.get(mid, set()) & {"list", "tree"}


def test_fixture5_line_model_gets_parent_m2o() -> None:
    import copy

    from app.ai_post_critique import ensure_line_model_parent_links

    draft = copy.deepcopy(_load_fixture5())
    ensure_line_model_parent_links(draft)
    line = next(m for m in draft["models"] if m["model"] == "x_branch_transfer_line")
    rels = {
        f.get("relation")
        for f in line.get("fields") or []
        if f.get("ttype") == "many2one"
    }
    assert "x_branch_transfer" in rels
    assert "x_from_branch_id" not in {f.get("name") for f in line.get("fields") or []}


def test_noun_stopwords_exclude_around_world() -> None:
    from app.ai_domain_nouns import domain_noun_coverage

    draft = _load_fixture5()
    items, uncovered, _w = domain_noun_coverage(draft, SUPERMARKET3_PROMPT)
    ids = {i["id"] for i in items}
    assert "noun_uncovered:around" not in ids
    assert "noun_uncovered:world" not in ids
    assert "around" not in uncovered
    assert "world" not in uncovered


def test_lifecycle_orders_planned_before_closed() -> None:
    from app.ai_workflow_semantic import order_states_by_lifecycle

    keys = ["closed", "planned", "open"]
    ordered = order_states_by_lifecycle(keys)
    assert ordered.index("planned") < ordered.index("open") < ordered.index("closed")


def test_transition_button_uses_target_label_not_complete() -> None:
    from app.ai_workflow import transition_button_label

    assert transition_button_label("open", "closed") == "Closed"
    assert transition_button_label("active", "done") == "Done"


def test_production_shape_adds_search_views() -> None:
    import copy

    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    draft = copy.deepcopy(_load_fixture5())
    run_post_critique_pipeline(draft, user_prompt=SUPERMARKET3_PROMPT)
    run_production_shape_pass(draft)
    action_models = {a.get("model") for a in draft.get("actions") or []}
    search_models = {
        v.get("model")
        for v in draft.get("views") or []
        if v.get("type") == "search"
    }
    assert action_models.issubset(search_models)
    sample = next(v for v in draft["views"] if v.get("type") == "search")
    assert sample["arch"].count("<filter") >= 2


def test_scorecard_fixture5_floor_after_passes() -> None:
    import copy

    from app.ai_draft_scorecard import draft_scorecard
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    raw = draft_scorecard(_load_fixture5(), user_prompt=SUPERMARKET3_PROMPT)
    assert raw["score_0_10"] >= 5.8
    draft = copy.deepcopy(_load_fixture5())
    run_post_critique_pipeline(draft, user_prompt=SUPERMARKET3_PROMPT)
    run_production_shape_pass(draft)
    scored = draft_scorecard(draft, user_prompt=SUPERMARKET3_PROMPT)
    assert scored["score_0_10"] >= 9.5


def test_apply_readiness_company_rules_match_fields() -> None:
    import copy

    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    draft = copy.deepcopy(_load_fixture5())
    run_post_critique_pipeline(draft, user_prompt=SUPERMARKET3_PROMPT)
    run_production_shape_pass(draft)
    branch = next(m for m in draft["models"] if m["model"] == "x_branch")
    names = {f["name"] for f in branch["fields"]}
    assert "x_company_id" in names
    assert "company_id" not in names
    rule = next(r for r in draft["record_rules"] if r.get("model") == "x_branch")
    assert "x_company_id" in rule["domain_force"]
    assert "('company_id'" not in rule["domain_force"]


def test_apply_readiness_dedupes_transfer_smart_buttons() -> None:
    import copy

    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    draft = copy.deepcopy(_load_fixture5())
    run_post_critique_pipeline(draft, user_prompt=SUPERMARKET3_PROMPT)
    run_production_shape_pass(draft)
    labels = [
        b["label"]
        for b in draft.get("smart_buttons") or []
        if b.get("on_model") == "x_branch" and b.get("related_model") == "x_branch_transfer"
    ]
    assert len(labels) == len(set(labels))


def test_apply_readiness_fixture5_scores_ten() -> None:
    import copy

    from app.ai_draft_scorecard import draft_scorecard
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    draft = copy.deepcopy(_load_fixture5())
    run_post_critique_pipeline(draft, user_prompt=SUPERMARKET3_PROMPT)
    run_production_shape_pass(draft)
    scored = draft_scorecard(draft, user_prompt=SUPERMARKET3_PROMPT)
    assert scored["score_0_10"] >= 9.9
    assert not any("duplicate smart button" in f.get("detail", "") for f in scored["findings"])
    assert not any(
        "record rule uses company_id but model has x_company_id" in f.get("detail", "")
        for f in scored["findings"]
    )


def test_enrich_draft_sync_runs_production_shape() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    draft = {
        "technical_name": "sync_enrich_demo",
        "models": [
            {
                "model": "x_store_order_invoice",
                "is_workflow": True,
                "state_field": {
                    "selection": "[('draft','Draft'),('sent','Sent'),('paid','Paid')]",
                },
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "anti_patterns": ["Do NOT implement payment capture — link purchase/sale documents only"],
        "_user_prompt": "mega supermarket",
    }
    with TestClient(app) as tc:
        res = tc.post(
            "/api/ai/enrich-draft",
            json={
                "prompt": "mega supermarket",
                "draft": draft,
                "connection_id": None,
                "failed_steps": [],
                "async_job": False,
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    out = body["draft"]
    assert isinstance(out.get("_scorecard"), dict)
    model_ids = {m["model"] for m in out.get("models") or []}
    assert "x_store_order_invoice" not in model_ids
    assert any("apply:" in w or "production:" in w for w in body.get("warnings") or [])


def test_llm_deepen_malformed_json_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_model_quality import llm_deepen_model_fields

    monkeypatch.setattr(
        "app.llm_provider.generate_json_with_timeout_retry",
        lambda *_a, **_k: '{"missing_fields":[{"model":"x_branch","name":}]}',
    )
    draft = {"models": [{"model": "x_branch", "fields": [{"name": "x_name", "ttype": "char"}]}]}
    out, notes = llm_deepen_model_fields(
        MagicMock(), draft, user_prompt="shop", ambition="standard", min_fields=6
    )
    assert out is draft
    assert any("malformed JSON" in n for n in notes)


def test_scorecard_regression_monotonic_supermarket_fixtures() -> None:
    from app.ai_draft_scorecard import draft_scorecard
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass
    import copy

    scores: list[float] = []
    for loader, prompt in (
        (_load_fixture2, SUPERMARKET_PROMPT),
        (_load_fixture3, SUPERMARKET3_PROMPT),
        (_load_fixture4, SUPERMARKET3_PROMPT),
        (_load_fixture5, SUPERMARKET3_PROMPT),
    ):
        d = copy.deepcopy(loader())
        run_post_critique_pipeline(d, user_prompt=prompt)
        run_production_shape_pass(d)
        scores.append(draft_scorecard(d, user_prompt=prompt)["score_0_10"])
    assert scores[-1] >= 8.0
    assert scores[-1] >= scores[0] - 1.0


def test_expert_review_improves_score_mocked() -> None:
    from app.expert.draft_review import review_draft

    draft = _load_fixture5()
    before = review_draft(draft, user_prompt=SUPERMARKET3_PROMPT, apply_fixes=False)
    after = review_draft(draft, user_prompt=SUPERMARKET3_PROMPT, apply_fixes=True)
    assert after.score_after is not None
    assert after.score_after >= before.score_before


def test_gen2_13_calibration_bands() -> None:
    """Known-bad fixtures must not score 10; post-shape fixture6 lands in honest band."""
    import copy

    from app.ai_draft_scorecard import draft_scorecard
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    raw6 = draft_scorecard(_load_fixture6(), user_prompt=SUPERMARKET3_PROMPT)
    assert raw6["score_0_10"] < 10.0
    assert raw6["validators"]["all_green"] is False

    shaped = copy.deepcopy(_load_fixture6())
    shaped["_user_prompt"] = SUPERMARKET3_PROMPT
    run_post_critique_pipeline(shaped, user_prompt=SUPERMARKET3_PROMPT)
    run_production_shape_pass(shaped)
    scored6 = draft_scorecard(shaped, user_prompt=SUPERMARKET3_PROMPT)
    assert scored6["score_0_10"] >= 9.5
    assert scored6["score_0_10"] < 10.0
    assert scored6["validators"]["all_green"] is True

    s2 = draft_scorecard(_load_fixture2(), user_prompt=SUPERMARKET_PROMPT)["score_0_10"]
    assert s2 < 8.5
    assert s2 < 10.0

    s4 = draft_scorecard(_load_fixture4(), user_prompt=SUPERMARKET3_PROMPT)["score_0_10"]
    assert 7.0 <= s4 <= 8.5

    law = draft_scorecard(_load_law_firm_gold(), user_prompt="law firm matter billing")["score_0_10"]
    assert law < 10.0

    shaped5 = copy.deepcopy(_load_fixture5())
    run_post_critique_pipeline(shaped5, user_prompt=SUPERMARKET3_PROMPT)
    run_production_shape_pass(shaped5)
    s5 = draft_scorecard(shaped5, user_prompt=SUPERMARKET3_PROMPT)["score_0_10"]
    assert s5 >= 9.5


def test_gen2_13_depth_metrics_not_swapped_after_shape() -> None:
    import copy

    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    draft = copy.deepcopy(_load_fixture6())
    run_post_critique_pipeline(draft, user_prompt=SUPERMARKET3_PROMPT)
    run_production_shape_pass(draft)
    depth = draft.get("_depth") or {}
    metrics = depth.get("metrics") or {}
    metrics_ns = depth.get("metrics_without_seeds") or {}
    assert int(metrics_ns.get("model_count") or 0) <= int(metrics.get("model_count") or 0)
