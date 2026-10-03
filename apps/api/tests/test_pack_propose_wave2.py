"""Wave 2 — pack invent only via admit_and_apply."""

from __future__ import annotations

from app.ai_domain_packs import admit_pack_models, car_rental_pack, merge_domain_pack
from app.ai_generate_ir_lint import invent_outside_admit_violations
from app.ai_pipeline import seed_studio_draft


def test_pack_seed_admits_models_not_deepcopy() -> None:
    prompt = (
        "Build a car rental system with vehicles, rental contracts, "
        "branches, and damage reports"
    )
    draft = seed_studio_draft(prompt)
    assert draft.get("domain_pack") == "car_rental"
    assert draft.get("_pipeline") == "pack_seed"
    models = [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    ]
    assert models, "pack seed must admit pack models"
    assert any(m.startswith("x_rent") for m in models)
    ir = draft.get("_generate_ir") if isinstance(draft.get("_generate_ir"), dict) else {}
    admitted = ir.get("admitted") or []
    assert admitted, "pack seed must leave GenerateIR.admitted"
    # Invent-source pack fields must be covered by admit (nested model payloads OK).
    assert invent_outside_admit_violations(draft) == []


def test_merge_pack_proposes_missing_model() -> None:
    pack = car_rental_pack()
    thin = {
        "domain_pack": "car_rental",
        "_user_prompt": "car rental vehicles and contracts",
        "models": [
            {
                "model": "x_rent_vehicle",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
    }
    out, notes = merge_domain_pack(thin, pack)
    ids = {
        str(m.get("model"))
        for m in (out.get("models") or [])
        if isinstance(m, dict)
    }
    assert "x_rent_vehicle" in ids
    assert any("propose model" in n or "admitted model" in n for n in notes)
    assert invent_outside_admit_violations(out) == []


def test_pack_spray_without_cue_rejected() -> None:
    pack = {
        "domain_pack": "toy",
        "models": [
            {
                "model": "x_toy",
                "description": "Toy",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            }
        ],
    }
    draft: dict = {
        "domain_pack": "toy",
        "_user_prompt": "toy inventory name only",
        "models": [],
    }
    gate = admit_pack_models(draft, pack, proposer="domain_pack")
    assert any("admitted model" in g for g in gate) or any(
        str(m.get("model")) == "x_toy" for m in (draft.get("models") or [])
    )
    partners = [
        f
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        for f in (m.get("fields") or [])
        if isinstance(f, dict) and f.get("name") == "x_partner_id"
    ]
    assert partners == [], "uncued pack spray must not invent"
    ir = draft.get("_generate_ir") if isinstance(draft.get("_generate_ir"), dict) else {}
    rejected = ir.get("rejected_proposals") or []
    assert any(
        isinstance(r, dict) and r.get("name") == "x_partner_id" for r in rejected
    )
