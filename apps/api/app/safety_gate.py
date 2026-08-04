"""TRUST-2 — SafetyGate choke point for mutating API operations."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.account_models import Workspace
from app.db_models import DryRunReceipt, OdooConnection
from app.snapshots import ConfirmationRequired, require_advanced_confirmation

RiskClass = Literal["read", "reversible", "partially_reversible", "destructive", "code"]
ConfirmLevel = Literal["none", "simple", "phrase"]

RECEIPT_TTL_MINUTES = 15


@dataclass(frozen=True)
class SafetySpec:
    risk: RiskClass
    snapshot: bool = False
    dry_run_first: bool = False
    confirm: ConfirmLevel = "none"
    odoo_mutation: bool = True
    entitlement: str | None = None
    bypass_writes_paused: bool = False


@dataclass
class SafetyRefusal:
    code: str
    message: str
    options: list[str] = field(default_factory=list)

    def http_detail(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "options": self.options,
        }


class SafetyGateError(Exception):
    def __init__(self, refusal: SafetyRefusal) -> None:
        self.refusal = refusal
        super().__init__(refusal.message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def params_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SafetyGate:
    """Evaluate safety checks in order before mutating work proceeds."""

    def __init__(
        self,
        db: Session,
        *,
        connection: OdooConnection | None = None,
        workspace: Workspace | None = None,
    ) -> None:
        self.db = db
        self.connection = connection
        self.workspace = workspace

    def preflight(self, spec: SafetySpec) -> None:
        if not spec.bypass_writes_paused:
            self._check_writes_paused()
        if spec.odoo_mutation:
            self._check_write_mode()

    def _check_writes_paused(self) -> None:
        if self.workspace is not None and getattr(self.workspace, "writes_paused", False):
            raise SafetyGateError(
                SafetyRefusal(
                    code="writes_paused",
                    message="Workspace writes are paused by an administrator.",
                    options=["Resume writes from admin settings", "Contact workspace admin"],
                )
            )
        if self.connection is not None and getattr(self.connection, "writes_paused", False):
            raise SafetyGateError(
                SafetyRefusal(
                    code="writes_paused",
                    message="Writes are paused for this connection.",
                    options=["Resume writes on the connection overview", "Contact workspace admin"],
                )
            )

    def _check_write_mode(self) -> None:
        if self.connection is None:
            return
        mode = getattr(self.connection, "write_mode", "standard") or "standard"
        if mode == "observer":
            raise SafetyGateError(
                SafetyRefusal(
                    code="observer_mode",
                    message="Connection is in Observer mode — unlock write mode before mutating Odoo.",
                    options=["Enable standard write mode (admin+)", "Continue read-only analysis"],
                )
            )

    def check_confirm(
        self,
        spec: SafetySpec,
        *,
        confirm_advanced: bool,
        confirm_phrase: str | None,
        warning: str,
        risks: list[str],
    ) -> None:
        if spec.confirm == "none":
            return
        if spec.confirm == "simple" and confirm_advanced:
            return
        try:
            require_advanced_confirmation(
                confirm_advanced=confirm_advanced,
                confirm_phrase=confirm_phrase if spec.confirm == "phrase" else None,
                warning=warning,
                risks=risks,
            )
        except ConfirmationRequired as exc:
            raise SafetyGateError(
                SafetyRefusal(
                    code="confirmation_required",
                    message=exc.warning,
                    options=exc.risks,
                )
            ) from exc

    def issue_dry_run_receipt(
        self,
        *,
        connection_id: str,
        operation: str,
        params: dict[str, Any],
    ) -> str:
        token = str(uuid.uuid4())
        digest = params_fingerprint(params)
        row = DryRunReceipt(
            connection_id=connection_id,
            operation=operation,
            params_hash=digest,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            expires_at=_now() + timedelta(minutes=RECEIPT_TTL_MINUTES),
        )
        self.db.add(row)
        self.db.commit()
        return token

    def require_dry_run_receipt(
        self,
        spec: SafetySpec,
        *,
        connection_id: str,
        operation: str,
        params: dict[str, Any],
        receipt_token: str | None,
    ) -> None:
        if not spec.dry_run_first:
            return
        if not receipt_token:
            raise SafetyGateError(
                SafetyRefusal(
                    code="dry_run_receipt_required",
                    message="Run a dry-run with the same parameters first (within 15 minutes).",
                    options=["POST with dry_run=true, then retry with receipt_token"],
                )
            )
        digest = hashlib.sha256(receipt_token.encode("utf-8")).hexdigest()
        expected = params_fingerprint(params)
        row = (
            self.db.query(DryRunReceipt)
            .filter(
                DryRunReceipt.token_hash == digest,
                DryRunReceipt.connection_id == connection_id,
                DryRunReceipt.operation == operation,
            )
            .first()
        )
        if row is None or row.expires_at < _now() or row.params_hash != expected:
            raise SafetyGateError(
                SafetyRefusal(
                    code="dry_run_receipt_invalid",
                    message="Dry-run receipt is missing, expired, or parameters changed.",
                    options=["Re-run dry_run with identical parameters"],
                )
            )
        if row.used_at is not None:
            raise SafetyGateError(
                SafetyRefusal(
                    code="dry_run_receipt_invalid",
                    message="Dry-run receipt was already used.",
                    options=["Re-run dry_run with identical parameters"],
                )
            )
        row.used_at = _now()
        self.db.add(row)
        self.db.commit()
