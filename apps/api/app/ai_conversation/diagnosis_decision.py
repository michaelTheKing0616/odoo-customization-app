"""Canonical DiagnosisDecision: checklist, exclusions, declines, questions, choices,
stock_plan and integration routes. Lives in the session even when there is no app design.

AI proposes the checklist rows; code authorizes (decide, stock_check, route_service, capability).
"""
from __future__ import annotations

import json
from typing import Any

KEY = "_diagnosis_decision_json"


def from_checklist(chk: dict[str, Any] | None) -> dict[str, Any]:
    """Build the decision from a checklist meta dict (contract path or checklist_only)."""
    chk = chk or {}
    left = list(chk.get("left_out") or [])
    routes = list(chk.get("routes") or [])
    reg = chk.get("register") or {}
    declines = [
        {"kind": "exclusion", "item": r.get("item"), "id": r.get("id"), "message": r.get("message"),
         "quote": r.get("quote"), "status": r.get("status")}
        for r in left
    ] + [
        {"kind": "route", "item": r.get("service"), "id": r.get("service"), "message": r.get("label") or r.get("reason"),
         "route": r.get("route"), "reason": r.get("reason")}
        for r in routes if r.get("route") == "decline"
    ]
    return {
        "version": 1,
        "items": chk.get("items") or 0,
        "second_look": chk.get("second_look"),
        "statuses": chk.get("statuses") or {},
        "left_out": left,
        "choices": list(chk.get("choices") or []),
        "stock_checks": list(chk.get("stock_checks") or []),
        "routes": routes,
        "register": {"quoted": list(reg.get("quoted") or []),
                     "defaults": list(reg.get("defaults") or []),
                     "questions": list(reg.get("questions") or [])},
        "declines": declines,
        "stock_plan": [
            {"id": c.get("id"), "item": c.get("item"), "choice": c.get("choice"),
             "use": c.get("use"), "install": c.get("install"), "label": c.get("label"),
             "verified_reason": c.get("verified_reason")}
            for c in (chk.get("stock_checks") or [])
        ],
        "capability": list(chk.get("capability") or []),
        "conflicts": list(chk.get("conflicts") or []),
    }


def persist(resolved: dict[str, Any], decision: dict[str, Any] | None) -> None:
    if decision:
        resolved[KEY] = json.dumps(decision, ensure_ascii=False)


def load(resolved: dict[str, Any] | None) -> dict[str, Any] | None:
    if not resolved:
        return None
    raw = resolved.get(KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def attach_to_clarification(out: dict[str, Any], decision: dict[str, Any] | None) -> dict[str, Any]:
    """Surface the decision on the diagnosis clarifier the UI and the scorer already read."""
    if not decision or not isinstance(out, dict):
        return out
    out = dict(out)
    out["diagnosis_decision"] = decision
    out["integration_routes"] = decision.get("routes") or out.get("integration_routes") or []
    out["left_out"] = decision.get("left_out") or out.get("left_out") or []
    out["checklist_choices"] = decision.get("choices") or out.get("checklist_choices") or []
    out["stock_checks"] = decision.get("stock_checks") or out.get("stock_checks") or []
    headline = decline_only_headline(out.get("app_design"), decision)
    if headline and out.get("kind") == "diagnosis":
        out["question"], out["help"] = headline
        out["decline_only"] = True
    return out


def has_approved_build(decision: dict[str, Any] | None) -> bool:
    """Any item code authorized to build, or any outside service with a working route."""
    dec = decision or {}
    if any(c.get("decision") == "authorize" for c in dec.get("capability") or []):
        return True
    if any(r.get("route") not in {None, "decline"} for r in dec.get("routes") or []):
        return True
    if not dec.get("capability"):  # older decisions: fall back to the checklist statuses
        return bool((dec.get("statuses") or {}).get("build"))
    return False


def decline_only_headline(design: Any, decision: dict[str, Any] | None) -> tuple[str, str] | None:
    """When code declined everything and the design builds nothing, say so plainly."""
    d = design if isinstance(design, dict) else {}
    builds = (d.get("new_models") or d.get("automations") or
              any(e.get("fields") for e in d.get("stock_extensions") or [] if isinstance(e, dict)))
    reasons = [str(x.get("message") or x.get("reason") or "").strip() for x in (decision or {}).get("declines") or []]
    reasons = [r for r in dict.fromkeys(reasons) if r]
    if builds or not reasons or has_approved_build(decision):
        return None
    why = " ".join(r if r.endswith(".") else r + "." for r in reasons[:3])
    return ("Nothing will be built for this request",
            f"App Studio can't build what you asked for here. {why} You can change the request and try again.")
