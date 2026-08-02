"""Declarative AppBlueprint — shared live-scaffold layout + related-model polish.

Wizard templates and ad-hoc Builder polish both apply form layouts and ensure
related ``x_*`` models stay first-class (ACL, menus already via ensure_app_menus).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from odoo_client.client import OdooClient, OdooClientError
from odoo_client.view_arch import FieldNode, FormViewSpec, GroupNode, render_form_arch


@dataclass
class FormGroupLayout:
    """One labeled ``<group string=...>`` on a form."""

    string: str
    fields: list[str] = field(default_factory=list)
    # Optional per-field widgets, e.g. {"x_barcode": "barcode"}
    widgets: dict[str, str] = field(default_factory=dict)


@dataclass
class ModelFormLayout:
    model: str
    string: str = "Form"
    groups: list[FormGroupLayout] = field(default_factory=list)
    # O2M field name → list of column field names for an embedded list
    o2m_lists: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class AppBlueprint:
    """High-level module integration descriptor (layouts; models come from scaffold)."""

    display_name: str
    form_layouts: list[ModelFormLayout] = field(default_factory=list)
    # Field label overrides: (model, field_name) → label
    field_labels: dict[tuple[str, str], str] = field(default_factory=dict)


def _field_tag(name: str, widget: str | None = None) -> FieldNode:
    return FieldNode(name=name, widget=widget)


def _list_arch_root_for_major(major: int) -> str:
    """Embedded O2M subview root tag (``list`` on 18+, ``tree`` on ≤17)."""
    if major == 16:
        from odoo_client.compat.adapters import views_v16 as views
    elif major == 17:
        from odoo_client.compat.adapters import views_v17 as views
    elif major == 18:
        from odoo_client.compat.adapters import views_v18 as views
    else:
        from odoo_client.compat.adapters import views_v19 as views
    return views.list_arch_root()


def render_layout_form_arch(
    layout: ModelFormLayout, *, list_root: str = "list"
) -> str:
    """Build a labeled multi-group form arch from a layout spec."""
    children: list[GroupNode] = []
    for group in layout.groups:
        nodes: list[Any] = []
        for fname in group.fields:
            if fname in layout.o2m_lists:
                # O2M rendered as field with nested list — use raw-ish via FieldNode only;
                # nested list XML is appended after render for simplicity.
                nodes.append(_field_tag(fname))
            else:
                nodes.append(_field_tag(fname, group.widgets.get(fname)))
        children.append(GroupNode(string=group.string, children=nodes))
    arch = render_form_arch(FormViewSpec(string=layout.string, children=children))
    # Expand O2M placeholders into nested list/tree subviews when present
    tag = list_root if list_root in {"list", "tree"} else "list"
    for o2m_name, cols in layout.o2m_lists.items():
        simple = f'<field name="{o2m_name}"/>'
        if simple not in arch:
            continue
        inner = "".join(f'<field name="{c}"/>' for c in cols)
        rich = f'<field name="{o2m_name}"><{tag}>{inner}</{tag}></field>'
        arch = arch.replace(simple, rich, 1)
    return arch


def unlink_custom_form_injects(client: OdooClient, model: str) -> int:
    ids = client.execute_kw(
        "ir.ui.view",
        "search",
        [[("model", "=", model), ("type", "=", "form"), ("name", "like", f"{model}.custom.")]],
    )
    if ids:
        client.execute_kw("ir.ui.view", "unlink", [ids])
    return len(ids or [])


def set_field_label(client: OdooClient, model: str, field_name: str, label: str) -> None:
    ids = client.execute_kw(
        "ir.model.fields",
        "search",
        [[("model", "=", model), ("name", "=", field_name)]],
        {"limit": 1},
    )
    if ids:
        client.execute_kw(
            "ir.model.fields",
            "write",
            [ids, {"field_description": label}],
        )


def apply_form_layout(
    client: OdooClient,
    layout: ModelFormLayout,
    *,
    drop_custom_injects: bool = True,
) -> dict[str, Any]:
    """Rewrite primary form for ``layout.model``; drop conflicting inject inherits."""
    if not client.model_exists(layout.model):
        return {"model": layout.model, "skipped": True, "reason": "model_missing"}
    removed = 0
    if drop_custom_injects:
        removed = unlink_custom_form_injects(client, layout.model)
    list_root = _list_arch_root_for_major(client.capabilities.major)
    arch = render_layout_form_arch(layout, list_root=list_root)
    primary = client.find_view(layout.model, "form", primary_only=True)
    if primary is None:
        primary = client.find_view(layout.model, "form")
    if primary is None:
        from odoo_client.models import CreateViewRequest

        view = client.create_view(
            CreateViewRequest(
                name=f"{layout.model}.form",
                model=layout.model,
                type="form",
                arch=arch,
            )
        )
        return {
            "model": layout.model,
            "view_id": view.id,
            "created": True,
            "injects_removed": removed,
        }
    client.update_view_arch(primary.id, arch)
    return {
        "model": layout.model,
        "view_id": primary.id,
        "created": False,
        "injects_removed": removed,
    }


def apply_blueprint(client: OdooClient, blueprint: AppBlueprint) -> dict[str, Any]:
    """Apply field labels + form layouts for a blueprint."""
    label_updates = 0
    for (model, fname), label in blueprint.field_labels.items():
        try:
            set_field_label(client, model, fname, label)
            label_updates += 1
        except OdooClientError:
            continue
    layouts_applied: list[dict[str, Any]] = []
    for layout in blueprint.form_layouts:
        try:
            layouts_applied.append(apply_form_layout(client, layout))
        except Exception as exc:  # noqa: BLE001
            layouts_applied.append(
                {"model": layout.model, "error": str(exc)}
            )
    return {
        "display_name": blueprint.display_name,
        "field_labels": label_updates,
        "layouts": layouts_applied,
    }


def auto_form_layout_for_model(
    client: OdooClient,
    model: str,
    *,
    string: str | None = None,
) -> ModelFormLayout | None:
    """Heuristic layout: Identity (name + M2Os), Details (scalars), Lines (O2Ms).

    Used for CRM/Inventory and Builder "Polish form" so every app gets labeled groups.
    """
    if not client.model_exists(model):
        return None
    rows = client.execute_kw(
        "ir.model.fields",
        "search_read",
        [[("model", "=", model), ("state", "=", "manual")]],
        {"fields": ["name", "ttype", "relation"], "order": "name"},
    )
    if not rows:
        return None
    identity: list[str] = []
    details: list[str] = []
    lines: list[str] = []
    o2m_lists: dict[str, list[str]] = {}
    for row in rows:
        name = row["name"]
        ttype = row["ttype"]
        if name == "x_name":
            identity.insert(0, name)
        elif ttype == "many2one":
            identity.append(name)
        elif ttype == "one2many":
            lines.append(name)
            # Best-effort child columns: x_name only (safe default)
            o2m_lists[name] = ["x_name"]
        elif ttype not in {"binary", "html"}:
            details.append(name)
    groups: list[FormGroupLayout] = []
    if identity:
        groups.append(FormGroupLayout(string="Identity", fields=identity))
    if details:
        groups.append(FormGroupLayout(string="Details", fields=details))
    if lines:
        groups.append(FormGroupLayout(string="Lines", fields=lines))
    if not groups:
        return None
    return ModelFormLayout(
        model=model,
        string=string or model,
        groups=groups,
        o2m_lists=o2m_lists,
    )
