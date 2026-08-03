"""Standalone approval process service — target Odoo x_approval_* models (CMP-10)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.approval_process_semantics import (
    LevelApproval,
    ProcessLevel,
    all_levels_satisfied,
    can_approve_at_level,
    dump_level_approvals,
    level_satisfied,
    parse_chain,
    parse_level_approvals,
    pending_level,
)
from app.ee_drivers import probe_enterprise_approvals_driver

ProcessEngine = Literal["community", "enterprise"]

TYPE_MODEL = "x_approval_type"
REQUEST_MODEL = "x_approval_request"


@dataclass(frozen=True)
class ProcessEngineInfo:
    engine: ProcessEngine
    enterprise_available: bool
    verify_state: str
    enterprise_note: str | None = None


def resolve_process_engine(client: OdooClient) -> ProcessEngineInfo:
    status = probe_enterprise_approvals_driver(client)
    if status.available:
        note = None
        if status.verify_state == "pending-live":
            note = "[SKIPPED-LIVE-VERIFY] Enterprise approval.request fields not fully verified."
        return ProcessEngineInfo(
            engine="enterprise",
            enterprise_available=True,
            verify_state=status.verify_state,
            enterprise_note=note,
        )
    return ProcessEngineInfo(
        engine="community",
        enterprise_available=False,
        verify_state=status.verify_state,
    )


def _user_group_ids(client: OdooClient, user_id: int) -> set[int]:
    rows = client.execute_kw("res.users", "read", [[user_id]], {"fields": ["groups_id"]})
    if not rows:
        return set()
    gids = rows[0].get("groups_id") or []
    return {int(g) for g in gids}


def _post_chatter(client: OdooClient, *, model: str, record_id: int, body: str) -> None:
    try:
        client.execute_kw(
            model,
            "message_post",
            [[record_id]],
            {"body": body, "message_type": "comment", "subtype_xmlid": "mail.mt_note"},
        )
    except OdooClientError:
        pass


def _create_activity(
    client: OdooClient,
    *,
    model: str,
    record_id: int,
    user_id: int,
    summary: str,
) -> int | None:
    try:
        types = client.execute_kw(
            "mail.activity.type",
            "search_read",
            [[]],
            {"fields": ["id"], "limit": 1},
        )
        if not types:
            return None
        act_id = client.execute_kw(
            "mail.activity",
            "create",
            [
                {
                    "activity_type_id": types[0]["id"],
                    "res_model": model,
                    "res_id": record_id,
                    "user_id": user_id,
                    "summary": summary,
                }
            ],
        )
        return int(act_id)
    except OdooClientError:
        return None


def _notify_level_approvers(
    client: OdooClient,
    *,
    request_id: int,
    level: ProcessLevel,
    subject: str,
) -> None:
    for uid in level.approver_user_ids:
        _create_activity(
            client,
            model=REQUEST_MODEL,
            record_id=request_id,
            user_id=uid,
            summary=f"Approve: {subject} (level {level.level})",
        )


def _read_type_chain(client: OdooClient, type_id: int) -> list[ProcessLevel]:
    row = client.execute_kw(
        TYPE_MODEL,
        "read",
        [[type_id]],
        {"fields": ["x_chain_json"]},
    )
    if not row:
        raise OdooClientError(f"Approval type {type_id} not found")
    return parse_chain(row[0].get("x_chain_json"))


def list_types(client: OdooClient, *, limit: int = 50) -> list[dict[str, Any]]:
    if not client.model_exists(TYPE_MODEL):
        return []
    rows = client.execute_kw(
        TYPE_MODEL,
        "search_read",
        [[]],
        {"fields": ["id", "x_name", "x_chain_json", "x_active"], "limit": limit, "order": "id desc"},
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        chain = parse_chain(row.get("x_chain_json"))
        out.append(
            {
                "id": int(row["id"]),
                "name": row.get("x_name"),
                "active": bool(row.get("x_active", True)),
                "levels": len(chain),
                "chain": [
                    {
                        "level": lv.level,
                        "min_approvals": lv.min_approvals,
                        "approver_user_ids": list(lv.approver_user_ids),
                        "approver_group_id": lv.approver_group_id,
                        "domain": lv.domain,
                    }
                    for lv in chain
                ],
            }
        )
    return out


def create_type(
    client: OdooClient,
    *,
    name: str,
    chain: list[dict[str, Any]],
) -> dict[str, Any]:
    if not client.model_exists(TYPE_MODEL):
        raise OdooClientError(f"{TYPE_MODEL} not installed — scaffold Approval Requests first")
    type_id = int(
        client.execute_kw(
            TYPE_MODEL,
            "create",
            [
                {
                    "x_name": name,
                    "x_chain_json": json.dumps(chain),
                    "x_active": True,
                }
            ],
        )
    )
    return {"id": type_id, "name": name, "chain": chain}


def list_requests(client: OdooClient, *, limit: int = 50) -> list[dict[str, Any]]:
    if not client.model_exists(REQUEST_MODEL):
        return []
    rows = client.execute_kw(
        REQUEST_MODEL,
        "search_read",
        [[]],
        {
            "fields": [
                "id",
                "x_name",
                "x_subject",
                "x_amount",
                "x_state",
                "x_current_level",
                "x_type_id",
                "x_requester_id",
            ],
            "limit": limit,
            "order": "id desc",
        },
    )
    return [_request_summary(r) for r in rows]


def _request_summary(row: dict[str, Any]) -> dict[str, Any]:
    type_id = row.get("x_type_id")
    requester = row.get("x_requester_id")
    return {
        "id": int(row["id"]),
        "name": row.get("x_name"),
        "subject": row.get("x_subject"),
        "amount": row.get("x_amount"),
        "state": row.get("x_state"),
        "current_level": row.get("x_current_level"),
        "type_id": int(type_id[0]) if isinstance(type_id, (list, tuple)) and type_id else type_id,
        "requester_id": int(requester[0])
        if isinstance(requester, (list, tuple)) and requester
        else requester,
    }


def _read_request(client: OdooClient, request_id: int) -> dict[str, Any]:
    rows = client.execute_kw(
        REQUEST_MODEL,
        "read",
        [[request_id]],
        {
            "fields": [
                "x_name",
                "x_subject",
                "x_amount",
                "x_state",
                "x_current_level",
                "x_type_id",
                "x_requester_id",
                "x_level_approvals_json",
            ]
        },
    )
    if not rows:
        raise OdooClientError(f"Request {request_id} not found")
    return rows[0]


def create_request(
    client: OdooClient,
    *,
    type_id: int,
    subject: str,
    amount: float,
    requester_id: int,
) -> dict[str, Any]:
    if not client.model_exists(REQUEST_MODEL):
        raise OdooClientError(f"{REQUEST_MODEL} not installed — scaffold Approval Requests first")
    req_id = int(
        client.execute_kw(
            REQUEST_MODEL,
            "create",
            [
                {
                    "x_type_id": type_id,
                    "x_subject": subject,
                    "x_amount": amount,
                    "x_requester_id": requester_id,
                    "x_state": "draft",
                    "x_current_level": 0,
                    "x_level_approvals_json": dump_level_approvals({}),
                }
            ],
        )
    )
    _post_chatter(client, model=REQUEST_MODEL, record_id=req_id, body=f"Request created: {subject}")
    return {"id": req_id, "state": "draft", "subject": subject}


def submit_request(client: OdooClient, *, request_id: int) -> dict[str, Any]:
    row = _read_request(client, request_id)
    state = str(row.get("x_state") or "")
    if state != "draft":
        raise OdooClientError(f"Only draft requests can be submitted (state={state!r})")
    type_id = row.get("x_type_id")
    if isinstance(type_id, (list, tuple)):
        type_id = type_id[0]
    chain = _read_type_chain(client, int(type_id))
    if not chain:
        raise OdooClientError("Approval type has no chain levels defined")
    pending = chain[0].level
    client.execute_kw(
        REQUEST_MODEL,
        "write",
        [
            [request_id],
            {
                "x_state": "submitted",
                "x_current_level": pending,
            },
        ],
    )
    subject = str(row.get("x_subject") or row.get("x_name") or request_id)
    _post_chatter(client, model=REQUEST_MODEL, record_id=request_id, body="Request submitted.")
    _notify_level_approvers(client, request_id=request_id, level=chain[0], subject=subject)
    return {"id": request_id, "state": "submitted", "current_level": pending}


def approve_request(
    client: OdooClient,
    *,
    request_id: int,
    actor_user_id: int,
) -> dict[str, Any]:
    row = _read_request(client, request_id)
    state = str(row.get("x_state") or "")
    if state != "submitted":
        raise OdooClientError(f"Cannot approve request in state {state!r}")
    type_id = row.get("x_type_id")
    if isinstance(type_id, (list, tuple)):
        type_id = type_id[0]
    chain = _read_type_chain(client, int(type_id))
    levels = parse_level_approvals(row.get("x_level_approvals_json"))
    pending = pending_level(chain, levels)
    if pending is None:
        raise OdooClientError("No pending approval level")
    level_def = next((lv for lv in chain if lv.level == pending), None)
    if level_def is None:
        raise OdooClientError(f"Unknown pending level {pending}")
    groups = _user_group_ids(client, actor_user_id)
    existing = levels.get(pending, [])
    ok, msg = can_approve_at_level(
        level=level_def,
        pending=pending,
        user_id=actor_user_id,
        user_group_ids=groups,
        existing=existing,
    )
    if not ok:
        raise PermissionError(msg)
    existing = existing + [LevelApproval(user_id=actor_user_id, status="approved")]
    levels[pending] = existing
    client.execute_kw(
        REQUEST_MODEL,
        "write",
        [[request_id], {"x_level_approvals_json": dump_level_approvals(levels)}],
    )
    _post_chatter(
        client,
        model=REQUEST_MODEL,
        record_id=request_id,
        body=f"Approved at level {pending} by user {actor_user_id}.",
    )
    if level_satisfied(level_def, existing):
        next_pending = pending_level(chain, levels)
        if next_pending is None and all_levels_satisfied(chain, levels):
            client.execute_kw(
                REQUEST_MODEL,
                "write",
                [[request_id], {"x_state": "approved", "x_current_level": 0}],
            )
            _post_chatter(client, model=REQUEST_MODEL, record_id=request_id, body="Request fully approved.")
            return {"id": request_id, "state": "approved", "level": pending}
        if next_pending is not None:
            client.execute_kw(
                REQUEST_MODEL,
                "write",
                [[request_id], {"x_current_level": next_pending}],
            )
            subject = str(row.get("x_subject") or "")
            next_lv = next((lv for lv in chain if lv.level == next_pending), None)
            if next_lv:
                _notify_level_approvers(
                    client, request_id=request_id, level=next_lv, subject=subject
                )
        return {"id": request_id, "state": "submitted", "level": pending, "advanced_to": next_pending}
    return {"id": request_id, "state": "submitted", "level": pending, "approvals": len(existing)}


def refuse_request(
    client: OdooClient,
    *,
    request_id: int,
    actor_user_id: int,
    reason: str = "",
) -> dict[str, Any]:
    row = _read_request(client, request_id)
    state = str(row.get("x_state") or "")
    if state != "submitted":
        raise OdooClientError(f"Cannot refuse request in state {state!r}")
    type_id = row.get("x_type_id")
    if isinstance(type_id, (list, tuple)):
        type_id = type_id[0]
    chain = _read_type_chain(client, int(type_id))
    levels = parse_level_approvals(row.get("x_level_approvals_json"))
    pending = pending_level(chain, levels)
    if pending is None:
        raise OdooClientError("No pending level to refuse")
    level_def = next((lv for lv in chain if lv.level == pending), None)
    if level_def is None:
        raise OdooClientError(f"Unknown pending level {pending}")
    groups = _user_group_ids(client, actor_user_id)
    ok, msg = can_approve_at_level(
        level=level_def,
        pending=pending,
        user_id=actor_user_id,
        user_group_ids=groups,
        existing=levels.get(pending, []),
    )
    if not ok:
        raise PermissionError(msg)
    levels[pending] = levels.get(pending, []) + [
        LevelApproval(user_id=actor_user_id, status="refused")
    ]
    client.execute_kw(
        REQUEST_MODEL,
        "write",
        [
            [request_id],
            {
                "x_state": "refused",
                "x_current_level": 0,
                "x_level_approvals_json": dump_level_approvals(levels),
            },
        ],
    )
    body = f"Refused at level {pending} by user {actor_user_id}."
    if reason:
        body += f" Reason: {reason}"
    _post_chatter(client, model=REQUEST_MODEL, record_id=request_id, body=body)
    return {"id": request_id, "state": "refused", "level": pending}


def seed_demo_type(client: OdooClient) -> int | None:
    from app.approval_requests_pack import DEFAULT_CHAIN

    if not client.model_exists(TYPE_MODEL):
        return None
    existing = client.execute_kw(TYPE_MODEL, "search_count", [[("x_name", "=", "Two-level demo")]])
    if int(existing) > 0:
        return None
    return int(
        client.execute_kw(
            TYPE_MODEL,
            "create",
            [
                {
                    "x_name": "Two-level demo",
                    "x_chain_json": json.dumps(DEFAULT_CHAIN),
                    "x_active": True,
                }
            ],
        )
    )
