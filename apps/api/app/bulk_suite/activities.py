"""Bulk mail.activity scheduling (BLK-6)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.transitions import (
    BulkRunResult,
    BulkSuiteError,
    PerRecordResult,
    _load_display_names,
    resolve_record_ids,
)


class ActivityValidationError(BulkSuiteError):
    """Invalid bulk activity scheduling input."""


@dataclass
class ActivityProbeResult:
    major: int | None
    mail_installed: bool
    supports_model: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "major": self.major,
            "mail_installed": self.mail_installed,
            "supports_model": self.supports_model,
            "message": self.message,
        }


def probe_activity_model(client: OdooClient, model: str) -> ActivityProbeResult:
    major = getattr(getattr(client, "capabilities", None), "major", None)
    if not client.model_exists("mail.activity"):
        return ActivityProbeResult(
            major=major,
            mail_installed=False,
            supports_model=False,
            message="mail module is not installed — activities unavailable",
        )
    try:
        fg = client.execute_kw(model, "fields_get", [], {"attributes": []})
    except OdooClientError as exc:
        return ActivityProbeResult(
            major=major,
            mail_installed=True,
            supports_model=False,
            message=f"Model {model!r} is not available: {exc}",
        )
    if "activity_ids" not in fg:
        return ActivityProbeResult(
            major=major,
            mail_installed=True,
            supports_model=False,
            message=(
                f"Model {model!r} does not expose activity_ids — enable mail.activity.mixin "
                "(ir.model is_mail_activity) or use a mail.activity.mixin model."
            ),
        )
    return ActivityProbeResult(
        major=major,
        mail_installed=True,
        supports_model=True,
        message=f"Model {model!r} supports mail.activity scheduling.",
    )


def ensure_activity_ready(client: OdooClient, model: str) -> None:
    probe = probe_activity_model(client, model)
    if probe.supports_model:
        return
    if probe.mail_installed and model.startswith("x_"):
        try:
            if hasattr(client, "ensure_mail_mixins"):
                client.ensure_mail_mixins(model)
                probe = probe_activity_model(client, model)
        except OdooClientError as exc:
            raise ActivityValidationError(
                f"{probe.message} (tried ensure_mail_mixins: {exc})"
            ) from exc
    if not probe.supports_model:
        raise ActivityValidationError(probe.message)


def run_bulk_activities(
    client: OdooClient,
    *,
    model: str,
    record_ids: list[int],
    activity_type_id: int,
    summary: str,
    date_deadline: str,
    user_id: int | None = None,
    dry_run: bool = True,
    run_id: str | None = None,
) -> BulkRunResult:
    run_id = run_id or str(uuid.uuid4())
    ensure_activity_ready(client, model)
    model_id = client._model_id(model)

    if not summary.strip():
        raise ActivityValidationError("summary is required")
    if not date_deadline.strip():
        raise ActivityValidationError("date_deadline is required")

    type_rows = client.execute_kw(
        "mail.activity.type",
        "read",
        [[int(activity_type_id)]],
        {"fields": ["name"]},
    )
    if not type_rows:
        raise ActivityValidationError(f"activity_type_id={activity_type_id} not found")

    names = _load_display_names(client, model, record_ids)
    per_record: list[PerRecordResult] = []
    succeeded = 0
    failed = 0

    for rid in record_ids:
        label = names.get(rid, str(rid))
        vals: dict[str, Any] = {
            "res_model_id": model_id,
            "res_id": rid,
            "activity_type_id": int(activity_type_id),
            "summary": summary.strip(),
            "date_deadline": date_deadline.strip(),
        }
        if user_id is not None:
            vals["user_id"] = int(user_id)
        if dry_run:
            per_record.append(
                PerRecordResult(id=rid, display_name=label, ok=True, error="dry-run")
            )
            succeeded += 1
            continue
        try:
            client.execute_kw("mail.activity", "create", [vals])
            per_record.append(PerRecordResult(id=rid, display_name=label, ok=True))
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            per_record.append(
                PerRecordResult(id=rid, display_name=label, ok=False, error=str(exc))
            )

    return BulkRunResult(
        run_id=run_id,
        operation="bulk_activities",
        model=model,
        total=len(record_ids),
        succeeded=succeeded,
        failed=failed,
        per_record=per_record,
        dry_run=dry_run,
        message=(
            f"Bulk activities: {succeeded} ok, {failed} failed of {len(record_ids)}"
            if not dry_run
            else f"Dry-run: would schedule {len(record_ids)} activit(y/ies)"
        ),
    )
