"""Deterministic verification checks (INV-16).

The observation is supplied by the caller. This module does not call Odoo,
does not send mail, and does not render a live view. A ``model_success`` flag
and any success claim inside the observation are ignored. Check evidence is
the only source of the outcome.

A failed check rolls the change-set back when plan risk is R2 or higher.
Below that, the outcome is NEEDS_HUMAN and carries a runbook link.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.changeset.data_ops import SAMPLE_LIMIT
from app.changeset.policy import risk_of

CHECK_POSTCONDITIONS = "postconditions"
CHECK_FINGERPRINT = "fingerprint_diff"
CHECK_VIEW_REQUESTER = "view_render_requester"
CHECK_VIEW_LOW_PRIVILEGE = "view_render_low_privilege"
CHECK_VIEW_PORTAL = "view_render_portal"
CHECK_SMOKE = "smoke_probes"
CHECK_ACCESS = "access_regression"
CHECK_MAIL = "outbound_mail"
CHECK_DATA = "data_counts_and_samples"

CHECKS: tuple[str, ...] = (
    CHECK_POSTCONDITIONS,
    CHECK_FINGERPRINT,
    CHECK_VIEW_REQUESTER,
    CHECK_VIEW_LOW_PRIVILEGE,
    CHECK_VIEW_PORTAL,
    CHECK_SMOKE,
    CHECK_ACCESS,
    CHECK_MAIL,
    CHECK_DATA,
)

_VIEW_PERSONA: dict[str, str] = {
    CHECK_VIEW_REQUESTER: "requester",
    CHECK_VIEW_LOW_PRIVILEGE: "low_privilege",
    CHECK_VIEW_PORTAL: "portal",
}

REQUIRED_SMOKE: tuple[str, ...] = ("record_read", "action_resolves")

# Runbook 4 in docs/plans/next-phase/11_LOGGING_AUDIT_OBSERVABILITY.md §8.
RUNBOOK_VERIFY_FAILED = "docs/runbooks/4-failed-rollback.md"

_RISK_ORDER = ("R0", "R1", "R2", "R3", "R4")
_ROLLBACK_FLOOR = "R2"

_SCHEMA_POSTCONDITIONS: dict[str, tuple[str, ...]] | None = None
_ROLLBACK_LOG: list[dict[str, Any]] = []


def reset_verification_log() -> None:
    """Drop recorded rollbacks.

    Inputs: none.
    Outputs: none.
    Side effects: clears the in-process rollback log. Does not call Odoo.
    """
    _ROLLBACK_LOG.clear()


def recorded_rollbacks() -> list[dict[str, Any]]:
    """Return rollback records this process has ordered.

    Inputs: none.
    Outputs: a copy of the log. Each item has ``risk`` and ``compensations``.
    Side effects: none.
    """
    return [dict(item) for item in _ROLLBACK_LOG]


def postconditions_for(op: Mapping[str, Any]) -> tuple[str, ...]:
    """Names that must hold after one op.

    Inputs: one change-set op. Schema ops use the schema contract names.
    Every other known or unknown type uses ``"<type>: effect is present"``.
    Outputs: at least one name.
    Side effects: may import schema contracts once and cache them.
    """
    op_type = str(op.get("type") or "")
    table = _schema_postconditions()
    named = table.get(op_type)
    if named:
        return named
    label = op_type or "op"
    return (f"{label}: effect is present",)


def verify(
    changeset: list[dict[str, Any]],
    observation: Mapping[str, Any],
    *,
    model_success: bool | None = None,
) -> dict[str, Any]:
    """Run every verification check and decide the outcome.

    Inputs: the change-set, a fake observation, and an optional model claim.
    The claim and any ``status`` or ``verified`` key on the observation do
    not change the result. Plan risk comes from ``risk_of``. A risk key on
    an op or on the observation does not lower it.
    Outputs: a report. ``verified`` is true only when every check passed.
    Risk at or above R2 with a failed check records a reverse compensation
    and returns ``ROLLED_BACK``. A lower risk returns ``NEEDS_HUMAN`` with
    ``runbook``. ``live_view``, ``mail_sent``, and ``contacted_odoo`` stay
    false. This function does not render a view, send mail, or open a socket.
    Side effects: appends one rollback record when the outcome is
    ``ROLLED_BACK``.
    """
    checks = _run_checks(changeset, observation)
    failed = [item["name"] for item in checks if not item["passed"]]
    risk = _plan_risk(changeset)
    verified = not failed
    rolled_back = False
    compensations: list[dict[str, Any]] = []
    runbook: str | None = None
    if verified:
        status = "VERIFIED"
    elif _rank(risk) >= _rank(_ROLLBACK_FLOOR):
        status = "ROLLED_BACK"
        rolled_back = True
        compensations = _compensations(changeset)
        _ROLLBACK_LOG.append({"risk": risk, "compensations": list(compensations), "status": status})
    else:
        status = "NEEDS_HUMAN"
        runbook = RUNBOOK_VERIFY_FAILED
    return {
        "status": status,
        "verified": verified,
        "rolled_back": rolled_back,
        "risk": risk,
        "runbook": runbook,
        "checks": checks,
        "failed": failed,
        "compensations": compensations,
        "model_success": model_success,
        "model_success_ignored": True,
        "live_view": False,
        "mail_sent": 0,
        "contacted_odoo": False,
    }


def _schema_postconditions() -> dict[str, tuple[str, ...]]:
    global _SCHEMA_POSTCONDITIONS
    if _SCHEMA_POSTCONDITIONS is None:
        from app.changeset.schema_ops import schema_contracts

        _SCHEMA_POSTCONDITIONS = {item.type: item.postconditions for item in schema_contracts()}
    return _SCHEMA_POSTCONDITIONS


def _plan_risk(changeset: list[dict[str, Any]]) -> str:
    best = "R0"
    for op in changeset:
        current = risk_of(op, document=changeset)
        if _rank(current) > _rank(best):
            best = current
    return best


def _rank(risk: str) -> int:
    try:
        return _RISK_ORDER.index(risk)
    except ValueError:
        return _RISK_ORDER.index("R4")


def _compensations(changeset: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"index": index, "type": str(op.get("type") or "")}
        for index, op in reversed(list(enumerate(changeset)))
    ]


def _run_checks(changeset: list[dict[str, Any]], observation: Mapping[str, Any]) -> list[dict[str, Any]]:
    runners = {
        CHECK_POSTCONDITIONS: _check_postconditions,
        CHECK_FINGERPRINT: _check_fingerprint,
        CHECK_SMOKE: _check_smoke,
        CHECK_ACCESS: _check_access,
        CHECK_MAIL: _check_mail,
        CHECK_DATA: _check_data,
    }
    results: list[dict[str, Any]] = []
    for name in CHECKS:
        if name in _VIEW_PERSONA:
            passed, detail = _check_view(observation, _VIEW_PERSONA[name])
        else:
            passed, detail = runners[name](changeset, observation)
        results.append({"name": name, "passed": passed, "detail": detail})
    return results


def _check_postconditions(
    changeset: list[dict[str, Any]],
    observation: Mapping[str, Any],
) -> tuple[bool, str]:
    if not changeset:
        return True, "no ops"
    evidence = observation.get("postconditions")
    if not isinstance(evidence, Mapping):
        return False, "postconditions are missing"
    for index, op in enumerate(changeset):
        slot = _index_slot(evidence, index)
        if not isinstance(slot, Mapping):
            return False, f"op {index} has no postcondition evidence"
        for name in postconditions_for(op):
            if slot.get(name) is not True:
                return False, f"op {index} failed {name}"
    return True, "postconditions hold"


def _check_fingerprint(
    _changeset: list[dict[str, Any]],
    observation: Mapping[str, Any],
) -> tuple[bool, str]:
    raw = observation.get("fingerprint")
    if not isinstance(raw, Mapping):
        return False, "fingerprint diff is missing"
    before = raw.get("before")
    after = raw.get("after")
    expected = raw.get("expected_after")
    if not all(isinstance(item, str) and item for item in (before, after, expected)):
        return False, "fingerprint diff is incomplete"
    if after != expected:
        return False, "fingerprint diff does not match"
    return True, "fingerprint diff matches"


def _check_view(observation: Mapping[str, Any], persona: str) -> tuple[bool, str]:
    views = observation.get("views")
    if not isinstance(views, Mapping):
        return False, f"{persona} view evidence is missing"
    slot = views.get(persona)
    if not isinstance(slot, Mapping):
        return False, f"{persona} view evidence is missing"
    if slot.get("live") is True:
        return False, f"{persona} live view was not rendered"
    error = slot.get("error")
    if slot.get("rendered") is not True or error not in (None, ""):
        return False, f"{persona} view did not render"
    return True, f"{persona} view rendered from the fake"


def _check_smoke(
    _changeset: list[dict[str, Any]],
    observation: Mapping[str, Any],
) -> tuple[bool, str]:
    raw = observation.get("smoke")
    if not isinstance(raw, list):
        return False, "smoke probes are missing"
    by_name: dict[str, Any] = {}
    for item in raw:
        if isinstance(item, Mapping) and isinstance(item.get("name"), str):
            by_name[item["name"]] = item
    for name in REQUIRED_SMOKE:
        probe = by_name.get(name)
        if not isinstance(probe, Mapping) or probe.get("passed") is not True:
            return False, f"smoke probe {name} failed"
    return True, "smoke probes passed"


def _check_access(
    _changeset: list[dict[str, Any]],
    observation: Mapping[str, Any],
) -> tuple[bool, str]:
    raw = observation.get("access")
    if not isinstance(raw, Mapping):
        return False, "access evidence is missing"
    before = _permission_set(raw.get("before"))
    after = _permission_set(raw.get("after"))
    if before is None or after is None:
        return False, "access evidence is incomplete"
    lost = before - after
    if lost:
        return False, "access regression"
    return True, "no access regression"


def _check_mail(
    _changeset: list[dict[str, Any]],
    observation: Mapping[str, Any],
) -> tuple[bool, str]:
    raw = observation.get("mail")
    if not isinstance(raw, Mapping):
        return False, "mail counts are missing"
    before = _nonneg_int(raw.get("before"))
    after = _nonneg_int(raw.get("after"))
    if before is None or after is None:
        return False, "mail counts are incomplete"
    if after > before:
        return False, "new outbound mail"
    return True, "no new outbound mail"


def _check_data(
    _changeset: list[dict[str, Any]],
    observation: Mapping[str, Any],
) -> tuple[bool, str]:
    raw = observation.get("data")
    if not isinstance(raw, Mapping):
        return False, "data counts and samples are missing"
    counts = raw.get("counts")
    samples = raw.get("samples")
    if not isinstance(counts, Mapping) or not isinstance(samples, Mapping):
        return False, "data counts and samples are missing"
    for model, row in counts.items():
        if not isinstance(row, Mapping):
            return False, f"{model} count is missing"
        expected = _nonneg_int(row.get("expected"))
        actual = _nonneg_int(row.get("actual"))
        if expected is None or actual is None:
            return False, f"{model} count is incomplete"
        if actual != expected:
            return False, f"{model} count does not match"
    for model, rows in samples.items():
        if not isinstance(rows, list):
            return False, f"{model} sample is missing"
        if len(rows) > SAMPLE_LIMIT:
            return False, f"{model} sample exceeds the cap"
    return True, "counts match and samples are within the cap"


def _index_slot(evidence: Mapping[str, Any], index: int) -> Any:
    if index in evidence:
        return evidence[index]
    return evidence.get(str(index))


def _permission_set(snapshot: Any) -> set[tuple[str, str, str]] | None:
    if not isinstance(snapshot, Mapping):
        return None
    rights: set[tuple[str, str, str]] = set()
    for group, models in snapshot.items():
        if not isinstance(models, Mapping):
            return None
        for model, perm in models.items():
            values = perm if isinstance(perm, list) else [perm]
            if not isinstance(values, list):
                return None
            for item in values:
                if not isinstance(item, str) or not item:
                    return None
                rights.add((str(group), str(model), item))
    return rights


def _nonneg_int(value: Any) -> int | None:
    if type(value) is not int or value < 0:
        return None
    return value
