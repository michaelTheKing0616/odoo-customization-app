"""Master data batch — partners & products via public Odoo ORM/RPC.

Lifecycle: intake → map → validate → dry_run → apply.
Dry-run never writes.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.batch_os.partner_match import resolve_partner_id
from app.batch_os.types import (
    HONESTY_PREVIEW_NE_POSTED,
    BatchJobState,
    MappedLine,
    RowError,
)

HONESTY_MASTER = (
    "Preview ≠ written. Dry-run only proposes create/update — "
    "Apply writes via public RPC."
)

PARTNER_TARGETS: tuple[str, ...] = (
    "name", "email", "vat", "ref", "phone", "mobile", "street", "city", "zip",
    "country_code", "is_company", "customer_rank", "supplier_rank",
)
PARTNER_ALIASES: dict[str, str] = {
    "name": "name", "partner": "name", "partner_name": "name", "company": "name",
    "email": "email", "e_mail": "email",
    "vat": "vat", "tax_id": "vat", "tin": "vat",
    "ref": "ref", "reference": "ref", "code": "ref",
    "phone": "phone", "mobile": "mobile",
    "street": "street", "address": "street",
    "city": "city", "zip": "zip", "zip_code": "zip", "postcode": "zip",
    "country": "country_code", "country_code": "country_code",
    "is_company": "is_company", "company_type": "is_company",
    "customer_rank": "customer_rank",
    "supplier_rank": "supplier_rank", "vendor_rank": "supplier_rank",
}

PRODUCT_TARGETS: tuple[str, ...] = (
    "name", "default_code", "barcode", "list_price", "standard_price",
    "type", "uom", "categ", "sale_ok", "purchase_ok",
)
PRODUCT_ALIASES: dict[str, str] = {
    "name": "name", "product": "name", "product_name": "name",
    "default_code": "default_code", "code": "default_code", "sku": "default_code",
    "internal_reference": "default_code",
    "barcode": "barcode", "ean": "barcode",
    "list_price": "list_price", "sales_price": "list_price", "price": "list_price",
    "standard_price": "standard_price", "cost": "standard_price",
    "type": "type", "product_type": "type",
    "uom": "uom", "uom_name": "uom",
    "categ": "categ", "category": "categ",
    "sale_ok": "sale_ok", "purchase_ok": "purchase_ok",
}


def _pick(row: dict[str, str], column_map: dict[str, str], target: str) -> str:
    for header, mapped in column_map.items():
        if mapped == target:
            return (row.get(header) or "").strip()
    return ""


def _truthy(raw: str) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "y", "company", "t"}


def _num(raw: str) -> float | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(str(raw).replace(",", "").strip())
    except ValueError:
        return None


def _suggest(headers: list[str], aliases: dict[str, str], targets: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    used: set[str] = set()
    for h in headers:
        low = h.strip().lower().replace(" ", "_")
        target = aliases.get(low)
        if target and target not in used:
            out[h] = target
            used.add(target)
        elif low in targets and low not in used:
            out[h] = low
            used.add(low)
    return out


def suggest_partner_column_map(headers: list[str]) -> dict[str, str]:
    return _suggest(headers, PARTNER_ALIASES, PARTNER_TARGETS)


def suggest_product_column_map(headers: list[str]) -> dict[str, str]:
    return _suggest(headers, PRODUCT_ALIASES, PRODUCT_TARGETS)


def _build_partner_records(
    rows: list[dict[str, str]], column_map: dict[str, str]
) -> tuple[list[dict[str, Any]], list[MappedLine], list[RowError]]:
    records: list[dict[str, Any]] = []
    lines: list[MappedLine] = []
    errors: list[RowError] = []
    if "name" not in set(column_map.values()):
        errors.append(RowError(row_index=0, field="name", code="blocking", message="Column map missing required target: name"))
        return records, lines, errors
    for idx, row in enumerate(rows, start=1):
        name = _pick(row, column_map, "name")
        if not name:
            if not any((v or "").strip() for v in row.values()):
                continue
            errors.append(RowError(row_index=idx, field="name", code="blocking", message="Name required"))
            continue
        email = _pick(row, column_map, "email")
        vat = _pick(row, column_map, "vat")
        ref = _pick(row, column_map, "ref")
        rec = {
            "row_index": idx,
            "name": name,
            "email": email,
            "vat": vat,
            "ref": ref,
            "phone": _pick(row, column_map, "phone"),
            "mobile": _pick(row, column_map, "mobile"),
            "street": _pick(row, column_map, "street"),
            "city": _pick(row, column_map, "city"),
            "zip": _pick(row, column_map, "zip"),
            "country_code": _pick(row, column_map, "country_code").upper(),
            "is_company": _truthy(_pick(row, column_map, "is_company") or "1"),
            "customer_rank": int(_num(_pick(row, column_map, "customer_rank") or "1") or 1),
            "supplier_rank": int(_num(_pick(row, column_map, "supplier_rank") or "0") or 0),
        }
        records.append(rec)
        lines.append(MappedLine(row_index=idx, label=name, partner_key=name, ref=ref or vat or email, move_group=email or vat or name))
    return records, lines, errors


def _build_product_records(
    rows: list[dict[str, str]], column_map: dict[str, str]
) -> tuple[list[dict[str, Any]], list[MappedLine], list[RowError]]:
    records: list[dict[str, Any]] = []
    lines: list[MappedLine] = []
    errors: list[RowError] = []
    if "name" not in set(column_map.values()):
        errors.append(RowError(row_index=0, field="name", code="blocking", message="Column map missing required target: name"))
        return records, lines, errors
    for idx, row in enumerate(rows, start=1):
        name = _pick(row, column_map, "name")
        if not name:
            if not any((v or "").strip() for v in row.values()):
                continue
            errors.append(RowError(row_index=idx, field="name", code="blocking", message="Name required"))
            continue
        ptype = (_pick(row, column_map, "type") or "consu").strip().lower()
        if ptype in {"stockable", "product", "storable"}:
            ptype = "product"
        elif ptype in {"service", "serv"}:
            ptype = "service"
        elif ptype not in {"consu", "service", "product"}:
            ptype = "consu"
        code = _pick(row, column_map, "default_code")
        barcode = _pick(row, column_map, "barcode")
        rec = {
            "row_index": idx,
            "name": name,
            "default_code": code,
            "barcode": barcode,
            "list_price": _num(_pick(row, column_map, "list_price")),
            "standard_price": _num(_pick(row, column_map, "standard_price")),
            "type": ptype,
            "uom": _pick(row, column_map, "uom"),
            "categ": _pick(row, column_map, "categ"),
            "sale_ok": _truthy(_pick(row, column_map, "sale_ok") or "1"),
            "purchase_ok": _truthy(_pick(row, column_map, "purchase_ok") or "1"),
        }
        records.append(rec)
        lines.append(MappedLine(row_index=idx, label=name, account_key=code or name, ref=barcode or code or name, move_group=code or name))
    return records, lines, errors


def _resolve_country_id(client: Any, code: str) -> int | None:
    code = (code or "").strip().upper()
    if not code or not client.model_exists("res.country"):
        return None
    rows = client.execute_kw(
        "res.country", "search_read", [[("code", "=", code)]], {"fields": ["id"], "limit": 1}
    )
    return int(rows[0]["id"]) if rows else None


def _match_product(client: Any, rec: dict[str, Any]) -> tuple[int | None, int | None]:
    if not client.model_exists("product.product"):
        return None, None
    code = (rec.get("default_code") or "").strip()
    barcode = (rec.get("barcode") or "").strip()
    name = (rec.get("name") or "").strip()
    for domain in (
        [("default_code", "=", code)] if code else None,
        [("barcode", "=", barcode)] if barcode else None,
        [("name", "=", name)] if name else None,
        [("name", "ilike", name)] if name else None,
    ):
        if not domain:
            continue
        rows = client.execute_kw(
            "product.product",
            "search_read",
            [domain],
            {"fields": ["id", "product_tmpl_id"], "limit": 2},
        )
        if not rows:
            continue
        if len(rows) == 1 or domain[0][1] == "=":
            tid = rows[0].get("product_tmpl_id")
            if isinstance(tid, (list, tuple)):
                tid = tid[0]
            return int(rows[0]["id"]), int(tid) if tid else None
    return None, None


def _resolve_uom_id(client: Any, key: str) -> int | None:
    key = (key or "").strip()
    if not key:
        return None
    for model in ("uom.uom", "product.uom"):
        if not client.model_exists(model):
            continue
        rows = client.execute_kw(
            model,
            "search_read",
            [["|", ("name", "=", key), ("name", "ilike", key)]],
            {"fields": ["id"], "limit": 1},
        )
        if rows:
            return int(rows[0]["id"])
    return None


def _resolve_categ_id(client: Any, key: str) -> int | None:
    key = (key or "").strip()
    if not key or not client.model_exists("product.category"):
        return None
    rows = client.execute_kw(
        "product.category",
        "search_read",
        [["|", ("name", "=", key), ("complete_name", "ilike", key)]],
        {"fields": ["id"], "limit": 1},
    )
    return int(rows[0]["id"]) if rows else None


class PartnersBatchRecipe:
    id = "master_data.partners_batch"
    risk = "L1"
    title = "Partner batch"
    blurb = "CSV/XLSX → create/update res.partner. Dedup by VAT/email/ref/name. Preview ≠ written."
    atlas_class = "master_data"

    def intake(
        self,
        *,
        connection_id: str,
        filename: str = "",
        headers: list[str] | None = None,
        rows: list[dict[str, str]] | None = None,
        extras: dict[str, Any] | None = None,
    ) -> BatchJobState:
        headers = list(headers or [])
        rows = list(rows or [])
        return BatchJobState(
            job_id=str(uuid.uuid4()),
            connection_id=connection_id,
            recipe_id=self.id,
            risk="L1",
            phase="intake",
            filename=filename or "partners.csv",
            headers=headers,
            raw_rows=rows,
            column_map=suggest_partner_column_map(headers),
            message=f"Partner batch loaded ({len(rows)} rows). Map → validate → dry-run → apply.",
            honesty=f"{HONESTY_MASTER} {HONESTY_PREVIEW_NE_POSTED}",
            extras={"kind": "partners", **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState:
        state.column_map = dict(column_map if column_map is not None else state.column_map)
        records, lines, errors = _build_partner_records(state.raw_rows, state.column_map)
        state.mapped_lines = lines
        state.errors = errors
        state.extras["records"] = records
        state.phase = "mapped"
        state.message = f"Mapped {len(records)} partner row(s)"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not state.extras.get("records"):
            state = self.map(state)
        if not client.model_exists("res.partner"):
            state.errors.append(RowError(row_index=0, code="blocking", message="res.partner missing — Contacts not available"))
            state.phase = "failed"
            return state
        would_create: list[dict[str, Any]] = []
        would_update: list[dict[str, Any]] = []
        for rec in state.extras.get("records") or []:
            pid = resolve_partner_id(
                client,
                vat=rec.get("vat") or "",
                email=rec.get("email") or "",
                ref=rec.get("ref") or "",
                name=rec.get("name") or "",
            )
            rec["country_id"] = _resolve_country_id(client, rec.get("country_code") or "")
            if pid:
                rec["action"] = "update"
                rec["partner_id"] = pid
                would_update.append(rec)
            else:
                rec["action"] = "create"
                rec["partner_id"] = None
                would_create.append(rec)
        state.extras["would_create"] = would_create
        state.extras["would_update"] = would_update
        if any(e.code == "blocking" for e in state.errors):
            state.phase = "failed"
            return state
        state.phase = "validated"
        state.message = f"Partners: {len(would_create)} create, {len(would_update)} update (dedup VAT/email/ref/name)"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        state.message = (
            f"Dry-run: would create {len(state.extras.get('would_create') or [])}, "
            f"update {len(state.extras.get('would_update') or [])} partner(s). {HONESTY_MASTER}"
        )
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        created: list[int] = []
        updated: list[int] = []
        for rec in state.extras.get("would_create") or []:
            vals: dict[str, Any] = {"name": rec["name"], "is_company": bool(rec.get("is_company", True))}
            for k in ("email", "vat", "ref", "phone", "mobile", "street", "city", "zip"):
                if rec.get(k):
                    vals[k] = rec[k]
            if rec.get("country_id"):
                vals["country_id"] = rec["country_id"]
            if rec.get("customer_rank") is not None:
                vals["customer_rank"] = rec["customer_rank"]
            if rec.get("supplier_rank") is not None:
                vals["supplier_rank"] = rec["supplier_rank"]
            try:
                pid = client.execute_kw("res.partner", "create", [vals])
                if isinstance(pid, list):
                    pid = pid[0]
                created.append(int(pid))
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=int(rec.get("row_index") or 0), code="warn", message=f"Create partner failed: {exc}"))
        for rec in state.extras.get("would_update") or []:
            pid = int(rec["partner_id"])
            vals = {k: rec[k] for k in ("email", "vat", "ref", "phone", "mobile", "street", "city", "zip", "name") if rec.get(k)}
            if rec.get("country_id"):
                vals["country_id"] = rec["country_id"]
            if not vals:
                continue
            try:
                client.execute_kw("res.partner", "write", [[pid], vals])
                updated.append(pid)
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=int(rec.get("row_index") or 0), code="warn", message=f"Update partner {pid} failed: {exc}"))
        state.created_move_ids = created + updated
        state.extras["created_ids"] = created
        state.extras["updated_ids"] = updated
        state.phase = "applied"
        state.dry_run = False
        state.message = f"Created {len(created)}, updated {len(updated)} partner(s)"
        state.honesty = HONESTY_MASTER
        return state


class ProductsBatchRecipe:
    id = "master_data.products_batch"
    risk = "L1"
    title = "Product batch"
    blurb = "CSV/XLSX → create/update product.template. Dedup by default_code/barcode/name. Preview ≠ written."
    atlas_class = "master_data"

    def intake(
        self,
        *,
        connection_id: str,
        filename: str = "",
        headers: list[str] | None = None,
        rows: list[dict[str, str]] | None = None,
        extras: dict[str, Any] | None = None,
    ) -> BatchJobState:
        headers = list(headers or [])
        rows = list(rows or [])
        return BatchJobState(
            job_id=str(uuid.uuid4()),
            connection_id=connection_id,
            recipe_id=self.id,
            risk="L1",
            phase="intake",
            filename=filename or "products.csv",
            headers=headers,
            raw_rows=rows,
            column_map=suggest_product_column_map(headers),
            message=f"Product batch loaded ({len(rows)} rows).",
            honesty=f"{HONESTY_MASTER} {HONESTY_PREVIEW_NE_POSTED}",
            extras={"kind": "products", **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState:
        state.column_map = dict(column_map if column_map is not None else state.column_map)
        records, lines, errors = _build_product_records(state.raw_rows, state.column_map)
        state.mapped_lines = lines
        state.errors = errors
        state.extras["records"] = records
        state.phase = "mapped"
        state.message = f"Mapped {len(records)} product row(s)"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not state.extras.get("records"):
            state = self.map(state)
        if not client.model_exists("product.template"):
            state.errors.append(RowError(row_index=0, code="blocking", message="product.template missing — install Product"))
            state.phase = "failed"
            return state
        would_create: list[dict[str, Any]] = []
        would_update: list[dict[str, Any]] = []
        for rec in state.extras.get("records") or []:
            prod_id, tmpl_id = _match_product(client, rec)
            rec["uom_id"] = _resolve_uom_id(client, rec.get("uom") or "")
            rec["categ_id"] = _resolve_categ_id(client, rec.get("categ") or "")
            if tmpl_id or prod_id:
                rec["action"] = "update"
                rec["template_id"] = tmpl_id
                rec["product_id"] = prod_id
                would_update.append(rec)
            else:
                rec["action"] = "create"
                would_create.append(rec)
        state.extras["would_create"] = would_create
        state.extras["would_update"] = would_update
        if any(e.code == "blocking" for e in state.errors):
            state.phase = "failed"
            return state
        state.phase = "validated"
        state.message = f"Products: {len(would_create)} create, {len(would_update)} update"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        state.message = (
            f"Dry-run: would create {len(state.extras.get('would_create') or [])}, "
            f"update {len(state.extras.get('would_update') or [])} product(s). {HONESTY_MASTER}"
        )
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        created: list[int] = []
        updated: list[int] = []
        for rec in state.extras.get("would_create") or []:
            vals: dict[str, Any] = {
                "name": rec["name"],
                "type": rec.get("type") or "consu",
                "sale_ok": bool(rec.get("sale_ok", True)),
                "purchase_ok": bool(rec.get("purchase_ok", True)),
            }
            if rec.get("default_code"):
                vals["default_code"] = rec["default_code"]
            if rec.get("barcode"):
                vals["barcode"] = rec["barcode"]
            if rec.get("list_price") is not None:
                vals["list_price"] = rec["list_price"]
            if rec.get("standard_price") is not None:
                vals["standard_price"] = rec["standard_price"]
            if rec.get("uom_id"):
                vals["uom_id"] = rec["uom_id"]
                vals["uom_po_id"] = rec["uom_id"]
            if rec.get("categ_id"):
                vals["categ_id"] = rec["categ_id"]
            try:
                tid = client.execute_kw("product.template", "create", [vals])
                if isinstance(tid, list):
                    tid = tid[0]
                created.append(int(tid))
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=int(rec.get("row_index") or 0), code="warn", message=f"Create product failed: {exc}"))
        for rec in state.extras.get("would_update") or []:
            tid = rec.get("template_id")
            if not tid:
                continue
            vals = {}
            if rec.get("name"):
                vals["name"] = rec["name"]
            if rec.get("list_price") is not None:
                vals["list_price"] = rec["list_price"]
            if rec.get("standard_price") is not None:
                vals["standard_price"] = rec["standard_price"]
            if rec.get("default_code"):
                vals["default_code"] = rec["default_code"]
            if rec.get("barcode"):
                vals["barcode"] = rec["barcode"]
            if not vals:
                continue
            try:
                client.execute_kw("product.template", "write", [[int(tid)], vals])
                updated.append(int(tid))
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=int(rec.get("row_index") or 0), code="warn", message=f"Update product {tid} failed: {exc}"))
        state.created_move_ids = created + updated
        state.extras["created_ids"] = created
        state.extras["updated_ids"] = updated
        state.phase = "applied"
        state.dry_run = False
        state.message = f"Created {len(created)}, updated {len(updated)} product template(s)"
        state.honesty = HONESTY_MASTER
        return state
