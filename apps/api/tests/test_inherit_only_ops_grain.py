"""Inherit-only ops extension: field_pack grain, no Contact extras title."""

from __future__ import annotations

from app.ai_component_builder import build_component_draft
from app.ai_connect_points import propose_connect_points
from app.ai_grain import HostCandidate, classify_grain, is_inherit_only_ops
from app.ai_surface_invariants import title_is_grounded

OPS = (
    "Prefer for delivery + Delivery notes on res.partner already persist. "
    "Extend so they matter in workflows: surface preferred-delivery Contacts on "
    "pickings/transfers (domain or smart button), optional filter on Delivery/Inventory "
    "lists, and/or a light automation when the box is checked. Still inherit-only — "
    "no new app tile."
)

S1 = (
    "On Contacts, add checkbox Prefer for delivery and Delivery notes text under "
    "Delivery group. Do not create a new app."
)


def test_ops_extension_is_field_pack_not_feature_slice() -> None:
    assert is_inherit_only_ops(OPS) is True
    assert classify_grain(OPS) == "field_pack"


def test_smart_button_alone_does_not_force_slice_when_inherit_only() -> None:
    # Regression: _SLICE_RE matches "smart button" but inherit-only must win.
    assert "smart button" in OPS.lower() or "smart button" in OPS.lower().replace("-", " ")
    assert classify_grain(OPS) != "feature_slice"


def test_generic_extras_title_not_grounded_for_ops_brief() -> None:
    assert title_is_grounded("Contact extras", OPS) is False
    assert title_is_grounded("Inventory extras", OPS) is False


def test_ops_component_draft_inherits_partner_without_extras_title() -> None:
    host = HostCandidate(
        model="res.partner",
        label="Contacts",
        score=1.0,
        module="contacts",
        reason="test",
    )
    grain = classify_grain(OPS)
    cp = propose_connect_points(OPS, grain=grain, host=host)
    assert cp.get("sub_menu_name") in (None, "")
    out = build_component_draft(
        prompt=OPS,
        grain=grain,
        host=host,
        connect_points=cp,
        fields=[
            {
                "name": "x_prefer_for_delivery",
                "ttype": "boolean",
                "string": "Prefer for delivery",
            },
            {"name": "x_delivery_notes", "ttype": "text", "string": "Delivery notes"},
        ],
    )
    draft = out[0] if isinstance(out, tuple) else out
    display = str(draft.get("display_name") or "")
    assert display.lower() != "contact extras"
    assert "extras" not in display.lower()
    models = draft.get("models") or []
    assert any(
        str(m.get("model")) == "res.partner" and str(m.get("mode") or "") == "inherit"
        for m in models
        if isinstance(m, dict)
    )
    assert not (draft.get("menus") or []), "field_pack must not invent a home/sub menu tile"


def test_s1_field_pack_still_field_pack() -> None:
    assert classify_grain(S1) == "field_pack"
