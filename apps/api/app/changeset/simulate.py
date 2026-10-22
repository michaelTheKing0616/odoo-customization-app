"""Change-set simulation. Four in-process modes. None open a socket or call Odoo.

Static always runs. A Bridge in-place dry-run is only for ops the catalog does
not mark DDL, and it mutates a scratch copy that is discarded. Staging is a
neutralized in-memory clone for DDL ops and for plan risk at or above R3.
Synthetic record tests use generated rows, not a customer database.

A failed run returns the plan to planning (`PLAN`) and drops any recorded
success. Production apply is refused without a recorded success unless the
policy decision allows an R1 direct apply (INV-06).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.changeset.ops import get_op
from app.changeset.policy import policy_decision, risk_of

MODE_STATIC = "static"
MODE_BRIDGE_INPLACE = "bridge_inplace"
MODE_STAGING = "staging"
MODE_SYNTHETIC = "synthetic"
MODES = (MODE_STATIC, MODE_BRIDGE_INPLACE, MODE_STAGING, MODE_SYNTHETIC)

PLANNING_PHASE = "PLAN"
PRESENT_PHASE = "PRESENT"

_RISK_ORDER = ("R0", "R1", "R2", "R3", "R4")
_STAGING_FLOOR = "R3"


class SimulationRequired(Exception):
    """Production apply has no recorded successful simulation."""

    code = "simulation_required"

    def __init__(self, message: str = "production apply requires a recorded simulation") -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class ModeResult:
    """Outcome of one simulation mode. `live` stays false. No socket is opened."""

    mode: str
    passed: bool
    path_taken: bool
    detail: str
    target: str
    op_types: tuple[str, ...]
    writes: int = 0
    rolled_back: bool = False
    socket_opened: bool = False
    live: bool = False
    contacted_odoo: bool = False
    copied_customer_database: bool = False
    synthetic_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SimulationReport:
    """Full simulation. `recorded` is true only after every selected mode passes."""

    plan_id: str
    plan_hash: str
    risk: str
    passed: bool
    phase: str
    returned_to_planning: bool
    recorded: bool
    selected: tuple[str, ...]
    modes: tuple[ModeResult, ...]
    socket_opened: bool = False
    live: bool = False
    contacted_odoo: bool = False


_LEDGER: dict[str, SimulationReport] = {}


def reset_simulations() -> None:
    """Clear recorded simulations.

    Inputs: none.
    Outputs: none.
    Side effects: empties the in-process ledger. Does not contact Odoo.
    """
    _LEDGER.clear()


def plan_key(ops: list[dict[str, Any]], risk: str) -> str:
    """Stable id for a plan at a resolved risk.

    Inputs: ops and a risk class.
    Outputs: 16 hex characters.
    Side effects: none.
    """
    payload = {"ops": ops, "risk": risk}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def plan_hash(ops: list[dict[str, Any]]) -> str:
    """Ops fingerprint used as the recorded simulation plan hash.

    Inputs: the change-set ops list.
    Outputs: 16 hex characters. Same shape the executor stores as plan_hash
    (canonical JSON of the ops). Risk and assumptions are not included.
    Side effects: none.
    """
    raw = json.dumps(ops, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def plan_risk(ops: list[dict[str, Any]]) -> str:
    """Highest catalog risk on the plan.

    Inputs: ops. An empty plan is R0.
    Outputs: R0–R4 from `risk_of`. A caller-supplied risk on an op is ignored.
    Side effects: none.
    """
    best = "R0"
    for op in ops:
        current = risk_of(op)
        if _rank(current) > _rank(best):
            best = current
    return best


def select_modes(ops: list[dict[str, Any]], risk: str) -> tuple[str, ...]:
    """Modes for this plan.

    Inputs: ops and the resolved plan risk.
    Outputs: static, then Bridge in-place when any op is non-DDL, then staging
    when any op is DDL or risk is R3 or R4, then synthetic record tests.
    Side effects: none. Does not contact Odoo.
    """
    resolved = _require_risk(risk)
    modes = [MODE_STATIC]
    if not ops or any(not _is_ddl(op) for op in ops):
        modes.append(MODE_BRIDGE_INPLACE)
    if any(_is_ddl(op) for op in ops) or _rank(resolved) >= _rank(_STAGING_FLOOR):
        modes.append(MODE_STAGING)
    modes.append(MODE_SYNTHETIC)
    return tuple(modes)


def policy_allows_r1_direct(risk: str, decision: Mapping[str, Any]) -> bool:
    """Whether policy allows a production R1 apply with no recorded simulation.

    Inputs: resolved risk and a policy decision.
    Outputs: True only for R1 when the decision allows apply, does not deny,
    and `needs_simulation` is false. A missing `needs_simulation` stays required.
    The default production R1 decision keeps `needs_simulation` true, so this
    stays false until a decision explicitly allows the narrow class.
    Side effects: none.
    """
    if risk != "R1":
        return False
    if bool(decision.get("deny", True)):
        return False
    if not bool(decision.get("allow")):
        return False
    return not bool(decision.get("needs_simulation", True))


def recorded_simulation(plan_id: str) -> SimulationReport | None:
    """Return a passing record for this plan id.

    Inputs: plan id from `plan_key`.
    Outputs: the report, or None when nothing passing is recorded.
    Side effects: none.
    """
    found = _LEDGER.get(plan_id)
    if found is None or not found.passed:
        return None
    return found


def run_mode(
    mode: str,
    ops: list[dict[str, Any]],
    *,
    records: dict[str, Any] | None = None,
    fail: bool = False,
    staging_port: Any | None = None,
) -> ModeResult:
    """Run one mode against copies of `records`.

    Inputs: mode name, ops, an optional in-memory record dict, whether the
    mode should fail after it is entered, and an optional fake staging port.
    The staging port is only used by the staging mode. It must not open a
    socket or create a real database.
    Outputs: a ModeResult. Bridge in-place with a DDL op returns `path_taken`
    false and `ddl_no_inplace` without mutating `records`.
    Side effects: none on `records` or on the ledger. Does not open a socket.
    Raises ValueError for an unknown mode.
    """
    if mode not in MODES:
        raise ValueError(f"unknown simulation mode: {mode}")
    store = deepcopy(records) if records is not None else {}
    snapshot = deepcopy(store)
    outcome = _dispatch(mode, ops, store, fail=fail, staging_port=staging_port)
    if store != snapshot:
        return _result(
            mode,
            passed=False,
            path_taken=outcome.path_taken,
            detail="caller_store_mutated",
            target=outcome.target,
            op_types=outcome.op_types,
        )
    return outcome


def simulate(
    ops: list[dict[str, Any]],
    *,
    risk: str | None = None,
    records: dict[str, Any] | None = None,
    fail_mode: str | None = None,
    staging_port: Any | None = None,
) -> SimulationReport:
    """Run every selected mode. Stop on the first failure and return to planning.

    Inputs: ops, an optional risk (raised to the catalog risk when lower),
    an optional in-memory record dict, an optional mode name to fail, and an
    optional fake staging port for the staging mode (tests only; no real DB).
    Outputs: a report. `phase` is `PLAN` when a mode fails and `PRESENT` when
    every selected mode passes. `plan_hash` is the ops fingerprint. `live` is
    false.
    Side effects: stores the report on success and drops any prior record for
    this plan on failure. Does not open a socket or call Odoo.
    Raises ValueError when `fail_mode` is not one of the selected modes, or
    when `risk` is not a known class.
    """
    resolved = resolve_risk(ops, risk)
    selected = select_modes(ops, resolved)
    if fail_mode is not None and fail_mode not in selected:
        raise ValueError(f"fail_mode {fail_mode!r} is not selected")
    key = plan_key(ops, resolved)
    fingerprint = plan_hash(ops)
    executed: list[ModeResult] = []
    for mode in selected:
        subset = _ops_for_mode(mode, ops, resolved)
        outcome = run_mode(
            mode,
            subset,
            records=records,
            fail=fail_mode == mode,
            staging_port=staging_port if mode == MODE_STAGING else None,
        )
        executed.append(outcome)
        if not outcome.passed:
            _LEDGER.pop(key, None)
            return _report(
                plan_id=key,
                plan_hash=fingerprint,
                risk=resolved,
                passed=False,
                phase=PLANNING_PHASE,
                returned_to_planning=True,
                recorded=False,
                selected=selected,
                modes=tuple(executed),
            )
    report = _report(
        plan_id=key,
        plan_hash=fingerprint,
        risk=resolved,
        passed=True,
        phase=PRESENT_PHASE,
        returned_to_planning=False,
        recorded=True,
        selected=selected,
        modes=tuple(executed),
    )
    _LEDGER[key] = report
    return report


def guard_production_apply(
    ops: list[dict[str, Any]],
    *,
    environment: str,
    risk: str | None = None,
    decision: Mapping[str, Any] | None = None,
) -> None:
    """Refuse production apply when no successful simulation is recorded.

    Inputs: ops, environment, optional risk, optional policy decision.
    Risk is resolved the same way as `simulate`. A missing decision uses
    `policy_decision` for that risk on production.
    Outputs: None when this gate allows the apply to proceed. This function
    does not apply the plan.
    Side effects: none. Raises SimulationRequired for production when there is
    no recorded success for this exact plan hash at the resolved risk, the
    decision is not an R1 direct allowance, and the plan is not an R0 plan
    whose decision does not require a simulation (INV-06).
    Does not open a socket or call Odoo.
    """
    if environment.strip().lower() != "production":
        return
    resolved = resolve_risk(ops, risk)
    key = plan_key(ops, resolved)
    fingerprint = plan_hash(ops)
    found = recorded_simulation(key)
    if (
        found is not None
        and found.passed
        and found.risk == resolved
        and found.plan_hash == fingerprint
    ):
        return
    chosen = decision if decision is not None else policy_decision(resolved, "production")
    if policy_allows_r1_direct(resolved, chosen):
        return
    if _r0_skips_simulation(resolved, chosen):
        return
    raise SimulationRequired


def resolve_risk(ops: list[dict[str, Any]], risk: str | None) -> str:
    """Catalog risk, or the caller risk when that class is higher.

    Inputs: ops and an optional risk class.
    Outputs: R0–R4. A caller value below the catalog risk is discarded.
    Side effects: none. Raises ValueError for an unknown class.
    """
    catalog = plan_risk(ops)
    if risk is None:
        return catalog
    supplied = _require_risk(risk)
    if _rank(supplied) < _rank(catalog):
        return catalog
    return supplied


def _dispatch(
    mode: str,
    ops: list[dict[str, Any]],
    store: dict[str, Any],
    *,
    fail: bool,
    staging_port: Any | None = None,
) -> ModeResult:
    if mode == MODE_BRIDGE_INPLACE and any(_is_ddl(op) for op in ops):
        return _result(
            mode,
            passed=False,
            path_taken=False,
            detail="ddl_no_inplace",
            target="none",
            op_types=tuple(_op_type(op) for op in ops if _is_ddl(op)),
        )
    if fail:
        return _result(
            mode,
            passed=False,
            path_taken=True,
            detail="simulation_failed",
            target=_target_for(mode),
            op_types=tuple(_op_type(op) for op in ops),
            rolled_back=mode == MODE_BRIDGE_INPLACE,
        )
    if mode == MODE_STATIC:
        return _static(ops)
    if mode == MODE_BRIDGE_INPLACE:
        return _bridge(ops, store)
    if mode == MODE_STAGING:
        return _staging(ops, store, staging_port=staging_port)
    return _synthetic(ops)


def _static(ops: list[dict[str, Any]]) -> ModeResult:
    errors: list[str] = []
    for index, op in enumerate(ops):
        op_type = _op_type(op)
        entry = get_op(op_type)
        if entry is None:
            errors.append(f"op[{index}] unknown")
            continue
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        if entry.ddl and params.get("simulate_in_place") is True:
            errors.append(f"op[{index}] DDL op cannot set simulate_in_place=true")
    return _result(
        MODE_STATIC,
        passed=not errors,
        path_taken=True,
        detail="; ".join(errors) if errors else "static",
        target="none",
        op_types=tuple(_op_type(op) for op in ops),
    )


def _bridge(ops: list[dict[str, Any]], store: dict[str, Any]) -> ModeResult:
    before = deepcopy(store)
    scratch = deepcopy(store)
    scratch["_applied"] = [_op_type(op) for op in ops]
    if store != before:
        return _result(
            MODE_BRIDGE_INPLACE,
            passed=False,
            path_taken=True,
            detail="inplace_mutated_store",
            target="scratch",
            op_types=tuple(_op_type(op) for op in ops),
        )
    return _result(
        MODE_BRIDGE_INPLACE,
        passed=True,
        path_taken=True,
        detail="rolled_back",
        target="scratch",
        op_types=tuple(_op_type(op) for op in ops),
        rolled_back=True,
    )


def _staging(
    ops: list[dict[str, Any]],
    store: dict[str, Any],
    *,
    staging_port: Any | None = None,
) -> ModeResult:
    before = deepcopy(store)
    detail = "neutralized_clone"
    if staging_port is not None:
        # Fake staging port only. Never create a real staging database.
        apply_cs = getattr(staging_port, "apply_changeset", None)
        if callable(apply_cs):
            apply_cs(
                ops,
                mode="apply",
                environment="staging",
                neutralized_clone=True,
                max_risk="R4",
            )
            detail = "fake_staging_port"
        else:
            runs = getattr(staging_port, "staging_runs", None)
            if isinstance(runs, list):
                runs.append([_op_type(op) for op in ops])
            detail = "fake_staging_port"
    else:
        clone = deepcopy(store)
        clone["_neutralized"] = True
        clone["_target"] = "staging"
        clone["_applied"] = [_op_type(op) for op in ops]
    if store != before:
        return _result(
            MODE_STAGING,
            passed=False,
            path_taken=True,
            detail="production_store_mutated",
            target="staging",
            op_types=tuple(_op_type(op) for op in ops),
        )
    return _result(
        MODE_STAGING,
        passed=True,
        path_taken=True,
        detail=detail,
        target="staging",
        op_types=tuple(_op_type(op) for op in ops),
    )


def _synthetic(ops: list[dict[str, Any]]) -> ModeResult:
    ids = tuple(f"synthetic-{index + 1}" for index, _op in enumerate(ops))
    if not ids:
        ids = ("synthetic-0",)
    return _result(
        MODE_SYNTHETIC,
        passed=True,
        path_taken=True,
        detail="synthetic_rows",
        target="synthetic",
        op_types=tuple(_op_type(op) for op in ops),
        synthetic_ids=ids,
    )


def _ops_for_mode(mode: str, ops: list[dict[str, Any]], risk: str) -> list[dict[str, Any]]:
    if mode == MODE_BRIDGE_INPLACE:
        return [op for op in ops if not _is_ddl(op)]
    if mode == MODE_STAGING and _rank(risk) < _rank(_STAGING_FLOOR):
        return [op for op in ops if _is_ddl(op)]
    return list(ops)


def _r0_skips_simulation(risk: str, decision: Mapping[str, Any]) -> bool:
    if risk != "R0":
        return False
    if bool(decision.get("deny", True)) or not bool(decision.get("allow")):
        return False
    return not bool(decision.get("needs_simulation", True))


def _is_ddl(op: dict[str, Any]) -> bool:
    entry = get_op(_op_type(op))
    if entry is None:
        return False
    return bool(entry.ddl)


def _op_type(op: dict[str, Any]) -> str:
    return str(op.get("type") or "")


def _rank(risk: str) -> int:
    return _RISK_ORDER.index(risk)


def _require_risk(risk: str) -> str:
    if risk not in _RISK_ORDER:
        raise ValueError(f"unknown risk class: {risk}")
    return risk


def _target_for(mode: str) -> str:
    if mode == MODE_BRIDGE_INPLACE:
        return "scratch"
    if mode == MODE_STAGING:
        return "staging"
    if mode == MODE_SYNTHETIC:
        return "synthetic"
    return "none"


def _result(
    mode: str,
    *,
    passed: bool,
    path_taken: bool,
    detail: str,
    target: str,
    op_types: tuple[str, ...],
    writes: int = 0,
    rolled_back: bool = False,
    synthetic_ids: tuple[str, ...] = (),
) -> ModeResult:
    return ModeResult(
        mode=mode,
        passed=passed,
        path_taken=path_taken,
        detail=detail,
        target=target,
        op_types=op_types,
        writes=writes,
        rolled_back=rolled_back,
        synthetic_ids=synthetic_ids,
    )


def _report(
    *,
    plan_id: str,
    plan_hash: str,
    risk: str,
    passed: bool,
    phase: str,
    returned_to_planning: bool,
    recorded: bool,
    selected: tuple[str, ...],
    modes: tuple[ModeResult, ...],
) -> SimulationReport:
    return SimulationReport(
        plan_id=plan_id,
        plan_hash=plan_hash,
        risk=risk,
        passed=passed,
        phase=phase,
        returned_to_planning=returned_to_planning,
        recorded=recorded,
        selected=selected,
        modes=modes,
    )
