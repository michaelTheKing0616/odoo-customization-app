"""Presentation polish — menus, smart buttons, line totals (GEN2-7)."""

from __future__ import annotations

import re
from typing import Any

_MENU_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Operations": ("order", "sale", "task", "event", "appointment", "service"),
    "Inventory": ("stock", "inventory", "warehouse", "product", "branch", "store"),
    "People": ("employee", "staff", "team", "member", "hr", "user"),
    "Finance": ("invoice", "bill", "payment", "deposit", "expense", "account"),
}


def _menu_category(label: str, model: str) -> str:
    hay = f"{label} {model}".lower()
    for cat, keys in _MENU_CATEGORIES.items():
        if any(k in hay for k in keys):
            return cat
    return "Other"


def group_menus_if_needed(draft: dict[str, Any], *, threshold: int = 8) -> list[str]:
    notes: list[str] = []
    menus = draft.get("menus")
    if not isinstance(menus, list):
        return notes
    leaves = [m for m in menus if isinstance(m, dict) and m.get("action_xml_id")]
    if len(leaves) <= threshold:
        return notes
    root = next((m for m in menus if not m.get("parent_xml_id")), None)
    if not root:
        return notes
    root_xml = str(root.get("xml_id") or root.get("technical_name") or "")
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for leaf in leaves:
        cat = _menu_category(str(leaf.get("name") or ""), str(leaf.get("technical_name") or ""))
        by_cat.setdefault(cat, []).append(leaf)
    new_menus = [root]
    seq = 20
    for cat in ("Operations", "Inventory", "People", "Finance", "Other"):
        items = by_cat.get(cat) or []
        if not items:
            continue
        sub_xml = f"menu_sub_{cat.lower()}_{root.get('technical_name', 'root')}"
        new_menus.append(
            {
                "name": cat,
                "parent_xml_id": root_xml,
                "sequence": seq,
                "technical_name": sub_xml,
                "xml_id": sub_xml,
            }
        )
        seq += 1
        for i, leaf in enumerate(items):
            child = dict(leaf)
            child["parent_xml_id"] = sub_xml
            child["sequence"] = 10 + i
            new_menus.append(child)
    draft["menus"] = new_menus
    notes.append(f"presentation: grouped {len(leaves)} leaf menus into submenus")
    return notes


def dedupe_smart_button_labels(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    buttons = draft.get("smart_buttons")
    if not isinstance(buttons, list):
        return notes
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for btn in buttons:
        if not isinstance(btn, dict):
            continue
        key = (str(btn.get("on_model") or ""), str(btn.get("related_model") or ""))
        groups.setdefault(key, []).append(btn)
    for (_on, _rel), rows in groups.items():
        if len(rows) < 2:
            continue
        for i, btn in enumerate(rows):
            field = str(btn.get("relation_field") or btn.get("field") or "")
            suffix = ""
            if "out" in field.lower() or field.endswith("_from_id"):
                suffix = " out"
            elif "in" in field.lower() or field.endswith("_to_id"):
                suffix = " in"
            elif i > 0:
                suffix = f" ({field or i + 1})"
            label = str(btn.get("string") or btn.get("name") or "Related")
            if suffix and suffix.strip() not in label.lower():
                btn["string"] = f"{label}{suffix}".strip()
                notes.append(
                    f"presentation: smart button label dedupe on {btn.get('on_model')}"
                )
    return notes


def suggest_line_total_compute(draft: dict[str, Any]) -> list[str]:
    """Flag line models with qty × price for optional equation-compute automation."""
    notes: list[str] = []
    suggestions: list[dict[str, str]] = []
    qty_names = ("x_qty", "x_quantity", "quantity", "x_hours", "x_units")
    price_names = ("x_price", "x_unit_price", "x_rate", "price_unit")
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or "line" not in mid.lower():
            continue
        fields = {str(f.get("name")): f for f in (model.get("fields") or []) if isinstance(f, dict)}
        qty = next((n for n in qty_names if n in fields), None)
        price = next((n for n in price_names if n in fields), None)
        total = next(
            (n for n in ("x_subtotal", "x_total", "x_amount") if n in fields),
            None,
        )
        if qty and price and total:
            suggestions.append(
                {
                    "model": mid,
                    "message": (
                        f"Line model {mid} has {qty} × {price} → consider equation compute "
                        f"for {total} (advanced action — confirm before apply)."
                    ),
                }
            )
    if suggestions:
        draft.setdefault("_compute_suggestions", []).extend(suggestions)
        notes.append(f"presentation: {len(suggestions)} line-total compute suggestion(s)")
    return notes


__all__ = [
    "dedupe_smart_button_labels",
    "group_menus_if_needed",
    "suggest_line_total_compute",
]
