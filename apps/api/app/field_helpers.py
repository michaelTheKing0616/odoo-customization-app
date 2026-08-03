"""Builder field helpers — monetary currency companion, related path discovery."""

from __future__ import annotations

from typing import Any

from odoo_client import OdooClient, CreateFieldRequest, FieldType
from odoo_client.client import OdooClientError

DEFAULT_CURRENCY_FIELD = "x_currency_id"


def ensure_currency_field_for_monetary(
    client: OdooClient,
    model: str,
    *,
    currency_field: str | None = None,
) -> tuple[str, bool]:
    """Ensure a many2one currency field exists; return (field_name, created)."""
    target = (currency_field or DEFAULT_CURRENCY_FIELD).strip()
    if client.field_exists(model, target):
        return target, False
    client.create_field(
        CreateFieldRequest(
            model=model,
            name=target,
            field_description="Currency",
            ttype=FieldType.MANY2ONE,
            relation="res.currency",
            required=False,
        )
    )
    return target, True


def list_related_paths(
    client: OdooClient,
    model: str,
    *,
    depth: int = 2,
) -> list[dict[str, Any]]:
    """Return selectable related paths (m2o chain, depth 2) for read-through fields."""
    if not client.model_exists(model):
        raise OdooClientError(f"Model {model!r} not found")
    if depth < 1 or depth > 2:
        raise ValueError("depth must be 1 or 2")

    fg = client.execute_kw(model, "fields_get", [], {"attributes": ["type", "relation", "string"]})
    out: list[dict[str, Any]] = []

    def _add(path: str, label: str, ttype: str, relation: str | None) -> None:
        out.append({"path": path, "label": label, "ttype": ttype, "relation": relation})

    for fname, meta in sorted(fg.items()):
        if not isinstance(meta, dict):
            continue
        if meta.get("type") != "many2one" or not meta.get("relation"):
            continue
        rel = str(meta["relation"])
        label = str(meta.get("string") or fname)
        _add(fname, label, "many2one", rel)
        if depth < 2:
            continue
        try:
            rel_fg = client.execute_kw(
                rel, "fields_get", [], {"attributes": ["type", "relation", "string"]}
            )
        except OdooClientError:
            continue
        for sub, smeta in sorted(rel_fg.items()):
            if not isinstance(smeta, dict):
                continue
            stype = smeta.get("type")
            if stype not in {"char", "many2one", "selection", "boolean", "integer", "float"}:
                continue
            sub_label = str(smeta.get("string") or sub)
            path = f"{fname}.{sub}"
            _add(
                path,
                f"{label} → {sub_label}",
                str(stype),
                str(smeta["relation"]) if smeta.get("relation") else None,
            )
    return out
