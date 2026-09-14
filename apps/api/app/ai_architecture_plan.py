"""Explicit architecture plan stamp — stock-first before ModuleSpec expand.

Strategy values map grain + Option A + reuse into a scored plan IR.
"""

from __future__ import annotations

from typing import Any

# Parallel ERP leaves we refuse when stock hosts cover the brief
_DEFAULT_FORBIDDEN = [
    "x_bill",
    "x_invoice",
    "x_payment",
    "x_attorney",
    "x_lawyer",
    "x_employee",
    "x_task",
    "x_event",
    "x_product",
    "x_partner",
    "x_customer",
    "x_client",
]


def _x_models(draft: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        if mid.startswith("x_") and str(m.get("mode") or "") != "inherit":
            out.append(mid)
    return out


def _stock_hosts(draft: dict[str, Any]) -> list[str]:
    hosts: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        if mid and not mid.startswith("x_") and str(m.get("mode") or "") == "inherit":
            hosts.append(mid)
    # reuse plan
    reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
    for key in ("stock_models", "hosts", "prefer"):
        raw = reuse.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item and not item.startswith("x_"):
                    hosts.append(item)
                elif isinstance(item, dict):
                    mid = str(item.get("model") or "")
                    if mid and not mid.startswith("x_"):
                        hosts.append(mid)
    # dedupe preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for h in hosts:
        if h not in seen:
            seen.add(h)
            ordered.append(h)
    return ordered


def _surface_counts(draft: dict[str, Any]) -> dict[str, int]:
    blocks = draft.get("custom_code_blocks") or []
    js = 0
    controllers = 0
    for b in blocks:
        if not isinstance(b, dict):
            continue
        path = str(b.get("source_file") or b.get("path") or "")
        kind = str(b.get("kind") or "")
        if "static/src" in path or kind in {"js", "owl", "scss"}:
            js += 1
        if "controllers" in path or kind == "controller":
            controllers += 1
    return {
        "new_models": len(_x_models(draft)),
        "new_js": js,
        "new_controllers": controllers,
    }


def build_architecture_plan(
    draft: dict[str, Any],
    *,
    prompt: str = "",
) -> dict[str, Any]:
    """Derive plan from grain / Option A / reuse (deterministic)."""
    from app.ai_document_shape import classify_document_shape, shape_budget

    shape = classify_document_shape(prompt or str(draft.get("_user_prompt") or ""), draft)
    grain = str(draft.get("grain") or "full_app")
    option_a = bool(draft.get("_capability_primary_option_a"))
    hosts = _stock_hosts(draft)
    x_models = _x_models(draft)
    prompt_l = (prompt or str(draft.get("_user_prompt") or "")).lower()
    engine = draft.get("_generation_engine") if isinstance(draft.get("_generation_engine"), dict) else {}
    depends = [str(x) for x in (draft.get("depends") or []) if x]
    if (
        engine.get("capability") == "stock_reuse"
        or draft.get("_pipeline") == "generation_engine_stock_reuse"
        or str(draft.get("technical_name") or "") == "stock_reuse"
    ):
        return {
            "strategy": "stock_reuse",
            "stock_hosts": hosts or depends,
            "new_x_models": [],
            "forbidden_clones": list(_DEFAULT_FORBIDDEN) + ["x_receipt", "x_pos_config"],
            "customization_needed": False,
            "reason": "Named Community apps cover the brief; no x_* residual",
            "surface_budget": {"new_models": 0, "new_js": 0, "new_controllers": 0},
            "ambiguities": [],
            "grain": grain,
            "document_shape": "stock_reuse",
        }

    if option_a:
        strategy = "option_a_module"
        customization_needed = True
        reason = "Capability-primary ask (PDF/QR/pay/Python/OWL) — module → sandbox → promote"
        budget = {"new_models": 2, "new_js": 1, "new_controllers": 1}
        shape = "option_a"
    elif grain == "field_pack" or shape == "field_pack":
        strategy = "field_pack"
        customization_needed = True
        reason = "Inherit stock host with additive x_* fields only"
        budget = {"new_models": 0, "new_js": 0, "new_controllers": 0}
    elif grain == "feature_slice":
        strategy = "feature_slice"
        customization_needed = True
        reason = "Stock host + thin companion / activity slice"
        budget = {"new_models": 2, "new_js": 0, "new_controllers": 0}
    elif shape == "register":
        strategy = "residual_app"
        customization_needed = True
        reason = "Register: one header x_* — no satellites or CRM/invoice bridges"
        budget = {"new_models": 1, "new_js": 0, "new_controllers": 0}
    elif not x_models and hosts:
        strategy = "configure_stock"
        customization_needed = False
        reason = "Stock hosts cover the brief — prefer configuration over custom models"
        budget = {"new_models": 0, "new_js": 0, "new_controllers": 0}
    else:
        strategy = "residual_app"
        customization_needed = True
        reason = "Custom x_* residual + stock inherit bridges"
        pack_n = len(
            [
                x
                for x in (draft.get("_pack_model_ids") or [])
                if str(x).startswith("x_")
            ]
        )
        budget = {
            "new_models": shape_budget(shape, x_models=len(x_models), pack_n=pack_n),
            "new_js": 0,
            "new_controllers": 0,
        }

    ambiguities: list[str] = []
    if (
        shape not in {"register", "field_pack", "stock_reuse", "catalog"}
        and "or " in prompt_l
        and grain == "full_app"
        and str(draft.get("technical_name") or "") != "stock_reuse"
    ):
        ambiguities.append("Prompt contains alternatives — confirm residual vs stock-first")
    if option_a and grain == "field_pack":
        ambiguities.append("Option A primary with field_pack grain — prefer option_a_module")

    return {
        "strategy": strategy,
        "stock_hosts": hosts,
        "new_x_models": x_models,
        "forbidden_clones": list(_DEFAULT_FORBIDDEN),
        "customization_needed": customization_needed,
        "reason": reason,
        "surface_budget": budget,
        "ambiguities": ambiguities,
        "grain": grain,
        "document_shape": shape,
    }


def architecture_plan_drift(draft: dict[str, Any], plan: dict[str, Any] | None = None) -> list[str]:
    """Compare plan budget / forbidden clones to current ModuleSpec."""
    plan = plan or (
        draft.get("_architecture_plan")
        if isinstance(draft.get("_architecture_plan"), dict)
        else {}
    )
    if not plan:
        return []
    drift: list[str] = []
    budget = plan.get("surface_budget") if isinstance(plan.get("surface_budget"), dict) else {}
    counts = _surface_counts(draft)
    for key in ("new_models", "new_js", "new_controllers"):
        limit = budget.get(key)
        if limit is None:
            continue
        try:
            lim = int(limit)
        except (TypeError, ValueError):
            continue
        actual = int(counts.get(key) or 0)
        if actual > lim:
            drift.append(f"surface_budget.{key}: {actual} > {lim}")

    forbidden = {
        str(x).strip().lower()
        for x in (plan.get("forbidden_clones") or [])
        if str(x).strip()
    }
    planned = {
        str(x).strip().lower()
        for x in (plan.get("new_x_models") or [])
        if str(x).strip()
    }
    for mid in _x_models(draft):
        leaf = mid.split(".")[-1].lower()
        if mid.lower() in planned or leaf in planned:
            continue
        if mid.lower() in forbidden or leaf in forbidden:
            drift.append(f"forbidden_clone: {mid}")

    strategy = str(plan.get("strategy") or "")
    if strategy == "field_pack" and counts["new_models"] > 0:
        drift.append("field_pack strategy but new_x_models present")
    if strategy == "configure_stock" and counts["new_models"] > 0:
        drift.append("configure_stock strategy but custom models present")
    if strategy == "option_a_module" and not draft.get("custom_code_blocks") and not draft.get(
        "_capability_gaps"
    ):
        drift.append("option_a_module without scaffolds/gaps")

    return drift


def stamp_architecture_plan(
    draft: dict[str, Any],
    *,
    prompt: str = "",
    rebuild: bool = False,
) -> dict[str, Any]:
    """Attach / refresh ``_architecture_plan`` and drift list."""
    existing = draft.get("_architecture_plan") if isinstance(draft.get("_architecture_plan"), dict) else None
    built = build_architecture_plan(draft, prompt=prompt)
    if rebuild or not existing:
        plan = built
    else:
        plan = {**built, **existing}
        reuse = built.get("strategy") == "stock_reuse" or existing.get("strategy") == "stock_reuse"
        if reuse:
            plan["strategy"] = "stock_reuse"
            plan["surface_budget"] = built.get("surface_budget") or {
                "new_models": 0,
                "new_js": 0,
                "new_controllers": 0,
            }
            plan["ambiguities"] = []
            plan["customization_needed"] = False
            plan["new_x_models"] = []
            plan["reason"] = built.get("reason") or existing.get("reason")
        elif existing.get("strategy"):
            plan["strategy"] = existing["strategy"]
            if existing.get("surface_budget"):
                plan["surface_budget"] = existing["surface_budget"]
        if existing.get("forbidden_clones"):
            plan["forbidden_clones"] = existing["forbidden_clones"]
        if plan.get("strategy") != "stock_reuse":
            plan["new_x_models"] = _x_models(draft)
        plan["stock_hosts"] = _stock_hosts(draft) or list(
            existing.get("stock_hosts") or built.get("stock_hosts") or []
        )

    draft["_architecture_plan"] = plan
    from app.ai_document_shape import clip_forbidden_reuse_surfaces, stamp_document_shape

    stamp_document_shape(draft, prompt=prompt)
    plan["document_shape"] = draft.get("_document_shape") or plan.get("document_shape")
    draft["_architecture_plan"] = plan
    clip_forbidden_reuse_surfaces(draft)
    plan = (
        draft.get("_architecture_plan")
        if isinstance(draft.get("_architecture_plan"), dict)
        else plan
    )
    drift = architecture_plan_drift(draft, plan)
    draft["_architecture_drift"] = drift
    return plan


__all__ = [
    "architecture_plan_drift",
    "build_architecture_plan",
    "stamp_architecture_plan",
]
