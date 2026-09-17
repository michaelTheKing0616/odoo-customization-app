"""Structural Expert repair + inherit-only Generate — no Prefer residual."""

from __future__ import annotations

from app.ai_component_builder import draft_component_from_prompt, inherit_only_display_name
from app.ai_conversation.refine import apply_refinement, wants_structural_repair
from app.ai_grain import classify_grain, is_inherit_only_ops
from app.ai_surface_invariants import title_is_grounded

OPS = (
    "Prefer for delivery + Delivery notes on res.partner already persist. "
    "Extend so they matter in workflows: surface preferred-delivery Contacts on "
    "pickings/transfers (domain or smart button), optional filter on Delivery/Inventory "
    "lists, and/or a light automation when the box is checked. Still inherit-only — "
    "no new app tile."
)

REPAIR = (
    "Fix surface findings that block Install. Ground the app title in the operator brief "
    "(never a placeholder like Contact extras). Keep inherit-only on the named stock host — "
    "no new home-screen app. Preserve Must-do wiring."
)

RESIDUAL = {
    "display_name": "Contacts extension",
    "technical_name": "x_prefer",
    "grain": "full_app",
    "models": [
        {
            "model": "x_prefer",
            "mode": "new",
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                {
                    "name": "x_partner_id",
                    "ttype": "many2one",
                    "string": "res.partner",
                    "relation": "res.partner",
                },
                {"name": "x_notes", "ttype": "text", "string": "Notes"},
                {
                    "name": "x_company_id",
                    "ttype": "many2one",
                    "string": "Company",
                    "relation": "res.company",
                },
            ],
        }
    ],
    "menus": [{"name": "Prefer"}],
    "actions": [{"name": "Prefer"}],
    "_user_prompt": OPS,
}


def test_generate_inherit_only_is_field_pack_on_partner() -> None:
    assert is_inherit_only_ops(OPS)
    assert classify_grain(OPS) == "field_pack"
    draft, _hosts, _warn = draft_component_from_prompt(OPS, grain="field_pack")
    assert draft.get("display_name") == inherit_only_display_name(OPS, "Contacts")
    assert title_is_grounded(str(draft.get("display_name")), OPS)
    assert not title_is_grounded("Contacts extension", OPS)
    models = draft.get("models") or []
    assert any(
        m.get("model") == "res.partner" and m.get("mode") == "inherit" for m in models
    )
    assert not any(
        str(m.get("mode") or "") == "new" or str(m.get("model") or "").startswith("x_")
        for m in models
        if isinstance(m, dict)
    )
    assert not (draft.get("menus") or [])


def test_expert_structural_repair_reshapes_prefer_residual() -> None:
    assert wants_structural_repair(REPAIR)
    result = apply_refinement(RESIDUAL, REPAIR, prompt=OPS, provider=None)
    assert result.get("ok") is True
    assert result.get("structural") is True
    draft = result["draft"]
    assert draft["display_name"] == "Contacts delivery preferences"
    assert title_is_grounded(draft["display_name"], OPS)
    assert draft.get("grain") == "field_pack"
    models = draft.get("models") or []
    assert len(models) == 1
    assert models[0]["model"] == "res.partner"
    assert models[0]["mode"] == "inherit"
    labels = {str(f.get("string")) for f in models[0].get("fields") or []}
    assert "Prefer for delivery" in labels
    assert "Delivery notes" in labels
    assert "Name" not in labels
    assert "Notes" not in labels  # bare Notes must not ride along
    assert not (draft.get("menus") or [])


def test_field_chrome_still_works_for_ordinary_refine() -> None:
    draft = {
        "display_name": "Contacts delivery preferences",
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [
                    {
                        "name": "x_prefer_for_delivery",
                        "ttype": "boolean",
                        "string": "Prefer for delivery",
                    },
                    {
                        "name": "x_delivery_notes",
                        "ttype": "text",
                        "string": "Delivery notes",
                    },
                ],
            }
        ],
    }
    result = apply_refinement(
        draft, "make Delivery notes required", prompt=OPS, provider=None
    )
    assert result.get("ok") is True
    assert not result.get("structural")
    fields = (result["draft"]["models"][0].get("fields") or [])
    notes = next(f for f in fields if f.get("string") == "Delivery notes")
    assert notes.get("required") is True
