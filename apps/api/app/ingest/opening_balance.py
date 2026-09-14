"""Opening trial balance — never raw account.move.line invent (Slice B guardrail).

Routes TB rows through a draft journal entry on the instance's Opening journal.
If no Opening journal / accounts missing, gap-blocks commit instead of guessing.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from odoo_client import OdooClient

from app.ingest.schema import IngestGap, IngestTable


def find_opening_journal(client: OdooClient) -> dict[str, Any] | None:
    if not client.model_exists("account.journal"):
        return None
    rows = client.execute_kw(
        "account.journal",
        "search_read",
        [["|", ("code", "ilike", "OPEN"), ("name", "ilike", "opening")]],
        {"fields": ["id", "name", "code", "type"], "limit": 5},
    )
    if not rows:
        rows = client.execute_kw(
            "account.journal",
            "search_read",
            [[("type", "=", "general")]],
            {"fields": ["id", "name", "code", "type"], "limit": 1},
        )
    return rows[0] if rows else None


def resolve_account_id(client: OdooClient, code: str) -> int | None:
    code = (code or "").strip()
    if not code or not client.model_exists("account.account"):
        return None
    rows = client.execute_kw(
        "account.account",
        "search_read",
        [[("code", "=", code)]],
        {"fields": ["id", "code"], "limit": 1},
    )
    if not rows:
        rows = client.execute_kw(
            "account.account",
            "search_read",
            [[("code", "ilike", code)]],
            {"fields": ["id", "code"], "limit": 2},
        )
        if len(rows) != 1:
            return None
    return int(rows[0]["id"])


def validate_opening_tb_table(
    client: OdooClient, table: IngestTable
) -> tuple[list[IngestGap], list[str]]:
    """Validate TB rows; return gaps that must block commit."""
    gaps: list[IngestGap] = []
    warnings: list[str] = []
    if table.doc_type != "opening_trial_balance":
        return gaps, warnings
    if not client.model_exists("account.move"):
        gaps.append(
            IngestGap(
                model="account.move",
                field="*",
                value="",
                message="Accounting not installed — cannot import opening trial balance",
            )
        )
        return gaps, warnings
    journal = find_opening_journal(client)
    if not journal:
        gaps.append(
            IngestGap(
                model="account.journal",
                field="code",
                value="OPEN",
                message=(
                    "No Opening / general journal found. Create an Opening journal "
                    "in Odoo Accounting before committing trial balance."
                ),
            )
        )
    from app.config_packet.schema import COA_THRESHOLD
    from app.config_packet.rpc import search_read, exists as rpc_exists

    account_count = 0
    if rpc_exists(client, "account.account"):
        try:
            raw = client.execute_kw("account.account", "search_count", [[]])
            if isinstance(raw, int):
                account_count = raw
            else:
                raise TypeError("search_count unavailable")
        except Exception:  # noqa: BLE001
            rows = search_read(client, "account.account", [], ["code"], limit=5000)
            account_count = len(rows)
    if account_count < COA_THRESHOLD:
        gaps.append(
            IngestGap(
                model="account.account",
                field="*",
                value=str(account_count),
                message=(
                    f"Chart of accounts has {account_count} codes (need ≥ {COA_THRESHOLD}). "
                    "Install l10n / import CoA before opening trial balance — do not guess."
                ),
            )
        )
    for row in table.rows:
        code = str(
            row.values.get("code")
            or row.raw.get("code")
            or row.raw.get("account_code")
            or ""
        ).strip()
        debit = _num(row.values.get("debit") or row.raw.get("debit"))
        credit = _num(row.values.get("credit") or row.raw.get("credit"))
        if not code:
            gaps.append(
                IngestGap(
                    model="account.account",
                    field="code",
                    value="",
                    message=f"TB row {row.source_ref or '?'} missing account code",
                )
            )
            continue
        aid = resolve_account_id(client, code)
        if aid is None:
            gaps.append(
                IngestGap(
                    model="account.account",
                    field="code",
                    value=code,
                    message=f"Account code {code!r} not on instance — import CoA first",
                )
            )
            row.flags.append(f"tb_account_missing:{code}")
        else:
            row.values["account_id"] = aid
        if debit == 0.0 and credit == 0.0:
            gaps.append(
                IngestGap(
                    model="account.move.line",
                    field="debit/credit",
                    value=code,
                    message=f"TB row for {code} has zero debit and credit",
                )
            )
        row.values["debit"] = debit
        row.values["credit"] = credit
    warnings.append(
        "Opening TB commits as a single DRAFT journal entry on the Opening journal — "
        "never auto-posted; human must review and post in Odoo."
    )
    _append_lock_date_gaps(client, table, gaps)
    return gaps, warnings


def _parse_iso_date(raw: Any) -> date | None:
    text = str(raw or "").strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None


def _tb_as_of_date(table: IngestTable) -> date | None:
    for row in table.rows:
        for key in ("date", "as_of", "as_of_date", "period", "tb_date"):
            parsed = _parse_iso_date(row.values.get(key) or row.raw.get(key))
            if parsed:
                return parsed
    return None


def _append_lock_date_gaps(client: Any, table: IngestTable, gaps: list[IngestGap]) -> None:
    from app.config_packet.fingerprint import read_company_lock_dates

    locks = read_company_lock_dates(client)
    present = {k: _parse_iso_date(v) for k, v in locks.items() if v}
    if not any(present.values()):
        return
    tb_date = _tb_as_of_date(table)
    if tb_date is None:
        gaps.append(
            IngestGap(
                model="res.company",
                field="period_lock_date",
                value=",".join(f"{k}={v}" for k, v in locks.items() if v),
                message=(
                    "Opening TB has no date while company lock dates are set. "
                    "Add a date/as_of column or clear the lock in Odoo before ingest."
                ),
            )
        )
        return
    for field, lock in present.items():
        if lock is None:
            continue
        if tb_date <= lock:
            gaps.append(
                IngestGap(
                    model="res.company",
                    field=field,
                    value=str(lock),
                    message=(
                        f"Opening TB date {tb_date.isoformat()} is on or before {field}={lock.isoformat()}. "
                        "Clear or move the lock in Odoo before ingest — still never auto-posted."
                    ),
                )
            )


def commit_opening_tb(
    client: OdooClient,
    table: IngestTable,
    *,
    dry_run: bool,
    rpc_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one draft account.move with balanced lines — never posts."""
    gaps, _ = validate_opening_tb_table(client, table)
    if gaps:
        return {
            "table_id": table.id,
            "model": "account.move",
            "created": 0,
            "updated": 0,
            "failed": len(gaps),
            "skipped": 0,
            "ok": False,
            "message": "; ".join(g.message for g in gaps[:5]),
            "gaps": [g.model_dump() for g in gaps],
        }

    journal = find_opening_journal(client)
    assert journal is not None
    line_cmds: list[tuple[int, int, dict[str, Any]]] = []
    total_debit = 0.0
    total_credit = 0.0
    for row in table.rows:
        aid = int(row.values["account_id"])
        debit = float(row.values.get("debit") or 0)
        credit = float(row.values.get("credit") or 0)
        total_debit += debit
        total_credit += credit
        name = str(row.values.get("name") or row.raw.get("name") or f"Opening {aid}")
        line_cmds.append(
            (
                0,
                0,
                {
                    "account_id": aid,
                    "name": name,
                    "debit": debit,
                    "credit": credit,
                },
            )
        )

    if abs(total_debit - total_credit) > 0.01:
        return {
            "table_id": table.id,
            "model": "account.move",
            "created": 0,
            "updated": 0,
            "failed": 1,
            "skipped": 0,
            "ok": False,
            "message": (
                f"Trial balance not balanced: debit={total_debit:.2f} "
                f"credit={total_credit:.2f}"
            ),
        }

    vals = {
        "journal_id": int(journal["id"]),
        "ref": "Universal ingest — opening trial balance",
        "move_type": "entry",
        "line_ids": line_cmds,
    }
    # Prefer draft; never call action_post from ingest.
    if dry_run:
        return {
            "table_id": table.id,
            "model": "account.move",
            "created": 1,
            "updated": 0,
            "failed": 0,
            "skipped": 0,
            "ok": True,
            "message": (
                f"Dry-run: would create DRAFT opening entry "
                f"({len(line_cmds)} lines) on journal {journal.get('code')}"
            ),
        }

    kw: dict[str, Any] = {}
    if rpc_context:
        kw["context"] = dict(rpc_context)
    move_id = client.execute_kw("account.move", "create", [vals], kw)
    if isinstance(move_id, list):
        move_id = move_id[0]
    return {
        "table_id": table.id,
        "model": "account.move",
        "created": 1,
        "updated": 0,
        "failed": 0,
        "skipped": 0,
        "ok": True,
        "message": (
            f"Created DRAFT opening move id={move_id} "
            f"({len(line_cmds)} lines) — post manually in Odoo after review"
        ),
        "move_id": int(move_id),
    }


def _num(val: Any) -> float:
    if val is None or val == "":
        return 0.0
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return 0.0


__all__ = [
    "commit_opening_tb",
    "find_opening_journal",
    "resolve_account_id",
    "validate_opening_tb_table",
]
