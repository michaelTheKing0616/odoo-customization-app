"""Re-run the Option A authoring gate after a stock host app is installed.

No LLM. Zip stays locked until the gate passes. Promote stays human.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ai_conversation.refine import artifact_hash
from app.ai_conversation.session_store import get_session, session_to_dict, update_session
from app.ai_option_a_gate import (
    evaluate_authoring_gate,
    is_option_a_authored_draft,
    requires_authoring_gate,
)
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404


def run_option_a_reverify(
    db: Session,
    *,
    connection_id: str | None = None,
    session_id: str | None = None,
    draft: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = None
    payload_draft: dict[str, Any] = dict(draft or {})
    conn_id = (connection_id or "").strip() or None
    if session_id:
        row = get_session(db, session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="App Studio session not found")
        try:
            loaded = json.loads(row.artifact_json or "{}")
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict) and loaded:
            payload_draft = loaded
        conn_id = conn_id or row.connection_id

    if not isinstance(payload_draft, dict) or not payload_draft:
        raise HTTPException(status_code=409, detail="No draft artifact to re-verify")
    if not is_option_a_authored_draft(payload_draft) and not requires_authoring_gate(payload_draft):
        raise HTTPException(
            status_code=409,
            detail="Not an LLM-authored Option A draft — nothing to re-verify",
        )
    if not conn_id:
        raise HTTPException(status_code=422, detail="Pick a connection first")

    try:
        conn = get_connection_or_404(db, conn_id)
        client = client_from_connection(conn)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    major = 19
    raw = str(getattr(conn, "server_version", "") or "")
    if raw:
        try:
            major = int(raw.split(".")[0])
        except ValueError:
            major = 19

    payload = evaluate_authoring_gate(payload_draft, client=client, odoo_major=major)
    if row is not None:
        update_session(
            db,
            row,
            artifact=payload_draft,
            artifact_hash=artifact_hash(payload_draft),
        )

    out: dict[str, Any] = {
        "ok": payload.get("status") == "pass",
        "draft": payload_draft,
        "status": payload.get("status"),
        "findings": payload.get("findings") or [],
        "host_install": payload.get("host_install") or [],
        "message": (
            "Authoring gate passed — zip and sandbox unlocked."
            if payload.get("status") == "pass"
            else "Authoring gate still has findings. Zip stays locked. Promote stays human."
        ),
    }
    if row is not None:
        out["session"] = session_to_dict(row)
    return out
