"""Shared RPC helpers for connector recipes."""

from __future__ import annotations

from typing import Any


def exists(client: Any, model: str) -> bool:
    fn = getattr(client, "model_exists", None)
    if callable(fn):
        try:
            return bool(fn(model))
        except Exception:  # noqa: BLE001
            return False
    try:
        client.execute_kw(model, "fields_get", [], {"attributes": ["string"]})
        return True
    except Exception:  # noqa: BLE001
        return False


def search(client: Any, model: str, domain: list[Any], *, limit: int = 1) -> list[int]:
    try:
        ids = client.execute_kw(model, "search", [domain], {"limit": limit})
    except Exception:  # noqa: BLE001
        return []
    return [int(i) for i in (ids or [])]


def search_read(
    client: Any,
    model: str,
    domain: list[Any],
    fields: list[str],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    try:
        rows = client.execute_kw(
            model, "search_read", [domain], {"fields": fields, "limit": limit}
        )
    except Exception:  # noqa: BLE001
        return []
    return [r for r in (rows or []) if isinstance(r, dict)]


def create(client: Any, model: str, vals: dict[str, Any]) -> int | None:
    try:
        rid = client.execute_kw(model, "create", [vals])
        return int(rid)
    except Exception:  # noqa: BLE001
        return None


def first_product_id(client: Any) -> int | None:
    ids = search(client, "product.product", [], limit=1)
    return ids[0] if ids else None


def first_partner_id(client: Any) -> int | None:
    ids = search(client, "res.partner", [("name", "ilike", "Autopilot")], limit=1)
    if ids:
        return ids[0]
    return create(client, "res.partner", {"name": "Autopilot Channel Partner"})


__all__ = [
    "create",
    "exists",
    "first_partner_id",
    "first_product_id",
    "search",
    "search_read",
]
