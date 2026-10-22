"""Capability gate: AI proposes a delivery_shape; code authorizes or declines before design.

Shapes: record_workflow | record_automation | stock_extension | integration |
analysis_prediction | custom_runtime | unsupported.
"""
from __future__ import annotations

from typing import Any

SHAPES = ("record_workflow", "record_automation", "stock_extension", "integration",
          "analysis_prediction", "custom_runtime", "unsupported")
# Code policy: these never become Odoo record models.
DECLINE = frozenset({"analysis_prediction", "unsupported"})

# Plain reasons (code-authored, not AI).
REASON = {
    "analysis_prediction": "an Odoo app keeps records, forms and automations; forecasting and NPV are analysis, not something App Studio builds",
    "unsupported": "App Studio cannot deliver this on this Odoo database",
    "custom_runtime": "needs custom Python that Online cannot install; use Odoo.sh or self-hosted",
}


def derive_shape(i: dict[str, Any]) -> str:
    """Shape from the item's facts (structure, not wording). '' when facts are missing."""
    f = i.get("facts") if isinstance(i.get("facts"), dict) else None
    if not f:
        return ""
    if f.get("output_is_derived") is True and f.get("keeps_records") is not True:
        return "analysis_prediction"
    if f.get("needs_custom_code") is True:
        return "custom_runtime"
    if i.get("service"):
        return "integration"
    return "record_workflow" if f.get("keeps_records") is True else ""


def authorize(items: list[dict[str, Any]], snap: Any = None, online: bool = False) -> list[dict[str, Any]]:
    """Per build/cannot item: authorize the proposed delivery_shape, or decline with a plain reason."""
    out = []
    for i in items:
        shape = str(i.get("delivery_shape") or "").strip().lower()
        if i.get("status") == "cannot" and shape not in SHAPES:
            shape = "analysis_prediction"
        if shape not in SHAPES:
            # Missing shape: default by status. cannot -> analysis; build with service -> integration; else record.
            if i.get("status") == "cannot":
                shape = "analysis_prediction"
            elif i.get("service"):
                shape = "integration"
            elif i.get("plan") == "stock" or i.get("stock_options"):
                shape = "stock_extension"
            else:
                shape = "record_workflow"
        code_shape = derive_shape(i)
        row = {"id": i.get("id"), "item": i.get("item"), "shape": shape, "code_shape": code_shape}
        if code_shape and (code_shape in DECLINE) != (shape in DECLINE) and i.get("status") != "cannot":
            # The AI label and the item's facts disagree: the owner chooses; never a silent build.
            row.update(decision="ask", reason=REASON["analysis_prediction"],
                       options=["Leave it out", "Build it as records people fill in"])
            out.append(row)
            continue
        if shape in DECLINE or i.get("status") == "cannot":
            why = REASON.get(shape) or REASON["unsupported"]
            if shape == "analysis_prediction" or i.get("status") == "cannot":
                why = i.get("reason") or REASON["analysis_prediction"]
            row.update(decision="decline", reason=why)
        elif shape == "custom_runtime" and online:
            row.update(decision="decline", reason=REASON["custom_runtime"])
        else:
            row.update(decision="authorize")
        out.append(row)
    return out
