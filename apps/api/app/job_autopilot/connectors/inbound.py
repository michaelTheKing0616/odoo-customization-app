"""Inbound channel orders → stock sale.order (any vertical)."""

from __future__ import annotations

from typing import Any

from app.job_autopilot.connectors import rpcutil
from app.job_autopilot.connectors.catalog import detected_brands
from app.job_autopilot.packet import ProbeResult


def _product_create_vals() -> list[dict[str, Any]]:
    """Match smoke product shapes — Odoo 19 consu vs older type=product."""
    return [
        {
            "name": "Autopilot Channel Product",
            "type": "consu",
            "list_price": 10.0,
            "invoice_policy": "order",
        },
        {
            "name": "Autopilot Channel Product",
            "list_price": 10.0,
            "invoice_policy": "order",
        },
        {"name": "Autopilot Channel Product", "list_price": 10.0},
    ]


def _ensure_product_id(client: Any) -> int | None:
    existing = rpcutil.first_product_id(client)
    if existing:
        return existing
    if not rpcutil.exists(client, "product.template"):
        return None
    tmpl_id: int | None = None
    for vals in _product_create_vals():
        tmpl_id = rpcutil.create(client, "product.template", vals)
        if tmpl_id:
            break
    if not tmpl_id:
        return None
    if not rpcutil.exists(client, "product.product"):
        return None
    variants = rpcutil.search(
        client,
        "product.product",
        [("product_tmpl_id", "=", tmpl_id)],
        limit=1,
    )
    if variants:
        return variants[0]
    return rpcutil.create(
        client,
        "product.product",
        {"name": "Autopilot Channel Product", "product_tmpl_id": tmpl_id},
    )


def _line_vals(product_id: int) -> dict[str, Any]:
    return {"product_id": product_id, "product_uom_qty": 1.0, "price_unit": 10.0}


def ingest_sale_order(
    client: Any,
    *,
    channel: str,
    ref: str,
) -> tuple[int | None, str | None]:
    """Create a fixture sale.order. Returns (id, error_detail)."""
    if not rpcutil.exists(client, "sale.order"):
        return None, "sale.order missing (install Sales)"
    partner_id = rpcutil.first_partner_id(client)
    product_id = _ensure_product_id(client)
    if not partner_id:
        return None, "could not resolve/create res.partner"
    if not product_id:
        return None, "could not resolve/create product.product"
    line = _line_vals(product_id)
    vals: dict[str, Any] = {
        "partner_id": partner_id,
        "client_order_ref": ref[:64],
        "order_line": [(0, 0, line)],
    }
    rid = rpcutil.create(client, "sale.order", vals)
    if rid:
        return rid, None
    # Fallback: header then line (some majors reject command create)
    header = rpcutil.create(
        client,
        "sale.order",
        {"partner_id": partner_id, "client_order_ref": ref[:64]},
    )
    if not header:
        return None, "sale.order create failed (header and command)"
    if rpcutil.exists(client, "sale.order.line"):
        line_id = rpcutil.create(
            client,
            "sale.order.line",
            {"order_id": header, **line},
        )
        if not line_id:
            return header, "sale.order created but order line create failed"
    return header, None


def run_inbound_orders(client: Any, prompt: str) -> ProbeResult:
    brands = detected_brands(prompt, "inbound_orders")
    channel = brands[0] if brands else "channel"
    if rpcutil.exists(client, "autopilot.connector.event"):
        try:
            rid = client.execute_kw(
                "autopilot.connector.event",
                "ingest_channel_order",
                [channel, {"sku": "fixture", "qty": 1, "ref": "fixture-1"}],
            )
            return ProbeResult(
                name="inbound_orders",
                ok=True,
                detail=f"addon ingest channel={channel} event_id={rid}",
            )
        except Exception as exc:  # noqa: BLE001
            # Fall through to stock sale.order
            fallback_note = f"addon ingest failed ({exc}); "
    else:
        fallback_note = ""
    so_id, err = ingest_sale_order(
        client,
        channel=channel,
        ref=f"autopilot:{channel}:fixture",
    )
    if so_id:
        return ProbeResult(
            name="inbound_orders",
            ok=True,
            detail=f"{fallback_note}sale.order id={so_id} channel={channel}",
        )
    return ProbeResult(
        name="inbound_orders",
        ok=False,
        detail=f"{fallback_note}Could not land inbound fixture on sale.order: {err or 'unknown'}",
    )


__all__ = [
    "ingest_sale_order",
    "run_inbound_orders",
]
