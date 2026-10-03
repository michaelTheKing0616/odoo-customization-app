"""Critic checklist. A verdict cannot waive policy.

The checklist is coverage, scope creep, assumptions that should be
questions, missed dependents, rollback realism, security, business red
flags, and wording. The critic runs for Tier A when risk is R2 or higher,
or when there are at least 5 ops. An approve verdict does not change
``policy_decision``. R4 stays denied. The critic cannot lower risk, skip
approval, or mark a plan verified. This module does not call a model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.changeset.ops import get_op
from app.changeset.policy import policy_decision, risk_of

CHECKLIST = (
    "coverage",
    "scope creep",
    "assumptions that should be questions",
    "missed dependents",
    "rollback realism",
    "security",
    "business red flags",
    "wording",
)

_RISK_ORDER = ("R0", "R1", "R2", "R3", "R4")
_RUN_FROM_RISK = "R2"
_RUN_FROM_OPS = 5
_VERDICTS = frozenset({"approve", "revise"})
_SENSITIVE_TOPICS = frozenset({"financial", "hr", "legal"})
_BUSINESS_OP_TYPES = frozenset({"data.delete", "data.merge", "module.uninstall"})
_DELETE_OP_TYPES = frozenset({"data.delete", "field.delete", "module.uninstall"})
_ACCESS_OP_TYPES = frozenset(
    {"access.create", "access.update", "rule.create", "rule.update"}
)


@dataclass(frozen=True, slots=True)
class CriticFinding:
    """One checklist note. It is not an approval and not a risk class."""

    item: str
    detail: str

    def __post_init__(self) -> None:
        if self.item not in CHECKLIST:
            raise ValueError(f"unknown checklist item: {self.item}")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("finding detail must be a non-empty string")


@dataclass(frozen=True, slots=True)
class CriticPlan:
    """Structured plan the checklist can read.

    Inputs are the ops, the goal, models the request named, assumptions,
    questions already asked, dependents the planner accounted for,
    dependents the ops reference, human labels, whether the plan claims
    a full rollback, the topic token, and the environment.
    A ``risk`` key on an op is not an input to the risk class.
    """

    ops: tuple[Mapping[str, Any], ...] = ()
    goal: str = ""
    requested_models: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()
    dependents: tuple[str, ...] = ()
    referenced_dependents: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    claims_full_rollback: bool = False
    topic: str = "general"
    environment: str = "production"


@dataclass(frozen=True, slots=True)
class CriticResult:
    """Checklist outcome beside an unchanged policy decision.

    ``policy`` is the engine decision for ``risk``. ``verified`` is false.
    ``waivers_ignored`` names critic attempts that were not applied.
    """

    ran: bool
    verdict: str
    findings: tuple[CriticFinding, ...]
    risk: str
    policy: dict[str, bool | int]
    verified: bool = False
    waivers_ignored: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.verified:
            raise ValueError("the critic cannot mark a plan verified")


def critic_runs(*, tier: str | None, risk: str, op_count: int) -> bool:
    """Whether this plan must go through the critic.

    Inputs: model tier, engine risk class, and op count.
    Outputs: True only for tier A when risk is R2 or higher, or when
    there are at least 5 ops. Any other tier, including an unset tier,
    is False.
    Side effects: none.
    Raises ValueError when op_count is not a non-negative int.
    """
    if isinstance(op_count, bool) or not isinstance(op_count, int):
        raise ValueError("op_count must be an int")
    if op_count < 0:
        raise ValueError("op_count must be zero or greater")
    if tier != "A" or risk not in _RISK_ORDER:
        return False
    high = _RISK_ORDER.index(risk) >= _RISK_ORDER.index(_RUN_FROM_RISK)
    return high or op_count >= _RUN_FROM_OPS


def plan_risk(ops: Sequence[Mapping[str, Any]]) -> str:
    """Engine risk for the ops.

    Inputs: change-set ops. A ``risk`` key on an op is ignored.
    Outputs: the highest class from ``risk_of``, or R0 when there are no ops.
    Side effects: none. Does not call a model.
    Raises TypeError when ``ops`` is a string or bytes.
    """
    prepared = _prepare_ops(ops)
    if not prepared:
        return "R0"
    return max((risk_of(op) for op in prepared), key=_RISK_ORDER.index)


def review(plan: CriticPlan) -> tuple[CriticFinding, ...]:
    """Run the checklist.

    Inputs: a CriticPlan.
    Outputs: findings in checklist order. An empty tuple means the
    checklist found nothing. The verdict is not decided here.
    Side effects: none. Does not call a model and does not read policy.
    """
    ops = _prepare_ops(plan.ops)
    risk = plan_risk(ops)
    findings: list[CriticFinding] = []
    findings.extend(_coverage(plan, ops))
    findings.extend(_scope(plan, ops))
    findings.extend(_assumptions(plan, risk))
    findings.extend(_dependents(plan))
    findings.extend(_rollback(plan, ops))
    findings.extend(_security(ops))
    findings.extend(_business(plan, ops))
    findings.extend(_wording(plan, ops))
    return tuple(findings)


def policy_stands(
    risk: str,
    environment: str,
    *,
    verdict: str,
    claimed_risk: str | None = None,
    skip_approval: bool = False,
    mark_verified: bool = False,
) -> dict[str, bool | int]:
    """Return the policy decision and ignore the critic.

    Inputs: the engine risk class, the environment, and critic attempts.
    ``verdict`` may be approve. ``claimed_risk`` is not the risk class.
    ``skip_approval`` does not change the approver count. ``mark_verified``
    is not a policy field.
    Outputs: ``policy_decision`` for ``risk`` and ``environment`` at the
    default autonomy. R4 stays denied.
    Side effects: none. Does not call a model and does not enable L4.
    """
    _ = (verdict, claimed_risk, skip_approval, mark_verified)
    return policy_decision(risk, environment)


def judge(
    plan: CriticPlan,
    *,
    tier: str | None,
    verdict: str | None = None,
    claimed_risk: str | None = None,
    skip_approval: bool = False,
    mark_verified: bool = False,
) -> CriticResult:
    """Review a plan when the tier rule says so, then leave policy alone.

    Inputs: a CriticPlan, the model tier, and optional critic attempts.
    ``verdict`` may be approve or revise. Risk is ``plan_risk`` of the ops.
    Outputs: whether the critic ran, the recorded verdict, findings when
    it ran, the engine risk, the unchanged policy decision, and verified
    false. Attempts to lower risk, skip approval, mark the plan verified,
    or approve an R4 plan are listed on ``waivers_ignored`` and are not
    applied.
    Side effects: none. Does not call a model and does not enable L4.
    Raises ValueError for a verdict other than approve or revise, or for
    an environment that is not a non-empty string.
    """
    if verdict is not None and verdict not in _VERDICTS:
        raise ValueError("verdict must be approve or revise")
    if not isinstance(plan.environment, str) or not plan.environment.strip():
        raise ValueError("environment must be a non-empty string")
    ops = _prepare_ops(plan.ops)
    risk = plan_risk(ops)
    ran = critic_runs(tier=tier, risk=risk, op_count=len(ops))
    findings = review(plan) if ran else ()
    if not ran:
        recorded = "not_run"
    elif verdict is not None:
        recorded = verdict
    elif findings:
        recorded = "revise"
    else:
        recorded = "approve"
    policy = policy_stands(
        risk,
        plan.environment,
        verdict=recorded,
        claimed_risk=claimed_risk,
        skip_approval=skip_approval,
        mark_verified=mark_verified,
    )
    ignored: list[str] = []
    if claimed_risk is not None:
        ignored.append("claimed_risk")
    if skip_approval:
        ignored.append("skip_approval")
    if mark_verified:
        ignored.append("mark_verified")
    if verdict == "approve":
        ignored.append("approve")
    return CriticResult(
        ran=ran,
        verdict=recorded,
        findings=findings,
        risk=risk,
        policy=policy,
        verified=False,
        waivers_ignored=tuple(ignored),
    )


def _prepare_ops(ops: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if isinstance(ops, (str, bytes)):
        raise TypeError("ops must be a sequence of objects")
    return tuple(_as_op(op) for op in ops)


def _as_op(op: object) -> dict[str, Any]:
    """Copy type and params. A caller-supplied risk key is dropped."""
    if not isinstance(op, Mapping):
        return {"type": "", "params": {}}
    params = op.get("params")
    body = dict(params) if isinstance(params, Mapping) else {}
    return {"type": str(op.get("type") or ""), "params": body}


def _models(ops: Sequence[Mapping[str, Any]]) -> set[str]:
    found: set[str] = set()
    for op in ops:
        model = _model_of(op)
        if model:
            found.add(model)
    return found


def _model_of(op: Mapping[str, Any]) -> str:
    params = op.get("params")
    if not isinstance(params, Mapping):
        return ""
    model = params.get("model")
    if isinstance(model, str):
        return model.strip()
    return ""


def _nonempty(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(value.strip() for value in values if isinstance(value, str) and value.strip())


def _coverage(plan: CriticPlan, ops: Sequence[Mapping[str, Any]]) -> list[CriticFinding]:
    item = "coverage"
    found: list[CriticFinding] = []
    if not plan.goal.strip():
        found.append(CriticFinding(item, "The goal is empty."))
    present = _models(ops)
    if ops and not _nonempty(plan.requested_models):
        found.append(CriticFinding(item, "The request names no models."))
    for model in _nonempty(plan.requested_models):
        if model not in present:
            found.append(CriticFinding(item, f"{model} is not in the ops."))
    return found


def _scope(plan: CriticPlan, ops: Sequence[Mapping[str, Any]]) -> list[CriticFinding]:
    requested = set(_nonempty(plan.requested_models))
    if not requested:
        return []
    found: list[CriticFinding] = []
    for op in ops:
        model = _model_of(op)
        if model and model not in requested:
            found.append(CriticFinding("scope creep", f"{model} is outside the request."))
    return found


def _assumptions(plan: CriticPlan, risk: str) -> list[CriticFinding]:
    if risk not in _RISK_ORDER:
        return []
    if _RISK_ORDER.index(risk) < _RISK_ORDER.index(_RUN_FROM_RISK):
        return []
    assumptions = _nonempty(plan.assumptions)
    if not assumptions or _nonempty(plan.questions):
        return []
    return [
        CriticFinding(
            "assumptions that should be questions",
            f"Ask instead of assuming: {text}",
        )
        for text in assumptions
    ]


def _dependents(plan: CriticPlan) -> list[CriticFinding]:
    accounted = set(_nonempty(plan.dependents))
    return [
        CriticFinding(
            "missed dependents",
            f"{name} is referenced and not accounted for.",
        )
        for name in _nonempty(plan.referenced_dependents)
        if name not in accounted
    ]


def _reversible(op: Mapping[str, Any]) -> str:
    entry = get_op(str(op.get("type") or ""))
    if entry is None:
        return "N"
    return entry.reversible


def _rollback(plan: CriticPlan, ops: Sequence[Mapping[str, Any]]) -> list[CriticFinding]:
    found: list[CriticFinding] = []
    for op in ops:
        kind = _reversible(op)
        if kind == "E":
            continue
        limit = "not reversible" if kind == "N" else "a soft inverse only"
        claim = " The plan claimed a full rollback." if plan.claims_full_rollback else ""
        op_type = str(op.get("type") or "unknown")
        found.append(CriticFinding("rollback realism", f"{op_type} is {limit}.{claim}"))
    return found


def _security_detail(op: Mapping[str, Any]) -> str:
    op_type = str(op.get("type") or "")
    params = op.get("params")
    body = params if isinstance(params, Mapping) else {}
    if op_type in _DELETE_OP_TYPES:
        return f"{op_type} needs a security review."
    if op_type == "user.groups.assign" and body.get("admin"):
        return "Assigning admin is a security finding."
    if op_type == "company.update" and body.get("lock_date"):
        return "Setting a lock date is a security finding."
    if op_type in _ACCESS_OP_TYPES and not _group_name(body):
        return f"{op_type} has no group."
    if get_op(op_type) is None:
        return "The op type is not in the catalog."
    return ""


def _group_name(params: Mapping[str, Any]) -> str:
    group = params.get("group")
    if isinstance(group, str):
        return group.strip()
    return ""


def _security(ops: Sequence[Mapping[str, Any]]) -> list[CriticFinding]:
    found: list[CriticFinding] = []
    for op in ops:
        detail = _security_detail(op)
        if detail:
            found.append(CriticFinding("security", detail))
    return found


def _business(plan: CriticPlan, ops: Sequence[Mapping[str, Any]]) -> list[CriticFinding]:
    found: list[CriticFinding] = []
    if plan.topic in _SENSITIVE_TOPICS:
        found.append(CriticFinding("business red flags", f"The topic is {plan.topic}."))
    for op in ops:
        op_type = str(op.get("type") or "")
        if op_type in _BUSINESS_OP_TYPES:
            found.append(CriticFinding("business red flags", f"{op_type} is a business red flag."))
    return found


def _wording(plan: CriticPlan, ops: Sequence[Mapping[str, Any]]) -> list[CriticFinding]:
    found: list[CriticFinding] = []
    for index, op in enumerate(ops):
        op_type = str(op.get("type") or "")
        label = plan.labels[index].strip() if index < len(plan.labels) else ""
        if not label or label.lower() == op_type.lower():
            found.append(CriticFinding("wording", f"Op {index} has no human wording."))
    return found
