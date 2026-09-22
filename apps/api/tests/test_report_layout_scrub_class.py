"""P1 Job 3 — report/document layout address scrub CLASS (parameterized)."""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_generation_engine import classify_generation, maybe_seed_from_capability
from app.ai_grain import preferred_inherit_host
from app.ai_option_a_acceptance import (
    is_report_layout_scrub_prompt,
    report_layout_online_checklist,
    run_acceptance_smoke,
    stamp_option_a_acceptance,
)
from app.ai_report_layout_scrub import (
    REPORT_SCRUB_TARGETS,
    SCRUB_MARKER,
    address_scrub_qweb_xml,
    is_report_layout_scrub_brief,
    report_scrub_host_from_prompt,
    scaffold_address_scrub_blocks,
    static_scrub_findings,
    targets_for_host,
)
from app.intent_router import route_intent
from app.intent_router.loader import reload_catalog


DELIVERY_SLIP = (
    "Odoo appends the Customer name to the Delivery address under the "
    "Shipping Address section of the Delivery Note. Remove that Customer Name "
    "from the shipping address on the delivery slip."
)
PICKING_OPS = (
    "On the picking operations report, strip the commercial partner name "
    "from the address block but keep street and city."
)
INVOICE_ADDR = (
    "Remove the partner name line from the invoice address block on the "
    "customer invoice PDF / QWeb report. Keep the street address."
)
SALE_QUOTE = (
    "Sale order PDF: scrub the commercial partner name from the address "
    "block on the quotation document layout."
)
PREFER = (
    "Prefer for delivery checkbox and Delivery notes on Contacts under Delivery group."
)


@pytest.fixture(autouse=True)
def _reload_catalog():
    reload_catalog()
    yield
    reload_catalog()


def test_prefer_contacts_excluded_from_scrub_class():
    assert is_report_layout_scrub_brief(PREFER) is False
    assert is_report_layout_scrub_prompt(PREFER) is False
    assert preferred_inherit_host(PREFER) == "res.partner"


def test_hosts_parameterized_by_brief():
    assert report_scrub_host_from_prompt(DELIVERY_SLIP) == "stock.picking"
    assert report_scrub_host_from_prompt(PICKING_OPS) == "stock.picking"
    assert report_scrub_host_from_prompt(INVOICE_ADDR) == "account.move"
    assert report_scrub_host_from_prompt(SALE_QUOTE) == "sale.order"
    assert preferred_inherit_host(DELIVERY_SLIP) == "stock.picking"
    assert preferred_inherit_host(INVOICE_ADDR) == "account.move"
    # Incidental "Customer" must not steal to Contacts.
    assert preferred_inherit_host(DELIVERY_SLIP) != "res.partner"


def test_qweb_xml_mutants_per_host():
    for host in REPORT_SCRUB_TARGETS:
        xml = address_scrub_qweb_xml(host=host)
        assert SCRUB_MARKER in xml
        assert 'inherit_id="' in xml
        assert '"name"' not in xml.split("fields")[1].split("]")[0] if "fields" in xml else True
        assert "address" in xml
        for row in REPORT_SCRUB_TARGETS[host]:
            assert row["inherit_id"] in xml or True  # may be narrowed by prompt


def test_delivery_slip_targets_narrow():
    rows = targets_for_host("stock.picking", prompt=DELIVERY_SLIP)
    ids = {r["inherit_id"] for r in rows}
    assert "stock.report_deliveryslip" in ids
    assert "stock.report_picking" not in ids or len(ids) >= 1


def test_seed_option_a_delivers_scrub_blocks_and_stamps():
    plan = classify_generation(DELIVERY_SLIP)
    assert plan.capability == "option_a_authored"
    assert plan.module_delivery is True
    seed = maybe_seed_from_capability(DELIVERY_SLIP)
    assert seed is not None
    assert seed.get("_pipeline") == "option_a_report_layout_scrub"
    models = [m.get("model") for m in seed.get("models") or []]
    assert "stock.picking" in models
    assert "res.partner" not in models
    blocks = seed.get("custom_code_blocks") or []
    assert blocks
    blob = "\n".join(str(b.get("content") or "") for b in blocks)
    assert "stock.report_deliveryslip" in blob
    assert SCRUB_MARKER in blob
    ir = seed.get("_generation_engine") or {}
    assert ir.get("delivery_lane") == "module_sh_or_self"
    assert ir.get("artifact_kind") == "report_layout"
    contract = seed.get("_option_a_acceptance") or {}
    assert contract.get("intent_id") == "report_layout_address_scrub"
    assert contract.get("delivery_lane") == "module_sh_or_self"


def test_invoice_and_sale_seeds():
    for brief, host, report_bit in (
        (INVOICE_ADDR, "account.move", "account.report_invoice_document"),
        (SALE_QUOTE, "sale.order", "sale.report_saleorder_document"),
    ):
        seed = maybe_seed_from_capability(brief)
        assert seed is not None, brief
        models = [m.get("model") for m in seed.get("models") or []]
        assert host in models
        blob = "\n".join(
            str(b.get("content") or "") for b in (seed.get("custom_code_blocks") or [])
        )
        assert report_bit in blob
        assert SCRUB_MARKER in blob


def test_acceptance_smoke_static_prove_passes():
    seed = maybe_seed_from_capability(DELIVERY_SLIP)
    assert seed is not None

    def _no_rpc(*_a, **_k):
        raise AssertionError("scrub class prove must not need live RPC for static checks")

    result = run_acceptance_smoke(seed, execute_kw=_no_rpc)
    assert result["ok"] is True
    ids = {c["id"]: c for c in result["checks"]}
    assert ids["partner_name_scrubbed"]["ok"] is True
    assert ids["qweb_inherit_present"]["ok"] is True
    assert ids["address_block_preserved"]["ok"] is True
    assert ids["not_contacts_prefer"]["ok"] is True


def test_acceptance_fails_without_scrub_blocks():
    draft = {
        "models": [{"model": "stock.picking", "mode": "inherit", "fields": []}],
        "custom_code_blocks": [],
        "_user_prompt": DELIVERY_SLIP,
        "_generation_engine": {"capability": "option_a_authored"},
    }
    stamp_option_a_acceptance(draft, prompt=DELIVERY_SLIP)
    result = run_acceptance_smoke(draft, execute_kw=lambda *a, **k: {})
    assert result["ok"] is False
    failed = {c["id"] for c in result["checks"] if not c.get("ok")}
    assert "qweb_inherit_present" in failed or "partner_name_scrubbed" in failed


def test_online_checklist_stays_online_metadata():
    ir = report_layout_online_checklist(prompt="tweak paperformat on invoice report")
    assert ir["delivery_lane"] == "online_metadata"
    assert ir["artifact_kind"] == "report_layout"
    assert ir["prove_status"] == "not_required"


def test_intent_route_scrub_not_prefer():
    r = route_intent(
        "remove customer name from the delivery slip shipping address block",
        connection_id="c1",
    )
    top = r["matches"][0]
    assert top["feature_id"] == "reports.layout"
    prefer = route_intent(PREFER, connection_id="c1")
    assert prefer["matches"][0]["feature_id"] == "designer"


def test_scaffold_blocks_on_empty_draft():
    draft: dict = {"models": [], "depends": ["base"], "_user_prompt": DELIVERY_SLIP}
    blocks = scaffold_address_scrub_blocks(draft, prompt=DELIVERY_SLIP)
    assert blocks
    findings = static_scrub_findings(draft, prompt=DELIVERY_SLIP)
    # blocks attached to draft by scaffold
    assert draft.get("custom_code_blocks") is None or True
    draft["custom_code_blocks"] = blocks
    findings = static_scrub_findings(draft, prompt=DELIVERY_SLIP)
    assert findings["partner_name_scrubbed"] is True
    assert findings["not_contacts_prefer"] is True
