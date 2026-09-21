"""Build PreviewViewSchema slices from draft ModuleSpec for Studio / Wizard previews."""

from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from odoo_client.view_arch import (
    FieldNode,
    GroupNode,
    NotebookNode,
    ViewNode,
    parse_form_arch,
    parse_kanban_arch,
    parse_list_arch,
)

PreviewField = TypedDict(
    "PreviewField",
    {
        "id": str,
        "name": str,
        "string": str,
        "ttype": str,
        "widget": str | None,
        "required": bool,
        "selection": list[dict[str, str]] | None,
    },
    total=False,
)

PreviewGroup = TypedDict(
    "PreviewGroup",
    {
        "id": str,
        "string": str,
        "columns": Literal[1, 2],
        "fields": list[PreviewField],
    },
)

PreviewNotebookPage = TypedDict(
    "PreviewNotebookPage",
    {
        "id": str,
        "string": str,
        "fields": list[PreviewField],
    },
)

PreviewNotebook = TypedDict(
    "PreviewNotebook",
    {
        "id": str,
        "pages": list[PreviewNotebookPage],
    },
)

PreviewHeaderButton = TypedDict(
    "PreviewHeaderButton",
    {
        "id": str,
        "string": str,
        "variant": Literal["primary", "secondary"],
    },
)

PreviewStatusBar = TypedDict(
    "PreviewStatusBar",
    {
        "field": str,
        "stages": list[str],
        "activeStage": str | None,
    },
)

PreviewSmartButton = TypedDict(
    "PreviewSmartButton",
    {
        "id": str,
        "string": str,
        "count": int | str | None,
    },
)

PreviewFormView = TypedDict(
    "PreviewFormView",
    {
        "type": Literal["form"],
        "model": str,
        "title": str,
        "appLabel": str | None,
        "recordTitleField": str | None,
        "statusbar": PreviewStatusBar | None,
        "headerButtons": list[PreviewHeaderButton],
        "smartButtons": list[PreviewSmartButton],
        "groups": list[PreviewGroup],
        "notebooks": list[PreviewNotebook],
        "chatter": Literal["stub", "hidden"],
        "groupLayout": Literal["stack", "two-column"],
    },
    total=False,
)

PreviewListColumn = TypedDict(
    "PreviewListColumn",
    {
        "id": str,
        "name": str,
        "string": str,
    },
)

PreviewListDecorations = TypedDict(
    "PreviewListDecorations",
    {
        "danger": str | None,
        "info": str | None,
        "muted": str | None,
    },
    total=False,
)

PreviewListView = TypedDict(
    "PreviewListView",
    {
        "type": Literal["list"],
        "model": str,
        "title": str,
        "columns": list[PreviewListColumn],
        "decorations": PreviewListDecorations | None,
    },
)

PreviewKanbanView = TypedDict(
    "PreviewKanbanView",
    {
        "type": Literal["kanban"],
        "model": str,
        "title": str,
        "groupBy": str | None,
        "cardFields": list[PreviewField],
    },
)

PreviewViewBundle = TypedDict(
    "PreviewViewBundle",
    {
        "form": PreviewFormView | None,
        "list": PreviewListView | None,
        "kanban": PreviewKanbanView | None,
    },
)

_MAX_STAT_BUTTONS = 6
_LINE_SUFFIXES = ("_line", "_party")


def _is_line_model(model: str) -> bool:
    return any(model.endswith(sfx) for sfx in _LINE_SUFFIXES)


def _field_index_for_row(row: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index fields for a single model — never merge across models (name collisions)."""
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(row, dict):
        return out
    for field in row.get("fields") or []:
        if isinstance(field, dict) and field.get("name"):
            out[str(field["name"])] = field
    return out


def _field_index(models: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Deprecated global merge — prefer `_field_index_for_row`."""
    out: dict[str, dict[str, Any]] = {}
    for row in models.values():
        out.update(_field_index_for_row(row))
    return out


def _workflow_score(row: dict[str, Any]) -> int:
    """Prefer document workflows with more transitions / statusbar stages."""
    sf = row.get("state_field") if isinstance(row.get("state_field"), dict) else {}
    transitions = sf.get("transitions") or []
    visible = sf.get("statusbar_visible") or []
    return len(transitions) * 10 + len(visible)


_STUDIO_NAME_RE = re.compile(r"^x_studio_", re.I)
_FALSE_TRUE_STRINGS = frozenset({"false", "true", "checkbox", "boolean"})


def _rewrite_ingenium_name(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return raw
    return _STUDIO_NAME_RE.sub("x_", raw)


def _human_preview_string(name: str, raw_string: str) -> str:
    label = str(raw_string or "").strip()
    tech = _rewrite_ingenium_name(name)
    if not label or label == name or label.lower() in _FALSE_TRUE_STRINGS:
        leaf = re.sub(r"^x_", "", tech)
        leaf = leaf.replace("_", " ").strip()
        return leaf[:1].upper() + leaf[1:] if leaf else tech
    if label.lower().startswith("x_studio_"):
        leaf = _STUDIO_NAME_RE.sub("", label).replace("_", " ").strip()
        return leaf[:1].upper() + leaf[1:] if leaf else label
    return label


def _coerce_preview_ttype(name: str, spec: dict[str, Any]) -> str:
    ttype = str(spec.get("ttype") or spec.get("type") or "char").lower()
    widget = str(spec.get("widget") or "").lower()
    blob = f"{name} {spec.get('string') or ''}".lower()
    if ttype in {"boolean", "bool"} or widget in {"boolean", "boolean_toggle"}:
        return "boolean"
    if "checkbox" in blob or re.search(r"\bpreferred\b", blob):
        # Must-do checkbox briefs sometimes land as char — stamp boolean for preview.
        if ttype in {"char", "text", ""} and "note" not in blob:
            return "boolean"
    # Honest date vs datetime preview samples when IR is weak/wrong.
    if widget in {"date", "datetime"}:
        return widget
    if ttype in {"date", "datetime"}:
        return ttype
    try:
        from app.ai_field_ir import infer_date_or_datetime

        temporal = infer_date_or_datetime(str(spec.get("string") or "")) or infer_date_or_datetime(
            name
        )
        if temporal and ttype in {"char", "text", ""}:
            return temporal
    except Exception:  # noqa: BLE001
        pass
    return ttype or "char"


def _preview_field(name: str, field_map: dict[str, dict[str, Any]]) -> PreviewField:
    tech = _rewrite_ingenium_name(name)
    spec = field_map.get(name) or field_map.get(tech) or {}
    selection_raw = spec.get("selection")
    selection: list[dict[str, str]] | None = None
    if isinstance(selection_raw, list):
        selection = []
        for item in selection_raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                selection.append({"value": str(item[0]), "label": str(item[1])})
            elif isinstance(item, dict):
                selection.append(
                    {
                        "value": str(item.get("value") or ""),
                        "label": str(item.get("label") or item.get("value") or ""),
                    }
                )
    ttype = _coerce_preview_ttype(tech, spec)
    widget = str(spec.get("widget")) if spec.get("widget") else None
    if ttype == "boolean" and widget and widget.lower() not in {"boolean", "boolean_toggle"}:
        widget = None
    return {
        "id": tech,
        "name": tech,
        "string": _human_preview_string(tech, str(spec.get("string") or "")),
        "ttype": ttype,
        "widget": widget,
        "required": bool(spec.get("required")),
        "selection": selection,
    }


def _fields_from_nodes(
    nodes: list[ViewNode],
    field_map: dict[str, dict[str, Any]],
) -> list[PreviewField]:
    out: list[PreviewField] = []
    for node in nodes:
        if isinstance(node, FieldNode) and node.name:
            out.append(_preview_field(node.name, field_map))
    return out


def _flatten_untitled_wrap_groups(nodes: list[ViewNode]) -> list[ViewNode]:
    """Unwrap Odoo ``<group col="2">`` wrappers so Studio still sees Identity | Details."""
    out: list[ViewNode] = []
    for node in nodes:
        if (
            isinstance(node, GroupNode)
            and not str(node.string or "").strip()
            and node.children
            and any(isinstance(child, GroupNode) for child in node.children)
        ):
            out.extend(node.children)
        else:
            out.append(node)
    return out


def _groups_from_nodes(
    nodes: list[ViewNode],
    field_map: dict[str, dict[str, Any]],
    *,
    prefix: str,
) -> tuple[list[PreviewGroup], list[PreviewNotebook], Literal["stack", "two-column"]]:
    groups: list[PreviewGroup] = []
    notebooks: list[PreviewNotebook] = []
    flat = _flatten_untitled_wrap_groups(nodes)
    top_groups = [n for n in flat if isinstance(n, GroupNode)]
    layout: Literal["stack", "two-column"] = (
        "two-column" if len(top_groups) >= 2 else "stack"
    )
    for idx, node in enumerate(flat):
        if isinstance(node, GroupNode):
            gid = f"{prefix}-group-{idx}"
            groups.append(
                {
                    "id": gid,
                    "string": str(node.string or "Group"),
                    "columns": 2 if layout == "two-column" else 1,
                    "fields": _fields_from_nodes(node.children, field_map),
                }
            )
        elif isinstance(node, NotebookNode):
            pages: list[PreviewNotebookPage] = []
            for pidx, page in enumerate(node.pages):
                pages.append(
                    {
                        "id": f"{prefix}-nb-{idx}-page-{pidx}",
                        "string": str(page.string or f"Page {pidx + 1}"),
                        "fields": _fields_from_nodes(page.children, field_map),
                    }
                )
            notebooks.append({"id": f"{prefix}-notebook-{idx}", "pages": pages})
    return groups, notebooks, layout


def _statusbar_from_arch(
    *,
    statusbar_field: str | None,
    statusbar_visible: str | None,
    field_map: dict[str, dict[str, Any]],
) -> PreviewStatusBar | None:
    if not statusbar_field:
        return None
    stages: list[str] = []
    if statusbar_visible:
        stages = [s.strip() for s in statusbar_visible.split(",") if s.strip()]
    if not stages:
        spec = field_map.get(statusbar_field) or {}
        selection = spec.get("selection") or []
        if isinstance(selection, list):
            for item in selection:
                if isinstance(item, (list, tuple)) and item:
                    stages.append(str(item[0]))
                elif isinstance(item, dict) and item.get("value"):
                    stages.append(str(item["value"]))
    if not stages:
        return None
    active = stages[0] if stages else None
    spec = field_map.get(statusbar_field) or {}
    sel_keys = spec.get("selection_keys") or spec.get("states")
    if isinstance(sel_keys, list) and sel_keys:
        active = str(sel_keys[0])
    return {
        "field": statusbar_field,
        "stages": stages,
        "activeStage": active,
    }


def _header_buttons(spec_buttons: list[Any]) -> list[PreviewHeaderButton]:
    out: list[PreviewHeaderButton] = []
    for idx, btn in enumerate(spec_buttons):
        cls = str(getattr(btn, "class_name", None) or "")
        variant: Literal["primary", "secondary"] = (
            "primary" if "oe_highlight" in cls else "secondary"
        )
        out.append(
            {
                "id": f"hdr-{idx}-{getattr(btn, 'name', None) or idx}",
                "string": str(getattr(btn, "string", None) or "Button"),
                "variant": variant,
            }
        )
    return out


def _selection_chrome_labels(draft: dict[str, Any], model: str) -> set[str]:
    """Labels of selection/status values — must never render as button_box smart buttons."""
    labels: set[str] = set()
    for m in draft.get("models") or []:
        if not isinstance(m, dict) or str(m.get("model") or "") != model:
            continue
        for field in m.get("fields") or []:
            if not isinstance(field, dict):
                continue
            ftype = str(field.get("ttype") or field.get("type") or "").lower()
            if ftype != "selection":
                continue
            raw = field.get("selection")
            if isinstance(raw, str):
                for key, lab in re.findall(
                    r"\(\s*'([^']*)'\s*,\s*'([^']+)'\s*\)", raw
                ):
                    labels.add(lab.strip().lower())
                    if key.strip():
                        labels.add(key.strip().lower().replace("_", " "))
                # also bare labels if key-only form slipped through
                for lab in re.findall(r"\(\s*'[^']*'\s*,\s*'([^']+)'\s*\)", raw):
                    labels.add(lab.strip().lower())
            elif isinstance(raw, (list, tuple)):
                for item in raw:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        labels.add(str(item[0]).strip().lower().replace("_", " "))
                        labels.add(str(item[1]).strip().lower())
                    elif isinstance(item, dict):
                        labels.add(str(item.get("value") or item.get("key") or "").strip().lower().replace("_", " "))
                        labels.add(str(item.get("label") or item.get("name") or "").strip().lower())
    # Synonyms operators still call "Dirty" when IR says "Needs cleaning"
    if "needs cleaning" in labels or "dirty" in labels:
        labels.update({"dirty", "needs cleaning", "needs cleaning".replace(" ", "")})
    return {x for x in labels if x}


def _smart_buttons_for_model(
    draft: dict[str, Any],
    model: str,
    *,
    arch_buttons: list[Any],
) -> list[PreviewSmartButton]:
    counts: dict[str, int | str | None] = {}
    for btn in arch_buttons:
        label = str(getattr(btn, "string", None) or "")
        count_field = getattr(btn, "count_field", None)
        if label and count_field:
            counts[label] = 0

    chrome = _selection_chrome_labels(draft, model)
    out: list[PreviewSmartButton] = []
    seen: set[tuple[str, str]] = set()
    for idx, btn in enumerate(draft.get("smart_buttons") or []):
        if not isinstance(btn, dict):
            continue
        on_model = str(btn.get("on_model") or "")
        if on_model != model:
            continue
        related = str(btn.get("related_model") or "")
        label = str(btn.get("string") or btn.get("label") or related or "Open")
        # Selection/state chrome (Reserved/Seated/Dirty/Blocked) ≠ smart buttons.
        if label.strip().lower() in chrome:
            continue
        key = (related, label)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "id": f"stat-{idx}-{related or label}",
                "string": label,
                "count": counts.get(label),
            }
        )
        if len(out) >= _MAX_STAT_BUTTONS:
            break

    # Fall back to form arch button_box when draft IR has no smart_buttons for model.
    if not out:
        for idx, btn in enumerate(arch_buttons):
            label = str(getattr(btn, "string", None) or "Open")
            if label.strip().lower() in chrome:
                continue
            key = ("", label)
            if key in seen:
                continue
            seen.add(key)
            count_field = getattr(btn, "count_field", None)
            out.append(
                {
                    "id": f"stat-arch-{idx}",
                    "string": label,
                    "count": 0 if count_field else counts.get(label),
                }
            )
            if len(out) >= _MAX_STAT_BUTTONS:
                break
    return out


def _inherit_document_title(model: str, draft: dict[str, Any]) -> str:
    """Human document name for an inherit host — not the Apps tile."""
    prompt = " ".join(
        [
            str(draft.get("_user_prompt") or ""),
            str(draft.get("display_name") or ""),
        ]
    ).lower()
    if model == "account.move":
        if re.search(r"\b(vendor\s+bills?|supplier\s+bills?)\b", prompt):
            return "Vendor bill"
        return "Customer invoice"
    if model == "sale.order":
        return "Quotation"
    if model == "purchase.order":
        return "Purchase order"
    if model == "stock.picking":
        if re.search(r"\b(incoming|receipt|goods in)\b", prompt):
            return "Receipt"
        return "Delivery"
    if model == "res.partner":
        return "Contact"
    if model == "product.template" or model == "product.product":
        return "Product"
    if model == "hr.employee":
        return "Employee"
    leaf = model.split(".")[-1].replace("_", " ")
    return leaf[:1].upper() + leaf[1:] if leaf else model


def _inherit_host_rank(model: str, draft: dict[str, Any]) -> tuple[int, str]:
    prompt = str(draft.get("_user_prompt") or "").lower()
    preferred = 0
    if model == "account.move" and re.search(r"\b(bill|invoice)\b", prompt):
        preferred = 3
    elif model == "sale.order" and re.search(r"\b(quotation|sales?\s+order)\b", prompt):
        preferred = 3
    elif model == "stock.picking" and re.search(r"\b(delivery|picking)\b", prompt):
        preferred = 3
    elif model == "res.partner" and re.search(r"\b(contact|partner|customer)\b", prompt):
        preferred = 2
    return (-preferred, model)


def _is_inherit_host_row(mid: str, row: dict[str, Any]) -> bool:
    if _is_line_model(mid):
        return False
    mode = str(row.get("mode") or "new")
    if mode == "inherit":
        return True
    return not mid.startswith("x_")


def _pick_primary_model(draft: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    models = {
        str(m.get("model")): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }

    workflows: list[tuple[str, dict[str, Any]]] = []
    fallback: tuple[str, dict[str, Any]] | None = None
    inherit_hosts: list[tuple[str, dict[str, Any]]] = []
    for mid, row in models.items():
        if _is_line_model(mid):
            continue
        if _is_inherit_host_row(mid, row):
            inherit_hosts.append((mid, row))
            continue
        if not mid.startswith("x_"):
            continue
        if row.get("mode") == "inherit":
            inherit_hosts.append((mid, row))
            continue
        if row.get("is_workflow"):
            workflows.append((mid, row))
        elif fallback is None:
            fallback = (mid, row)

    if workflows:
        workflows.sort(key=lambda item: _workflow_score(item[1]), reverse=True)
        return workflows[0]

    # Prefer first custom form view when no workflow flag.
    for view in draft.get("views") or []:
        if not isinstance(view, dict):
            continue
        if str(view.get("type") or "") != "form":
            continue
        mid = str(view.get("model") or "")
        if not mid.startswith("x_") or _is_line_model(mid):
            continue
        return mid, models.get(mid) or {}

    if fallback:
        return fallback

    if inherit_hosts:
        inherit_hosts.sort(key=lambda item: _inherit_host_rank(item[0], draft))
        return inherit_hosts[0]

    return None


def _view_arch(draft: dict[str, Any], model: str, view_type: str) -> str | None:
    for view in draft.get("views") or []:
        if not isinstance(view, dict):
            continue
        if str(view.get("model") or "") != model:
            continue
        vtype = str(view.get("type") or "")
        if vtype == view_type:
            arch = view.get("arch")
            return str(arch) if arch else None
        if view_type == "list" and vtype == "tree":
            arch = view.get("arch")
            return str(arch) if arch else None
    return None


def _stock_placeholder_field(fid: str, label: str, ttype: str = "char") -> PreviewField:
    return {
        "id": fid,
        "name": fid,
        "string": label,
        "ttype": ttype,
        "widget": None,
        "required": False,
        "selection": None,
    }


def _partner_host_skeleton(
    extension_groups: list[PreviewGroup],
    extension_notebooks: list[PreviewNotebook],
) -> tuple[list[PreviewGroup], list[PreviewNotebook]]:
    """Stock Contact form chrome + highlighted extension groups (never island-only)."""
    identity: PreviewGroup = {
        "id": "host_identity",
        "string": "",
        "columns": 2,
        "fields": [
            _stock_placeholder_field("_host_name", "Name"),
            _stock_placeholder_field("_host_email", "Email"),
            _stock_placeholder_field("_host_phone", "Phone"),
            _stock_placeholder_field("_host_mobile", "Mobile"),
        ],
    }
    address: PreviewGroup = {
        "id": "host_address",
        "string": "Address",
        "columns": 1,
        "fields": [
            _stock_placeholder_field("_host_street", "Street"),
            _stock_placeholder_field("_host_city", "City"),
            _stock_placeholder_field("_host_country", "Country", "many2one"),
        ],
    }
    groups: list[PreviewGroup] = [identity, address]
    groups.extend(extension_groups)
    pages: list[PreviewNotebookPage] = [
        {"id": "host_contacts", "string": "Contacts", "fields": []},
        {"id": "host_sales", "string": "Sales & Purchase", "fields": []},
        {"id": "host_notes", "string": "Internal Notes", "fields": []},
    ]
    # Merge extension notebook pages after stock chrome (keep Delivery as group, not page).
    for nb in extension_notebooks:
        for page in nb.get("pages") or []:
            if page.get("fields"):
                pages.append(page)
    notebooks: list[PreviewNotebook] = [{"id": "host_notebook", "pages": pages}]
    return groups, notebooks


def _inherit_slot_preview(
    draft: dict[str, Any],
    row: dict[str, Any],
    field_map: dict[str, dict[str, Any]],
) -> tuple[list[PreviewGroup], list[PreviewNotebook]] | None:
    """Preview inherit fields by named slot — never an EXTENSION island."""
    stamp = draft.get("_form_slots")
    if not isinstance(stamp, dict):
        return None
    mapping = stamp.get("fields") if isinstance(stamp.get("fields"), dict) else {}
    catalog = stamp.get("catalog") if isinstance(stamp.get("catalog"), list) else []
    labels = {
        str(item.get("id") or ""): str(item.get("label") or item.get("id") or "")
        for item in catalog
        if isinstance(item, dict) and item.get("id")
    }
    tab = str(stamp.get("tab_title") or "Details")
    group_title = stamp.get("group_title")
    group_title = str(group_title).strip() if group_title else ""
    buckets: dict[str, list[PreviewField]] = {
        "next_to_partner": [],
        "next_to_dates": [],
        "other_info": [],
        "new_tab": [],
    }
    for field in row.get("fields") or []:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "")
        if not name or field.get("ttype") == "one2many":
            continue
        # Keep field_map in sync when names were rewritten x_studio_* → x_*.
        rewritten = _rewrite_ingenium_name(name)
        if rewritten != name and name in field_map and rewritten not in field_map:
            field_map[rewritten] = field_map[name]
        slot = str(mapping.get(name) or mapping.get(rewritten) or "")
        if slot not in buckets:
            slot = "next_to_dates"
        buckets[slot].append(_preview_field(name, field_map))
    groups: list[PreviewGroup] = []
    for sid in ("next_to_partner", "next_to_dates"):
        if not buckets[sid]:
            continue
        groups.append(
            {
                "id": f"slot_{sid}",
                "string": labels.get(sid) or sid.replace("_", " ").title(),
                "columns": 1,
                "fields": buckets[sid],
            }
        )
    # Named sheet group (Delivery): group title — never a selection / fake field.
    if buckets["new_tab"] and group_title:
        groups.append(
            {
                "id": "slot_named_group",
                "string": group_title,
                "columns": 1,
                "fields": buckets["new_tab"],
            }
        )
        buckets["new_tab"] = []
    pages: list[PreviewNotebookPage] = []
    if buckets["other_info"]:
        pages.append(
            {
                "id": "slot_other_info",
                "string": "Other Info",
                "fields": buckets["other_info"],
            }
        )
    if buckets["new_tab"]:
        pages.append({"id": "slot_new_tab", "string": tab, "fields": buckets["new_tab"]})
    notebooks: list[PreviewNotebook] = (
        [{"id": "slot_notebook", "pages": pages}] if pages else []
    )
    if not groups and not notebooks:
        return None
    return groups, notebooks


def _has_mail_thread(model_row: dict[str, Any]) -> bool:
    mixins = model_row.get("inherit") or model_row.get("mixins") or []
    if isinstance(mixins, list):
        for item in mixins:
            if "mail.thread" in str(item):
                return True
    return bool(model_row.get("enable_mail_thread"))


def build_form_preview(
    draft: dict[str, Any],
    *,
    model: str | None = None,
    model_row: dict[str, Any] | None = None,
) -> PreviewFormView | None:
    picked = _pick_primary_model(draft) if model is None else (model, model_row or {})
    if not picked:
        return None
    mid, row = picked
    models = {
        str(m.get("model")): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    # Prefer the concrete model row from the draft index when only a name was passed.
    if not row and mid in models:
        row = models[mid]
    field_map = _field_index_for_row(row if row else models.get(mid))
    arch = _view_arch(draft, mid, "form")
    is_inherit = _is_inherit_host_row(mid, row) or str(row.get("mode") or "") == "inherit"
    title = (
        _inherit_document_title(mid, draft)
        if is_inherit
        else str(row.get("description") or row.get("name") or mid)
    )
    is_line = _is_line_model(mid)

    groups: list[PreviewGroup] = []
    notebooks: list[PreviewNotebook] = []
    group_layout: Literal["stack", "two-column"] = "stack"
    statusbar: PreviewStatusBar | None = None
    header_buttons: list[PreviewHeaderButton] = []
    smart_buttons: list[PreviewSmartButton] = []
    record_title: str | None = "x_name"

    slotted = _inherit_slot_preview(draft, row, field_map) if is_inherit else None
    if slotted:
        groups, notebooks = slotted
    elif arch:
        try:
            spec = parse_form_arch(arch)
            groups, notebooks, group_layout = _groups_from_nodes(
                spec.children, field_map, prefix=mid.replace(".", "_")
            )
            if not is_line:
                statusbar = _statusbar_from_arch(
                    statusbar_field=spec.statusbar_field,
                    statusbar_visible=spec.statusbar_visible,
                    field_map=field_map,
                )
                header_buttons = _header_buttons(spec.header_buttons)
            smart_buttons = _smart_buttons_for_model(
                draft, mid, arch_buttons=spec.button_box
            )
            if spec.string and not is_inherit:
                title = str(spec.string)
        except Exception:  # noqa: BLE001
            pass

    # Empty / Name-only Identity from a shell form arch must not hide model fields
    # (IR/preview desync: Must-do has Company/Visit/Purpose/Host while canvas shows Name*).
    if groups and not notebooks and not is_inherit:
        total = sum(len(g.get("fields") or []) for g in groups if isinstance(g, dict))
        model_field_count = sum(
            1 for f in (row.get("fields") or []) if isinstance(f, dict) and f.get("name")
        )
        if total == 0 or (model_field_count > total and total <= 1):
            groups = []

    if not groups and not notebooks:
        fields = [
            _preview_field(str(f.get("name") or ""), field_map)
            for f in (row.get("fields") or [])
            if isinstance(f, dict) and f.get("name")
        ][:16]
        group_label = "Added on this form" if is_inherit else "Identity"
        points = draft.get("connect_points") if isinstance(draft.get("connect_points"), dict) else {}
        raw_label = (
            str(points.get("sub_menu_name") or "")
            if is_inherit and isinstance(points, dict)
            else ""
        )
        if raw_label and raw_label.strip().lower() not in {
            "extension",
            "extensions",
            "invoice extras",
        }:
            group_label = raw_label
        groups = [
            {
                "id": "identity",
                "string": group_label,
                "columns": 1,
                "fields": fields,
            }
        ]
        if not is_line and any(f["name"] == "x_status" for f in fields):
            statusbar = _statusbar_from_arch(
                statusbar_field="x_status",
                statusbar_visible=None,
                field_map=field_map,
            )

    # Inherit host skeleton: show stock Contact chrome around new fields (S1).
    if is_inherit and mid == "res.partner" and (groups or notebooks):
        # Avoid double-wrapping if we somehow already have host_identity.
        if not any(g.get("id") == "host_identity" for g in groups):
            groups, notebooks = _partner_host_skeleton(groups, notebooks)
            group_layout = "two-column"

    chatter: Literal["stub", "hidden"] = "hidden"
    if not is_line and not is_inherit and (
        _has_mail_thread(row)
        or any(str(d).strip() == "mail" for d in (draft.get("depends") or []))
    ):
        chatter = "stub"
    # Contact forms always show chatter stub in the structural preview.
    if is_inherit and mid == "res.partner":
        chatter = "stub"

    # App tile label for breadcrumb (Contacts / Contact) — not technical model.
    from app.ai_grain import HOST_LABELS

    app_label = HOST_LABELS.get(mid) if is_inherit else None

    return {
        "type": "form",
        "model": mid,
        "title": title,
        "appLabel": app_label,
        "recordTitleField": record_title,
        "statusbar": statusbar if not is_line else None,
        "headerButtons": header_buttons if not is_line else [],
        "smartButtons": smart_buttons,
        "groups": groups,
        "notebooks": notebooks,
        "chatter": chatter,
        "groupLayout": group_layout,
    }


def build_list_preview(draft: dict[str, Any], *, model: str | None = None) -> PreviewListView | None:
    picked = _pick_primary_model(draft) if model is None else (model, {})
    if not picked:
        return None
    mid, _row = picked
    arch = _view_arch(draft, mid, "list")
    models = {
        str(m.get("model")): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    row = models.get(mid) or {}
    if not arch:
        fields = [
            str(f.get("name") or "")
            for f in (row.get("fields") or [])
            if isinstance(f, dict) and f.get("name")
        ][:6]
        if not fields:
            return None
        field_map = _field_index_for_row(row)
        columns: list[PreviewListColumn] = []
        for name in fields:
            pf = _preview_field(name, field_map)
            columns.append({"id": pf["id"], "name": pf["name"], "string": pf["string"]})
        return {
            "type": "list",
            "model": mid,
            "title": _inherit_document_title(mid, draft) if _is_inherit_host_row(mid, row) else str(mid),
            "columns": columns,
            "decorations": {"danger": None, "info": None, "muted": None},
        }
    try:
        spec = parse_list_arch(arch)
    except Exception:  # noqa: BLE001
        return None
    field_map = _field_index_for_row(models.get(mid))
    columns: list[PreviewListColumn] = []
    for col in spec.columns:
        pf = _preview_field(col.name, field_map)
        columns.append({"id": pf["id"], "name": pf["name"], "string": pf["string"]})
    return {
        "type": "list",
        "model": mid,
        "title": str(spec.string or mid),
        "columns": columns,
        "decorations": {
            "danger": spec.decoration_danger,
            "info": spec.decoration_info,
            "muted": spec.decoration_muted,
        },
    }


def build_kanban_preview(
    draft: dict[str, Any], *, model: str | None = None
) -> PreviewKanbanView | None:
    picked = _pick_primary_model(draft) if model is None else (model, {})
    if not picked:
        return None
    mid, _row = picked
    arch = _view_arch(draft, mid, "kanban")
    if not arch:
        return None
    try:
        spec = parse_kanban_arch(arch)
    except Exception:  # noqa: BLE001
        return None
    models = {
        str(m.get("model")): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    field_map = _field_index_for_row(models.get(mid))
    card_fields = [_preview_field(name, field_map) for name in spec.records_fields if name]
    return {
        "type": "kanban",
        "model": mid,
        "title": str(spec.string or mid),
        "groupBy": spec.default_group_by,
        "cardFields": card_fields,
    }


def build_preview_views(draft: dict[str, Any]) -> PreviewViewBundle:
    form = build_form_preview(draft)
    mid = form.get("model") if form else None
    return {
        "form": form,
        "list": build_list_preview(draft, model=mid) if mid else None,
        "kanban": build_kanban_preview(draft, model=mid) if mid else None,
    }


def residual_form_preview(draft: dict[str, Any]) -> dict[str, Any] | None:
    """Backward-compatible form preview dict for generation engine IR."""
    form = build_form_preview(draft)
    return dict(form) if form else None
