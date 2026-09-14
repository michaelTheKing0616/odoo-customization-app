"""Seed a linked walkthrough spine so Open-app is not an empty model picker.

Domain-agnostic: topo-create custom x_* records (catalogs → headers → lines).
Required values come from the spec **and** live ``ir.model.fields`` (leftover
required columns from earlier applies). Stock M2Os use the first existing row.
Writes live Odoo data — callers must confirm.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol

from app.ai_odoo_app_bar import (
    _BOOKING_TOKENS,
    _JOB_HEADER_LEAVES,
    _SITE_TOKENS,
    _field_names,
    _find_role_model,
    _models_index,
    short_model_label,
)
from app.ai_selection import parse_selection_literal

WALKTHROUGH_PREFIX = "Walkthrough"
_MAX_RECORDS = 16
_SKIP_TTYPES = frozenset({"one2many", "many2many", "binary", "html", "reference"})
_SKIP_FIELD_NAMES = frozenset(
    {
        "id",
        "display_name",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "__last_update",
    }
)
_STOCK_RELATIONS = frozenset(
    {
        "res.partner",
        "res.users",
        "res.company",
        "res.currency",
        "hr.employee",
        "product.product",
        "product.template",
        "account.move",
        "sale.order",
        "purchase.order",
        "uom.uom",
    }
)


class _SeedClient(Protocol):
    def model_exists(self, model: str) -> bool: ...

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any: ...


def walkthrough_name(model_id: str) -> str:
    return f"{WALKTHROUGH_PREFIX} {short_model_label(model_id, plural=False)}"


def _x_m2o_relations(model: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for field in model.get("fields") or []:
        if not isinstance(field, dict) or field.get("ttype") != "many2one":
            continue
        rel = str(field.get("relation") or "")
        if rel.startswith("x_") and rel not in out:
            out.append(rel)
    return out


def plan_walkthrough_models(spec: dict[str, Any]) -> list[str]:
    """Catalogs and headers first, then line children whose parents are in the plan."""
    by_id = _models_index(spec)
    remaining = {
        mid
        for mid in by_id
        if mid.startswith("x_") and (by_id[mid].get("mode") or "new") == "new"
    }
    ordered: list[str] = []
    guard = 0
    while remaining and guard < 40:
        guard += 1
        ready = [
            mid
            for mid in remaining
            if not [d for d in _x_m2o_relations(by_id[mid]) if d in remaining]
        ]
        if not ready:
            ready = sorted(remaining)
        ready.sort(key=lambda m: (m.endswith("_line"), m))
        pick = ready[0]
        ordered.append(pick)
        remaining.discard(pick)
        if len(ordered) >= _MAX_RECORDS:
            break
    preferred: list[str] = []
    for tokens in (
        _SITE_TOKENS,
        ("artist", "guest", "patient", "member", "tenant", "client"),
        ("equipment", "asset", "instrument", "vehicle", "gear"),
        ("rate_card", "fee", "tariff"),
        tuple(_JOB_HEADER_LEAVES),
        _BOOKING_TOKENS,
        ("deliverable", "output", "recording", "track"),
    ):
        hit = _find_role_model(spec, tokens, skip=("line",))
        if hit and hit in ordered and hit not in preferred:
            preferred.append(hit)
    rest = [m for m in ordered if m not in preferred]
    non_line = [m for m in rest if not m.endswith("_line")]
    lines = [m for m in rest if m.endswith("_line")]
    return (preferred + non_line + lines)[:_MAX_RECORDS]


def _selection_default(field: dict[str, Any]) -> str | None:
    default = field.get("default")
    if isinstance(default, str) and default and default not in {"today", "now"}:
        return default
    pairs = parse_selection_literal(field.get("selection")) or []
    return str(pairs[0][0]) if pairs else None


def _skip_live_field(name: str) -> bool:
    if name in _SKIP_FIELD_NAMES or not name.startswith("x_"):
        return True
    return name.startswith(("message_", "activity_"))


def _live_required_fields(client: _SeedClient, mid: str) -> list[dict[str, Any]]:
    try:
        rows = client.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "=", mid), ("required", "=", True)]],
            {
                "fields": [
                    "name",
                    "ttype",
                    "relation",
                    "selection",
                    "readonly",
                    "related",
                    "compute",
                ]
            },
        )
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        if _skip_live_field(name):
            continue
        if row.get("readonly") or row.get("related") or row.get("compute"):
            continue
        out.append(row)
    return out


def _merged_fields(
    spec_model: dict[str, Any], live_required: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for field in spec_model.get("fields") or []:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "")
        if name:
            by_name[name] = dict(field)
    for row in live_required:
        name = str(row.get("name") or "")
        if not name:
            continue
        existing = by_name.get(name, {})
        by_name[name] = {
            **existing,
            "name": name,
            "ttype": row.get("ttype") or existing.get("ttype"),
            "relation": row.get("relation") or existing.get("relation") or "",
            "selection": existing.get("selection") or row.get("selection"),
            "required": True,
            "default": existing.get("default"),
        }
    return list(by_name.values())


def _scalar_default(fname: str, ttype: str, mid: str) -> Any:
    if ttype == "date":
        return date.today().isoformat()
    if ttype == "datetime":
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if ttype in {"float", "monetary"}:
        return 1.0
    if ttype == "integer":
        return 1
    if ttype == "boolean":
        return True
    if fname.endswith("_code") or fname in {"x_code"}:
        return "WT01"
    return walkthrough_name(mid)


def _vals_for_model(
    model: dict[str, Any],
    *,
    created: dict[str, int],
    stock_ids: dict[str, int],
    fields: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    mid = str(model.get("model") or "")
    rows = fields if fields is not None else list(model.get("fields") or [])
    vals: dict[str, Any] = {}
    names = {str(f.get("name") or "") for f in rows if isinstance(f, dict)}
    if "x_name" in names:
        vals["x_name"] = walkthrough_name(mid)
    for field in rows:
        if not isinstance(field, dict):
            continue
        fname = str(field.get("name") or "")
        if not fname or fname in vals or _skip_live_field(fname):
            continue
        if field.get("compute") or field.get("related"):
            continue
        ttype = str(field.get("ttype") or "")
        if ttype in _SKIP_TTYPES:
            continue
        required = bool(field.get("required"))
        rel = str(field.get("relation") or "")
        if ttype == "many2one":
            if rel.startswith("x_") and rel in created:
                vals[fname] = created[rel]
            elif rel in _STOCK_RELATIONS and rel in stock_ids:
                vals[fname] = stock_ids[rel]
            continue
        if ttype == "selection":
            key = _selection_default(field)
            if key:
                vals[fname] = key
            elif required:
                vals[fname] = "draft"
            continue
        if not required:
            continue
        vals[fname] = _scalar_default(fname, ttype, mid)
    if "x_currency_id" in names and "x_currency_id" not in vals:
        cid = stock_ids.get("res.currency")
        if cid:
            vals["x_currency_id"] = cid
    return vals


def _missing_required_x_parents(
    fields: list[dict[str, Any]], created: dict[str, int]
) -> list[str]:
    missing: list[str] = []
    for field in fields:
        if not isinstance(field, dict) or not field.get("required"):
            continue
        if field.get("ttype") != "many2one":
            continue
        rel = str(field.get("relation") or "")
        if rel.startswith("x_") and rel not in created:
            missing.append(rel)
    return missing


def seed_walkthrough(client: _SeedClient, spec: dict[str, Any]) -> dict[str, Any]:
    """Create or reuse Walkthrough records. Returns created ids + warnings."""
    created: dict[str, int] = {}
    warnings: list[str] = []
    stock_ids: dict[str, int] = {}
    for rel in _STOCK_RELATIONS:
        try:
            if not client.model_exists(rel):
                continue
            found = client.execute_kw(rel, "search", [[]], {"limit": 1})
            if found:
                stock_ids[rel] = int(found[0])
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{rel}: {exc}")
    by_id = _models_index(spec)
    for mid in plan_walkthrough_models(spec):
        model = by_id.get(mid)
        if not model:
            continue
        try:
            if not client.model_exists(mid):
                warnings.append(f"skip {mid}: model not on this connection")
                continue
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"skip {mid}: {exc}")
            continue
        name = walkthrough_name(mid)
        try:
            existing = client.execute_kw(
                mid,
                "search",
                [[("x_name", "=", name)]],
                {"limit": 1},
            )
            if existing:
                created[mid] = int(existing[0])
                continue
        except Exception:
            existing = []
        live = _live_required_fields(client, mid)
        fields = _merged_fields(model, live)
        missing = _missing_required_x_parents(fields, created)
        if missing:
            warnings.append(
                f"skip {mid}: parent {', '.join(missing)} was not created"
            )
            continue
        vals = _vals_for_model(
            model, created=created, stock_ids=stock_ids, fields=fields
        )
        if "x_name" not in vals and "x_name" in _field_names(model):
            vals["x_name"] = name
        try:
            rid = int(client.execute_kw(mid, "create", [vals]))
            created[mid] = rid
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{mid} create failed: {exc}")
    job_or_booking = _JOB_HEADER_LEAVES | set(_BOOKING_TOKENS)
    open_model = next(
        (
            m
            for m in plan_walkthrough_models(spec)
            if m in created
            and not m.endswith("_line")
            and any(tok in m for tok in job_or_booking)
        ),
        None,
    )
    if open_model is None:
        open_model = next((m for m in created if not m.endswith("_line")), None)
    failed = sum(1 for w in warnings if "create failed" in w or w.startswith("skip "))
    extra = f" {failed} could not be created (see warnings)." if failed else ""
    return {
        "ok": True,
        "created": created,
        "open_model": open_model,
        "open_record_id": created.get(open_model) if open_model else None,
        "warnings": warnings,
        "message": (
            f"Walkthrough: {len(created)} linked record(s).{extra} "
            "Open the app — Operations shows the job/booking with lines filled in."
        ),
    }
