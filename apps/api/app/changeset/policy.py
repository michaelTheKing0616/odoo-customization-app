"""Risk ladder and environment policy for change-set ops."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.changeset.logic_ops import logic_base_raise
from app.changeset.ops import is_known_op, op_base_risk
from app.changeset.protected_registry import protection_level, requires_domain_owner
from app.changeset.schema_ops import nonempty_sensitive_delete
from app.changeset.security_ops import group_implies_admin, privileged_assignment
from app.changeset.setting_ops import company_update_issues, protected_config_key

_RISK_ORDER = ("R0", "R1", "R2", "R3", "R4")
# Staging R1 needs no human approval at L3 and L4. Production does not use this set.
_STAGING_R1_OPEN_AUTONOMY = frozenset({"L3", "L4"})
STAGING_APPROVAL_EXPIRY_HOURS = 7 * 24
PRODUCTION_R2_APPROVAL_EXPIRY_HOURS = 24


def _bump(risk: str, steps: int) -> str:
    idx = _RISK_ORDER.index(risk)
    return _RISK_ORDER[min(idx + steps, len(_RISK_ORDER) - 1)]


def risk_of(
    op: dict[str, Any],
    *,
    rows: int = 0,
    users: int = 0,
    outbound: bool = False,
    mode_c: bool = False,
    protected: bool = False,
    no_simulation_on_production: bool = False,
    tenant: dict[str, Any] | None = None,
    document: list[dict[str, Any]] | None = None,
) -> str:
    """Catalog risk plus escalations. Each escalation adds one. The result stays in R0–R4.

    Inputs: one op and optional impact flags. A `risk` key on the op is ignored, so a
    caller cannot talk the catalog class down. `no_simulation_on_production` is a
    production apply with no recorded simulation. Defaults leave existing callers unchanged.
    Output: R0–R4.
    Side effects: none.
    """
    op_type = str(op.get("type", ""))
    params = op.get("params")
    if not isinstance(params, dict):
        params = {}
    base = op_base_risk(op_type, params)
    if base == "R4":
        return "R4"
    level = protection_level(op, tenant=tenant, document=document)
    if level == "deny":
        return "R4"
    bumps = 0
    if protected:
        bumps += 1
    if level == "elevate":
        bumps += 1
    if rows > 1000:
        bumps += 1
    if users > 10:
        bumps += 1
    if outbound:
        bumps += 1
    if no_simulation_on_production:
        bumps += 1
    if mode_c:
        bumps += 1
    return _bump(base, bumps)


def r4_gate(op: dict[str, Any]) -> str | None:
    """Classify one op as heavy R4, hard-stop R4, or neither.

    Inputs: one change-set op with ``type`` and optional ``params``.
    Output: ``heavy`` for module uninstall, data delete, granting
    admin/system/service, fiscal year, currency, chart of accounts, and
    accounting or legal sequence changes. ``hard_stop`` for raw SQL,
    ``rpc.write``, payment secrets, posted accounting entries, lock dates,
    a group-less access rule, and any other R4. ``None`` when the op is not
    an R4 gate. Hard stop wins when both could apply.
    Side effects: none.
    """
    op_type = str(op.get("type") or "")
    params = op.get("params") if isinstance(op.get("params"), dict) else {}
    if op_type == "rpc.write" or not is_known_op(op_type):
        return "hard_stop"
    if "sql" in params:
        return "hard_stop"
    if op_type in {"access.create", "access.update"} and not params.get("group"):
        return "hard_stop"
    if op_type == "config_param.set" and _payment_secret(params):
        return "hard_stop"
    if op_type == "company.update" and any("lock date" in issue for issue in company_update_issues(params)):
        return "hard_stop"
    if _posted_accounting(params):
        return "hard_stop"
    if op_type == "field.delete" and nonempty_sensitive_delete(params):
        return "hard_stop"
    if protection_level(op) == "deny":
        return "hard_stop"
    if op_type in {"module.uninstall", "data.delete"}:
        return "heavy"
    if op_type == "group.create" and group_implies_admin(params):
        return "heavy"
    if op_type == "user.groups.assign" and (bool(params.get("admin")) or privileged_assignment(params)):
        return "heavy"
    if op_type == "company.update" and company_update_issues(params):
        return "heavy"
    if logic_base_raise(op_type, params) == "R4":
        return "heavy"
    if op_base_risk(op_type, params) == "R4":
        return "hard_stop"
    return None


def changeset_r4_posture(changeset: list[dict[str, Any]]) -> str | None:
    """Whether a change-set is heavy R4, hard-stop R4, or neither.

    Inputs: the change-set. Non-dicts are ignored.
    Output: ``hard_stop`` when any op is a hard stop, else ``heavy`` when any
    op is heavy, else ``None``.
    Side effects: none.
    """
    gates = [r4_gate(op) for op in changeset if isinstance(op, dict)]
    if any(gate == "hard_stop" for gate in gates):
        return "hard_stop"
    if any(gate == "heavy" for gate in gates):
        return "heavy"
    return None


def _payment_secret(params: dict[str, Any]) -> bool:
    if protected_config_key(params):
        return True
    key = params.get("key")
    if not isinstance(key, str):
        return False
    folded = key.casefold()
    return "payment" in folded and any(token in folded for token in ("secret", "token", "password", "api_key"))


def _posted_accounting(params: dict[str, Any]) -> bool:
    model = str(params.get("model") or "")
    if model not in {"account.move", "account.move.line"}:
        return False
    if params.get("posted") is True:
        return True
    state = params.get("state")
    if isinstance(state, str) and state.strip().casefold() == "posted":
        return True
    values = params.get("values")
    if isinstance(values, dict):
        posted = values.get("state")
        if isinstance(posted, str) and posted.strip().casefold() == "posted":
            return True
    return False


def approval_expiry_hours(risk: str, environment: str) -> int:
    """How long an approval stays valid.

    Inputs: risk class R0–R4 and environment. Any environment other than staging
    follows the production rule.
    Output: 24 hours on production when risk is R2 or higher. 168 hours (7 days)
    on staging, and on production for R0 and R1, where the 24-hour rule does not apply.
    Side effects: none. Raises ValueError for an unknown risk class.
    """
    if risk not in _RISK_ORDER:
        raise ValueError(f"unknown risk class: {risk}")
    high = _RISK_ORDER.index(risk) >= _RISK_ORDER.index("R2")
    if environment.lower() != "staging" and high:
        return PRODUCTION_R2_APPROVAL_EXPIRY_HOURS
    return STAGING_APPROVAL_EXPIRY_HOURS


def approval_count_met(received: int, required: int) -> bool:
    """Whether distinct approvers satisfy the required count.

    Inputs: distinct approvers already recorded, and the count from the matrix.
    Output: True when received >= required. An equal count is enough.
    Side effects: none.
    """
    return received >= required


def apply_blocked(decision: dict[str, bool | int], *, frozen: bool) -> bool:
    """Whether apply must stop.

    Inputs: a policy decision and whether a freeze window is active.
    Output: True when a freeze is on, or the decision denies or does not allow.
    A freeze blocks every apply, including a cell the matrix would otherwise allow.
    Side effects: none.
    """
    if frozen:
        return True
    return bool(decision["deny"]) or not bool(decision["allow"])


def policy_decision(
    risk: str,
    environment: str,
    *,
    autonomy: str = "L2",
    elevated: bool = False,
    heavy: bool = False,
) -> dict[str, bool | int]:
    """Who must approve.

    Inputs: risk class, environment, autonomy, whether the target is
    protected:elevate, and whether an R4 op is on the heavy list.
    Output: allow, approvers, needs_simulation, deny, domain_owner, needs_backup,
    needs_window, and expiry_hours. R3 is one approval on staging and production.
    The approver may be the requester. R3 does not require a simulation, a
    backup, or a window. Heavy R4 is one approval on staging. Heavy R4 on
    production is two distinct people, a domain owner when elevated, a
    simulation, a backup, and an allowed window. Hard-stop R4 stays denied.
    L4 does not reduce R3 or R4, and does not apply either by itself.
    Side effects: none.
    """

    def finish(
        allow: bool,
        approvers: int,
        needs_simulation: bool,
        deny: bool,
        *,
        needs_backup: bool = False,
        needs_window: bool = False,
    ) -> dict[str, bool | int]:
        known = risk if risk in _RISK_ORDER else "R4"
        return {
            "allow": allow,
            "approvers": approvers,
            "needs_simulation": needs_simulation,
            "deny": deny,
            "domain_owner": bool(elevated) and not deny,
            "needs_backup": needs_backup,
            "needs_window": needs_window,
            "expiry_hours": approval_expiry_hours(known, env),
        }

    env = environment.lower()
    if risk == "R4" and not heavy:
        return finish(False, 0, False, True)

    if env == "staging":
        if risk == "R0":
            return finish(True, 0, False, False)
        if risk == "R1":
            approvers = 0 if autonomy in _STAGING_R1_OPEN_AUTONOMY else 1
            return finish(True, approvers, False, False)
        if risk in {"R2", "R3", "R4"}:
            return finish(True, 1, False, False)
        return finish(False, 0, False, True)

    # production (default). L4 does not drop an R3 or heavy-R4 approval.
    if risk == "R0":
        return finish(True, 0, False, False)
    if risk in {"R1", "R2"}:
        return finish(True, 1, True, False)
    if risk == "R3":
        return finish(True, 1, False, False)
    if risk == "R4" and heavy:
        return finish(True, 2, True, False, needs_backup=True, needs_window=True)
    return finish(False, 0, False, True)


def policy_for_op(
    op: dict[str, Any],
    environment: str,
    *,
    autonomy: str = "L2",
    tenant: dict[str, Any] | None = None,
    document: list[dict[str, Any]] | None = None,
    rows: int = 0,
    users: int = 0,
    outbound: bool = False,
    mode_c: bool = False,
    no_simulation_on_production: bool = False,
) -> dict[str, bool | int]:
    """Policy for one op, including the protected:elevate domain-owner requirement.

    Inputs: the op, environment, and the same risk bumps `risk_of` accepts.
    Output: the policy decision. `domain_owner` is true only for an allowed elevate.
    Side effects: none.
    """
    risk = risk_of(
        op,
        rows=rows,
        users=users,
        outbound=outbound,
        mode_c=mode_c,
        no_simulation_on_production=no_simulation_on_production,
        tenant=tenant,
        document=document,
    )
    elevated = requires_domain_owner(op, document=document, tenant=tenant)
    return policy_decision(
        risk,
        environment,
        autonomy=autonomy,
        elevated=elevated,
        heavy=r4_gate(op) == "heavy",
    )


def self_approval_allowed(risk: str) -> bool:
    """Whether the requester may be an approver for this risk class.

    Inputs: a risk class.
    Output: True for R0–R3. The requester may approve R3. False for R4, which
    the heavy gate counts as at most one person and never as both approvers.
    Side effects: none.
    """
    return risk != "R4"


def _text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def approver_is_requester(approver_id: object, requester_id: object, *, user_id: object = None) -> bool:
    """Whether this approval is the requester under any identity.

    Inputs: the approver id, the requester id, and the canonical user id when
    the caller knows which person the session or OAuth identity belongs to.
    Output: True when the user id or the approver id is the requester.
    Side effects: none.
    """
    requester = _text(requester_id)
    if requester == "":
        return False
    if _text(user_id) == requester:
        return True
    return _text(approver_id) == requester


def _person_key(item: Mapping[str, Any]) -> str:
    """One person on the one-approval path.

    Inputs: one approval record.
    Output: ``user:<id>`` when user_id is set, otherwise ``approver:<id>``.
    An empty record returns an empty string and does not count. Production
    heavy R4 does not use this key. That gate uses ``_authenticated_person_key``.
    Side effects: none.
    """
    user_id = _text(item.get("user_id"))
    if user_id:
        return f"user:{user_id}"
    approver_id = _text(item.get("approver_id"))
    if approver_id:
        return f"approver:{approver_id}"
    return ""


def _authenticated_person_key(item: Mapping[str, Any]) -> str:
    """The authenticated person on a production heavy-R4 approval.

    Inputs: one approval record.
    Output: ``user:<id>`` when user_id is set. Empty when user_id is absent,
    so two calls that omit it, or that send different approver ids for one
    caller, do not become two people. ``approver_id``, ``session_id``, and
    ``provider`` do not add a person.
    Side effects: none.
    """
    user_id = _text(item.get("user_id"))
    if not user_id:
        return ""
    return f"user:{user_id}"


def _approve_records(approvals: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [item for item in approvals if isinstance(item, Mapping) and item.get("decision") == "approve"]


def distinct_approver_count(approvals: list[Mapping[str, Any]]) -> int:
    """How many people approved.

    Inputs: approval records. Only ``decision == approve`` counts.
    Output: the number of distinct people. Records that share ``user_id`` are
    one person, including two sessions or a Google identity and a Microsoft
    identity. Without ``user_id``, ``approver_id`` is the person. That fallback
    is only for the one-approval path, including production R3. Production
    heavy R4 counts ``user_id`` only.
    Side effects: none.
    """
    keys: set[str] = set()
    for item in _approve_records(approvals):
        key = _person_key(item)
        if key:
            keys.add(key)
    return len(keys)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    if not isinstance(value, str) or value.strip() == "":
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return _as_utc(parsed)


def allowed_window_open(window: object, now: datetime) -> bool:
    """Whether the clock sits inside an allowed change window.

    Inputs: a mapping with ``start`` and ``end``, and the clock.
    Output: True when start <= now < end. A missing, reversed, or equal pair
    is closed. Naive timestamps are UTC.
    Side effects: none.
    """
    if not isinstance(window, Mapping):
        return False
    start = _parse_time(window.get("start"))
    end = _parse_time(window.get("end"))
    if start is None or end is None or start >= end:
        return False
    return start <= _as_utc(now) < end


def _backup_present(backup_id: object) -> bool:
    return isinstance(backup_id, str) and backup_id.strip() != ""


def _is_domain_owner(item: Mapping[str, Any]) -> bool:
    return item.get("domain_owner") is True or item.get("role") == "domain_owner"


def target_requires_domain_owner(changeset: list[dict[str, Any]]) -> bool:
    """Whether any op is protected:elevate and needs a domain-owner approver.

    Inputs: the change-set. Each item needs ``type`` and ``params``.
    Output: True when a domain owner must approve. A deny target is not an
    approval requirement.
    Side effects: none. Does not record a protected-registry detection.
    """
    return any(
        requires_domain_owner(op, document=changeset) for op in changeset if isinstance(op, dict)
    )


def production_r3_approval_met(
    decision: Mapping[str, Any],
    approvals: list[Mapping[str, Any]],
    *,
    requester_id: str,
    protected: bool,
    simulation_passed: bool,
    backup_id: object,
    allowed_window: object,
    now: datetime,
) -> dict[str, Any]:
    """Whether a production heavy-R4 approval is complete.

    Inputs: the policy decision, the recorded approvals, the requester, whether
    the target is protected, the simulation result, the backup id, the allowed
    window, and the clock.
    Output: ``met``, ``distinct_approvers``, and ``blockers``. Blockers are
    ``not_heavy_r4``, ``distinct_approvers``, ``domain_owner``,
    ``simulation``, ``backup``, and ``window``, and only the ones that failed.
    ``met`` is True when blockers is empty. An R3 decision does not pass.
    Side effects: none. The requester does not count toward the two people, so
    the requester cannot be both approvers, including a second identity. A
    heavy-R4 approval counts only when ``user_id`` names the authenticated
    person. Two records that omit ``user_id``, or that share ``user_id`` and
    differ in ``approver_id``, session, or OAuth provider, are not two people.
    An approval with no ``user_id`` is not a person, so a different
    ``approver_id`` cannot slip past requester exclusion. A protected target,
    or a decision with ``domain_owner``, needs that role on one of the counted
    people. L4 is not an input and cannot skip a gate.
    """
    counted: set[str] = set()
    owner = False
    for item in _approve_records(approvals):
        key = _authenticated_person_key(item)
        if not key:
            continue
        if approver_is_requester(item.get("approver_id"), requester_id, user_id=item.get("user_id")):
            continue
        counted.add(key)
        if _is_domain_owner(item):
            owner = True
    blockers: list[str] = []
    required = int(decision.get("approvers") or 0)
    if len(counted) < required:
        blockers.append("distinct_approvers")
    if (protected or bool(decision.get("domain_owner"))) and not owner:
        blockers.append("domain_owner")
    if simulation_passed is not True:
        blockers.append("simulation")
    if not _backup_present(backup_id):
        blockers.append("backup")
    if not allowed_window_open(allowed_window, now):
        blockers.append("window")
    heavy_production = (
        bool(decision.get("allow"))
        and not bool(decision.get("deny"))
        and int(decision.get("approvers") or 0) >= 2
        and bool(decision.get("needs_simulation"))
        and bool(decision.get("needs_backup"))
        and bool(decision.get("needs_window"))
    )
    if not heavy_production:
        blockers.insert(0, "not_heavy_r4")
    return {"met": not blockers, "distinct_approvers": len(counted), "blockers": blockers}


HEAVY_GATE_DISTINCT = "heavy gate requires two distinct approvers"
HEAVY_GATE_SIMULATION = "heavy gate requires a passed simulation"
HEAVY_GATE_BACKUP = "heavy gate requires a backup"
HEAVY_GATE_WINDOW = "heavy gate requires an allowed window"
HEAVY_GATE_DOMAIN_OWNER = "heavy gate requires a domain owner"
HEAVY_GATE_APPROVER = "heavy gate requires an approver"

_HEAVY_BLOCKER_REASON = {
    "distinct_approvers": HEAVY_GATE_DISTINCT,
    "simulation": HEAVY_GATE_SIMULATION,
    "backup": HEAVY_GATE_BACKUP,
    "window": HEAVY_GATE_WINDOW,
    "domain_owner": HEAVY_GATE_DOMAIN_OWNER,
}


def _gate_field(op: Mapping[str, Any], params: Mapping[str, Any], *keys: str) -> Any:
    gate = op.get("heavy_gate") if isinstance(op.get("heavy_gate"), Mapping) else None
    sources: list[Mapping[str, Any]] = [op, params]
    if isinstance(gate, Mapping):
        sources.insert(0, gate)
    for key in keys:
        for source in sources:
            if key in source:
                return source[key]
    return None


def _gate_approvals(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    records: list[Mapping[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            record = dict(item)
            if "decision" not in record:
                record["decision"] = "approve"
            if not _text(record.get("approver_id")) and _text(record.get("user_id")):
                record["approver_id"] = _text(record.get("user_id"))
            records.append(record)
            continue
        token = _text(item)
        if token:
            records.append({"approver_id": token, "decision": "approve"})
    return records


def heavy_gate_refusal(
    op: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> str | None:
    """Named reason when a heavy-R4 op is missing a passed heavy gate.

    Inputs: one change-set op. Gate evidence may sit on the op, in ``params``,
    or under ``heavy_gate``: ``approvals`` / ``approvers``, ``requester_id`` /
    ``requester``, ``simulation_passed``, ``backup_id``, ``allowed_window``,
    ``now``, ``protected``, and ``environment``.
    Output: ``None`` when the op is not heavy, or when the same gate the
    approval store uses is met. Otherwise a named blocker reason. Hard-stop
    ops are not opened here. ``module.uninstall`` stays prohibited elsewhere.
    Side effects: none. Reuses ``policy_decision(..., heavy=True)`` and
    ``production_r3_approval_met``.
    """
    body = op if isinstance(op, Mapping) else {}
    if r4_gate(dict(body)) != "heavy":
        return None
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    env = _text(_gate_field(body, params, "environment")) or "production"
    decision = policy_decision("R4", env, heavy=True)
    approvals = _gate_approvals(_gate_field(body, params, "approvals", "approvers", "approved_by"))
    requester = _text(_gate_field(body, params, "requester_id", "requester", "requested_by"))
    if env.lower() == "staging":
        needed = int(decision.get("approvers") or 0)
        if distinct_approver_count(list(approvals)) >= needed:
            return None
        return HEAVY_GATE_APPROVER if needed <= 1 else HEAVY_GATE_DISTINCT
    clock = now
    raw_now = _gate_field(body, params, "now")
    if clock is None and raw_now is not None:
        clock = _parse_time(raw_now)
    if clock is None:
        clock = datetime.now(timezone.utc)
    protected = bool(_gate_field(body, params, "protected")) or bool(decision.get("domain_owner"))
    if not protected:
        protected = target_requires_domain_owner([dict(body)])
    outcome = production_r3_approval_met(
        decision,
        list(approvals),
        requester_id=requester,
        protected=protected,
        simulation_passed=_gate_field(body, params, "simulation_passed") is True,
        backup_id=_gate_field(body, params, "backup_id"),
        allowed_window=_gate_field(body, params, "allowed_window"),
        now=clock,
    )
    if outcome["met"]:
        return None
    for blocker in outcome["blockers"]:
        if blocker == "not_heavy_r4":
            continue
        reason = _HEAVY_BLOCKER_REASON.get(blocker)
        if reason:
            return reason
    return HEAVY_GATE_DISTINCT
