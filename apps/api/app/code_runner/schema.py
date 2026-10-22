"""Live, version-exact schema for autocomplete, hover docs and lint (public ORM reads only)."""

from __future__ import annotations

import re
import threading
import time
from typing import Any

FIELD_ATTRS = ["string", "type", "relation", "selection", "help", "required", "readonly", "store"]
from app.schema_freshness import SCHEMA_TTL_S as _TTL  # one staleness rule
_lock = threading.Lock()
_cache: dict[tuple[str, str], tuple[float, Any]] = {}

# Public ORM methods callable over RPC, by first and last major version they exist in.
ORM_METHODS: dict[str, tuple[int, int, str]] = {
    "search": (17, 99, "search(domain, offset=0, limit=None, order=None) → ids"),
    "search_read": (17, 99, "search_read(domain, fields, offset, limit, order) → list of dicts"),
    "search_count": (17, 99, "search_count(domain) → int"),
    "read": (17, 99, "read(ids, fields) → list of dicts"),
    "create": (17, 99, "create(vals_list) → ids (one dict or a list of dicts)"),
    "write": (17, 99, "write(ids, vals) → True"),
    "unlink": (17, 99, "unlink(ids) → True  (deletes: blocked on dry run)"),
    "copy": (17, 99, "copy(id, default=None) → new id"),
    "fields_get": (17, 99, "fields_get(allfields=None, attributes=None) → field metadata"),
    "default_get": (17, 99, "default_get(fields) → default values"),
    "name_search": (17, 99, "name_search(name, domain, operator='ilike', limit=100) → [(id, label)]"),
    "read_group": (17, 99, "read_group(domain, fields, groupby) → groups (prefer formatted_read_group on 19+)"),
    "formatted_read_group": (19, 99, "formatted_read_group(domain, groupby, aggregates) → groups"),
    "web_search_read": (17, 99, "web_search_read(domain, specification, offset, limit) → {length, records}"),
    "web_read": (17, 99, "web_read(ids, specification) → list of dicts"),
    "action_archive": (17, 99, "action_archive(ids) → archives the records"),
    "action_unarchive": (17, 99, "action_unarchive(ids) → restores archived records"),
    "check_access_rights": (17, 17, "check_access_rights(operation) → bool (renamed check_access on 18+)"),
    "check_access": (18, 99, "check_access(operation) → raises if not allowed"),
    "get_views": (17, 99, "get_views(views, options) → view definitions"),
}
# Calls that no longer exist (or are on their way out) per version: (from_major, message, replacement).
DEPRECATED: dict[str, tuple[int, str, str]] = {
    "name_get": (17, "name_get was removed in Odoo 17", "read(ids, ['display_name'])"),
    "fields_view_get": (16, "fields_view_get was removed in Odoo 16", "get_views"),
    "check_access_rights": (18, "check_access_rights is replaced in Odoo 18", "check_access"),
    "read_group": (19, "read_group is deprecated in Odoo 19", "formatted_read_group"),
}


def major_of(version: str | None) -> int:
    m = re.search(r"(\d+)", str(version or ""))
    return int(m.group(1)) if m else 0


def methods_for(major: int) -> dict[str, str]:
    return {k: doc for k, (lo, hi, doc) in ORM_METHODS.items() if lo <= (major or 17) <= hi}


def _cached(key: tuple[str, str], fn: Any) -> Any:
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _TTL:
            return hit[1]
    val = fn()
    with _lock:
        _cache[key] = (now, val)
    return val


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def models(client: Any, cache_key: str) -> list[dict[str, str]]:
    def load() -> list[dict[str, str]]:
        rows = client.execute_kw("ir.model", "search_read", [[("transient", "=", False)]],
                                 {"fields": ["model", "name"], "order": "model"})
        return [{"model": r["model"], "name": r["name"]} for r in rows]
    return _cached((cache_key, "models"), load)


def fields(client: Any, cache_key: str, model: str) -> dict[str, dict[str, Any]]:
    def load() -> dict[str, dict[str, Any]]:
        return client.execute_kw(model, "fields_get", [], {"attributes": FIELD_ATTRS})
    return _cached((cache_key, f"fields:{model}"), load)
