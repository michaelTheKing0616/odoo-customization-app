"""Post-process ModuleSpec drafts: menus, actions, default views, statusbar hints."""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from typing import Any
from xml.sax.saxutils import escape

from module_generator import list_view_for_major
from odoo_client.image_pipeline import guess_image_role, image_field_xml, is_image_field

from app.ai_model_quality import is_embedded_line_model, is_party_link_model
from app.ai_workflow import build_transition_header_buttons


def _is_register_surface(draft: dict[str, Any], model: dict[str, Any]) -> bool:
    from app.ai_document_shape import document_shape_of
    from app.ai_odoo_app_bar import looks_like_register

    mid = str(model.get("model") or "")
    if looks_like_register(mid):
        return True
    return document_shape_of(draft) == "register"

_FORM_GROUP_FIELD_THRESHOLD = 10
_CONTACT_HINTS = frozenset(
    {"phone", "email", "manager", "website", "fax", "contact", "mobile", "tel"}
)
_LOCATION_HINTS = frozenset(
    {
        "address",
        "city",
        "zip",
        "postal",
        "country",
        "latitude",
        "longitude",
        "state",
        "location",
        "street",
    }
)


def _slug(text: str, *, fallback: str = "custom") -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", (text or "").lower()).strip("_")
    return slug[:40] or fallback


def _field_list(model: dict[str, Any]) -> list[dict[str, Any]]:
    fields = model.get("fields") or []
    return [f for f in fields if isinstance(f, dict) and f.get("name")]


def _ensure_x_name(model: dict[str, Any]) -> None:
    """Identity label for new x_* models only — never clone name onto stock inherits."""
    mid = str(model.get("model") or "")
    mode = str(model.get("mode") or "new")
    if mode == "inherit" and not mid.startswith("x_"):
        return
    fields = _field_list(model)
    names = {f.get("name") for f in fields}
    if "x_name" not in names:
        model.setdefault("fields", [])
        if isinstance(model["fields"], list):
            model["fields"].insert(
                0,
                {
                    "name": "x_name",
                    "ttype": "char",
                    "string": "Name",
                    "required": True,
                },
            )


def _field_names_set(fields: list[dict[str, Any]]) -> set[str]:
    return {str(f.get("name")) for f in fields if f.get("name")}


def _arch_field_node(
    name: str,
    fields: list[dict[str, Any]],
    *,
    view_type: str,
    model_name: str,
) -> str:
    if not name or not str(name).strip():
        return ""
    fdef = next((f for f in fields if f.get("name") == name), None)
    if is_image_field(fdef):
        role_raw = fdef.get("image_role") if fdef else None
        role = role_raw if role_raw in {"avatar", "content"} else guess_image_role(model_name, name)
        return image_field_xml(
            name,
            view_type=view_type,  # type: ignore[arg-type]
            field_names=_field_names_set(fields),
            role=role,
            string=str((fdef or {}).get("string") or "") or None,
        )
    attrs = ""
    if isinstance(fdef, dict):
        opts = fdef.get("options")
        if isinstance(opts, dict) and opts:
            # Odoo form options use Python-literal style: {'no_create': True}
            lit = (
                "{"
                + ", ".join(
                    f"'{k}': {'True' if v is True else 'False' if v is False else repr(v)}"
                    for k, v in opts.items()
                )
                + "}"
            )
            attrs += f' options="{escape(lit)}"'
    return f'<field name="{escape(name)}"{attrs}/>'


def _list_columns(fields: list[dict[str, Any]], *, limit: int = 8) -> list[str]:
    skip = {"one2many", "many2many", "html", "text"}
    cols: list[str] = []
    for f in fields:
        ttype = str(f.get("ttype") or "char").lower()
        name = f.get("name")
        if not name:
            continue
        if ttype == "binary" and not is_image_field(f):
            continue
        if ttype in skip:
            continue
        cols.append(str(name))
        if len(cols) >= limit:
            break
    if "x_name" in {f.get("name") for f in fields} and "x_name" not in cols:
        cols.insert(0, "x_name")
    return cols or ["x_name"]


_PREFERRED_EMBEDDED_COLS = (
    "x_name",
    "x_date",
    "x_partner_id",
    "x_employee_id",
    "x_role",
    "x_hours",
    "x_qty",
    "x_rate",
    "x_price_unit",
    "x_unit_price",
    "x_amount",
    "x_total",
    "x_status",
    "x_doc_type",
    "x_code",
    "x_notes",
)
_LINE_VALUE_COLS = frozenset(
    {
        "x_hours",
        "x_qty",
        "x_rate",
        "x_amount",
        "x_price_unit",
        "x_unit_price",
        "x_total",
    }
)
# sale.order.line: name → qty/price/amount, then extras (reference/notes).
_TRAILING_EMBEDDED_COLS = frozenset({"x_code", "x_notes", "x_reference"})
# Related stock *documents* belong on button_box, not header Identity (sale.order shape).
# People/org FKs (partner, employee, company, currency) stay on the form.
_RELATED_STOCK_DOCUMENT_MODELS = frozenset(
    {
        "crm.lead",
        "sale.order",
        "account.move",
        "account.payment",
        "purchase.order",
        "calendar.event",
        "project.task",
        "project.project",
        "stock.picking",
        "hr.expense",
        "account.analytic.line",
    }
)


def _embedded_o2m_columns(
    field: dict[str, Any],
    models_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Columns for a nested one2many list — not x_name-only (sale.order.line shape)."""
    child = (models_by_id or {}).get(str(field.get("relation") or ""))
    if not child:
        return ["x_name"]
    parent_m2os = {
        str(f.get("name"))
        for f in _field_list(child)
        if f.get("ttype") == "many2one" and str(f.get("relation") or "").startswith("x_")
    }
    names = {str(f.get("name")) for f in _field_list(child)}
    identity: list[str] = []
    values: list[str] = []
    trailing: list[str] = []
    for preferred in _PREFERRED_EMBEDDED_COLS:
        if preferred not in names or preferred in parent_m2os:
            continue
        if preferred in _LINE_VALUE_COLS:
            values.append(preferred)
        elif preferred in _TRAILING_EMBEDDED_COLS:
            trailing.append(preferred)
        else:
            identity.append(preferred)
    cap = 8
    reserved = len(values) + len(trailing)
    ident_budget = max(1 if "x_name" in names else 0, cap - reserved)
    ident = identity[:ident_budget]
    if "x_name" in names and "x_name" not in ident:
        ident = ["x_name"] + [c for c in ident if c != "x_name"]
        ident = ident[:ident_budget]
    return (ident + values + trailing)[:cap] or ["x_name"]


def _m2o_role_bases(fields: list[dict[str, Any]]) -> set[str]:
    roles: set[str] = set()
    for f in fields:
        name = str(f.get("name") or "")
        if f.get("ttype") == "many2one" and name.startswith("x_") and name.endswith("_id"):
            roles.add(name[2:-3])
    return roles


def drop_redundant_role_name_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop x_<role>_name char fields when a matching x_<role>_id many2one exists."""
    roles = _m2o_role_bases(fields)
    if not roles:
        return fields
    kept: list[dict[str, Any]] = []
    for f in fields:
        name = str(f.get("name") or "")
        if (
            f.get("ttype") == "char"
            and name.startswith("x_")
            and name.endswith("_name")
            and name != "x_name"
            and name[2:-5] in roles
        ):
            continue
        kept.append(f)
    return kept


def _scalar_group_label(name: str) -> str:
    lower = name.lower()
    if any(h in lower for h in _CONTACT_HINTS):
        return "Contact"
    if any(h in lower for h in _LOCATION_HINTS):
        return "Location"
    return "Details"


def _partition_scalar_fields(names: list[str]) -> list[tuple[str, list[str]]]:
    """Split scalar form fields into semantic groups when the flat list is large."""
    filtered = [n for n in names if n != "x_status"]
    if len(filtered) <= _FORM_GROUP_FIELD_THRESHOLD:
        return [("Details", filtered)] if filtered else []
    buckets: dict[str, list[str]] = {"Contact": [], "Location": [], "Details": []}
    for name in filtered:
        buckets[_scalar_group_label(name)].append(name)
    groups: list[tuple[str, list[str]]] = []
    for title in ("Contact", "Location", "Details"):
        if buckets[title]:
            groups.append((title, buckets[title]))
    return groups


def _is_related_stock_document_m2o(field: dict[str, Any]) -> bool:
    return (
        str(field.get("ttype") or "") == "many2one"
        and str(field.get("relation") or "") in _RELATED_STOCK_DOCUMENT_MODELS
    )


def _form_field_names(fields: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str]]:
    identity: list[str] = []
    details: list[str] = []
    lines: list[str] = []
    for f in fields:
        name = str(f.get("name"))
        ttype = str(f.get("ttype") or "char").lower()
        if ttype in {"one2many", "many2many"}:
            lines.append(name)
        elif name == "x_name" or ttype == "many2one":
            if _is_related_stock_document_m2o(f):
                continue
            identity.append(name)
        elif ttype == "binary" and not is_image_field(f):
            continue
        elif ttype == "binary":
            details.append(name)
        else:
            details.append(name)
    if "x_name" in {f.get("name") for f in fields} and "x_name" not in identity:
        identity.insert(0, "x_name")
    return identity, details, lines


def _selection_keys(selection: Any) -> list[str]:
    if not isinstance(selection, str):
        return []
    return re.findall(r"\('([^']+)'\s*,", selection)


def _build_list_arch(
    model_name: str, fields: list[dict[str, Any]], *, odoo_major: int = 19, sample: bool = True
) -> str:
    cols = _list_columns(fields)
    inner = "".join(
        _arch_field_node(c, fields, view_type="list", model_name=model_name) for c in cols
    )
    status = next((f for f in fields if f.get("name") == "x_status"), None)
    attrs = ' sample="1"' if sample else ""
    if status:
        keys = _selection_keys(status.get("selection"))
        danger = next((k for k in keys if k in {"overdue", "lost", "retired", "cancelled"}), None)
        muted = next((k for k in keys if k in {"draft", "returned"}), None)
        if danger:
            attrs += f' decoration-danger="x_status == \'{danger}\'"'
        if muted:
            attrs += f' decoration-muted="x_status == \'{muted}\'"'
    _type, root = list_view_for_major(odoo_major)
    return f'<{root} string="{escape(model_name)}"{attrs}>{inner}</{root}>'


def _wrap_scalar_groups_two_col(groups: list[str]) -> list[str]:
    """Pair titled groups so Odoo sits them side-by-side (sale.order sheet shape).

    Sibling ``<group string=...>`` as direct sheet children stack full-width,
    especially with chatter-right. Wrapping each pair in ``<group col="2">``
    matches App Studio's Identity | Details grid in live Odoo.
    """
    titled = [g for g in groups if g]
    out: list[str] = []
    idx = 0
    while idx < len(titled):
        if idx + 1 < len(titled):
            out.append(f'<group col="2">{titled[idx]}{titled[idx + 1]}</group>')
            idx += 2
        else:
            out.append(titled[idx])
            idx += 1
    return out


def _sheet_needs_two_col_wrap(arch: str) -> bool:
    """True when Identity/Details (or any 2+ titled groups) sit directly on the sheet."""
    try:
        root = ET.fromstring(arch or "")
    except ET.ParseError:
        return False
    sheet = root.find("sheet")
    if sheet is None:
        return False
    titled = [c for c in list(sheet) if c.tag == "group" and c.get("string")]
    return len(titled) >= 2


def _form_arch_flow_kwargs(
    draft: dict[str, Any] | None, model: dict[str, Any]
) -> dict[str, Any]:
    sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
    flow = (
        draft.get("_approval_flow")
        if isinstance(draft, dict) and isinstance(draft.get("_approval_flow"), dict)
        else {}
    )
    manager_dests: set[str] | None = None
    if flow.get("manager_dests"):
        manager_dests = {str(x) for x in (flow.get("manager_dests") or [])}
    elif sf.get("approval"):
        manager_dests = {"approved", "refused", "rejected"}
    name = str(sf.get("field") or "").strip()
    return {
        "state_field_name": name or None,
        "manager_dests": manager_dests,
    }


def _build_form_arch(
    description: str,
    fields: list[dict[str, Any]],
    *,
    smart_buttons: list[dict[str, Any]] | None = None,
    transitions: list[list[str]] | None = None,
    statusbar_visible: list[str] | None = None,
    odoo_major: int = 19,
    models_by_id: dict[str, dict[str, Any]] | None = None,
    model_id: str | None = None,
    state_field_name: str | None = None,
    manager_dests: set[str] | frozenset[str] | None = None,
) -> str:
    identity, details, lines = _form_field_names(fields)
    state_name = str(state_field_name or "").strip() or "x_status"
    status = next((f for f in fields if f.get("name") == state_name), None)
    if status is None:
        status = next((f for f in fields if f.get("name") == "x_status"), None)
        if status is not None:
            state_name = "x_status"
    line_form = is_embedded_line_model(model_id or "")
    header = ""
    if status and line_form:
        # sale.order.line: billing flag is a sheet column, not a document statusbar.
        if state_name not in identity:
            identity.append(state_name)
        details = [n for n in details if n != state_name]
    elif status:
        keys = _selection_keys(status.get("selection"))
        if statusbar_visible:
            visible = [str(k) for k in statusbar_visible if k]
        elif transitions:
            visible = []
            seen: set[str] = set()
            for tr in transitions:
                if isinstance(tr, (list, tuple)) and len(tr) >= 2:
                    for k in (str(tr[0]), str(tr[1])):
                        if k not in seen:
                            visible.append(k)
                            seen.add(k)
        else:
            visible = keys[:6] if keys else []
        vis_attr = f' statusbar_visible="{escape(",".join(visible))}"' if visible else ""
        btn_xml = build_transition_header_buttons(
            transitions or [], field=state_name, manager_dests=manager_dests
        )
        # Header buttons are the execution path; a clickable statusbar races them.
        lock_attr = (
            " options=\"{'clickable': False}\" readonly=\"1\"" if btn_xml else ""
        )
        header = (
            f"<header>"
            f'<field name="{escape(state_name)}" widget="statusbar"{vis_attr}{lock_attr}/>'
            f"{btn_xml}"
            f"</header>"
        )

    def group_xml(title: str, names: list[str]) -> str:
        if not names:
            return ""
        inner = "".join(
            _arch_field_node(n, fields, view_type="form", model_name=description)
            for n in names
        )
        return f'<group string="{escape(title)}">{inner}</group>'

    _type, list_root = list_view_for_major(odoo_major)

    scalar_xml = [group_xml("Identity", identity)]
    for title, names in _partition_scalar_fields(details):
        scalar_xml.append(group_xml(title, names))
    sheet_bits = _wrap_scalar_groups_two_col(scalar_xml)
    pages: list[str] = []
    for line in lines:
        fdef = next((f for f in fields if f.get("name") == line), None) or {}
        title = str(fdef.get("string") or line)
        cols = _embedded_o2m_columns(fdef, models_by_id)
        inner = "".join(f'<field name="{escape(c)}"/>' for c in cols)
        pages.append(
            f'<page string="{escape(title)}">'
            f'<field name="{escape(line)}">'
            f'<{list_root} editable="bottom">{inner}</{list_root}>'
            f"</field>"
            f"</page>"
        )
    if pages:
        sheet_bits.append(f"<notebook>{''.join(pages)}</notebook>")

    # Smart buttons are applied live with real action ids; draft keeps metadata only.
    _ = smart_buttons
    sheet = f"<sheet>{''.join(sheet_bits)}</sheet>"
    return f'<form string="{escape(description)}">{header}{sheet}</form>'


def _xml_parent_map(root: ET.Element) -> dict[ET.Element, ET.Element | None]:
    mapping: dict[ET.Element, ET.Element | None] = {root: None}
    for parent in root.iter():
        for child in list(parent):
            mapping[child] = parent
    return mapping


def _xml_inside_embedded_list(
    el: ET.Element, parents: dict[ET.Element, ET.Element | None]
) -> bool:
    parent = parents.get(el)
    while parent is not None:
        if parent.tag in {"list", "tree"}:
            return True
        parent = parents.get(parent)
    return False


def _xml_o2m_field_els(
    root: ET.Element,
    o2m_names: set[str],
    parents: dict[ET.Element, ET.Element | None],
) -> list[ET.Element]:
    found: list[ET.Element] = []
    for field_el in root.iter("field"):
        name = str(field_el.get("name") or "")
        if name in o2m_names and not _xml_inside_embedded_list(field_el, parents):
            found.append(field_el)
    return found


def _xml_nearest_title(
    el: ET.Element,
    parents: dict[ET.Element, ET.Element | None],
    fallback: str,
) -> str:
    parent = parents.get(el)
    while parent is not None:
        if parent.tag in {"page", "group"} and parent.get("string"):
            return str(parent.get("string"))
        parent = parents.get(parent)
    return fallback


def _xml_list_column_names(field_el: ET.Element) -> list[str]:
    cols: list[str] = []
    for child in list(field_el):
        if child.tag not in {"list", "tree"}:
            continue
        for sub in list(child):
            if sub.tag == "field" and sub.get("name"):
                cols.append(str(sub.get("name")))
    return cols


def _xml_set_embedded_list(
    field_el: ET.Element, cols: list[str], list_root: str
) -> None:
    existing = next((c for c in list(field_el) if c.tag in {"list", "tree"}), None)
    attrs = dict(existing.attrib) if existing is not None else {}
    if "editable" not in attrs:
        attrs["editable"] = "bottom"
    for child in list(field_el):
        if child.tag in {"list", "tree"}:
            field_el.remove(child)
    lst = ET.SubElement(field_el, list_root, attrs)
    for col in cols:
        ET.SubElement(lst, "field", {"name": col})


def _xml_prune_empty_wrappers(root: ET.Element) -> None:
    changed = True
    while changed:
        changed = False
        parents = _xml_parent_map(root)
        sheet = root.find("sheet")
        for el in list(root.iter()):
            if el.tag not in {"group", "page", "notebook"}:
                continue
            if el is sheet:
                continue
            if el.find(".//field") is not None:
                continue
            parent = parents.get(el)
            if parent is None:
                continue
            parent.remove(el)
            changed = True


def _xml_strip_related_stock_document_fields(
    root: ET.Element, model: dict[str, Any]
) -> bool:
    """Related stock documents stay on the model; header Identity is people/org FKs only."""
    drop = {
        str(f.get("name") or "")
        for f in _field_list(model)
        if _is_related_stock_document_m2o(f) and f.get("name")
    }
    if not drop:
        return False
    mutated = False
    parents = _xml_parent_map(root)
    for field_el in list(root.iter("field")):
        name = str(field_el.get("name") or "")
        if name not in drop or _xml_inside_embedded_list(field_el, parents):
            continue
        parent = parents.get(field_el)
        if parent is None:
            continue
        parent.remove(field_el)
        mutated = True
        parents = _xml_parent_map(root)
    if mutated:
        _xml_prune_empty_wrappers(root)
    return mutated


def _xml_official_single_notebook(
    sheet: ET.Element,
    o2m_names: set[str],
    parents: dict[ET.Element, ET.Element | None],
) -> bool:
    notebooks = [child for child in list(sheet) if child.tag == "notebook"]
    if len(notebooks) != 1:
        return False
    inside = {
        str(el.get("name") or "")
        for el in _xml_o2m_field_els(notebooks[0], o2m_names, parents)
    }
    outside = [
        el
        for el in _xml_o2m_field_els(sheet, o2m_names, parents)
        if str(el.get("name") or "") not in inside
    ]
    return not outside


def collapse_header_o2ms_into_notebook(draft: dict[str, Any]) -> list[str]:
    """sale.order shape: scalars in groups, one notebook page per custom child O2M.

    Unwraps ``<group><notebook><page>`` (production_shape used to wrap each O2M
    independently) and enriches nested lists that only show ``x_name``.
    """
    notes: list[str] = []
    by_id = {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    try:
        odoo_major = int(draft.get("odoo_major") or 19)
    except (TypeError, ValueError):
        odoo_major = 19
    _type, list_root = list_view_for_major(odoo_major)
    views = draft.get("views")
    if not isinstance(views, list):
        return notes
    for view in views:
        if not isinstance(view, dict) or str(view.get("type") or "") != "form":
            continue
        mid = str(view.get("model") or "")
        model = by_id.get(mid)
        if not model or not mid.startswith("x_") or str(model.get("mode") or "new") == "inherit":
            continue
        o2m_meta = {
            str(f.get("name") or ""): f
            for f in _field_list(model)
            if str(f.get("ttype") or "") in {"one2many", "many2many"}
            and str(f.get("name") or "")
            and str(f.get("relation") or "").startswith("x_")
        }
        arch = str(view.get("arch") or "").strip()
        if not arch:
            continue
        try:
            root = ET.fromstring(arch)
        except ET.ParseError:
            notes.append(f"enrich: skip notebook collapse on {mid} (unparseable form)")
            continue
        sheet = root.find("sheet")
        if sheet is None:
            continue
        mutated = False
        if o2m_meta:
            parents = _xml_parent_map(root)
            field_els = _xml_o2m_field_els(sheet, set(o2m_meta), parents)
            official = _xml_official_single_notebook(sheet, set(o2m_meta), parents)
            if field_els and not official:
                moved: list[tuple[str, ET.Element]] = []
                for field_el in field_els:
                    fname = str(field_el.get("name") or "")
                    title = _xml_nearest_title(
                        field_el,
                        parents,
                        str((o2m_meta.get(fname) or {}).get("string") or fname),
                    )
                    moved.append((title, field_el))
                for _title, field_el in moved:
                    parent = parents.get(field_el)
                    if parent is not None:
                        parent.remove(field_el)
                _xml_prune_empty_wrappers(root)
                notebook = ET.SubElement(sheet, "notebook")
                for title, field_el in moved:
                    page = ET.SubElement(notebook, "page", {"string": title})
                    page.append(field_el)
                mutated = True
            parents = _xml_parent_map(root)
            for field_el in _xml_o2m_field_els(sheet, set(o2m_meta), parents):
                fname = str(field_el.get("name") or "")
                child_id = str((o2m_meta.get(fname) or {}).get("relation") or "")
                if child_id not in by_id:
                    continue
                cols = _embedded_o2m_columns(o2m_meta.get(fname) or {}, by_id)
                existing = _xml_list_column_names(field_el)
                if cols == existing:
                    continue
                _xml_set_embedded_list(field_el, cols, list_root)
                mutated = True
        if _xml_strip_related_stock_document_fields(root, model):
            mutated = True
        if mutated:
            view["arch"] = ET.tostring(root, encoding="unicode")
            notes.append(f"enrich: one notebook of custom children on {mid}")
    return notes


def _build_kanban_arch(
    fields: list[dict[str, Any]], *, sample: bool = True, model_name: str = ""
) -> str | None:
    names = {f.get("name") for f in fields}
    if "x_status" not in names and "x_name" not in names:
        return None
    sample_attr = ' sample="1"' if sample else ""
    card_bits = [
        _arch_field_node("x_name", fields, view_type="kanban", model_name=model_name)
        if "x_name" in names
        else "",
    ]
    if "x_status" in names:
        card_bits.append(
            _arch_field_node("x_status", fields, view_type="kanban", model_name=model_name)
        )
    for f in fields:
        if is_image_field(f) and f.get("name") not in {"x_name", "x_status"}:
            card_bits.append(
                _arch_field_node(
                    str(f.get("name")),
                    fields,
                    view_type="kanban",
                    model_name=model_name,
                )
            )
            break
    return (
        f'<kanban default_group_by="x_status" class="o_kanban_small_column"{sample_attr}>'
        "<templates><t t-name=\"card\">"
        f"{''.join(card_bits)}"
        "</t></templates></kanban>"
        if "x_status" in names
        else None
    )


def _ensure_actions_for_models(
    draft: dict[str, Any],
    new_models: list[dict[str, Any]],
    default_view_mode: str,
    default_view_mode_kanban: str,
) -> list[str]:
    notes: list[str] = []
    actions = list(draft.get("actions") or []) if isinstance(draft.get("actions"), list) else []
    have = {a.get("model") for a in actions if isinstance(a, dict)}
    added = 0
    for m in new_models:
        mid = str(m["model"])
        if mid in have:
            continue
        label = str(m.get("description") or mid)
        has_status = any(f.get("name") == "x_status" for f in _field_list(m))
        use_kanban = (
            has_status
            and not is_party_link_model(m)
            and not is_embedded_line_model(m)
            and not _is_register_surface(draft, m)
        )
        actions.append(
            {
                "name": label,
                "model": mid,
                "view_mode": (
                    default_view_mode_kanban if use_kanban else default_view_mode
                ),
                "technical_name": f"action_{_slug(mid)}",
            }
        )
        have.add(mid)
        added += 1
    if added:
        draft["actions"] = actions
        notes.append(f"added {added} action(s) for seeded/extra models")
    return notes


def _ensure_menus_for_models(
    draft: dict[str, Any],
    new_models: list[dict[str, Any]],
    display: str,
    tech: str,
) -> list[str]:
    notes: list[str] = []
    menus = list(draft.get("menus") or []) if isinstance(draft.get("menus"), list) else []
    root_xml = f"menu_root_{_slug(tech)}"
    if not any(isinstance(m, dict) and m.get("xml_id") == root_xml for m in menus):
        root = next(
            (
                m
                for m in menus
                if isinstance(m, dict)
                and not m.get("parent_xml_id")
                and not m.get("action_xml_id")
            ),
            None,
        )
        if root and root.get("xml_id"):
            root_xml = str(root["xml_id"])
        else:
            menus.insert(
                0,
                {
                    "name": display,
                    "sequence": 10,
                    "technical_name": f"root_{_slug(tech)}",
                    "xml_id": root_xml,
                },
            )
    covered_actions = {
        str(m.get("action_xml_id") or "")
        for m in menus
        if isinstance(m, dict) and m.get("action_xml_id")
    }
    actions_by_model = {
        a.get("model"): a
        for a in (draft.get("actions") or [])
        if isinstance(a, dict)
    }
    added = 0
    seq = 10 + len(menus)
    for m in new_models:
        mid = str(m["model"])
        if mid.endswith("_line"):
            continue
        act = actions_by_model.get(mid)
        act_xml = (act or {}).get("technical_name") or f"action_{_slug(mid)}"
        if act_xml in covered_actions:
            continue
        label = str(m.get("description") or mid)
        menus.append(
            {
                "name": label,
                "action_xml_id": act_xml,
                "parent_xml_id": root_xml,
                "sequence": seq,
                "technical_name": f"menu_{_slug(mid)}",
            }
        )
        covered_actions.add(str(act_xml))
        seq += 1
        added += 1
    if added:
        draft["menus"] = menus
        notes.append(f"added {added} menu(s) for seeded/extra models")
    return notes


def _view_arch_field_names(arch: str) -> set[str]:
    return set(re.findall(r'name="(x_[A-Za-z0-9_]+)"', arch or ""))


def _stored_form_field_names(model: dict[str, Any]) -> set[str]:
    """Scalar + binary image fields that belong on a form arch (not O2M/M2M lines)."""
    names: set[str] = set()
    for f in _field_list(model):
        name = str(f.get("name") or "")
        ttype = str(f.get("ttype") or "").lower()
        if ttype in {"one2many", "many2many"}:
            continue
        if ttype == "binary" and not is_image_field(f):
            continue
        if ttype == "many2one" and _is_related_stock_document_m2o(f):
            continue
        if name:
            names.add(name)
    return names


def _expected_statusbar_visible(model: dict[str, Any]) -> str | None:
    sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
    visible = sf.get("statusbar_visible")
    if isinstance(visible, list) and visible:
        return ",".join(str(k) for k in visible if k)
    return None


def _arch_statusbar_visible(arch: str) -> str | None:
    m = re.search(r'statusbar_visible="([^"]*)"', arch or "")
    return m.group(1) if m else None


def sync_form_archs_to_models(draft: dict[str, Any]) -> list[str]:
    """Rebuild form views when model fields or statusbar_visible drift from the arch."""
    notes: list[str] = []
    by_id = {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    try:
        odoo_major = int(draft.get("odoo_major") or 19)
    except (TypeError, ValueError):
        odoo_major = 19
    smart_by_model: dict[str, list[dict[str, Any]]] = {}
    for btn in draft.get("smart_buttons") or []:
        if isinstance(btn, dict) and btn.get("on_model"):
            smart_by_model.setdefault(str(btn["on_model"]), []).append(btn)
    views = draft.get("views")
    if not isinstance(views, list):
        return notes
    rebuilt = 0
    for v in views:
        if not isinstance(v, dict) or v.get("type") != "form":
            continue
        # Inherit xpath arches are authored by form slots — do not rebuild as a
        # standalone form (that would wipe partner/dates/Other Info placement).
        if str(v.get("mode") or "") == "extension" or v.get("inherit_xml_id"):
            continue
        mid = str(v.get("model") or "")
        model = by_id.get(mid)
        if not model:
            continue
        fields = _field_list(model)
        stored = _stored_form_field_names(model)
        arch = str(v.get("arch") or "")
        arch_names = _view_arch_field_names(arch)
        missing = stored - arch_names
        expected_sb = _expected_statusbar_visible(model)
        actual_sb = _arch_statusbar_visible(arch)
        statusbar_stale = bool(
            expected_sb is not None
            and "statusbar" in arch
            and actual_sb != expected_sb
        )
        rel_names = {
            str(f.get("name"))
            for f in fields
            if str(f.get("ttype") or "") in {"one2many", "many2many", "binary"}
            and (str(f.get("ttype")) != "binary" or is_image_field(f))
        }
        missing_rel = rel_names - arch_names
        line_chrome_stale = bool(
            is_embedded_line_model(mid)
            and (
                'widget="statusbar"' in arch
                or "<chatter" in arch.lower()
                or "oe_chatter" in arch
                or re.search(r"<header>", arch, re.I)
            )
        )
        layout_stale = _sheet_needs_two_col_wrap(arch)
        sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
        tr = sf.get("transitions") if isinstance(sf.get("transitions"), list) else None
        header_stale = bool(tr) and "data-transition-to" not in arch
        if (
            not missing
            and not statusbar_stale
            and not missing_rel
            and not line_chrome_stale
            and not layout_stale
            and not header_stale
        ):
            continue
        sb_vis = (
            sf.get("statusbar_visible")
            if isinstance(sf.get("statusbar_visible"), list)
            else None
        )
        v["arch"] = _build_form_arch(
            str(model.get("description") or mid),
            fields,
            smart_buttons=smart_by_model.get(mid),
            transitions=tr,
            statusbar_visible=sb_vis,
            odoo_major=odoo_major,
            models_by_id=by_id,
            model_id=mid,
            **_form_arch_flow_kwargs(draft, model),
        )
        rebuilt += 1
    if rebuilt:
        notes.append(
            f"enrich: synced {rebuilt} form arch(es) to model fields/statusbar"
        )
    return notes


def _rebuild_stale_views(
    draft: dict[str, Any],
    new_models: list[dict[str, Any]],
    *,
    odoo_major: int,
) -> list[str]:
    """Rebuild primary views that reference fields no longer on the model."""
    notes: list[str] = []
    by_id = {str(m["model"]): m for m in new_models}
    views = list(draft.get("views") or []) if isinstance(draft.get("views"), list) else []
    smart_by_model: dict[str, list[dict[str, Any]]] = {}
    for btn in draft.get("smart_buttons") or []:
        if isinstance(btn, dict) and btn.get("on_model"):
            smart_by_model.setdefault(str(btn["on_model"]), []).append(btn)
    list_type, _ = list_view_for_major(odoo_major)
    rebuilt = 0
    new_views: list[dict[str, Any]] = []
    for v in views:
        if not isinstance(v, dict):
            continue
        mid = str(v.get("model") or "")
        model = by_id.get(mid)
        if not model:
            new_views.append(v)
            continue
        field_names = {str(f.get("name")) for f in _field_list(model)}
        arch_fields = _view_arch_field_names(str(v.get("arch") or ""))
        stale = arch_fields - field_names
        if not stale:
            new_views.append(v)
            continue
        vtype = str(v.get("type") or "form")
        desc = str(model.get("description") or mid)
        fields = _field_list(model)
        if vtype in {"list", "tree"}:
            arch = _build_list_arch(desc, fields, odoo_major=odoo_major)
            vtype = list_type
        elif vtype == "kanban":
            arch = _build_kanban_arch(fields, model_name=mid) or str(v.get("arch") or "")
        else:
            sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
            tr = sf.get("transitions") if isinstance(sf.get("transitions"), list) else None
            sb_vis = (
                sf.get("statusbar_visible") if isinstance(sf.get("statusbar_visible"), list) else None
            )
            arch = _build_form_arch(
                desc,
                fields,
                smart_buttons=smart_by_model.get(mid),
                transitions=tr,
                statusbar_visible=sb_vis,
                odoo_major=odoo_major,
                models_by_id=by_id,
                model_id=mid,
                **_form_arch_flow_kwargs(draft, model),
            )
        new_views.append({**v, "type": vtype, "arch": arch})
        rebuilt += 1
    if rebuilt:
        draft["views"] = new_views
        notes.append(f"rebuilt {rebuilt} stale view arch(es) (field rename sync)")
    return notes


def ensure_default_ui(draft: dict[str, Any]) -> list[str]:
    """Add actions/menus/views when missing. Mutates draft. Returns warnings."""
    warnings: list[str] = []
    models = [m for m in (draft.get("models") or []) if isinstance(m, dict) and m.get("model")]
    if not models:
        return warnings

    for model in models:
        _ensure_x_name(model)
        fields = model.get("fields")
        if isinstance(fields, list):
            pruned = drop_redundant_role_name_fields(
                [f for f in fields if isinstance(f, dict)]
            )
            if len(pruned) != len(fields):
                model["fields"] = pruned
        mode = model.get("mode") or "new"
        if mode not in {"new", "inherit"}:
            model["mode"] = "new"

    tech = str(draft.get("technical_name") or "custom_app")
    display = str(draft.get("display_name") or tech.replace("_", " ").title())

    new_models = [m for m in models if (m.get("mode") or "new") == "new"]

    # Draft may carry connection major; default 19-primary when unset.
    try:
        odoo_major = int(draft.get("odoo_major") or 19)
    except (TypeError, ValueError):
        odoo_major = 19
    list_type, _list_root = list_view_for_major(odoo_major)
    default_view_mode = f"{list_type},form"
    default_view_mode_kanban = f"{list_type},kanban,form"

    if not draft.get("actions") and new_models:
        actions = []
        for m in new_models:
            mid = str(m["model"])
            label = str(m.get("description") or mid)
            has_status = any(f.get("name") == "x_status" for f in _field_list(m))
            use_kanban = (
                has_status
                and not is_party_link_model(m)
                and not is_embedded_line_model(m)
                and not _is_register_surface(draft, m)
            )
            actions.append(
                {
                    "name": label,
                    "model": mid,
                    "view_mode": (
                        default_view_mode_kanban if use_kanban else default_view_mode
                    ),
                    "technical_name": f"action_{_slug(mid)}",
                }
            )
        draft["actions"] = actions
        warnings.append(f"added {len(actions)} default action(s)")
    else:
        # Fill gaps when seed/critique added models after the first enrich pass
        warnings.extend(_ensure_actions_for_models(draft, new_models, default_view_mode, default_view_mode_kanban))

    if not draft.get("menus") and new_models:
        root_xml = f"menu_root_{_slug(tech)}"
        menus = [
            {
                "name": display,
                "sequence": 10,
                "technical_name": f"root_{_slug(tech)}",
                "xml_id": root_xml,
            }
        ]
        actions_by_model = {
            a.get("model"): a
            for a in (draft.get("actions") or [])
            if isinstance(a, dict)
        }
        for i, m in enumerate(new_models):
            mid = str(m["model"])
            if mid.endswith("_line"):
                continue
            label = str(m.get("description") or mid)
            act = actions_by_model.get(mid)
            menus.append(
                {
                    "name": label,
                    "action_xml_id": (act or {}).get("technical_name")
                    or f"action_{_slug(mid)}",
                    "parent_xml_id": root_xml,
                    "sequence": 10 + i,
                    "technical_name": f"menu_{_slug(mid)}",
                }
            )
        draft["menus"] = menus
        warnings.append(f"added root + {len(new_models)} menu(s)")
    else:
        warnings.extend(_ensure_menus_for_models(draft, new_models, display, tech))

    existing_view_keys = {
        (v.get("model"), v.get("type"))
        for v in (draft.get("views") or [])
        if isinstance(v, dict)
    }
    # Treat list/tree as the same slot for idempotency across majors.
    for v in draft.get("views") or []:
        if isinstance(v, dict) and v.get("type") in {"list", "tree"}:
            existing_view_keys.add((v.get("model"), "list"))
            existing_view_keys.add((v.get("model"), "tree"))

    views = list(draft.get("views") or []) if isinstance(draft.get("views"), list) else []
    smart_by_model: dict[str, list[dict[str, Any]]] = {}
    for btn in draft.get("smart_buttons") or []:
        if isinstance(btn, dict) and btn.get("on_model"):
            smart_by_model.setdefault(str(btn["on_model"]), []).append(btn)
    by_id = {str(m["model"]): m for m in models}

    added_views = 0
    for m in new_models:
        mid = str(m["model"])
        desc = str(m.get("description") or mid)
        fields = _field_list(m)
        sf = m.get("state_field") if isinstance(m.get("state_field"), dict) else {}
        tr = sf.get("transitions") if isinstance(sf.get("transitions"), list) else None
        sb_vis = sf.get("statusbar_visible") if isinstance(sf.get("statusbar_visible"), list) else None
        for vtype, arch in (
            (list_type, _build_list_arch(desc, fields, odoo_major=odoo_major)),
            (
                "form",
                _build_form_arch(
                    desc,
                    fields,
                    smart_buttons=smart_by_model.get(mid),
                    transitions=tr,
                    statusbar_visible=sb_vis,
                    odoo_major=odoo_major,
                    models_by_id=by_id,
                    model_id=mid,
                    **_form_arch_flow_kwargs(draft, m),
                ),
            ),
        ):
            if (mid, vtype) in existing_view_keys:
                continue
            if vtype in {"list", "tree"} and (
                (mid, "list") in existing_view_keys or (mid, "tree") in existing_view_keys
            ):
                continue
            views.append(
                {
                    "name": f"{mid}.{vtype}",
                    "model": mid,
                    "type": vtype,
                    "arch": arch,
                    "mode": "primary",
                }
            )
            added_views += 1
        kanban = _build_kanban_arch(fields, model_name=mid)
        if (
            kanban
            and not is_party_link_model(m)
            and not is_embedded_line_model(m)
            and not _is_register_surface(draft, m)
            and (mid, "kanban") not in existing_view_keys
        ):
            views.append(
                {
                    "name": f"{mid}.kanban",
                    "model": mid,
                    "type": "kanban",
                    "arch": kanban,
                    "mode": "primary",
                }
            )
            added_views += 1

    if added_views:
        draft["views"] = views
        warnings.append(f"added {added_views} default view arch(es)")

    warnings.extend(_rebuild_stale_views(draft, new_models, odoo_major=odoo_major))
    warnings.extend(sync_form_archs_to_models(draft))
    return warnings


def attach_reuse_context(
    draft: dict[str, Any],
    *,
    reuse_models: list[str] | None = None,
    reuse_views: list[dict[str, Any]] | None = None,
    reuse_actions: list[dict[str, Any]] | None = None,
) -> None:
    reuse = dict(draft.get("reuse") or {}) if isinstance(draft.get("reuse"), dict) else {}
    if reuse_models:
        reuse["models"] = list(dict.fromkeys([*(reuse.get("models") or []), *reuse_models]))
    if reuse_views:
        reuse["views"] = reuse_views
    if reuse_actions:
        reuse["actions"] = reuse_actions
    if reuse:
        draft["reuse"] = reuse


def enrich_draft_module_spec(
    draft: dict[str, Any],
    *,
    reuse_models: list[str] | None = None,
    reuse_views: list[dict[str, Any]] | None = None,
    reuse_actions: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    out = copy.deepcopy(draft)
    warnings = ensure_default_ui(out)
    attach_reuse_context(
        out,
        reuse_models=reuse_models,
        reuse_views=reuse_views,
        reuse_actions=reuse_actions,
    )
    # Summary for UI
    out["_meta"] = {
        "model_count": len(out.get("models") or []),
        "view_count": len(out.get("views") or []),
        "menu_count": len(out.get("menus") or []),
        "smart_button_count": len(out.get("smart_buttons") or []),
        "automation_count": len(out.get("automations") or []),
        "domain_pack": out.get("domain_pack"),
    }
    return out, warnings
