"""Generation Engine — capability map, gold POS template, stock-first rental, refuse clone."""

from __future__ import annotations

import io
import zipfile

from app.ai_domain_packs import car_rental_pack, match_domain_pack
from app.ai_elite import run_elite_quality_pass
from app.ai_generation_engine import (
    classify_generation,
    is_gold_option_a_draft,
    is_refuse_draft,
    is_stock_reuse_draft,
    maybe_seed_from_capability,
    residual_form_preview,
)
from app.ai_pipeline import seed_studio_draft
from app.ai_structural_zip_gate import structural_zip_gate
from app.option_a_templates import apply_gold_template


POS_CUSTOM = "Create a POS receipt configurator [custom] app"
CLONE = "clone the GM POS receipt configurator from the apps store"
MAKERSPACE = (
    "community makerspace: member badges, tool loans, and workshop bookings"
)
RENTAL = "I need a car rental service management app"


def test_car_rental_pack_is_stock_first() -> None:
    pack = car_rental_pack()
    models = {m["model"] for m in pack["models"]}
    assert "x_rent_customer" not in models
    assert "x_rent_payment" not in models
    assert "res.partner" in models
    assert "x_rent_contract" in models
    contract = next(m for m in pack["models"] if m["model"] == "x_rent_contract")
    fields = {f["name"]: f for f in contract["fields"]}
    assert fields["x_partner_id"]["relation"] == "res.partner"
    assert fields["x_invoice_id"]["relation"] == "account.move"
    assert "sale" in pack["depends"]
    assert "account" in pack["depends"]


def test_car_rental_prompt_seeds_pack_without_clones() -> None:
    draft = seed_studio_draft(RENTAL)
    models = {m["model"] for m in draft.get("models") or []}
    assert draft.get("domain_pack") == "car_rental"
    assert "x_rent_customer" not in models
    assert "x_rent_payment" not in models
    assert "x_rent_contract" in models
    ir = draft.get("_generation_engine") or {}
    assert ir.get("capability") == "residual_app"
    assert ir.get("promote_human") is True


def test_pos_custom_app_binds_gold_template_not_x_receipt() -> None:
    plan = classify_generation(POS_CUSTOM)
    assert plan.capability == "option_a_standalone"
    assert plan.gold_artifact_id == "pos_receipt_options"
    assert plan.module_delivery is True

    draft = maybe_seed_from_capability(POS_CUSTOM)
    assert draft is not None
    assert is_gold_option_a_draft(draft)
    models = [m.get("model") for m in draft.get("models") or []]
    assert "x_receipt" not in models
    assert "pos.config" in models
    ir = draft["_generation_engine"]
    assert ir["gold_artifact_id"] == "pos_receipt_options"
    assert ir.get("option_a_settings", {}).get("model") == "pos.config"
    preview = residual_form_preview(draft)
    assert preview is None or str(preview.get("model") or "") != "x_receipt"

    seeded = seed_studio_draft(POS_CUSTOM)
    assert seeded.get("technical_name") == "pos_receipt_options"
    assert seeded.get("domain_pack") not in {"restaurant", "retail_supermarket"}


def test_clone_apps_store_is_refused() -> None:
    plan = classify_generation(CLONE)
    assert plan.capability == "refuse_clone"
    draft = seed_studio_draft(CLONE)
    assert is_refuse_draft(draft)
    assert draft.get("models") == []
    assert "clone" in str(draft["_generation_engine"].get("honesty") or "").lower()


def test_gm_marketing_paste_selects_gold_not_clone() -> None:
    text = (
        "GM Pos Receipt Configurator\n"
        "Design your Point of Sale receipt visually: paper width and preview."
    )
    plan = classify_generation(text)
    assert plan.capability == "option_a_standalone"
    assert plan.gold_artifact_id == "pos_receipt_options"
    draft = seed_studio_draft(text)
    assert draft.get("technical_name") == "pos_receipt_options"


def test_makerspace_does_not_steal_vertical_packs() -> None:
    assert match_domain_pack(MAKERSPACE) is None
    draft = seed_studio_draft(MAKERSPACE)
    assert draft.get("domain_pack") not in {
        "restaurant",
        "retail_supermarket",
        "law_firm",
        "hotel",
        "car_rental",
    }
    models = {str(m.get("model")) for m in draft.get("models") or []}
    assert "x_receipt" not in models
    assert "x_rent_customer" not in models


POS_STOCK_FIRST = """# Operator brief
## Goal
Stand up Community Point of Sale for one company: cashiers sell from POS, stock quotations/invoices exist for B2B, receipts stay stock POS until a separate Option A print module is proven.

## Industry
(not stated in this brief — fill only if you have one)

## Actors
- cashier
- shop manager
- accountant

## Processes
- POS sale → payment → stock receipt print
- quote → confirm → customer invoice (B2B, stock Accounting)

## Stock reuse (named)
- point_of_sale
- sale
- account
- contacts
- mail
- hr (cashiers as employees, if you use attendance)

## Custom residual
None. Do not invent x_receipt, x_pos_config, x_client, or x_invoice.

## Constraints (stated)
- One company (not multi-company)
- Sandbox only; Promote stays human
- Standard Odoo receipt remains the fallback

## Out of scope
- Visual drag-and-drop receipt designer (font-per-element, column reorder, design library, cashier design picker)
- Cloning third-party POS receipt apps
- Writing partner API keys

## Unknowns — do not assume
- Country / l10n
- Currency
- Company legal name
- Number of pos.config terminals
- Whether IoT/printer hardware is on this instance

## Capability path
stock_first (+ later Option A only if we explicitly ask for receipt OWL/QWeb)

## Done bar
Autopilot RPC smoke on sandbox. Completeness 10.0 ≠ Certification. Cert stays Reject until Option A prove if we add print/layout Python/JS.
"""


def test_stock_first_pos_brief_is_stock_reuse_not_invoice_qr() -> None:
    plan = classify_generation(POS_STOCK_FIRST)
    assert plan.capability == "stock_reuse"
    assert plan.gold_artifact_id is None

    draft = seed_studio_draft(POS_STOCK_FIRST)
    assert is_stock_reuse_draft(draft)
    models = [str(m.get("model")) for m in draft.get("models") or []]
    assert models == []
    assert "x_receipt" not in models
    assert "account.move" not in models
    assert not draft.get("custom_code_blocks")
    assert draft.get("_capability_primary_option_a") is not True
    ir = draft["_generation_engine"]
    assert ir.get("gold_artifact_id") in (None, "")
    assert "Pay/QR" in (ir.get("honesty") or "") or "stock-first" in (ir.get("honesty") or "").lower()
    names = {str(f.get("name")) for m in draft.get("models") or [] for f in (m.get("fields") or [])}
    assert "x_payment_url" not in names
    assert "x_qr_payload" not in names
    done = draft.get("_done_bar") if isinstance(draft.get("_done_bar"), dict) else {}
    assert done.get("mode") in {"autopilot", None, "live"}
    assert done.get("mode") != "option_a"


def test_stock_first_pos_brief_skips_component_grain_path() -> None:
    """The 08:23 live miss: component_grain + invoice Pay/QR + POS gold honesty."""
    from app.ai_grain import classify_grain
    from app.ai_ollama import draft_module_from_prompt
    from app.ai_operator_brief import intent_corpus, wants_extension_grain, wants_stock_reuse

    assert wants_stock_reuse(POS_STOCK_FIRST)
    assert wants_extension_grain(POS_STOCK_FIRST) is False
    assert classify_grain(intent_corpus(POS_STOCK_FIRST)) != "field_pack"

    draft, _raw, _w, _r = draft_module_from_prompt(POS_STOCK_FIRST)
    assert is_stock_reuse_draft(draft)
    assert draft.get("_llm_status", {}).get("reason") != "component_grain"
    models = [str(m.get("model")) for m in draft.get("models") or []]
    assert "account.move" not in models
    assert not draft.get("custom_code_blocks")
    ir = draft.get("_generation_engine") or {}
    assert ir.get("gold_artifact_id") in (None, "")
    assert ir.get("capability") == "stock_reuse"


def test_stock_first_with_named_residual_is_not_empty_seed() -> None:
    text = (
        "# Operator brief\n"
        "## Goal\nStand up Community POS and a loyalty punch card cashiers stamp.\n"
        "## Stock reuse (named)\n- point_of_sale\n- sale\n- account\n"
        "## Custom residual\nloyalty punch card\n"
        "## Capability path\nstock_first\n"
    )
    plan = classify_generation(text)
    assert plan.capability == "residual_app"
    assert plan.gold_artifact_id is None
    assert maybe_seed_from_capability(text) is None
    draft = seed_studio_draft(text)
    assert not is_stock_reuse_draft(draft)
    models = {str(m.get("model")) for m in draft.get("models") or []}
    assert "x_receipt" not in models
    assert any("loyalty" in m for m in models)


def test_stock_first_sla_inherit_is_field_pack_not_stock_reuse() -> None:
    text = (
        "# Operator brief\n"
        "## Goal\nAdd SLA due date on invoices\n"
        "## Custom residual\nNone.\n"
        "## Capability path\nstock_first\n"
    )
    plan = classify_generation(text)
    assert plan.capability == "residual_app"
    assert plan.grain == "field_pack"
    assert maybe_seed_from_capability(text) is None
    from app.ai_component_builder import draft_component_from_prompt

    draft, _hosts, _w = draft_component_from_prompt(text, grain="field_pack")
    models = {str(m.get("model")) for m in draft.get("models") or []}
    assert "account.move" in models
    names = {
        str(f.get("name"))
        for m in draft.get("models") or []
        for f in (m.get("fields") or [])
        if isinstance(f, dict)
    }
    assert any("sla" in n for n in names)


def test_elite_does_not_overwrite_gold_pos_tests() -> None:
    draft = apply_gold_template(POS_CUSTOM, "pos_receipt_options")
    before = {
        str(b.get("source_file")): str(b.get("content"))
        for b in draft.get("custom_code_blocks") or []
        if isinstance(b, dict)
    }
    run_elite_quality_pass(draft)
    after_paths = {
        str(b.get("source_file"))
        for b in draft.get("custom_code_blocks") or []
        if isinstance(b, dict)
    }
    assert "tests/test_pos_receipt_options.py" in after_paths
    assert not any("smoke" in p for p in after_paths)
    gold = next(
        b
        for b in draft["custom_code_blocks"]
        if b.get("source_file") == "tests/test_pos_receipt_options.py"
    )
    assert gold["content"] == before["tests/test_pos_receipt_options.py"]


def test_structural_zip_gate_missing_access_and_syntax() -> None:
    bad_access = {
        "demo/__manifest__.py": "{'name': 'Demo'}\n",
        "demo/models/thing.py": "from odoo import models\n\nclass T(models.Model):\n    _name = 'x_thing'\n",
    }
    gate = structural_zip_gate(files=bad_access)
    assert gate["ok"] is False
    assert any("ir.model.access.csv" in f for f in gate["findings"])

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("demo/models/broken.py", "def oops(\n")
    gate2 = structural_zip_gate(buf.getvalue())
    assert gate2["ok"] is False
    assert any("syntax" in f for f in gate2["findings"])


def test_structural_zip_gate_gold_pos_passes() -> None:
    from app.module_spec_codec import export_draft_module_zip

    draft = apply_gold_template(POS_CUSTOM, "pos_receipt_options")
    zip_bytes = export_draft_module_zip(draft, odoo_major=19)
    gate = structural_zip_gate(zip_bytes)
    assert gate["ok"] is True, gate["findings"]
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
    assert any(n.endswith("tests/test_pos_receipt_options.py") for n in names)
    assert not any("/x_receipt" in n for n in names)
