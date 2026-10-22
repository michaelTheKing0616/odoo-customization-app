"""Offline-queue flush. Every queued route claims through claim_db."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.offline.flush import FlushBody, apply_queued_flush
from app.offline.idempotency import claim_db
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired, require_advanced_confirmation

router = APIRouter(prefix="/offline", tags=["offline"])

PROMOTE_QUEUE_WARNING = (
    "A queued promote still requires a human confirm and is never flushed automatically."
)
PROMOTE_QUEUE_RISKS = [
    "Promote installs a module on the connection",
    "The offline queue will not flush promote without confirm_advanced",
]


def _require_promote_confirm(body: FlushBody) -> None:
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=PROMOTE_QUEUE_WARNING,
            risks=PROMOTE_QUEUE_RISKS,
        )
    except ConfirmationRequired as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "requires_confirmation": True,
                "warning": exc.warning,
                "risks": exc.risks,
                "confirm_phrase": CONFIRM_PHRASE,
            },
        ) from exc


@router.post("/flush")
def flush_queued(
    body: FlushBody,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    """Claim the ULID once, then record the effect. Does not write Odoo."""
    key = (idempotency_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="Idempotency-Key required")
    if body.kind == "promote":
        _require_promote_confirm(body)
    return claim_db(db, key, lambda: apply_queued_flush(body))
