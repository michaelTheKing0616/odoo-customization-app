"""Approval inbox. The card is rendered by the engine. The model does not write it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.changeset.plan_card import render_plan_card
from app.changeset.policy import self_approval_allowed
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
        if report["max_risk"] == "R4":
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
        self.cards[card["plan_hash"]] = card
        return {"ok": True, "card": card}

    def decide(
        self,
        plan_hash: str,
        *,
        approver_id: str,
        decision: Decision,
        connection_id: str,
    ) -> dict[str, Any]:
        card = self.cards.get(plan_hash)
        if card is None or card["connection_id"] != connection_id:
            raise InboxError("not found")
        if card["status"] != "pending":
            raise InboxError("plan is not pending")
        if decision == "approve" and not self_approval_allowed(card["max_risk"]):
            if approver_id == card["requester_id"]:
                raise InboxError("the requester cannot approve this risk")
        card["approvals"].append({"approver_id": approver_id, "decision": decision})
        if decision == "approve":
            needed = int(card["risk"]["policy"]["approvers"])
            approvals = [a for a in card["approvals"] if a["decision"] == "approve"]
            distinct = {a["approver_id"] for a in approvals}
            if len(distinct) >= needed:
                card["status"] = "approved"
        elif decision == "deny":
            card["status"] = "denied"
        else:
            card["status"] = "stopped"
        return card

    def visible(self, connection_id: str) -> list[dict[str, Any]]:
        return [card for card in self.cards.values() if card["connection_id"] == connection_id]
