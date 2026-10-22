"""GATE-L4-04. A standing rule activates only after two distinct admins, one an owner.

The book is in-memory. It is not a table, not an apply path, and not an L4 level.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

GATE_L4_04 = "GATE-L4-04"
STANDING_RULE_ROLES = frozenset({"admin", "owner"})
OWNER_ROLE = "owner"

_RULE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _rule_id(value: object) -> str:
    """Standing-rule id.

    Inputs: the caller-supplied id.
    Outputs: the stripped id when it is a short token.
    Side effects: none.
    Raises ValueError when the id is missing or not a token.
    """
    if not isinstance(value, str):
        raise ValueError("invalid standing rule id")
    token = value.strip()
    if not _RULE_ID_RE.fullmatch(token):
        raise ValueError("invalid standing rule id")
    return token


def _user_id(value: object) -> str | None:
    """Authenticated person id.

    Inputs: the ``user_id`` field from one approval.
    Outputs: the stripped id, or None when it is missing, blank, or not a string.
    Side effects: none. A label, approver id, session, or provider is not this value.
    """
    if not isinstance(value, str):
        return None
    token = value.strip()
    if not token:
        return None
    return token


def _role(value: object) -> str | None:
    """Admin or owner role.

    Inputs: the ``role`` field from one approval.
    Outputs: ``admin`` or ``owner`` after strip and case fold. None for any other value.
    Side effects: none.
    """
    if not isinstance(value, str):
        return None
    token = value.strip().casefold()
    if token in STANDING_RULE_ROLES:
        return token
    return None


def counted_standing_rule_admins(
    approvals: Sequence[Mapping[str, object]],
) -> tuple[frozenset[str], frozenset[str]]:
    """Distinct admins and which of them are the workspace owner.

    Inputs: approval records. Only ``user_id`` and ``role`` are read.
    Outputs: ``(admin_user_ids, owner_user_ids)``. ``owner_user_ids`` is a subset
    of ``admin_user_ids``. A record with no string ``user_id`` is not a person.
    Two records that share ``user_id`` are one person even when their labels or
    approver ids differ. Owner is a role on that person. A later ``owner`` role
    for the same user id upgrades that one person. It does not add a second person.
    A role outside ``admin`` and ``owner`` is not an admin.
    Side effects: none.
    """
    if isinstance(approvals, (str, bytes)) or not isinstance(approvals, Sequence):
        return frozenset(), frozenset()
    roles: dict[str, str] = {}
    for item in approvals:
        if not isinstance(item, Mapping):
            continue
        user_id = _user_id(item.get("user_id"))
        role = _role(item.get("role"))
        if user_id is None or role is None:
            continue
        if roles.get(user_id) == OWNER_ROLE:
            continue
        roles[user_id] = role
    admin_ids = frozenset(roles)
    owner_ids = frozenset(user_id for user_id, role in roles.items() if role == OWNER_ROLE)
    return admin_ids, owner_ids


def standing_rule_is_active(approvals: Sequence[Mapping[str, object]]) -> bool:
    """Whether these approvals activate a standing rule.

    Inputs: approval records, same shape as ``counted_standing_rule_admins``.
    Outputs: True only when at least two distinct admin user ids are present and
    at least one of them has role ``owner``. The same admin twice is False.
    Two admins and no owner is False. One owner is False.
    Side effects: none. Does not enable L4 and does not read eligibility history.
    """
    admin_ids, owner_ids = counted_standing_rule_admins(approvals)
    return len(admin_ids) >= 2 and len(owner_ids) >= 1


@dataclass(frozen=True, slots=True)
class StandingRuleView:
    """One standing rule as stored in memory.

    ``active`` is True only after GATE-L4-04 is met. Holding an active view
    does not enable L4.
    """

    rule_id: str
    active: bool
    admin_user_ids: frozenset[str]
    owner_user_ids: frozenset[str]


class StandingRuleBook:
    """In-process standing rules. Not a customer database and not an L4 level."""

    def __init__(self) -> None:
        self._approvals: dict[str, list[dict[str, str]]] = {}

    def get(self, rule_id: str) -> StandingRuleView:
        """Return one rule.

        Inputs: the rule id.
        Outputs: the current view. A rule that was never opened is inactive
        and has no admins.
        Side effects: none. Does not create the rule.
        """
        token = _rule_id(rule_id)
        return self._view(token, self._approvals.get(token, ()))

    def open(self, rule_id: str) -> StandingRuleView:
        """Open a pending rule.

        Inputs: the rule id.
        Outputs: the current view. A new rule is inactive.
        Side effects: creates the in-memory rule when it is absent. A second
        open does not clear approvals and does not enable L4.
        """
        token = _rule_id(rule_id)
        self._approvals.setdefault(token, [])
        return self._view(token, self._approvals[token])

    def approve(self, rule_id: str, approval: Mapping[str, object]) -> StandingRuleView:
        """Record one approval against a standing rule.

        Inputs: the rule id and one approval mapping. ``user_id`` is the person.
        ``role`` is ``admin`` or ``owner``. Any other key, including ``label``,
        ``approver_id``, ``display_name``, ``name``, ``session_id``, and
        ``provider``, is not an identity and is not stored.
        Outputs: the view after this attempt. ``active`` is True only when two
        distinct admin user ids are recorded and one of them is the owner.
        Side effects: stores ``user_id`` and ``role`` when both identify an
        admin. A missing user id, a blank user id, or a non-admin role changes
        nothing. Does not write a database row, does not call Odoo, and does
        not enable L4.
        """
        token = _rule_id(rule_id)
        stored = self._approvals.setdefault(token, [])
        if isinstance(approval, Mapping):
            user_id = _user_id(approval.get("user_id"))
            role = _role(approval.get("role"))
            if user_id is not None and role is not None:
                stored.append({"user_id": user_id, "role": role})
        return self._view(token, stored)

    def _view(self, rule_id: str, approvals: Sequence[Mapping[str, object]]) -> StandingRuleView:
        admin_ids, owner_ids = counted_standing_rule_admins(approvals)
        return StandingRuleView(
            rule_id=rule_id,
            active=len(admin_ids) >= 2 and len(owner_ids) >= 1,
            admin_user_ids=admin_ids,
            owner_user_ids=owner_ids,
        )
