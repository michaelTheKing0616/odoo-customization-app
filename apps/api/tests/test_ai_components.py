"""AI-8: component-grain classifier, connect points, gallery, collision."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.no_app_db

from app.ai_component_builder import draft_component_from_prompt
from app.ai_connect_points import detect_field_collisions, propose_connect_points
from app.ai_grain import HostCandidate, classify_grain, discover_hosts
from app.component_gallery import get_gallery_seed, list_gallery


@pytest.mark.parametrize(
    "prompt,expected",
    [
        ("add a warranty tracker to my sale orders", "feature_slice"),
        ("attach inspection checklist to project tasks", "feature_slice"),
        ("extend contacts with compliance status", "feature_slice"),
        ("add a field to partner", "field_pack"),
        ("build a library management app from scratch", "full_app"),
        ("create a car rental system with fleet and contracts", "full_app"),
        ("comprehensive enterprise-grade CRM platform", "full_app"),
        ("add warranty to sales", "feature_slice"),
        ("plug compliance into res.partner", "feature_slice"),
        ("minimal todo list", "full_app"),
        ("add document expiry tracking to sale order", "feature_slice"),
        ("manage inventory operations workflow system", "full_app"),
        ("add SLA due date on invoices", "field_pack"),
        ("add a due date on invoices", "field_pack"),
        (
            "On vendor bills only, add Vendor TIN. Show it on the vendor bill form, "
            "required before Confirm. Do not add it on customer invoices.",
            "field_pack",
        ),
    ],
)
def test_classify_grain_prompts(prompt: str, expected: str) -> None:
    assert classify_grain(prompt) == expected


def test_vendor_tin_on_bills_names_the_tin_field() -> None:
    draft, hosts, _ = draft_component_from_prompt(
        "On vendor bills only, add Vendor TIN. Show it on the vendor bill form, "
        "required before Confirm. Do not add it on customer invoices.",
        available_models=["account.move"],
    )
    assert draft["grain"] == "field_pack"
    assert hosts[0].model == "account.move"
    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    labels = {str(f.get("string") or "") for f in inherit.get("fields") or []}
    names = {str(f.get("name") or "") for f in inherit.get("fields") or []}
    assert any("tin" in s.lower() for s in labels)
    assert any("tin" in n for n in names)
    assert "x_only" not in names
    assert "x_active" not in names
    assert "x_notes" not in names
    assert draft["display_name"] == "Vendor bill fields"
    assert not (draft.get("menus") or [])



def test_discover_hosts_sale_order() -> None:
    hosts = discover_hosts(
        "add warranty to sale orders",
        available_models=["sale.order", "res.partner", "x_custom"],
    )
    assert hosts
    assert hosts[0].model == "sale.order"


def test_discover_hosts_invoice() -> None:
    hosts = discover_hosts(
        "add SLA due date on invoices",
        available_models=["sale.order", "account.move", "res.partner"],
    )
    assert hosts
    assert hosts[0].model == "account.move"


def test_discover_hosts_invoice_without_account_in_catalog() -> None:
    hosts = discover_hosts(
        "add SLA due date on invoices",
        available_models=["sale.order", "res.partner", "project.task"],
    )
    assert hosts
    assert hosts[0].model == "account.move"


def test_warranty_tracker_draft_shape() -> None:
    draft, hosts, warnings = draft_component_from_prompt(
        "add a warranty tracker to my sale orders",
        available_models=["sale.order"],
        gallery_id="warranty_tracker",
    )
    assert draft["grain"] == "feature_slice"
    assert draft["depends"] == ["sale"]
    assert draft.get("_component") is True
    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    assert inherit["model"] == "sale.order"
    assert any(f["name"] == "x_warranty_start" for f in inherit["fields"])
    assert draft["connect_points"]["host_model"] == "sale.order"
    assert hosts[0].model == "sale.order"
    assert isinstance(warnings, list)


def test_inspection_checklist_gallery_seed() -> None:
    draft, _, _ = draft_component_from_prompt(
        "add inspection checklist to project tasks",
        available_models=["project.task"],
        gallery_id="inspection_checklist",
    )
    assert draft["depends"] == ["project"]
    assert draft.get("gallery_id") == "inspection_checklist"
    companion = next((m for m in draft["models"] if m.get("model") == "x_inspection_line"), None)
    assert companion is not None


def test_full_app_not_component_path() -> None:
    assert classify_grain("build library app with books and loans") == "full_app"


def test_connect_points_emission() -> None:
    host = HostCandidate(model="sale.order", label="Sales", score=0.9, module="sale", reason="test")
    cp = propose_connect_points("add warranty", grain="feature_slice", host=host)
    assert cp["host_model"] == "sale.order"
    assert cp["form_xpath"] == "//sheet/group[1]"
    assert cp["host_module"] == "sale"


def test_parent_menu_xml_id_for_module_odoo19() -> None:
    from app.ai_grain import parent_menu_xml_id_for_module

    assert parent_menu_xml_id_for_module("sale") == "sale.sale_menu_root"
    assert parent_menu_xml_id_for_module("project") == "project.menu_main_pm"
    assert parent_menu_xml_id_for_module("crm") == "crm.crm_menu_root"
    assert parent_menu_xml_id_for_module("stock") == "stock.menu_stock_root"
    assert parent_menu_xml_id_for_module("base") is None


def test_collision_detection_fake_client() -> None:
    class _Client:
        def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None):
            return [{"name": "x_warranty_start"}]

    hits = detect_field_collisions(
        _Client(),  # type: ignore[arg-type]
        host_model="sale.order",
        field_names=["x_warranty_start", "x_new_field"],
    )
    assert len(hits) == 1
    assert hits[0]["field"] == "x_warranty_start"
    assert hits[0]["suggested_rename"].startswith("x_cmp_")


def test_gallery_lists_four_seeds() -> None:
    items = list_gallery()
    assert len(items) == 4
    ids = {i["id"] for i in items}
    assert ids == {
        "warranty_tracker",
        "inspection_checklist",
        "compliance_status",
        "document_expiry_pack",
    }


def test_compliance_on_partner() -> None:
    draft, _, _ = draft_component_from_prompt(
        "add compliance status to contacts",
        available_models=["res.partner"],
        gallery_id="compliance_status",
    )
    inherit = draft["models"][0]
    assert inherit["model"] == "res.partner"
    assert any("compliance" in f["name"] for f in inherit["fields"])


def test_document_expiry_host_slot_any() -> None:
    seed = get_gallery_seed("document_expiry_pack")
    assert seed is not None
    assert seed["host_slot"] == "any"


def test_pcm_keeps_additive_x_on_tier1_host_fields() -> None:
    from app.protected_modules import community_manifest_for_version
    from app.ai_rules import strip_protected_module_effects

    draft, _, _ = draft_component_from_prompt(
        "add extension note to invoice records",
        available_models=["account.move"],
        host_model_override="account.move",
    )
    manifest = community_manifest_for_version("19.0")
    cleaned, refusals, warnings = strip_protected_module_effects(draft, manifest=manifest)
    assert not refusals
    inherit_models = [m for m in cleaned.get("models", []) if m.get("mode") == "inherit"]
    assert inherit_models
    names = {f["name"] for f in inherit_models[0].get("fields") or [] if isinstance(f, dict)}
    assert any(n.startswith("x_") for n in names)


def test_component_module_zip_exports() -> None:
    from app.module_spec_codec import export_draft_module_zip

    draft, _, _ = draft_component_from_prompt(
        "add warranty to sale orders",
        available_models=["sale.order"],
        gallery_id="warranty_tracker",
    )
    raw = export_draft_module_zip(draft, odoo_major=19)
    assert raw[:2] == b"PK"
    assert len(raw) > 200


def test_preview_connect_points_component() -> None:
    from app.ai_component_builder import preview_connect_points

    preview = preview_connect_points(
        "add inspection checklist to project tasks",
        available_models=["project.task"],
        gallery_id="inspection_checklist",
    )
    assert preview["grain"] == "feature_slice"
    assert preview["requires_review"] is True
    assert preview["connect_points"]["host_model"] == "project.task"
    assert preview["gallery_id"] == "inspection_checklist"


def test_preview_connect_points_full_app() -> None:
    from app.ai_component_builder import preview_connect_points

    preview = preview_connect_points("build library app from scratch")
    assert preview["grain"] == "full_app"
    assert preview["requires_review"] is False


def test_generalize_component_template_shape() -> None:
    from app.ai_pack_generalizer import generalize_spec_to_component_template

    draft, _, _ = draft_component_from_prompt(
        "add warranty to sale orders",
        available_models=["sale.order"],
        gallery_id="warranty_tracker",
    )
    out = generalize_spec_to_component_template(draft, host_slot="sale.order")
    assert out["host_slot"] == "sale.order"
    assert out["filename"].endswith(".py")
    assert "connect_points_template" in out
    assert "Component template" in out["note"]


def test_sla_on_invoices_is_senior_inherit() -> None:
    draft, hosts, _ = draft_component_from_prompt(
        "add SLA due date on invoices",
        available_models=["sale.order", "res.partner"],
        host_model_override="sale.order",
        connect_points_override={"host_model": "sale.order", "sub_menu_name": "Extensions"},
    )
    assert draft["grain"] == "field_pack"
    assert draft.get("_component") is True
    assert hosts[0].model == "account.move"
    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    assert inherit["model"] == "account.move"
    names = {str(f.get("name")) for f in inherit.get("fields") or []}
    assert "x_extension_note" not in names
    assert "x_sla" not in names
    assert "x_sla_due" in names
    assert any(str(f.get("string")) == "SLA due date" for f in inherit["fields"])
    assert draft["depends"] == ["account"]
    assert draft["display_name"] == "SLA"
    assert not (draft.get("menus") or [])
    assert not (draft.get("groups") or [])
    assert inherit.get("mixins") in (None, [])
    assert any(
        str(a.get("trg_date_field_name")) == "x_sla_due"
        for a in (draft.get("automations") or [])
        if isinstance(a, dict)
    )
    assert "smart_button" not in (draft.get("connect_points") or {})
    assert (draft.get("connect_points") or {}).get("host_model") == "account.move"
    assert any(
        str(v.get("model")) == "account.move" and str(v.get("mode")) == "extension"
        for v in (draft.get("views") or [])
        if isinstance(v, dict)
    )
    assert not any(
        str(m.get("model") or "").startswith("x_") for m in draft["models"] if m.get("mode") != "inherit"
    )
    from app.ai_draft_scorecard import attach_scorecard
    from app.ai_live_apply_contract import attach_live_apply_contract
    from app.ai_llm_status import attach_llm_status, finalize_llm_status

    attach_live_apply_contract(draft)
    attach_scorecard(draft, user_prompt="Add SLA due date on invoices")
    findings = (draft.get("_scorecard") or {}).get("findings") or []
    assert not any(f.get("element") == "noun:invoice" for f in findings)
    assert not any(f.get("detail") == "missing search view" for f in findings)
    assert inherit.get("mixins") in (None, [])
    attach_llm_status(draft, mode="llm_full", reason="component_grain")
    finalize_llm_status(draft, mode="llm_full")
    status = draft.get("_llm_status") or {}
    assert status.get("completed_steps") == ["Host", "Fields", "View", "Ready"]
    assert status.get("step_total") == 4


def test_field_pack_on_partner_has_no_companion() -> None:
    draft, _, _ = draft_component_from_prompt(
        "add a field to partner",
        available_models=["res.partner"],
    )
    assert draft["grain"] == "field_pack"
    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    assert inherit["model"] == "res.partner"
    names = {str(f.get("name")) for f in inherit.get("fields") or []}
    assert "x_extension_note" not in names
    assert "x_extra_info" in names
    assert "x_active" not in names
    assert not any(str(m.get("model") or "").startswith("x_") for m in draft["models"])


def test_register_slice_adds_companion_and_smart_button() -> None:
    draft, _, _ = draft_component_from_prompt(
        "add a safety register on sale orders",
        available_models=["sale.order"],
    )
    assert draft["grain"] == "feature_slice"
    companion = next(
        (m for m in draft["models"] if str(m.get("model") or "").startswith("x_")),
        None,
    )
    assert companion is not None
    assert companion["model"] != "x_extension_note"
    assert any(
        str(b.get("related_model")) == companion["model"]
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    )


def test_close_architecture_does_not_bloat_component() -> None:
    from app.ai_odoo_app_bar import close_odoo_architecture

    draft, _, _ = draft_component_from_prompt(
        "add SLA due date on invoices",
        available_models=["account.move"],
    )
    before = {str(m.get("model")) for m in draft["models"]}
    close_odoo_architecture(draft, user_prompt="add SLA due date on invoices")
    after = {str(m.get("model")) for m in draft["models"]}
    extra = {mid for mid in after - before if mid.startswith("x_")}
    assert not extra


def test_component_comprehensive_depth_does_not_require_ten_models() -> None:
    from app.ai_depth import depth_gaps

    draft, _, _ = draft_component_from_prompt(
        "add SLA due date on invoices",
        available_models=["account.move"],
    )
    gaps = depth_gaps(draft, "comprehensive")
    assert "depth_models" not in gaps

