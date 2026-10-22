"""Approval inbox. The card is rendered by the engine. The model does not write it."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from app.changeset.plan_card import (
    changeset_ops_fingerprint,
    ops_from_card_changes,
    render_plan_card,
)
from app.changeset.policy import (
    approver_is_requester,
    changeset_r4_posture,
    distinct_approver_count,
    production_r3_approval_met,
    self_approval_allowed,
    target_requires_domain_owner,
)
from app.changeset.validate import validate

Decision = Literal["approve", "deny", "deny_and_stop"]


class InboxError(ValueError):
    pass


@dataclass
class Inbox:
    cards: dict[str, dict[str, Any]] = field(default_factory=dict)

    def submit(
        self,
        changeset: list[dict[str, Any]],
        *,
        goal: str,
        assumptions: list[str],
        environment: str,
        requester_id: str,
        known_models: set[str],
        connection_id: str,
    ) -> dict[str, Any]:
        report = validate(changeset, known_models=known_models)
        if not report["valid"]:
            return {"ok": False, "report": report}
        if report["max_risk"] == "R4" and changeset_r4_posture(changeset) != "heavy":
            return {"ok": False, "report": report, "error": "R4 is denied"}
        card = render_plan_card(
            changeset,
            goal=goal,
            assumptions=assumptions,
            environment=environment,
        )
        card["requester_id"] = requester_id
        card["connection_id"] = connection_id
        card["status"] = "pending"
        card["approvals"] = []
        card["max_risk"] = report["max_risk"]
        ops_fp = changeset_ops_fingerprint(changeset)
        for other in self.cards.values():
            if other.get("connection_id") != connection_id:
                continue
            if other.get("status") != "pending":
                continue
            if other.get("plan_hash") == card["plan_hash"]:
                continue
            if changeset_ops_fingerprint(ops_from_card_changes(other)) != ops_fp:
                continue
            other["status"] = "voided"
        self.cards[card["plan_hash"]] = card
        return {"ok": True, "card": card}

    def decide(
        self,
        plan_hash: str,
        *,
        approver_id: str,
        decision: Decision,
        connection_id: str,
        user_id: str | None = None,
        session_id: str | None = None,
        provider: str | None = None,
        domain_owner: bool | None = None,
        role: str | None = None,
        simulation_passed: bool | None = None,
        backup_id: str | None = None,
        allowed_window: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Record approve, deny, or deny-and-stop.

        Inputs: the plan hash, the approver, the decision, and the connection.
        ``user_id`` is the authenticated person. ``session_id`` and ``provider``
        name a session or an OAuth identity and do not add a second person.
        ``approver_id`` alone is not a person on production heavy R4. Two
        calls that omit ``user_id``, or that send different ``approver_id``
        values for the same caller, do not count as two people.
        ``domain_owner`` or ``role="domain_owner"`` marks a domain owner.
        Production R3 also reads ``simulation_passed``, ``backup_id``,
        ``allowed_window``, and ``now``.
        Output: the updated card. Production and staging R3 become approved on
        one approval. The approver may be the requester. Production heavy R4
        stays pending until two distinct authenticated people have approved,
        a protected target has a domain owner, the simulation passed, a backup
        id is present, and the clock is inside the allowed window.
        Side effects: mutates the stored card. Does not call Odoo.
        Raises InboxError when the card is missing or not pending. The
        requester cannot be both approvers on a production heavy-R4 plan,
        including through a second identity.
        """
        card = self.cards.get(plan_hash)
        if card is None or card["connection_id"] != connection_id:
            raise InboxError("not found")
        if card["status"] != "pending":
            raise InboxError("plan is not pending")
        if (
            decision == "approve"
            and not self_approval_allowed(card["max_risk"])
            and not _heavy_card(card)
            and approver_is_requester(approver_id, card["requester_id"], user_id=user_id)
        ):
            raise InboxError("the requester cannot approve this risk")
        record: dict[str, Any] = {"approver_id": approver_id, "decision": decision}
        if user_id:
            record["user_id"] = user_id
        if session_id:
            record["session_id"] = session_id
        if provider:
            record["provider"] = provider
        if domain_owner is True or role == "domain_owner":
            record["domain_owner"] = True
        if role:
            record["role"] = role
        card["approvals"].append(record)
        if decision == "approve":
            _remember_r3_evidence(
                card,
                simulation_passed=simulation_passed,
                backup_id=backup_id,
                allowed_window=allowed_window,
            )
            if _heavy_production(card):
                outcome = production_r3_approval_met(
                    card["risk"]["policy"],
                    card["approvals"],
                    requester_id=str(card["requester_id"]),
                    protected=_card_is_protected(card),
                    simulation_passed=card.get("simulation_passed") is True,
                    backup_id=card.get("backup_id"),
                    allowed_window=card.get("allowed_window"),
                    now=now or datetime.now(timezone.utc),
                )
                card["r3_blockers"] = outcome["blockers"]
                if outcome["met"]:
                    card["status"] = "approved"
            else:
                needed = int(card["risk"]["policy"]["approvers"])
                if distinct_approver_count(card["approvals"]) >= needed:
                    card["status"] = "approved"
        elif decision == "deny":
            card["status"] = "denied"
        else:
            card["status"] = "stopped"
        return card

    def visible(self, connection_id: str) -> list[dict[str, Any]]:
        return [card for card in self.cards.values() if card["connection_id"] == connection_id]


def _heavy_card(card: dict[str, Any]) -> bool:
    """Whether this card is an allowed heavy-R4 plan.

    Inputs: a stored plan card.
    Output: True when the card risk is R4 and policy allows it.
    Side effects: none.
    """
    risk = card.get("risk")
    policy = risk.get("policy") if isinstance(risk, Mapping) else None
    if not isinstance(policy, Mapping):
        return False
    return card.get("max_risk") == "R4" and bool(policy.get("allow")) and not bool(policy.get("deny"))


def _heavy_production(card: dict[str, Any]) -> bool:
    """Whether this card is a production heavy-R4 plan.

    Inputs: a stored plan card.
    Output: True when policy asks for two approvers, a simulation, a backup,
    and an allowed window, and the card risk is R4.
    Side effects: none.
    """
    risk = card.get("risk")
    policy = risk.get("policy") if isinstance(risk, Mapping) else None
    if not isinstance(policy, Mapping) or not _heavy_card(card):
        return False
    return (
        int(policy.get("approvers") or 0) >= 2
        and bool(policy.get("needs_simulation"))
        and bool(policy.get("needs_backup"))
        and bool(policy.get("needs_window"))
    )


def _card_is_protected(card: dict[str, Any]) -> bool:
    risk = card.get("risk")
    policy = risk.get("policy") if isinstance(risk, Mapping) else None
    if isinstance(policy, Mapping) and bool(policy.get("domain_owner")):
        return True
    return target_requires_domain_owner(ops_from_card_changes(card))


def _remember_r3_evidence(
    card: dict[str, Any],
    *,
    simulation_passed: bool | None,
    backup_id: str | None,
    allowed_window: Mapping[str, Any] | None,
) -> None:
    """Keep the latest explicit production-R3 evidence on the card.

    Inputs: the card and the evidence from this decision. None leaves the
    previous value in place.
    Output: none.
    Side effects: writes ``simulation_passed``, ``backup_id``, and
    ``allowed_window`` on the card when the caller sent them.
    """
    if simulation_passed is not None:
        card["simulation_passed"] = simulation_passed is True
    if backup_id is not None:
        card["backup_id"] = backup_id if isinstance(backup_id, str) else ""
    if allowed_window is not None:
        card["allowed_window"] = {
            "start": allowed_window.get("start"),
            "end": allowed_window.get("end"),
        }
