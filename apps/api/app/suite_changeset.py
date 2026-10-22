"""Suite setup steps as shared change-set operations.

Maps each normalised suite step to validator-accepted change-set ops and runs
them through the shared gates (validate, protected registry, policy). The
suite runner keeps its own writes, so runs, receipts and undo are unchanged;
this module only decides whether the shared gates accept the plan.
Side effects: none, except ``protected_denial`` detections inside validate.
"""
from __future__ import annotations

from typing import Any

from app.changeset import policy as cs_policy
from app.changeset.validate import MAX_OPS, validate
from app.changeset.data_ops import ROW_CAP

UNITS_MODEL = "uom.uom"


def _modules(step: dict[str, Any]) -> list[str]:
    inp = step["inputs"]
    if step["type"] == "install":
        return [str(m) for m in (inp.get("modules") or [])]
    return [f"l10n_{str(inp.get('country_code') or '').lower()}"]


def step_ops(step: dict[str, Any]) -> list[dict[str, Any]]:
    """One step -> one or more ops (installs per module, imports per 1000 rows)."""
    t, inp, op = step["type"], step["inputs"], step.get("cs_op")
    tag = {"suite_step_id": step["id"]}
    if t in {"install", "country_package"}:
        return [{"type": op, "params": {"module": m, **tag}} for m in _modules(step)]
    if t == "setting":
        return [{"type": op, "params": {"values": dict(inp.get("values") or {}), **tag}}]
    if t == "units":
        return [{"type": op, "params": {"model": UNITS_MODEL, "row_count": 1,
                                        "values": {"name": inp.get("name")}, **tag}}]
    if t == "create":
        return [{"type": op, "params": {"model": str(inp["model"]), "row_count": 1,
                                        "values": dict(inp.get("values") or {}), **tag}}]
    if t == "update":
        if inp.get("id"):
            domain = [["id", "=", int(inp["id"])]]
        else:
            match = dict(inp.get("match") or {}) or {"name": (inp.get("values") or {}).get("name")}
            domain = [[k, "=", v] for k, v in match.items()]
        return [{"type": op, "params": {"model": str(inp["model"]), "domain": domain, "row_count": 1,
                                        "values": dict(inp.get("values") or {}), **tag}}]
    if t == "import":
        n = len(inp.get("rows") or [])
        chunks = [min(ROW_CAP, n - i) for i in range(0, n, ROW_CAP)] or [0]
        return [{"type": op, "params": {"model": str(inp["model"]), "row_count": c, "chunk": k, **tag}}
                for k, c in enumerate(chunks)]
    if t == "access":
        return [{"type": op, "params": {"model": str(inp.get("model")), "group": str(inp.get("role")),
                                        "perms": dict(inp.get("can") or {}), **tag}}]
    if t == "remove":
        ids = [int(inp["id"])] if inp.get("id") else []
        params = {"model": str(inp["model"]), "ids": ids or list(inp.get("xmlids") or []),
                  "row_count": max(1, len(ids or inp.get("xmlids") or [])), **tag}
        return [{"type": op, "params": params}]
    return []


def steps_to_changesets(steps: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Ops in step order, split into change-sets of at most MAX_OPS.

    ``depends_on`` holds int indices inside the same change-set; a dependency
    in an earlier change-set is already ordered by the change-set sequence.
    """
    out: list[list[dict[str, Any]]] = [[]]
    where: dict[str, list[tuple[int, int]]] = {}
    for s in steps:
        ops = step_ops(s)
        if len(out[-1]) + len(ops) > MAX_OPS and out[-1]:
            out.append([])
        cs, ci = out[-1], len(out) - 1
        deps = sorted({i for d in s.get("depends_on") or [] for (c, i) in where.get(str(d), []) if c == ci})
        for o in ops:
            o["depends_on"] = list(deps)
            cs.append(o)
            where.setdefault(s["id"], []).append((ci, len(cs) - 1))
    return [c for c in out if c]


def _environment(env: str | None) -> str:
    return env or "production"


def gate(steps: list[dict[str, Any]], *, known_models: set[str] | None = None,
         environment: str | None = None) -> dict[str, Any]:
    """Run the shared gates. Output: ok, per-change-set reports, blocked step ids."""
    models = set(known_models or ()) | {str(s["inputs"]["model"]) for s in steps if s["inputs"].get("model")}
    if any(s["type"] == "units" for s in steps):
        models.add(UNITS_MODEL)
    env = _environment(environment)
    reports, blocked = [], {}
    for cs in steps_to_changesets(steps):
        rep = validate(cs, known_models=models)
        errs = [e for st in rep["stages"] for e in st["errors"]]
        pol = []
        for o in cs:
            d = cs_policy.policy_for_op(o, env)
            pol.append({"step": o["params"]["suite_step_id"], "type": o["type"], **d})
            if d.get("deny"):
                blocked[o["params"]["suite_step_id"]] = "The shared change policy refuses this step."
        if not rep["valid"]:
            for o in cs:
                blocked.setdefault(o["params"]["suite_step_id"], "; ".join(errs[:3]) or "Not a valid change.")
        reports.append({"valid": rep["valid"], "max_risk": rep["max_risk"], "errors": errs, "policy": pol, "ops": len(cs)})
    return {"ok": not blocked, "changesets": reports, "blocked": blocked}


def submit_to_inbox(db: Any, connection_id: str, name: str, steps: list[dict[str, Any]], *,
                    requester_id: str, environment: str | None = None) -> list[str]:
    """Post the plan's change-sets to the shared inbox as plan cards. Returns card hashes.

    Best effort: the builders' approval item stays the gate the suite run checks.
    """
    from app.changeset import store

    models = {str(s["inputs"]["model"]) for s in steps if s["inputs"].get("model")} | {UNITS_MODEL}
    out: list[str] = []
    for cs in steps_to_changesets(steps):
        try:
            res = store.submit_plan(db, changeset=cs, goal=f"Setup plan: {name}", assumptions=[],
                                    environment=_environment(environment), requester_id=requester_id,
                                    known_models=models, connection_id=connection_id)
        except Exception:  # noqa: BLE001  inbox is advisory here
            continue
        if res.get("ok"):
            card = res.get("card") or {}
            out.append(str(card.get("plan_hash") or card.get("id") or ""))
    return out
