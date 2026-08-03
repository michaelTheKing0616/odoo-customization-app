"""Discover bulk-safe object buttons from form view arch."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from odoo_client import OdooClient

# Heuristics (BLK-1 card):
# - type="object" buttons on models with selection `state` / `x_status` are candidates.
# - Wizard/dialog openers: special=, wizard-like method names, wizard context patterns.
_WIZARD_NAME = re.compile(r"(?i)(^|_)(wizard|open_wizard)(_|$)|^open_|^preview_|^print_")
_WIZARD_CONTEXT = re.compile(r"active_id.*active_model|form_view_ref|default_.*_id")

_STATE_FIELD_NAMES = frozenset({"state", "x_status"})


@dataclass(frozen=True)
class TransitionButton:
    name: str
    label: str
    bulk_safe: bool
    reason: str
    in_header: bool


def _ancestor_tags(element: ET.Element) -> set[str]:
    tags: set[str] = set()
    parent = element
    while True:
        parent = _parent_map_get(parent)
        if parent is None:
            break
        tags.add(parent.tag.split("}")[-1] if "}" in parent.tag else parent.tag)
    return tags


_parent_map: dict[ET.Element, ET.Element] = {}


def _parent_map_get(element: ET.Element) -> ET.Element | None:
    return _parent_map.get(element)


def _build_parent_map(root: ET.Element) -> None:
    global _parent_map
    _parent_map = {child: parent for parent in root.iter() for child in parent}


def parse_object_buttons(arch: str) -> list[dict[str, Any]]:
    """Parse ``<button type=\"object\">`` entries from form arch XML."""
    try:
        root = ET.fromstring(arch)
    except ET.ParseError:
        return []
    _build_parent_map(root)
    state_in_arch = {
        el.get("name")
        for el in root.iter("field")
        if el.get("name") in _STATE_FIELD_NAMES
    }
    out: list[dict[str, Any]] = []
    for el in root.iter("button"):
        if el.get("type", "object") != "object":
            continue
        name = (el.get("name") or "").strip()
        if not name:
            continue
        ancestors = _ancestor_tags(el)
        in_header = bool(ancestors & {"header", "statusbar"})
        out.append(
            {
                "name": name,
                "string": (el.get("string") or name).strip(),
                "special": el.get("special"),
                "context": el.get("context") or "",
                "confirm": el.get("confirm"),
                "in_header": in_header,
                "state_fields_in_arch": set(state_in_arch),
            }
        )
    return out


def classify_button(btn: dict[str, Any], *, has_state_field: bool) -> tuple[bool, str]:
    """Return (bulk_safe, reason). Conservative on wizard patterns."""
    if btn.get("special"):
        return False, "button has special= (cancel/save — not a bulk workflow action)"
    name = str(btn["name"])
    ctx = str(btn.get("context") or "")
    if _WIZARD_NAME.search(name):
        return False, "method name suggests wizard/dialog opener"
    if _WIZARD_CONTEXT.search(ctx.replace(" ", "")):
        return False, "context suggests wizard/dialog opener"
    if not has_state_field:
        return False, "no state/x_status selection field on model — review manually"
    if btn.get("in_header"):
        return True, "header/statusbar object button on workflow model"
    if name.startswith(("action_", "button_")):
        return True, "workflow-style object method on model with state/status field"
    return True, "object button on workflow model (confirm target set before run)"


def classify_buttons(
    buttons: list[dict[str, Any]], *, has_state_field: bool
) -> list[TransitionButton]:
    seen: set[str] = set()
    out: list[TransitionButton] = []
    for btn in buttons:
        name = btn["name"]
        if name in seen:
            continue
        seen.add(name)
        bulk_safe, reason = classify_button(btn, has_state_field=has_state_field)
        out.append(
            TransitionButton(
                name=name,
                label=str(btn.get("string") or name),
                bulk_safe=bulk_safe,
                reason=reason,
                in_header=bool(btn.get("in_header")),
            )
        )
    return sorted(out, key=lambda b: (not b.bulk_safe, b.label.lower()))


def _model_has_state_field(client: OdooClient, model: str) -> bool:
    for fname in _STATE_FIELD_NAMES:
        try:
            rows = client.execute_kw(
                "ir.model.fields",
                "search_read",
                [[("model", "=", model), ("name", "=", fname), ("ttype", "=", "selection")]],
                {"fields": ["name"], "limit": 1},
            )
            if rows:
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _primary_form_arch(client: OdooClient, model: str) -> str | None:
    """Prefer get_views when available; fall back to ir.ui.view search_read."""
    try:
        payload = client.execute_kw(
            model,
            "get_views",
            [[], {"views": [(False, "form")], "options": {}}],
        )
        if isinstance(payload, dict):
            views = payload.get("views") or payload.get("fields_views") or {}
            form = views.get("form") if isinstance(views, dict) else None
            if isinstance(form, dict) and form.get("arch"):
                return str(form["arch"])
    except Exception:  # noqa: BLE001
        pass
    rows = client.execute_kw(
        "ir.ui.view",
        "search_read",
        [[("model", "=", model), ("type", "=", "form")]],
        {"fields": ["arch"], "limit": 1, "order": "priority, id"},
    )
    if rows and rows[0].get("arch"):
        return str(rows[0]["arch"])
    return None


def discover_buttons_from_arch(
    arch: str, *, has_state_field: bool
) -> list[TransitionButton]:
    raw = parse_object_buttons(arch)
    return classify_buttons(raw, has_state_field=has_state_field)
