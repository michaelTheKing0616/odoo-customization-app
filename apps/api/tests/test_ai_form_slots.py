"""Named inherit slots — no nested EXTENSION group on stock forms."""

from __future__ import annotations

import pytest

from app.ai_component_builder import draft_component_from_prompt
from app.ai_conversation.refine import apply_refinement, classify_intent
from app.ai_form_slots import infer_slot, slot_from_location
from app.preview_views import build_form_preview


VENDOR_TIN = (
    "On vendor bills only, add Vendor TIN. Show it on the vendor bill form, "
    "required before Confirm. Do not add it on customer invoices."
)
SLA_INVOICES = "Add SLA due date on invoices"
NOTES_ON_BILLS = "add a notes field on vendor bills"


def _extension_arch(draft: dict) -> str:
    for view in draft.get("views") or []:
        if (
            isinstance(view, dict)
            and str(view.get("mode") or "") == "extension"
            and str(view.get("type") or "") == "form"
        ):
            return str(view.get("arch") or "")
    return ""


def test_vendor_tin_sits_after_partner_not_in_extension_group() -> None:
    draft, hosts, _ = draft_component_from_prompt(
        VENDOR_TIN,
        available_models=["account.move"],
    )
    assert hosts[0].model == "account.move"
    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    names = {str(f.get("name") or "") for f in inherit.get("fields") or []}
    assert any("tin" in n for n in names)
    assert "x_active" not in names
    assert "x_notes" not in names
    arch = _extension_arch(draft)
    assert arch
    assert "extension" not in arch.lower()
    assert "string=\"Invoice extras\"" not in arch
    assert "//group[@id='header_left_group']/div[@class='o_col']" in arch
    assert "//field[@name='partner_id']" not in arch
    assert 'position="after"' in arch
    assert "<group string=" not in arch
    assert draft["_form_slots"]["fields"][next(n for n in names if "tin" in n)] == (
        "next_to_partner"
    )


def test_sla_due_lands_in_dates_column_without_nested_group() -> None:
    draft, _, _ = draft_component_from_prompt(
        SLA_INVOICES,
        available_models=["account.move"],
    )
    arch = _extension_arch(draft)
    assert "//group[@id='header_right_group']" in arch
    assert "<group string=" not in arch
    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    names = {str(f.get("name") or "") for f in inherit.get("fields") or []}
    assert "x_sla_due" in names
    assert draft["_form_slots"]["fields"]["x_sla_due"] == "next_to_dates"


def test_notes_go_to_other_info_tab() -> None:
    draft, _, _ = draft_component_from_prompt(
        NOTES_ON_BILLS,
        available_models=["account.move"],
    )
    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    names = {str(f.get("name") or "") for f in inherit.get("fields") or []}
    assert "x_notes" in names
    arch = _extension_arch(draft)
    assert "//page[@id='other_tab']" in arch
    assert draft["_form_slots"]["fields"]["x_notes"] == "other_info"


def test_refine_moves_tin_to_dates_slot() -> None:
    draft, _, _ = draft_component_from_prompt(
        VENDOR_TIN,
        available_models=["account.move"],
    )
    intent = classify_intent("put Vendor TIN next to dates")
    assert intent is not None
    assert intent.verb == "place"
    result = apply_refinement(draft, "put Vendor TIN next to dates")
    assert result["ok"] is True, result.get("error") or result
    arch = _extension_arch(result["draft"])
    assert "//group[@id='header_right_group']" in arch
    assert "//field[@name='partner_id']" not in arch


def test_put_it_back_is_still_restore() -> None:
    intent = classify_intent("put it back")
    assert intent is not None
    assert intent.verb == "restore"


def test_slot_from_location_phrases() -> None:
    assert slot_from_location("vendor") == "next_to_partner"
    assert slot_from_location("dates") == "next_to_dates"
    assert slot_from_location("other info") == "other_info"
    assert slot_from_location("a new tab") == "new_tab"


def test_infer_slot_defaults() -> None:
    assert (
        infer_slot({"name": "x_vendor_tin", "string": "Vendor TIN", "ttype": "char"}, host="account.move", prompt="")
        == "next_to_partner"
    )
    assert (
        infer_slot({"name": "x_sla_due", "string": "SLA due date", "ttype": "date"}, host="account.move", prompt="")
        == "next_to_dates"
    )


def test_live_apply_prep_restamps_stale_partner_xpath() -> None:
    from app.ai_apply_readiness import prepare_spec_for_live_apply

    stale = {
        "_user_prompt": VENDOR_TIN,
        "grain": "field_pack",
        "models": [
            {
                "model": "account.move",
                "mode": "inherit",
                "fields": [{"name": "x_tin", "ttype": "char", "string": "TIN"}],
            }
        ],
        "views": [
            {
                "name": "account.move.form.extension",
                "model": "account.move",
                "type": "form",
                "mode": "extension",
                "arch": (
                    '<data><xpath expr="//group[@id=\'header_left_group\']'
                    '//field[@name=\'partner_id\']" position="after">'
                    '<field name="x_tin"/></xpath></data>'
                ),
            }
        ],
        "_form_slots": {"fields": {"x_tin": "next_to_partner"}},
    }
    prepared, _ = prepare_spec_for_live_apply(stale)
    arch = "".join(str(v.get("arch") or "") for v in (prepared.get("views") or []))
    assert "//group[@id='header_left_group']/div[@class='o_col']" in arch
    assert "//field[@name='partner_id']" not in arch


def test_account_move_partner_xpath_matches_one_header_node() -> None:
    etree = pytest.importorskip("lxml.etree")

    from app.ai_form_slots import _HOST_SLOTS

    expr = _HOST_SLOTS["account.move"]["next_to_partner"][0]
    form = etree.fromstring(
        """
        <form>
          <group id="header_left_group">
            <div class="o_col"><field name="partner_id" nolabel="1"/></div>
            <field name="ref"/>
          </group>
          <notebook>
            <page id="invoice_tab">
              <field name="invoice_line_ids">
                <list><field name="partner_id"/></list>
              </field>
            </page>
          </notebook>
        </form>
        """
    )
    assert len(form.xpath("//field[@name='partner_id']")) == 2
    assert len(form.xpath(expr)) == 1


def test_preview_uses_slot_labels_not_extension() -> None:
    draft, _, _ = draft_component_from_prompt(
        VENDOR_TIN,
        available_models=["account.move"],
    )
    preview = build_form_preview(draft)
    assert preview is not None
    labels = [g.get("string") for g in preview.get("groups") or []]
    assert "Extension" not in labels
    assert any("vendor" in str(s).lower() for s in labels)
