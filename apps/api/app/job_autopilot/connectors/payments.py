"""Payment acquirer recipe — stock payment.provider, never generated payment.transaction."""

from __future__ import annotations

from typing import Any

from app.job_autopilot.connectors import rpcutil
from app.job_autopilot.connectors.catalog import detected_brands
from app.job_autopilot.packet import ProbeResult


def _env_secret_note() -> str:
    """Mention env presence only — never interpolate the secret."""
    try:
        from app.settings import settings

        secret = (getattr(settings, "autopilot_payment_secret", "") or "").strip()
        token = (getattr(settings, "autopilot_webhook_token", "") or "").strip()
    except Exception:  # noqa: BLE001
        secret = token = ""
    if secret or token:
        return (
            " Partner secret/token is in env — Autopilot does not write it into "
            "Odoo, ir.config_parameter, or the packet. Live capture stays off."
        )
    return " No AUTOPILOT_PAYMENT_SECRET — fixture provider only."


def run_payments(client: Any, prompt: str) -> ProbeResult:
    brands = detected_brands(prompt, "payments")
    label = ", ".join(brands) or "generic acquirer"
    note = _env_secret_note()
    if not rpcutil.exists(client, "payment.provider"):
        return ProbeResult(
            name="payments",
            ok=False,
            detail=(
                f"Need payment.provider for {label}. Install Accounting/POS payments, "
                "then set the acquirer secret in Odoo — Autopilot never writes API keys."
                + note
            ),
        )
    rows = rpcutil.search_read(
        client,
        "payment.provider",
        [("name", "ilike", "Autopilot")],
        ["id", "name", "state"],
        limit=1,
    )
    if rows:
        return ProbeResult(
            name="payments",
            ok=True,
            detail=(
                f"provider id={rows[0].get('id')} name={rows[0].get('name')} "
                f"brands={label}.{note}"
            ),
        )
    rid = rpcutil.create(
        client,
        "payment.provider",
        {"name": f"Autopilot {label}", "state": "disabled"},
    )
    if rid:
        return ProbeResult(
            name="payments",
            ok=True,
            detail=(
                f"created payment.provider id={rid} ({label}) state=disabled. "
                "Operator enables test/prod and pastes keys in Odoo — not in the packet."
                + note
            ),
        )
    existing = rpcutil.search_read(
        client, "payment.provider", [], ["id", "name", "state"], limit=3
    )
    if existing:
        names = ", ".join(str(r.get("name")) for r in existing)
        return ProbeResult(
            name="payments",
            ok=True,
            detail=(
                f"payment.provider present ({names}). Create skipped — configure {label} "
                "on an existing provider. Secrets stay out of Autopilot.{note}"
            ),
        )
    return ProbeResult(
        name="payments",
        ok=False,
        detail=f"Could not create a provider for {label}. Configure Payments in Odoo UI.{note}",
    )
