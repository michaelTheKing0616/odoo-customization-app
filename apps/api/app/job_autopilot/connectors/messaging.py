"""Messaging channel → stock sale.order (WhatsApp/SMS/Telegram, any vertical)."""

from __future__ import annotations

from typing import Any

from app.job_autopilot.connectors.catalog import detected_brands
from app.job_autopilot.connectors.inbound import ingest_sale_order
from app.job_autopilot.packet import ProbeResult


def run_messaging(client: Any, prompt: str) -> ProbeResult:
    brands = detected_brands(prompt, "messaging")
    channel = brands[0] if brands else "messaging"
    so_id, err = ingest_sale_order(
        client,
        channel=channel,
        ref=f"autopilot:msg:{channel}:fixture",
    )
    if so_id:
        return ProbeResult(
            name="messaging",
            ok=True,
            detail=(
                f"sale.order id={so_id} from {channel} fixture. "
                "Live Cloud API tokens stay in env / Odoo, not the packet."
            ),
        )
    return ProbeResult(
        name="messaging",
        ok=False,
        detail=(
            "Could not land a messaging fixture on sale.order"
            + (f": {err}" if err else ".")
        ),
    )
