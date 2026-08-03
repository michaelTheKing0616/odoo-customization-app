"""Pure approval step semantics (CMP-5 Community engine)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

EntryStatus = Literal["pending", "approved", "rejected"]


@dataclass(frozen=True)
class ApprovalStep:
    order: int
    approver_user_ids: tuple[int, ...] = ()
    approver_group_id: int | None = None
    exclusive: bool = False
    domain: str | None = None


@dataclass(frozen=True)
class ApprovalEntryState:
    step_order: int
    status: EntryStatus
    approver_user_id: int | None = None


def parse_steps(raw: str | list[Any]) -> list[ApprovalStep]:
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, list):
        return []
    out: list[ApprovalStep] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        users = row.get("approver_user_ids") or row.get("user_ids") or []
        if not isinstance(users, list):
            users = []
        out.append(
            ApprovalStep(
                order=int(row.get("order") or row.get("notification_order") or len(out) + 1),
                approver_user_ids=tuple(int(u) for u in users if u is not None),
                approver_group_id=int(row["approver_group_id"])
                if row.get("approver_group_id") is not None
                else (int(row["group_id"]) if row.get("group_id") is not None else None),
                exclusive=bool(row.get("exclusive") or row.get("exclusive_user")),
                domain=str(row["domain"]).strip() if row.get("domain") else None,
            )
        )
    return sorted(out, key=lambda s: s.order)


def step_applies_to_user(step: ApprovalStep, *, user_id: int, user_group_ids: set[int]) -> bool:
    if user_id in step.approver_user_ids:
        return True
    if step.approver_group_id is not None and step.approver_group_id in user_group_ids:
        return True
    if not step.approver_user_ids and step.approver_group_id is None:
        return False
    return False


def exclusive_violation(
    *,
    step: ApprovalStep,
    user_id: int,
    entries: list[ApprovalEntryState],
    all_steps: list[ApprovalStep],
) -> bool:
    for entry in entries:
        if entry.status != "approved" or entry.approver_user_id != user_id:
            continue
        approved_step = next((s for s in all_steps if s.order == entry.step_order), None)
        if approved_step and approved_step.exclusive and step.order != entry.step_order:
            return True
    if step.exclusive:
        other_orders = {
            e.step_order
            for e in entries
            if e.status == "approved" and e.approver_user_id == user_id
        }
        if other_orders and step.order not in other_orders:
            return True
    return False


def pending_step_order(
    steps: list[ApprovalStep],
    entries: list[ApprovalEntryState],
) -> int | None:
    if not steps:
        return None
    approved_orders = {e.step_order for e in entries if e.status == "approved"}
    for step in steps:
        if step.order not in approved_orders:
            rejected = any(e.step_order == step.order and e.status == "rejected" for e in entries)
            if rejected:
                return None
            return step.order
    return None


def all_steps_approved(steps: list[ApprovalStep], entries: list[ApprovalEntryState]) -> bool:
    if not steps:
        return True
    approved = {e.step_order for e in entries if e.status == "approved"}
    return all(s.order in approved for s in steps)


def can_approve_step(
    *,
    step: ApprovalStep,
    user_id: int,
    user_group_ids: set[int],
    entries: list[ApprovalEntryState],
    all_steps: list[ApprovalStep],
) -> tuple[bool, str]:
    if not step_applies_to_user(step, user_id=user_id, user_group_ids=user_group_ids):
        return False, "User is not an approver for this step"
    if exclusive_violation(step=step, user_id=user_id, entries=entries, all_steps=all_steps):
        return False, "Exclusive approval — you already approved another step on this record"
    pending = pending_step_order(all_steps, entries)
    if pending is None:
        return False, "Approval was rejected or no pending step"
    if step.order != pending:
        return False, f"Step {pending} must be approved first (ordered steps)"
    return True, "OK"
