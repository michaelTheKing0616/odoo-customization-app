"""Approval rules service — Community engine + Studio delegation (CMP-5)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from odoo_client import OdooClient
from odoo_client.client import OdooClientError
from odoo_client.view_arch import render_inherit_xpath_arch
from sqlalchemy.orm import Session

from app.approval_semantics import (
    ApprovalEntryState,
    all_steps_approved,
    can_approve_step,
    parse_steps,
    pending_step_order,
)
from app.db_models import ApprovalEntry, ApprovalRule
from app.ee_drivers import (
    create_approval_rule as studio_create_rule,
    delete_approval_rule as studio_delete_rule,
    probe_approval_rules_driver,
    update_approval_rule as studio_update_rule,
)
from app.snapshots import snapshot_view

EngineKind = Literal["community", "studio"]


@dataclass(frozen=True)
class EngineInfo:
    engine: EngineKind
    studio_available: bool
    studio_verify_state: str
    community_available: bool = True


def resolve_engine(client: OdooClient) -> EngineInfo:
    status = probe_approval_rules_driver(client)
    if status.available:
        return EngineInfo(
            engine="studio",
            studio_available=True,
            studio_verify_state=status.verify_state,
        )
    return EngineInfo(
        engine="community",
        studio_available=False,
        studio_verify_state=status.verify_state,
    )


def _config_param_key(rule_id: str, record_id: int) -> str:
    return f"odoo_custom.approval.{rule_id}.{record_id}"


def _entry_states(entries: list[ApprovalEntry]) -> list[ApprovalEntryState]:
    return [
        ApprovalEntryState(
            step_order=e.step_order,
            status=e.status,  # type: ignore[arg-type]
            approver_user_id=e.approver_user_id,
        )
        for e in entries
    ]


def _user_group_ids(client: OdooClient, user_id: int) -> set[int]:
    rows = client.execute_kw("res.users", "read", [[user_id]], {"fields": ["groups_id"]})
    if not rows:
        return set()
    gids = rows[0].get("groups_id") or []
    return {int(g) for g in gids}


def _record_matches_domain(client: OdooClient, model: str, record_id: int, domain: str | None) -> bool:
    if not domain:
        return True
    try:
        extra = eval(domain) if isinstance(domain, str) else domain  # noqa: S307
        if not isinstance(extra, list):
            return True
        full = extra + [("id", "=", record_id)]
        count = client.execute_kw(model, "search_count", [full])
        return int(count) > 0
    except Exception:  # noqa: BLE001
        return True


def _sync_odoo_param(
    client: OdooClient,
    *,
    rule_id: str,
    record_id: int,
    payload: dict[str, Any],
) -> None:
    key = _config_param_key(rule_id, record_id)
    client.execute_kw(
        "ir.config_parameter",
        "set_param",
        [key, json.dumps(payload)],
    )


def _post_chatter(
    client: OdooClient,
    *,
    model: str,
    record_id: int,
    body: str,
) -> None:
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


def list_rules(db: Session, connection_id: str) -> list[ApprovalRule]:
    return (
        db.query(ApprovalRule)
        .filter(ApprovalRule.connection_id == connection_id)
        .order_by(ApprovalRule.created_at.desc())
        .all()
    )


def get_rule(db: Session, connection_id: str, rule_id: str) -> ApprovalRule | None:
    return (
        db.query(ApprovalRule)
        .filter(ApprovalRule.connection_id == connection_id, ApprovalRule.id == rule_id)
        .first()
    )


def create_rule(
    db: Session,
    client: OdooClient,
    *,
    connection_id: str,
    name: str,
    target_model: str,
    button_method: str,
    button_label: str | None,
    steps: list[dict[str, Any]],
    engine: EngineKind | None = None,
) -> ApprovalRule:
    info = resolve_engine(client)
    use_engine = engine or info.engine
    steps_json = json.dumps(steps)

    studio_rule_id: int | None = None
    if use_engine == "studio":
        payload: dict[str, Any] = {"name": name, "active": True}
        if steps:
            first = steps[0]
            if first.get("approver_user_ids"):
                payload["user_ids"] = first["approver_user_ids"]
            if first.get("approver_group_id") or first.get("group_id"):
                payload["group_id"] = first.get("approver_group_id") or first.get("group_id")
            if first.get("domain"):
                payload["domain"] = first["domain"]
        studio_rule_id, _ = studio_create_rule(client, payload)

    row = ApprovalRule(
        id=str(uuid.uuid4()),
        connection_id=connection_id,
        engine=use_engine,
        name=name,
        target_model=target_model,
        button_method=button_method,
        button_label=button_label,
        steps_json=steps_json,
        odoo_studio_rule_id=studio_rule_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_rule(
    db: Session,
    client: OdooClient,
    row: ApprovalRule,
    *,
    name: str | None = None,
    steps: list[dict[str, Any]] | None = None,
    active: bool | None = None,
) -> ApprovalRule:
    if name is not None:
        row.name = name
    if steps is not None:
        row.steps_json = json.dumps(steps)
    if active is not None:
        row.active = active
    if row.engine == "studio" and row.odoo_studio_rule_id:
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if active is not None:
            payload["active"] = active
        if payload:
            studio_update_rule(client, row.odoo_studio_rule_id, payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_rule(db: Session, client: OdooClient, row: ApprovalRule) -> None:
    if row.engine == "studio" and row.odoo_studio_rule_id:
        studio_delete_rule(client, row.odoo_studio_rule_id)
    db.delete(row)
    db.commit()


def _wrapper_code(*, rule_id: str, original_method: str) -> str:
    return f"""
record = records[:1]
if not record:
    raise UserError("No record selected")
import json
ICP = env['ir.config_parameter'].sudo()
key = 'odoo_custom.approval.{rule_id}.' + str(record.id)
raw = ICP.get_param(key) or '{{}}'
state = json.loads(raw)
if state.get('status') != 'approved':
    raise UserError(state.get('message') or 'Approval required before this action.')
getattr(record, '{original_method}')()
""".strip()


def deploy_community_rule(
    db: Session,
    client: OdooClient,
    *,
    connection_id: str,
    row: ApprovalRule,
) -> ApprovalRule:
    if row.engine != "community":
        raise ValueError("Deploy applies to Community engine rules only")
    model_id = client.execute_kw(
        "ir.model",
        "search",
        [[("model", "=", row.target_model)]],
        {"limit": 1},
    )
    if not model_id:
        raise OdooClientError(f"Model {row.target_model} not found")
    code = _wrapper_code(rule_id=row.id, original_method=row.button_method)
    action_id = int(
        client.execute_kw(
            "ir.actions.server",
            "create",
            [
                {
                    "name": f"Approval gate: {row.name}",
                    "model_id": model_id[0],
                    "binding_model_id": model_id[0],
                    "binding_type": "action",
                    "state": "code",
                    "code": code,
                }
            ],
        )
    )
    primary = client.execute_kw(
        "ir.ui.view",
        "search_read",
        [[("model", "=", row.target_model), ("type", "=", "form")]],
        {"fields": ["id", "arch_db"], "limit": 1, "order": "priority asc, id asc"},
    )
    if not primary:
        raise OdooClientError(f"No form view for {row.target_model}")
    view_id = int(primary[0]["id"])
    snapshot_view(db, connection_id, client, view_id)
    inherit_arch = render_inherit_xpath_arch(
        expr=f"//button[@name='{row.button_method}']",
        position="attributes",
        body_xml=f'<attribute name="type">action</attribute><attribute name="name">{action_id}</attribute>',
    )
    inherit_id = int(
        client.execute_kw(
            "ir.ui.view",
            "create",
            [
                {
                    "name": f"approval.gate.{row.id[:8]}",
                    "model": row.target_model,
                    "type": "form",
                    "inherit_id": view_id,
                    "mode": "extension",
                    "arch": inherit_arch,
                }
            ],
        )
    )
    row.deployed = True
    row.odoo_wrapper_action_id = action_id
    row.odoo_view_inherit_id = inherit_id
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def check_action(
    db: Session,
    client: OdooClient,
    *,
    row: ApprovalRule,
    record_id: int,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    steps = parse_steps(row.steps_json)
    entries = (
        db.query(ApprovalEntry)
        .filter(
            ApprovalEntry.rule_id == row.id,
            ApprovalEntry.record_model == row.target_model,
            ApprovalEntry.record_id == record_id,
        )
        .all()
    )
    states = _entry_states(entries)
    if all_steps_approved(steps, states):
        _sync_odoo_param(
            client,
            rule_id=row.id,
            record_id=record_id,
            payload={"status": "approved", "message": "All steps approved"},
        )
        return {"allowed": True, "message": "All approval steps complete", "pending_step": None}

    pending = pending_step_order(steps, states)
    if pending is None:
        return {"allowed": False, "message": "Approval rejected or blocked", "pending_step": None}

    existing_pending = next(
        (e for e in entries if e.step_order == pending and e.status == "pending"),
        None,
    )
    if existing_pending:
        return {
            "allowed": False,
            "message": existing_pending.message or f"Approval pending (step {pending})",
            "pending_step": pending,
            "entry_id": existing_pending.id,
        }

    step = next((s for s in steps if s.order == pending), None)
    if step is None:
        return {"allowed": False, "message": "No matching step", "pending_step": pending}

    if not _record_matches_domain(client, row.target_model, record_id, step.domain):
        return {"allowed": True, "message": "Step condition not met — action allowed", "pending_step": None}

    msg = f"Approval required (step {pending}) before '{row.button_method}'"
    _sync_odoo_param(
        client,
        rule_id=row.id,
        record_id=record_id,
        payload={"status": "pending", "message": msg, "pending_step": pending},
    )
    _post_chatter(
        client,
        model=row.target_model,
        record_id=record_id,
        body=f"<p>Approval requested: {row.name} (step {pending})</p>",
    )
    approver_id = step.approver_user_ids[0] if step.approver_user_ids else (actor_user_id or 2)
    activity_id = _create_activity(
        client,
        model=row.target_model,
        record_id=record_id,
        user_id=approver_id,
        summary=f"Approve: {row.name}",
    )
    entry = ApprovalEntry(
        id=str(uuid.uuid4()),
        connection_id=row.connection_id,
        rule_id=row.id,
        record_model=row.target_model,
        record_id=record_id,
        step_order=pending,
        status="pending",
        activity_id=activity_id,
        message=msg,
    )
    db.add(entry)
    db.commit()
    return {"allowed": False, "message": msg, "pending_step": pending, "entry_id": entry.id}


def resolve_entry(
    db: Session,
    client: OdooClient,
    *,
    entry: ApprovalEntry,
    approve: bool,
    actor_user_id: int,
) -> ApprovalEntry:
    rule = db.get(ApprovalRule, entry.rule_id)
    if rule is None:
        raise LookupError("Rule not found")
    steps = parse_steps(rule.steps_json)
    step = next((s for s in steps if s.order == entry.step_order), None)
    if step is None:
        raise ValueError("Step not found on rule")

    prior = (
        db.query(ApprovalEntry)
        .filter(
            ApprovalEntry.rule_id == rule.id,
            ApprovalEntry.record_model == entry.record_model,
            ApprovalEntry.record_id == entry.record_id,
        )
        .all()
    )
    ok, reason = can_approve_step(
        step=step,
        user_id=actor_user_id,
        user_group_ids=_user_group_ids(client, actor_user_id),
        entries=_entry_states(prior),
        all_steps=steps,
    )
    if not ok:
        raise PermissionError(reason)

    entry.status = "approved" if approve else "rejected"
    entry.approver_user_id = actor_user_id
    entry.resolved_at = datetime.now(timezone.utc)
    entry.message = "Approved" if approve else "Rejected"
    db.add(entry)
    db.commit()
    db.refresh(entry)

    merged = [e for e in prior if e.id != entry.id] + [entry]
    verb = "approved" if approve else "rejected"
    _post_chatter(
        client,
        model=entry.record_model,
        record_id=entry.record_id,
        body=f"<p>Approval step {entry.step_order} {verb} by user {actor_user_id}</p>",
    )

    if approve and all_steps_approved(steps, _entry_states(merged)):
        _sync_odoo_param(
            client,
            rule_id=rule.id,
            record_id=entry.record_id,
            payload={"status": "approved", "message": "All steps approved"},
        )
    elif not approve:
        _sync_odoo_param(
            client,
            rule_id=rule.id,
            record_id=entry.record_id,
            payload={"status": "rejected", "message": "Approval rejected"},
        )
    db.refresh(entry)
    return entry


def list_entries(db: Session, connection_id: str, *, rule_id: str | None = None) -> list[ApprovalEntry]:
    q = db.query(ApprovalEntry).filter(ApprovalEntry.connection_id == connection_id)
    if rule_id:
        q = q.filter(ApprovalEntry.rule_id == rule_id)
    return q.order_by(ApprovalEntry.created_at.desc()).limit(200).all()
