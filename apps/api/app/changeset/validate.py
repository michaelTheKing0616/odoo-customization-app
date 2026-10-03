"""Nine-stage change-set validation.

``validate`` always records all nine stages and does not change the change-set.
``repair`` may ask the caller to revise the plan, at most four rounds, then
stops and explains.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from difflib import get_close_matches
from typing import Any

from app.changeset.ops import get_op, is_known_op
from app.changeset.policy import risk_of
from app.changeset.protected_registry import protected_denial

MAX_OPS = 50
MAX_PARAMS_BYTES = 64 * 1024
# Same payload-depth cap as the gateway args parser and the $ref walker.
MAX_DEPTH = 12
MAX_REPAIR_ROUNDS = 4
# RT-33 names this class. The set is closed: no extra keys.
PROTOTYPE_POLLUTION_KEYS = frozenset({"__proto__", "constructor", "prototype"})

Revise = Callable[[list[dict[str, Any]], dict[str, Any]], list[dict[str, Any]] | None]

STAGE_NAMES = (
    "shape",
    "static",
    "grounding",
    "dependency",
    "preconditions",
    "impact",
    "risk",
    "lints",
    "report",
)


def _payload_problems(value: Any, *, op_index: int) -> list[str]:
    """Depth and prototype-pollution problems for one params value.

    Inputs: a JSON-like value and the op index. The root container is level 0.
    Outputs: error strings. Empty when every container is shallower than depth
    12 and no prototype-pollution key is present.
    Side effects: none. Walking stops at ``MAX_DEPTH``.
    """
    problems: list[str] = []
    reported_depth = False

    def walk(node: Any, level: int) -> None:
        nonlocal reported_depth
        if not isinstance(node, (dict, list)):
            return
        if level >= MAX_DEPTH:
            if not reported_depth:
                problems.append(f"op[{op_index}].params exceeds depth {MAX_DEPTH}")
                reported_depth = True
            return
        if isinstance(node, dict):
            for key, child in node.items():
                if key in PROTOTYPE_POLLUTION_KEYS:
                    problems.append(
                        f"op[{op_index}].params contains prototype-pollution key {key!r}"
                    )
                walk(child, level + 1)
            return
        for child in node:
            walk(child, level + 1)

    walk(value, 0)
    return problems


def validate(
    changeset: list[dict[str, Any]],
    *,
    known_models: set[str] | frozenset[str] | None = None,
    tenant: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all nine stages and return the report.

    Inputs: a change-set, optional known model names, optional tenant.
    Outputs: valid, stages (always nine, in ``STAGE_NAMES`` order), impact,
    risks, and max_risk. An early failure does not skip later stage entries.
    Side effects: ``protected_denial`` may append a detection when an op hits
    the protected registry. The change-set is not modified.
    """
    known = set(known_models or ())
    stages: list[dict[str, Any]] = []
    halted = False
    impact: dict[str, Any] = {}
    risks: list[dict[str, Any]] = []
    max_risk = "R0"

    def record(name: str, errors: list[str], *, extra: dict[str, Any] | None = None) -> None:
        nonlocal halted
        passed = len(errors) == 0 and not halted
        entry: dict[str, Any] = {"name": name, "passed": passed, "errors": errors}
        if extra:
            entry.update(extra)
        stages.append(entry)
        if errors:
            halted = True

    # 1 shape
    shape_errors: list[str] = []
    if len(changeset) > MAX_OPS:
        shape_errors.append(f"changeset exceeds max {MAX_OPS} ops")
    for i, op in enumerate(changeset):
        params = op.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            shape_errors.append(f"op[{i}].params must be a JSON object")
            continue
        try:
            encoded = json.dumps(params, sort_keys=True, default=str)
        except (TypeError, ValueError):
            shape_errors.append(f"op[{i}].params is not JSON-serializable")
            continue
        if len(encoded.encode("utf-8")) > MAX_PARAMS_BYTES:
            shape_errors.append(f"op[{i}].params exceeds {MAX_PARAMS_BYTES} bytes")
        shape_errors.extend(_payload_problems(params, op_index=i))
    record("shape", shape_errors)

    # 2 static
    static_errors: list[str] = []
    if not halted:
        for i, op in enumerate(changeset):
            op_type = op.get("type")
            if op_type == "rpc.write":
                static_errors.append(f"op[{i}].type rpc.write is not allowed")
                continue
            if not isinstance(op_type, str) or not is_known_op(op_type):
                static_errors.append(f"op[{i}].type unknown or forbidden: {op_type!r}")
            params = op.get("params") or {}
            if isinstance(op, dict) and protected_denial(op, document=changeset, tenant=tenant):
                static_errors.append(f"op[{i}] protected_deny")
            if isinstance(params, dict):
                if "sql" in params:
                    static_errors.append(f"op[{i}].params must not contain sql key")
                method = params.get("method")
                if method == "execute_kw":
                    static_errors.append(f"op[{i}].params.method execute_kw is forbidden")
    record("static", static_errors)

    # 3 grounding
    grounding_errors: list[str] = []
    if not halted:
        for i, op in enumerate(changeset):
            params = op.get("params") or {}
            if not isinstance(params, dict):
                continue
            model = params.get("model")
            if model is None:
                continue
            if not isinstance(model, str):
                grounding_errors.append(f"op[{i}].params.model must be a string")
                continue
            if model not in known:
                hint = get_close_matches(model, sorted(known), n=3, cutoff=0.6)
                msg = f"op[{i}].params.model {model!r} not in known_models"
                if hint:
                    msg += f"; did_you_mean={hint}"
                grounding_errors.append(msg)
    record("grounding", grounding_errors)

    # 4 dependency
    dep_errors: list[str] = []
    if not halted:
        n = len(changeset)
        graph: dict[int, list[int]] = {i: [] for i in range(n)}
        for i, op in enumerate(changeset):
            deps = op.get("depends_on") or []
            if not isinstance(deps, list):
                dep_errors.append(f"op[{i}].depends_on must be a list")
                continue
            for d in deps:
                if not isinstance(d, int) or d < 0 or d >= n:
                    dep_errors.append(f"op[{i}].depends_on invalid index {d!r}")
                elif d == i:
                    dep_errors.append(f"op[{i}].depends_on cannot self-reference")
                else:
                    graph[i].append(d)
        if not dep_errors:

            def has_cycle() -> bool:
                state = [0] * n

                def dfs(node: int) -> bool:
                    state[node] = 1
                    for nxt in graph[node]:
                        if state[nxt] == 1:
                            return True
                        if state[nxt] == 0 and dfs(nxt):
                            return True
                    state[node] = 2
                    return False

                return any(state[i] == 0 and dfs(i) for i in range(n))

            if has_cycle():
                dep_errors.append("depends_on contains a cycle")
    record("dependency", dep_errors)

    # 5 preconditions
    pre_errors: list[str] = []
    if not halted:
        for i, op in enumerate(changeset):
            op_type = op.get("type")
            entry = get_op(str(op_type)) if isinstance(op_type, str) else None
            params = op.get("params") or {}
            if entry and entry.ddl and isinstance(params, dict) and params.get("simulate_in_place") is True:
                pre_errors.append(f"op[{i}] DDL op cannot set simulate_in_place=true")
    record("preconditions", pre_errors)

    # 6 impact
    impact_errors: list[str] = []
    if not halted:
        impact = {"op_count": len(changeset)}
    record("impact", impact_errors, extra={"impact": impact} if impact else None)

    # 7 risk
    risk_errors: list[str] = []
    if not halted:
        order = ("R0", "R1", "R2", "R3", "R4")
        for i, op in enumerate(changeset):
            r = risk_of(op, tenant=tenant, document=changeset)
            risks.append({"index": i, "type": op.get("type"), "risk": r})
            if order.index(r) > order.index(max_risk):
                max_risk = r
    record("risk", risk_errors, extra={"risks": risks, "max_risk": max_risk} if risks else None)

    # 8 lints
    lint_errors: list[str] = []
    if not halted:
        for i, op in enumerate(changeset):
            if op.get("type") != "field.create":
                continue
            params = op.get("params") or {}
            if not isinstance(params, dict):
                continue
            name = params.get("name")
            if not isinstance(name, str) or not name.startswith("x_"):
                lint_errors.append(f"op[{i}] field.create name must start with x_")
    record("lints", lint_errors)

    # 9 report
    report_errors: list[str] = []
    valid = not halted and all(s["passed"] for s in stages if s["name"] != "report")
    if not halted:
        record("report", report_errors, extra={"valid": valid})
    else:
        record("report", report_errors, extra={"valid": False})

    return {
        "valid": valid,
        "stages": stages,
        "impact": impact,
        "risks": risks,
        "max_risk": max_risk,
    }


def repair(
    changeset: list[dict[str, Any]],
    revise: Revise,
    *,
    known_models: set[str] | frozenset[str] | None = None,
    tenant: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate, then ask ``revise`` for a new plan, at most four rounds.

    Inputs: the change-set, ``revise(changeset, report)`` returning a new
    change-set or None, and the same ``known_models`` and ``tenant`` as
    ``validate``.
    Outputs: valid, rounds, explanation, the last change-set, and the last
    report. Explanation says the plan passed, that revise made no further
    change, or that repair stopped after four rounds.
    Side effects: none in this function. ``revise`` may allocate a new list.
    Stops when validation passes, ``revise`` returns None, or four rounds
    have run.
    """
    current = changeset
    report = validate(current, known_models=known_models, tenant=tenant)
    rounds = 0
    stopped_early = False
    while not report["valid"] and rounds < MAX_REPAIR_ROUNDS:
        revised = revise(current, report)
        rounds += 1
        if revised is None:
            stopped_early = True
            break
        current = revised
        report = validate(current, known_models=known_models, tenant=tenant)

    if report["valid"] and rounds == 0:
        explanation = "validation passed"
    elif report["valid"]:
        explanation = f"validation passed after {rounds} repair round(s)"
    elif stopped_early:
        explanation = f"repair stopped after {rounds} round(s): no further change"
    else:
        explanation = f"repair stopped after {MAX_REPAIR_ROUNDS} rounds"
    return {
        "valid": bool(report["valid"]),
        "rounds": rounds,
        "explanation": explanation,
        "changeset": current,
        "report": report,
    }
