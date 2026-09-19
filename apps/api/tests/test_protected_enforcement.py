"""Unit tests for PCM-4 protected mutation enforcement helpers."""

from __future__ import annotations

from app.protected_enforcement import (
    check_automation_create,
    check_field_create,
    check_invoicing_draft_create,
    check_relational_pair,
    scrub_spec_for_protected_apply,
)
from app.protected_modules import community_manifest_for_version


def _manifest():
    return community_manifest_for_version("19.0")


def test_block_stock_field_create_on_tier1() -> None:
    m = _manifest()
    viol = check_field_create(
        m, model="account.move", ttype="char", field_name="note"
    )
    assert viol is not None
    assert viol.tier == "tier_1"
    assert "docs" in viol.http_detail()


def test_allow_additive_x_field_on_tier1() -> None:
    m = _manifest()
    assert (
        check_field_create(
            m, model="account.move", ttype="date", field_name="x_sla_due"
        )
        is None
    )


def test_allow_link_only_from_custom() -> None:
    m = _manifest()
    assert (
        check_field_create(
            m,
            model="x_matter",
            ttype="many2one",
            relation="account.move",
            field_name="x_invoice_id",
        )
        is None
    )


def test_block_o2m_on_tier1_parent_pair() -> None:
    m = _manifest()
    viol = check_relational_pair(
        m, parent_model="account.move", child_model="x_matter_line"
    )
    assert viol is not None
    assert viol.model == "account.move"


def test_allow_m2o_pair_custom_parent() -> None:
    m = _manifest()
    assert (
        check_relational_pair(
            m, parent_model="x_matter", child_model="x_matter_line"
        )
        is None
    )


def test_automation_tier1_write_blocked_chatter_allowed() -> None:
    m = _manifest()
    assert (
        check_automation_create(
            m, model="account.move", action_kind="update_field"
        )
        is not None
    )
    assert (
        check_automation_create(
            m, model="account.move", action_kind="create_activity"
        )
        is None
    )
    assert (
        check_automation_create(m, model="account.move", action_kind="mail_post")
        is None
    )
    assert (
        check_automation_create(
            m,
            model="x_matter",
            action_kind="create_record",
            target_model="account.move",
        )
        is not None
    )


def test_scrub_spec_skips_tier1_keeps_link_only() -> None:
    m = _manifest()
    spec = {
        "models": [
            {
                "model": "account.move",
                "mode": "inherit",
                "fields": [
                    {"name": "x_bad", "ttype": "char"},
                ],
            },
            {
                "model": "x_matter",
                "fields": [
                    {
                        "name": "x_invoice_id",
                        "ttype": "many2one",
                        "relation": "account.move",
                    },
                    {"name": "x_title", "ttype": "char"},
                ],
            },
        ],
        "automations": [
            {
                "name": "Post invoice",
                "model": "account.move",
                "safe_actions": [{"kind": "update_field", "field_name": "state"}],
            },
            {
                "name": "Chatter",
                "model": "account.move",
                "safe_actions": [{"kind": "mail_post"}],
            },
        ],
    }
    cleaned, skips = scrub_spec_for_protected_apply(spec, m)
    assert any("protected:" in s for s in skips)
    # Additive x_* on tier-1 kept (Studio field-pack parity)
    move = next(x for x in cleaned["models"] if x["model"] == "account.move")
    assert any(f.get("name") == "x_bad" for f in move["fields"])
    # Link-only field retained
    matter = next(x for x in cleaned["models"] if x["model"] == "x_matter")
    names = {f["name"] for f in matter["fields"]}
    assert "x_invoice_id" in names
    assert "x_title" in names
    # Chatter automation kept; write automation skipped
    autos = cleaned.get("automations") or []
    assert any(a.get("name") == "Chatter" for a in autos)
    assert not any(a.get("name") == "Post invoice" for a in autos)


def test_pcm_invoicing_draft_from_custom_allowed() -> None:
    assert check_invoicing_draft_create(source_model="x_matter") is None
    viol = check_invoicing_draft_create(source_model="account.move")
    assert viol is not None


def test_pcm_invoicing_m2m_link_only_no_violation() -> None:
    m = _manifest()
    assert (
        check_field_create(
            m,
            model="x_matter",
            ttype="many2many",
            relation="account.move",
            field_name="x_invoice_ids",
        )
        is None
    )


def test_scrub_keeps_stock_host_smart_buttons_to_custom_residual() -> None:
    """Contacts / PoS button_box → x_* residual must survive Apply scrub."""
    m = _manifest()
    spec = {
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "label": "Punch Cards",
                "related_model": "x_punch_card",
                "relation_field": "x_partner_id",
            },
            {
                "on_model": "pos.order",
                "label": "Punch Cards",
                "related_model": "x_punch_card",
                "relation_field": "x_last_transaction_id",
            },
            {
                # Still blocked: button *into* a tier-1 related model
                "on_model": "x_punch_card",
                "label": "Invoices",
                "related_model": "account.move",
                "relation_field": "x_move_id",
            },
        ]
    }
    cleaned, skips = scrub_spec_for_protected_apply(spec, m)
    hosts = {b.get("on_model") for b in cleaned["smart_buttons"]}
    assert "res.partner" in hosts
    assert "pos.order" in hosts
    assert "x_punch_card" not in hosts
    assert any("account.move" in s for s in skips)


def test_scrub_keeps_stock_link_only_smart_button_contacts_to_pickings() -> None:
    """Contacts → Transfers via existing stock.picking.partner_id must survive scrub.

    Apply injects button_box inherit and skips inventing O2M on tier-1 hosts.
    Scrub used to drop this as "mutates tier-1" even though no protected FK is created.
    """
    m = _manifest()
    spec = {
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "related_model": "stock.picking",
                "relation_field": "partner_id",
                "label": "Transfers",
                "icon": "fa-truck",
                "requires_inherit_view": True,
                "source": "senior_ops",
            },
            {
                # Still blocked: inventing custom FK onto tier-1 related
                "on_model": "res.partner",
                "related_model": "account.move",
                "relation_field": "x_partner_id",
                "label": "Invoices",
            },
        ]
    }
    cleaned, skips = scrub_spec_for_protected_apply(spec, m)
    kept = cleaned["smart_buttons"]
    assert len(kept) == 1
    assert kept[0]["label"] == "Transfers"
    assert kept[0]["relation_field"] == "partner_id"
    # Invent-FK button stripped (host is tier-1; skip names res.partner, not related).
    assert not any(b.get("label") == "Invoices" for b in kept)
    assert any("smart button mutates tier-1" in s for s in skips)
