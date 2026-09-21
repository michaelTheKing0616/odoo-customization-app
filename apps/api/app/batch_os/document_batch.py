"""Document batch — CSV/XLSX → customer invoices & vendor bills (public RPC).

Creates account.move drafts (out_invoice / in_invoice). Reuses Batch OS runner.
Preview ≠ posted.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from typing import Any

from app.batch_os.partner_match import resolve_partner_id
from app.batch_os.types import (
    DOCUMENT_COLUMN_TARGETS,
    DOCUMENT_HEADER_ALIASES,
    HONESTY_PREVIEW_NE_POSTED,
    BatchJobState,
    MappedLine,
    MovePreview,
    RowError,
)
from app.ingest.opening_balance import resolve_account_id

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_OUT = {"out_invoice", "out", "invoice", "customer", "customer_invoice", "sale"}
_IN = {"in_invoice", "in", "bill", "vendor", "vendor_bill", "purchase", "supplier"}


def suggest_document_column_map(headers: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    used: set[str] = set()
    for h in headers:
        low = h.strip().lower().replace(" ", "_")
        target = DOCUMENT_HEADER_ALIASES.get(low)
        if target and target not in used:
            out[h] = target
            used.add(target)
            continue
        if low in DOCUMENT_COLUMN_TARGETS and low not in used:
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


def _normalize_move_type(raw: str) -> str:
    low = (raw or "").strip().lower().replace(" ", "_")
    if low in _IN:
        return "in_invoice"
    if low in {"out_invoice", "in_invoice"}:
        return low
    return "out_invoice"


def _encode_ref(*, ref: str, due: str, move_type: str, product: str, tax: str, tax_incl: str = "", currency: str = "", amount_currency: str = "") -> str:
    parts: list[str] = []
    if ref:
        parts.append(ref)
    if due:
        parts.append(f"due:{due[:10]}")
    parts.append(f"type:{move_type}")
    if product:
        parts.append(f"product:{product}")
    if tax:
        parts.append(f"taxkey:{tax}")
    if tax_incl:
        parts.append(f"taxincl:{tax_incl}")
    if currency:
        parts.append(f"currency:{currency}")
    if amount_currency:
        parts.append(f"amtcurr:{amount_currency}")
    return "||".join(parts)


def _parse_ref(ref: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, part in enumerate((ref or "").split("||")):
        if part.startswith("due:"):
            out["due"] = part[4:]
        elif part.startswith("type:"):
            out["move_type"] = part[5:]
        elif part.startswith("product:"):
            out["product"] = part[8:]
        elif part.startswith("taxkey:"):
            out["taxkey"] = part[7:]
        elif part.startswith("taxincl:"):
            out["tax_inclusive"] = part[8:]
        elif part.startswith("currency:"):
            out["currency"] = part[9:]
        elif part.startswith("amtcurr:"):
            out["amount_currency"] = part[8:]
        elif part.startswith("taxids:"):
            out["taxids"] = part[7:]
        elif part and i == 0:
            out["ref"] = part
    return out


def build_document_lines(
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
        account = _pick(row, column_map, "account")
        label = _pick(row, column_map, "label") or product or "Invoice line"
        if not partner and qty == 0 and price == 0 and not product and not account:
            continue
        if not partner:
            errors.append(
                RowError(
                    row_index=idx, field="partner", code="blocking", message="Partner required"
                )
            )
        if not product and not account and not label:
            errors.append(
                RowError(
                    row_index=idx,
                    field="product",
                    code="blocking",
                    message="Need product, account, or label",
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
        due_s = _pick(row, column_map, "due")
        move_type = _normalize_move_type(_pick(row, column_map, "move_type"))
        group = (
            _pick(row, column_map, "invoice_group")
            or _pick(row, column_map, "ref")
            or f"{partner}-{date_s or 'nodate'}-{idx}"
        )
        tax = _pick(row, column_map, "tax")
        tax_incl = _pick(row, column_map, "tax_inclusive")
        currency = _pick(row, column_map, "currency")
        amount_currency = _pick(row, column_map, "amount_currency")
        lines.append(
            MappedLine(
                row_index=idx,
                journal_key=_pick(row, column_map, "journal"),
                date=(date_s[:10] if date_s else ""),
                ref=_encode_ref(
                    ref=_pick(row, column_map, "ref"),
                    due=due_s,
                    move_type=move_type,
                    product=product,
                    tax=tax,
                    tax_incl=tax_incl,
                    currency=currency,
                    amount_currency=amount_currency,
                ),
                label=label,
                account_key=account or product,
                debit=qty,
                credit=price,
                partner_key=partner,
                analytic_key=tax,
                move_group=group,
            )
        )
    return lines, errors


def _resolve_partner_id(client: Any, key: str, *, vat: str = "", email: str = "", ref: str = "") -> int | None:
    return resolve_partner_id(client, key=key, vat=vat, email=email, ref=ref, name=key)




def _resolve_journal_id(client: Any, key: str, move_type: str) -> tuple[int | None, str | None]:
    if not client.model_exists("account.journal"):
        return None, None
    jtype = "sale" if move_type == "out_invoice" else "purchase"
    key = (key or "").strip()
    if key:
        for domain in (
            [("code", "=", key)],
            [("name", "=", key)],
            [("code", "ilike", key)],
            [("name", "ilike", key)],
        ):
            rows = client.execute_kw(
                "account.journal",
                "search_read",
                [domain],
                {"fields": ["id", "name", "code"], "limit": 2},
            )
            if rows:
                return int(rows[0]["id"]), str(rows[0].get("name") or rows[0].get("code") or "")
    rows = client.execute_kw(
        "account.journal",
        "search_read",
        [[("type", "=", jtype)]],
        {"fields": ["id", "name", "code"], "limit": 1},
    )
    if rows:
        return int(rows[0]["id"]), str(rows[0].get("name") or "")
    return None, None


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


def _resolve_tax_ids(client: Any, key: str) -> list[int]:
    key = (key or "").strip()
    if not key or not client.model_exists("account.tax"):
        return []
    if key.isdigit():
        return [int(key)]
    rows = client.execute_kw(
        "account.tax",
        "search_read",
        [["|", ("name", "=", key), ("name", "ilike", key)]],
        {"fields": ["id"], "limit": 2},
    )
    if len(rows) == 1:
        return [int(rows[0]["id"])]
    return []


def resolve_document_lines(
    client: Any, lines: list[MappedLine]
) -> tuple[list[MappedLine], list[RowError]]:
    errors: list[RowError] = []
    out: list[MappedLine] = []
    journal_cache: dict[str, tuple[int | None, str | None]] = {}

    for line in lines:
        meta = _parse_ref(line.ref)
        move_type = meta.get("move_type") or "out_invoice"
        jkey = f"{line.journal_key}|{move_type}"
        if jkey not in journal_cache:
            journal_cache[jkey] = _resolve_journal_id(client, line.journal_key, move_type)
        jid, _ = journal_cache[jkey]

        partner_id = _resolve_partner_id(client, line.partner_key)
        if partner_id is None:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="partner",
                    code="blocking",
                    message=f"Partner not found: {line.partner_key!r}",
                )
            )

        product_key = meta.get("product") or ""
        product_id = _resolve_product_id(client, product_key) if product_key else None
        account_id = None
        if line.account_key and line.account_key != product_key:
            account_id = resolve_account_id(client, line.account_key)
            if account_id is None and product_id is None:
                product_id = _resolve_product_id(client, line.account_key)
        elif line.account_key and product_id is None:
            product_id = _resolve_product_id(client, line.account_key)
            if product_id is None:
                account_id = resolve_account_id(client, line.account_key)

        if product_id is None and account_id is None:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="product",
                    code="blocking",
                    message=f"Product/account not resolved: {line.account_key or product_key!r}",
                )
            )
        if jid is None:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="journal",
                    code="blocking",
                    message=f"Journal not found for {move_type}: {line.journal_key or '(default)'!r}",
                )
            )

        tax_ids = _resolve_tax_ids(client, line.analytic_key) if line.analytic_key else []
        if line.analytic_key and not tax_ids:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="tax",
                    code="warn",
                    message=f"Tax not resolved: {line.analytic_key!r}",
                )
            )

        date_s = line.date
        if not date_s:
            from datetime import date as _date

            date_s = _date.today().isoformat()

        ref = line.ref
        if tax_ids:
            ref = f"{ref}||taxids:{','.join(str(t) for t in tax_ids)}"

        out.append(
            MappedLine(
                row_index=line.row_index,
                journal_key=line.journal_key,
                journal_id=jid,
                date=date_s[:10],
                ref=ref,
                label=line.label,
                account_key=line.account_key,
                account_id=account_id,
                debit=line.debit,
                credit=line.credit,
                partner_key=line.partner_key,
                partner_id=partner_id,
                analytic_key=line.analytic_key,
                analytic_id=product_id,  # product_id parked here
                move_group=line.move_group,
            )
        )
    return out, errors


def _group_key(line: MappedLine) -> str:
    meta = _parse_ref(line.ref)
    move_type = meta.get("move_type") or "out_invoice"
    return f"{line.move_group}|{move_type}|{line.partner_id}|{line.journal_id}|{line.date}"


def group_documents(lines: list[MappedLine]) -> list[MovePreview]:
    groups: dict[str, list[MappedLine]] = defaultdict(list)
    for line in lines:
        groups[_group_key(line)].append(line)

    moves: list[MovePreview] = []
    for key, group_lines in groups.items():
        errs: list[str] = []
        first = group_lines[0]
        meta = _parse_ref(first.ref)
        move_type = meta.get("move_type") or "out_invoice"
        if not first.partner_id:
            errs.append("Missing partner")
        if first.journal_id is None:
            errs.append("Missing journal")
        total = sum(round(l.debit * l.credit, 2) for l in group_lines)
        balanced = bool(first.partner_id and first.journal_id and not errs)
        moves.append(
            MovePreview(
                group_key=key,
                journal_id=first.journal_id,
                journal_name=move_type,
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


def create_draft_documents(
    client: Any,
    lines: list[MappedLine],
    moves: list[MovePreview],
    *,
    dry_run: bool,
    post_after_create: bool = False,
) -> tuple[list[MovePreview], list[int], list[int], list[RowError]]:
    errors: list[RowError] = []
    created: list[int] = []
    posted: list[int] = []
    by_group: dict[str, list[MappedLine]] = defaultdict(list)
    for line in lines:
        by_group[_group_key(line)].append(line)

    updated: list[MovePreview] = []
    for move in moves:
        if not move.balanced or move.journal_id is None:
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
        move_type = meta.get("move_type") or "out_invoice"
        due = meta.get("due") or ""

        line_cmds: list[tuple[int, int, dict[str, Any]]] = []
        for gl in group_lines:
            qty = gl.debit if gl.debit else 1.0
            price = gl.credit
            vals: dict[str, Any] = {
                "name": gl.label,
                "quantity": qty,
                "price_unit": price,
            }
            if gl.analytic_id:
                vals["product_id"] = gl.analytic_id
            if gl.account_id:
                vals["account_id"] = gl.account_id
            gmeta = _parse_ref(gl.ref)
            if gmeta.get("taxids"):
                try:
                    tids = [int(x) for x in gmeta["taxids"].split(",") if x]
                    if tids:
                        vals["tax_ids"] = [(6, 0, tids)]
                except ValueError:
                    pass
            line_cmds.append((0, 0, vals))

        move_vals: dict[str, Any] = {
            "move_type": move_type,
            "partner_id": int(first.partner_id) if first.partner_id else False,
            "journal_id": int(move.journal_id),
            "invoice_date": move.date,
            "ref": move.ref or "ingenium document batch",
            "invoice_line_ids": line_cmds,
        }
        if due:
            move_vals["invoice_date_due"] = due
        # Multi-currency (graceful skip if currency missing / field unavailable)
        cur = meta.get("currency") or ""
        if cur and client.model_exists("res.currency"):
            try:
                crows = client.execute_kw(
                    "res.currency",
                    "search_read",
                    [[("|", ("name", "=", cur.upper()), ("name", "ilike", cur))]],
                    {"fields": ["id"], "limit": 1},
                )
                if crows:
                    move_vals["currency_id"] = int(crows[0]["id"])
            except Exception:
                pass
        if meta.get("tax_inclusive"):
            # Honesty: price_include is a tax-flag in Odoo; we record intent in ref only.
            move_vals["narration"] = (move_vals.get("narration") or "") + f" [tax_inclusive={meta.get('tax_inclusive')}]"

        if dry_run:
            updated.append(
                MovePreview(
                    group_key=move.group_key,
                    journal_id=move.journal_id,
                    journal_name=move.journal_name,
                    date=move.date,
                    ref=move.ref,
                    line_count=move.line_count,
                    total_debit=move.total_debit,
                    total_credit=move.total_credit,
                    balanced=True,
                    line_indexes=list(move.line_indexes),
                    errors=list(move.errors) + ["dry-run: would create DRAFT (not posted)"],
                )
            )
            continue

        try:
            move_id = client.execute_kw("account.move", "create", [move_vals])
            if isinstance(move_id, list):
                move_id = move_id[0]
            move_id = int(move_id)
            created.append(move_id)
            did_post = False
            if post_after_create:
                try:
                    client.execute_kw("account.move", "action_post", [[move_id]])
                    posted.append(move_id)
                    did_post = True
                except Exception as exc:  # noqa: BLE001
                    errors.append(
                        RowError(
                            row_index=move.line_indexes[0] if move.line_indexes else 0,
                            code="warn",
                            message=f"Created draft {move_id} but post failed: {exc}",
                        )
                    )
            updated.append(
                MovePreview(
                    group_key=move.group_key,
                    journal_id=move.journal_id,
                    journal_name=move.journal_name,
                    date=move.date,
                    ref=move.ref,
                    line_count=move.line_count,
                    total_debit=move.total_debit,
                    total_credit=move.total_credit,
                    balanced=True,
                    line_indexes=list(move.line_indexes),
                    errors=[],
                    move_id=move_id,
                    posted=did_post,
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
    return updated, created, posted, errors


class DocumentBatchRecipe:
    """Recipe document_batch.invoices — invoices & bills."""

    id = "document_batch.invoices"
    risk = "L1"
    title = "Invoices & bills"
    blurb = "CSV/XLSX → draft customer invoices / vendor bills. Preview ≠ posted."
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
        suggested = suggest_document_column_map(headers)
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
            honesty=HONESTY_PREVIEW_NE_POSTED,
            extras={"model": "account.move", "document_batch": True, **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState:
        cmap = column_map if column_map is not None else state.column_map
        state.column_map = dict(cmap)
        lines, errors = build_document_lines(state.raw_rows, state.column_map)
        state.mapped_lines = lines
        state.errors = [e for e in errors if e.code == "blocking"] + [
            e for e in errors if e.code != "blocking"
        ]
        state.phase = "mapped"
        state.message = f"Mapped {len(lines)} document lines"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not state.mapped_lines:
            state = self.map(state)
        if not client.model_exists("account.move"):
            state.errors.append(
                RowError(
                    row_index=0,
                    code="blocking",
                    message="Accounting not installed (account.move missing)",
                )
            )
            state.phase = "failed"
            return state
        resolved, res_errors = resolve_document_lines(client, state.mapped_lines)
        state.mapped_lines = resolved
        state.errors = [e for e in state.errors if e.code != "blocking"] + res_errors
        state.moves = group_documents(resolved)
        for m in state.moves:
            if not m.balanced:
                state.errors.append(
                    RowError(
                        row_index=m.line_indexes[0] if m.line_indexes else 0,
                        code="blocking",
                        message=f"Document {m.ref or m.group_key} invalid: {'; '.join(m.errors)}",
                    )
                )
        state.phase = "validated"
        state.message = (
            f"Validated {len(state.moves)} document(s) "
            f"({sum(1 for m in state.moves if m.balanced)} ready)"
        )
        state.honesty = HONESTY_PREVIEW_NE_POSTED
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        blocking = [e for e in state.errors if e.code == "blocking"]
        if blocking:
            state.phase = "failed"
            state.message = f"Dry-run blocked: {len(blocking)} error(s)"
            return state
        updated, _, _, err = create_draft_documents(
            client,
            state.mapped_lines,
            state.moves,
            dry_run=True,
            post_after_create=False,
        )
        state.moves = updated
        state.errors.extend(err)
        state.phase = "dry_run"
        state.dry_run = True
        state.message = (
            f"Dry-run OK — would create {len(state.moves)} DRAFT invoice/bill(s). "
            f"{HONESTY_PREVIEW_NE_POSTED}"
        )
        return state

    def apply(
        self,
        state: BatchJobState,
        client: Any,
        *,
        post_after_create: bool = False,
    ) -> BatchJobState:
        state = self.validate(state, client)
        blocking = [e for e in state.errors if e.code == "blocking"]
        if blocking:
            state.phase = "failed"
            state.message = f"Apply blocked: {len(blocking)} error(s)"
            return state
        if post_after_create:
            state.risk = "L2"
        updated, created, posted, err = create_draft_documents(
            client,
            state.mapped_lines,
            state.moves,
            dry_run=False,
            post_after_create=post_after_create,
        )
        state.moves = updated
        state.created_move_ids = created
        state.posted_move_ids = posted
        state.errors.extend(err)
        state.phase = "applied"
        state.dry_run = False
        state.post_after_create = post_after_create
        state.message = (
            f"Created {len(created)} draft invoice/bill(s)"
            + (f"; posted {len(posted)}" if post_after_create else " (not posted)")
        )
        state.honesty = HONESTY_PREVIEW_NE_POSTED
        return state
