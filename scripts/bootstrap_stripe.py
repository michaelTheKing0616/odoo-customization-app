#!/usr/bin/env python3
"""Idempotent Stripe product/price bootstrap for test or live mode (MON-2).

Requires STRIPE_SECRET_KEY. Prints price IDs to set in .env — never commits secrets.
"""

from __future__ import annotations

import os
import sys

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from app.settings import settings  # noqa: E402


PLANS = [
    ("pro", "Odoo Custom Pro", 3900),
    ("business", "Odoo Custom Business", 14900),
    ("agency", "Odoo Custom Agency", 39900),
    ("project_pass", "Odoo Custom Project Pass", 29900),
]


def main() -> None:
    key = (settings.stripe_secret_key or os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not key:
        print("Set STRIPE_SECRET_KEY or stripe_secret_key in .env", file=sys.stderr)
        sys.exit(1)

    import stripe

    stripe.api_key = key
    print("# Add these to .env (test-mode price IDs from your Stripe account):")
    for plan_id, name, cents in PLANS:
        products = stripe.Product.list(limit=100, active=True)
        product = next((p for p in products.data if p.metadata.get("plan_id") == plan_id), None)
        if product is None:
            product = stripe.Product.create(name=name, metadata={"plan_id": plan_id})
        prices = stripe.Price.list(product=product.id, active=True, limit=10)
        price = next((p for p in prices.data if p.unit_amount == cents), None)
        if price is None:
            mode = "payment" if plan_id == "project_pass" else "recurring"
            kwargs: dict = {
                "product": product.id,
                "unit_amount": cents,
                "currency": "usd",
            }
            if mode == "recurring":
                kwargs["recurring"] = {"interval": "month"}
            price = stripe.Price.create(**kwargs)
        env_key = f"STRIPE_PRICE_{plan_id.upper()}"
        print(f"{env_key}={price.id}")


if __name__ == "__main__":
    main()
