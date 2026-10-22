"""A5 — every write uses the shared Run sheet rules.

One gate for record writes made from any page: the same money guard, approval rule and undo
point the suite's Run sheet uses. It adds guards only; it never changes what a write does.

    snap = guard_record_write(db, client, cid, model="res.partner", ids=[7], vals={...}, source="Record editor")
    client.execute_kw("res.partner", "write", [[7], vals])   # the caller's own write, unchanged

Undo goes through History like every other change (snapshot resource_type "record_values").
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

# The suite's own rules, reused rather than copied.
from app.suite_change import MONEY_ROUTE, NEVER_EDIT, money_route
from app.suite_setup import APPROVAL_THRESHOLD

RESOURCE_TYPE = "record_values"
# Accounting setup is configuration work: it may be imported, but always through approval.
ACCOUNTING_SETUP = {"account.account", "account.tax", "account.journal", "account.fiscal.position",
                    "account.fiscal.position.tax", "account.fiscal.position.account", "account.tax.group"}
# Posted money is never written from here.
MONEY_DOCUMENTS = {"account.move", "account.move.line", "account.payment", "account.bank.statement.line"}
MAX_UNDO_ROWS = 2000  # beyond this the undo point would be too big to keep; the write is refused, not left unprotected


class WriteRefused(Exception):
    """A guard said no. `code` is money_guard | too_many_for_undo."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class WriteNeedsApproval(Exception):
    def __init__(self, count: int, threshold: int) -> None:
        msg = f"This changes {count} records. Changes over {threshold} need a person to approve them first."
        super().__init__(msg)
        self.count = count
        self.threshold = threshold
        self.message = msg


def approval_threshold(db: Session, connection_id: str) -> int:
    """The database's own threshold from suite settings (same source as the Run sheet)."""
    try:
        from app.routers.suite import _policy

        return int(_policy(db, connection_id).get("approval_threshold") or APPROVAL_THRESHOLD)
    except Exception:  # noqa: BLE001 - settings unreadable: fall back to the shared default
        return APPROVAL_THRESHOLD


def write_hash(model: str, ids: list[int], vals: dict[str, Any]) -> str:
    import hashlib
    import json

    raw = json.dumps({"model": model, "ids": sorted(int(i) for i in ids), "vals": vals}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def approval_status(db: Session, request: Any, connection_id: str, *, model: str, ids: list[int], vals: dict[str, Any], source: str,
                    always: bool = False) -> bool:
    """Same approval rule as the Run sheet: over the threshold, someone else approves this exact change.

    True when approval is not needed or already granted. Otherwise files (or finds) the request in the
    approvals list and raises WriteNeedsApproval with its status.
    """
    threshold = approval_threshold(db, connection_id)
    if len(ids) <= threshold and not always:
        return True
    if always:
        self_approve(db, request, connection_id, model=model, ids=ids, vals=vals, source=source)
        return True
    from app.routers import suite as rs

    h = write_hash(model, ids, vals)
    found = rs.find_approval(db, connection_id, "shared_write", model, h)
    if found and found.get("status") == "approved":
        return True
    if not found or found.get("status") not in {"pending", "approved"}:
        rs.ask_approval(connection_id, db, request, "shared_write", model, h,
                        [f"{source}: change {len(ids)} {model} records", f"Fields: {', '.join(sorted(vals))[:200]}"])
    err = WriteNeedsApproval(len(ids), threshold)
    if always:
        err.message = f"Changes to accounting setup ({model}) need a person to approve them first."
    err.message += " We sent it to the approvals list; run it again once it is approved."
    raise err


def self_approve(db: Session, request: Any, connection_id: str, *, model: str, ids: list[int], vals: dict[str, Any], source: str) -> Any:
    """Accounting setup (CoA, taxes, journals, fiscal positions): the consultant asking approves it themselves.

    Recorded in History with who and when; other large changes keep the someone-else-approves rule.
    """
    from datetime import UTC, datetime

    from app.routers import suite as rs
    from app.snapshots import save_snapshot

    who = rs._who(request)
    name = str(who.get("email") or who.get("user_id") or "this login")
    when = datetime.now(UTC).isoformat(timespec="seconds")
    return save_snapshot(
        db, connection_id=connection_id, resource_type="self_approval",
        resource_key=f"{model}:{write_hash(model, ids, vals)[:16]}",
        label=f"{source}: accounting setup change ({model}) approved by {name}",
        payload={"model": model, "ids": [int(i) for i in ids][:200], "count": len(ids), "fields": sorted(vals),
                 "approved_by": name, "approved_by_id": who.get("user_id"), "approved_at": when, "source": source,
                 "kind": "self_approval"},
        reversible="no",
    )


def run_guards(db: Session, request: Any, connection_id: str, client: Any, *, model: str, ids: list[int],
               vals: dict[str, Any], source: str, undo: bool = True) -> Any:
    """All three shared guards for one write, as a route uses them. Returns the History snapshot (or None)."""
    check_record_write(model, ids, threshold=10**9, approved=True)
    approved = approval_status(db, request, connection_id, model=model, ids=ids, vals=vals, source=source,
                               always=is_accounting_setup(model))
    if not undo:
        return None
    return guard_record_write(db, client, connection_id, model=model, ids=ids, vals=vals, source=source, approved=approved)


def guard_one(db: Session, connection_id: str, client: Any, model: str, ids: list[int], vals: dict[str, Any], source: str) -> Any:
    """Single-record config/report writes: same guards, raised as plain HTTP errors."""
    try:
        if ids:
            return run_guards(db, None, connection_id, client, model=model, ids=[int(i) for i in ids], vals=vals, source=source)
        guard_record_create(db, connection_id, model=model, source=source)
        return None
    except (WriteRefused, WriteNeedsApproval) as exc:
        raise http_error(exc) from exc


def http_error(exc: Exception) -> Any:
    """Plain HTTP errors for the gate, shared by every route that uses it."""
    from fastapi import HTTPException

    if isinstance(exc, WriteRefused):
        return HTTPException(status_code=403, detail={"code": exc.code, "message": exc.message})
    if isinstance(exc, WriteNeedsApproval):
        return HTTPException(status_code=409, detail={"code": "needs_approval", "message": exc.message, "count": exc.count, "threshold": exc.threshold})
    raise exc


def check_record_write(model: str, ids: list[int], *, threshold: int, approved: bool) -> None:
    """Pure guard check (no I/O): money guard first, then the approval rule."""
    if model in MONEY_ROUTE:
        raise WriteRefused("money_guard", f"Refused by the money guard. {money_route(model)}")
    if len(ids) > MAX_UNDO_ROWS:
        raise WriteRefused("too_many_for_undo", f"This changes {len(ids)} records; Ingenium keeps undo for up to {MAX_UNDO_ROWS} at a time. Split it into smaller runs.")
    if len(ids) > threshold and not approved:
        raise WriteNeedsApproval(len(ids), threshold)


def guard_record_write(
    db: Session,
    client: Any,
    connection_id: str,
    *,
    model: str,
    ids: list[int],
    vals: dict[str, Any],
    source: str,
    approved: bool = False,
    threshold: int | None = None,
) -> Any:
    """Run the shared guards, then save the undo point (current values of the fields being written).

    Returns the History snapshot row. Raises WriteRefused / WriteNeedsApproval before anything is read
    or written when a guard says no.
    """
    ids = [int(i) for i in ids]
    check_record_write(model, ids, threshold=threshold if threshold is not None else approval_threshold(db, connection_id), approved=approved)
    fields = sorted(k for k in vals if k not in NEVER_EDIT)
    before: list[dict[str, Any]] = []
    if ids and fields:
        rows = client.execute_kw(model, "read", [ids], {"fields": fields}) or []
        for r in rows:
            before.append({k: _plain(r.get(k)) for k in ["id", *fields]})
    from app.snapshots import save_snapshot

    n = len(ids)
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type=RESOURCE_TYPE,
        resource_key=f"{model}:{','.join(map(str, ids[:20]))}{'…' if n > 20 else ''}",
        label=f"{source}: changed {n} {model} record{'s' if n != 1 else ''}",
        payload={"model": model, "op": "write", "fields": fields, "before": before, "source": source},
        reversible="yes" if before else "no",
    )


def guard_record_create(db: Session, connection_id: str, *, model: str, source: str) -> None:
    """Imports: posted money is refused; accounting setup goes through approval (see is_accounting_setup)."""
    if model in MONEY_DOCUMENTS or (model in MONEY_ROUTE and model not in ACCOUNTING_SETUP):
        raise WriteRefused("money_guard", f"Refused by the money guard. {money_route(model)}")


def is_accounting_setup(model: str) -> bool:
    return model in ACCOUNTING_SETUP


def read_before(client: Any, model: str, rid: int, vals: dict[str, Any]) -> dict[str, Any] | None:
    """Current values of the fields about to be written on one record (call just before the write)."""
    fields = sorted(k for k in vals if k not in NEVER_EDIT)
    if not fields:
        return None
    got = client.execute_kw(model, "read", [[int(rid)]], {"fields": fields}) or []
    return {k: _plain(got[0].get(k)) for k in ["id", *fields]} if got else None


def save_before_values(db: Session, connection_id: str, *, model: str, before: list[dict[str, Any]], source: str) -> Any:
    """Undo point for updates whose ids are only known mid-run (import upsert): old values per record."""
    from app.snapshots import save_snapshot

    if not before:
        return None
    return save_snapshot(
        db, connection_id=connection_id, resource_type=RESOURCE_TYPE,
        resource_key=f"{model}:{','.join(str(b['id']) for b in before[:20])}",
        label=f"{source}: updated {len(before)} {model} record{'s' if len(before) != 1 else ''}",
        payload={"model": model, "op": "write", "fields": sorted({k for b in before for k in b if k != 'id'}), "before": before, "source": source},
        reversible="yes",
    )


def record_created(db: Session, connection_id: str, *, model: str, ids: list[int], source: str) -> Any:
    from app.snapshots import save_snapshot

    ids = [int(i) for i in ids]
    return save_snapshot(
        db,
        connection_id=connection_id,
        resource_type=RESOURCE_TYPE,
        resource_key=f"{model}:{','.join(map(str, ids[:20]))}",
        label=f"{source}: added {len(ids)} {model} record{'s' if len(ids) != 1 else ''}",
        payload={"model": model, "op": "create", "ids": ids, "source": source},
        reversible="yes",
    )


def undo_record_values(client: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Put back what the snapshot saved. Records deleted since are skipped and reported."""
    model = str(payload["model"])
    if payload.get("op") == "create":
        ids = [int(i) for i in payload.get("ids") or []]
        alive = client.execute_kw(model, "search", [[("id", "in", ids)]], {"context": {"active_test": False}}) if ids else []
        if alive:
            client.execute_kw(model, "unlink", [list(alive)])
        return {"restored": RESOURCE_TYPE, "model": model, "removed": len(alive), "skipped": len(ids) - len(alive)}
    before = payload.get("before") or []
    ids = [int(r["id"]) for r in before]
    alive = set(client.execute_kw(model, "search", [[("id", "in", ids)]], {"context": {"active_test": False}}) or []) if ids else set()
    restored = 0
    for r in before:
        if int(r["id"]) not in alive:
            continue
        vals = {k: v for k, v in r.items() if k != "id"}
        if vals:
            client.execute_kw(model, "write", [[int(r["id"])], vals])
            restored += 1
    return {"restored": RESOURCE_TYPE, "model": model, "records": restored, "skipped": len(before) - restored}


def _plain(v: Any) -> Any:
    """many2one [id, name] -> id; x2many lists -> [(6, 0, ids)] so the value can be written back as is."""
    if isinstance(v, (list, tuple)):
        if len(v) == 2 and isinstance(v[0], int) and isinstance(v[1], str):
            return v[0]
        if all(isinstance(x, int) for x in v):
            return [(6, 0, list(v))]
    return v


__all__ = [
    "RESOURCE_TYPE",
    "WriteNeedsApproval",
    "WriteRefused",
    "ACCOUNTING_SETUP",
    "MONEY_DOCUMENTS",
    "approval_status",
    "is_accounting_setup",
    "guard_one",
    "self_approve",
    "read_before",
    "run_guards",
    "save_before_values",
    "approval_threshold",
    "http_error",
    "write_hash",
    "check_record_write",
    "guard_record_create",
    "guard_record_write",
    "record_created",
    "undo_record_values",
]
