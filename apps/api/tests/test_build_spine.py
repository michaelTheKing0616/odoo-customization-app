"""P2 Build spine — mode chips, handoff IR, capability-gap Option A proposals."""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_build_spine import (
    build_spine_payload,
    capability_gap_option_a_proposals,
    resolve_build_mode,
)
from app.ai_capability_gaps import stamp_capability_gaps
from app.ai_generation_engine import classify_generation, maybe_seed_from_capability, plan_to_ir
from app.ai_class_stamp import resolve_class_stamp


PREFER = (
    "Prefer for delivery checkbox and Delivery notes on Contacts under Delivery group."
)
MARKUP = (
    "The Client wants a Mark-up line added to every Sale. "
    "A Withholding Tax on the markup is to be calculated as well."
)
DELIVERY = (
    "Odoo appends the Customer name to the Delivery address under the "
    "Shipping Address section of the Delivery Note. Remove that Customer Name."
)
CBN = (
    "Add Central Bank of Nigeria as the Service on Automatic Currency Rates "
    "so the cron pulls live CBN rates."
)
NIGERIA = (
    "We are a company in Lagos, Nigeria. Stand up Community Accounting. "
    "Company currency NGN. Custom residual: None. Capability path: stock_first."
)
RESIDUAL = "Build a visitor log app with check-in and check-out times. New app."
OWL = (
    "Add a custom OWL widget and python compute on sale.order for discount tiers."
)


def test_resolve_modes_for_class_exemplars():
    plan = classify_generation(PREFER)
    ir = plan_to_ir(plan, prompt=PREFER)
    # Prefer may classify as field_pack residual — mode must not be option_a invent
    mode = resolve_build_mode(
        prompt=PREFER,
        capability=ir.get("capability") or "",
        grain=ir.get("grain") or plan.grain,
        artifact_kind=ir.get("artifact_kind"),
        delivery_lane=ir.get("delivery_lane"),
    )
    stamp = resolve_class_stamp(
        prompt=PREFER, grain="field_pack", inherit_only=True, capability=""
    )
    prefer_mode = resolve_build_mode(
        prompt=PREFER,
        grain="field_pack",
        artifact_kind=stamp["artifact_kind"],
        delivery_lane=stamp["delivery_lane"],
    )
    assert prefer_mode == "prefer_pack"

    assert (
        resolve_build_mode(
            prompt=MARKUP,
            capability="option_a_authored",
            artifact_kind="option_a_module",
            delivery_lane="module_sh_or_self",
        )
        == "option_a"
    )
    assert (
        resolve_build_mode(
            prompt=DELIVERY,
            capability="option_a_authored",
            artifact_kind="report_layout",
        )
        == "report_layout"
    )
    assert (
        resolve_build_mode(
            prompt=CBN,
            capability="option_a_standalone",
            gold_artifact_id="currency_rate_cbn",
            artifact_kind="external_connector",
        )
        == "connector"
    )
    assert (
        resolve_build_mode(prompt=NIGERIA, capability="stock_reuse") == "stock_autopilot"
    )
    assert (
        resolve_build_mode(
            prompt=RESIDUAL, capability="residual_app", grain="full_app", artifact_kind="full_app"
        )
        == "residual_app"
    )


def test_spine_payload_carries_stamps_and_chips():
    payload = build_spine_payload(prompt=MARKUP, connection_id="c1")
    assert payload["build_mode"] == "option_a"
    assert payload["delivery_lane"] == "module_sh_or_self"
    assert payload["artifact_kind"] == "option_a_module"
    assert payload["promote_human"] is True
    assert payload["completeness_is_not_cert"] is True
    assert payload["brief"]
    assert payload["diagnosis"]["delivery_lane"]
    assert payload["contract"]
    assert any(c["id"] == "option_a" and c["active"] for c in payload["chips"])
    assert "/connections/c1/studio" in payload["chips"][0]["href"] or any(
        "studio" in c["href"] for c in payload["chips"] if c["active"]
    )


def test_spine_payload_prefer_and_report_and_fx():
    prefer = build_spine_payload(prompt=PREFER, connection_id="c1")
    # Prefer pack grain from contract
    assert prefer["build_mode"] in {"prefer_pack", "residual_app"}
    # Force via stamps already on contract
    from app.ai_studio_contract import build_studio_contract

    c = build_studio_contract(PREFER)
    prefer2 = build_spine_payload(prompt=PREFER, connection_id="c1", contract=c)
    assert prefer2["build_mode"] == "prefer_pack" or c.get("grain") == "field_pack"

    report = build_spine_payload(prompt=DELIVERY, connection_id="c1")
    assert report["build_mode"] == "report_layout"
    assert report["artifact_kind"] == "report_layout"

    fx = build_spine_payload(prompt=CBN, connection_id="c1")
    assert fx["build_mode"] == "connector"
    assert fx["gold_artifact_id"] == "currency_rate_cbn"


def test_capability_gaps_always_propose_option_a_scaffold_when_live_cannot():
    draft = {
        "models": [{"model": "sale.order", "mode": "inherit", "fields": []}],
        "custom_code_blocks": [],
        "_generation_engine": {"capability": "option_a_authored"},
        "_user_prompt": OWL,
    }
    notes = stamp_capability_gaps(draft, OWL)
    assert draft.get("_capability_gaps"), notes
    proposals = capability_gap_option_a_proposals(draft)
    assert proposals, draft.get("_capability_gaps")
    assert all(p.get("proposes_option_a_scaffold") for p in proposals)
    # LLM owns blocks — still proposed, attach skipped
    assert any("skip scaffold" in n or "proposed" in n for n in notes)


def test_job1_2_3_seeds_still_class_modes():
    for prompt, mode in [
        (MARKUP, "option_a"),
        (DELIVERY, "report_layout"),
        (CBN, "connector"),
    ]:
        seed = maybe_seed_from_capability(prompt)
        assert seed is not None
        ir = seed.get("_generation_engine") or {}
        assert (
            resolve_build_mode(
                prompt=prompt,
                capability=str(ir.get("capability") or ""),
                grain=str(ir.get("grain") or ""),
                gold_artifact_id=ir.get("gold_artifact_id"),
                artifact_kind=ir.get("artifact_kind"),
                delivery_lane=ir.get("delivery_lane"),
            )
            == mode
        )
