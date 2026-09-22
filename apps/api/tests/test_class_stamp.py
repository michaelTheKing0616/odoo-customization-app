"""Class-wide delivery_lane / artifact_kind / prove_status stamps."""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_class_stamp import (
    online_python_block_alternatives,
    resolve_class_stamp,
)
from app.ai_conversation.understand import build_understanding
from app.ai_generation_engine import classify_generation, plan_to_ir
from app.ai_option_a_acceptance import (
    acceptance_for_draft,
    is_report_layout_scrub_prompt,
    report_layout_online_checklist,
    stamp_option_a_acceptance,
)
from app.ai_studio_contract import build_studio_contract
from app.hosting import online_python_promote_block
from app.tier_gating import online_python_promote_gating


MARKUP = (
    "The Client wants a Mark-up line added to every Sale. "
    "A Withholding Tax on the markup is to be calculated as well."
)
DELIVERY = (
    "Odoo appends the Customer name to the Delivery address under the "
    "Shipping Address section of the Delivery Note. Remove that Customer Name."
)
PREFER = (
    "Prefer for delivery checkbox and Delivery notes on Contacts under Delivery group."
)
CBN = (
    "Add Central Bank of Nigeria as the Service on Automatic Currency Rates "
    "so the cron pulls live CBN rates."
)


def test_markup_stamp_module_lane_option_a():
    stamp = resolve_class_stamp(
        prompt=MARKUP,
        capability="option_a_authored",
        needs_module=True,
        module_delivery=True,
    )
    assert stamp["delivery_lane"] == "module_sh_or_self"
    assert stamp["artifact_kind"] == "option_a_module"
    assert stamp["prove_status"] == "pending"
    assert stamp["promote_human"] is True


def test_cbn_stamp_external_connector_kind_module_lane():
    stamp = resolve_class_stamp(
        prompt=CBN,
        capability="option_a_standalone",
        gold_artifact_id="currency_rate_cbn",
        module_delivery=True,
        needs_module=True,
    )
    assert stamp["delivery_lane"] == "module_sh_or_self"
    assert stamp["artifact_kind"] == "external_connector"
    assert stamp["prove_status"] == "pending"


def test_report_scrub_stamp_report_layout():
    stamp = resolve_class_stamp(
        prompt=DELIVERY,
        capability="option_a_authored",
        needs_module=True,
        module_delivery=True,
    )
    assert stamp["artifact_kind"] == "report_layout"
    assert stamp["delivery_lane"] == "module_sh_or_self"


def test_prefer_stamp_online_field_pack():
    stamp = resolve_class_stamp(
        prompt=PREFER,
        grain="field_pack",
        inherit_only=True,
    )
    assert stamp["delivery_lane"] == "online_metadata"
    assert stamp["artifact_kind"] == "field_pack"
    assert stamp["prove_status"] == "not_required"


def test_diagnosis_understanding_carries_stamps():
    u = build_understanding(MARKUP)
    data = u.to_dict()
    assert data["delivery_lane"] == "module_sh_or_self"
    assert data["artifact_kind"] == "option_a_module"
    assert data["prove_status"] == "pending"
    assert "delivery_lane_copy" in data


def test_studio_contract_stamps_prefer_and_report():
    prefer = build_studio_contract(PREFER)
    assert prefer["delivery_lane"] == "online_metadata"
    assert prefer["artifact_kind"] == "field_pack"

    report = build_studio_contract(DELIVERY)
    assert report["artifact_kind"] == "report_layout"
    assert report["delivery_lane"] == "module_sh_or_self"


def test_generation_ir_stamps_present():
    plan = classify_generation(MARKUP)
    ir = plan_to_ir(plan, prompt=MARKUP)
    assert ir["delivery_lane"] == "module_sh_or_self"
    assert ir["artifact_kind"] == "option_a_module"
    assert ir["prove_status"] == "pending"
    assert ir["promote_human"] is True


def test_option_a_acceptance_stamps_and_report_class():
    assert is_report_layout_scrub_prompt(DELIVERY) is True
    assert is_report_layout_scrub_prompt(PREFER) is False

    draft = {
        "grain": "full_app",
        "models": [{"model": "stock.picking", "mode": "inherit", "fields": []}],
        "custom_code_blocks": [],
        "_generation_engine": {"capability": "option_a_authored"},
        "_user_prompt": DELIVERY,
    }
    contract = stamp_option_a_acceptance(draft, prompt=DELIVERY)
    assert contract["intent_id"] == "report_layout_address_scrub"
    assert contract["delivery_lane"] == "module_sh_or_self"
    assert contract["artifact_kind"] == "report_layout"
    assert "not_contacts_prefer" in {c["id"] for c in contract["checks"]}

    checklist = report_layout_online_checklist(prompt="tweak invoice report paperformat")
    assert checklist["delivery_lane"] == "online_metadata"
    assert checklist["artifact_kind"] == "report_layout"
    assert checklist["prove_status"] == "not_required"


def test_online_python_block_lists_sh_self_connector():
    alts = online_python_block_alternatives()
    blob = " ".join(alts).lower()
    assert "odoo.sh" in blob or "self-host" in blob
    assert "connector" in blob
    assert "install_mode=data" in blob or "metadata" in blob

    gating = online_python_promote_gating()
    assert gating.available is False
    assert any("connector" in o.lower() or "odoo.sh" in o.lower() for o in gating.options)

    block = online_python_promote_block(hosting_hint="online")
    assert block["blocked"] is True
    assert block["delivery_lane"] == "online_metadata"
    assert "connector" in block["message"].lower()
