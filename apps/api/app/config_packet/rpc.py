"""RPC helpers shared by Config Packet capture / apply (no LLM)."""

from __future__ import annotations

from typing import Any


def search_read(
    client: Any,
    model: str,
    domain: list[Any],
    fields: list[str],
    *,
    limit: int = 80,
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    kw: dict[str, Any] = {"fields": fields, "limit": limit}
    if context:
        kw["context"] = context
    try:
        rows = client.execute_kw(model, "search_read", [domain], kw)
    except Exception:  # noqa: BLE001
        return []
    return [r for r in (rows or []) if isinstance(r, dict)]


def search_ids(client: Any, model: str, domain: list[Any], *, limit: int = 8) -> list[int]:
    try:
        ids = client.execute_kw(model, "search", [domain], {"limit": limit})
    except Exception:  # noqa: BLE001
        return []
    return [int(i) for i in (ids or [])]


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


def field_exists(client: Any, model: str, name: str) -> bool:
    fn = getattr(client, "field_exists", None)
    if callable(fn):
        try:
            return bool(fn(model, name))
        except Exception:  # noqa: BLE001
            return False
    try:
        meta = client.execute_kw(model, "fields_get", [[name]], {"attributes": ["string"]})
        return bool(isinstance(meta, dict) and name in meta)
    except Exception:  # noqa: BLE001
        return False


def xml_id(client: Any, xmlid: str) -> int | None:
    if "." not in (xmlid or ""):
        return None
    module, name = xmlid.split(".", 1)
    rows = search_read(
        client,
        "ir.model.data",
        [("module", "=", module), ("name", "=", name)],
        ["res_id"],
        limit=1,
    )
    if not rows:
        return None
    rid = rows[0].get("res_id")
    return int(rid) if rid else None


def xmlids_for_records(client: Any, model: str, ids: list[int]) -> dict[int, str]:
    if not ids or not exists(client, "ir.model.data"):
        return {}
    rows = search_read(
        client,
        "ir.model.data",
        [("model", "=", model), ("res_id", "in", ids)],
        ["module", "name", "res_id"],
        limit=max(len(ids) * 2, 20),
    )
    out: dict[int, str] = {}
    for row in rows:
        rid = int(row.get("res_id") or 0)
        module = str(row.get("module") or "")
        name = str(row.get("name") or "")
        if rid and module and name:
            out[rid] = f"{module}.{name}"
    return out


def user_groups_field(client: Any) -> str:
    """Odoo 19 uses ``group_ids``; 17/18 keep ``groups_id``."""
    if field_exists(client, "res.users", "group_ids"):
        return "group_ids"
    if field_exists(client, "res.users", "groups_id"):
        return "groups_id"
    return "groups_id"


def m2o_name(value: Any) -> str | None:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[1]) if value[1] else None
    if isinstance(value, str) and value:
        return value
    return None


def m2o_id(value: Any) -> int | None:
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, (list, tuple)) and value:
        try:
            return int(value[0])
        except (TypeError, ValueError):
            return None
    return None


def action_id_for_xmlids(client: Any, xmlids: tuple[str, ...] | list[str]) -> tuple[int | None, str | None]:
    for xmlid in xmlids:
        rid = xml_id(client, xmlid)
        if rid:
            return rid, xmlid
    return None, None


def action_id_for_model(client: Any, model: str) -> int | None:
    """Standalone act_window for a model — skip related smart-buttons with active_id."""
    if not model or not exists(client, "ir.actions.act_window"):
        return None
    rows = search_read(
        client,
        "ir.actions.act_window",
        [("res_model", "=", model)],
        ["id", "name", "domain", "context", "view_mode"],
        limit=12,
    )
    standalone: list[dict[str, Any]] = []
    for row in rows:
        blob = f"{row.get('domain') or ''} {row.get('context') or ''}"
        if "active_id" in blob:
            continue
        standalone.append(row)
    pool = standalone or []
    if not pool:
        return None
    return int(pool[0]["id"]) if pool[0].get("id") else None
