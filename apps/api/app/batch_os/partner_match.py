"""Stronger public-RPC partner matching for invoice/payment/master batches.

Resolve order (first unique hit wins):
  1. numeric id
  2. VAT / company_registry
  3. email
  4. ref
  5. name / display_name (exact, then unique ilike)
"""

from __future__ import annotations

from typing import Any


def _search_one(client: Any, domain: list[Any]) -> int | None:
    rows = client.execute_kw(
        "res.partner",
        "search_read",
        [domain],
        {"fields": ["id"], "limit": 2},
    )
    if len(rows) == 1:
        return int(rows[0]["id"])
    if len(rows) > 1 and domain and domain[0][1] == "=":
        return int(rows[0]["id"])
    return None


def resolve_partner_id(
    client: Any,
    *,
    key: str = "",
    vat: str = "",
    email: str = "",
    ref: str = "",
    name: str = "",
) -> int | None:
    if not client.model_exists("res.partner"):
        return None

    key = (key or "").strip()
    vat = (vat or "").strip()
    email = (email or "").strip()
    ref = (ref or "").strip()
    name = (name or key or "").strip()

    if key.isdigit():
        return int(key)

    if vat:
        for domain in (
            [("vat", "=", vat)],
            [("company_registry", "=", vat)],
            [("vat", "ilike", vat)],
        ):
            hit = _search_one(client, domain)
            if hit is not None:
                return hit

    if email:
        for domain in (
            [("email", "=", email)],
            [("email", "ilike", email)],
        ):
            hit = _search_one(client, domain)
            if hit is not None:
                return hit

    if ref:
        hit = _search_one(client, [("ref", "=", ref)])
        if hit is not None:
            return hit

    if name:
        for domain in (
            [("name", "=", name)],
            [("display_name", "=", name)],
            [("name", "ilike", name)],
        ):
            hit = _search_one(client, domain)
            if hit is not None:
                return hit

    return None


def find_partner_duplicates(client: Any, *, limit: int = 50) -> list[dict[str, Any]]:
    if not client.model_exists("res.partner"):
        return []
    rows = client.execute_kw(
        "res.partner",
        "search_read",
        [[("active", "=", True)]],
        {"fields": ["id", "name", "vat", "email", "ref"], "limit": 2000},
    )
    by_vat: dict[str, list[dict[str, Any]]] = {}
    by_email: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        vat = (r.get("vat") or "").strip().upper()
        email = (r.get("email") or "").strip().lower()
        if vat:
            by_vat.setdefault(vat, []).append(r)
        if email:
            by_email.setdefault(email, []).append(r)
    clusters: list[dict[str, Any]] = []
    for key, group in by_vat.items():
        if len(group) > 1:
            clusters.append({"match": "vat", "key": key, "partners": group})
    for key, group in by_email.items():
        if len(group) > 1:
            clusters.append({"match": "email", "key": key, "partners": group})
    return clusters[:limit]
