"""Community trigger firings. Existence is not approval.

Each firing submits a new plan card through the existing inbox. The card
stays pending until a later approve call for that plan hash. Apply is a
separate function and it refuses to call the executor without the approval
id for that same firing.

Bucket C sources are not built here. This module does not enable L4 and it
does not publish.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.audit_chain import append_entry
from app.changeset import executor
from app.changeset.inbox import Inbox
from app.changeset.protected_registry import deny_models, protected_denial
from app.mcp_guard import trigger_is_not_approval

# Community `base.automation` trigger values. Studio models are not a host.
_COMMUNITY_TRIGGERS = frozenset(
    {
        "on_change",
        "on_create",
        "on_create_or_write",
        "on_priority_set",
        "on_stage_set",
        "on_state_set",
        "on_tag_set",
        "on_time",
        "on_time_created",
        "on_time_updated",
        "on_unlink",
        "on_user_set",
        "on_webhook",
        "on_write",
    }
)
_HOST_MODEL = "base.automation"

_FIRINGS: dict[str, _FiringRecord] = {}


class TriggerGateError(Exception):
    """A firing stopped before apply."""


class ProtectedModelBlocked(TriggerGateError):
    """The trigger targets a protected model."""


class EnterpriseTriggerRefused(TriggerGateError):
    """The trigger is not a Community base.automation trigger."""


class ApprovalRequired(TriggerGateError):
    """This firing has no matching approval id."""


class TriggerRejected(TriggerGateError):
    """The inbox refused the firing's change-set."""


@dataclass(frozen=True, slots=True)
class CommunityTrigger:
    """One Community automation. `record_id` means the row already exists.

    Inputs: name, the model the automation watches, a Community trigger
    value, the change-set the firing will submit, the existing form, and the
    optional existing row id.
    A set `record_id` is not an approval.
    """

    name: str
    target_model: str
    trigger: str
    changeset: tuple[dict[str, Any], ...]
    host_model: str = _HOST_MODEL
    record_id: int | None = None


@dataclass(frozen=True, slots=True)
class Firing:
    """The plan card opened by one firing. Approval is still empty."""

    firing_id: str
    plan_hash: str
    status: str
    approval_id: None
    trigger: str
    person: str


@dataclass
class _FiringRecord:
    firing_id: str
    trigger_name: str
    person: str
    card: dict[str, Any]
    changeset: list[dict[str, Any]]
    inbox: Inbox
    connection_id: str
    environment: str
    approval_id: str | None = None


def community_trigger(
    *,
    name: str,
    target_model: str,
    trigger: str,
    changeset: list[dict[str, Any]],
    host_model: str = _HOST_MODEL,
    record_id: int | None = None,
) -> CommunityTrigger:
    """Build a Community trigger backed by base.automation.

    Inputs: trigger name, watched model, Community trigger value, change-set,
    existing form, and optional existing automation id.
    Output: a CommunityTrigger. The host is base.automation.
    Side effects: none. Does not call Odoo and does not write an audit row.
    Raises EnterpriseTriggerRefused when the host or trigger is not Community.
    Raises ValueError when the name, model, or change-set is empty.
    """
    built = CommunityTrigger(
        name=name,
        target_model=target_model,
        trigger=trigger,
        changeset=_copy_changeset(changeset),
        host_model=host_model,
        record_id=record_id,
    )
    _require_community(built)
    _require_target(built)
    return built


def reset_trigger_gate() -> None:
    """Drop process-local firing cards.

    Inputs: none.
    Output: none.
    Side effects: clears this process's firing ledger. Does not write a
    database and does not call Odoo.
    """
    _FIRINGS.clear()


def fire(
    trigger: CommunityTrigger,
    *,
    person: str,
    connection_id: str,
    environment: str,
    requester_id: str,
    known_models: set[str],
    db: Session,
    trigger_exists: bool = False,
) -> Firing:
    """Open a new pending plan card for one firing.

    Inputs: the Community trigger, the person, connection, environment,
    requester, known models, the audit session, and whether the automation
    row already exists.
    Output: a pending firing. `approval_id` is always None.
    Side effects: stores the card in this process and appends one `note` row
    on the audit chain naming the trigger, the person, and the plan hash.
    Does not call the executor. Does not call Odoo.
    Raises ProtectedModelBlocked when the watched model is protected,
    EnterpriseTriggerRefused when the host is not base.automation,
    TriggerRejected when the inbox refuses the change-set, TriggerGateError
    when existence would be treated as approval, and ValueError when the
    person or connection is blank.
    """
    _require_community(trigger)
    _require_person(person)
    if not connection_id.strip():
        raise ValueError("connection_id is required")
    if trigger_is_not_approval(trigger_exists):
        raise TriggerGateError("a trigger's existence is not approval")

    blocked = _protected_model(trigger)
    if blocked is not None:
        raise ProtectedModelBlocked(blocked)

    firing_id = uuid.uuid4().hex
    assumptions = [
        "The trigger already existing is not approval.",
        f"trigger:{trigger.name}",
        f"firing:{firing_id}",
    ]
    changeset = [dict(op) for op in trigger.changeset]
    inbox = Inbox()
    result = inbox.submit(
        changeset,
        goal=f"Trigger {trigger.name}",
        assumptions=assumptions,
        environment=environment,
        requester_id=requester_id,
        known_models=set(known_models),
        connection_id=connection_id,
    )
    if not result.get("ok"):
        raise TriggerRejected("the approval gate refused this firing")
    card = result["card"]
    if card.get("status") != "pending" or card.get("approvals"):
        raise TriggerGateError("a firing must open a pending plan card")
    plan_hash = str(card["plan_hash"])
    record = _FiringRecord(
        firing_id=firing_id,
        trigger_name=trigger.name,
        person=person,
        card=card,
        changeset=changeset,
        inbox=inbox,
        connection_id=connection_id,
        environment=environment,
    )
    _FIRINGS[plan_hash] = record
    append_entry(
        db,
        actor=person,
        kind="note",
        payload={
            "trigger": trigger.name,
            "person": person,
            "plan_hash": plan_hash,
        },
        run_id=firing_id,
    )
    return Firing(
        firing_id=firing_id,
        plan_hash=plan_hash,
        status="pending",
        approval_id=None,
        trigger=trigger.name,
        person=person,
    )


def approve(plan_hash: str, *, person: str) -> str:
    """Approve one firing. Other firings of the same trigger stay pending.

    Inputs: the plan hash from fire, and the person approving.
    Output: a new approval id bound to that plan hash only.
    Side effects: records the decision on the stored inbox card.
    Does not call the executor and does not call Odoo.
    Raises ApprovalRequired when the card is missing or the gate does not
    approve it. Raises ValueError when the person is blank.
    """
    _require_person(person)
    record = _FIRINGS.get(plan_hash)
    if record is None:
        raise ApprovalRequired("plan card not found")
    if record.approval_id is not None:
        raise ApprovalRequired("this firing already has an approval")
    card = record.inbox.decide(
        plan_hash,
        approver_id=person,
        decision="approve",
        connection_id=record.connection_id,
        user_id=person,
    )
    if card.get("status") != "approved":
        raise ApprovalRequired("approval gate did not approve this firing")
    approval_id = uuid.uuid4().hex
    record.approval_id = approval_id
    record.card = card
    return approval_id


def apply_firing(plan_hash: str, *, approval_id: str, mode: str = "T") -> dict[str, Any]:
    """Apply one firing after its own approval id checks out.

    Inputs: the plan hash, the approval id from approve for that hash, and
    executor mode T or C.
    Output: the executor result.
    Side effects: calls executor.apply only after the approval id matches
    this firing. Does not call Odoo itself.
    Raises ApprovalRequired when the id is missing or belongs to another firing.
    """
    if not approval_id or not isinstance(approval_id, str):
        raise ApprovalRequired("approval id is required")
    record = _FIRINGS.get(plan_hash)
    if record is None or record.approval_id != approval_id:
        raise ApprovalRequired("approval id does not match this firing")
    if record.card.get("status") != "approved":
        raise ApprovalRequired("plan is not approved")
    changeset = [dict(op) for op in record.changeset]
    return executor.apply(
        changeset,
        mode=mode,
        approved_hash=executor.changeset_fingerprint(changeset),
        environment=record.environment,
    )


def plan_card(plan_hash: str) -> dict[str, Any]:
    """Return a copy of the plan card for one firing.

    Inputs: the plan hash.
    Output: the stored card including its sections and status.
    Side effects: none.
    Raises ApprovalRequired when the firing is unknown.
    """
    record = _FIRINGS.get(plan_hash)
    if record is None:
        raise ApprovalRequired("plan card not found")
    return dict(record.card)


def approval_id_for(plan_hash: str) -> str | None:
    """Return the approval id for one firing, or None while it is pending.

    Inputs: the plan hash.
    Output: the id from approve, or None.
    Side effects: none.
    Raises ApprovalRequired when the firing is unknown.
    """
    record = _FIRINGS.get(plan_hash)
    if record is None:
        raise ApprovalRequired("plan card not found")
    return record.approval_id


def _require_community(trigger: CommunityTrigger) -> None:
    host = trigger.host_model
    if host != _HOST_MODEL or "studio" in host.casefold():
        raise EnterpriseTriggerRefused("Community triggers use base.automation")
    if "studio" in trigger.trigger.casefold() or trigger.trigger not in _COMMUNITY_TRIGGERS:
        raise EnterpriseTriggerRefused(
            "trigger is not a Community base.automation trigger"
        )


def _require_target(trigger: CommunityTrigger) -> None:
    if not trigger.name.strip():
        raise ValueError("trigger name is required")
    if not trigger.target_model.strip():
        raise ValueError("target_model is required")
    if not trigger.changeset:
        raise ValueError("changeset is required")


def _require_person(person: str) -> None:
    if not isinstance(person, str) or not person.strip():
        raise ValueError("person is required")
    if len(person) > 200:
        raise ValueError("person is too long")


def _copy_changeset(changeset: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    copied: list[dict[str, Any]] = []
    for op in changeset:
        if not isinstance(op, dict):
            raise ValueError("changeset ops must be objects")
        params = op.get("params")
        item = dict(op)
        if isinstance(params, dict):
            item["params"] = dict(params)
        copied.append(item)
    return tuple(copied)


def _is_protected_model(name: str) -> bool:
    folded = name.casefold()
    for model in deny_models():
        token = model.casefold()
        if folded == token or folded.startswith(token + "."):
            return True
    return False


def _protected_model(trigger: CommunityTrigger) -> str | None:
    if _is_protected_model(trigger.target_model):
        return trigger.target_model
    document = list(trigger.changeset)
    for op in document:
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        model = params.get("model")
        if isinstance(model, str) and _is_protected_model(model):
            return model
        if protected_denial(op, document=document):
            return "protected_deny"
    return None
