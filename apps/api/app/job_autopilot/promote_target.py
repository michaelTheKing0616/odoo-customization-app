"""Human Promote of a sandbox-validated zip onto another connection.

Autopilot never runs on production. This step is the operator confirm.
"""

from __future__ import annotations

import base64

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.job_autopilot.sandbox_gate import classify_connection
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.promote import PromoteResult, promote_module_zip
from app.snapshots import CONFIRM_PHRASE, require_advanced_confirmation

PROMOTE_TO_WARNING = (
    "This installs a sandbox-validated module zip onto the TARGET connection. "
    "Job Autopilot does not run on the target. Production Autopilot stays refused; "
    "this human Promote is the only write path onto another database."
)
PROMOTE_TO_RISKS = [
    "Writes a custom module onto the target Odoo database",
    "Does not clone or dump a production database",
    "Does not replace UAT sign-off",
    "Scorecard 10.0 is ModuleSpec completeness, not go-live",
    "Stock-only jobs have no zip — refuse rather than fake a promote",
]


class PromoteToResult(BaseModel):
    ok: bool = False
    refused: bool = False
    refuse_reason: str | None = None
    source_connection_id: str
    target_connection_id: str
    target_kind: str = "unknown"
    module: str | None = None
    method: str | None = None
    message: str = ""
    confirm_phrase: str = CONFIRM_PHRASE


def _zip_from_b64(raw: str | None) -> bytes | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return base64.b64decode(raw, validate=False)
    except Exception:  # noqa: BLE001
        return None


def promote_to_connection(
    db: Session,
    *,
    source_connection_id: str,
    target_connection_id: str,
    zip_base64: str | None,
    confirm_advanced: bool = False,
    confirm_phrase: str | None = None,
) -> PromoteToResult:
    """Install zip from the Autopilot sandbox onto a different connection."""
    if source_connection_id == target_connection_id:
        return PromoteToResult(
            ok=False,
            refused=True,
            refuse_reason="Target must be a different connection than the Autopilot sandbox.",
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            message="Pick another connection. Promoting onto the same sandbox is a no-op.",
        )
    zip_bytes = _zip_from_b64(zip_base64)
    if not zip_bytes:
        return PromoteToResult(
            ok=False,
            refused=True,
            refuse_reason=(
                "No module zip. Stock-only jobs hand off the sandbox + UAT report; "
                "Autopilot will not invent a zip or write production."
            ),
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            message="Refuse module promote without a zip.",
        )
    try:
        source = get_connection_or_404(db, source_connection_id)
        target = get_connection_or_404(db, target_connection_id)
    except LookupError as exc:
        return PromoteToResult(
            ok=False,
            refused=True,
            refuse_reason=str(exc),
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            message=str(exc),
        )
    source_kind, _ = classify_connection(source)
    target_kind, _ = classify_connection(target)
    if target_kind == "observer":
        return PromoteToResult(
            ok=False,
            refused=True,
            refuse_reason="Observer targets cannot install modules.",
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            target_kind=target_kind,
            message="Observer refused.",
        )
    require_advanced_confirmation(
        confirm_advanced=confirm_advanced,
        confirm_phrase=confirm_phrase,
        warning=PROMOTE_TO_WARNING + f" Target kind={target_kind}. Source kind={source_kind}.",
        risks=PROMOTE_TO_RISKS,
    )
    try:
        client = client_from_connection(target)
    except OdooClientError as exc:
        return PromoteToResult(
            ok=False,
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            target_kind=target_kind,
            message=str(exc),
        )
    try:
        result: PromoteResult = promote_module_zip(client, zip_bytes)
    except Exception as exc:  # noqa: BLE001
        return PromoteToResult(
            ok=False,
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            target_kind=target_kind,
            message=str(exc),
        )
    return PromoteToResult(
        ok=bool(result.ok),
        source_connection_id=source_connection_id,
        target_connection_id=target_connection_id,
        target_kind=target_kind,
        module=result.module,
        method=result.method,
        message=result.message,
    )


__all__ = [
    "PROMOTE_TO_RISKS",
    "PROMOTE_TO_WARNING",
    "PromoteToResult",
    "promote_to_connection",
]
