"""Live / catalog / fake Odoo schema facade for GenerateIR admit (handoff PR-A).

Wraps existing ``packages/odoo-client`` + connection catalog — no mcp-odoo vendor.
``schema_verified_reuse`` (PR-B) will consult this; PR-A ships the contract only.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# Catalog older than this at confirm-time → deny schema_verified path (stale).
SCHEMA_CATALOG_TTL_S = 15 * 60


@runtime_checkable
class SchemaClient(Protocol):
    def model_exists(self, model: str) -> bool: ...

    def fields_get(self, model: str) -> dict[str, dict[str, Any]]: ...

    def relation_ok(self, model: str, field: str, relation: str) -> bool: ...

    def field_is_writable(self, model: str, field: str) -> bool: ...

    def view_has_field(self, model: str, field: str) -> bool:
        """Stub — not load-bearing for admit; Install-grammar L4 uses Live/Fake."""
        ...


@dataclass
class DenySchemaClient:
    """Empty client — every schema_verified check fails closed."""

    reason: str = "deny"

    def model_exists(self, model: str) -> bool:
        return False

    def fields_get(self, model: str) -> dict[str, dict[str, Any]]:
        return {}

    def relation_ok(self, model: str, field: str, relation: str) -> bool:
        return False

    def field_is_writable(self, model: str, field: str) -> bool:
        return False

    def view_has_field(self, model: str, field: str) -> bool:
        return False


@dataclass
class FakeSchemaClient:
    """Deterministic unit-test schema."""

    models: set[str] = field(default_factory=set)
    # model -> field -> meta (ttype, relation, readonly, compute, related)
    fields: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    # model -> set of field names present on form/list arch (Wave 6)
    view_fields: dict[str, set[str]] = field(default_factory=dict)

    def model_exists(self, model: str) -> bool:
        return model in self.models or model in self.fields

    def fields_get(self, model: str) -> dict[str, dict[str, Any]]:
        return dict(self.fields.get(model) or {})

    def relation_ok(self, model: str, field: str, relation: str) -> bool:
        meta = (self.fields.get(model) or {}).get(field) or {}
        if not meta:
            return False
        ttype = str(meta.get("type") or meta.get("ttype") or "")
        if ttype not in {"many2one", "one2many", "many2many"}:
            return False
        return str(meta.get("relation") or "") == relation

    def field_is_writable(self, model: str, field: str) -> bool:
        meta = (self.fields.get(model) or {}).get(field) or {}
        if not meta:
            return False
        if meta.get("readonly") is True:
            return False
        if meta.get("compute") and not meta.get("inverse"):
            return False
        if meta.get("related") and meta.get("readonly") is not False:
            # related defaults readonly in Odoo unless explicitly writable
            if meta.get("readonly") is True or meta.get("readonly") is None:
                return False
        return True

    def view_has_field(self, model: str, field: str) -> bool:
        """True when operator-supplied arch map lists the field (fail closed if absent)."""
        listed = self.view_fields.get(model)
        if listed is None:
            return False
        return field in listed


@dataclass
class CatalogSchemaClient:
    """Point-in-time model list from Diagnosis / draft ``_connection_catalog``."""

    models: set[str]
    loaded_at: float
    # Optional field map when tests or live enrichment stamped it
    fields: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def fields_get(self, model: str) -> dict[str, dict[str, Any]]:
        return dict(self.fields.get(model) or {})

    def relation_ok(self, model: str, field: str, relation: str) -> bool:
        if not self.model_exists(model) or not self.model_exists(relation):
            return False
        meta = (self.fields.get(model) or {}).get(field)
        if meta is None:
            # Catalog-only: relation target exists; field detail unknown → deny
            # (must not invent writable M2O from model list alone).
            return False
        ttype = str(meta.get("type") or meta.get("ttype") or "")
        if ttype not in {"many2one", "one2many", "many2many"}:
            return False
        return str(meta.get("relation") or "") == relation

    def field_is_writable(self, model: str, field: str) -> bool:
        meta = (self.fields.get(model) or {}).get(field)
        if meta is None:
            return False
        if meta.get("readonly") is True:
            return False
        if meta.get("compute") and not meta.get("inverse"):
            return False
        return True

    def view_has_field(self, model: str, field: str) -> bool:
        return False


class LiveSchemaClient:
    """Delegates to existing ``OdooClient`` (public ORM/RPC)."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._fg_cache: dict[str, dict[str, dict[str, Any]]] = {}

    def model_exists(self, model: str) -> bool:
        try:
            return bool(self._client.model_exists(model))
        except Exception:  # noqa: BLE001
            return False

    def fields_get(self, model: str) -> dict[str, dict[str, Any]]:
        if model in self._fg_cache:
            return self._fg_cache[model]
        out: dict[str, dict[str, Any]] = {}
        try:
            if hasattr(self._client, "list_fields"):
                for row in self._client.list_fields(model) or []:
                    name = str(getattr(row, "name", None) or "")
                    if not name:
                        continue
                    out[name] = {
                        "type": str(getattr(row, "ttype", "") or ""),
                        "ttype": str(getattr(row, "ttype", "") or ""),
                        "string": str(getattr(row, "field_description", "") or ""),
                        "relation": getattr(row, "relation", None),
                        "readonly": bool(getattr(row, "readonly", False)),
                        "related": getattr(row, "related", None),
                        "required": bool(getattr(row, "required", False)),
                    }
            elif hasattr(self._client, "execute_kw"):
                raw = self._client.execute_kw(
                    model, "fields_get", [], {"attributes": ["type", "relation", "readonly", "string"]}
                )
                if isinstance(raw, dict):
                    for name, meta in raw.items():
                        if isinstance(meta, dict):
                            out[str(name)] = dict(meta)
        except Exception:  # noqa: BLE001
            out = {}
        self._fg_cache[model] = out
        return out

    def relation_ok(self, model: str, field: str, relation: str) -> bool:
        if not self.model_exists(model) or not self.model_exists(relation):
            return False
        meta = self.fields_get(model).get(field) or {}
        ttype = str(meta.get("type") or meta.get("ttype") or "")
        if ttype not in {"many2one", "one2many", "many2many"}:
            return False
        return str(meta.get("relation") or "") == relation

    def field_is_writable(self, model: str, field: str) -> bool:
        meta = self.fields_get(model).get(field) or {}
        if not meta:
            return False
        if meta.get("readonly") is True:
            return False
        # ir.model.fields list path may omit compute; treat related+readonly as non-writable
        if meta.get("related") and meta.get("readonly") is not False:
            return False
        return True

    def view_has_field(self, model: str, field: str) -> bool:
        """Parse stock form arch via get_views / fields_view_get (public RPC)."""
        try:
            arch = ""
            if hasattr(self._client, "execute_kw"):
                try:
                    raw = self._client.execute_kw(
                        model,
                        "get_views",
                        [],
                        {"views": [(False, "form")], "options": {}},
                    )
                    if isinstance(raw, dict):
                        views = raw.get("views") if isinstance(raw.get("views"), dict) else {}
                        form = views.get("form") if isinstance(views, dict) else None
                        if isinstance(form, dict):
                            arch = str(form.get("arch") or "")
                except Exception:  # noqa: BLE001
                    arch = ""
                if not arch:
                    try:
                        fv = self._client.execute_kw(
                            model, "fields_view_get", [], {"view_type": "form"}
                        )
                        if isinstance(fv, dict):
                            arch = str(fv.get("arch") or "")
                    except Exception:  # noqa: BLE001
                        arch = ""
            if not arch:
                return False
            import re

            return bool(
                re.search(
                    rf'(?i)<field[^>]*\bname=(["\']){re.escape(field)}\1',
                    arch,
                )
            )
        except Exception:  # noqa: BLE001
            return False


def _catalog_models(draft: dict[str, Any]) -> tuple[set[str], float | None]:
    cat = draft.get("_connection_catalog")
    if not isinstance(cat, dict):
        return set(), None
    models: set[str] = set()
    for m in cat.get("available_models") or []:
        if m:
            models.add(str(m))
    for row in cat.get("stock") or []:
        if isinstance(row, dict) and row.get("model"):
            models.add(str(row["model"]))
    loaded = cat.get("loaded_at")
    try:
        loaded_f = float(loaded) if loaded is not None else None
    except (TypeError, ValueError):
        loaded_f = None
    return models, loaded_f


def schema_client_for_draft(
    draft: dict[str, Any] | None,
    client: Any | None = None,
    *,
    now: float | None = None,
    ttl_s: float = SCHEMA_CATALOG_TTL_S,
) -> SchemaClient:
    """Prefer live RPC, else fresh catalog snapshot, else deny.

    Stale catalog (older than ``ttl_s``) → deny — never ``schema_verified_reuse``
    on a Diagnosis-time snapshot that may no longer match Install.
    """
    if client is not None:
        return LiveSchemaClient(client)
    if not isinstance(draft, dict):
        return DenySchemaClient(reason="no_draft")
    # Explicit fake for tests
    injected = draft.get("_schema_client")
    if isinstance(injected, SchemaClient):
        return injected
    models, loaded_at = _catalog_models(draft)
    if not models:
        return DenySchemaClient(reason="no_catalog")
    clock = time.time() if now is None else now
    if loaded_at is None or (clock - loaded_at) > ttl_s:
        return DenySchemaClient(reason="stale_or_missing_catalog_ts")
    field_map = draft.get("_schema_fields")
    fields = field_map if isinstance(field_map, dict) else {}
    return CatalogSchemaClient(models=models, loaded_at=loaded_at, fields=fields)


__all__ = [
    "SCHEMA_CATALOG_TTL_S",
    "CatalogSchemaClient",
    "DenySchemaClient",
    "FakeSchemaClient",
    "LiveSchemaClient",
    "SchemaClient",
    "schema_client_for_draft",
]
