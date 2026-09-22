"""P2 Build spine — one front door, mode chips, handoff without re-briefing.

Unifies App Studio / Draft Studio / Job Autopilot as modes of one Build entry
(not rival homes). Expert routes into the same spine. Carries brief + Diagnosis
/ Contract + delivery_lane stamps across surfaces.

Completeness ≠ Cert ≠ Autopilot. Promote stays human.
"""

from __future__ import annotations

from typing import Any, Literal

from app.ai_class_stamp import resolve_class_stamp
from app.ai_generation_engine import classify_generation, plan_to_ir

BuildMode = Literal[
    "prefer_pack",
    "residual_app",
    "option_a",
    "stock_autopilot",
    "report_layout",
    "connector",
]

MODE_META: dict[str, dict[str, str]] = {
    "prefer_pack": {
        "label": "Prefer pack",
        "surface": "designer",
        "blurb": "Inherit-only field pack on a stock host — not a new Apps tile.",
    },
    "residual_app": {
        "label": "Residual app",
        "surface": "studio",
        "blurb": "New x_* residual / full app — identity lock; never Prefer-reshape.",
    },
    "option_a": {
        "label": "Option A",
        "surface": "studio",
        "blurb": "Installable module (Python / QWeb / OWL) — sandbox prove, human Promote.",
    },
    "stock_autopilot": {
        "label": "Stock Autopilot",
        "surface": "job",
        "blurb": "Stock-first Job Autopilot — no custom residual invent.",
    },
    "report_layout": {
        "label": "Report layout",
        "surface": "studio",
        "blurb": "QWeb / document layout class — not Contacts Prefer delivery-notes.",
    },
    "connector": {
        "label": "Connector",
        "surface": "studio",
        "blurb": "FX / HTTP provider — gold Option A or external connector lane.",
    },
}

SURFACE_HREF = {
    "studio": "studio",
    "wizard": "wizard",
    "job": "job",
    "designer": "designer",
    "modulespec": "modulespec",
}


def resolve_build_mode(
    *,
    prompt: str = "",
    capability: str = "",
    grain: str = "",
    gold_artifact_id: str | None = None,
    artifact_kind: str | None = None,
    delivery_lane: str | None = None,
) -> BuildMode:
    """Map generation IR / class stamps → one Build mode chip."""
    kind = (artifact_kind or "").strip()
    cap = (capability or "").strip()
    g = (grain or "").strip()
    gold = (gold_artifact_id or "").strip() or None
    lane = (delivery_lane or "").strip()

    if kind == "report_layout" or (
        not kind and __import__("app.ai_class_stamp", fromlist=["is_report_layout_class"]).is_report_layout_class(prompt)
    ):
        return "report_layout"
    if kind == "external_connector" or gold == "currency_rate_cbn" or lane == "external_connector":
        return "connector"
    if cap in {"option_a_authored", "option_a_standalone"} or kind == "option_a_module":
        return "option_a"
    if cap == "stock_reuse" or kind == "stock_config":
        return "stock_autopilot"
    if g == "field_pack" or kind == "field_pack" or (cap == "residual_app" and g == "field_pack"):
        # Prefer-style inherit pack — never residual reshape.
        if kind == "full_app":
            return "residual_app"
        return "prefer_pack"
    if g == "full_app" or kind == "full_app" or cap == "residual_app":
        return "residual_app"
    if not prompt.strip():
        return "residual_app"
    # Classify once — do not recurse (capability/grain from plan are authoritative).
    plan = classify_generation(prompt)
    ir = plan_to_ir(plan, prompt=prompt)
    cap2 = str(ir.get("capability") or plan.capability or "")
    g2 = str(ir.get("grain") or plan.grain or "")
    kind2 = str(ir.get("artifact_kind") or "")
    lane2 = str(ir.get("delivery_lane") or "")
    gold2 = ir.get("gold_artifact_id") or plan.gold_artifact_id
    if kind2 == "report_layout":
        return "report_layout"
    if kind2 == "external_connector" or gold2 == "currency_rate_cbn" or lane2 == "external_connector":
        return "connector"
    if cap2 in {"option_a_authored", "option_a_standalone"} or kind2 == "option_a_module":
        return "option_a"
    if cap2 == "stock_reuse" or kind2 == "stock_config":
        return "stock_autopilot"
    if g2 == "field_pack" or kind2 == "field_pack":
        return "prefer_pack"
    if g2 == "full_app" or kind2 == "full_app" or cap2 == "residual_app":
        return "residual_app"
    return "residual_app"


def applicable_modes(primary: BuildMode) -> list[BuildMode]:
    """Modes to show as chips — primary first, then siblings that may apply."""
    order: list[BuildMode] = [
        "prefer_pack",
        "residual_app",
        "option_a",
        "stock_autopilot",
        "report_layout",
        "connector",
    ]
    # Always show Prefer / Residual / Option A / Stock; report+connector when primary or class.
    base: list[BuildMode] = ["prefer_pack", "residual_app", "option_a", "stock_autopilot"]
    if primary in {"report_layout", "connector"}:
        base.append(primary)
    elif primary not in base:
        base.append(primary)
    # Dedupe preserving order; put primary first.
    seen: set[str] = set()
    out: list[BuildMode] = []
    for m in [primary, *base, *order]:
        if m in seen:
            continue
        seen.add(m)
        out.append(m)
    return out


def surface_for_mode(mode: BuildMode) -> str:
    return MODE_META[mode]["surface"]


def href_for_mode(connection_id: str, mode: BuildMode) -> str:
    surface = surface_for_mode(mode)
    slug = SURFACE_HREF.get(surface, "studio")
    return f"/connections/{connection_id}/{slug}"


def build_spine_payload(
    *,
    prompt: str = "",
    connection_id: str = "",
    understanding: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    generation_ir: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Handoff IR — brief + Diagnosis/Contract + stamps — no re-brief required."""
    text = (prompt or "").strip()
    ir = dict(generation_ir or {})
    u = dict(understanding or {})
    c = dict(contract or {})

    if not ir and text:
        plan = classify_generation(text)
        ir = plan_to_ir(plan, prompt=text)
    if not u and text:
        try:
            from app.ai_conversation.understand import build_understanding

            u = build_understanding(text).to_dict()
        except Exception:  # noqa: BLE001
            u = {}
    if not c and text:
        try:
            from app.ai_studio_contract import build_studio_contract

            c = build_studio_contract(text)
        except Exception:  # noqa: BLE001
            c = {}

    stamp = resolve_class_stamp(
        prompt=text,
        capability=str(ir.get("capability") or u.get("capability") or ""),
        grain=str(ir.get("grain") or u.get("grain") or c.get("grain") or ""),
        needs_module=bool(ir.get("module_delivery") or ir.get("capability", "").startswith("option_a")),
        gold_artifact_id=ir.get("gold_artifact_id"),
        module_delivery=bool(ir.get("module_delivery")),
        inherit_only=bool(c.get("inherit_only") or str(ir.get("grain") or "") == "field_pack"),
    )
    # Prefer stamps already on IR / understanding / contract.
    for src in (ir, u, c):
        for key in ("delivery_lane", "artifact_kind", "prove_status"):
            if src.get(key):
                stamp[key] = src[key]
                copy_key = f"{key}_copy"
                if src.get(copy_key):
                    stamp[copy_key] = src[copy_key]

    mode = resolve_build_mode(
        prompt=text,
        capability=str(ir.get("capability") or u.get("capability") or ""),
        grain=str(ir.get("grain") or u.get("grain") or c.get("grain") or ""),
        gold_artifact_id=ir.get("gold_artifact_id"),
        artifact_kind=stamp.get("artifact_kind"),
        delivery_lane=stamp.get("delivery_lane"),
    )
    modes = applicable_modes(mode)
    chips = []
    for m in modes:
        meta = MODE_META[m]
        chips.append(
            {
                "id": m,
                "label": meta["label"],
                "blurb": meta["blurb"],
                "surface": meta["surface"],
                "href": href_for_mode(connection_id, m) if connection_id else "",
                "active": m == mode,
            }
        )

    return {
        "version": 1,
        "prompt": text,
        "brief": text,
        "build_mode": mode,
        "chips": chips,
        "capability": ir.get("capability") or u.get("capability"),
        "grain": ir.get("grain") or u.get("grain") or c.get("grain"),
        "gold_artifact_id": ir.get("gold_artifact_id"),
        "delivery_lane": stamp.get("delivery_lane"),
        "artifact_kind": stamp.get("artifact_kind"),
        "prove_status": stamp.get("prove_status"),
        "delivery_lane_copy": stamp.get("delivery_lane_copy"),
        "artifact_kind_copy": stamp.get("artifact_kind_copy"),
        "promote_human": True,
        "completeness_is_not_cert": True,
        "diagnosis": {
            "capability": u.get("capability") or ir.get("capability"),
            "grain": u.get("grain") or ir.get("grain"),
            "host_model": u.get("host_model") or c.get("host_model"),
            "delivery_lane": stamp.get("delivery_lane"),
            "artifact_kind": stamp.get("artifact_kind"),
            "prove_status": stamp.get("prove_status"),
        },
        "contract": {
            "grain": c.get("grain"),
            "host_model": c.get("host_model"),
            "inherit_only": c.get("inherit_only"),
            "delivery_lane": c.get("delivery_lane") or stamp.get("delivery_lane"),
            "artifact_kind": c.get("artifact_kind") or stamp.get("artifact_kind"),
        },
        "surfaces": {
            "studio": href_for_mode(connection_id, "option_a") if connection_id else "/studio",
            "wizard": f"/connections/{connection_id}/wizard" if connection_id else "/wizard",
            "job": href_for_mode(connection_id, "stock_autopilot") if connection_id else "/job",
            "designer": href_for_mode(connection_id, "prefer_pack") if connection_id else "/designer",
        },
        "honesty": (
            "One Build entry — App Studio, Draft Studio, and Job Autopilot share this "
            "brief and stamps. Completeness ≠ Cert ≠ Autopilot. Promote stays human."
        ),
    }


def capability_gap_option_a_proposals(draft: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Read stamped gap → Option A scaffold proposals (domain-agnostic)."""
    if not isinstance(draft, dict):
        return []
    gaps = draft.get("_capability_gaps")
    if not isinstance(gaps, list):
        return []
    out: list[dict[str, Any]] = []
    for g in gaps:
        if not isinstance(g, dict):
            continue
        path = str(g.get("option_a_path") or "").strip()
        if not path:
            continue
        out.append(
            {
                "gap_id": g.get("id"),
                "label": g.get("label"),
                "option_a_path": path,
                "detail": g.get("detail"),
                "proposes_option_a_scaffold": True,
            }
        )
    return out


__all__ = [
    "MODE_META",
    "applicable_modes",
    "build_spine_payload",
    "capability_gap_option_a_proposals",
    "href_for_mode",
    "resolve_build_mode",
    "surface_for_mode",
]
