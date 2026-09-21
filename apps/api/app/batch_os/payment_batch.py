"""Payment / matching helpers v1 — register payments against open moves (public RPC).

Risk L2 on apply. Dry-run first. Honesty: preview ≠ posted.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.batch_os.partner_match import resolve_partner_id
from app.batch_os.types import (
    HONESTY_PREVIEW_NE_POSTED,
    PAYMENT_COLUMN_TARGETS,
    PAYMENT_HEADER_ALIASES,
    BatchJobState,
    MappedLine,
    MovePreview,
    RowError,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def suggest_payment_column_map(headers: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    used: set[str] = set()
    for h in headers:
        low = h.strip().lower().replace(" ", "_")
        target = PAYMENT_HEADER_ALIASES.get(low)
        if target and target not in used:
            out[h] = target
            used.add(target)
            continue
        if low in PAYMENT_COLUMN_TARGETS and low not in used:
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


def build_payment_lines(
    rows: list[dict[str, str]],
    column_map: dict[str, str],
) -> tuple[list[MappedLine], list[RowError]]:
    lines: list[MappedLine] = []
    errors: list[RowError] = []
    targets = set(column_map.values())
    if "move_ref" not in targets and "partner" not in targets:
        errors.append(
            RowError(
                row_index=0,
                code="blocking",
                message="Need move_ref and/or partner column",
            )
        )
        return lines, errors
    if "amount" not in targets:
        errors.append(
            RowError(row_index=0, field="amount", code="blocking", message="amount column required")
        )
        return lines, errors

    for idx, row in enumerate(rows, start=1):
        move_ref = _pick(row, column_map, "move_ref")
        partner = _pick(row, column_map, "partner")
        amount = _num(_pick(row, column_map, "amount"))
        if not move_ref and not partner and amount == 0:
            continue
        if amount <= 0:
            errors.append(
                RowError(
                    row_index=idx, field="amount", code="blocking", message="Amount must be > 0"
                )
            )
        date_s = _pick(row, column_map, "date")
        if date_s and not _DATE_RE.match(date_s[:10]):
            errors.append(
                RowError(
                    row_index=idx, field="date", code="warn", message="Prefer ISO YYYY-MM-DD"
                )
            )
        pay_type = (_pick(row, column_map, "payment_type") or "inbound").lower()
        if pay_type not in {"inbound", "outbound"}:
            # infer later from move
            pay_type = "inbound"
        lines.append(
            MappedLine(
                row_index=idx,
                journal_key=_pick(row, column_map, "journal"),
                date=(date_s[:10] if date_s else ""),
                ref=move_ref,
                label=_pick(row, column_map, "memo") or f"Payment {move_ref or partner}",
                account_key=pay_type,  # park payment_type
                debit=amount,
                credit=0.0,
                partner_key=partner,
                move_group=move_ref or f"pay-{idx}",
            )
        )
    return lines, errors


def _resolve_open_move(client: Any, ref: str, partner_id: int | None) -> dict[str, Any] | None:
    if not client.model_exists("account.move"):
        return None
    domain: list[Any] = [
        ("state", "=", "posted"),
        ("payment_state", "in", ["not_paid", "partial"]),
        ("move_type", "in", ["out_invoice", "in_invoice", "out_refund", "in_refund"]),
    ]
    if ref:
        if ref.isdigit():
            domain = [("id", "=", int(ref))] + domain[1:]  # keep filters loosely
            domain = [
                ("id", "=", int(ref)),
                ("state", "=", "posted"),
            ]
        else:
            domain = [
                "|",
                ("name", "=", ref),
                ("ref", "=", ref),
                ("state", "=", "posted"),
                ("payment_state", "in", ["not_paid", "partial"]),
            ]
    if partner_id and not (ref and ref.isdigit()):
        domain.append(("partner_id", "=", partner_id))
    rows = client.execute_kw(
        "account.move",
        "search_read",
        [domain],
        {
            "fields": [
                "id",
                "name",
                "ref",
                "partner_id",
                "amount_residual",
                "move_type",
                "payment_state",
            ],
            "limit": 2,
        },
    )
    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1 and ref:
        return rows[0]
    return None


def _resolve_partner_id(client: Any, key: str) -> int | None:
    return resolve_partner_id(client, key=key, name=key)



def _resolve_payment_journal(client: Any, key: str) -> int | None:
    if not client.model_exists("account.journal"):
        return None
    key = (key or "").strip()
    if key:
        for domain in (
            [("code", "=", key)],
            [("name", "=", key)],
            [("type", "in", ["bank", "cash"]), ("code", "ilike", key)],
        ):
            rows = client.execute_kw(
                "account.journal",
                "search_read",
                [domain],
                {"fields": ["id"], "limit": 1},
            )
            if rows:
                return int(rows[0]["id"])
    rows = client.execute_kw(
        "account.journal",
        "search_read",
        [[("type", "in", ["bank", "cash"])]],
        {"fields": ["id"], "limit": 1},
    )
    return int(rows[0]["id"]) if rows else None


def resolve_payment_lines(
    client: Any, lines: list[MappedLine]
) -> tuple[list[MappedLine], list[RowError]]:
    errors: list[RowError] = []
    out: list[MappedLine] = []
    for line in lines:
        partner_id = _resolve_partner_id(client, line.partner_key) if line.partner_key else None
        if line.partner_key and partner_id is None:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="partner",
                    code="warn",
                    message=f"Partner not resolved: {line.partner_key!r}",
                )
            )
        move = _resolve_open_move(client, line.ref, partner_id)
        if move is None:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="move_ref",
                    code="blocking",
                    message=f"Open move not found: {line.ref or line.partner_key!r}",
                )
            )
            move_id = None
            residual = 0.0
            move_type = ""
        else:
            move_id = int(move["id"])
            residual = float(move.get("amount_residual") or 0)
            move_type = str(move.get("move_type") or "")
            if not partner_id and move.get("partner_id"):
                partner_id = (
                    int(move["partner_id"][0])
                    if isinstance(move["partner_id"], (list, tuple))
                    else int(move["partner_id"])
                )
            if line.debit - residual > 0.01:
                errors.append(
                    RowError(
                        row_index=line.row_index,
                        field="amount",
                        code="warn",
                        message=f"Amount {line.debit} > residual {residual} on {move.get('name')}",
                    )
                )

        journal_id = _resolve_payment_journal(client, line.journal_key)
        if journal_id is None:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="journal",
                    code="blocking",
                    message=f"Bank/cash journal not found: {line.journal_key or '(default)'!r}",
                )
            )

        # Infer payment type from move if needed
        pay_type = line.account_key or "inbound"
        if move_type in {"in_invoice", "in_refund"}:
            pay_type = "outbound" if move_type == "in_invoice" else "inbound"
        elif move_type in {"out_invoice", "out_refund"}:
            pay_type = "inbound" if move_type == "out_invoice" else "outbound"

        date_s = line.date
        if not date_s:
            from datetime import date as _date

            date_s = _date.today().isoformat()

        out.append(
            MappedLine(
                row_index=line.row_index,
                journal_key=line.journal_key,
                journal_id=journal_id,
                date=date_s[:10],
                ref=line.ref,
                label=line.label,
                account_key=pay_type,
                account_id=move_id,  # park target move id
                debit=line.debit,
                credit=residual,
                partner_key=line.partner_key,
                partner_id=partner_id,
                move_group=line.move_group,
            )
        )
    return out, errors


def group_payments(lines: list[MappedLine]) -> list[MovePreview]:
    moves: list[MovePreview] = []
    for line in lines:
        ok = line.account_id is not None and line.journal_id is not None and line.debit > 0
        errs: list[str] = []
        if line.account_id is None:
            errs.append("No open move")
        if line.journal_id is None:
            errs.append("No payment journal")
        moves.append(
            MovePreview(
                group_key=f"pay-{line.row_index}-{line.account_id}",
                journal_id=line.journal_id,
                journal_name=line.account_key,  # inbound/outbound
                date=line.date,
                ref=line.ref or line.label,
                line_count=1,
                total_debit=line.debit,
                total_credit=line.credit,  # residual
                balanced=ok,
                line_indexes=[line.row_index],
                errors=errs,
            )
        )
    return moves


def _register_payment(
    client: Any,
    *,
    move_id: int,
    amount: float,
    journal_id: int,
    partner_id: int | None,
    payment_type: str,
    date: str,
    memo: str,
    dry_run: bool,
) -> int | None:
    """Prefer account.payment.register wizard; fall back to account.payment create."""
    if dry_run:
        return None

    # Try payment register wizard (Odoo 14+)
    if client.model_exists("account.payment.register"):
        try:
            wiz_id = client.execute_kw(
                "account.payment.register",
                "create",
                [
                    {
                        "payment_date": date,
                        "amount": amount,
                        "journal_id": journal_id,
                        "communication": memo,
                    }
                ],
                {
                    "context": {
                        "active_model": "account.move",
                        "active_ids": [move_id],
                    }
                },
            )
            if isinstance(wiz_id, list):
                wiz_id = wiz_id[0]
            client.execute_kw(
                "account.payment.register",
                "action_create_payments",
                [[int(wiz_id)]],
                {
                    "context": {
                        "active_model": "account.move",
                        "active_ids": [move_id],
                    }
                },
            )
            return int(wiz_id)
        except Exception:
            pass  # fall through

    if not client.model_exists("account.payment"):
        raise RuntimeError("account.payment / account.payment.register not available")

    partner_type = "customer" if payment_type == "inbound" else "supplier"
    vals: dict[str, Any] = {
        "payment_type": payment_type,
        "partner_type": partner_type,
        "amount": amount,
        "date": date,
        "journal_id": journal_id,
        "ref": memo,
    }
    if partner_id:
        vals["partner_id"] = partner_id
    pay_id = client.execute_kw("account.payment", "create", [vals])
    if isinstance(pay_id, list):
        pay_id = pay_id[0]
    pay_id = int(pay_id)
    client.execute_kw("account.payment", "action_post", [[pay_id]])
    return pay_id


def create_payments(
    client: Any,
    lines: list[MappedLine],
    moves: list[MovePreview],
    *,
    dry_run: bool,
) -> tuple[list[MovePreview], list[int], list[RowError]]:
    errors: list[RowError] = []
    created: list[int] = []
    updated: list[MovePreview] = []
    line_by_row = {l.row_index: l for l in lines}

    for move in moves:
        row_idx = move.line_indexes[0] if move.line_indexes else 0
        line = line_by_row.get(row_idx)
        if not move.balanced or line is None or line.account_id is None or line.journal_id is None:
            errors.append(
                RowError(
                    row_index=row_idx,
                    code="blocking",
                    message=f"Skip payment: {'; '.join(move.errors) or 'invalid'}",
                )
            )
            updated.append(move)
            continue
        if dry_run:
            updated.append(
                MovePreview(
                    group_key=move.group_key,
                    journal_id=move.journal_id,
                    journal_name=move.journal_name,
                    date=move.date,
                    ref=move.ref,
                    line_count=1,
                    total_debit=move.total_debit,
                    total_credit=move.total_credit,
                    balanced=True,
                    line_indexes=list(move.line_indexes),
                    errors=list(move.errors)
                    + [
                        f"dry-run: would register {line.debit} against move {line.account_id} "
                        f"(residual {line.credit}). Preview ≠ posted."
                    ],
                )
            )
            continue
        try:
            pay_id = _register_payment(
                client,
                move_id=int(line.account_id),
                amount=float(line.debit),
                journal_id=int(line.journal_id),
                partner_id=line.partner_id,
                payment_type=line.account_key or "inbound",
                date=line.date,
                memo=line.label,
                dry_run=False,
            )
            if pay_id:
                created.append(pay_id)
            updated.append(
                MovePreview(
                    group_key=move.group_key,
                    journal_id=move.journal_id,
                    journal_name=move.journal_name,
                    date=move.date,
                    ref=move.ref,
                    line_count=1,
                    total_debit=move.total_debit,
                    total_credit=move.total_credit,
                    balanced=True,
                    line_indexes=list(move.line_indexes),
                    errors=[],
                    move_id=pay_id,
                    posted=True,
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                RowError(
                    row_index=row_idx,
                    code="blocking",
                    message=f"Payment failed for move {line.account_id}: {exc}",
                )
            )
            updated.append(move)
    return updated, created, errors


class PaymentBatchRecipe:
    """Recipe document_batch.payments — register payments (L2)."""

    id = "document_batch.payments"
    risk = "L2"
    title = "Payment matching"
    blurb = "Register payments against open invoices/bills. Dry-run first. Preview ≠ posted."
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
        suggested = suggest_payment_column_map(headers)
        return BatchJobState(
            job_id=str(uuid.uuid4()),
            connection_id=connection_id,
            recipe_id=self.id,
            risk="L2",
            phase="intake",
            filename=filename,
            headers=list(headers),
            raw_rows=list(rows),
            column_map=suggested,
            warnings=[],
            message=f"Loaded {len(rows)} payment rows from {filename or 'upload'}",
            honesty=(
                "Payment preview is not posted. Dry-run only validates open moves and amounts. "
                + HONESTY_PREVIEW_NE_POSTED
            ),
            extras={"model": "account.payment", **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState:
        cmap = column_map if column_map is not None else state.column_map
        state.column_map = dict(cmap)
        lines, errors = build_payment_lines(state.raw_rows, state.column_map)
        state.mapped_lines = lines
        state.errors = [e for e in errors if e.code == "blocking"] + [
            e for e in errors if e.code != "blocking"
        ]
        state.phase = "mapped"
        state.message = f"Mapped {len(lines)} payment rows"
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
        resolved, res_errors = resolve_payment_lines(client, state.mapped_lines)
        state.mapped_lines = resolved
        state.errors = [e for e in state.errors if e.code != "blocking"] + res_errors
        state.moves = group_payments(resolved)
        for m in state.moves:
            if not m.balanced:
                state.errors.append(
                    RowError(
                        row_index=m.line_indexes[0] if m.line_indexes else 0,
                        code="blocking",
                        message=f"Payment row invalid: {'; '.join(m.errors)}",
                    )
                )
        state.phase = "validated"
        state.risk = "L2"
        state.message = f"Validated {len(state.moves)} payment(s)"
        state.honesty = (
            "Payment apply posts payments (L2). Dry-run does not. " + HONESTY_PREVIEW_NE_POSTED
        )
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        blocking = [e for e in state.errors if e.code == "blocking"]
        if blocking:
            state.phase = "failed"
            state.message = f"Dry-run blocked: {len(blocking)} error(s)"
            return state
        updated, _, err = create_payments(
            client, state.mapped_lines, state.moves, dry_run=True
        )
        state.moves = updated
        state.errors.extend(err)
        state.phase = "dry_run"
        state.dry_run = True
        state.message = (
            f"Dry-run OK — would register {len(state.moves)} payment(s). "
            "Preview ≠ posted."
        )
        return state

    def apply(
        self,
        state: BatchJobState,
        client: Any,
        *,
        post_after_create: bool = False,
    ) -> BatchJobState:
        del post_after_create  # payments always post via register/action_post
        state = self.validate(state, client)
        blocking = [e for e in state.errors if e.code == "blocking"]
        if blocking:
            state.phase = "failed"
            state.message = f"Apply blocked: {len(blocking)} error(s)"
            return state
        state.risk = "L2"
        updated, created, err = create_payments(
            client, state.mapped_lines, state.moves, dry_run=False
        )
        state.moves = updated
        state.created_move_ids = created
        state.posted_move_ids = list(created)
        state.errors.extend(err)
        state.phase = "applied"
        state.dry_run = False
        state.post_after_create = True
        state.message = f"Registered {len(created)} payment(s) (posted)"
        state.honesty = HONESTY_PREVIEW_NE_POSTED
        return state
