"""Serialize a narrow Studio-like view tree into Odoo view XML.

Supported tags (80/20): field, group, notebook/page, button, list/tree columns,
search fields, kanban, calendar, graph, pivot, map, activity, gantt, cohort, grid.
No full Odoo directive coverage — expand deliberately.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Literal
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from pydantic import BaseModel, Field

from odoo_client.field_attrs import emit_field_modifiers


class FieldNode(BaseModel):
    kind: Literal["field"] = "field"
    name: str
    string: str | None = None
    required: bool | str | None = None
    readonly: bool | str | None = None
    invisible: str | None = None  # domain / expr
    widget: str | None = None
    options: str | None = None  # JSON string for widget options (e.g. image size)


class ButtonNode(BaseModel):
    """Form button. Prefer ``type="action"`` + numeric ``name`` (action id).

    ``type="object"`` requires a Python method on the model (Option A modules).
    Smart buttons use ``class_name="oe_stat_button"`` + optional ``icon``.
    When ``count_field`` is set, emit ``<field widget="statinfo"/>`` for the badge.
    """

    kind: Literal["button"] = "button"
    string: str
    name: str | None = None
    type: str = "action"
    class_name: str | None = Field(default=None, alias="class")
    icon: str | None = None
    context: str | None = None
    count_field: str | None = None

    model_config = {"populate_by_name": True}


class GroupNode(BaseModel):
    kind: Literal["group"] = "group"
    string: str | None = None
    children: list["ViewNode"] = Field(default_factory=list)


class PageNode(BaseModel):
    string: str
    children: list["ViewNode"] = Field(default_factory=list)


class NotebookNode(BaseModel):
    kind: Literal["notebook"] = "notebook"
    pages: list[PageNode] = Field(default_factory=list)


ViewNode = FieldNode | ButtonNode | GroupNode | NotebookNode

GroupNode.model_rebuild()
PageNode.model_rebuild()
NotebookNode.model_rebuild()


class FormViewSpec(BaseModel):
    string: str = "Form"
    create: bool | None = Field(
        default=None,
        description="Root create attr (Odoo Can Create); None omits",
    )
    edit: bool | None = Field(
        default=None,
        description="Root edit attr (Odoo Can Edit); None omits",
    )
    delete: bool | None = Field(
        default=None,
        description="Root delete attr (Odoo Can Delete); None omits",
    )
    duplicate: bool | None = Field(
        default=None,
        description="Root duplicate attr; None omits",
    )
    header_buttons: list[ButtonNode] = Field(
        default_factory=list,
        description="Rendered inside <header> (status / workflow style)",
    )
    statusbar_field: str | None = Field(
        default=None,
        description="Selection/many2one field rendered as widget=statusbar in header",
    )
    statusbar_visible: str | None = Field(
        default=None,
        description="Comma-separated statusbar_visible values",
    )
    button_box: list[ButtonNode] = Field(
        default_factory=list,
        description="Smart buttons inside sheet oe_button_box",
    )
    children: list[ViewNode] = Field(default_factory=list)


class ListViewSpec(BaseModel):
    string: str = "List"
    create: bool | None = None
    edit: bool | None = None
    delete: bool | None = None
    multi_edit: bool | None = Field(
        default=None,
        description="Mass editing (multi_edit) on list root",
    )
    default_order: str | None = Field(
        default=None,
        description="Sort By — Odoo default_order string",
    )
    columns: list[FieldNode] = Field(default_factory=list)
    decoration_danger: str | None = None
    decoration_info: str | None = None
    decoration_muted: str | None = None
    sample: bool | None = Field(
        default=None,
        description='When True, emit sample="1" on list root for demo data',
    )


class SearchFilterNode(BaseModel):
    kind: Literal["filter"] = "filter"
    name: str
    string: str
    domain: str | None = None
    context: str | None = None


class SearchViewSpec(BaseModel):
    string: str = "Search"
    fields: list[FieldNode] = Field(default_factory=list)
    filters: list[SearchFilterNode] = Field(default_factory=list)
    group_by_filters: list[SearchFilterNode] = Field(default_factory=list)


class KanbanViewSpec(BaseModel):
    string: str = "Kanban"
    records_fields: list[str] = Field(default_factory=list)
    default_group_by: str | None = None
    create: bool | None = None
    quick_create: bool | None = None
    sample: bool | None = None


class AxisFieldNode(BaseModel):
    """Field role in graph/pivot arches (``type`` = row | col | measure)."""

    kind: Literal["field"] = "field"
    name: str
    type: Literal["row", "col", "measure"] | None = None
    interval: str | None = None
    string: str | None = None


class CalendarViewSpec(BaseModel):
    string: str = "Calendar"
    date_start: str
    date_stop: str | None = None
    color: str | None = None
    mode: str | None = None  # day | week | month
    fields: list[FieldNode] = Field(default_factory=list)


class GraphViewSpec(BaseModel):
    string: str = "Graph"
    type: Literal["bar", "line", "pie"] = "bar"
    fields: list[AxisFieldNode] = Field(default_factory=list)
    sample: bool | None = None


class PivotViewSpec(BaseModel):
    string: str = "Pivot"
    fields: list[AxisFieldNode] = Field(default_factory=list)
    sample: bool | None = None


class MapViewSpec(BaseModel):
    """Map arch (``ir.ui.view`` type=map; contact/res_partner field gated).

    Public docs: https://www.odoo.com/documentation/19.0/developer/reference/user_interface/view_architectures.html#map
    """

    string: str = "Map"
    res_partner: str | None = None
    routing: bool | None = None
    default_order: str | None = None
    fields: list[FieldNode] = Field(default_factory=list)


class ActivityViewSpec(BaseModel):
    """Activity view — field list shown in the activity stream panel."""

    string: str = "Activity"
    fields: list[FieldNode] = Field(default_factory=list)


class GanttViewSpec(BaseModel):
    """Gantt arch (often module-gated: web_gantt / project). date_start required.

    Public docs: https://www.odoo.com/documentation/19.0/developer/reference/user_interface/view_architectures.html#gantt
    """

    string: str = "Gantt"
    date_start: str
    date_stop: str | None = None
    default_group_by: str | None = None
    default_scale: str | None = None
    dependency_field: str | None = None
    allow_drag_drop: bool | None = None
    color: str | None = None
    progress: str | None = None
    decoration_danger: str | None = None
    fields: list[FieldNode] = Field(default_factory=list)


class CohortViewSpec(BaseModel):
    """Cohort arch (module/version gated). date_start required."""

    string: str = "Cohort"
    date_start: str
    date_stop: str | None = None
    interval: Literal["day", "week", "month", "year"] | None = "week"
    mode: Literal["retention", "churn"] | None = "retention"
    timeline: Literal["forward", "backward"] | None = None
    measure: str | None = None
    fields: list[FieldNode] = Field(default_factory=list)


class GridViewSpec(BaseModel):
    """Grid/planning arch (EE/module-gated — public docs attrs).

    Public docs: https://www.odoo.com/documentation/19.0/developer/reference/user_interface/view_architectures.html#grid
    """

    string: str = "Grid"
    row_field: str | None = None
    col_field: str | None = None
    measure: str | None = None
    adjustment: str | None = None
    date_start: str | None = None
    date_stop: str | None = None
    fields: list[FieldNode] = Field(default_factory=list)


def _set_bool_attr(el: Element, key: str, value: bool | None) -> None:
    if value is True:
        el.set(key, "1")
    elif value is False:
        el.set(key, "0")


def _parse_bool_attr(raw: str | None) -> bool | None:
    if raw is None:
        return None
    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes"}:
        return True
    if lowered in {"0", "false", "no"}:
        return False
    return None


def _render_node(parent: Element, node: ViewNode, *, major: int = 19) -> None:
    if isinstance(node, FieldNode):
        el = SubElement(parent, "field")
        el.set("name", node.name)
        if node.string:
            el.set("string", node.string)
        for key, val in emit_field_modifiers(
            major=major,
            required=node.required,
            readonly=node.readonly,
            invisible=node.invisible,
        ).items():
            el.set(key, val)
        if node.widget:
            el.set("widget", node.widget)
        if node.options:
            el.set("options", node.options)
        return

    if isinstance(node, ButtonNode):
        _render_button(parent, node)
        return

    if isinstance(node, GroupNode):
        el = SubElement(parent, "group")
        if node.string:
            el.set("string", node.string)
        for child in node.children:
            _render_node(el, child, major=major)
        return

    if isinstance(node, NotebookNode):
        el = SubElement(parent, "notebook")
        for page in node.pages:
            page_el = SubElement(el, "page")
            page_el.set("string", page.string)
            kids = list(page.children)
            if kids and not any(isinstance(c, GroupNode) for c in kids):
                group_el = SubElement(page_el, "group")
                for child in kids:
                    _render_node(group_el, child, major=major)
            else:
                for child in kids:
                    _render_node(page_el, child, major=major)
        return

    raise TypeError(f"Unsupported node: {type(node)!r}")


def _render_button(parent: Element, node: ButtonNode) -> Element:
    el = SubElement(parent, "button")
    el.set("string", node.string)
    el.set("type", node.type or "action")
    if node.name:
        el.set("name", str(node.name))
    if node.class_name:
        el.set("class", node.class_name)
    if node.icon:
        el.set("icon", node.icon)
    if node.context:
        el.set("context", node.context)
    is_smart = bool(node.class_name and "oe_stat_button" in node.class_name)
    if node.count_field:
        fld = SubElement(el, "field")
        fld.set("name", node.count_field)
        fld.set("widget", "statinfo")
        fld.set("string", node.string)
    elif is_smart:
        # Smart-button label when no count field
        info = SubElement(el, "div")
        info.set("class", "o_stat_info")
        text = SubElement(info, "span")
        text.set("class", "o_stat_text")
        text.text = node.string
    return el


def _pretty_xml(root: Element) -> str:
    rough = tostring(root, encoding="unicode")
    parsed = minidom.parseString(rough)
    # minidom adds XML declaration; Odoo arch usually doesn't need it.
    body = parsed.documentElement.toprettyxml(indent="  ")
    # Strip declaration line if present
    lines = [ln for ln in body.splitlines() if ln.strip()]
    return "\n".join(lines)


def render_form_arch(spec: FormViewSpec, *, major: int = 19) -> str:
    root = Element("form")
    root.set("string", spec.string)
    _set_bool_attr(root, "create", spec.create)
    _set_bool_attr(root, "edit", spec.edit)
    _set_bool_attr(root, "delete", spec.delete)
    _set_bool_attr(root, "duplicate", spec.duplicate)
    if spec.header_buttons or spec.statusbar_field:
        header = SubElement(root, "header")
        for btn in spec.header_buttons:
            _render_button(header, btn)
        if spec.statusbar_field:
            sb = SubElement(header, "field")
            sb.set("name", spec.statusbar_field)
            sb.set("widget", "statusbar")
            if spec.statusbar_visible:
                sb.set("statusbar_visible", spec.statusbar_visible)
    sheet = SubElement(root, "sheet")
    if spec.button_box:
        box = SubElement(sheet, "div")
        box.set("name", "button_box")
        box.set("class", "oe_button_box")
        for btn in spec.button_box:
            # Ensure smart-button chrome
            if not btn.class_name:
                btn = btn.model_copy(update={"class_name": "oe_stat_button"})
            elif "oe_stat_button" not in btn.class_name:
                btn = btn.model_copy(
                    update={"class_name": f"{btn.class_name} oe_stat_button".strip()}
                )
            _render_button(box, btn)
    for child in spec.children:
        _render_node(sheet, child, major=major)
    return _pretty_xml(root)


def render_list_arch(spec: ListViewSpec, *, major: int = 19) -> str:
    # Odoo 19 prefers <list>; older used <tree>. Emit <list>.
    root = Element("list")
    root.set("string", spec.string)
    _set_bool_attr(root, "create", spec.create)
    _set_bool_attr(root, "edit", spec.edit)
    _set_bool_attr(root, "delete", spec.delete)
    _set_bool_attr(root, "multi_edit", spec.multi_edit)
    if spec.sample:
        root.set("sample", "1")
    if spec.default_order:
        root.set("default_order", spec.default_order)
    if spec.decoration_danger:
        root.set("decoration-danger", spec.decoration_danger)
    if spec.decoration_info:
        root.set("decoration-info", spec.decoration_info)
    if spec.decoration_muted:
        root.set("decoration-muted", spec.decoration_muted)
    for col in spec.columns:
        _render_node(root, col, major=major)
    return _pretty_xml(root)


def render_search_arch(spec: SearchViewSpec, *, major: int = 19) -> str:
    root = Element("search")
    root.set("string", spec.string)
    for fld in spec.fields:
        _render_node(root, fld, major=major)
    for filt in spec.filters:
        el = SubElement(root, "filter")
        el.set("name", filt.name)
        el.set("string", filt.string)
        if filt.domain:
            el.set("domain", filt.domain)
        if filt.context:
            el.set("context", filt.context)
    if spec.group_by_filters:
        group_el = SubElement(root, "group")
        group_el.set("expand", "0")
        group_el.set("string", "Group By")
        for filt in spec.group_by_filters:
            el = SubElement(group_el, "filter")
            el.set("name", filt.name)
            el.set("string", filt.string)
            if filt.context:
                el.set("context", filt.context)
            elif filt.domain:
                el.set("domain", filt.domain)
    return _pretty_xml(root)


def render_kanban_arch(
    string: str = "Kanban",
    records_fields: list[str] | None = None,
    default_group_by: str | None = None,
    create: bool | None = None,
    quick_create: bool | None = None,
    sample: bool | None = None,
) -> str:
    """Render a simple Odoo 19 kanban board with field cards.

    Cards list each field by name. Optional ``default_group_by`` sets the
    column grouping field (selection / boolean / many2one).
    """
    fields = list(records_fields or [])
    root = Element("kanban")
    root.set("string", string)
    if default_group_by:
        root.set("default_group_by", default_group_by)
    _set_bool_attr(root, "create", create)
    _set_bool_attr(root, "quick_create", quick_create)
    if sample:
        root.set("sample", "1")
    templates = SubElement(root, "templates")
    card = SubElement(templates, "t")
    card.set("t-name", "card")
    for name in fields:
        field_el = SubElement(card, "field")
        field_el.set("name", name)
    if not fields:
        # Valid empty card so Odoo accepts the arch during design
        SubElement(card, "div")
    return _pretty_xml(root)


def _render_axis_field(parent: Element, node: AxisFieldNode) -> None:
    el = SubElement(parent, "field")
    el.set("name", node.name)
    if node.type:
        el.set("type", node.type)
    if node.interval:
        el.set("interval", node.interval)
    if node.string:
        el.set("string", node.string)


def render_calendar_arch(spec: CalendarViewSpec) -> str:
    root = Element("calendar")
    root.set("string", spec.string)
    root.set("date_start", spec.date_start)
    if spec.date_stop:
        root.set("date_stop", spec.date_stop)
    if spec.color:
        root.set("color", spec.color)
    if spec.mode:
        root.set("mode", spec.mode)
    for fld in spec.fields:
        _render_node(root, fld)
    return _pretty_xml(root)


def render_graph_arch(spec: GraphViewSpec) -> str:
    root = Element("graph")
    root.set("string", spec.string)
    root.set("type", spec.type)
    if spec.sample:
        root.set("sample", "1")
    for fld in spec.fields:
        _render_axis_field(root, fld)
    return _pretty_xml(root)


def render_pivot_arch(spec: PivotViewSpec) -> str:
    root = Element("pivot")
    root.set("string", spec.string)
    if spec.sample:
        root.set("sample", "1")
    for fld in spec.fields:
        _render_axis_field(root, fld)
    return _pretty_xml(root)


def render_map_arch(spec: MapViewSpec) -> str:
    """Map render — contact field via ``res_partner`` attribute."""
    root = Element("map")
    root.set("string", spec.string)
    if spec.res_partner:
        root.set("res_partner", spec.res_partner)
    _set_bool_attr(root, "routing", spec.routing)
    if spec.default_order:
        root.set("default_order", spec.default_order)
    for fld in spec.fields:
        _render_node(root, fld)
    return _pretty_xml(root)


def render_activity_arch(spec: ActivityViewSpec) -> str:
    """Activity views require OWL template ``activity-box`` (mail ActivityController).

    Bare ``<activity><field/></activity>`` validates in ORM but crashes the web
    client with ``Missing template: "undefined"``. Match stock arches (e.g.
    ``res.partner.activity``): optional preload fields + ``<templates>``.
    """
    root = Element("activity")
    root.set("string", spec.string)
    templates = SubElement(root, "templates")
    box = SubElement(templates, "div")
    box.set("t-name", "activity-box")
    if spec.fields:
        body = SubElement(box, "div")
        body.set("class", "ms-2")
        for fld in spec.fields:
            el = SubElement(body, "field")
            el.set("name", fld.name)
            if fld.string:
                el.set("string", fld.string)
            el.set("display", "full")
            el.set("class", "o_text_block")
            _set_bool_attr(el, "required", fld.required)
            _set_bool_attr(el, "readonly", fld.readonly)
            if fld.invisible:
                el.set("invisible", fld.invisible)
            if fld.widget:
                el.set("widget", fld.widget)
    return _pretty_xml(root)


def render_gantt_arch(spec: GanttViewSpec) -> str:
    root = Element("gantt")
    root.set("string", spec.string)
    root.set("date_start", spec.date_start)
    if spec.date_stop:
        root.set("date_stop", spec.date_stop)
    if spec.default_group_by:
        root.set("default_group_by", spec.default_group_by)
    if spec.default_scale:
        root.set("default_scale", spec.default_scale)
    if spec.dependency_field:
        root.set("dependency_field", spec.dependency_field)
    _set_bool_attr(root, "allow_drag_drop", spec.allow_drag_drop)
    if spec.color:
        root.set("color", spec.color)
    if spec.progress:
        root.set("progress", spec.progress)
    if spec.decoration_danger:
        root.set("decoration-danger", spec.decoration_danger)
    for fld in spec.fields:
        _render_node(root, fld)
    return _pretty_xml(root)


def render_cohort_arch(spec: CohortViewSpec) -> str:
    root = Element("cohort")
    root.set("string", spec.string)
    root.set("date_start", spec.date_start)
    if spec.date_stop:
        root.set("date_stop", spec.date_stop)
    if spec.interval:
        root.set("interval", spec.interval)
    if spec.mode:
        root.set("mode", spec.mode)
    if spec.timeline:
        root.set("timeline", spec.timeline)
    if spec.measure:
        root.set("measure", spec.measure)
    for fld in spec.fields:
        _render_node(root, fld)
    return _pretty_xml(root)


def render_grid_arch(spec: GridViewSpec) -> str:
    root = Element("grid")
    root.set("string", spec.string)
    if spec.row_field:
        root.set("row_field", spec.row_field)
    if spec.col_field:
        root.set("col_field", spec.col_field)
    if spec.measure:
        root.set("measure", spec.measure)
    if spec.adjustment:
        root.set("adjustment", spec.adjustment)
    if spec.date_start:
        root.set("date_start", spec.date_start)
    if spec.date_stop:
        root.set("date_stop", spec.date_stop)
    for fld in spec.fields:
        _render_node(root, fld)
    return _pretty_xml(root)


def _major_from_payload(payload: dict[str, Any]) -> int:
    raw = payload.get("major")
    if raw is None:
        return 19
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 19


def render_arch(view_type: str, payload: dict[str, Any]) -> str:
    major = _major_from_payload(payload)
    if view_type in {"form"}:
        return render_form_arch(FormViewSpec.model_validate(payload), major=major)
    if view_type in {"list", "tree"}:
        return render_list_arch(ListViewSpec.model_validate(payload), major=major)
    if view_type == "search":
        return render_search_arch(SearchViewSpec.model_validate(payload), major=major)
    if view_type == "kanban":
        if "records_fields" in payload or "default_group_by" in payload or "string" in payload:
            spec = KanbanViewSpec.model_validate(
                {
                    "string": payload.get("string", "Kanban"),
                    "records_fields": payload.get("records_fields")
                    or [
                        f.get("name")
                        for f in payload.get("fields", [])
                        if isinstance(f, dict) and f.get("name")
                    ],
                    "default_group_by": payload.get("default_group_by"),
                    "create": payload.get("create"),
                    "quick_create": payload.get("quick_create"),
                    "sample": payload.get("sample"),
                }
            )
            return render_kanban_arch(
                string=spec.string,
                records_fields=spec.records_fields,
                default_group_by=spec.default_group_by,
                create=spec.create,
                quick_create=spec.quick_create,
                sample=spec.sample,
            )
        return render_kanban_arch(
            string=payload.get("string", "Kanban"),
            records_fields=payload.get("records_fields"),
            default_group_by=payload.get("default_group_by"),
            create=payload.get("create"),
            quick_create=payload.get("quick_create"),
            sample=payload.get("sample"),
        )
    if view_type == "calendar":
        return render_calendar_arch(CalendarViewSpec.model_validate(payload))
    if view_type == "graph":
        return render_graph_arch(GraphViewSpec.model_validate(payload))
    if view_type == "pivot":
        return render_pivot_arch(PivotViewSpec.model_validate(payload))
    if view_type == "map":
        return render_map_arch(MapViewSpec.model_validate(payload))
    if view_type == "activity":
        return render_activity_arch(ActivityViewSpec.model_validate(payload))
    if view_type == "gantt":
        return render_gantt_arch(GanttViewSpec.model_validate(payload))
    if view_type == "cohort":
        return render_cohort_arch(CohortViewSpec.model_validate(payload))
    if view_type == "grid":
        return render_grid_arch(GridViewSpec.model_validate(payload))
    raise ValueError(f"Unsupported view type for designer: {view_type!r}")


def field_names_in_arch(arch: str) -> list[str]:
    """Ordered unique field names referenced in arch (best-effort regex)."""
    import re

    names: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r'<field\b[^>]*\bname=["\']([^"\']+)["\']', arch):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def inject_field_into_arch(
    arch: str, field_name: str, *, view_type: str, widget: str | None = None
) -> str:
    """Append a field node into form/list/search arch if not already present.

    Form: insert before closing </group> of first group, else before </sheet>, else before </form>.
    List/tree: insert before closing </list> or </tree>.
    Search: insert before closing </search>.
    """
    if f'name="{field_name}"' in arch or f"name='{field_name}'" in arch:
        return arch

    if widget:
        field_tag = f'<field name="{field_name}" widget="{widget}"/>'
    else:
        field_tag = f'<field name="{field_name}"/>'
    vt = view_type if view_type != "tree" else "list"

    if vt == "list":
        for closer in ("</list>", "</tree>"):
            idx = arch.rfind(closer)
            if idx != -1:
                return arch[:idx] + field_tag + arch[idx:]
        return arch + field_tag

    if vt == "search":
        idx = arch.rfind("</search>")
        if idx != -1:
            return arch[:idx] + field_tag + arch[idx:]
        return arch + field_tag

    # form
    group_close = arch.find("</group>")
    if group_close != -1:
        return arch[:group_close] + field_tag + arch[group_close:]
    for closer in ("</sheet>", "</form>"):
        idx = arch.rfind(closer)
        if idx != -1:
            return arch[:idx] + field_tag + arch[idx:]
    return arch + field_tag


def render_inherit_field_arch(
    field_name: str,
    view_type: str,
    *,
    parent_arch: str | None = None,
    widget: str | None = None,
) -> str:
    """Build xpath extension arch that injects a field into a parent view.

    Prefer inherit-over-mutate so existing module views stay untouched.
    Odoo validates every xpath against the parent — emit only one list/tree
    expr matching the parent's root tag (Odoo 19 uses <list>).
    """
    vt = view_type if view_type != "tree" else "list"
    # Widget is form-oriented (e.g. barcode); skip on list/search injects.
    use_widget = widget if vt == "form" else None
    if use_widget:
        field_tag = f'<field name="{field_name}" widget="{use_widget}"/>'
    else:
        field_tag = f'<field name="{field_name}"/>'
    parent = parent_arch or ""

    if vt == "form":
        # Prefer first <group> so Odoo renders field labels (sheet children often look bare).
        if "<group" in parent:
            expr = "//group[1]"
        elif "<sheet" in parent or not parent:
            expr = "//sheet"
        else:
            expr = "//form"
        return (
            "<data>\n"
            f'  <xpath expr="{expr}" position="inside">\n'
            f"    {field_tag}\n"
            "  </xpath>\n"
            "</data>"
        )

    if vt == "list":
        if "<tree" in parent and "<list" not in parent:
            expr = "//tree"
        else:
            expr = "//list"
        return (
            "<data>\n"
            f'  <xpath expr="{expr}" position="inside">\n'
            f"    {field_tag}\n"
            "  </xpath>\n"
            "</data>"
        )

    if vt == "search":
        return (
            "<data>\n"
            '  <xpath expr="//search" position="inside">\n'
            f"    {field_tag}\n"
            "  </xpath>\n"
            "</data>"
        )

    raise ValueError(f"Unsupported inherit inject view_type={view_type!r}")


def _parse_modifier_attr(raw: str | None) -> bool | str | None:
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    if s in {"1", "True", "true"}:
        return True
    if s in {"0", "False", "false"}:
        return False
    if s.startswith("[") and s.endswith("]"):
        return s
    return s


def _domain_from_attrs_value(value: Any) -> str | None:
    if value is True:
        return "1"
    if value is False or value is None:
        return None
    if isinstance(value, list):
        return repr(value)
    if isinstance(value, str):
        return value
    return str(value)


def _parse_field_el(el: Element) -> FieldNode:
    required: bool | str | None = None
    readonly: bool | str | None = None
    invisible: str | None = None

    attrs_raw = el.get("attrs")
    if attrs_raw:
        try:
            attrs = ast.literal_eval(attrs_raw)
            if isinstance(attrs, dict):
                required = _domain_from_attrs_value(attrs.get("required"))
                readonly = _domain_from_attrs_value(attrs.get("readonly"))
                inv = _domain_from_attrs_value(attrs.get("invisible"))
                invisible = inv if inv else None
        except (SyntaxError, ValueError):
            pass
    else:
        required = _parse_modifier_attr(el.get("required"))
        readonly = _parse_modifier_attr(el.get("readonly"))
        invisible = el.get("invisible")

    return FieldNode(
        name=el.get("name") or "",
        string=el.get("string"),
        required=required,
        readonly=readonly,
        invisible=invisible,
        widget=el.get("widget"),
        options=el.get("options"),
    )


def _parse_button_el(el: Element) -> ButtonNode:
    label = el.get("string")
    count_field: str | None = None
    for child in list(el):
        if child.tag == "field" and child.get("widget") == "statinfo":
            count_field = child.get("name")
            if not label:
                label = child.get("string")
            break
    if not label:
        # Prefer nested o_stat_text for smart buttons
        for span in el.iter("span"):
            if span.get("class") == "o_stat_text" and (span.text or "").strip():
                label = span.text.strip()
                break
    return ButtonNode(
        string=label or "Button",
        name=el.get("name"),
        type=el.get("type") or "action",
        class_name=el.get("class"),
        icon=el.get("icon"),
        context=el.get("context"),
        count_field=count_field,
    )


def _parse_view_children(parent: Element) -> list[ViewNode]:
    nodes: list[ViewNode] = []
    for child in list(parent):
        tag = child.tag
        if tag == "field":
            if child.get("name"):
                nodes.append(_parse_field_el(child))
        elif tag == "button":
            nodes.append(_parse_button_el(child))
        elif tag == "group":
            nodes.append(
                GroupNode(
                    string=child.get("string"),
                    children=_parse_view_children(child),
                )
            )
        elif tag == "notebook":
            pages: list[PageNode] = []
            for page_el in child.findall("page"):
                raw_kids = _parse_view_children(page_el)
                # Designer stores flat fields on a page; unwrap a single unlabeled
                # group inserted by render_form_arch for Odoo label layout.
                if (
                    len(raw_kids) == 1
                    and isinstance(raw_kids[0], GroupNode)
                    and not raw_kids[0].string
                ):
                    page_kids = raw_kids[0].children
                else:
                    page_kids = raw_kids
                pages.append(
                    PageNode(
                        string=page_el.get("string") or "Page",
                        children=page_kids,
                    )
                )
            nodes.append(NotebookNode(pages=pages))
    return nodes


def parse_form_arch(arch: str) -> FormViewSpec:
    from xml.etree.ElementTree import fromstring

    root = fromstring(arch)
    if root.tag != "form":
        raise ValueError(f"Expected <form>, got <{root.tag}>")

    header_buttons: list[ButtonNode] = []
    statusbar_field: str | None = None
    statusbar_visible: str | None = None
    header = root.find("header")
    if header is not None:
        for el in list(header):
            if el.tag == "button":
                header_buttons.append(_parse_button_el(el))
            elif el.tag == "field" and el.get("widget") == "statusbar":
                statusbar_field = el.get("name")
                statusbar_visible = el.get("statusbar_visible")

    button_box: list[ButtonNode] = []
    sheet = root.find("sheet")
    container = sheet if sheet is not None else root
    # Pull smart buttons out of button_box so they don't pollute group children
    for child in list(container):
        if child.tag == "div" and (
            child.get("name") == "button_box"
            or (child.get("class") or "").find("oe_button_box") >= 0
        ):
            for btn_el in child.findall("button"):
                button_box.append(_parse_button_el(btn_el))
            container.remove(child)

    return FormViewSpec(
        string=root.get("string") or "Form",
        create=_parse_bool_attr(root.get("create")),
        edit=_parse_bool_attr(root.get("edit")),
        delete=_parse_bool_attr(root.get("delete")),
        duplicate=_parse_bool_attr(root.get("duplicate")),
        header_buttons=header_buttons,
        statusbar_field=statusbar_field,
        statusbar_visible=statusbar_visible,
        button_box=button_box,
        children=_parse_view_children(container),
    )


def parse_list_arch(arch: str) -> ListViewSpec:
    from xml.etree.ElementTree import fromstring

    root = fromstring(arch)
    if root.tag not in {"list", "tree"}:
        raise ValueError(f"Expected <list>/<tree>, got <{root.tag}>")
    columns = [_parse_field_el(el) for el in root.findall("field") if el.get("name")]
    return ListViewSpec(
        string=root.get("string") or "List",
        create=_parse_bool_attr(root.get("create")),
        edit=_parse_bool_attr(root.get("edit")),
        delete=_parse_bool_attr(root.get("delete")),
        multi_edit=_parse_bool_attr(root.get("multi_edit")),
        sample=_parse_bool_attr(root.get("sample")),
        default_order=root.get("default_order"),
        columns=columns,
        decoration_danger=root.get("decoration-danger"),
        decoration_info=root.get("decoration-info"),
        decoration_muted=root.get("decoration-muted"),
    )


def parse_search_arch(arch: str) -> SearchViewSpec:
    from xml.etree.ElementTree import fromstring

    root = fromstring(arch)
    if root.tag != "search":
        raise ValueError(f"Expected <search>, got <{root.tag}>")
    fields = [_parse_field_el(el) for el in root.findall("field") if el.get("name")]
    filters: list[SearchFilterNode] = []
    group_by: list[SearchFilterNode] = []
    for el in root.findall("filter"):
        filters.append(
            SearchFilterNode(
                name=el.get("name") or "filter",
                string=el.get("string") or el.get("name") or "Filter",
                domain=el.get("domain"),
                context=el.get("context"),
            )
        )
    for group_el in root.findall("group"):
        for el in group_el.findall("filter"):
            group_by.append(
                SearchFilterNode(
                    name=el.get("name") or "groupby",
                    string=el.get("string") or el.get("name") or "Group",
                    domain=el.get("domain"),
                    context=el.get("context"),
                )
            )
    return SearchViewSpec(
        string=root.get("string") or "Search",
        fields=fields,
        filters=filters,
        group_by_filters=group_by,
    )


def _unwrap_inherit_inner_arch(arch: str) -> str | None:
    """If ``arch`` is a designer inherit replace wrapper, return the replaced body."""
    from xml.etree.ElementTree import fromstring

    try:
        root = fromstring(arch)
    except Exception:  # noqa: BLE001
        return None
    if root.tag != "data":
        return None
    for xpath in root.findall("xpath"):
        if xpath.get("position") != "replace":
            continue
        # Prefer first element child (the replaced view root)
        for child in list(xpath):
            if isinstance(child.tag, str):
                return tostring(child, encoding="unicode")
        text = (xpath.text or "").strip()
        if text:
            return text
    return None


def parse_kanban_arch(arch: str) -> KanbanViewSpec:
    from xml.etree.ElementTree import fromstring

    unwrapped = _unwrap_inherit_inner_arch(arch)
    if unwrapped:
        arch = unwrapped

    root = fromstring(arch)
    if root.tag != "kanban":
        raise ValueError(f"Expected <kanban>, got <{root.tag}>")
    # Prefer ordered fields from the card template; fall back to whole-arch scan.
    names: list[str] = []
    seen: set[str] = set()
    for t_el in root.iter("t"):
        if t_el.get("t-name") != "card":
            continue
        for field_el in t_el.iter("field"):
            name = field_el.get("name")
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        break
    if not names:
        names = field_names_in_arch(arch)
    return KanbanViewSpec(
        string=root.get("string") or "Kanban",
        records_fields=names,
        default_group_by=root.get("default_group_by"),
        create=_parse_bool_attr(root.get("create")),
        quick_create=_parse_bool_attr(root.get("quick_create")),
        sample=_parse_bool_attr(root.get("sample")),
    )


def _parse_axis_field_el(el: Element) -> AxisFieldNode:
    raw_type = el.get("type")
    axis_type: Literal["row", "col", "measure"] | None = None
    if raw_type == "row":
        axis_type = "row"
    elif raw_type == "col":
        axis_type = "col"
    elif raw_type == "measure":
        axis_type = "measure"
    return AxisFieldNode(
        name=el.get("name") or "",
        type=axis_type,
        interval=el.get("interval"),
        string=el.get("string"),
    )


def parse_calendar_arch(arch: str) -> CalendarViewSpec:
    from xml.etree.ElementTree import fromstring

    unwrapped = _unwrap_inherit_inner_arch(arch)
    if unwrapped:
        arch = unwrapped

    root = fromstring(arch)
    if root.tag != "calendar":
        raise ValueError(f"Expected <calendar>, got <{root.tag}>")
    date_start = root.get("date_start")
    if not date_start:
        raise ValueError("calendar arch requires date_start")
    fields = [_parse_field_el(el) for el in root.findall("field") if el.get("name")]
    return CalendarViewSpec(
        string=root.get("string") or "Calendar",
        date_start=date_start,
        date_stop=root.get("date_stop"),
        color=root.get("color"),
        mode=root.get("mode"),
        fields=fields,
    )


def parse_graph_arch(arch: str) -> GraphViewSpec:
    from xml.etree.ElementTree import fromstring

    unwrapped = _unwrap_inherit_inner_arch(arch)
    if unwrapped:
        arch = unwrapped

    root = fromstring(arch)
    if root.tag != "graph":
        raise ValueError(f"Expected <graph>, got <{root.tag}>")
    raw_type = root.get("type") or "bar"
    graph_type: Literal["bar", "line", "pie"] = "bar"
    if raw_type == "line":
        graph_type = "line"
    elif raw_type == "pie":
        graph_type = "pie"
    elif raw_type == "bar":
        graph_type = "bar"
    fields = [
        _parse_axis_field_el(el) for el in root.findall("field") if el.get("name")
    ]
    return GraphViewSpec(
        string=root.get("string") or "Graph",
        type=graph_type,
        fields=fields,
        sample=_parse_bool_attr(root.get("sample")),
    )


def parse_pivot_arch(arch: str) -> PivotViewSpec:
    from xml.etree.ElementTree import fromstring

    unwrapped = _unwrap_inherit_inner_arch(arch)
    if unwrapped:
        arch = unwrapped

    root = fromstring(arch)
    if root.tag != "pivot":
        raise ValueError(f"Expected <pivot>, got <{root.tag}>")
    fields = [
        _parse_axis_field_el(el) for el in root.findall("field") if el.get("name")
    ]
    return PivotViewSpec(
        string=root.get("string") or "Pivot",
        fields=fields,
        sample=_parse_bool_attr(root.get("sample")),
    )


def parse_map_arch(arch: str) -> MapViewSpec:
    from xml.etree.ElementTree import fromstring

    unwrapped = _unwrap_inherit_inner_arch(arch)
    if unwrapped:
        arch = unwrapped

    root = fromstring(arch)
    if root.tag != "map":
        raise ValueError(f"Expected <map>, got <{root.tag}>")
    fields = [_parse_field_el(el) for el in root.findall("field") if el.get("name")]
    return MapViewSpec(
        string=root.get("string") or "Map",
        res_partner=root.get("res_partner"),
        routing=_parse_bool_attr(root.get("routing")),
        default_order=root.get("default_order"),
        fields=fields,
    )


def parse_activity_arch(arch: str) -> ActivityViewSpec:
    from xml.etree.ElementTree import fromstring

    unwrapped = _unwrap_inherit_inner_arch(arch)
    if unwrapped:
        arch = unwrapped

    root = fromstring(arch)
    if root.tag != "activity":
        raise ValueError(f"Expected <activity>, got <{root.tag}>")

    fields: list[FieldNode] = []
    templates = root.find("templates")
    if templates is not None:
        box = next(
            (
                el
                for el in templates.iter()
                if el.tag == "div" and el.get("t-name") == "activity-box"
            ),
            None,
        )
        if box is not None:
            fields = [
                _parse_field_el(el) for el in box.iter("field") if el.get("name")
            ]
    if not fields:
        # Legacy designer arches (pre activity-box) or preload-only fields
        fields = [_parse_field_el(el) for el in root.findall("field") if el.get("name")]
    return ActivityViewSpec(
        string=root.get("string") or "Activity",
        fields=fields,
    )


def parse_gantt_arch(arch: str) -> GanttViewSpec:
    from xml.etree.ElementTree import fromstring

    unwrapped = _unwrap_inherit_inner_arch(arch)
    if unwrapped:
        arch = unwrapped

    root = fromstring(arch)
    if root.tag != "gantt":
        raise ValueError(f"Expected <gantt>, got <{root.tag}>")
    date_start = root.get("date_start")
    if not date_start:
        raise ValueError("gantt arch requires date_start")
    fields = [_parse_field_el(el) for el in root.findall("field") if el.get("name")]
    return GanttViewSpec(
        string=root.get("string") or "Gantt",
        date_start=date_start,
        date_stop=root.get("date_stop"),
        default_group_by=root.get("default_group_by"),
        default_scale=root.get("default_scale"),
        dependency_field=root.get("dependency_field"),
        allow_drag_drop=_parse_bool_attr(root.get("allow_drag_drop")),
        color=root.get("color"),
        progress=root.get("progress"),
        decoration_danger=root.get("decoration-danger"),
        fields=fields,
    )


def parse_cohort_arch(arch: str) -> CohortViewSpec:
    from xml.etree.ElementTree import fromstring

    unwrapped = _unwrap_inherit_inner_arch(arch)
    if unwrapped:
        arch = unwrapped

    root = fromstring(arch)
    if root.tag != "cohort":
        raise ValueError(f"Expected <cohort>, got <{root.tag}>")
    date_start = root.get("date_start")
    if not date_start:
        raise ValueError("cohort arch requires date_start")
    raw_interval = root.get("interval") or "week"
    interval: Literal["day", "week", "month", "year"] | None = "week"
    if raw_interval in {"day", "week", "month", "year"}:
        interval = raw_interval  # type: ignore[assignment]
    raw_mode = root.get("mode") or "retention"
    mode: Literal["retention", "churn"] | None = "retention"
    if raw_mode in {"retention", "churn"}:
        mode = raw_mode  # type: ignore[assignment]
    raw_timeline = root.get("timeline")
    timeline: Literal["forward", "backward"] | None = None
    if raw_timeline in {"forward", "backward"}:
        timeline = raw_timeline  # type: ignore[assignment]
    fields = [_parse_field_el(el) for el in root.findall("field") if el.get("name")]
    return CohortViewSpec(
        string=root.get("string") or "Cohort",
        date_start=date_start,
        date_stop=root.get("date_stop"),
        interval=interval,
        mode=mode,
        timeline=timeline,
        measure=root.get("measure"),
        fields=fields,
    )


def parse_grid_arch(arch: str) -> GridViewSpec:
    from xml.etree.ElementTree import fromstring

    unwrapped = _unwrap_inherit_inner_arch(arch)
    if unwrapped:
        arch = unwrapped

    root = fromstring(arch)
    if root.tag != "grid":
        raise ValueError(f"Expected <grid>, got <{root.tag}>")
    fields = [_parse_field_el(el) for el in root.findall("field") if el.get("name")]
    return GridViewSpec(
        string=root.get("string") or "Grid",
        row_field=root.get("row_field"),
        col_field=root.get("col_field"),
        measure=root.get("measure"),
        adjustment=root.get("adjustment"),
        date_start=root.get("date_start"),
        date_stop=root.get("date_stop"),
        fields=fields,
    )


def parse_arch(view_type: str, arch: str) -> dict[str, Any]:
    """Parse Odoo view XML into a designer-friendly spec dict."""
    vt = "list" if view_type == "tree" else view_type
    if vt == "form":
        return parse_form_arch(arch).model_dump(by_alias=True)
    if vt == "list":
        return parse_list_arch(arch).model_dump()
    if vt == "search":
        return parse_search_arch(arch).model_dump()
    if vt == "kanban":
        return parse_kanban_arch(arch).model_dump()
    if vt == "calendar":
        return parse_calendar_arch(arch).model_dump()
    if vt == "graph":
        return parse_graph_arch(arch).model_dump()
    if vt == "pivot":
        return parse_pivot_arch(arch).model_dump()
    if vt == "map":
        return parse_map_arch(arch).model_dump()
    if vt == "activity":
        return parse_activity_arch(arch).model_dump()
    if vt == "gantt":
        return parse_gantt_arch(arch).model_dump()
    if vt == "cohort":
        return parse_cohort_arch(arch).model_dump()
    if vt == "grid":
        return parse_grid_arch(arch).model_dump()
    raise ValueError(f"Unsupported parse view_type={view_type!r}")


def render_inherit_replace_arch(view_type: str, inner_arch: str) -> str:
    """Wrap a full view arch as an inherit that replaces the root node."""
    vt = "list" if view_type == "tree" else view_type
    # Strip XML declaration / pretty whitespace that breaks xpath replace bodies
    body = inner_arch.strip()
    if body.startswith("<?xml"):
        body = "\n".join(body.splitlines()[1:]).strip()
    if vt == "form":
        expr = "//form"
    elif vt == "list":
        expr = "//list" if "<list" in body or "<list" not in body else "//tree"
        if body.lstrip().startswith("<tree"):
            expr = "//tree"
        else:
            expr = "//list"
    elif vt == "search":
        expr = "//search"
    elif vt == "kanban":
        expr = "//kanban"
    elif vt == "calendar":
        expr = "//calendar"
    elif vt == "graph":
        expr = "//graph"
    elif vt == "pivot":
        expr = "//pivot"
    elif vt == "map":
        expr = "//map"
    elif vt == "activity":
        expr = "//activity"
    elif vt == "gantt":
        expr = "//gantt"
    elif vt == "cohort":
        expr = "//cohort"
    elif vt == "grid":
        expr = "//grid"
    else:
        raise ValueError(f"Unsupported inherit replace view_type={view_type!r}")
    return (
        "<data>\n"
        f'  <xpath expr="{expr}" position="replace">\n'
        f"    {body}\n"
        "  </xpath>\n"
        "</data>"
    )


def render_inherit_xpath_arch(
    *,
    expr: str,
    position: Literal[
        "inside", "after", "before", "replace", "attributes", "move"
    ] = "inside",
    body_xml: str = "",
) -> str:
    """Build a single-xpath inherit arch for power users / Designer xpath editor."""
    expr_clean = expr.strip()
    if not expr_clean:
        raise ValueError("xpath expr is required")
    if position == "move":
        return (
            "<data>\n"
            f'  <xpath expr="{expr_clean}" position="move"/>\n'
            "</data>"
        )
    body = body_xml.strip()
    if not body:
        raise ValueError("xpath body_xml is required")
    return (
        "<data>\n"
        f'  <xpath expr="{expr_clean}" position="{position}">\n'
        f"    {body}\n"
        "  </xpath>\n"
        "</data>"
    )


def render_xpath_wrap_arch(*, expr: str, wrapper_xml: str) -> str:
    """Wrap the matched node using Odoo ``$0`` placeholder (position replace)."""
    wrapper = wrapper_xml.strip()
    if not wrapper:
        raise ValueError("wrapper_xml is required")
    if "$0" not in wrapper:
        raise ValueError("wrapper_xml must contain $0 for the matched node")
    return render_inherit_xpath_arch(expr=expr, position="replace", body_xml=wrapper)


def render_xpath_move_arch(*, expr: str) -> str:
    """Move the matched node elsewhere (parent arch defines drop target)."""
    return render_inherit_xpath_arch(expr=expr, position="move")


def _normalize_smart_button(node: ButtonNode) -> ButtonNode:
    if not node.class_name:
        return node.model_copy(update={"class_name": "oe_stat_button"})
    if "oe_stat_button" not in node.class_name:
        return node.model_copy(
            update={"class_name": f"{node.class_name} oe_stat_button".strip()}
        )
    return node


def _serialize_button_nodes(buttons: list[ButtonNode]) -> str:
    """Serialize smart-button nodes to XML fragment (no wrapper)."""
    holder = Element("div")
    for btn in buttons:
        _render_button(holder, _normalize_smart_button(btn))
    parts = [tostring(child, encoding="unicode") for child in list(holder)]
    return "\n".join(parts)


def render_inherit_smart_buttons_arch(
    buttons: list[ButtonNode],
    *,
    parent_arch: str | None = None,
) -> str:
    """Build an inherit arch that injects smart buttons without mutating the primary form.

    Prefer ``//div[@name='button_box']`` (Contacts and most stock forms). If the parent
    has no button box, create one before the first sheet child. Never rewrite the parent.
    """
    if not buttons:
        raise ValueError("buttons must be non-empty")
    parent = parent_arch or ""
    inner = _serialize_button_nodes(buttons)
    if 'name="button_box"' in parent or "name='button_box'" in parent:
        return render_inherit_xpath_arch(
            expr="//div[@name='button_box']",
            position="inside",
            body_xml=inner,
        )
    if "oe_button_box" in parent:
        return render_inherit_xpath_arch(
            expr="//div[contains(@class,'oe_button_box')]",
            position="inside",
            body_xml=inner,
        )
    box_xml = (
        f'<div name="button_box" class="oe_button_box">\n{inner}\n</div>'
    )
    if "<sheet" not in parent and parent:
        # Unusual form without sheet — still avoid primary rewrite by targeting form.
        return render_inherit_xpath_arch(
            expr="//form",
            position="inside",
            body_xml=box_xml,
        )
    # Empty or missing parent_arch: assume standard sheet layout (custom x_ forms).
    if not parent.strip() or "<sheet" in parent:
        # Prefer before first sheet child so the box sits at the top.
        if re.search(r"<sheet[^>]*>\s*<", parent):
            return render_inherit_xpath_arch(
                expr="//sheet/*[1]",
                position="before",
                body_xml=box_xml,
            )
        return render_inherit_xpath_arch(
            expr="//sheet",
            position="inside",
            body_xml=box_xml,
        )
    return render_inherit_xpath_arch(
        expr="//form",
        position="inside",
        body_xml=box_xml,
    )


def validate_xpath_arch(arch: str) -> list[str]:
    """Return human-readable issues for an inherit xpath arch (best-effort)."""
    from xml.etree.ElementTree import ParseError, fromstring

    issues: list[str] = []
    try:
        root = fromstring(arch)
    except ParseError as exc:
        return [f"Invalid XML: {exc}"]
    if root.tag not in {"data", "xpath"}:
        issues.append(f"Root should be <data> or <xpath>, got <{root.tag}>")
    xpaths = root.findall(".//xpath") if root.tag == "data" else (
        [root] if root.tag == "xpath" else []
    )
    if not xpaths:
        issues.append("No <xpath> elements found")
    for xp in xpaths:
        if not (xp.get("expr") or "").strip():
            issues.append("xpath missing expr attribute")
        pos = xp.get("position") or "inside"
        if pos not in {"inside", "after", "before", "replace", "attributes", "move"}:
            issues.append(f"Unusual xpath position={pos!r}")
        if pos != "move" and not list(xp) and not (xp.text or "").strip():
            issues.append("xpath body is empty")
    return issues
