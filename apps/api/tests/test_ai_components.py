"""AI-8: component-grain classifier, connect points, gallery, collision."""

from __future__ import annotations

from typing import Any

import pytest

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
    ],
)
def test_classify_grain_prompts(prompt: str, expected: str) -> None:
    assert classify_grain(prompt) == expected


def test_discover_hosts_sale_order() -> None:
    hosts = discover_hosts(
        "add warranty to sale orders",
        available_models=["sale.order", "res.partner", "x_custom"],
    )
    assert hosts
    assert hosts[0].model == "sale.order"


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
    assert cp["form_xpath"] == "//sheet"
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


def test_pcm_strip_tier1_host_fields() -> None:
    from app.protected_modules import community_manifest_for_version
    from app.ai_rules import strip_protected_module_effects

    draft, _, _ = draft_component_from_prompt(
        "add extension note to invoice records",
        available_models=["account.move"],
        host_model_override="account.move",
    )
    manifest = community_manifest_for_version("19.0")
    cleaned, refusals, warnings = strip_protected_module_effects(draft, manifest=manifest)
    assert refusals or warnings
    inherit_models = [m for m in cleaned.get("models", []) if m.get("mode") == "inherit"]
    assert not inherit_models


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

