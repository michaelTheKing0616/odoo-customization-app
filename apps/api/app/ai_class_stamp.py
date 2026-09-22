"""Class-wide Contract/Diagnosis stamps — delivery lane, artifact kind, prove status.

ingenium owns ANY Odoo customization (LLM + hard gates). CBN / markup+WHT /
delivery-note QWeb scrub are proof exemplars of classes — never one-offs.

Completeness ≠ Cert ≠ Autopilot. Promote stays human.
"""

from __future__ import annotations

import re
from typing import Any, Literal

DeliveryLane = Literal["online_metadata", "module_sh_or_self", "external_connector"]
ArtifactKind = Literal[
    "field_pack",
    "full_app",
    "option_a_module",
    "report_layout",
    "stock_config",
    "external_connector",
    "refuse",
]
ProveStatus = Literal["not_required", "pending", "proved", "failed"]

# Plain operator copy — never invent features or claim Online Python promote.
LANE_COPY: dict[str, str] = {
    "online_metadata": (
        "Online lane: metadata / Studio / data-XML only — custom Python cannot "
        "install on Odoo Online."
    ),
    "module_sh_or_self": (
        "Module lane: Odoo.sh or self-host. Sandbox prove first; human Promote."
    ),
    "external_connector": (
        "External connector lane: rate/HTTP provider outside Online Python promote "
        "(or Option A module on .sh / self-host)."
    ),
}

ARTIFACT_COPY: dict[str, str] = {
    "field_pack": "Prefer / field pack on a stock host — not a new Apps tile.",
    "full_app": "Residual full app — new model/menu; promote stays human.",
    "option_a_module": "Option A installable module — Python/QWeb/OWL under gates.",
    "report_layout": "Report / QWeb layout class — scrub or reshape document blocks.",
    "stock_config": "Stock / Config / Batch — Atlas or Batch OS, not Prefer.",
    "external_connector": "FX / HTTP provider class — gold Option A or external connector.",
    "refuse": "Refuse / escalate — ingenium will not invent an unsupported feature.",
}

_FX_CONNECTOR_RE = re.compile(
    r"(?i)\b("
    r"cbn|central\s+bank|fx\s+rate|exchange\s+rate|currency\s+rate|"
    r"live\s+rates?|rate\s+provider|automatic\s+currency\s+rates?"
    r")\b"
)
_MARKUP_TAX_RE = re.compile(
    r"(?i)\b(mark-?up|withh?olding\s+tax|\bwht\b|price\s+compute)\b"
)
_REPORT_SCRUB_RE = re.compile(
    r"(?i)\b("
    r"delivery\s+(?:note|slip)|shipping\s+address|qweb|"
    r"report\s+layout|address\s+block|invoice\s+address|"
    r"remove.{0,60}(?:customer|partner|name).{0,40}(?:slip|note|pdf|address)|"
    r"(?:customer|partner)\s+name.{0,40}(?:removed|strip|scrub)"
    r")\b"
)
_PREFER_FIELD_RE = re.compile(
    r"(?i)\b("
    r"prefer\s+for\s+delivery|delivery\s+notes?\s+on\s+contacts|"
    r"add\s+(?:a\s+)?field\s+on|"
    r"checkbox\s+on\s+(?:contacts|sales)|"
    r"inherit[\s-]only|no\s+new\s+app"
    r")\b"
)


def is_fx_rate_class(prompt: str) -> bool:
    return bool(_FX_CONNECTOR_RE.search(prompt or ""))


def is_markup_tax_class(prompt: str) -> bool:
    try:
        from app.ai_markup_wht_class import is_markup_wht_class_brief

        if is_markup_wht_class_brief(prompt or ""):
            return True
    except Exception:  # noqa: BLE001
        pass
    return bool(_MARKUP_TAX_RE.search(prompt or ""))


def is_prefer_field_class(prompt: str) -> bool:
    text = prompt or ""
    if _PREFER_FIELD_RE.search(text):
        return True
    return False


def is_report_layout_class(prompt: str) -> bool:
    from app.ai_report_layout_scrub import is_report_layout_scrub_brief

    if is_prefer_field_class(prompt or ""):
        return False
    if is_report_layout_scrub_brief(prompt or ""):
        return True
    return bool(_REPORT_SCRUB_RE.search(prompt or ""))


def resolve_class_stamp(
    *,
    prompt: str = "",
    capability: str = "",
    grain: str = "",
    needs_module: bool = False,
    gold_artifact_id: str | None = None,
    module_delivery: bool = False,
    prove_ok: bool | None = None,
    inherit_only: bool = False,
) -> dict[str, Any]:
    """Resolve class-wide stamps for Contract / Diagnosis / generation IR."""
    text = (prompt or "").strip()
    cap = (capability or "").strip()
    g = (grain or "").strip()
    gold = (gold_artifact_id or "").strip() or None

    if cap == "refuse_clone":
        lane: DeliveryLane = "online_metadata"
        kind: ArtifactKind = "refuse"
        prove: ProveStatus = "not_required"
    elif gold == "currency_rate_cbn" or (
        is_fx_rate_class(text) and (needs_module or module_delivery or cap.startswith("option_a"))
    ):
        # FX / CBN-class: Option A gold module on .sh/self-host; Online → connector alt.
        lane = "module_sh_or_self"
        kind = "external_connector"
        prove = "pending"
    elif is_report_layout_class(text) and not is_prefer_field_class(text):
        if needs_module or module_delivery or cap in {
            "option_a_authored",
            "option_a_standalone",
        }:
            lane = "module_sh_or_self"
            kind = "report_layout"
            prove = "pending"
        else:
            # Studio report metadata path (Online-capable).
            lane = "online_metadata"
            kind = "report_layout"
            prove = "not_required"
    elif (
        needs_module
        or module_delivery
        or cap in {"option_a_authored", "option_a_standalone"}
        or is_markup_tax_class(text)
    ):
        lane = "module_sh_or_self"
        kind = "option_a_module"
        prove = "pending"
    elif inherit_only or g == "field_pack" or is_prefer_field_class(text):
        lane = "online_metadata"
        kind = "field_pack"
        prove = "not_required"
    elif g in {"full_app", "feature_slice"} or cap == "residual_app":
        lane = "online_metadata" if not needs_module else "module_sh_or_self"
        kind = "full_app"
        prove = "not_required" if lane == "online_metadata" else "pending"
    elif cap == "stock_reuse" or g in {"", "stock"}:
        lane = "online_metadata"
        kind = "stock_config"
        prove = "not_required"
    else:
        lane = "online_metadata"
        kind = "full_app" if g == "full_app" else "field_pack"
        prove = "not_required"

    if prove_ok is True and prove == "pending":
        prove = "proved"
    elif prove_ok is False and prove == "pending":
        prove = "failed"

    return {
        "delivery_lane": lane,
        "artifact_kind": kind,
        "prove_status": prove,
        "delivery_lane_copy": LANE_COPY[lane],
        "artifact_kind_copy": ARTIFACT_COPY[kind],
        "promote_human": True,
        "completeness_is_not_cert": True,
    }


def apply_class_stamp(target: dict[str, Any], stamp: dict[str, Any]) -> dict[str, Any]:
    """Merge class stamps onto an IR / contract dict (in place)."""
    for key in (
        "delivery_lane",
        "artifact_kind",
        "prove_status",
        "delivery_lane_copy",
        "artifact_kind_copy",
        "promote_human",
        "completeness_is_not_cert",
    ):
        if key in stamp:
            target[key] = stamp[key]
    return target


def online_python_block_alternatives() -> tuple[str, ...]:
    """Operator alternatives when Online + Python Option A cannot promote."""
    return (
        "Re-export with install_mode=data for Online metadata-only import.",
        "Promote on Odoo.sh or self-hosted Docker where Option A Python installs.",
        "Use an external connector for FX/HTTP providers instead of Online Python.",
    )


__all__ = [
    "ARTIFACT_COPY",
    "LANE_COPY",
    "apply_class_stamp",
    "is_fx_rate_class",
    "is_markup_tax_class",
    "is_prefer_field_class",
    "is_report_layout_class",
    "online_python_block_alternatives",
    "resolve_class_stamp",
]
