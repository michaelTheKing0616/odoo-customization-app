"""Journal Batch v1 — CSV/XLSX → balanced account.move drafts via public RPC."""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from typing import Any

from app.batch_os.types import (
    HONESTY_PREVIEW_NE_POSTED,
    JOURNAL_COLUMN_TARGETS,
    JOURNAL_HEADER_ALIASES,
    BatchJobState,
    MappedLine,
    MovePreview,
    RowError,
)
from app.ingest.opening_balance import find_opening_journal, resolve_account_id

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def suggest_journal_column_map(headers: list[str]) -> dict[str, str]:
    """Map CSV header → canonical target (journal, date, …)."""
    out: dict[str, str] = {}
    used_targets: set[str] = set()
    for h in headers:
        low = h.strip().lower().replace(" ", "_")
        target = JOURNAL_HEADER_ALIASES.get(low)
        if target and target not in used_targets:
            out[h] = target
            used_targets.add(target)
            continue
        # Exact target name as header
        if low in JOURNAL_COLUMN_TARGETS and low not in used_targets:
            out[h] = low
            used_targets.add(low)
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


def build_mapped_lines(
    rows: list[dict[str, str]],
    column_map: dict[str, str],
) -> tuple[list[MappedLine], list[RowError]]:
    lines: list[MappedLine] = []
    errors: list[RowError] = []
    required = {"account", "debit", "credit"}
    mapped_targets = set(column_map.values())
    missing = required - mapped_targets
    if missing:
        errors.append(
            RowError(
                row_index=0,
                code="blocking",
                message=f"Column map missing required targets: {', '.join(sorted(missing))}",
            )
        )
        return lines, errors

    for idx, row in enumerate(rows, start=1):
        debit = _num(_pick(row, column_map, "debit"))
        credit = _num(_pick(row, column_map, "credit"))
        account = _pick(row, column_map, "account")
        if not account and debit == 0 and credit == 0:
            continue
        if not account:
            errors.append(
                RowError(row_index=idx, field="account", code="blocking", message="Account required")
            )
        if debit < 0 or credit < 0:
            errors.append(
                RowError(
                    row_index=idx,
                    field="debit/credit",
                    code="blocking",
                    message="Debit/credit must be non-negative",
                )
            )
        if debit > 0 and credit > 0:
            errors.append(
                RowError(
                    row_index=idx,
                    field="debit/credit",
                    code="blocking",
                    message="Line cannot have both debit and credit",
                )
            )
        if debit == 0 and credit == 0:
            errors.append(
                RowError(
                    row_index=idx,
                    field="debit/credit",
                    code="blocking",
                    message="Line needs debit or credit",
                )
            )
        date_s = _pick(row, column_map, "date")
        if date_s and not _DATE_RE.match(date_s[:10]):
            # Try to normalize common slash formats later; flag soft for now
            if "/" in date_s:
                parts = date_s.replace(".", "/").split("/")
                if len(parts) == 3:
                    # assume D/M/Y or M/D/Y — prefer ISO if year first already failed
                    if len(parts[2]) == 4:
                        # D/M/Y or M/D/Y — keep as warning, Operator should use ISO
                        pass
            errors.append(
                RowError(
                    row_index=idx,
                    field="date",
                    code="warn",
                    message="Prefer ISO date YYYY-MM-DD",
                )
            )
        group = _pick(row, column_map, "move_group") or _pick(row, column_map, "ref") or f"row-{idx}"
        lines.append(
            MappedLine(
                row_index=idx,
                journal_key=_pick(row, column_map, "journal"),
                date=(date_s[:10] if date_s else ""),
                ref=_pick(row, column_map, "ref"),
                label=_pick(row, column_map, "label") or "Journal batch line",
                account_key=account,
                debit=debit,
                credit=credit,
                partner_key=_pick(row, column_map, "partner"),
                analytic_key=_pick(row, column_map, "analytic"),
                move_group=group,
            )
        )
    return lines, errors


def _resolve_journal_id(client: Any, key: str) -> tuple[int | None, str | None]:
    key = (key or "").strip()
    if not key:
        journal = find_opening_journal(client) if hasattr(client, "model_exists") else None
        # Prefer a general journal for miscellaneous entries when no key given
        if journal:
            return int(journal["id"]), str(journal.get("name") or journal.get("code") or "")
        return None, None
    if not client.model_exists("account.journal"):
        return None, None
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
        if len(rows) == 1:
            return int(rows[0]["id"]), str(rows[0].get("name") or rows[0].get("code") or "")
        if len(rows) > 1 and domain[0][1] == "=":
            return int(rows[0]["id"]), str(rows[0].get("name") or "")
    return None, None


def _resolve_partner_id(client: Any, key: str) -> int | None:
    key = (key or "").strip()
    if not key or not client.model_exists("res.partner"):
        return None
    if key.isdigit():
        return int(key)
    rows = client.execute_kw(
        "res.partner",
        "search_read",
        [[("name", "=", key)]],
        {"fields": ["id"], "limit": 1},
    )
    if rows:
        return int(rows[0]["id"])
    rows = client.execute_kw(
        "res.partner",
        "search_read",
        [[("name", "ilike", key)]],
        {"fields": ["id"], "limit": 2},
    )
    if len(rows) == 1:
        return int(rows[0]["id"])
    return None


def _resolve_analytic_id(client: Any, key: str) -> int | None:
    key = (key or "").strip()
    if not key:
        return None
    model = None
    for candidate in ("account.analytic.account", "analytic.account"):
        if client.model_exists(candidate):
            model = candidate
            break
    if not model:
        return None
    if key.isdigit():
        return int(key)
    rows = client.execute_kw(
        model,
        "search_read",
        [["|", ("code", "=", key), ("name", "=", key)]],
        {"fields": ["id"], "limit": 1},
    )
    return int(rows[0]["id"]) if rows else None


def resolve_lines(client: Any, lines: list[MappedLine]) -> tuple[list[MappedLine], list[RowError]]:
    errors: list[RowError] = []
    journal_cache: dict[str, tuple[int | None, str | None]] = {}
    out: list[MappedLine] = []
    for line in lines:
        jkey = line.journal_key or ""
        if jkey not in journal_cache:
            journal_cache[jkey] = _resolve_journal_id(client, jkey)
        jid, _jname = journal_cache[jkey]
        aid = resolve_account_id(client, line.account_key)
        if aid is None:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="account",
                    code="blocking",
                    message=f"Account not found: {line.account_key!r}",
                )
            )
        if jid is None:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="journal",
                    code="blocking",
                    message=f"Journal not found: {line.journal_key or '(default)'!r}",
                )
            )
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
        analytic_id = (
            _resolve_analytic_id(client, line.analytic_key) if line.analytic_key else None
        )
        if line.analytic_key and analytic_id is None:
            errors.append(
                RowError(
                    row_index=line.row_index,
                    field="analytic",
                    code="warn",
                    message=f"Analytic not resolved: {line.analytic_key!r}",
                )
            )
        date_s = line.date
        if not date_s:
            from datetime import date as _date

            date_s = _date.today().isoformat()
        out.append(
            MappedLine(
                row_index=line.row_index,
                journal_key=line.journal_key,
                journal_id=jid,
                date=date_s[:10],
                ref=line.ref,
                label=line.label,
                account_key=line.account_key,
                account_id=aid,
                debit=line.debit,
                credit=line.credit,
                partner_key=line.partner_key,
                partner_id=partner_id,
                analytic_key=line.analytic_key,
                analytic_id=analytic_id,
                move_group=line.move_group,
            )
        )
    return out, errors


def group_moves(lines: list[MappedLine]) -> list[MovePreview]:
    groups: dict[str, list[MappedLine]] = defaultdict(list)
    for line in lines:
        # Include journal+date so mixed journals don't silently merge
        key = f"{line.move_group}|{line.journal_id}|{line.date}"
        groups[key].append(line)

    moves: list[MovePreview] = []
    for key, group_lines in groups.items():
        total_d = sum(l.debit for l in group_lines)
        total_c = sum(l.credit for l in group_lines)
        balanced = abs(total_d - total_c) <= 0.01
        errs: list[str] = []
        if not balanced:
            errs.append(f"Unbalanced: debit={total_d:.2f} credit={total_c:.2f}")
        jids = {l.journal_id for l in group_lines if l.journal_id}
        if len(jids) > 1:
            errs.append("Mixed journals in one move group")
            balanced = False
        first = group_lines[0]
        moves.append(
            MovePreview(
                group_key=key,
                journal_id=first.journal_id,
                journal_name=None,
                date=first.date,
                ref=first.ref or first.move_group,
                line_count=len(group_lines),
                total_debit=round(total_d, 2),
                total_credit=round(total_c, 2),
                balanced=balanced,
                line_indexes=[l.row_index for l in group_lines],
                errors=errs,
            )
        )
    return moves


def create_draft_moves(
    client: Any,
    lines: list[MappedLine],
    moves: list[MovePreview],
    *,
    dry_run: bool,
    post_after_create: bool = False,
) -> tuple[list[MovePreview], list[int], list[int], list[RowError]]:
    """Create account.move drafts (and optionally action_post). Public RPC only."""
    errors: list[RowError] = []
    created: list[int] = []
    posted: list[int] = []
    lines_by_group: dict[str, list[MappedLine]] = defaultdict(list)
    for line in lines:
        key = f"{line.move_group}|{line.journal_id}|{line.date}"
        lines_by_group[key].append(line)

    updated: list[MovePreview] = []
    for move in moves:
        if not move.balanced or move.journal_id is None:
            errors.append(
                RowError(
                    row_index=move.line_indexes[0] if move.line_indexes else 0,
                    code="blocking",
                    message=f"Skip move {move.group_key}: {'; '.join(move.errors) or 'not balanced'}",
                )
            )
            updated.append(move)
            continue
        group_lines = lines_by_group.get(move.group_key) or []
        line_cmds: list[tuple[int, int, dict[str, Any]]] = []
        for gl in group_lines:
            if gl.account_id is None:
                continue
            vals: dict[str, Any] = {
                "account_id": gl.account_id,
                "name": gl.label,
                "debit": gl.debit,
                "credit": gl.credit,
            }
            if gl.partner_id:
                vals["partner_id"] = gl.partner_id
            if gl.analytic_id:
                # Odoo 16 uses analytic_account_id; 17+ analytic_distribution — try classic field
                vals["analytic_account_id"] = gl.analytic_id
            line_cmds.append((0, 0, vals))
        move_vals = {
            "journal_id": int(move.journal_id),
            "date": move.date,
            "ref": move.ref or "ingenium journal batch",
            "move_type": "entry",
            "line_ids": line_cmds,
        }
        if dry_run:
            updated.append(
                MovePreview(
                    **{
                        **move.to_dict(),
                        "errors": list(move.errors)
                        + ["dry-run: would create DRAFT (not posted)"],
                    }
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


class JournalBatchRecipe:
    """Recipe: accounting.journal_batch (P0)."""

    id = "accounting.journal_batch"
    risk = "L1"  # drafts; posting elevates to L2 at apply time
    title = "Journal batch"
    blurb = "CSV/XLSX → balanced account.move drafts. Preview ≠ posted."

    def intake(
        self,
        *,
        connection_id: str,
        filename: str,
        headers: list[str],
        rows: list[dict[str, str]],
        extras: dict[str, Any] | None = None,
    ) -> BatchJobState:
        suggested = suggest_journal_column_map(headers)
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
            extras={"model": "account.move", **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState:
        cmap = column_map if column_map is not None else state.column_map
        state.column_map = dict(cmap)
        lines, errors = build_mapped_lines(state.raw_rows, state.column_map)
        state.mapped_lines = lines
        state.errors = [e for e in errors if e.code == "blocking"] + [
            e for e in errors if e.code != "blocking"
        ]
        state.phase = "mapped"
        state.message = f"Mapped {len(lines)} lines"
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
        resolved, res_errors = resolve_lines(client, state.mapped_lines)
        state.mapped_lines = resolved
        state.errors = [e for e in state.errors if e.code != "blocking"] + res_errors
        state.moves = group_moves(resolved)
        unbalanced = [m for m in state.moves if not m.balanced]
        for m in unbalanced:
            state.errors.append(
                RowError(
                    row_index=m.line_indexes[0] if m.line_indexes else 0,
                    code="blocking",
                    message=f"Move {m.ref or m.group_key} unbalanced",
                )
            )
        state.phase = "validated"
        state.message = (
            f"Validated {len(state.moves)} moves "
            f"({sum(1 for m in state.moves if m.balanced)} balanced)"
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
        updated, _, _, err = create_draft_moves(
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
            f"Dry-run OK — would create {len(state.moves)} DRAFT move(s). "
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
        # Re-validate before write
        state = self.validate(state, client)
        blocking = [e for e in state.errors if e.code == "blocking"]
        if blocking:
            state.phase = "failed"
            state.message = f"Apply blocked: {len(blocking)} error(s)"
            return state
        if post_after_create:
            state.risk = "L2"
        updated, created, posted, err = create_draft_moves(
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
            f"Created {len(created)} draft move(s)"
            + (f"; posted {len(posted)}" if post_after_create else " (not posted)")
        )
        state.honesty = HONESTY_PREVIEW_NE_POSTED
        return state
