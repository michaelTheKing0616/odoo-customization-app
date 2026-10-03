"""Nine-stage change-set validation (no repair)."""

from __future__ import annotations

import json
from difflib import get_close_matches
from typing import Any

from app.changeset.ops import get_op, is_known_op
from app.changeset.policy import risk_of
from app.changeset.protected_registry import protected_denial

MAX_OPS = 50
MAX_PARAMS_BYTES = 64 * 1024

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


def validate(
    changeset: list[dict[str, Any]],
    *,
    known_models: set[str] | frozenset[str] | None = None,
    tenant: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
