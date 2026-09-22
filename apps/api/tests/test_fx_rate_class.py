"""P1 Job 1 — FX / rate-provider sync CLASS (parameterized mutants)."""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_fx_rate_class import (
    CLASS_INTENT_ID,
    CLASS_MARKER,
    DEFAULT_CURRENCIES,
    GOLD_CBN_ID,
    class_mutant_briefs,
    is_cbn_class_match,
    is_fx_rate_provider_class_brief,
    is_nigeria_autopilot_stock_only,
    online_connector_runbook,
    quoted_currencies_from_prompt,
    resolve_fx_host_stamp,
    resolve_fx_member,
    static_fx_rate_findings,
)
from app.ai_generation_engine import classify_generation, maybe_seed_from_capability
from app.ai_option_a_acceptance import (
    fx_rate_online_connector_runbook,
    is_fx_rate_provider_prompt,
    run_acceptance_smoke,
    stamp_option_a_acceptance,
)
from app.ai_option_a_gate import evaluate_authoring_gate
from app.ai_option_a_policy import policy_findings
from app.intent_router import route_intent
from app.intent_router.loader import reload_catalog


NIGERIA_AUTOPILOT = (
    "We are a company in Lagos, Nigeria. Stand up Community Accounting. "
    "Company currency NGN. Custom residual: None. Capability path: stock_first."
)
PREFER_ONLY = "Prefer for delivery checkbox on Contacts under Delivery group."


@pytest.fixture(autouse=True)
def _reload():
    reload_catalog()
    yield
    reload_catalog()


def test_mutants_detect_as_class():
    for row in class_mutant_briefs():
        assert is_fx_rate_provider_class_brief(row["prompt"]), row["id"]
        assert is_fx_rate_provider_prompt(row["prompt"]), row["id"]


def test_nigeria_autopilot_and_prefer_not_this_class():
    assert is_nigeria_autopilot_stock_only(NIGERIA_AUTOPILOT) is True
    assert is_fx_rate_provider_class_brief(NIGERIA_AUTOPILOT) is False
    assert is_fx_rate_provider_class_brief(PREFER_ONLY) is False
    assert is_fx_rate_provider_class_brief("activate NGN for Nigeria") is False


def test_cbn_mutants_select_gold():
    for row in class_mutant_briefs():
        if not row["id"].startswith("cbn"):
            continue
        assert is_cbn_class_match(row["prompt"]), row["id"]
        assert resolve_fx_member(row["prompt"]) == "cbn_gold"
        plan = classify_generation(row["prompt"])
        assert plan.gold_artifact_id == GOLD_CBN_ID, row["id"]
        assert plan.capability == "option_a_standalone"
        seed = maybe_seed_from_capability(row["prompt"])
        assert seed is not None
        assert seed.get("technical_name") == GOLD_CBN_ID
        contract = seed.get("_option_a_acceptance") or {}
        assert contract.get("intent_id") == CLASS_INTENT_ID, row["id"]
        ids = {c["id"] for c in contract.get("checks") or []}
        assert "writes_currency_rate" in ids
        assert "currencies_parameterized" in ids
        assert "no_x_fx_app" in ids
        assert contract.get("delivery_lane") == "module_sh_or_self"
        assert contract.get("artifact_kind") == "external_connector"


def test_generic_mutants_option_a_scaffold():
    for row in class_mutant_briefs():
        if row["id"].startswith("cbn") or row["id"] == "online_connector":
            continue
        plan = classify_generation(row["prompt"])
        assert plan.capability == "option_a_authored", (row["id"], plan)
        assert plan.gold_artifact_id is None
        assert plan.module_delivery is True
        assert "Prefer" not in plan.honesty or "Never Prefer" in plan.honesty
        seed = maybe_seed_from_capability(row["prompt"])
        assert seed is not None, row["id"]
        assert seed.get("_pipeline") == "option_a_fx_rate_class", row["id"]
        blob = "\n".join(
            str(b.get("content") or "") for b in seed.get("custom_code_blocks") or []
        )
        assert CLASS_MARKER in blob, row["id"]
        assert "res.currency.rate" in blob, row["id"]
        assert '_name = "x_fx"' not in blob and "model=\"x_fx\"" not in blob
        findings = static_fx_rate_findings(seed, prompt=row["prompt"])
        assert findings["writes_currency_rate"], (row["id"], findings)
        assert findings["currencies_parameterized"], (row["id"], findings)
        assert findings["no_x_fx_app"], (row["id"], findings)
        assert findings["gold_or_scaffold_present"], (row["id"], findings)


def test_online_connector_member_and_runbook():
    row = next(r for r in class_mutant_briefs() if r["id"] == "online_connector")
    assert resolve_fx_member(row["prompt"]) == "external_connector"
    plan = classify_generation(row["prompt"])
    assert plan.capability == "option_a_authored"
    assert "external_connector" in " ".join(plan.notes) or "connector" in plan.honesty.lower()
    runbook = online_connector_runbook(prompt=row["prompt"])
    assert runbook["delivery_lane"] == "external_connector"
    assert runbook["online_python_promote"] is False
    assert "USD" in runbook["quoted_currencies"]
    assert fx_rate_online_connector_runbook(prompt=row["prompt"])["intent_id"] == (
        "fx_rate_online_connector_runbook"
    )
    stamp = resolve_fx_host_stamp(prompt=row["prompt"], hosting_hint="online")
    assert stamp["delivery_lane"] == "external_connector"
    assert stamp["online_python_promote"] is False


def test_host_stamps_module_vs_online():
    cbn = class_mutant_briefs()[0]["prompt"]
    sh = resolve_fx_host_stamp(prompt=cbn, hosting_hint="odoo_sh", gold_artifact_id=GOLD_CBN_ID)
    assert sh["delivery_lane"] == "module_sh_or_self"
    assert sh["artifact_kind"] == "external_connector"
    online = resolve_fx_host_stamp(prompt=cbn, hosting_hint="online", gold_artifact_id=GOLD_CBN_ID)
    assert online["delivery_lane"] == "external_connector"
    assert "online_block" in online


def test_quoted_currencies_parameterized():
    assert quoted_currencies_from_prompt("rates for USD and JPY") == ("USD", "JPY")
    assert quoted_currencies_from_prompt("pull live FX rates") == DEFAULT_CURRENCIES


def test_nigeria_not_gold():
    plan = classify_generation(NIGERIA_AUTOPILOT)
    assert plan.gold_artifact_id != GOLD_CBN_ID
    assert plan.capability != "option_a_standalone" or plan.gold_artifact_id is None


def test_acceptance_smoke_cbn_and_generic():
    cbn = class_mutant_briefs()[0]["prompt"]
    seed = maybe_seed_from_capability(cbn)
    assert seed is not None

    def _rpc_fail(*_a, **_k):
        raise RuntimeError("no live odoo in unit test")

    result = run_acceptance_smoke(seed, execute_kw=_rpc_fail)
    assert result["ok"] is True, result
    by_id = {c["id"]: c for c in result["checks"]}
    assert by_id["writes_currency_rate"]["ok"]
    assert by_id["currencies_parameterized"]["ok"]
    assert by_id["no_x_fx_app"]["ok"]
    assert by_id["not_nigeria_autopilot_alone"]["ok"]
    assert by_id["gold_or_scaffold_present"]["ok"]

    generic = next(r for r in class_mutant_briefs() if r["id"] == "generic_http_provider")
    gseed = maybe_seed_from_capability(generic["prompt"])
    assert gseed is not None
    gresult = run_acceptance_smoke(gseed, execute_kw=_rpc_fail)
    assert gresult["ok"] is True, gresult


def test_policy_and_gate_green_on_generic_scaffold():
    row = next(r for r in class_mutant_briefs() if r["id"] == "generic_http_provider")
    seed = maybe_seed_from_capability(row["prompt"])
    assert seed is not None
    findings = policy_findings(seed)
    assert findings == [], findings
    gate = evaluate_authoring_gate(seed)
    assert gate["status"] == "pass", gate


def test_intent_routes_fx_to_studio_not_prefer():
    r = route_intent(
        "pull CBN FX rates into Accounting Automatic Currency Rates",
        connection_id="c1",
    )
    top = r["matches"][0]
    assert top["feature_id"] in {"studio.app", "draft.studio"}
    assert top["feature_id"] != "designer"


def test_stamp_option_a_acceptance_on_generic():
    row = next(r for r in class_mutant_briefs() if r["id"] == "ecb_service")
    seed = maybe_seed_from_capability(row["prompt"])
    assert seed is not None
    contract = stamp_option_a_acceptance(seed, prompt=row["prompt"])
    assert contract["intent_id"] == CLASS_INTENT_ID
    assert contract["artifact_kind"] == "external_connector"
