"""Wave 16 GEN2 — LLM reliability + semantic fidelity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.ai_llm_status import banner_for_mode, sanitize_draft_payload
from app.ai_reuse_planner import plan_reuse
from app.ai_stock_catalog import infer_catalog_reuse, stock_entry
from app.ai_stock_reuse import infer_stock_reuse
from app.ai_workflow_semantic import apply_semantic_workflow_pass, synthesize_semantic_transitions, classify_state
from app.ai_rules import validate_and_enrich_draft
from app.llm_provider import LLMError, generate_json_with_timeout_retry

FIXTURE2 = Path(__file__).parent / "fixtures" / "draft_supermarket2_2026-08-05.json"
SUPERMARKET_PROMPT = "A large mega Super Market with multiple branches"


def _load_fixture2() -> dict[str, Any]:
    return json.loads(FIXTURE2.read_text())


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
