"""Order batch — CSV/XLSX → draft sale.order / purchase.order (public RPC).

Creates quotation / RFQ drafts only. Preview ≠ confirmed.
Never invent EE-only fields; never auto-confirm.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from typing import Any

from app.batch_os.partner_match import resolve_partner_id
from app.batch_os.types import (
    HONESTY_PREVIEW_NE_CONFIRMED,
    ORDER_COLUMN_TARGETS,
    ORDER_HEADER_ALIASES,
    BatchJobState,
    MappedLine,
    MovePreview,
    RowError,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SALE = {
    "sale",
    "sale_order",
    "sales",
    "quotation",
    "quote",
    "so",
    "customer",
    "out",
}
_PURCHASE = {
    "purchase",
    "purchase_order",
    "po",
    "rfq",
    "vendor",
    "supplier",
    "in",
}


def suggest_order_column_map(headers: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    used: set[str] = set()
    for h in headers:
        low = h.strip().lower().replace(" ", "_")
        target = ORDER_HEADER_ALIASES.get(low)
        if target and target not in used:
            out[h] = target
            used.add(target)
            continue
        if low in ORDER_COLUMN_TARGETS and low not in used:
            out[h] = low
            used.add(low)
    return out


def _num(val: Any) -> float:
    if val is None or val == "":
        return 0.0
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return 0.0


def _pick(row: dict[str, str], column_map: dict[str, str], target: str) -> str:
    for header, mapped in column_map.items():
        if mapped == target:
            return (row.get(header) or "").strip()
    return ""


def _normalize_order_type(raw: str) -> str:
    low = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if low in _PURCHASE or low.startswith("purchase") or low.startswith("po"):
        return "purchase"
    if low in {"sale", "sale_order", "purchase"}:
        return low if low != "sale_order" else "sale"
    if low in _SALE:
        return "sale"
    return "sale"


def _encode_ref(*, ref: str, order_type: str, product: str) -> str:
    parts: list[str] = []
    if ref:
        parts.append(ref)
    parts.append(f"otype:{order_type}")
    if product:
        parts.append(f"product:{product}")
    return "||".join(parts)


def _parse_ref(ref: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, part in enumerate((ref or "").split("||")):
        if part.startswith("otype:"):
            out["order_type"] = part[6:]
        elif part.startswith("product:"):
            out["product"] = part[8:]
        elif part and i == 0:
            out["ref"] = part
    return out


def build_order_lines(
    rows: list[dict[str, str]],
    column_map: dict[str, str],
) -> tuple[list[MappedLine], list[RowError]]:
    lines: list[MappedLine] = []
    errors: list[RowError] = []
    targets = set(column_map.values())
    if "partner" not in targets:
        errors.append(
            RowError(
                row_index=0,
                field="partner",
                code="blocking",
                message="Column map missing required target: partner",
            )
        )
        return lines, errors

    for idx, row in enumerate(rows, start=1):
        partner = _pick(row, column_map, "partner")
        qty = _num(_pick(row, column_map, "qty") or "1")
        price = _num(_pick(row, column_map, "price"))
        product = _pick(row, column_map, "product")
        label = _pick(row, column_map, "label") or product or "Order line"
        if not partner and qty == 0 and price == 0 and not product:
            continue
        if not partner:
            errors.append(
                RowError(
                    row_index=idx, field="partner", code="blocking", message="Partner required"
                )
            )
        if not product and not label:
            errors.append(
                RowError(
                    row_index=idx,
                    field="product",
                    code="blocking",
                    message="Need product or label",
                )
            )
        if qty <= 0:
            errors.append(
                RowError(row_index=idx, field="qty", code="blocking", message="Qty must be > 0")
            )
        date_s = _pick(row, column_map, "date")
        if date_s and not _DATE_RE.match(date_s[:10]):
            errors.append(
                RowError(
                    row_index=idx,
                    field="date",
                    code="warn",
                    message="Prefer ISO date YYYY-MM-DD",
                )
            )
        order_type = _normalize_order_type(_pick(row, column_map, "order_type"))
        group = (
            _pick(row, column_map, "order_group")
            or _pick(row, column_map, "ref")
            or f"{partner}-{date_s or 'nodate'}-{order_type}-{idx}"
        )
        lines.append(
            MappedLine(
                row_index=idx,
                journal_key=order_type,
                date=(date_s[:10] if date_s else ""),
                ref=_encode_ref(
                    ref=_pick(row, column_map, "ref"),
                    order_type=order_type,
                    product=product,
                ),
                label=label,
                account_key=product,
                debit=qty,
                credit=price,
                partner_key=partner,
                move_group=group,
            )
        )
    return lines, errors


def _resolve_product_id(client: Any, key: str) -> int | None:
    key = (key or "").strip()
    if not key or not client.model_exists("product.product"):
        return None
    if key.isdigit():
        return int(key)
    for domain in (
        [("default_code", "=", key)],
        [("name", "=", key)],
        [("default_code", "ilike", key)],
        [("name", "ilike", key)],
    ):
        rows = client.execute_kw(
            "product.product",
            "search_read",
            [domain],
            {"fields": ["id"], "limit": 2},
        )
        if len(rows) == 1:
            return int(rows[0]["id"])
        if len(rows) > 1 and domain[0][1] == "=":
            return int(rows[0]["id"])
    return None


def resolve_order_lines(
    client: Any, lines: list[MappedLine]
) -> tuple[list[MappedLine], list[RowError]]:
    errors: list[RowError] = []
    out: list[MappedLine] = []
    for line in lines:
        meta = _parse_ref(line.ref)
        order_type = meta.get("order_type") or "sale"
        model = "sale.order" if order_type == "sale" else "purchase.order"
        if not client.model_exists(model):
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="order_type",
                    code="blocking",
                    message=f"{model} not installed on this database",
                )
            )

        partner_id = resolve_partner_id(client, key=line.partner_key, name=line.partner_key)
        if partner_id is None:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="partner",
                    code="blocking",
                    message=f"Partner not found: {line.partner_key!r}",
                )
            )

        product_key = meta.get("product") or line.account_key or ""
        product_id = _resolve_product_id(client, product_key) if product_key else None
        if product_id is None:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="product",
                    code="blocking",
                    message=f"Product not resolved: {product_key!r}",
                )
            )

        date_s = line.date
        if not date_s:
            from datetime import date as _date

            date_s = _date.today().isoformat()

        out.append(
            MappedLine(
                row_index=line.row_index,
                journal_key=order_type,
                journal_id=1 if partner_id and product_id else None,
                date=date_s,
                ref=line.ref,
                label=line.label,
                account_key=line.account_key,
                account_id=None,
                debit=line.debit,
                credit=line.credit,
                partner_key=line.partner_key,
                partner_id=partner_id,
                analytic_key="",
                analytic_id=product_id,
                move_group=line.move_group,
            )
        )
    return out, errors


def group_orders(lines: list[MappedLine]) -> list[MovePreview]:
    groups: dict[str, list[MappedLine]] = defaultdict(list)
    for line in lines:
        groups[line.move_group or f"row-{line.row_index}"].append(line)
    moves: list[MovePreview] = []
    for key, group_lines in groups.items():
        errs: list[str] = []
        first = group_lines[0]
        meta = _parse_ref(first.ref)
        order_type = meta.get("order_type") or "sale"
        if not first.partner_id:
            errs.append("Missing partner")
        if not all(gl.analytic_id for gl in group_lines):
            errs.append("Missing product on one or more lines")
        total = sum(round(l.debit * l.credit, 2) for l in group_lines)
        balanced = bool(first.partner_id and not errs)
        moves.append(
            MovePreview(
                group_key=key,
                journal_id=first.journal_id,
                journal_name=order_type,
                date=first.date,
                ref=meta.get("ref") or first.move_group,
                line_count=len(group_lines),
                total_debit=round(total, 2),
                total_credit=0.0,
                balanced=balanced,
                line_indexes=[l.row_index for l in group_lines],
                errors=errs,
            )
        )
    return moves


def create_draft_orders(
    client: Any,
    lines: list[MappedLine],
    moves: list[MovePreview],
    *,
    dry_run: bool,
) -> tuple[list[MovePreview], list[int], list[RowError]]:
    errors: list[RowError] = []
    created: list[int] = []
    by_group: dict[str, list[MappedLine]] = defaultdict(list)
    for line in lines:
        by_group[line.move_group or f"row-{line.row_index}"].append(line)

    updated: list[MovePreview] = []
    for move in moves:
        if not move.balanced:
            errors.append(
                RowError(
                    row_index=move.line_indexes[0] if move.line_indexes else 0,
                    code="blocking",
                    message=f"Skip {move.group_key}: {'; '.join(move.errors) or 'invalid'}",
                )
            )
            updated.append(move)
            continue
        group_lines = by_group.get(move.group_key) or []
        if not group_lines:
            updated.append(move)
            continue
        first = group_lines[0]
        meta = _parse_ref(first.ref)
        order_type = meta.get("order_type") or move.journal_name or "sale"
        model = "sale.order" if order_type == "sale" else "purchase.order"
        line_model_qty_field = "product_uom_qty" if order_type == "sale" else "product_qty"

        line_cmds: list[tuple[int, int, dict[str, Any]]] = []
        for gl in group_lines:
            qty = gl.debit if gl.debit else 1.0
            price = gl.credit
            vals: dict[str, Any] = {
                "name": gl.label,
                line_model_qty_field: qty,
                "price_unit": price,
            }
            if gl.analytic_id:
                vals["product_id"] = gl.analytic_id
            line_cmds.append((0, 0, vals))

        order_vals: dict[str, Any] = {
            "partner_id": int(first.partner_id) if first.partner_id else False,
            "order_line": line_cmds,
        }
        if first.date:
            order_vals["date_order"] = first.date
        ref = move.ref or meta.get("ref") or ""
        if ref:
            if order_type == "sale":
                order_vals["client_order_ref"] = ref
            else:
                order_vals["partner_ref"] = ref

        if dry_run:
            updated.append(
                MovePreview(
                    group_key=move.group_key,
                    journal_id=move.journal_id,
                    journal_name=order_type,
                    date=move.date,
                    ref=move.ref,
                    line_count=move.line_count,
                    total_debit=move.total_debit,
                    total_credit=move.total_credit,
                    balanced=True,
                    line_indexes=list(move.line_indexes),
                    errors=list(move.errors)
                    + [f"dry-run: would create DRAFT {model} (not confirmed)"],
                )
            )
            continue

        try:
            order_id = client.execute_kw(model, "create", [order_vals])
            if isinstance(order_id, list):
                order_id = order_id[0]
            order_id = int(order_id)
            created.append(order_id)
            updated.append(
                MovePreview(
                    group_key=move.group_key,
                    journal_id=move.journal_id,
                    journal_name=order_type,
                    date=move.date,
                    ref=move.ref,
                    line_count=move.line_count,
                    total_debit=move.total_debit,
                    total_credit=move.total_credit,
                    balanced=True,
                    line_indexes=list(move.line_indexes),
                    errors=[],
                    move_id=order_id,
                    posted=False,
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                RowError(
                    row_index=move.line_indexes[0] if move.line_indexes else 0,
                    code="blocking",
                    message=f"Create failed for {move.group_key}: {exc}",
                )
            )
            updated.append(move)
    return updated, created, errors


class OrderBatchRecipe:
    """Recipe document_batch.orders — sales / purchase order drafts."""

    id = "document_batch.orders"
    risk = "L1"
    title = "Order batch"
    blurb = (
        "CSV/XLSX → draft sale.order / purchase.order. "
        "Preview ≠ confirmed. Never auto-confirm."
    )
    atlas_class = "document_batch"

    def intake(
        self,
        *,
        connection_id: str,
        filename: str,
        headers: list[str],
        rows: list[dict[str, str]],
        extras: dict[str, Any] | None = None,
    ) -> BatchJobState:
        suggested = suggest_order_column_map(headers)
        return BatchJobState(
            job_id=str(uuid.uuid4()),
            connection_id=connection_id,
            recipe_id=self.id,
            risk="L1",
            phase="intake",
            filename=filename,
            headers=list(headers),
            raw_rows=list(rows),
            column_map=suggested,
            warnings=[],
            message=f"Loaded {len(rows)} rows from {filename or 'upload'}",
            honesty=HONESTY_PREVIEW_NE_CONFIRMED,
            extras={"model": "sale.order|purchase.order", "order_batch": True, **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState:
        cmap = column_map if column_map is not None else state.column_map
        state.column_map = dict(cmap)
        lines, errors = build_order_lines(state.raw_rows, state.column_map)
        state.mapped_lines = lines
        state.errors = [e for e in errors if e.code == "blocking"] + [
            e for e in errors if e.code != "blocking"
        ]
        state.phase = "mapped"
        state.message = f"Mapped {len(lines)} order lines"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not state.mapped_lines:
            state = self.map(state)
        sale_ok = client.model_exists("sale.order")
        purchase_ok = client.model_exists("purchase.order")
        if not sale_ok and not purchase_ok:
            state.errors.append(
                RowError(
                    row_index=0,
                    code="blocking",
                    message="Neither sale.order nor purchase.order is installed",
                )
            )
            state.phase = "failed"
            return state
        resolved, res_errors = resolve_order_lines(client, state.mapped_lines)
        state.mapped_lines = resolved
        state.errors = [e for e in state.errors if e.code != "blocking"] + res_errors
        state.moves = group_orders(resolved)
        for m in state.moves:
            if not m.balanced:
                state.errors.append(
                    RowError(
                        row_index=m.line_indexes[0] if m.line_indexes else 0,
                        code="blocking",
                        message=f"Order {m.ref or m.group_key} invalid: {'; '.join(m.errors)}",
                    )
                )
        state.phase = "validated"
        state.message = (
            f"Validated {len(state.moves)} order(s) "
            f"({sum(1 for m in state.moves if m.balanced)} ready)"
        )
        state.honesty = HONESTY_PREVIEW_NE_CONFIRMED
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        blocking = [e for e in state.errors if e.code == "blocking"]
        if blocking:
            state.phase = "failed"
            state.message = f"Dry-run blocked: {len(blocking)} error(s)"
            return state
        updated, _, err = create_draft_orders(
            client, state.mapped_lines, state.moves, dry_run=True
        )
        state.moves = updated
        state.errors.extend(err)
        state.phase = "dry_run"
        state.dry_run = True
        state.message = (
            f"Dry-run OK — would create {len(state.moves)} DRAFT order(s). "
            f"{HONESTY_PREVIEW_NE_CONFIRMED}"
        )
        return state

    def apply(
        self,
        state: BatchJobState,
        client: Any,
        *,
        post_after_create: bool = False,
    ) -> BatchJobState:
        del post_after_create  # orders never auto-confirm
        state = self.validate(state, client)
        blocking = [e for e in state.errors if e.code == "blocking"]
        if blocking:
            state.phase = "failed"
            state.message = f"Apply blocked: {len(blocking)} error(s)"
            return state
        updated, created, err = create_draft_orders(
            client, state.mapped_lines, state.moves, dry_run=False
        )
        state.moves = updated
        state.created_move_ids = created
        state.posted_move_ids = []
        state.errors.extend(err)
        state.phase = "applied"
        state.dry_run = False
        state.post_after_create = False
        state.message = f"Created {len(created)} draft order(s) (not confirmed)"
        state.honesty = HONESTY_PREVIEW_NE_CONFIRMED
        return state
