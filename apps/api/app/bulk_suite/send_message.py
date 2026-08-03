"""Threaded bulk chatter send — one message_post per record (BLK-7)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.transitions import BulkRunResult, BulkSuiteError, PerRecordResult, _load_display_names


class SendMessageValidationError(BulkSuiteError):
    pass


@dataclass
class SendMessageRunResult(BulkRunResult):
    mail_template_id: int | None = None
    subject: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["mail_template_id"] = self.mail_template_id
        data["subject"] = self.subject
        return data


def _model_supports_message_post(client: OdooClient, model: str) -> None:
    if not client.model_exists("mail.message"):
        raise SendMessageValidationError("mail module is not installed")
    fg = client.execute_kw(model, "fields_get", [], {"attributes": []})
    if "message_ids" not in fg:
        raise SendMessageValidationError(
            f"Model {model!r} has no message_ids — enable mail.thread mixin before bulk send."
        )


def _render_template(
    client: OdooClient,
    *,
    template_id: int,
    model: str,
    res_id: int,
) -> tuple[str | None, str]:
    try:
        subject_raw = client.execute_kw(
            "mail.template",
            "_render_field",
            [[template_id], "subject", [res_id]],
        )
        body_raw = client.execute_kw(
            "mail.template",
            "_render_field",
            [[template_id], "body_html", [res_id]],
        )
        subject = str(subject_raw) if subject_raw not in (None, False) else None
        body = str(body_raw or "")
        if body:
            return subject, body
    except OdooClientError:
        pass
    rows = client.execute_kw(
        "mail.template",
        "read",
        [[template_id]],
        {"fields": ["subject", "body_html"]},
    )
    if not rows:
        raise SendMessageValidationError(f"mail.template id={template_id} not found")
    row = rows[0]
    return (
        str(row.get("subject") or "") or None,
        str(row.get("body_html") or ""),
    )


def run_bulk_send_message(
    client: OdooClient,
    *,
    model: str,
    record_ids: list[int],
    body: str | None = None,
    subject: str | None = None,
    mail_template_id: int | None = None,
    dry_run: bool = True,
    run_id: str | None = None,
) -> SendMessageRunResult:
    run_id = run_id or str(uuid.uuid4())
    _model_supports_message_post(client, model)
    if not record_ids:
        raise SendMessageValidationError("No target records")

    if mail_template_id is None and not (body or "").strip():
        raise SendMessageValidationError("Provide body or mail_template_id")

    if mail_template_id is not None:
        rows = client.execute_kw(
            "mail.template",
            "read",
            [[int(mail_template_id)]],
            {"fields": ["model"]},
        )
        if not rows:
            raise SendMessageValidationError(f"mail.template id={mail_template_id} not found")
        tpl_model = rows[0].get("model")
        if tpl_model and str(tpl_model) != model:
            raise SendMessageValidationError(
                f"Template model {tpl_model!r} does not match target model {model!r}"
            )

    names = _load_display_names(client, model, record_ids)
    per_record: list[PerRecordResult] = []
    succeeded = 0
    failed = 0

    for rid in record_ids:
        label = names.get(rid, str(rid))
        msg_subject = subject
        msg_body = (body or "").strip()
        if mail_template_id is not None:
            try:
                msg_subject, msg_body = _render_template(
                    client,
                    template_id=int(mail_template_id),
                    model=model,
                    res_id=rid,
                )
            except SendMessageValidationError as exc:
                failed += 1
                per_record.append(
                    PerRecordResult(id=rid, display_name=label, ok=False, error=str(exc))
                )
                continue
        if not msg_body:
            failed += 1
            per_record.append(
                PerRecordResult(id=rid, display_name=label, ok=False, error="empty message body")
            )
            continue
        if dry_run:
            succeeded += 1
            per_record.append(
                PerRecordResult(id=rid, display_name=label, ok=True, error="dry-run")
            )
            continue
        kwargs: dict[str, Any] = {
            "body": msg_body,
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_comment",
        }
        if msg_subject:
            kwargs["subject"] = msg_subject
        try:
            client.execute_kw(model, "message_post", [[rid]], kwargs)
            succeeded += 1
            per_record.append(PerRecordResult(id=rid, display_name=label, ok=True))
        except Exception as exc:  # noqa: BLE001
            failed += 1
            per_record.append(
                PerRecordResult(id=rid, display_name=label, ok=False, error=str(exc))
            )

    return SendMessageRunResult(
        run_id=run_id,
        operation="bulk_send_message",
        model=model,
        total=len(record_ids),
        succeeded=succeeded,
        failed=failed,
        per_record=per_record,
        dry_run=dry_run,
        message=(
            f"Threaded send: {succeeded} ok, {failed} failed of {len(record_ids)}"
            if not dry_run
            else f"Dry-run: would message_post on {len(record_ids)} record(s)"
        ),
        mail_template_id=mail_template_id,
        subject=subject,
    )
