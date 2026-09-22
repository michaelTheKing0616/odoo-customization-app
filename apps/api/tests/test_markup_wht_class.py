"""P1 Job 2 — sale markup % + WHT-on-markup CLASS (parameterized mutants)."""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_generation_engine import classify_generation, maybe_seed_from_capability
from app.ai_grain import preferred_inherit_host
from app.ai_markup_wht_class import (
    CLASS_INTENT_ID,
    CLASS_MARKER,
    class_mutant_briefs,
    is_markup_wht_class_brief,
    online_metadata_incomplete_interim,
    scaffold_markup_wht_blocks,
    static_markup_wht_findings,
)
from app.ai_option_a_acceptance import (
    is_sales_markup_prompt,
    run_acceptance_smoke,
    stamp_option_a_acceptance,
)
from app.ai_option_a_gate import evaluate_authoring_gate
from app.ai_option_a_policy import policy_findings
from app.intent_router import route_intent
from app.intent_router.loader import reload_catalog


PURCHASE_ONLY = (
    "Add markup percent on purchase orders for vendor cost plus. Not sales."
)


@pytest.fixture(autouse=True)
def _reload():
    reload_catalog()
    yield
    reload_catalog()


def test_mutants_detect_as_class():
    for row in class_mutant_briefs():
        assert is_markup_wht_class_brief(row["prompt"]), row["id"]
        assert is_sales_markup_prompt(row["prompt"]), row["id"]
        assert preferred_inherit_host(row["prompt"]) == "sale.order", row["id"]


def test_purchase_only_not_this_class():
    assert is_markup_wht_class_brief(PURCHASE_ONLY) is False


def test_seed_attaches_class_scaffold_and_stamps():
    brief = class_mutant_briefs()[0]["prompt"]
    plan = classify_generation(brief)
    assert plan.capability == "option_a_authored"
    assert plan.module_delivery is True
    seed = maybe_seed_from_capability(brief)
    assert seed is not None
    assert seed.get("_pipeline") == "option_a_markup_wht_class"
    models = [m.get("model") for m in seed.get("models") or []]
    assert "sale.order" in models
    assert "purchase.order" not in models
    blob = "\n".join(str(b.get("content") or "") for b in seed.get("custom_code_blocks") or [])
    assert CLASS_MARKER in blob
    assert "x_markup_percent" in blob
    assert "x_wht_on_markup" in blob
    assert "account.tax" not in blob or ".create" not in blob
    assert "_inherit = \"purchase.order\"" not in blob
    ir = seed.get("_generation_engine") or {}
    assert ir.get("delivery_lane") == "module_sh_or_self"
    assert ir.get("artifact_kind") == "option_a_module"
    contract = seed.get("_option_a_acceptance") or {}
    assert contract.get("intent_id") == CLASS_INTENT_ID
    ids = {c["id"] for c in contract.get("checks") or []}
    assert "markup_present" in ids
    assert "wht_base_is_markup" in ids
    assert "purchase_untouched" in ids
    assert "no_tax_create" in ids


def test_all_mutants_seed_and_static_prove():
    for row in class_mutant_briefs():
        seed = maybe_seed_from_capability(row["prompt"])
        assert seed is not None, row["id"]
        findings = static_markup_wht_findings(seed, prompt=row["prompt"])
        assert findings["markup_present"], row["id"]
        assert findings["purchase_untouched"], row["id"]
        assert findings["no_tax_create"], row["id"]
        assert findings["wht_base_is_markup"], row["id"]


def test_acceptance_smoke_static_class_floor():
    brief = class_mutant_briefs()[1]["prompt"]
    seed = maybe_seed_from_capability(brief)
    assert seed is not None

    def _rpc_fail(*_a, **_k):
        raise RuntimeError("no live odoo in unit test")

    result = run_acceptance_smoke(seed, execute_kw=_rpc_fail)
    assert result["ok"] is True, result
    by_id = {c["id"]: c for c in result["checks"]}
    assert by_id["markup_present"]["ok"]
    assert by_id["wht_base_is_markup"]["ok"]
    assert by_id["purchase_untouched"]["ok"]
    assert by_id["no_tax_create"]["ok"]


def test_policy_and_gate_green_on_scaffold():
    brief = class_mutant_briefs()[0]["prompt"]
    seed = maybe_seed_from_capability(brief)
    assert seed is not None
    findings = policy_findings(seed)
    assert findings == [], findings
    # Authoring gate may still be pending until evaluate — call it
    payload = evaluate_authoring_gate(seed)
    assert payload.get("status") == "pass", payload
    assert not payload.get("findings"), payload.get("findings")


def test_tax_create_and_purchase_inherit_fail_static():
    draft = {
        "models": [{"model": "purchase.order", "mode": "inherit", "fields": []}],
        "custom_code_blocks": [
            {
                "source_file": "models/bad.py",
                "kind": "python",
                "content": (
                    "from odoo import models\n"
                    "class PO(models.Model):\n"
                    "    _inherit = 'purchase.order'\n"
                    "    def action_tax(self):\n"
                    "        self.env['account.tax'].create({'name': 'X'})\n"
                ),
            }
        ],
        "_user_prompt": class_mutant_briefs()[0]["prompt"],
        "_generation_engine": {"capability": "option_a_authored"},
    }
    stamp_option_a_acceptance(draft, prompt=draft["_user_prompt"])
    findings = static_markup_wht_findings(draft, prompt=draft["_user_prompt"])
    assert findings["purchase_untouched"] is False
    assert findings["no_tax_create"] is False
    assert any(f["code"] == "tax_create_forbidden" for f in policy_findings(draft))


def test_online_incomplete_interim_stamps():
    ir = online_metadata_incomplete_interim(
        prompt="Add markup % field on Sales via Studio"
    )
    assert ir["complete"] is False
    assert ir["interim"] is True
    assert ir["delivery_lane"] == "online_metadata"
    assert ir["module_lane_required"] is True
    assert ir["artifact_kind"] == "option_a_module"
    assert ir["prove_status"] == "pending"
    assert "Option A" in ir["operator_copy"] or "module" in ir["operator_copy"].lower()


def test_intent_routes_markup_to_studio_not_prefer():
    r = route_intent(
        "add markup percent and withholding tax compute on Sales quotations",
        connection_id="c1",
    )
    top = r["matches"][0]
    assert top["feature_id"] in {"studio.app", "draft.studio"}
    assert top["feature_id"] != "designer"


def test_job3_scrub_not_regressed():
    from app.ai_report_layout_scrub import is_report_layout_scrub_brief

    scrub = (
        "Remove the Customer Name from the shipping address on the delivery slip."
    )
    assert is_report_layout_scrub_brief(scrub) is True
    assert is_markup_wht_class_brief(scrub) is False
    seed = maybe_seed_from_capability(scrub)
    assert seed is not None
    assert seed.get("_pipeline") == "option_a_report_layout_scrub"
