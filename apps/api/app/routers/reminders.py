"""Reminder wizard — create mail.template + optional ir.cron (no raw XML)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import ReminderCreateBody, ReminderCreateOut
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)

router = APIRouter(
    prefix="/connections/{connection_id}/reminders", tags=["reminders"]
)


def _confirm_http(exc: ConfirmationRequired) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "requires_confirmation": True,
            "confirm_phrase": CONFIRM_PHRASE,
            "warning": exc.warning,
            "risks": exc.risks,
        },
    )


@router.post("", response_model=ReminderCreateOut)
def create_reminder(
    connection_id: str,
    body: ReminderCreateBody,
    db: Session = Depends(get_db),
) -> ReminderCreateOut:
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                "Creates a mail.template and optionally an ir.cron on the live Odoo "
                "database. Emails may be queued depending on outgoing mail config."
            ),
            risks=[
                "Live mail.template write",
                "Scheduled code cron may email many records",
                "Requires mail module and valid email_to expression",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    try:
        conn = get_connection_or_404(db, connection_id)
        client = client_from_connection(conn)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not client.model_exists(body.model):
        raise HTTPException(status_code=422, detail=f"Model {body.model} not found")
    if not client.field_exists(body.model, body.date_field):
        raise HTTPException(
            status_code=422,
            detail=f"Field {body.model}.{body.date_field} not found",
        )

    mode = body.mode.strip().lower()
    if mode not in {"overdue", "due_soon"}:
        raise HTTPException(status_code=422, detail="mode must be overdue|due_soon")

    warnings: list[str] = []
    subject = body.subject or (
        f"{'Overdue' if mode == 'overdue' else 'Due soon'}: {{{{ object.display_name }}}}"
    )
    if body.body_html:
        body_html = body.body_html
    elif mode == "overdue":
        body_html = (
            f"<p>Record is overdue based on <strong>{body.date_field}</strong>.</p>"
            f"<p>Please take action.</p>"
        )
    else:
        body_html = (
            f"<p>Record is due within {body.due_soon_days} day(s) "
            f"(field <strong>{body.date_field}</strong>).</p>"
        )

    try:
        client.ensure_module_installed("mail")
        tpl_id = client.create_mail_template(
            name=body.name,
            model=body.model,
            subject=subject,
            body_html=body_html,
            email_to=body.email_to,
            description=f"Reminder wizard ({mode}) on {body.date_field}",
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cron_id: int | None = None
    if body.create_cron:
        if mode == "overdue":
            code = (
                "today = fields.Date.context_today(model)\n"
                f"template = env['mail.template'].browse({tpl_id})\n"
                "if template:\n"
                f"    recs = model.search([('{body.date_field}', '<', today)])\n"
                "    for rec in recs:\n"
                "        template.send_mail(rec.id, force_send=False)\n"
            )
        else:
            code = (
                "from datetime import timedelta\n"
                "today = fields.Date.context_today(model)\n"
                f"soon = today + timedelta(days={body.due_soon_days})\n"
                f"template = env['mail.template'].browse({tpl_id})\n"
                "if template:\n"
                f"    recs = model.search([\n"
                f"        ('{body.date_field}', '>=', today),\n"
                f"        ('{body.date_field}', '<=', soon),\n"
                "    ])\n"
                "    for rec in recs:\n"
                "        template.send_mail(rec.id, force_send=False)\n"
            )
        try:
            cron_id = client.create_cron(
                name=f"{body.name} (cron)",
                model=body.model,
                code=code,
                interval_number=body.interval_number,
                interval_type=body.interval_type,
                active=True,
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Cron not created: {exc}")

    return ReminderCreateOut(
        ok=True,
        mail_template_id=tpl_id,
        cron_id=cron_id,
        message=(
            f"Created mail template {tpl_id}"
            + (f" and cron {cron_id}" if cron_id else " (no cron)")
        ),
        warnings=warnings,
    )
