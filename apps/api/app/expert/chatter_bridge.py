"""Read-only export: post Expert answers as Odoo internal notes (mail.message)."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from odoo_client.client import OdooClientError

from app.odoo_service import client_from_connection, get_connection_or_404


@dataclass
class ChatterPostResult:
    ok: bool
    message: str
    posted: bool = False


def _markdown_to_odoo_html(body: str) -> str:
    """Minimal markdown → safe HTML for message_post body."""
    text = body.strip()
    if not text:
        return ""
    escaped = html.escape(text)
    escaped = re.sub(
        r"\[(\d+)\]",
        r'<sup style="color:#714B67;">[\1]</sup>',
        escaped,
    )
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", escaped) if p.strip()]
    if not paragraphs:
        return f"<p>{escaped}</p>"
    return "".join(f"<p>{p.replace(chr(10), '<br/>')}</p>" for p in paragraphs)


def post_expert_note_to_chatter(
    db: Session,
    *,
    connection_id: str,
    model: str,
    res_id: int,
    body_markdown: str,
    subject: str = "Odoo Expert note",
    confirmed: bool = False,
) -> ChatterPostResult:
    """Post Expert answer as mail.mt_note on a record. Requires explicit confirmation."""
    if not confirmed:
        return ChatterPostResult(ok=False, message="Confirmation required to post to Odoo chatter.")
    model = (model or "").strip()
    if not model or res_id < 1:
        return ChatterPostResult(ok=False, message="Valid model and res_id are required.")
    body = (body_markdown or "").strip()
    if not body:
        return ChatterPostResult(ok=False, message="Empty body — nothing to post.")

    row = get_connection_or_404(db, connection_id)
    client = client_from_connection(row)
    html_body = _markdown_to_odoo_html(body)
    prefix = f"<p><strong>{html.escape(subject)}</strong></p>"
    try:
        client.execute_kw(
            model,
            "message_post",
            [[res_id]],
            {
                "body": prefix + html_body,
                "message_type": "comment",
                "subtype_xmlid": "mail.mt_note",
            },
        )
    except OdooClientError as exc:
        return ChatterPostResult(ok=False, message=f"Odoo message_post failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        return ChatterPostResult(ok=False, message=f"Unexpected error: {exc}")

    return ChatterPostResult(
        ok=True,
        posted=True,
        message=f"Logged Expert note on {model} #{res_id}.",
    )


__all__ = ["ChatterPostResult", "post_expert_note_to_chatter"]
