"""Class-wide domain-pack adoption policy — residual Contract identity wins.

Shared workflow words (manager approve, request, amount, date, employee, status)
must NEVER alone adopt a foreign pack's models/menus/actions/title onto a residual
full_app. Positive pack-specific product cues are required. Prefer inherit paths
and real pack briefs still work.
"""

from __future__ import annotations

import copy
import os

import pytest

pytestmark = pytest.mark.no_app_db

os.environ["AI_INTENT_LLM"] = "off"

from app.ai_conversation.understand import build_understanding  # noqa: E402
from app.ai_domain_coherence import (  # noqa: E402
    pack_adoption_cues_present,
    pack_conflicts_with_brief,
    residual_noun_conflicts_pack,
    should_apply_domain_pack,
)
from app.ai_domain_pack_purchase_request import (  # noqa: E402
    purchase_request_intent,
    purchase_request_pack,
)
from app.ai_domain_packs import (  # noqa: E402
    load_domain_pack,
    match_domain_pack,
    retrieve_domain_pack,
    retrieve_domain_pack_lexical,
    score_domain_pack,
)
from app.ai_draft_jobs import _finish_seed_draft  # noqa: E402
from app.ai_pipeline import seed_studio_draft  # noqa: E402

VEHICLE = (
    "Build Vehicle request: employees request a fleet vehicle for a date range; "
    "manager approve/refuse; on approve, optionally link/create a Fleet vehicle "
    "assignment note. List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet or HR — pick the more natural parent."
)
FLEET_LIKE = (
    "Employees request a company car for travel dates; manager approve or refuse; "
    "status draft/submitted/approved. Amount of passengers and date of trip."
)
VISITOR = (
    "Build Visitor Log: front desk logs visitors with host employee, badge, "
    "check-in/out times; manager can approve VIP visits. List by date."
)
DINING = (
    "Build Dining Tables app: track table status Free/Seated/Reserved; "
    "manager approve large party requests; amount of seats; employee assigned "
    "as waiter note."
)
SHARED_VERBS = (
    "Build Approval Workflow: employees submit a request with amount and date; "
    "manager approve; status draft submitted approved; employee field."
)
PURCHASE = (
    "Build Purchase request: employees submit purchase requests with amount and "
    "currency; manager approve/refuse; list by draft/submitted/approved."
)
RESTAURANT = (
    "Restaurant Management: dining tables, kitchen tickets, waiter assignments, "
    "food menu items."
)
PREFER_SALES = (
    "Prefer for delivery + Delivery notes on sale.order already persist. "
    "Extend so they matter in workflows. Still inherit-only — no new app tile."
)
CONTACTS_PREFER = (
    "Prefer Contacts: add loyalty punch card fields on res.partner; inherit only."
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


@pytest.mark.parametrize(
    "prompt",
    [VEHICLE, FLEET_LIKE, VISITOR, SHARED_VERBS, DINING],
)
def test_residuals_never_retrieve_purchase_pack(prompt: str) -> None:
    assert purchase_request_intent(prompt) is False
    assert pack_adoption_cues_present(prompt, "purchase_request") is False
    assert match_domain_pack(prompt) is None or match_domain_pack(prompt)[0] != "purchase_request"
    assert retrieve_domain_pack(prompt) is None or retrieve_domain_pack(prompt)[0] != "purchase_request"
    assert retrieve_domain_pack_lexical(prompt) is None or (
        retrieve_domain_pack_lexical(prompt)[0] != "purchase_request"
    )
    conflicts, _ = pack_conflicts_with_brief(
        prompt, "purchase_request", purchase_request_pack()
    )
    assert conflicts is True
    ok, _ = should_apply_domain_pack(
        prompt,
        "purchase_request",
        purchase_request_pack(),
        retrieval_score=0.20,
        retrieval_method="jaccard",
    )
    assert ok is False
    assert score_domain_pack(prompt, purchase_request_pack()) < 0.12


def test_shared_verbs_alone_adopt_no_pack() -> None:
    assert match_domain_pack(SHARED_VERBS) is None
    assert retrieve_domain_pack(SHARED_VERBS) is None
    assert retrieve_domain_pack_lexical(SHARED_VERBS) is None


def test_visitor_does_not_become_restaurant_or_hotel() -> None:
    assert match_domain_pack(VISITOR) is None
    hit = retrieve_domain_pack(VISITOR)
    assert hit is None
    for pack_id in ("restaurant", "hotel", "purchase_request"):
        conflicts, _ = residual_noun_conflicts_pack(
            VISITOR, pack_id, load_domain_pack(pack_id)
        )
        assert conflicts is True


def test_restaurant_still_gets_restaurant_not_visitor_or_purchase() -> None:
    hit = match_domain_pack(RESTAURANT)
    assert hit is not None and hit[0] == "restaurant"
    assert purchase_request_intent(RESTAURANT) is False
    conflicts, _ = residual_noun_conflicts_pack(
        RESTAURANT, "purchase_request", purchase_request_pack()
    )
    assert conflicts is True


def test_real_purchase_still_adopts_purchase_pack() -> None:
    assert purchase_request_intent(PURCHASE) is True
    assert pack_adoption_cues_present(PURCHASE, "purchase_request") is True
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


def test_vehicle_generate_finish_keeps_vehicle_not_purchase() -> None:
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
    blob = (
        str(finished.get("menus") or []).lower()
        + str(finished.get("actions") or []).lower()
        + str(finished.get("display_name") or "").lower()
    )
    assert "purchase request" not in blob


def test_fleet_like_generate_never_stamps_purchase() -> None:
    seed = seed_studio_draft(FLEET_LIKE)
    warnings: list[str] = []
    finished = _finish_seed_draft(
        FLEET_LIKE,
        copy.deepcopy(seed),
        warnings,
        locked_understanding=_locked(FLEET_LIKE),
    )
    assert finished.get("domain_pack") in (None, "")
    models = [
        str(m.get("model") or "")
        for m in (finished.get("models") or [])
        if isinstance(m, dict)
    ]
    assert "x_purchase_request" not in models
    assert all("purchase" not in m for m in models)


def test_prefer_sales_and_contacts_still_inherit() -> None:
    u = build_understanding(PREFER_SALES)
    assert u.grain in {"field_pack", "feature_slice"}
    assert u.inherit_existing is True or u.host_model == "sale.order"
    assert match_domain_pack(PREFER_SALES) is None

    u2 = build_understanding(CONTACTS_PREFER)
    assert u2.grain in {"field_pack", "feature_slice"}
    assert u2.inherit_existing is True or u2.host_model == "res.partner"
    assert match_domain_pack(CONTACTS_PREFER) is None


def test_jaccard_ignores_shared_workflow_overlap() -> None:
    """manager/approve/request alone must not score purchase above the floor."""
    score = score_domain_pack(FLEET_LIKE, purchase_request_pack())
    assert score == 0.0 or score < 0.08
