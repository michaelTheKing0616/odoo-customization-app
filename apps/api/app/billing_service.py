"""Stripe/Paystack billing helpers (MON-2)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.billing_models import BillingWebhookEvent, ProjectPass, WorkspaceSubscription
from app.entitlements import ensure_workspace_subscription, seed_plan_features
from app.settings import settings

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def billing_enabled() -> bool:
    return settings.billing_mode.strip().lower() in {"fake", "live", "test"}


def stripe_available() -> bool:
    return bool((settings.stripe_secret_key or "").strip())


def paystack_available() -> bool:
    return bool((settings.paystack_secret_key or "").strip())


def verify_stripe_signature(payload: bytes, sig_header: str) -> bool:
    secret = (settings.stripe_webhook_secret or "").strip()
    if not secret:
        return settings.billing_mode.strip().lower() == "fake"
    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    timestamp = parts.get("t", "")
    v1 = parts.get("v1", "")
    signed = f"{timestamp}.{payload.decode('utf-8')}"
    expected = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def verify_paystack_signature(payload: bytes, sig_header: str) -> bool:
    secret = (settings.paystack_secret_key or "").strip()
    if not secret:
        return settings.billing_mode.strip().lower() == "fake"
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)


def record_webhook(db: Session, *, processor: str, event_id: str, payload: dict) -> bool:
    existing = (
        db.query(BillingWebhookEvent)
        .filter(BillingWebhookEvent.processor == processor, BillingWebhookEvent.event_id == event_id)
        .first()
    )
    if existing:
        return False
    db.add(
        BillingWebhookEvent(
            processor=processor,
            event_id=event_id,
            payload_json=json.dumps(payload),
        )
    )
    db.commit()
    return True


def apply_stripe_event(db: Session, event: dict) -> None:
    seed_plan_features(db)
    etype = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}
    metadata = obj.get("metadata") or {}

    if etype == "checkout.session.completed":
        workspace_id = metadata.get("workspace_id")
        plan_id = metadata.get("plan_id", "pro")
        mode = obj.get("mode")
        if not workspace_id:
            return
        sub = ensure_workspace_subscription(db, workspace_id)
        if mode == "payment" and metadata.get("sku") == "project_pass":
            db.add(
                ProjectPass(
                    workspace_id=workspace_id,
                    status="active",
                    expires_at=_now() + timedelta(days=60),
                )
            )
        else:
            sub.plan_id = plan_id
            sub.status = "active"
            sub.processor = "stripe"
            sub.external_customer_id = str(obj.get("customer") or "")
            sub.external_subscription_id = str(obj.get("subscription") or "")
        db.add(sub)
        db.commit()
        return

    if etype in {"customer.subscription.updated", "customer.subscription.created"}:
        workspace_id = metadata.get("workspace_id")
        if not workspace_id:
            return
        sub = ensure_workspace_subscription(db, workspace_id)
        sub.processor = "stripe"
        sub.external_subscription_id = str(obj.get("id") or "")
        sub.external_customer_id = str(obj.get("customer") or "")
        status = str(obj.get("status") or "active")
        sub.status = "trialing" if status == "trialing" else "active" if status == "active" else status
        plan_id = metadata.get("plan_id")
        if plan_id:
            sub.plan_id = plan_id
        trial_end = obj.get("trial_end")
        if trial_end:
            sub.trial_ends_at = datetime.fromtimestamp(int(trial_end), tz=timezone.utc)
        db.add(sub)
        db.commit()
        return

    if etype == "customer.subscription.deleted":
        workspace_id = metadata.get("workspace_id")
        if not workspace_id:
            return
        sub = ensure_workspace_subscription(db, workspace_id)
        sub.status = "canceled"
        sub.plan_id = "free_solo"
        sub.canceled_at = _now()
        db.add(sub)
        db.commit()
        return

    if etype == "invoice.payment_failed":
        workspace_id = metadata.get("workspace_id")
        if not workspace_id:
            return
        sub = ensure_workspace_subscription(db, workspace_id)
        sub.status = "past_due"
        db.add(sub)
        db.commit()


def create_stripe_checkout_session(
    *,
    workspace_id: str,
    plan_id: str,
    seat_quantity: int = 1,
    success_url: str,
    cancel_url: str,
) -> dict[str, str]:
    if not stripe_available():
        if settings.billing_mode.strip().lower() == "fake":
            fake_id = f"cs_fake_{workspace_id[:8]}"
            return {
                "checkout_url": f"{success_url}?session_id={fake_id}&fake=1",
                "session_id": fake_id,
                "mode": "fake",
            }
        raise RuntimeError("Stripe not configured")

    import stripe

    stripe.api_key = settings.stripe_secret_key
    price_map = settings.stripe_price_map()
    price_id = price_map.get(plan_id)
    if not price_id:
        raise RuntimeError(f"No Stripe price configured for plan {plan_id}")

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": seat_quantity}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"workspace_id": workspace_id, "plan_id": plan_id},
    )
    return {"checkout_url": session.url or "", "session_id": session.id, "mode": "stripe"}


def create_stripe_portal_link(*, customer_id: str, return_url: str) -> str:
    if not stripe_available():
        return return_url
    import stripe

    stripe.api_key = settings.stripe_secret_key
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
    return session.url or return_url


async def paystack_initialize(
    *,
    email: str,
    amount_kobo: int,
    workspace_id: str,
    plan_id: str,
    callback_url: str,
) -> dict:
    if not paystack_available():
        if settings.billing_mode.strip().lower() == "fake":
            return {
                "authorization_url": f"{callback_url}?reference=fake_ps_{workspace_id[:8]}",
                "reference": f"fake_ps_{workspace_id[:8]}",
                "mode": "fake",
            }
        raise RuntimeError("Paystack not configured")

    headers = {"Authorization": f"Bearer {settings.paystack_secret_key}"}
    payload = {
        "email": email,
        "amount": amount_kobo,
        "callback_url": callback_url,
        "metadata": {"workspace_id": workspace_id, "plan_id": plan_id},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post("https://api.paystack.co/transaction/initialize", json=payload, headers=headers)
        res.raise_for_status()
        data = res.json()["data"]
        return {"authorization_url": data["authorization_url"], "reference": data["reference"], "mode": "paystack"}


async def paystack_verify(reference: str) -> dict:
    if not paystack_available():
        if settings.billing_mode.strip().lower() == "fake":
            return {"status": "success", "reference": reference, "mode": "fake"}
        raise RuntimeError("Paystack not configured")
    headers = {"Authorization": f"Bearer {settings.paystack_secret_key}"}
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
        res.raise_for_status()
        return res.json()["data"]
