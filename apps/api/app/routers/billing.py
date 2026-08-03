"""Billing checkout, webhooks, entitlements API (MON-2)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.billing_service import (
    apply_stripe_event,
    create_stripe_checkout_session,
    create_stripe_portal_link,
    paystack_initialize,
    paystack_verify,
    record_webhook,
    verify_paystack_signature,
    verify_stripe_signature,
)
from app.db import get_db
from app.entitlements import (
    WorkspaceEntitlements,
    count_active_projects,
    resolve_entitlements,
    seed_plan_features,
)
from app.settings import settings
from app.workspace_auth import WorkspaceAuth, require_app_auth

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutBody(BaseModel):
    plan_id: str = Field(..., min_length=1, max_length=40)
    seat_quantity: int = Field(1, ge=1, le=500)
    success_url: str
    cancel_url: str


class PaystackInitBody(BaseModel):
    plan_id: str
    email: str
    callback_url: str


class EntitlementsOut(BaseModel):
    workspace_id: str
    plan_id: str
    subscription_status: str
    features: dict[str, str]
    extra_project_slots: int
    active_projects: int
    active_project_limit: int | None
    trial_ends_at: str | None = None
    current_period_end: str | None = None


@router.get("/entitlements", response_model=EntitlementsOut)
def get_entitlements(
    auth: WorkspaceAuth = Depends(require_app_auth),
    db: Session = Depends(get_db),
) -> EntitlementsOut:
    if not auth.workspace_id:
        raise HTTPException(status_code=400, detail="Workspace context required")
    ent = resolve_entitlements(db, auth.workspace_id)
    limit = ent.active_project_slot_limit()
    return EntitlementsOut(
        workspace_id=ent.workspace_id,
        plan_id=ent.plan_id,
        subscription_status=ent.subscription_status,
        features=ent.features,
        extra_project_slots=ent.extra_project_slots,
        active_projects=count_active_projects(db, ent.workspace_id),
        active_project_limit=limit,
        trial_ends_at=ent.trial_ends_at.isoformat() if ent.trial_ends_at else None,
        current_period_end=ent.current_period_end.isoformat() if ent.current_period_end else None,
    )


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)) -> list[dict]:
    seed_plan_features(db)
    from app.billing_models import BillingPlan, PlanFeature

    plans = db.query(BillingPlan).filter(BillingPlan.is_public.is_(True)).order_by(BillingPlan.sort_order).all()
    out = []
    for p in plans:
        feats = db.query(PlanFeature).filter(PlanFeature.plan_id == p.id).all()
        out.append(
            {
                "id": p.id,
                "display_name": p.display_name,
                "features": {f.feature_key: f.value for f in feats},
            }
        )
    return out


@router.post("/checkout/stripe")
def stripe_checkout(
    body: CheckoutBody,
    auth: WorkspaceAuth = Depends(require_app_auth),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not auth.workspace_id:
        raise HTTPException(status_code=400, detail="Workspace required")
    try:
        return create_stripe_checkout_session(
            workspace_id=auth.workspace_id,
            plan_id=body.plan_id,
            seat_quantity=body.seat_quantity,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/portal/stripe")
def stripe_portal(
    auth: WorkspaceAuth = Depends(require_app_auth),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not auth.workspace_id:
        raise HTTPException(status_code=400, detail="Workspace required")
    from app.entitlements import ensure_workspace_subscription

    sub = ensure_workspace_subscription(db, auth.workspace_id)
    if not sub.external_customer_id:
        raise HTTPException(status_code=400, detail="No billing customer on file")
    url = create_stripe_portal_link(
        customer_id=sub.external_customer_id,
        return_url=settings.app_public_url,
    )
    return {"portal_url": url}


@router.post("/checkout/paystack")
async def paystack_checkout(
    body: PaystackInitBody,
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    if not auth.workspace_id:
        raise HTTPException(status_code=400, detail="Workspace required")
    amount = settings.paystack_price_pro_kobo if body.plan_id == "pro" else settings.paystack_price_business_kobo
    if not amount:
        amount = 3900 * 100  # fake default for dev
    try:
        return await paystack_initialize(
            email=body.email,
            amount_kobo=amount,
            workspace_id=auth.workspace_id,
            plan_id=body.plan_id,
            callback_url=body.callback_url,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/paystack/verify/{reference}")
async def paystack_verify_route(reference: str, db: Session = Depends(get_db)) -> dict:
    data = await paystack_verify(reference)
    if data.get("status") == "success":
        meta = data.get("metadata") or {}
        workspace_id = meta.get("workspace_id")
        plan_id = meta.get("plan_id", "pro")
        if workspace_id:
            from app.entitlements import ensure_workspace_subscription

            sub = ensure_workspace_subscription(db, workspace_id)
            sub.plan_id = plan_id
            sub.status = "active"
            sub.processor = "paystack"
            db.add(sub)
            db.commit()
    return data


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if not verify_stripe_signature(payload, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")
    event = json.loads(payload.decode("utf-8"))
    event_id = str(event.get("id", ""))
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing event id")
    if not record_webhook(db, processor="stripe", event_id=event_id, payload=event):
        return {"status": "duplicate"}
    apply_stripe_event(db, event)
    return {"status": "ok"}


@router.post("/webhooks/paystack")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    payload = await request.body()
    sig = request.headers.get("x-paystack-signature", "")
    if not verify_paystack_signature(payload, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")
    event = json.loads(payload.decode("utf-8"))
    event_id = str(event.get("data", {}).get("id") or event.get("event", ""))
    if not record_webhook(db, processor="paystack", event_id=event_id, payload=event):
        return {"status": "duplicate"}
    # Minimal mapping — charge.success upgrades plan from metadata
    if event.get("event") == "charge.success":
        data = event.get("data") or {}
        meta = data.get("metadata") or {}
        workspace_id = meta.get("workspace_id")
        plan_id = meta.get("plan_id", "pro")
        if workspace_id:
            from app.entitlements import ensure_workspace_subscription

            sub = ensure_workspace_subscription(db, workspace_id)
            sub.plan_id = plan_id
            sub.status = "active"
            sub.processor = "paystack"
            db.add(sub)
            db.commit()
    return {"status": "ok"}
