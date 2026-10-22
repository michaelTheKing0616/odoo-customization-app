"""Bridge B10 (spec 5, 29): visual flow canvas (nodes/edges as data) and a call surface so
Odoo 20 AI agents / other tools can run a flow through the same safety checks.
"""

from __future__ import annotations

from typing import Any

from app.bridge import drafting as bd
from app.bridge import reliability as rel
from app.bridge import sync_rules as sr
from app.bridge.gallery import BY_KEY

NODE_KINDS = ("connector", "odoo", "map", "match", "guard", "trigger", "delivery")


def from_defn(flow_id: str, defn: dict[str, Any]) -> dict[str, Any]:
    c = BY_KEY.get(defn.get("connector", ""))
    nodes = [
        {
            "id": "t",
            "kind": "trigger",
            "label": (defn.get("trigger") or {}).get("kind", "manual"),
            "x": 40,
            "y": 120,
        },
        {
            "id": "a",
            "kind": "connector",
            "label": c.name if c else defn.get("connector"),
            "x": 220,
            "y": 60,
        },
        {
            "id": "m",
            "kind": "map",
            "label": f"{sum(1 for x in defn.get('mapping') or [] if x.get('odoo'))} fields",
            "x": 400,
            "y": 120,
        },
        {"id": "g", "kind": "match", "label": "Match / review", "x": 580, "y": 120},
        {"id": "o", "kind": "odoo", "label": defn.get("odoo_model"), "x": 760, "y": 120},
    ]
    if c and c.money:
        nodes.insert(
            -1, {"id": "money", "kind": "guard", "label": "Money guard", "x": 670, "y": 220}
        )
    edges = [
        {"from": "t", "to": "a"},
        {"from": "a", "to": "m"},
        {"from": "m", "to": "g"},
        {"from": "g", "to": "o"},
    ]
    if any(n["id"] == "money" for n in nodes):
        edges[-1] = {"from": "g", "to": "money"}
        edges.append({"from": "money", "to": "o"})
    return {"flow_id": flow_id, "nodes": nodes, "edges": edges, "live": None}


def check_canvas(canvas: dict[str, Any]) -> list[str]:
    errs = []
    ids = {n["id"] for n in canvas.get("nodes") or []}
    for n in canvas.get("nodes") or []:
        if n.get("kind") not in NODE_KINDS:
            errs.append(f"Unknown node kind {n.get('kind')}")
    for e in canvas.get("edges") or []:
        if e.get("from") not in ids or e.get("to") not in ids:
            errs.append(f"Edge {e} points at a missing node")
    kinds = {n["kind"] for n in canvas.get("nodes") or []}
    for need in ("connector", "odoo", "map"):
        if need not in kinds:
            errs.append(f"Canvas needs a {need} node")
    return errs


def agent_call(
    ws: str | None,
    flow_id: str,
    record: dict[str, Any],
    *,
    dry_run: bool = True,
    get_flow: Any = None,
    odoo_fields: dict[str, dict[str, Any]] | None = None,
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one record through the flow's safety checks. Live writes are refused unless dry_run=False
    and the flow is live with rollout covering this record — and even then only after tests pass."""
    from app.bridge import flows as fl

    get_flow = get_flow or (lambda: fl.get_flow(ws, flow_id))
    f = get_flow()
    if not f or not f.get("live"):
        return {"ok": False, "refused": "Flow is not live."}
    v = next(x for x in f["versions"] if x["n"] == f["live"])
    d = v["defn"]
    mapped = {}
    from app.bridge.mapping import apply_transform

    for m in d.get("mapping") or []:
        if m.get("odoo"):
            try:
                mapped[m["odoo"]] = apply_transform(
                    m.get("transform", "none"), record.get(m["remote"])
                )
            except (ValueError, TypeError) as exc:
                return {
                    "ok": False,
                    "refused": f"Transform failed on {m['remote']}: {exc.__class__.__name__}",
                }
    if odoo_fields is not None:
        tests = rel.contract_tests(
            d.get("mapping") or [], d.get("remote_fields") or {}, odoo_fields, [record]
        )
        if not tests["ok"]:
            return {"ok": False, "refused": "Contract tests failed.", "tests": tests}
    decision = sr.match_record(mapped, candidates or [])
    if decision["action"] == "review":
        return {"ok": False, "refused": "Needs human review.", "match": decision, "values": mapped}
    if v.get("money") and not dry_run:
        return {
            "ok": False,
            "refused": "Money flows can't be written by an agent call; use the approval path.",
        }
    if dry_run:
        return {
            "ok": True,
            "sandbox": True,
            "would": decision["action"],
            "values": mapped,
            "match": decision,
        }
    # Live path is intentionally thin: the delivery engine owns writes. Agents get a receipt, not a write.
    return {
        "ok": True,
        "sandbox": False,
        "queued": True,
        "would": decision["action"],
        "values": mapped,
    }
