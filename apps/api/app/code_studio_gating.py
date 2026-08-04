"""DEV-1 — developer role + dev_tools entitlement + probe gating."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.account_service import can_develop
from app.code_studio_probe import parse_stored_probe, probe_code_server_actions, probe_supported
from app.db_models import OdooConnection
from app.entitlements import assert_feature
from app.odoo_service import OdooClientError, client_from_connection
from app.workspace_auth import WorkspaceAuth

MODULE_PATH_OPTIONS = [
    "Export Python as an installable module (Option A)",
    "Sandbox-test the module, then promote explicitly",
    "Use Automations → Python module export for scheduled logic",
]


def assert_developer_role(auth: WorkspaceAuth) -> None:
    if auth.mode != "accounts" or auth.api_key_authenticated or auth.is_superadmin:
        return
    role = auth.role or ""
    if not can_develop(role):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "developer_role_required",
                "message": "Code Studio requires the developer workspace role (granted by admin+).",
                "role": role,
            },
        )


def assert_code_studio_entitlement(db: Session, auth: WorkspaceAuth) -> None:
    workspace_id = auth.workspace_id if auth.workspace_scoped else None
    assert_feature(db, workspace_id, "dev_tools", auth)


def load_or_probe(
    db: Session,
    connection: OdooConnection,
    *,
    force: bool = False,
) -> dict[str, Any]:
    if not force:
        cached = parse_stored_probe(getattr(connection, "code_studio_probe_json", None))
        if cached is not None:
            return cached
    try:
        client = client_from_connection(connection)
        probe = probe_code_server_actions(client)
    except OdooClientError as exc:
        probe = {
            "key": "code_server_actions",
            "supported": False,
            "error": str(exc),
            "source": "error",
        }
    connection.code_studio_probe_json = json.dumps(probe)
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return probe


def code_studio_gate_payload(probe: dict[str, Any] | None) -> dict[str, Any]:
    supported = probe_supported(probe)
    if supported:
        return {
            "available": True,
            "capability_key": "code_server_actions",
            "title": "Live code server actions",
            "why": "This instance accepts state=code server actions via RPC.",
            "options": [],
        }
    reason = (probe or {}).get("error") or "Live code actions are not available on this instance."
    return {
        "available": False,
        "capability_key": "code_server_actions",
        "title": "Live code actions unavailable",
        "why": reason,
        "options": list(MODULE_PATH_OPTIONS),
    }


def assert_probe_available(probe: dict[str, Any] | None) -> None:
    if probe_supported(probe):
        return
    payload = code_studio_gate_payload(probe)
    raise HTTPException(
        status_code=409,
        detail={"gating": payload, "message": payload["title"]},
    )
