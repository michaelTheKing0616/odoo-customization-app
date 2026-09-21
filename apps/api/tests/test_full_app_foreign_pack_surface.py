"""Residual full_app must never adopt a foreign pack's surface IR.

Class (Vehicle Request Generate regression, post Prefer-reshape lock):
- Contract chrome stays Vehicle-ish while Generate canvas is Purchase Requests
- Root: purchase_request_intent matched bare «manager approve», and
  scrub_purchase_request_prompt_fit replaced residual IR with pack surface
- Also: weak Jaccard retrieve + single foreign header identity gap

Guarantees:
- Vehicle / fleet residuals keep x_vehicle_request (not x_purchase_request)
- Actual Purchase Request prompts still get the purchase pack
- Prefer Sales / inherit field_packs still Prefer when intended
- Contract title strips Build/Create/Make
"""

from __future__ import annotations

import copy
import os

import pytest

pytestmark = pytest.mark.no_app_db

os.environ["AI_INTENT_LLM"] = "off"

from app.ai_conversation.understand import build_understanding  # noqa: E402
from app.ai_domain_coherence import (  # noqa: E402
    pack_conflicts_with_brief,
    should_apply_domain_pack,
)
from app.ai_domain_pack_purchase_request import (  # noqa: E402
    purchase_request_intent,
    purchase_request_pack,
    scrub_purchase_request_prompt_fit,
)
from app.ai_domain_packs import match_domain_pack, retrieve_domain_pack  # noqa: E402
from app.ai_draft_jobs import _finish_seed_draft  # noqa: E402
from app.ai_pipeline import seed_studio_draft  # noqa: E402
from app.ai_residual_identity import (  # noqa: E402
    draft_mismatches_residual_identity,
    enforce_residual_draft_identity,
)
from app.ai_studio_contract import build_studio_contract  # noqa: E402

VEHICLE = (
    "Build Vehicle request: employees request a fleet vehicle for a date range; "
    "manager approve/refuse; on approve, optionally link/create a Fleet vehicle "
    "assignment note. List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet or HR — pick the more natural parent."
)

PURCHASE = (
    "Build Purchase request: employees submit purchase requests with amount and "
    "currency; manager approve/refuse; list by draft/submitted/approved."
)

PREFER_SALES = (
    "Prefer for delivery + Delivery notes on sale.order already persist. "
    "Extend so they matter in workflows. Still inherit-only — no new app tile."
)


def _locked(prompt: str) -> dict:
    u = build_understanding(prompt)
    return {
        "title": u.title,
        "grain": u.grain,
        "inherit_existing": getattr(u, "inherit_existing", False),
        "host_model": u.host_model,
        "capability": getattr(u, "capability", None),
        "craft_smart_buttons": list(getattr(u, "craft_smart_buttons", None) or []),
    }


def test_vehicle_intent_does_not_claim_purchase_pack() -> None:
    assert purchase_request_intent(VEHICLE) is False
    assert match_domain_pack(VEHICLE) is None
    assert retrieve_domain_pack(VEHICLE) is None
    conflicts, notes = pack_conflicts_with_brief(
        VEHICLE, "purchase_request", purchase_request_pack()
    )
    assert conflicts is True
    assert any("purchase_request" in n for n in notes)
    ok, _ = should_apply_domain_pack(
        VEHICLE,
        "purchase_request",
        purchase_request_pack(),
        retrieval_score=0.10,
        retrieval_method="jaccard",
    )
    assert ok is False


def test_purchase_prompt_still_gets_purchase_pack() -> None:
    assert purchase_request_intent(PURCHASE) is True
    hit = match_domain_pack(PURCHASE)
    assert hit is not None and hit[0] == "purchase_request"
    seed = seed_studio_draft(PURCHASE)
    models = [
        m.get("model")
        for m in (seed.get("models") or [])
        if isinstance(m, dict)
    ]
    assert "x_purchase_request" in models
    assert seed.get("domain_pack") == "purchase_request"


def test_contract_title_strips_build_verb() -> None:
    c = build_studio_contract(VEHICLE, grain="full_app")
    title = str(c.get("title") or "")
    assert title == "Vehicle Request"
    assert not title.lower().startswith("build")
    summary = str(c.get("summary") or "").lower()
    assert "build vehicle" not in summary


def test_scrub_does_not_replace_vehicle_with_purchase_surface() -> None:
    draft = {
        "display_name": "Vehicle Request",
        "technical_name": "vehicle_request",
        "grain": "full_app",
        "domain_pack": "purchase_request",
        "_user_prompt": VEHICLE,
        "models": [
            {
                "model": "x_vehicle_request",
                "mode": "new",
                "description": "Vehicle Request",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                ],
            }
        ],
    }
    notes = scrub_purchase_request_prompt_fit(draft, prompt=VEHICLE)
    models = [
        m.get("model")
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
    ]
    assert "x_vehicle_request" in models
    assert "x_purchase_request" not in models
    assert draft.get("domain_pack") in (None, "")
    assert any("cleared foreign domain_pack" in n for n in notes) or notes == []


def test_single_foreign_purchase_header_is_identity_mismatch() -> None:
    draft = {
        "display_name": "Vehicle Request",
        "technical_name": "vehicle_request",
        "grain": "full_app",
        "_user_prompt": VEHICLE,
        "models": [
            {
                "model": "x_purchase_request",
                "mode": "new",
                "description": "Purchase Requests",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Reference"},
                    {"name": "x_amount", "ttype": "monetary", "string": "Amount"},
                ],
            }
        ],
    }
    locked = {"title": "Vehicle Request", "grain": "full_app"}
    assert draft_mismatches_residual_identity(
        draft, prompt=VEHICLE, locked=locked, prefer_locked=True
    )
    enforce_residual_draft_identity(
        draft, prompt=VEHICLE, locked=locked, prefer_locked=True
    )
    models = [
        m.get("model")
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    ]
    assert "x_vehicle_request" in models
    assert "x_purchase_request" not in models


def test_vehicle_generate_finish_keeps_vehicle_surface() -> None:
    seed = seed_studio_draft(VEHICLE)
    warnings: list[str] = []
    finished = _finish_seed_draft(
        VEHICLE,
        copy.deepcopy(seed),
        warnings,
        locked_understanding=_locked(VEHICLE),
    )
    models = [
        m.get("model")
        for m in (finished.get("models") or [])
        if isinstance(m, dict)
    ]
    assert "x_vehicle_request" in models
    assert "x_purchase_request" not in models
    assert finished.get("domain_pack") in (None, "")
    assert "vehicle" in str(finished.get("display_name") or "").lower()
    blob = str(finished.get("menus") or []).lower() + str(finished.get("actions") or []).lower()
    assert "purchase request" not in blob
    assert not any(
        "purchase_request: seeded" in w or "purchase_request: dropped" in w
        for w in warnings
    )


def test_prefer_sales_still_field_pack() -> None:
    u = build_understanding(PREFER_SALES)
    assert u.grain in {"field_pack", "feature_slice"}
    assert u.inherit_existing is True or u.host_model in {
        "sale.order",
        "res.partner",
        "product.template",
    }
