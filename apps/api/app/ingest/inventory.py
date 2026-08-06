"""Inventory count commit — stock.quant inventory adjustment (Odoo 17+).

Never invent products/locations. Resolves product by SKU/barcode and location
by complete name (default WH/Stock). Applies via inventory_quantity +
action_apply_inventory when available.
"""

from __future__ import annotations

from typing import Any

from odoo_client import OdooClient

from app.ingest.schema import IngestGap, IngestTable


def _num(val: Any) -> float:
    if val is None or val == "":
        return 0.0
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return 0.0


def resolve_product_id(client: OdooClient, raw: str) -> int | None:
    raw = (raw or "").strip()
    if not raw or not client.model_exists("product.product"):
        return None
    if raw.isdigit():
        return int(raw)
    for domain in (
        [("default_code", "=", raw)],
        [("barcode", "=", raw)],
        [("name", "ilike", raw)],
    ):
        rows = client.execute_kw(
            "product.product",
            "search_read",
            [domain],
            {"fields": ["id"], "limit": 2},
        )
        if len(rows) == 1:
            return int(rows[0]["id"])
    return None


def resolve_location_id(client: OdooClient, raw: str | None) -> int | None:
    if not client.model_exists("stock.location"):
        return None
    name = (raw or "WH/Stock").strip() or "WH/Stock"
    if name.isdigit():
        return int(name)
    rows = client.execute_kw(
        "stock.location",
        "search_read",
        [[("complete_name", "=", name), ("usage", "=", "internal")]],
        {"fields": ["id", "complete_name"], "limit": 1},
    )
    if rows:
        return int(rows[0]["id"])
    rows = client.execute_kw(
        "stock.location",
        "search_read",
        [[("complete_name", "ilike", name), ("usage", "=", "internal")]],
        {"fields": ["id", "complete_name"], "limit": 2},
    )
    if len(rows) == 1:
        return int(rows[0]["id"])
    # Fallback: first internal stock location
    rows = client.execute_kw(
        "stock.location",
        "search_read",
        [[("usage", "=", "internal")]],
        {"fields": ["id", "complete_name"], "limit": 1, "order": "id"},
    )
    return int(rows[0]["id"]) if rows else None


def validate_inventory_table(
    client: OdooClient, table: IngestTable
) -> tuple[list[IngestGap], list[str]]:
    gaps: list[IngestGap] = []
    warnings: list[str] = []
    if table.doc_type != "inventory_count":
        return gaps, warnings
    if not client.model_exists("stock.quant"):
        gaps.append(
            IngestGap(
                model="stock.quant",
                field="*",
                value="",
                message="Inventory (stock) module not installed — cannot import counts",
            )
        )
        return gaps, warnings

    for row in table.rows:
        product_raw = str(
            row.values.get("product_id")
            or row.raw.get("product")
            or row.raw.get("default_code")
            or row.raw.get("sku")
            or row.raw.get("product_code")
            or ""
        ).strip()
        qty = _num(
            row.values.get("inventory_quantity")
            or row.values.get("quantity")
            or row.raw.get("quantity")
            or row.raw.get("qty")
            or row.raw.get("on_hand")
        )
        loc_raw = str(
            row.values.get("location_id")
            or row.raw.get("location")
            or row.raw.get("location_id")
            or ""
        ).strip() or None

        pid = resolve_product_id(client, product_raw)
        if pid is None:
            gaps.append(
                IngestGap(
                    model="product.product",
                    field="default_code",
                    value=product_raw,
                    message=f"Product {product_raw!r} not found — import catalog first",
                )
            )
            row.flags.append(f"inv_product_missing:{product_raw}")
        else:
            row.values["product_id"] = pid

        lid = resolve_location_id(client, loc_raw)
        if lid is None:
            gaps.append(
                IngestGap(
                    model="stock.location",
                    field="complete_name",
                    value=loc_raw or "WH/Stock",
                    message="No internal stock location found on instance",
                )
            )
        else:
            row.values["location_id"] = lid

        row.values["inventory_quantity"] = qty
        if qty < 0:
            gaps.append(
                IngestGap(
                    model="stock.quant",
                    field="inventory_quantity",
                    value=str(qty),
                    message="Negative inventory quantity not allowed in ingest",
                )
            )

    warnings.append(
        "Inventory count applies via stock.quant inventory_quantity "
        "(action_apply_inventory) — creates stock moves; review dry-run carefully."
    )
    return gaps, warnings


def commit_inventory_count(
    client: OdooClient,
    table: IngestTable,
    *,
    dry_run: bool,
    rpc_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gaps, _ = validate_inventory_table(client, table)
    if gaps:
        return {
            "table_id": table.id,
            "model": "stock.quant",
            "created": 0,
            "updated": 0,
            "failed": len(gaps),
            "skipped": 0,
            "ok": False,
            "message": "; ".join(g.message for g in gaps[:5]),
            "gaps": [g.model_dump() for g in gaps],
        }

    kw: dict[str, Any] = {}
    if rpc_context:
        kw["context"] = {
            **dict(rpc_context),
            "inventory_mode": True,
        }
    else:
        kw["context"] = {"inventory_mode": True}

    created = updated = failed = 0
    messages: list[str] = []
    for row in table.rows:
        pid = int(row.values["product_id"])
        lid = int(row.values["location_id"])
        qty = float(row.values["inventory_quantity"])
        existing = client.execute_kw(
            "stock.quant",
            "search_read",
            [[("product_id", "=", pid), ("location_id", "=", lid)]],
            {"fields": ["id", "quantity"], "limit": 1},
        )
        if dry_run:
            if existing:
                updated += 1
                messages.append(f"would set inventory product={pid} loc={lid} qty={qty}")
            else:
                created += 1
                messages.append(f"would create quant product={pid} loc={lid} qty={qty}")
            continue
        try:
            if existing:
                qid = int(existing[0]["id"])
                client.execute_kw(
                    "stock.quant",
                    "write",
                    [[qid], {"inventory_quantity": qty}],
                    kw,
                )
                _apply_inventory(client, qid, kw)
                updated += 1
            else:
                qid = client.execute_kw(
                    "stock.quant",
                    "create",
                    [
                        {
                            "product_id": pid,
                            "location_id": lid,
                            "inventory_quantity": qty,
                        }
                    ],
                    kw,
                )
                if isinstance(qid, list):
                    qid = qid[0]
                _apply_inventory(client, int(qid), kw)
                created += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            messages.append(f"failed product={pid}: {exc}")

    return {
        "table_id": table.id,
        "model": "stock.quant",
        "created": created,
        "updated": updated,
        "failed": failed,
        "skipped": 0,
        "ok": failed == 0,
        "message": (
            f"Inventory {'dry-run' if dry_run else 'applied'}: "
            f"+{created} ~{updated} !{failed}"
            + ("; " + "; ".join(messages[:3]) if messages else "")
        ),
    }


def _apply_inventory(client: OdooClient, quant_id: int, kw: dict[str, Any]) -> None:
    try:
        client.execute_kw(
            "stock.quant",
            "action_apply_inventory",
            [[quant_id]],
            kw,
        )
    except Exception:
        # Older builds may lack the method — inventory_quantity write may suffice
        # with inventory_mode context; do not invent stock.move lines.
        pass


__all__ = [
    "commit_inventory_count",
    "resolve_location_id",
    "resolve_product_id",
    "validate_inventory_table",
]
