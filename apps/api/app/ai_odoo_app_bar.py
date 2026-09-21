"""Odoo Apps Store bar — deterministic senior-Community module shape.

Runs after pack merge / LLM so every domain (not just curated verticals) ships
with short menus, search-ready UI, chatter, document lines, stock-app links,
and at least one real automation. Public ORM/RPC shapes only.
"""

from __future__ import annotations

import ast
import re
from html import escape
from typing import Any

_CATALOG_STATUS = frozenset(
    {"active", "inactive", "retired", "standby", "archived", "maintenance"}
)
_REGISTER_TOKENS = (
    "asset",
    "equipment",
    "facility",
    "studio",
    "artist",
    "staff",
    "crew",
    "client",
    "link",
    "product",
    "reason",
    "category",
    "type",
    "tag",
    "uom",
    "currency",
    "rate_card",
    "rate_unit",
    "unavailability",
    "blackout",
    "downtime",
    "outage",
    "role",
    "specialty",
)
_REGISTER_LEAF_TOKENS = frozenset(
    {
        "rate",
        "roster",
        "catalog",
        "log",
        "ledger",
        "checklist",
        "guestbook",
        "book",
        # Resource registers (status = statusbar chrome, never workflow/smart buttons)
        "table",
        "room",
        "bed",
        "desk",
        "seat",
        "stall",
        "bay",
    }
)
_NEEDS_SITE_TOKENS = (
    "booking",
    "session",
    "appointment",
    "reservation",
    "unavailability",
    "rate",
    "equipment",
    "engagement",
    "project",
)
_STOCK_CLONE_MODELS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    ("x_currency", "res.currency", (), ""),
    ("x_payment", "account.move", ("account.move", "account.payment", "account"), "payment"),
    ("x_crew", "hr.employee", ("hr.employee", "hr"), "crew"),
    ("x_staffing", "hr.employee", ("hr.employee", "hr"), "staffing"),
)
_HEADER_TOKENS = (
    "work_order",
    "order",
    "transfer",
    "request",
    "ticket",
    "job",
    "intervention",
    "booking",
    "reservation",
    "appointment",
    "session",
    "quote",
    "case",
    "matter",
)
_BOOKING_TOKENS = ("session", "booking", "appointment", "reservation")
_JOB_HEADER_LEAVES = frozenset(
    {"engagement", "project", "matter", "case", "stay", "job"}
)
_JOB_HEADER_PREFERENCE = (
    "stay",
    "engagement",
    "matter",
    "case",
    "project",
    "job",
)
_ASSET_LINE_PARENT_TOKENS = (
    "equipment",
    "asset",
    "instrument",
    "vehicle",
    "gear",
    "tool",
)
_JOB_CHILD_SKIP = (
    "line",
    "rate",
    "card",
    "session",
    "booking",
    "appointment",
    "reservation",
)
_CRM_PARTY_FIELDS = frozenset(
    {
        "x_last_interaction_date",
        "last_interaction_date",
        "x_last_interaction",
        "last_interaction",
    }
)
_UOM_REGISTER_SUFFIXES = ("_unit", "_uom")
_UOM_SELECTION_NAMES = frozenset({"x_rate_unit", "x_uom", "x_unit", "x_rate_uom"})
_UOM_KEY_HINTS = frozenset(
    {"hour", "hourly", "session", "day", "stem", "week", "month", "minute"}
)
_DROP_SELECTION_ALIAS = frozenset({"x_rate_type", "x_billing_type", "x_type"})
_KEEP_SELECTION_NAMES = frozenset({"x_status", "state", "x_priority", "x_stage"})
_COPIED_USAGE_FIELD_NAMES = frozenset(
    {
        "x_usage_date",
        "x_hours_used",
        "x_rate_per_hour",
        "usage_date",
        "hours_used",
    }
)
_TERMINAL_STATUS_KEYS = frozenset({"done", "completed", "cancelled", "canceled"})
_RATE_CARD_TOKENS = ("rate", "fee", "tariff", "pricelist")
_PARTY_RATE_FIELDS = frozenset(
    {"x_rate", "x_rate_unit", "x_hourly_rate", "x_list_price"}
)
_GENERIC_LOOP_LEAVES = frozenset(
    {
        "deposit",
        "party_link",
        "document",
        "bill",
        "invoice",
        "task",
        "event",
        "milestone",
        "compliance",
        "fee",
        "staff",
        "staffing",
    }
)
GENERIC_LOOP_LEAVES = _GENERIC_LOOP_LEAVES
_GENERIC_LOOP_PRIORITY = (
    "party_link",
    "deposit",
    "document",
    "fee",
    "bill",
    "invoice",
    "task",
    "event",
    "milestone",
    "compliance",
    "staffing",
    "staff",
)
_FOREIGN_FK_LEAVES = frozenset({"matter", "hearing", "retainer"})
_FOREIGN_ROLE_LEAVES = frozenset(
    {"attorney", "solicitor", "barrister", "paralegal"}
)
_ASSET_MODEL_TOKENS = ("equipment", "asset", "gear")


def _is_asset_catalog(mid: str) -> bool:
    """Catalog only — `{asset}_line` and `{asset}_usage` are operational children."""
    if not mid or mid.endswith("_line") or mid.endswith("_usage"):
        return False
    return any(tok in mid for tok in _ASSET_MODEL_TOKENS)


_DEFAULT_ASSET_TYPE_LEAVES = frozenset(
    {
        "console",
        "microphone",
        "monitor",
        "outboard",
        "instrument",
        "miscellaneous",
        "camera",
        "lens",
        "lighting",
        "rigging",
    }
)
_GENERIC_SITE_STRINGS = frozenset({"site", "site name", "location"})
_CORRUPT_LABEL_RE = re.compile(r"\}\s*,\s*\{")
_CREW_ROLE_LEAVES = frozenset(
    {"staff", "crew", "employee", "attorney", "lawyer", "counsel", "fee_earner"}
)
_COST_HEADER_SKIP = ("rate", "card", "center", "category", "type")
_STOCK_FK_LEAVES = frozenset(
    {
        "partner",
        "user",
        "company",
        "currency",
        "country",
        "state",
        "uom",
        "product",
        "employee",
        "parent",
        "account",
        "category",
        "tax",
        "pricelist",
    }
)
_KEEP_MODELS_FLOOR = 3
_GENERIC_SITE_LEAVES = frozenset({"site", "location", "place"})
_GENERIC_PARTY_LEAVES = frozenset({"party"})
_SKIP_LINE_TOKENS = (
    "permit",
    "incident",
    "facility",
    "asset",
    "shift",
    "reason",
    "promotion",
    "campaign",
    "agreement",
    "partner",
    "employee",
)
_SITE_TOKENS = (
    "studio",
    "facility",
    "branch",
    "site",
    "location",
    "store",
    "warehouse",
    "room",
    "booth",
    "clinic",
    "ward",
)
_INCIDENT_TOKENS = ("incident", "near_miss", "hse")
_IRREGULAR_PLURALS = {
    "facility": "Facilities",
    "category": "Categories",
    "country": "Countries",
    "company": "Companies",
    "currency": "Currencies",
    "staff": "Staff",
    "equipment": "Equipment",
}
# Community button_box labels (not technical model titles).
_STOCK_COMMERCIAL_LABELS: dict[str, tuple[str, str]] = {
    "sale.order": ("Quotation", "Quotations"),
    "account.move": ("Invoice", "Invoices"),
    "calendar.event": ("Meeting", "Meetings"),
    "project.task": ("Task", "Tasks"),
    "project.project": ("Project", "Projects"),
    "crm.lead": ("Lead", "Leads"),
    "purchase.order": ("Purchase Order", "Purchase Orders"),
    "account.analytic.line": ("Timesheet", "Timesheets"),
    "account.payment": ("Payment", "Payments"),
    "hr.expense": ("Expense", "Expenses"),
    "stock.picking": ("Transfer", "Transfers"),
}


def _models_index(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def _field_names(model: dict[str, Any]) -> set[str]:
    return {
        str(f.get("name"))
        for f in (model.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }


def _leaf_tokens(model_id: str) -> list[str]:
    parts = str(model_id).replace("x_", "").replace(".", "_").split("_")
    if parts and len(parts[0]) <= 3 and len(parts) > 1:
        parts = parts[1:]
    return [p for p in parts if p]


def _title_tokens(tokens: list[str]) -> str:
    special = {"hse": "HSE", "wo": "WO", "ptw": "PTW", "mro": "MRO", "api": "API"}
    return " ".join(special.get(t, t.replace("_", " ").title()) for t in tokens)


def _pluralize_label(singular: str) -> str:
    raw = singular.strip()
    if not raw:
        return raw
    low = raw.lower()
    if low in _IRREGULAR_PLURALS:
        stem = _IRREGULAR_PLURALS[low]
        if raw[0].isupper():
            return stem
        return stem.lower()
    if raw.endswith(("s", "x", "z", "ch", "sh")):
        return raw + "es"
    if raw.endswith("y") and len(raw) > 1 and raw[-2] not in "aeiou":
        return raw[:-1] + "ies"
    return raw + "s"


def short_model_label(model_id: str, description: str = "", *, plural: bool = False) -> str:
    """Odoo Apps-style name from the model id: Facilities, Work Orders."""
    del description  # menus/actions must not inherit pack description essays
    commercial = _STOCK_COMMERCIAL_LABELS.get(str(model_id))
    if commercial:
        return commercial[1] if plural else commercial[0]
    tokens = _leaf_tokens(model_id)
    if not tokens:
        base = str(model_id).replace("x_", " ").replace("_", " ").title()
    else:
        base = _title_tokens(tokens)
    if plural:
        parts = base.split()
        if parts:
            parts[-1] = _pluralize_label(parts[-1])
            return " ".join(parts)
    return base


def senior_sequence_prefix(model_id: str) -> str:
    tokens = _leaf_tokens(model_id)
    key = "_".join(tokens)
    special = {
        "work_order": "WO",
        "permit": "PTW",
        "hse_incident": "INC",
        "incident": "INC",
        "store_order": "SO",
        "branch_transfer": "TR",
        "inventory_adjustment": "ADJ",
        "inventory_count": "CNT",
        "loan": "LOAN",
    }
    if key in special:
        return f"{special[key]}/"
    if len(tokens) >= 2:
        return f"{tokens[-2][0]}{tokens[-1][0]}".upper() + "/"
    token = (tokens[-1] if tokens else "ref").upper()
    return f"{token}/"


def looks_like_register(model_id: str) -> bool:
    """Rosters/catalogs (studio, artist, equipment, crew, rate card, calendar blocks) are not documents."""
    mid = model_id.lower()
    if "work_order" in mid or mid.endswith("_line"):
        return False
    if any(tok in mid for tok in _REGISTER_TOKENS):
        return True
    tokens = _leaf_tokens(mid if mid.startswith("x_") else f"x_{mid}")
    return bool(tokens) and tokens[-1] in _REGISTER_LEAF_TOKENS


def _looks_like_register(model_id: str) -> bool:
    return looks_like_register(model_id)


def _looks_like_header(model: dict[str, Any]) -> bool:
    mid = str(model.get("model") or "")
    if not mid.startswith("x_") or mid.endswith("_line"):
        return False
    skip = any(tok in mid for tok in _SKIP_LINE_TOKENS)
    if skip and not any(tok in mid for tok in ("work_order", "order", "transfer", "ticket", "job")):
        return False
    if any(tok in mid for tok in _BOOKING_TOKENS):
        return True
    if model.get("is_workflow") and any(tok in mid for tok in _HEADER_TOKENS):
        return True
    return False


def _has_line_child(draft: dict[str, Any], parent_id: str) -> bool:
    line_id = f"{parent_id}_line"
    by_id = _models_index(draft)
    if line_id in by_id:
        return True
    parent = by_id.get(parent_id) or {}
    for field in parent.get("fields") or []:
        if not isinstance(field, dict):
            continue
        if field.get("ttype") == "one2many" and str(field.get("relation") or "").endswith("_line"):
            return True
    return False



def scrub_selection_chrome_smart_buttons(draft: dict[str, Any]) -> list[str]:
    """Drop smart_buttons whose label is a selection/status value on the same model.

    Reserved / Seated / Dirty / Blocked are statusbar chrome — never button_box.
    """
    notes: list[str] = []
    buttons = draft.get("smart_buttons")
    if not isinstance(buttons, list) or not buttons:
        return notes
    # Local chrome extractor (mirrors preview_views; keep IR source-of-truth scrubbed).
    import re as _re

    def _chrome(model: str) -> set[str]:
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
                    for key, lab in _re.findall(
                        r"\(\s*'([^']*)'\s*,\s*'([^']+)'\s*\)", raw
                    ):
                        labels.add(lab.strip().lower())
                        if key.strip():
                            labels.add(key.strip().lower().replace("_", " "))
                elif isinstance(raw, (list, tuple)):
                    for item in raw:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            labels.add(str(item[0]).strip().lower().replace("_", " "))
                            labels.add(str(item[1]).strip().lower())
        if "needs cleaning" in labels or "dirty" in labels:
            labels.update({"dirty", "needs cleaning"})
        return {x for x in labels if x}

    kept: list[Any] = []
    for btn in buttons:
        if not isinstance(btn, dict):
            continue
        on_model = str(btn.get("on_model") or btn.get("model") or "")
        label = str(btn.get("label") or btn.get("string") or "").strip()
        chrome = _chrome(on_model) if on_model else set()
        if label and label.lower() in chrome:
            notes.append(
                f"app_bar: scrubbed selection-chrome smart_button {label!r} on {on_model}"
            )
            continue
        kept.append(btn)
    draft["smart_buttons"] = kept
    return notes


def demote_register_status_workflows(draft: dict[str, Any]) -> list[str]:
    """Paper books and catalogs are not document workflows (no Confirm/Done header)."""
    notes: list[str] = []
    from app.ai_document_shape import document_shape_of

    shape = document_shape_of(draft)
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or not model.get("is_workflow"):
            continue
        mid = str(model.get("model") or "")
        if shape != "register" and not _looks_like_register(mid):
            continue
        model["is_workflow"] = False
        model.pop("state_field", None)
        notes.append(f"app_bar: demoted register workflow on {mid}")
    return notes


def humanize_app_surface(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    by_id = _models_index(draft)
    labels: dict[str, str] = {}
    plurals: dict[str, str] = {}
    for mid, model in by_id.items():
        singular = short_model_label(mid, str(model.get("description") or ""), plural=False)
        plural = short_model_label(mid, str(model.get("description") or ""), plural=True)
        labels[mid] = singular
        plurals[mid] = plural
        desc = str(model.get("description") or "")
        if desc != singular and (
            "/" in desc
            or len(desc) > 28
            or desc.startswith("X ")
            or desc.lower().startswith("x ")
        ):
            model["description"] = singular
            notes.append(f"app_bar: humanized description on {mid}")

    for action in draft.get("actions") or []:
        if not isinstance(action, dict):
            continue
        mid = str(action.get("model") or "")
        if mid in plurals:
            action["name"] = plurals[mid]

    for menu in draft.get("menus") or []:
        if not isinstance(menu, dict) or not menu.get("action_xml_id"):
            continue
        ref = str(menu.get("action_xml_id") or "")
        for action in draft.get("actions") or []:
            if not isinstance(action, dict):
                continue
            if str(action.get("technical_name") or "") == ref:
                mid = str(action.get("model") or "")
                if mid in plurals:
                    if menu.get("name") != plurals[mid]:
                        menu["name"] = plurals[mid]
                        notes.append(f"app_bar: humanized menu {menu.get('technical_name')}")
                break

    for btn in draft.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        rel = str(btn.get("related_model") or "")
        if rel in plurals:
            if btn.get("label") != plurals[rel]:
                btn["label"] = plurals[rel]
                if btn.get("string"):
                    btn["string"] = plurals[rel]

    for view in draft.get("views") or []:
        if not isinstance(view, dict):
            continue
        mid = str(view.get("model") or "")
        if mid not in plurals:
            continue
        label = escape(plurals[mid], quote=True)
        arch = str(view.get("arch") or "")
        new_arch = re.sub(
            r'(<(?:form|list|kanban|search|tree)\b[^>]*\bstring=")[^"]*(")',
            rf"\1{label}\2",
            arch,
            count=1,
            flags=re.I,
        )
        if new_arch != arch:
            view["arch"] = new_arch
    return notes


def ensure_header_line_models(draft: dict[str, Any]) -> list[str]:
    """Document headers get a line model — Odoo sale.order / purchase.order shape."""
    notes: list[str] = []
    from app.ai_document_shape import may_add_line_satellite

    if not may_add_line_satellite(draft):
        return notes
    depends = set(draft.get("depends") or [])
    by_id = _models_index(draft)
    for mid, model in list(by_id.items()):
        if not _looks_like_header(model):
            continue
        if _has_line_child(draft, mid):
            continue
        line_id = f"{mid}_line"
        if line_id in by_id:
            continue
        parent_label = short_model_label(mid, str(model.get("description") or ""))
        fk = "x_order_id" if mid.endswith("_order") else "x_transfer_id" if "transfer" in mid else f"x_{mid.replace('x_', '')}_id"
        if mid.endswith("_work_order") or "work_order" in mid:
            fk = "x_work_order_id"
        fields: list[dict[str, Any]] = [
            {"name": "x_name", "ttype": "char", "string": "Line", "required": True},
            {
                "name": fk,
                "ttype": "many2one",
                "relation": mid,
                "string": parent_label,
                "required": True,
            },
            {"name": "x_qty", "ttype": "float", "string": "Quantity", "default": 1.0},
            {"name": "x_notes", "ttype": "text", "string": "Notes"},
        ]
        if any(tok in mid for tok in _BOOKING_TOKENS):
            fields = [
                {"name": "x_name", "ttype": "char", "string": "Line", "required": True},
                {
                    "name": fk,
                    "ttype": "many2one",
                    "relation": mid,
                    "string": parent_label,
                    "required": True,
                },
                {"name": "x_hours", "ttype": "float", "string": "Hours", "default": 1.0},
                {
                    "name": "x_user_id",
                    "ttype": "many2one",
                    "relation": "res.users",
                    "string": "Assignee",
                },
                {"name": "x_notes", "ttype": "text", "string": "Notes"},
            ]
        elif "product" in depends or "stock" in depends:
            fields.insert(
                2,
                {
                    "name": "x_product_id",
                    "ttype": "many2one",
                    "relation": "product.product",
                    "string": "Product / spare",
                },
            )
        line = {
            "model": line_id,
            "description": f"{parent_label} Line",
            "mode": "new",
            "source": "odoo_app_bar",
            "fields": fields,
        }
        draft.setdefault("models", []).append(line)
        o2m = f"x_{line_id.replace('x_', '')}_ids"
        if o2m not in _field_names(model):
            model.setdefault("fields", []).append(
                {
                    "name": o2m,
                    "ttype": "one2many",
                    "relation": line_id,
                    "relation_field": fk,
                    "string": "Lines",
                    "source": "odoo_app_bar",
                }
            )
        notes.append(f"app_bar: added line model {line_id}")
        by_id[line_id] = line
    return notes


def _skip_stock_project_on_residual(
    draft: dict[str, Any], by_id: dict[str, dict[str, Any]]
) -> bool:
    """Project.task with x_<residual>_id is the link — do not also put project.project on the header."""
    for key in ("_pack_reuse_stock", "reuse_stock"):
        raw = draft.get(key)
        if not isinstance(raw, list):
            continue
        for row in raw:
            if (
                isinstance(row, dict)
                and str(row.get("model") or "") == "project.task"
                and row.get("link_only")
            ):
                return True
    residual = {
        mid
        for mid, model in by_id.items()
        if str(mid).startswith("x_") and str(model.get("mode") or "new") != "inherit"
    }
    task = by_id.get("project.task") or {}
    for field in task.get("fields") or []:
        if not isinstance(field, dict) or field.get("ttype") != "many2one":
            continue
        if str(field.get("relation") or "") in residual:
            return True
    return False


def wire_stock_apps_from_depends(draft: dict[str, Any]) -> list[str]:
    """If depends lists hr/maintenance/purchase/project/stock, actually link them."""
    notes: list[str] = []
    from app.ai_document_shape import additive_model_growth_blocked

    if additive_model_growth_blocked(draft):
        return notes
    brief = draft.get("_operator_brief") if isinstance(draft.get("_operator_brief"), dict) else {}
    forbidden = {str(x).strip().lower() for x in (brief.get("forbidden_bridges") or []) if x}
    depends = {str(x) for x in (draft.get("depends") or []) if str(x) not in forbidden}
    by_id = _models_index(draft)

    def _pick(tokens: tuple[str, ...]) -> dict[str, Any] | None:
        for mid, model in by_id.items():
            if any(tok in mid for tok in tokens):
                return model
        return None

    site = _pick(_SITE_TOKENS)
    ops = None
    for mid, model in by_id.items():
        if model.get("is_workflow") and any(tok in mid for tok in _HEADER_TOKENS):
            ops = model
            break
    if ops is None:
        ops = next(
            (m for m in by_id.values() if m.get("is_workflow") and not str(m.get("model")).endswith("_line")),
            None,
        )
    asset = _pick(("asset", "equipment", "well"))

    def _add_m2o(model: dict[str, Any] | None, name: str, relation: str, label: str) -> None:
        if not model:
            return
        if name in _field_names(model):
            return
        model.setdefault("fields", []).append(
            {
                "name": name,
                "ttype": "many2one",
                "relation": relation,
                "string": label,
                "help": f"Link-only — use the {relation} app; do not duplicate it.",
                "source": "odoo_app_bar",
            }
        )
        notes.append(f"app_bar: {model.get('model')}.{name} → {relation}")

    if "hr" in depends:
        already_employee = any(
            isinstance(f, dict) and str(f.get("relation") or "") == "hr.employee"
            for f in ((ops or {}).get("fields") or [])
        )
        if not already_employee:
            _add_m2o(ops, "x_employee_id", "hr.employee", "Employee / crew")
    if "maintenance" in depends:
        _add_m2o(asset or ops, "x_equipment_id", "maintenance.equipment", "Equipment")
        _add_m2o(ops, "x_maintenance_request_id", "maintenance.request", "Maintenance request")
    if "purchase" in depends:
        _add_m2o(ops, "x_purchase_order_id", "purchase.order", "Purchase order")
    if "project" in depends and not _skip_stock_project_on_residual(draft, by_id):
        _add_m2o(ops or site, "x_project_id", "project.project", "Project / turnaround")
    if "stock" in depends:
        _add_m2o(site, "x_warehouse_id", "stock.warehouse", "Warehouse")

    reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
    models_reuse = set(reuse.get("models") or [])
    for rel in (
        "hr.employee",
        "maintenance.equipment",
        "maintenance.request",
        "purchase.order",
        "project.project",
        "stock.warehouse",
        "product.product",
    ):
        if any(
            isinstance(f, dict) and f.get("relation") == rel
            for m in by_id.values()
            for f in (m.get("fields") or [])
        ):
            models_reuse.add(rel)
    if models_reuse:
        draft["reuse"] = {**reuse, "models": sorted(models_reuse)}
    return notes


_STOCK_BRIDGE_HOSTS: tuple[tuple[str, str, str], ...] = (
    ("sale", "sale.order", "Quotations"),
    ("account", "account.move", "Invoices"),
    ("crm", "crm.lead", "Leads"),
    ("calendar", "calendar.event", "Meetings"),
    ("project", "project.task", "Tasks"),
)


def _residual_header_id(draft: dict[str, Any]) -> str | None:
    """Primary custom document — explicit residual, else first workflow header."""
    by_id = _models_index(draft)
    prompt = str(draft.get("_user_prompt") or "")
    try:
        from app.ai_stock_first import extract_explicit_residuals

        for _leaf, mid, _reason in extract_explicit_residuals(prompt):
            if mid in by_id and str((by_id[mid] or {}).get("mode") or "new") != "inherit":
                return mid
    except Exception:  # noqa: BLE001
        pass
    for mid, model in by_id.items():
        if not str(mid).startswith("x_"):
            continue
        if mid.endswith("_line") or mid.endswith("_party"):
            continue
        if str(model.get("mode") or "new") == "inherit":
            continue
        if looks_like_register(mid):
            continue
        if model.get("is_workflow"):
            return mid
    for mid, model in by_id.items():
        if not str(mid).startswith("x_"):
            continue
        if mid.endswith("_line") or mid.endswith("_party"):
            continue
        if str(model.get("mode") or "new") == "inherit":
            continue
        if looks_like_register(mid):
            continue
        return mid
    return None


def ensure_residual_satellites(draft: dict[str, Any]) -> list[str]:
    """Party + line on the residual header (senior document workspace)."""
    notes: list[str] = []
    if draft.get("domain_pack") or draft.get("_component"):
        return notes
    from app.ai_document_shape import (
        additive_model_growth_blocked,
        may_add_line_satellite,
        may_add_party_satellite,
    )

    if additive_model_growth_blocked(draft):
        return notes
    mid = _residual_header_id(draft)
    if not mid:
        return notes
    by_id = _models_index(draft)
    header = by_id.get(mid)
    if not isinstance(header, dict):
        return notes
    leaf = mid[2:] if mid.startswith("x_") else mid
    label = short_model_label(mid, str(header.get("description") or ""))
    fk = f"x_{leaf}_id"

    party_id = f"{mid}_party"
    if party_id not in by_id and may_add_party_satellite(draft):
        party = {
            "model": party_id,
            "description": f"{label} party / role",
            "mode": "new",
            "source": "odoo_app_bar",
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Role label"},
                {
                    "name": fk,
                    "ttype": "many2one",
                    "relation": mid,
                    "string": label,
                    "required": True,
                },
                {
                    "name": "x_partner_id",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "string": "Contact",
                    "required": True,
                },
                {"name": "x_role", "ttype": "char", "string": "Role"},
                {
                    "name": "x_company_id",
                    "ttype": "many2one",
                    "relation": "res.company",
                    "string": "Company",
                },
            ],
        }
        draft.setdefault("models", []).append(party)
        o2m = f"x_{leaf}_party_ids"
        if o2m not in _field_names(header):
            header.setdefault("fields", []).append(
                {
                    "name": o2m,
                    "ttype": "one2many",
                    "relation": party_id,
                    "relation_field": fk,
                    "string": "Parties",
                    "source": "odoo_app_bar",
                }
            )
        notes.append(f"app_bar: added party satellite {party_id}")
        by_id[party_id] = party

    line_id = f"{mid}_line"
    if line_id not in by_id and not _has_line_child(draft, mid) and may_add_line_satellite(draft):
        line = {
            "model": line_id,
            "description": f"{label} line",
            "mode": "new",
            "source": "odoo_app_bar",
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Line", "required": True},
                {
                    "name": fk,
                    "ttype": "many2one",
                    "relation": mid,
                    "string": label,
                    "required": True,
                },
                {"name": "x_qty", "ttype": "float", "string": "Quantity", "default": 1.0},
                {"name": "x_notes", "ttype": "text", "string": "Notes"},
                {
                    "name": "x_company_id",
                    "ttype": "many2one",
                    "relation": "res.company",
                    "string": "Company",
                },
            ],
        }
        draft.setdefault("models", []).append(line)
        o2m = f"x_{leaf}_line_ids"
        if o2m not in _field_names(header):
            header.setdefault("fields", []).append(
                {
                    "name": o2m,
                    "ttype": "one2many",
                    "relation": line_id,
                    "relation_field": fk,
                    "string": "Lines",
                    "source": "odoo_app_bar",
                }
            )
        notes.append(f"app_bar: added line satellite {line_id}")
    return notes


def ensure_stock_inherit_bridges(draft: dict[str, Any]) -> list[str]:
    """Hang the residual FK on stock documents — senior Community inherit, not x_bill."""
    notes: list[str] = []
    if draft.get("_component"):
        return notes
    from app.ai_document_shape import additive_model_growth_blocked, allowed_bridge_modules

    if additive_model_growth_blocked(draft):
        return notes
    residual = _residual_header_id(draft)
    if not residual:
        return notes
    leaf = residual[2:] if residual.startswith("x_") else residual.replace(".", "_")
    fk = f"x_{leaf}_id"
    header = _models_index(draft).get(residual) or {}
    label = short_model_label(residual, str(header.get("description") or ""))
    depends = {str(x) for x in (draft.get("depends") or []) if x}
    reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
    reused = {str(x) for x in (reuse.get("models") or []) if x}
    plan = reuse.get("plan") if isinstance(reuse.get("plan"), dict) else {}
    reused |= {str(x) for x in (plan.get("models") or []) if x}
    by_id = _models_index(draft)
    existing_btns = {
        (str(b.get("on_model")), str(b.get("related_model")), str(b.get("relation_field")))
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }

    allowed = allowed_bridge_modules(draft)
    for module, host, btn_label in _STOCK_BRIDGE_HOSTS:
        if module not in allowed:
            continue
        if module not in depends and host not in reused:
            continue
        row = by_id.get(host)
        if row is None:
            row = {
                "model": host,
                "mode": "inherit",
                "inherit": host,
                "description": f"{btn_label} linked to {label}",
                "source": "odoo_app_bar",
                "fields": [],
            }
            draft.setdefault("models", []).append(row)
            by_id[host] = row
            notes.append(f"app_bar: inherit {host} for {fk}")
        elif str(row.get("mode") or "new") != "inherit" and not str(host).startswith("x_"):
            row["mode"] = "inherit"
            row["inherit"] = host
        if fk not in _field_names(row):
            row.setdefault("fields", []).append(
                {
                    "name": fk,
                    "ttype": "many2one",
                    "relation": residual,
                    "string": label,
                    "help": f"Link-only — use the {host} app; do not duplicate it.",
                    "source": "odoo_app_bar",
                }
            )
            notes.append(f"app_bar: {host}.{fk} → {residual}")
        key = (residual, host, fk)
        if key not in existing_btns:
            draft.setdefault("smart_buttons", []).append(
                {
                    "on_model": residual,
                    "related_model": host,
                    "relation_field": fk,
                    "label": btn_label,
                    "icon": "fa-external-link",
                    "source": "odoo_app_bar",
                }
            )
            existing_btns.add(key)
            notes.append(f"app_bar: smart button {residual} → {host}")
    return notes


def _custom_child_o2m_targets(model: dict[str, Any]) -> set[str]:
    """Custom x_* children already on the header notebook (sale.order.line shape)."""
    out: set[str] = set()
    for field in model.get("fields") or []:
        if not isinstance(field, dict) or field.get("ttype") != "one2many":
            continue
        rel = str(field.get("relation") or "")
        if rel.startswith("x_"):
            out.add(rel)
    return out


def _notebook_child_ids(by_id: dict[str, dict[str, Any]]) -> set[str]:
    """Custom children already on an x_* header as O2M (party/line/register pages)."""
    out: set[str] = set()
    for mid, model in by_id.items():
        if not str(mid).startswith("x_"):
            continue
        if str((model or {}).get("mode") or "new") == "inherit":
            continue
        out |= _custom_child_o2m_targets(model or {})
    return out


def _is_notebook_duplicate_smart_button(
    on_model: str, related_model: str, by_id: dict[str, dict[str, Any]]
) -> bool:
    if not on_model.startswith("x_") or not related_model.startswith("x_"):
        return False
    return related_model in _custom_child_o2m_targets(by_id.get(on_model) or {})


def ensure_relational_smart_buttons(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    existing = {
        (str(b.get("on_model")), str(b.get("related_model")), str(b.get("relation_field")))
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        if mid.endswith("_line"):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "one2many":
                continue
            rel = str(field.get("relation") or "")
            fk = str(field.get("relation_field") or "")
            if not rel.startswith("x_") or not fk:
                continue
            if _is_notebook_duplicate_smart_button(mid, rel, by_id):
                continue
            key = (mid, rel, fk)
            if key in existing:
                continue
            label = short_model_label(rel, str((by_id.get(rel) or {}).get("description") or ""), plural=True)
            draft.setdefault("smart_buttons", []).append(
                {
                    "on_model": mid,
                    "related_model": rel,
                    "relation_field": fk,
                    "label": label,
                    "icon": "fa-list",
                    "source": "odoo_app_bar",
                }
            )
            existing.add(key)
            notes.append(f"app_bar: smart button {mid} → {rel}")
    kept_btns: list[dict[str, Any]] = []
    for btn in draft.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        on_model = str(btn.get("on_model") or "")
        rel = str(btn.get("related_model") or "")
        if _is_notebook_duplicate_smart_button(on_model, rel, by_id):
            notes.append(f"app_bar: dropped notebook-duplicate smart button {on_model} → {rel}")
            continue
        label = str(btn.get("label") or "")
        if rel in by_id and ("/" in label or len(label) > 28):
            btn["label"] = short_model_label(
                rel, str(by_id[rel].get("description") or ""), plural=True
            )
        kept_btns.append(btn)
    draft["smart_buttons"] = kept_btns
    return notes


def ensure_mail_mixins(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or mid.endswith("_line"):
            continue
        if not (model.get("is_workflow") or any(
            tok in mid for tok in _SITE_TOKENS + ("asset", "studio", "artist", "client")
        )):
            continue
        mixins = list(model.get("mixins") or [])
        added = False
        for mixin in ("mail.thread", "mail.activity.mixin"):
            if mixin not in mixins:
                mixins.append(mixin)
                added = True
        if added:
            model["mixins"] = mixins
            notes.append(f"app_bar: mail mixins on {mid}")
    return notes


def rebuild_form_transition_headers(draft: dict[str, Any]) -> list[str]:
    """Collapse duplicate Cancel buttons using grouped transition metadata."""
    notes: list[str] = []
    from app.ai_workflow import build_transition_header_buttons
    from html import escape as html_escape

    by_id = _models_index(draft)
    from app.ai_model_quality import is_embedded_line_model

    for view in draft.get("views") or []:
        if not isinstance(view, dict) or str(view.get("type") or "") != "form":
            continue
        mid = str(view.get("model") or "")
        if is_embedded_line_model(mid):
            continue
        model = by_id.get(mid) or {}
        sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
        transitions = sf.get("transitions") if isinstance(sf.get("transitions"), list) else []
        if not transitions:
            continue
        visible = sf.get("statusbar_visible") if isinstance(sf.get("statusbar_visible"), list) else []
        vis_attr = (
            f' statusbar_visible="{html_escape(",".join(str(s) for s in visible))}"' if visible else ""
        )
        state_name = str(sf.get("field") or "x_status")
        manager_dests: set[str] | None = None
        flow = draft.get("_approval_flow")
        if isinstance(flow, dict):
            manager_dests = {str(x) for x in (flow.get("manager_dests") or [])}
        elif sf.get("approval"):
            manager_dests = {"approved", "refused", "rejected"}
        buttons = build_transition_header_buttons(
            transitions, field=state_name, manager_dests=manager_dests
        )
        lock_attr = (
            " options=\"{'clickable': False}\" readonly=\"1\"" if buttons else ""
        )
        header = (
            f"<header>"
            f'<field name="{html_escape(state_name)}" widget="statusbar"{vis_attr}{lock_attr}/>'
            f"{buttons}"
            f"</header>"
        )
        arch = str(view.get("arch") or "")
        new_arch, n = re.subn(r"<header>.*?</header>", header, arch, count=1, flags=re.I | re.S)
        if n:
            view["arch"] = new_arch
            notes.append(f"app_bar: rebuilt header buttons on {mid}")
        elif re.search(r"<form\b", arch, re.I) and not re.search(r"<header>", arch, re.I):
            view["arch"] = re.sub(
                r"(<form\b[^>]*>)", r"\1" + header, arch, count=1, flags=re.I
            )
            notes.append(f"app_bar: injected header buttons on {mid}")
    return notes


def inject_chatter_on_forms(draft: dict[str, Any]) -> list[str]:
    """Odoo 17+ form chatter sibling. Skip majors ≤16 (experimental, different arch)."""
    notes: list[str] = []
    try:
        major = int(draft.get("odoo_major") or 19)
    except (TypeError, ValueError):
        major = 19
    if major < 17:
        return notes
    by_id = _models_index(draft)
    from app.ai_model_quality import is_embedded_line_model

    for view in draft.get("views") or []:
        if not isinstance(view, dict) or str(view.get("type") or "") != "form":
            continue
        mid = str(view.get("model") or "")
        if is_embedded_line_model(mid):
            continue
        model = by_id.get(mid) or {}
        mixins = {str(x) for x in (model.get("mixins") or [])}
        if "mail.thread" not in mixins:
            continue
        arch = str(view.get("arch") or "")
        if "<chatter" in arch.lower() or "oe_chatter" in arch:
            continue
        if "</sheet>" not in arch:
            continue
        view["arch"] = arch.replace("</sheet>", "</sheet><chatter/>", 1)
        notes.append(f"app_bar: chatter on {mid} form")
    return notes


def enrich_kanban_cards(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    by_id = _models_index(draft)
    for view in draft.get("views") or []:
        if not isinstance(view, dict) or str(view.get("type") or "") != "kanban":
            continue
        mid = str(view.get("model") or "")
        model = by_id.get(mid)
        if not model:
            continue
        arch = str(view.get("arch") or "")
        m2o = next(
            (
                str(f.get("name"))
                for f in (model.get("fields") or [])
                if isinstance(f, dict)
                and f.get("ttype") == "many2one"
                and str(f.get("relation") or "").startswith("x_")
            ),
            None,
        )
        if not m2o or f'name="{m2o}"' in arch:
            continue
        if '<field name="x_status"/>' in arch:
            view["arch"] = arch.replace(
                '<field name="x_status"/>',
                f'<field name="x_status"/><field name="{m2o}"/>',
                1,
            )
            notes.append(f"app_bar: kanban card m2o on {mid}")
    return notes


def ensure_lifecycle_automations(draft: dict[str, Any]) -> list[str]:
    """Permit expiry / overdue jobs / critical incidents — not generic follow-ups."""
    notes: list[str] = []
    autos = [a for a in (draft.get("automations") or []) if isinstance(a, dict)]
    names = {str(a.get("name") or "") for a in autos}

    def _add(auto: dict[str, Any]) -> None:
        if auto["name"] in names:
            return
        draft.setdefault("automations", []).append(auto)
        names.add(auto["name"])
        notes.append(f"app_bar: automation {auto['name']}")

    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        names_f = _field_names(model)
        end_field = next(
            (
                n
                for n in (
                    "x_date_end",
                    "x_date_due",
                    "x_due_date",
                    "x_end_date",
                    "x_end_time",
                )
                if n in names_f
            ),
            None,
        )
        status_field = next(
            (
                f
                for f in (model.get("fields") or [])
                if isinstance(f, dict) and f.get("name") == "x_status"
            ),
            None,
        )
        from app.ai_selection import selection_keys

        keys = set(selection_keys((status_field or {}).get("selection")))
        if end_field and "expired" in keys:
            _add(
                {
                    "name": f"Expire overdue {short_model_label(mid)}",
                    "model": mid,
                    "trigger": "on_time",
                    "trg_date_field_name": end_field,
                    "description": f"Mark {short_model_label(mid).lower()} expired when {end_field} has passed.",
                    "filter_domain": f"[('{end_field}', '!=', False), ('{end_field}', '<', 'now'), ('x_status', 'not in', ['expired', 'cancelled', 'done', 'closed'])]",
                    "safe_actions": [{"kind": "object_write", "field": "x_status", "value": "expired"}],
                    "source": "odoo_app_bar",
                }
            )
        if end_field and keys & {
            "in_progress",
            "planned",
            "active",
            "confirmed",
            "open",
            "recording",
        }:
            _add(
                {
                    "name": f"Follow up overdue {short_model_label(mid)}",
                    "model": mid,
                    "trigger": "on_time",
                    "trg_date_field_name": end_field,
                    "description": f"Schedule an activity when {short_model_label(mid).lower()} is past {end_field}.",
                    "filter_domain": f"[('{end_field}', '!=', False), ('{end_field}', '<', 'now'), ('x_status', 'in', ['in_progress', 'planned', 'active'])]",
                    "safe_actions": [
                        {"kind": "next_activity", "summary": f"Overdue {short_model_label(mid).lower()}"}
                    ],
                    "source": "odoo_app_bar",
                }
            )
        if any(tok in mid for tok in _INCIDENT_TOKENS) and "x_severity" in names_f:
            _add(
                {
                    "name": f"Notify critical {short_model_label(mid)}",
                    "model": mid,
                    "trigger": "on_create",
                    "description": "Post a chatter note when a critical incident is logged.",
                    "filter_domain": "[('x_severity', '=', 'critical')]",
                    "safe_actions": [
                        {"kind": "mail_post", "body": "Critical incident reported — review immediately."}
                    ],
                    "source": "odoo_app_bar",
                }
            )
    return notes


def apply_senior_sequence_prefixes(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for seq in draft.get("sequences") or []:
        if not isinstance(seq, dict):
            continue
        mid = str(seq.get("model") or "")
        if not mid.startswith("x_") or mid.endswith("_line"):
            continue
        prefix = senior_sequence_prefix(mid)
        if seq.get("prefix") != prefix:
            seq["prefix"] = prefix
            notes.append(f"app_bar: sequence prefix {mid} → {prefix}")
        by_id = _models_index(draft)
        model = by_id.get(mid)
        if not model:
            continue
        token = prefix.rstrip("/")
        for field in model.get("fields") or []:
            if isinstance(field, dict) and field.get("name") in {"x_code", "x_reference"}:
                field["help"] = f"Auto-numbered via ir.sequence ({token}/00001)"
    return notes


def ensure_reverse_o2ms(draft: dict[str, Any]) -> list[str]:
    """Parent gets O2M when a child already M2Os it (permit→WO, incident→facility).

    Stock inherit (sale.order, calendar.event) is a smart-button target — not
    an embedded form O2M. Nested lists would emit x_name those models lack.
    """
    from app.ai_model_quality import odoo_o2m_field_name

    notes: list[str] = []
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        if mid.endswith("_line") or not str(mid).startswith("x_"):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "many2one":
                continue
            parent_id = str(field.get("relation") or "")
            parent = by_id.get(parent_id)
            if not parent or not parent_id.startswith("x_"):
                continue
            fk = str(field.get("name") or "")
            already = any(
                isinstance(f, dict)
                and f.get("ttype") == "one2many"
                and f.get("relation") == mid
                for f in (parent.get("fields") or [])
            )
            if already:
                continue
            o2m = odoo_o2m_field_name(mid)
            parent.setdefault("fields", []).append(
                {
                    "name": o2m,
                    "ttype": "one2many",
                    "relation": mid,
                    "relation_field": fk,
                    "string": short_model_label(mid, str(model.get("description") or ""), plural=True),
                    "source": "odoo_app_bar",
                }
            )
            notes.append(f"app_bar: reverse O2M {parent_id}.{o2m} → {mid}")
    return notes


def drop_orphan_relational_fields(draft: dict[str, Any]) -> list[str]:
    """Drop M2O/O2M/M2M whose x_ target is not in this spec (phantom LLM children)."""
    notes: list[str] = []
    known = set(_models_index(draft))
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        kept: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            fname = str(field.get("name") or "")
            if fname in seen_names:
                notes.append(f"app_bar: dropped duplicate field {mid}.{fname}")
                continue
            rel = str(field.get("relation") or "")
            ttype = str(field.get("ttype") or "")
            if (
                ttype in {"many2one", "one2many", "many2many"}
                and rel.startswith("x_")
                and rel not in known
            ):
                notes.append(f"app_bar: dropped orphan {ttype} {mid}.{fname} → {rel}")
                continue
            seen_names.add(fname)
            kept.append(field)
        model["fields"] = kept
    return notes


def _generic_loop_leaf(model_id: str) -> str | None:
    leaf = str(model_id).replace("x_", "")
    parts = [p for p in leaf.split("_") if p]
    if parts and len(parts[0]) <= 3 and len(parts) > 1:
        parts = parts[1:]
        leaf = "_".join(parts)
    hits: list[str] = []
    for generic in _GENERIC_LOOP_LEAVES:
        tokens = generic.split("_")
        if (
            leaf == generic
            or leaf.endswith("_" + generic)
            or leaf.startswith(generic + "_")
            or (generic == "staff" and leaf.startswith("staff"))
        ):
            hits.append(generic)
        elif all(t in parts for t in tokens):
            hits.append(generic)
    if not hits:
        return None
    return max(hits, key=len)


def _prompt_keeps_generic(prompt: str, generic: str) -> bool:
    from app.ai_domain_nouns import extract_prompt_nouns, noun_search_tokens

    expanded: set[str] = set()
    for noun in extract_prompt_nouns(prompt):
        expanded |= noun_search_tokens(noun)
    if generic in expanded:
        return True
    return bool(re.search(rf"\b{re.escape(generic)}s?\b", prompt, re.I))


def prune_generic_loop_models(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """Drop LLM ops-loop filler (deposit/task/bill/…) when the prompt did not ask for it.

    Pack-backed drafts keep their template models. Unpacked domains must not ship a
    second CRM/billing/task app around the actual nouns.
    """
    notes: list[str] = []
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    by_id = _models_index(draft)
    from app.ai_stock_first import restore_pack_identity

    restore_pack_identity(draft, user_prompt=prompt)
    pack_keep = {
        str(x)
        for x in (draft.get("_pack_model_ids") or [])
        if x
    }
    if draft.get("domain_pack") and not pack_keep:
        return notes
    candidates: list[tuple[int, str]] = []
    for mid in by_id:
        if not mid.startswith("x_") or mid.endswith("_line"):
            continue
        if pack_keep and (mid in pack_keep or mid.endswith("_line") and mid in pack_keep):
            continue
        generic = _generic_loop_leaf(mid)
        if not generic and not (
            pack_keep
            and any(
                tok in mid.replace("x_", "")
                for tok in ("attorney", "bill", "payment", "deposit", "task", "event")
            )
        ):
            continue
        if pack_keep and mid not in pack_keep:
            pass
        elif prompt and generic and _prompt_keeps_generic(prompt, generic):
            continue
        rank = (
            _GENERIC_LOOP_PRIORITY.index(generic)
            if generic in _GENERIC_LOOP_PRIORITY
            else 99
        )
        candidates.append((rank, mid))
    if not candidates:
        return notes
    candidates.sort()
    remaining = {m for m in by_id if m.startswith("x_") and not m.endswith("_line")}
    removed: set[str] = set()
    floor = _KEEP_MODELS_FLOOR
    try:
        from app.ai_document_shape import document_shape_of, shape_budget

        shape = document_shape_of(draft, prompt=prompt)
        plan = draft.get("_architecture_plan") if isinstance(draft.get("_architecture_plan"), dict) else {}
        raw_b = (plan.get("surface_budget") or {}).get("new_models") if isinstance(plan.get("surface_budget"), dict) else None
        if raw_b is not None:
            floor = min(floor, int(raw_b))
        else:
            floor = min(floor, shape_budget(shape, x_models=len(remaining)))
        if shape == "register":
            floor = 1
    except Exception:  # noqa: BLE001
        pass
    for _rank, mid in candidates:
        if not pack_keep and len(remaining) - 1 < floor:
            break
        remaining.discard(mid)
        removed.add(mid)
        line_id = f"{mid}_line"
        if line_id in by_id:
            removed.add(line_id)
    if not removed:
        return notes
    from app.ai_domain_packs import _purge_draft_artifacts_for_models

    notes.extend(_retarget_removed_relations(draft, removed))
    _purge_draft_artifacts_for_models(draft, removed)
    pruned = list(draft.get("_app_bar_pruned") or [])
    draft["_app_bar_pruned"] = sorted({*pruned, *removed})
    notes.append(f"app_bar: pruned generic-loop model(s) {', '.join(sorted(removed))}")
    return notes


def _retarget_removed_relations(
    draft: dict[str, Any],
    removed: set[str],
    *,
    extra_fallbacks: dict[str, str] | None = None,
) -> list[str]:
    notes: list[str] = []
    fallbacks: dict[str, str] = dict(extra_fallbacks or {})
    for mid in removed:
        if mid in fallbacks:
            continue
        leaf = _generic_loop_leaf(mid) or mid.replace("x_", "")
        if leaf in {"bill", "invoice", "payment"}:
            fallbacks[mid] = "account.move"
        elif leaf in {"staff", "staffing", "crew", "attorney", "lawyer", "counsel"}:
            fallbacks[mid] = "hr.employee"
        elif leaf == "currency":
            fallbacks[mid] = "res.currency"
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        kept: list[dict[str, Any]] = []
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            rel = str(field.get("relation") or "")
            if rel not in removed:
                kept.append(field)
                continue
            target = fallbacks.get(rel)
            if not target:
                notes.append(
                    f"app_bar: dropped field {model.get('model')}.{field.get('name')} → {rel}"
                )
                continue
            if str(field.get("ttype") or "") == "one2many" and not target.startswith("x_"):
                notes.append(
                    f"app_bar: dropped O2M {model.get('model')}.{field.get('name')} "
                    f"(stock {target} has no inverse)"
                )
                continue
            field = dict(field)
            field["relation"] = target
            fname = str(field.get("name") or "")
            if target == "account.move" and fname in {
                "x_bill_id",
                "x_invoice_id",
                "x_payment_id",
            }:
                field["name"] = "x_invoice_id"
                field["string"] = "Invoice"
            elif target == "hr.employee":
                field["string"] = field.get("string") or "Employee"
            elif target == "res.currency":
                field["string"] = field.get("string") or "Currency"
            elif target == "res.users":
                field["string"] = field.get("string") or "User"
            kept.append(field)
            notes.append(
                f"app_bar: retargeted {model.get('model')}.{field.get('name')} → {target}"
            )
        model["fields"] = kept
    return notes


def drop_stock_inverse_o2ms(draft: dict[str, Any]) -> list[str]:
    """Stock related docs are smart buttons, not form O2M lists.

    Nested ``<list><field name="x_name"/></list>`` is illegal on sale.order /
    calendar.event. The inherit already has ``x_matter_id``; the stat button
    opens the stock action. Reverse O2M *on* a stock inherit
    (sale.order.x_matter_ids → x_sale_order_id) is the same lie.
    """
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        kept: list[dict[str, Any]] = []
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            rel = str(field.get("relation") or "")
            if field.get("ttype") == "one2many" and rel and not rel.startswith("x_"):
                notes.append(
                    f"app_bar: dropped O2M {mid}.{field.get('name')} "
                    f"(stock {rel} has no inverse)"
                )
                continue
            if (
                field.get("ttype") == "one2many"
                and not mid.startswith("x_")
                and rel.startswith("x_")
            ):
                notes.append(
                    f"app_bar: dropped reverse O2M {mid}.{field.get('name')} "
                    f"(stock inherit is not the O2M parent of {rel})"
                )
                continue
            kept.append(field)
        model["fields"] = kept
    return notes


def prune_leftover_specialty_satellites(draft: dict[str, Any]) -> list[str]:
    """Site already has x_specialty selection — drop leftover specialty catalogs."""
    notes: list[str] = []
    by_id = _models_index(draft)
    host_has_specialty = False
    for model in by_id.values():
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if (
                str(field.get("name") or "") == "x_specialty"
                and field.get("ttype") == "selection"
            ):
                host_has_specialty = True
                break
        if host_has_specialty:
            break
    if not host_has_specialty:
        return notes
    removed: set[str] = set()
    for mid, model in by_id.items():
        tokens = _leaf_tokens(mid)
        if not tokens or tokens[-1] != "specialty":
            continue
        has_sel = any(
            isinstance(f, dict)
            and str(f.get("name") or "") == "x_specialty"
            and f.get("ttype") == "selection"
            for f in (model.get("fields") or [])
        )
        if has_sel:
            continue
        removed.add(mid)
    if not removed:
        return notes
    from app.ai_domain_packs import _purge_draft_artifacts_for_models

    notes.extend(_retarget_removed_relations(draft, removed))
    _purge_draft_artifacts_for_models(draft, removed)
    notes.append(
        f"app_bar: pruned leftover specialty model(s) {', '.join(sorted(removed))}"
    )
    return notes


def repair_named_foreign_keys(draft: dict[str, Any]) -> list[str]:
    """x_studio_id must point at x_studio when that model exists, not res.partner."""
    notes: list[str] = []
    known = set(_models_index(draft))
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "many2one":
                continue
            fname = str(field.get("name") or "")
            match = re.match(r"^x_(.+)_id$", fname)
            if not match:
                continue
            leaf = match.group(1)
            if leaf in _STOCK_FK_LEAVES:
                continue
            target = f"x_{leaf}"
            if target not in known or target == mid:
                continue
            if str(field.get("relation") or "") != target:
                notes.append(
                    f"app_bar: repaired {mid}.{fname} {field.get('relation')} → {target}"
                )
                field["relation"] = target
    return notes


def prune_stock_clone_models(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """Drop x_currency / x_payment / x_crew / orphan x_line_item when stock models are reused."""
    notes: list[str] = []
    from app.ai_stock_first import restore_pack_identity

    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    restore_pack_identity(draft, user_prompt=prompt)
    pack_keep = {
        str(x) for x in (draft.get("_pack_model_ids") or []) if x
    }
    by_id = _models_index(draft)
    reuse: set[str] = set()
    blob = draft.get("reuse")
    if isinstance(blob, dict):
        reuse.update(str(x) for x in (blob.get("models") or []) if x)
        plan = blob.get("plan")
        if isinstance(plan, dict):
            reuse.update(str(x) for x in (plan.get("models") or []) if x)
    depends = {str(x) for x in (draft.get("depends") or []) if x}
    stock_known = reuse | depends

    removed: set[str] = set()
    extra: dict[str, str] = {}
    for mid, stock, signals, keep_noun in _STOCK_CLONE_MODELS:
        if mid not in by_id:
            continue
        if mid in pack_keep:
            continue
        if keep_noun and _prompt_keeps_generic(prompt, keep_noun) and mid not in pack_keep:
            continue
        if signals and not (stock_known & set(signals)):
            continue
        removed.add(mid)
        extra[mid] = stock

    if "x_line_item" in by_id:
        typed_lines = [
            m for m in by_id if m.endswith("_line") and m != "x_line_item"
        ]
        incoming = any(
            isinstance(f, dict)
            and f.get("ttype") == "many2one"
            and str(f.get("relation") or "") == "x_line_item"
            for model in by_id.values()
            for f in (model.get("fields") or [])
        )
        if typed_lines and not incoming:
            removed.add("x_line_item")

    if not removed:
        return notes
    from app.ai_domain_packs import _purge_draft_artifacts_for_models

    notes.extend(_retarget_removed_relations(draft, removed, extra_fallbacks=extra))
    _purge_draft_artifacts_for_models(draft, removed)
    pruned = list(draft.get("_app_bar_pruned") or [])
    draft["_app_bar_pruned"] = sorted({*pruned, *removed})
    notes.append(f"app_bar: pruned stock-clone model(s) {', '.join(sorted(removed))}")
    return notes


def _find_site_model(draft: dict[str, Any]) -> str | None:
    by_id = _models_index(draft)
    for token in _SITE_TOKENS:
        for mid in by_id:
            if mid.endswith("_line"):
                continue
            if token in mid.replace("x_", "").split("_") or mid == f"x_{token}":
                return mid
    return None


def ensure_site_fk_on_operations(draft: dict[str, Any]) -> list[str]:
    """Booking/session/unavailability/rate/equipment must M2O the site (studio/facility)."""
    notes: list[str] = []
    site = _find_site_model(draft)
    if not site:
        return notes
    site_leaf = site.replace("x_", "")
    fk_name = f"x_{site_leaf}_id"
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        if mid == site or mid.endswith("_line"):
            continue
        if not any(tok in mid for tok in _NEEDS_SITE_TOKENS):
            continue
        names = _field_names(model)
        already = any(
            isinstance(f, dict)
            and f.get("ttype") == "many2one"
            and str(f.get("relation") or "") == site
            for f in (model.get("fields") or [])
        )
        if already:
            continue
        if fk_name in names:
            for field in model.get("fields") or []:
                if isinstance(field, dict) and str(field.get("name") or "") == fk_name:
                    if str(field.get("relation") or "") != site:
                        field["relation"] = site
                        notes.append(f"app_bar: retargeted {mid}.{fk_name} → {site}")
            continue
        model.setdefault("fields", []).append(
            {
                "name": fk_name,
                "ttype": "many2one",
                "relation": site,
                "string": short_model_label(site, plural=False),
                "source": "odoo_app_bar",
            }
        )
        notes.append(f"app_bar: added {mid}.{fk_name} → {site}")
    return notes


def _find_role_model(
    draft: dict[str, Any],
    leaves: tuple[str, ...],
    *,
    skip: tuple[str, ...] = ("line", "cost", "rate", "card"),
) -> str | None:
    by_id = _models_index(draft)
    for leaf in leaves:
        exact = f"x_{leaf}"
        if exact in by_id:
            return exact
    for mid in by_id:
        if any(tok in mid for tok in skip):
            continue
        parts = mid.replace("x_", "").split("_")
        if any(leaf in parts for leaf in leaves):
            return mid
    return None


def _ensure_parent_fk(
    draft: dict[str, Any],
    *,
    child_id: str,
    parent_id: str,
    source: str = "odoo_app_bar",
) -> list[str]:
    notes: list[str] = []
    by_id = _models_index(draft)
    child = by_id.get(child_id)
    if not child or parent_id not in by_id or child_id == parent_id:
        return notes
    fk_name = f"x_{parent_id.replace('x_', '', 1)}_id"
    names = _field_names(child)
    already = any(
        isinstance(f, dict)
        and f.get("ttype") == "many2one"
        and str(f.get("relation") or "") == parent_id
        for f in (child.get("fields") or [])
    )
    if already:
        return notes
    if fk_name in names:
        for field in child.get("fields") or []:
            if isinstance(field, dict) and str(field.get("name") or "") == fk_name:
                if str(field.get("relation") or "") != parent_id:
                    field["relation"] = parent_id
                    field["string"] = short_model_label(parent_id, plural=False)
                    notes.append(f"app_bar: retargeted {child_id}.{fk_name} → {parent_id}")
        return notes
    child.setdefault("fields", []).append(
        {
            "name": fk_name,
            "ttype": "many2one",
            "relation": parent_id,
            "string": short_model_label(parent_id, plural=False),
            "source": source,
        }
    )
    notes.append(f"app_bar: added {child_id}.{fk_name} → {parent_id}")
    return notes


def ensure_booking_engagement_fk(draft: dict[str, Any]) -> list[str]:
    """Studio time (booking/session) belongs on the engagement/project, not a parallel header."""
    notes: list[str] = []
    engagement = _find_role_model(
        draft, ("engagement", "project", "matter", "case")
    )
    if not engagement:
        return notes
    by_id = _models_index(draft)
    for mid in by_id:
        if mid.endswith("_line"):
            continue
        if not any(tok in mid for tok in _BOOKING_TOKENS):
            continue
        notes.extend(_ensure_parent_fk(draft, child_id=mid, parent_id=engagement))
    return notes


def ensure_revision_deliverable_fk(draft: dict[str, Any]) -> list[str]:
    """A revision/take is a version of a deliverable, not a free-floating file."""
    notes: list[str] = []
    deliverable = _find_role_model(
        draft,
        ("deliverable", "output"),
        skip=("line", "cost", "rate", "card", "session", "booking"),
    )
    if not deliverable:
        from app.ai_domain_density import _OUTPUT_TOKENS

        deliverable = _find_role_model(
            draft,
            _OUTPUT_TOKENS,
            skip=("line", "cost", "rate", "card", "session", "booking", "studio"),
        )
    if not deliverable:
        return notes
    by_id = _models_index(draft)
    for mid in by_id:
        if mid.endswith("_line"):
            continue
        if not any(tok in mid for tok in ("revision", "take", "version")):
            continue
        notes.extend(_ensure_parent_fk(draft, child_id=mid, parent_id=deliverable))
    return notes


_LINK_ONLY_SALE_HELP = (
    "Link-only — wire to sale.order manually; this document is not a sales order."
)


def _mark_reuse_link_only(draft: dict[str, Any], stock_model: str, *, reason: str) -> None:
    reuse = draft.get("reuse")
    if not isinstance(reuse, dict):
        reuse = {}
        draft["reuse"] = reuse
    models = {str(x) for x in (reuse.get("models") or []) if x}
    models.add(stock_model)
    reuse["models"] = sorted(models)
    plan = reuse.get("plan")
    if not isinstance(plan, dict):
        plan = {}
        reuse["plan"] = plan
    decisions = list(plan.get("decisions") or [])
    found = False
    for row in decisions:
        if isinstance(row, dict) and str(row.get("model") or "") == stock_model:
            row["link_only"] = True
            row.setdefault("confirmed", True)
            found = True
    if not found:
        decisions.append(
            {
                "model": stock_model,
                "source": "odoo_app_bar",
                "reason": reason,
                "confirmed": True,
                "link_only": True,
            }
        )
    plan["decisions"] = decisions


def stamp_session_sale_order_link_only(draft: dict[str, Any]) -> list[str]:
    """sale.order on a session/booking is a pointer — never a native sales document."""
    notes: list[str] = []
    by_id = _models_index(draft)
    stamped = False
    for mid, model in by_id.items():
        if mid.endswith("_line"):
            continue
        if not any(tok in mid for tok in _BOOKING_TOKENS):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            fname = str(field.get("name") or "")
            rel = str(field.get("relation") or "")
            if field.get("ttype") != "many2one":
                continue
            if rel != "sale.order" and fname != "x_sale_order_id":
                continue
            field["relation"] = "sale.order"
            field["name"] = "x_sale_order_id"
            field["string"] = "Sales order"
            field["help"] = _LINK_ONLY_SALE_HELP
            stamped = True
            notes.append(f"app_bar: sale.order on {mid} is link-only")
    if stamped:
        _mark_reuse_link_only(
            draft, "sale.order", reason="Sales orders (link-only)"
        )
        depends = list(draft.get("depends") or [])
        if "sale" not in depends:
            depends.append("sale")
            draft["depends"] = depends
        review = draft.setdefault("review_notes", [])
        if isinstance(review, list):
            note = (
                "sale.order on sessions/bookings is link-only — metadata export "
                "does not create or post quotations."
            )
            if note not in review:
                review.append(note)
    return notes


def _has_m2o_to(model: dict[str, Any], targets: set[str]) -> bool:
    return any(
        isinstance(f, dict)
        and f.get("ttype") == "many2one"
        and str(f.get("relation") or "") in targets
        for f in (model.get("fields") or [])
    )


def _models_matching_leaves(
    draft: dict[str, Any],
    leaves: tuple[str, ...],
    *,
    skip: tuple[str, ...] = (),
) -> list[str]:
    out: list[str] = []
    for mid in _models_index(draft):
        if mid.endswith("_line"):
            continue
        if any(tok in mid for tok in skip):
            continue
        parts = mid.replace("x_", "", 1).split("_")
        if any(leaf in parts for leaf in leaves):
            out.append(mid)
    return out


def _keeper_job_header(draft: dict[str, Any], *, user_prompt: str = "") -> str | None:
    members = _job_header_model_ids(draft)
    if not members:
        return None
    if len(members) == 1:
        return members[0]
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    return _pick_job_header_keeper(draft, members, prompt)


def ensure_job_header_children_fk(
    draft: dict[str, Any], *, user_prompt: str = ""
) -> list[str]:
    """Deliverables, job costs, and agreements hang off the job header — not only the site."""
    notes: list[str] = []
    keeper = _keeper_job_header(draft, user_prompt=user_prompt)
    if not keeper:
        return notes
    headers = set(_job_header_model_ids(draft))
    from app.ai_domain_density import _AGREEMENT_TOKENS, _EXPENSE_TOKENS, _OUTPUT_TOKENS

    roles: tuple[tuple[str, ...], ...] = (
        ("deliverable", "output") + tuple(_OUTPUT_TOKENS),
        tuple(_EXPENSE_TOKENS),
        tuple(_AGREEMENT_TOKENS),
    )
    seen: set[str] = set()
    by_id = _models_index(draft)
    for leaves in roles:
        for mid in _models_matching_leaves(draft, leaves, skip=_JOB_CHILD_SKIP):
            if mid in headers or mid in seen:
                continue
            model = by_id.get(mid)
            if not model or _has_m2o_to(model, headers):
                continue
            seen.add(mid)
            notes.extend(_ensure_parent_fk(draft, child_id=mid, parent_id=keeper))
    return notes


def _line_primary_parent(
    mid: str, model: dict[str, Any], by_id: dict[str, dict[str, Any]]
) -> str | None:
    if not mid.endswith("_line"):
        return None
    stem = mid[: -len("_line")]
    if stem in by_id:
        return stem
    m2os = [
        str(f.get("relation") or "")
        for f in (model.get("fields") or [])
        if isinstance(f, dict)
        and f.get("ttype") == "many2one"
        and str(f.get("relation") or "").startswith("x_")
        and str(f.get("relation") or "") in by_id
        and not str(f.get("relation") or "").endswith("_line")
    ]
    for rel in m2os:
        if f"{rel}_line" == mid:
            return rel
    return m2os[0] if m2os else None


def _dedupe_o2ms_by_relation(model: dict[str, Any]) -> None:
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    for field in model.get("fields") or []:
        if not isinstance(field, dict):
            continue
        if field.get("ttype") == "one2many":
            rel = str(field.get("relation") or "")
            if rel and rel in seen:
                continue
            if rel:
                seen.add(rel)
        kept.append(field)
    model["fields"] = kept


def collapse_duplicate_line_models(draft: dict[str, Any]) -> list[str]:
    """One header keeps one `*_line` child — `x_rate_line` + `x_rate_card_line` is the same role."""
    notes: list[str] = []
    if draft.get("domain_pack"):
        return notes
    by_id = _models_index(draft)
    groups: dict[str, list[str]] = {}
    for mid, model in by_id.items():
        parent = _line_primary_parent(mid, model, by_id)
        if not parent:
            continue
        groups.setdefault(parent, []).append(mid)
    from app.ai_domain_packs import _purge_draft_artifacts_for_models

    for parent, lines in groups.items():
        unique = sorted(set(lines))
        if len(unique) < 2:
            continue
        canonical = f"{parent}_line"
        keep = canonical if canonical in unique else unique[0]
        doomed_ids = [m for m in unique if m != keep]
        for doomed in doomed_ids:
            by_id = _models_index(draft)
            keep_model = by_id.get(keep)
            src = by_id.get(doomed)
            if not keep_model or not src:
                continue
            keep_names = _field_names(keep_model)
            for field in src.get("fields") or []:
                if not isinstance(field, dict):
                    continue
                fname = str(field.get("name") or "")
                if not fname or fname in keep_names:
                    continue
                rel = str(field.get("relation") or "")
                if field.get("ttype") in {"many2one", "one2many"} and rel in {
                    keep,
                    doomed,
                }:
                    continue
                keep_model.setdefault("fields", []).append(dict(field))
                keep_names.add(fname)
                notes.append(f"app_bar: copied {doomed}.{fname} onto {keep}")
            notes.extend(
                _retarget_removed_relations(
                    draft, {doomed}, extra_fallbacks={doomed: keep}
                )
            )
            _purge_draft_artifacts_for_models(draft, {doomed})
            rewriter = lambda s, old=doomed, new=keep: _rewrite_model_ident(s, old, new)
            skip = {
                "_user_prompt",
                "_domain_briefing",
                "display_name",
                "technical_name",
            }
            for key, value in list(draft.items()):
                if key in skip:
                    continue
                draft[key] = _walk_rename_strings(value, rewriter)
            for model in draft.get("models") or []:
                if isinstance(model, dict):
                    _dedupe_model_fields(model)
                    _dedupe_o2ms_by_relation(model)
            notes.append(f"app_bar: collapsed duplicate line {doomed} → {keep}")
    return notes


def _cost_header_ids(draft: dict[str, Any]) -> list[str]:
    from app.ai_domain_density import _EXPENSE_TOKENS

    return _models_matching_leaves(
        draft, tuple(_EXPENSE_TOKENS), skip=_COST_HEADER_SKIP
    )


def _header_has_lines(draft: dict[str, Any], mid: str) -> bool:
    if _has_line_child(draft, mid):
        return True
    by_id = _models_index(draft)
    for child_id, child in by_id.items():
        if _line_primary_parent(child_id, child, by_id) == mid:
            return True
    return False


def collapse_hollow_cost_headers(draft: dict[str, Any]) -> list[str]:
    """Fold a cost header with no line child into the cost document that has lines.

    Two lined cost documents (expense + job_cost) stay two documents.
    """
    notes: list[str] = []
    if draft.get("domain_pack"):
        return notes
    members = _cost_header_ids(draft)
    if len(members) < 2:
        return notes
    lined = [m for m in members if _header_has_lines(draft, m)]
    hollow = [m for m in members if m not in lined]
    if not lined or not hollow:
        return notes

    def _key(mid: str) -> tuple[int, str]:
        return (-_inbound_m2o_count(draft, mid), mid)

    keep = sorted(lined, key=_key)[0]
    from app.ai_domain_packs import _purge_draft_artifacts_for_models

    for doomed in hollow:
        by_id = _models_index(draft)
        keep_model = by_id.get(keep)
        src = by_id.get(doomed)
        if not keep_model or not src:
            continue
        keep_names = _field_names(keep_model)
        for field in src.get("fields") or []:
            if not isinstance(field, dict):
                continue
            fname = str(field.get("name") or "")
            if not fname or fname in keep_names:
                continue
            rel = str(field.get("relation") or "")
            if field.get("ttype") in {"many2one", "one2many"} and rel in {keep, doomed}:
                continue
            keep_model.setdefault("fields", []).append(dict(field))
            keep_names.add(fname)
            notes.append(f"app_bar: copied {doomed}.{fname} onto {keep}")
        notes.extend(
            _retarget_removed_relations(
                draft, {doomed}, extra_fallbacks={doomed: keep}
            )
        )
        _purge_draft_artifacts_for_models(draft, {doomed})
        rewriter = lambda s, old=doomed, new=keep: _rewrite_model_ident(s, old, new)
        skip = {"_user_prompt", "_domain_briefing", "display_name", "technical_name"}
        for key, value in list(draft.items()):
            if key in skip:
                continue
            draft[key] = _walk_rename_strings(value, rewriter)
        for model in draft.get("models") or []:
            if isinstance(model, dict):
                _dedupe_model_fields(model)
                _dedupe_o2ms_by_relation(model)
        notes.append(f"app_bar: collapsed hollow cost header {doomed} → {keep}")
    return notes


def repair_agreement_party_shape(draft: dict[str, Any]) -> list[str]:
    """A contract is client (res.partner) ↔ at most one party-register M2O — not party↔party."""
    notes: list[str] = []
    if draft.get("domain_pack"):
        return notes
    from app.ai_domain_density import _AGREEMENT_TOKENS

    by_id = _models_index(draft)
    for mid in _models_matching_leaves(draft, tuple(_AGREEMENT_TOKENS), skip=("line",)):
        model = by_id.get(mid)
        if not model:
            continue
        grouped: dict[str, list[dict[str, Any]]] = {}
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "many2one":
                continue
            rel = str(field.get("relation") or "")
            if rel.startswith("x_") and rel in by_id:
                grouped.setdefault(rel, []).append(field)
        for _rel, twins in grouped.items():
            if len(twins) < 2:
                continue
            extras = twins[1:]
            names = _field_names(model)
            has_partner = any(
                isinstance(f, dict)
                and f.get("ttype") == "many2one"
                and str(f.get("relation") or "") == "res.partner"
                for f in (model.get("fields") or [])
            )
            for extra in extras:
                if not has_partner and "x_partner_id" not in names:
                    extra["name"] = "x_partner_id"
                    extra["relation"] = "res.partner"
                    extra["string"] = "Client"
                    names.add("x_partner_id")
                    has_partner = True
                    notes.append(f"app_bar: agreement {mid} Party B → res.partner")
                    continue
                fname = str(extra.get("name") or "")
                model["fields"] = [
                    f
                    for f in (model.get("fields") or [])
                    if not (isinstance(f, dict) and f is extra)
                ]
                notes.append(f"app_bar: dropped duplicate party M2O {mid}.{fname}")
        names = _field_names(model)
        has_partner = any(
            isinstance(f, dict)
            and f.get("ttype") == "many2one"
            and str(f.get("relation") or "") == "res.partner"
            for f in (model.get("fields") or [])
        )
        if not has_partner:
            model.setdefault("fields", []).append(
                {
                    "name": "x_partner_id",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "string": "Client",
                    "source": "odoo_app_bar",
                }
            )
            notes.append(f"app_bar: added {mid}.x_partner_id → res.partner")
    return notes


def relabel_company_fields(draft: dict[str, Any]) -> list[str]:
    """res.company is Company — never the site noun (Studio/Clinic/Facility)."""
    notes: list[str] = []
    by_id = _models_index(draft)
    site_labels = {tok.lower() for tok in _SITE_TOKENS}
    for mid, model in by_id.items():
        if any(tok in mid for tok in _SITE_TOKENS):
            site_labels.add(short_model_label(mid, plural=False).lower())
            desc = str(model.get("description") or "").strip().lower()
            if desc:
                site_labels.add(desc)
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "many2one":
                continue
            if str(field.get("relation") or "") != "res.company":
                continue
            raw = str(field.get("string") or "").strip()
            if not raw or raw.lower() == "company":
                continue
            lowered = raw.lower()
            if lowered in site_labels or any(tok in lowered for tok in _SITE_TOKENS):
                field["string"] = "Company"
                notes.append(
                    f"app_bar: relabeled {model.get('model')}.{field.get('name')} Company"
                )
    return notes


def ensure_asset_usage_line(draft: dict[str, Any]) -> list[str]:
    """Create `{asset}_line` when an equipment catalog and a booking/session exist."""
    notes: list[str] = []
    by_id = _models_index(draft)
    assets = [mid for mid in by_id if _is_asset_catalog(mid)]
    if not assets:
        return notes
    booking = _find_role_model(draft, _BOOKING_TOKENS, skip=("line",))
    if not booking:
        return notes
    if any(
        (mid.endswith("_line") or mid.endswith("_usage"))
        and any(tok in mid for tok in _ASSET_MODEL_TOKENS)
        for mid in by_id
    ):
        return notes
    asset = assets[0]
    line_id = f"{asset}_line"
    if line_id in by_id:
        return notes
    fk_asset = f"x_{asset.replace('x_', '', 1)}_id"
    fk_booking = f"x_{booking.replace('x_', '', 1)}_id"
    asset_label = short_model_label(asset, plural=False)
    booking_label = short_model_label(booking, plural=False)
    line = {
        "model": line_id,
        "description": f"{asset_label} Line",
        "mode": "new",
        "source": "odoo_app_bar",
        "fields": [
            {"name": "x_name", "ttype": "char", "string": "Line", "required": True},
            {
                "name": fk_asset,
                "ttype": "many2one",
                "relation": asset,
                "string": asset_label,
                "required": True,
            },
            {
                "name": fk_booking,
                "ttype": "many2one",
                "relation": booking,
                "string": booking_label,
            },
            {"name": "x_qty", "ttype": "float", "string": "Quantity", "default": 1.0},
            {"name": "x_notes", "ttype": "text", "string": "Notes"},
        ],
    }
    draft.setdefault("models", []).append(line)
    booking_model = _models_index(draft).get(booking)
    if booking_model:
        o2m = f"x_{line_id.replace('x_', '')}_ids"
        if o2m not in _field_names(booking_model):
            booking_model.setdefault("fields", []).append(
                {
                    "name": o2m,
                    "ttype": "one2many",
                    "relation": line_id,
                    "relation_field": fk_booking,
                    "string": "Lines",
                    "source": "odoo_app_bar",
                }
            )
    notes.append(f"app_bar: added asset usage line {line_id}")
    return notes


def ensure_asset_line_on_booking(draft: dict[str, Any]) -> list[str]:
    """Equipment/asset usage lines also belong on the booking/session, not only the catalog."""
    notes: list[str] = []
    booking = _find_role_model(draft, _BOOKING_TOKENS, skip=("line",))
    if not booking:
        return notes
    by_id = _models_index(draft)
    for mid in by_id:
        if not mid.endswith("_line"):
            continue
        parent = mid[: -len("_line")]
        if parent not in by_id:
            continue
        if not any(tok in parent for tok in _ASSET_LINE_PARENT_TOKENS):
            continue
        notes.extend(_ensure_parent_fk(draft, child_id=mid, parent_id=booking))
    return notes


def _fold_model_into(draft: dict[str, Any], doomed: str, keep: str, *, reason: str) -> list[str]:
    """Copy unique fields from doomed onto keep, retarget FKs, purge doomed."""
    notes: list[str] = []
    by_id = _models_index(draft)
    keep_model = by_id.get(keep)
    src = by_id.get(doomed)
    if not keep_model or not src:
        return notes
    from app.ai_domain_packs import _purge_draft_artifacts_for_models

    keep_names = _field_names(keep_model)
    for field in src.get("fields") or []:
        if not isinstance(field, dict):
            continue
        fname = str(field.get("name") or "")
        if not fname or fname in keep_names:
            continue
        rel = str(field.get("relation") or "")
        if field.get("ttype") in {"many2one", "one2many"} and rel in {keep, doomed}:
            continue
        copied = dict(field)
        # Copied extras were optional on the doomed register; required on the
        # keeper's line would block booking/catalog creates (usage_date, hours).
        copied.pop("required", None)
        keep_model.setdefault("fields", []).append(copied)
        keep_names.add(fname)
        notes.append(f"app_bar: copied {doomed}.{fname} onto {keep}")
    notes.extend(
        _retarget_removed_relations(draft, {doomed}, extra_fallbacks={doomed: keep})
    )
    _purge_draft_artifacts_for_models(draft, {doomed})
    rewriter = lambda s, old=doomed, new=keep: _rewrite_model_ident(s, old, new)
    skip = {
        "_user_prompt",
        "_domain_briefing",
        "display_name",
        "technical_name",
    }
    for key, value in list(draft.items()):
        if key in skip:
            continue
        draft[key] = _walk_rename_strings(value, rewriter)
    for model in draft.get("models") or []:
        if isinstance(model, dict):
            _dedupe_model_fields(model)
            _dedupe_o2ms_by_relation(model)
    notes.append(f"app_bar: {reason} {doomed} → {keep}")
    return notes


def collapse_parallel_asset_usage(draft: dict[str, Any]) -> list[str]:
    """Keep `{asset}_line` (booking-parented). Fold a parallel `{asset}_usage` into it.

    Domain-agnostic: any catalog matching `_ASSET_MODEL_TOKENS`.
    """
    notes: list[str] = []
    if draft.get("domain_pack"):
        return notes
    by_id = _models_index(draft)
    for mid in list(by_id):
        if not mid.endswith("_usage"):
            continue
        stem = mid[: -len("_usage")]
        if not any(tok in stem for tok in _ASSET_MODEL_TOKENS):
            continue
        if stem not in by_id:
            continue
        keep = f"{stem}_line"
        if keep not in by_id:
            notes.extend(rename_custom_model(draft, mid, keep))
            continue
        notes.extend(
            _fold_model_into(
                draft, mid, keep, reason="collapsed parallel asset usage"
            )
        )
    return notes


def _is_uom_register_model(mid: str) -> bool:
    if not str(mid).startswith("x_") or str(mid).endswith("_line"):
        return False
    return any(str(mid).endswith(suf) for suf in _UOM_REGISTER_SUFFIXES)


def _is_rate_card_model(mid: str) -> bool:
    if not str(mid).startswith("x_") or str(mid).endswith("_line"):
        return False
    if _is_uom_register_model(mid):
        return False
    return any(tok in str(mid) for tok in _RATE_CARD_TOKENS)


def _selection_key_set(field: dict[str, Any]) -> frozenset[str]:
    from app.ai_selection import parse_selection_literal

    pairs = parse_selection_literal(field.get("selection")) or []
    return frozenset(str(k).lower() for k, _ in pairs if k)


def _model_has_uom_selection(model: dict[str, Any]) -> bool:
    for field in model.get("fields") or []:
        if not isinstance(field, dict) or field.get("ttype") != "selection":
            continue
        name = str(field.get("name") or "")
        if name in _UOM_SELECTION_NAMES:
            return True
        if name in _DROP_SELECTION_ALIAS and _selection_key_set(field) & _UOM_KEY_HINTS:
            return True
    return False


def collapse_redundant_uom_register(draft: dict[str, Any]) -> list[str]:
    """Fold a unit/uom register into a rate card that already stores UOM as a selection.

    Distinct from merging two lined cost/rate documents. Skip when the unit
    model has its own ``*_line`` child.
    """
    notes: list[str] = []
    if draft.get("domain_pack"):
        return notes
    by_id = _models_index(draft)
    cards = [mid for mid in by_id if _is_rate_card_model(mid)]
    units = [mid for mid in by_id if _is_uom_register_model(mid)]
    if not cards or not units:
        return notes
    keep = next((c for c in cards if _model_has_uom_selection(by_id[c])), None)
    if not keep:
        return notes
    for doomed in units:
        if doomed == keep:
            continue
        if f"{doomed}_line" in by_id:
            continue
        notes.extend(
            _fold_model_into(
                draft, doomed, keep, reason="collapsed redundant UOM register"
            )
        )
    return notes


def drop_duplicate_identical_selections(draft: dict[str, Any]) -> list[str]:
    """One model must not carry two selection fields with the same option keys.

    Prefer ``x_rate_unit`` / ``x_uom`` over ``x_rate_type``. Never drop ``x_status``.
    """
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        groups: dict[frozenset[str], list[dict[str, Any]]] = {}
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "selection":
                continue
            name = str(field.get("name") or "")
            if not name or name in _KEEP_SELECTION_NAMES:
                continue
            keys = _selection_key_set(field)
            if len(keys) < 2:
                continue
            groups.setdefault(keys, []).append(field)
        drop_names: set[str] = set()
        for fields in groups.values():
            if len(fields) < 2:
                continue
            names = [str(f.get("name") or "") for f in fields]
            keep_name = next((n for n in names if n in _UOM_SELECTION_NAMES), None)
            if keep_name is None:
                keep_name = next(
                    (n for n in names if n not in _DROP_SELECTION_ALIAS), names[0]
                )
            for name in names:
                if name != keep_name:
                    drop_names.add(name)
        if not drop_names:
            continue
        model["fields"] = [
            f
            for f in (model.get("fields") or [])
            if not (isinstance(f, dict) and str(f.get("name") or "") in drop_names)
        ]
        for name in sorted(drop_names):
            notes.append(f"app_bar: dropped duplicate selection {mid}.{name}")
    return notes


def relax_copied_asset_line_requireds(draft: dict[str, Any]) -> list[str]:
    """Usage extras on an asset line must not be required (catalog/booking FKs stay)."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        if not mid.endswith("_line"):
            continue
        stem = mid[: -len("_line")]
        if stem not in by_id:
            continue
        if not any(tok in stem for tok in _ASSET_LINE_PARENT_TOKENS):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or not field.get("required"):
                continue
            fname = str(field.get("name") or "")
            ttype = str(field.get("ttype") or "")
            if fname in _COPIED_USAGE_FIELD_NAMES or ttype in {"date", "datetime"}:
                field.pop("required", None)
                notes.append(f"app_bar: dropped required on copied {mid}.{fname}")
    return notes


_LINED_HEADER_SCALAR_RATES = frozenset(
    {"x_rate", "x_price", "x_unit_price", "x_list_price"}
)


def relax_lined_header_rate_requireds(draft: dict[str, Any]) -> list[str]:
    """A lined cost/job header must not require a scalar rate beside line amounts."""
    notes: list[str] = []
    by_id = _models_index(draft)
    cost_ids = set(_cost_header_ids(draft))
    for mid, model in by_id.items():
        if mid.endswith("_line"):
            continue
        if not _header_has_lines(draft, mid):
            continue
        if not (_looks_like_header(model) or mid in cost_ids):
            continue
        line = by_id.get(f"{mid}_line") or {}
        line_totals = _field_names(line) & {"x_amount", "x_subtotal", "x_total"}
        header_totals = _field_names(model) & {
            "x_amount",
            "x_amount_total",
            "x_total",
            "x_total_cost",
            "x_subtotal",
        }
        if not line_totals and not header_totals:
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or not field.get("required"):
                continue
            fname = str(field.get("name") or "")
            ttype = str(field.get("ttype") or "")
            if fname in _LINED_HEADER_SCALAR_RATES or (
                fname in header_totals and ttype in {"float", "monetary", "integer"}
            ):
                field.pop("required", None)
                notes.append(f"app_bar: dropped required on lined header {mid}.{fname}")
    return notes


def drop_parent_m2o_when_child_o2m_exists(draft: dict[str, Any]) -> list[str]:
    """A parent that already O2Ms a child register must not also M2O one child.

    Mutual M2O (artist ↔ party_role) keeps the FK on the child register.
    """
    notes: list[str] = []
    child_leaves = ("role", "type", "category", "tag", "uom", "reason")
    by_id = _models_index(draft)

    def _is_child_register(mid: str) -> bool:
        parts = mid.replace("x_", "", 1).split("_")
        return any(p in child_leaves for p in parts)

    for mid, model in by_id.items():
        o2m_rels = {
            str(f.get("relation") or "")
            for f in (model.get("fields") or [])
            if isinstance(f, dict)
            and f.get("ttype") == "one2many"
            and str(f.get("relation") or "").startswith("x_")
        }
        if not o2m_rels:
            continue
        kept: list[dict[str, Any]] = []
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            rel = str(field.get("relation") or "")
            if (
                field.get("ttype") == "many2one"
                and rel in o2m_rels
                and _is_child_register(rel)
                and not _is_child_register(mid)
            ):
                notes.append(
                    f"app_bar: dropped circular M2O {mid}.{field.get('name')} "
                    f"(O2M already parents {rel})"
                )
                continue
            kept.append(field)
        model["fields"] = kept
    return notes


def trim_line_extra_parents(draft: dict[str, Any]) -> list[str]:
    """Keep catalog+booking on asset usage lines; drop extra in-spec parents (rate card, …).

    Other `*_line` models keep the prefix header, or the booking when the prefix
    catalog was pruned. Register parents (rate unit/card) are not line headers.
    """
    notes: list[str] = []
    by_id = _models_index(draft)
    booking = _find_role_model(draft, _BOOKING_TOKENS, skip=("line",))
    for mid, model in list(by_id.items()):
        if not mid.endswith("_line"):
            continue
        stem = mid[: -len("_line")]
        allowed: set[str] = set()
        is_asset_line = any(tok in stem for tok in _ASSET_LINE_PARENT_TOKENS)
        stem_leaf = stem.replace("x_", "", 1)
        crew_orphan = stem not in by_id and any(
            tok == stem_leaf or stem_leaf.endswith(tok)
            for tok in ("crew", "staff", "employee")
        )
        if is_asset_line and stem in by_id:
            allowed.add(stem)
            if booking:
                allowed.add(booking)
        elif crew_orphan and booking:
            allowed.add(booking)
        else:
            primary = stem if stem in by_id else _line_primary_parent(mid, model, by_id)
            if primary:
                allowed.add(primary)
        if not allowed:
            continue
        dropped_names: set[str] = set()
        drop_rels: set[str] = set()
        kept: list[dict[str, Any]] = []
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                kept.append(field)
                continue
            rel = str(field.get("relation") or "")
            if (
                field.get("ttype") == "many2one"
                and rel.startswith("x_")
                and rel in by_id
                and not rel.endswith("_line")
                and rel not in allowed
            ):
                dropped_names.add(str(field.get("name") or ""))
                drop_rels.add(rel)
                notes.append(
                    f"app_bar: dropped extra line parent {mid}.{field.get('name')} → {rel}"
                )
                continue
            kept.append(field)
        kept2: list[dict[str, Any]] = []
        for field in kept:
            related = str(field.get("related") or "").strip()
            hop = related.split(".")[0] if related else ""
            if hop and hop in dropped_names:
                notes.append(
                    f"app_bar: dropped {mid}.{field.get('name')} "
                    f"(related hop {hop} removed)"
                )
                continue
            kept2.append(field)
        model["fields"] = kept2
        if booking in allowed:
            notes.extend(
                _ensure_parent_fk(draft, child_id=mid, parent_id=booking)
            )
        for rel in drop_rels:
            parent = by_id.get(rel)
            if not parent:
                continue
            parent["fields"] = [
                f
                for f in (parent.get("fields") or [])
                if not (
                    isinstance(f, dict)
                    and f.get("ttype") == "one2many"
                    and str(f.get("relation") or "") == mid
                )
            ]
        buttons = draft.get("smart_buttons")
        if isinstance(buttons, list) and drop_rels:
            draft["smart_buttons"] = [
                b
                for b in buttons
                if not (
                    isinstance(b, dict)
                    and str(b.get("related_model") or "") == mid
                    and str(b.get("on_model") or "") in drop_rels
                )
            ]
        leftover_sel = {
            str(f.get("name") or "")
            for f in (model.get("fields") or [])
            if isinstance(f, dict)
            and f.get("ttype") == "selection"
            and "specialty" in str(f.get("name") or "")
        }
        if "x_site_specialty" in leftover_sel and (
            "x_specialty" in leftover_sel or "x_type" in _field_names(model)
        ):
            model["fields"] = [
                f
                for f in (model.get("fields") or [])
                if not (
                    isinstance(f, dict)
                    and str(f.get("name") or "") == "x_site_specialty"
                )
            ]
            notes.append(f"app_bar: dropped leftover x_site_specialty on {mid}")
    notes.extend(_collapse_same_relation_parent_m2os(draft))
    return notes


def _collapse_same_relation_parent_m2os(draft: dict[str, Any]) -> list[str]:
    """Keep one M2O per in-spec parent on a line (x_inventory_count_id vs x_count_id)."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        if not mid.endswith("_line"):
            continue
        by_rel: dict[str, list[dict[str, Any]]] = {}
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "many2one":
                continue
            rel = str(field.get("relation") or "")
            if rel.startswith("x_") and rel in by_id and not rel.endswith("_line"):
                by_rel.setdefault(rel, []).append(field)
        rename_to: dict[str, str] = {}
        drop_names: set[str] = set()
        for rel, fields_for_rel in by_rel.items():
            if len(fields_for_rel) < 2:
                continue
            preferred = f"x_{rel.replace('x_', '', 1)}_id"
            keeper = next(
                (f for f in fields_for_rel if str(f.get("name") or "") == preferred),
                fields_for_rel[0],
            )
            keeper_name = str(keeper.get("name") or "")
            for field in fields_for_rel:
                name = str(field.get("name") or "")
                if name and name != keeper_name:
                    drop_names.add(name)
                    rename_to[name] = keeper_name
                    notes.append(
                        f"app_bar: collapsed duplicate parent {mid}.{name} into {keeper_name}"
                    )
        if not drop_names:
            continue
        model["fields"] = [
            f
            for f in (model.get("fields") or [])
            if not (isinstance(f, dict) and str(f.get("name") or "") in drop_names)
        ]
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            related = str(field.get("related") or "").strip()
            hop = related.split(".")[0] if related else ""
            if hop in rename_to:
                field["related"] = related.replace(hop, rename_to[hop], 1)
        for parent in by_id.values():
            for field in parent.get("fields") or []:
                if (
                    isinstance(field, dict)
                    and field.get("ttype") == "one2many"
                    and str(field.get("relation") or "") == mid
                    and str(field.get("relation_field") or "") in rename_to
                ):
                    field["relation_field"] = rename_to[str(field.get("relation_field"))]
        for button in draft.get("smart_buttons") or []:
            if (
                isinstance(button, dict)
                and str(button.get("related_model") or "") == mid
                and str(button.get("relation_field") or "") in rename_to
            ):
                button["relation_field"] = rename_to[str(button.get("relation_field"))]
        for view in draft.get("views") or []:
            if not isinstance(view, dict):
                continue
            arch = str(view.get("arch") or "")
            if not arch:
                continue
            for old, new in rename_to.items():
                arch = _rewrite_field_ident(arch, old, new)
            view["arch"] = arch
    return notes


def drop_self_relations(draft: dict[str, Any]) -> list[str]:
    """A model must not M2O/O2M itself (rate unit → rate unit)."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        kept: list[dict[str, Any]] = []
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                kept.append(field)
                continue
            rel = str(field.get("relation") or "")
            if field.get("ttype") in {"many2one", "one2many"} and rel == mid:
                notes.append(
                    f"app_bar: dropped self-relation {mid}.{field.get('name')}"
                )
                continue
            kept.append(field)
        model["fields"] = kept
    buttons = draft.get("smart_buttons")
    if isinstance(buttons, list):
        draft["smart_buttons"] = [
            b
            for b in buttons
            if not (
                isinstance(b, dict)
                and str(b.get("on_model") or "") == str(b.get("related_model") or "")
            )
        ]
    return notes


def drop_purchase_on_booking_headers(draft: dict[str, Any]) -> list[str]:
    """purchase.order belongs on a cost/job document, not a booking/session."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        if mid.endswith("_line"):
            continue
        if not any(tok in mid for tok in _BOOKING_TOKENS):
            continue
        kept: list[dict[str, Any]] = []
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if (
                field.get("ttype") == "many2one"
                and str(field.get("relation") or "") == "purchase.order"
            ):
                notes.append(
                    f"app_bar: dropped purchase.order on booking {mid}.{field.get('name')}"
                )
                continue
            kept.append(field)
        model["fields"] = kept
    return notes


def fix_workflow_default_to_initial(draft: dict[str, Any]) -> list[str]:
    """Document default must be an initial state (draft/new), not active/scheduled."""
    notes: list[str] = []
    from app.ai_selection import parse_selection_literal
    from app.ai_workflow_semantic import _INITIAL_STATES

    for model in draft.get("models") or []:
        if not isinstance(model, dict) or not model.get("is_workflow"):
            continue
        sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
        fname = str(sf.get("field") or "x_status")
        status = next(
            (
                f
                for f in (model.get("fields") or [])
                if isinstance(f, dict) and str(f.get("name") or "") == fname
            ),
            None,
        )
        if not status:
            continue
        keys = [k for k, _ in (parse_selection_literal(status.get("selection")) or [])]
        visible = [
            str(s)
            for s in (sf.get("statusbar_visible") or keys)
            if str(s) in set(keys) or not keys
        ]
        if not visible:
            visible = keys
        initial = [k for k in visible if k.lower() in _INITIAL_STATES]
        if not initial:
            initial = [k for k in keys if k.lower() in _INITIAL_STATES]
        if not initial:
            continue
        want = initial[0]
        default = status.get("default")
        if isinstance(default, str) and default.lower() in _INITIAL_STATES:
            continue
        if default == want:
            continue
        status["default"] = want
        mid = str(model.get("model") or "")
        notes.append(f"app_bar: {mid}.{fname} default {default!r} → {want}")
    return notes


def strip_party_register_sellables(draft: dict[str, Any]) -> list[str]:
    """Party registers are not CRM leads or rate cards."""
    notes: list[str] = []
    if draft.get("domain_pack"):
        return notes
    from app.ai_domain_density import _PARTY_TOKENS, _RATE_TOKENS

    by_id = _models_index(draft)
    has_rate_card = any(
        any(tok in mid for tok in _RATE_TOKENS) for mid in by_id if not mid.endswith("_line")
    )
    for mid, model in by_id.items():
        if mid.endswith("_line"):
            continue
        if not any(tok in mid for tok in _PARTY_TOKENS) and "_role" not in mid:
            continue
        drop = set(_CRM_PARTY_FIELDS)
        if has_rate_card:
            drop |= _PARTY_RATE_FIELDS
        before = len(model.get("fields") or [])
        model["fields"] = [
            f
            for f in (model.get("fields") or [])
            if not (isinstance(f, dict) and str(f.get("name") or "") in drop)
        ]
        removed = before - len(model.get("fields") or [])
        if removed:
            notes.append(f"app_bar: stripped CRM/rate fields from party {mid}")
    return notes


def reconcile_stale_o2ms(draft: dict[str, Any]) -> list[str]:
    """Drop reverse O2Ms whose child FK no longer points at this parent."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        kept: list[dict[str, Any]] = []
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if field.get("ttype") != "one2many":
                kept.append(field)
                continue
            child_id = str(field.get("relation") or "")
            inverse = str(field.get("relation_field") or "")
            child = by_id.get(child_id)
            if not child or not inverse:
                kept.append(field)
                continue
            child_fk = next(
                (
                    f
                    for f in (child.get("fields") or [])
                    if isinstance(f, dict) and str(f.get("name") or "") == inverse
                ),
                None,
            )
            if not child_fk:
                notes.append(
                    f"app_bar: dropped O2M {mid}.{field.get('name')} "
                    f"(missing inverse {child_id}.{inverse})"
                )
                continue
            if (
                child_fk.get("ttype") == "many2one"
                and str(child_fk.get("relation") or "") != mid
            ):
                notes.append(
                    f"app_bar: dropped stale O2M {mid}.{field.get('name')} "
                    f"(child {inverse} → {child_fk.get('relation')})"
                )
                continue
            kept.append(field)
        model["fields"] = kept
    return notes


def repair_partner_smart_button_targets(draft: dict[str, Any]) -> list[str]:
    """Contacts button_box FKs must actually point at res.partner."""
    notes: list[str] = []
    buttons = draft.get("smart_buttons")
    if not isinstance(buttons, list):
        return notes
    by_id = _models_index(draft)
    kept: list[dict[str, Any]] = []
    for btn in buttons:
        if not isinstance(btn, dict) or str(btn.get("on_model") or "") != "res.partner":
            kept.append(btn)
            continue
        rel_model = str(btn.get("related_model") or "")
        fk_name = str(btn.get("relation_field") or "")
        target = by_id.get(rel_model)
        field = next(
            (
                f
                for f in ((target or {}).get("fields") or [])
                if isinstance(f, dict) and str(f.get("name") or "") == fk_name
            ),
            None,
        )
        if (
            field
            and field.get("ttype") == "many2one"
            and str(field.get("relation") or "") == "res.partner"
        ):
            kept.append(btn)
            continue
        notes.append(
            f"app_bar: dropped invalid Contacts button {rel_model}.{fk_name}"
        )
    draft["smart_buttons"] = kept
    return notes


_XML_ID_PREFIXES = (
    "rule",
    "action",
    "menu",
    "view",
    "model",
    "access",
    "seq",
    "sequence",
)


def _replace_ident(text: str, src: str, dst: str) -> str:
    """Replace an Odoo identifier without rewriting a longer id that contains it."""
    if not text or not src or src == dst:
        return text
    return re.sub(
        rf"(?<![A-Za-z0-9_]){re.escape(src)}(?![A-Za-z0-9_])",
        dst,
        text,
    )


def _rewrite_xml_prefixed_ident(text: str, old_id: str, new_id: str) -> str:
    """Rewrite ``rule_x_foo_multi_company`` when folding ``x_foo`` → ``x_bar``.

    Word-boundary replace misses these: the char before ``x_`` is ``_``.
    Do not rewrite a longer model (``rule_x_foo_line_…`` stays when old_id is ``x_foo``).
    """
    if not text or old_id == new_id:
        return text
    out = text
    # After old_id: end, or ``_`` not starting a ``line`` segment.
    tail = r"(?=$|_(?!line(?:_|$)))"
    for prefix in _XML_ID_PREFIXES:
        out = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(prefix)}_{re.escape(old_id)}{tail}",
            f"{prefix}_{new_id}",
            out,
        )
    return out


def _rewrite_model_ident(text: str, old_id: str, new_id: str) -> str:
    """Longest-first identifier rewrite so x_site_id becomes x_studio_id, not x_studio_id leftover."""
    if not text or old_id == new_id:
        return text
    old_leaf = old_id.replace("x_", "", 1)
    new_leaf = new_id.replace("x_", "", 1)
    old_xml = old_id.replace(".", "_")
    new_xml = new_id.replace(".", "_")
    out = text
    for src, dst in (
        (f"x_{old_leaf}_ids", f"x_{new_leaf}_ids"),
        (f"x_{old_leaf}_id", f"x_{new_leaf}_id"),
        (f"model_{old_xml}", f"model_{new_xml}"),
        (old_id, new_id),
    ):
        out = _replace_ident(out, src, dst)
    return _rewrite_xml_prefixed_ident(out, old_id, new_id)


def _walk_rename_strings(obj: Any, rewriter) -> Any:
    if isinstance(obj, dict):
        return {k: _walk_rename_strings(v, rewriter) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_rename_strings(v, rewriter) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_walk_rename_strings(v, rewriter) for v in obj)
    if isinstance(obj, str):
        return rewriter(obj)
    return obj


def rename_custom_model(draft: dict[str, Any], old_id: str, new_id: str) -> list[str]:
    """Rename an x_* model and every FK/UI/ACL reference (prompt studio ≠ LLM x_site)."""
    if not old_id or not new_id or old_id == new_id:
        return []
    by_id = _models_index(draft)
    if old_id not in by_id or new_id in by_id:
        return []
    rewriter = lambda s: _rewrite_model_ident(s, old_id, new_id)
    skip = {"_user_prompt", "_domain_briefing", "display_name", "technical_name"}
    for key, value in list(draft.items()):
        if key in skip:
            continue
        draft[key] = _walk_rename_strings(value, rewriter)
    new_leaf = new_id.replace("x_", "", 1)
    for model in draft.get("models") or []:
        if isinstance(model, dict) and str(model.get("model") or "") == new_id:
            desc = str(model.get("description") or "")
            if desc.lower() in {"site", "party", "location", old_id.replace("x_", "").replace("_", " ")}:
                model["description"] = new_leaf.replace("_", " ").title()
            break
    return [f"app_bar: renamed {old_id} → {new_id}"]


def prefer_prompt_model_names(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """Prefer prompt nouns (studio/artist) over generic LLM names (site/party)."""
    notes: list[str] = []
    if draft.get("domain_pack"):
        return notes
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    if not prompt.strip():
        return notes
    from app.ai_domain_density import _PARTY_TOKENS, _SITE_TOKENS, _prompt_token_hit
    from app.ai_domain_packs import _purge_draft_artifacts_for_models

    by_id = _models_index(draft)

    def _prefer(wanted: str | None, generic_leaves: frozenset[str]) -> None:
        nonlocal notes
        if not wanted:
            return
        dest = f"x_{wanted}"
        generics = [
            mid
            for mid in by_id
            if mid.replace("x_", "", 1) in generic_leaves
        ]
        if dest in _models_index(draft):
            leftover = [m for m in generics if m != dest]
            if leftover:
                removed = set(leftover)
                notes.extend(_retarget_removed_relations(draft, removed, extra_fallbacks={m: dest for m in leftover}))
                _purge_draft_artifacts_for_models(draft, removed)
                notes.append(f"app_bar: dropped generic {', '.join(sorted(leftover))} in favor of {dest}")
            return
        if generics:
            notes.extend(rename_custom_model(draft, generics[0], dest))

    _prefer(_prompt_token_hit(prompt, _SITE_TOKENS), _GENERIC_SITE_LEAVES)
    by_id = _models_index(draft)
    _prefer(_prompt_token_hit(prompt, _PARTY_TOKENS), _GENERIC_PARTY_LEAVES)
    return notes


def demote_line_model_workflows(draft: dict[str, Any]) -> list[str]:
    """sale.order.line is not a document header — no Confirm/Done on *_line."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.endswith("_line"):
            continue
        if model.get("is_workflow") or model.get("state_field"):
            model["is_workflow"] = False
            model.pop("state_field", None)
            notes.append(f"app_bar: demoted line workflow on {mid}")
    return notes


def drop_orphan_line_models(draft: dict[str, Any]) -> list[str]:
    """Drop *_line models that still have no parent header after link repair."""
    notes: list[str] = []
    by_id = _models_index(draft)
    removed: set[str] = set()
    for mid, model in by_id.items():
        if not mid.endswith("_line"):
            continue
        has_parent = any(
            isinstance(f, dict)
            and f.get("ttype") == "many2one"
            and str(f.get("relation") or "") in by_id
            and not str(f.get("relation") or "").endswith("_line")
            for f in (model.get("fields") or [])
        )
        if not has_parent:
            removed.add(mid)
    if not removed:
        return notes
    from app.ai_domain_packs import _purge_draft_artifacts_for_models

    notes.extend(_retarget_removed_relations(draft, removed))
    _purge_draft_artifacts_for_models(draft, removed)
    notes.append(f"app_bar: dropped orphan line model(s) {', '.join(sorted(removed))}")
    return notes


def drop_ghost_menus_and_actions(draft: dict[str, Any]) -> list[str]:
    """Menus whose action/model was pruned (deposit/crew/invoice) must not linger."""
    notes: list[str] = []
    known = set(_models_index(draft))
    actions = [a for a in (draft.get("actions") or []) if isinstance(a, dict)]
    kept_actions: list[dict[str, Any]] = []
    for action in actions:
        mid = str(action.get("model") or "")
        if mid.startswith("x_") and mid not in known:
            notes.append(
                f"app_bar: dropped ghost action {action.get('technical_name')} ({mid})"
            )
            continue
        kept_actions.append(action)
    if len(kept_actions) != len(actions):
        draft["actions"] = kept_actions
    known_xml = {str(a.get("technical_name") or "") for a in kept_actions}
    menus = draft.get("menus")
    if not isinstance(menus, list):
        return notes
    kept_menus: list[dict[str, Any]] = []
    for menu in menus:
        if not isinstance(menu, dict):
            continue
        xml = str(menu.get("action_xml_id") or "")
        if xml and xml not in known_xml:
            notes.append(f"app_bar: dropped ghost menu {menu.get('technical_name')}")
            continue
        kept_menus.append(menu)
    draft["menus"] = kept_menus
    return notes


def _rewrite_field_ident(text: str, old_name: str, new_name: str) -> str:
    if not text or old_name == new_name:
        return text
    return _replace_ident(text, old_name, new_name)


def _drop_field_nodes(arch: str, names: set[str]) -> str:
    out = arch
    for name in names:
        out = re.sub(
            rf'<field\b[^>]*\bname="{re.escape(name)}"[^>]*/>',
            "",
            out,
            flags=re.I,
        )
        out = re.sub(
            rf'<field\b[^>]*\bname="{re.escape(name)}"[^>]*>\s*</field>',
            "",
            out,
            flags=re.I,
        )
        out = re.sub(
            rf'<filter\b[^>]*\bname="group_{re.escape(name)}"[^>]*/>',
            "",
            out,
            flags=re.I,
        )
    return out


def _drop_named_fields(draft: dict[str, Any], model_id: str, drop: set[str]) -> None:
    if not drop:
        return
    by_id = _models_index(draft)
    model = by_id.get(model_id)
    if model:
        model["fields"] = [
            f
            for f in (model.get("fields") or [])
            if not (isinstance(f, dict) and str(f.get("name") or "") in drop)
        ]
    for view in draft.get("views") or []:
        if not isinstance(view, dict):
            continue
        if str(view.get("model") or "") != model_id:
            continue
        view["arch"] = _drop_field_nodes(str(view.get("arch") or ""), drop)
    for other in draft.get("models") or []:
        if not isinstance(other, dict):
            continue
        kept: list[dict[str, Any]] = []
        for field in other.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if (
                field.get("ttype") == "one2many"
                and str(field.get("relation_field") or "") in drop
                and str(field.get("relation") or "") == model_id
            ):
                continue
            kept.append(field)
        other["fields"] = kept
    buttons = draft.get("smart_buttons")
    if isinstance(buttons, list):
        draft["smart_buttons"] = [
            b
            for b in buttons
            if not (
                isinstance(b, dict)
                and str(b.get("related_model") or "") == model_id
                and str(b.get("relation_field") or "") in drop
            )
        ]


def rewrite_foreign_lexicon_fks(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """x_matter_id → x_engagement_id when the prompt is not a law firm."""
    notes: list[str] = []
    if "law" in str(draft.get("domain_pack") or ""):
        return notes
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    if re.search(r"\b(matter|hearing|law firm|attorney|solicitor)\b", prompt, re.I):
        return notes
    skip = {"_user_prompt", "_domain_briefing", "display_name", "technical_name"}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        names = _field_names(model)
        for field in list(model.get("fields") or []):
            if not isinstance(field, dict) or field.get("ttype") != "many2one":
                continue
            fname = str(field.get("name") or "")
            match = re.match(r"^x_(.+)_id$", fname)
            if not match:
                continue
            leaf = match.group(1)
            if leaf not in _FOREIGN_FK_LEAVES:
                continue
            rel = str(field.get("relation") or "")
            if not rel.startswith("x_") or rel == f"x_{leaf}":
                continue
            new_name = f"x_{rel.replace('x_', '', 1)}_id"
            if new_name == fname:
                continue
            if new_name in names:
                _drop_named_fields(draft, mid, {fname})
                names.discard(fname)
                notes.append(f"app_bar: dropped duplicate foreign FK {mid}.{fname}")
                continue
            rewriter = lambda s, old=fname, new=new_name: _rewrite_field_ident(s, old, new)
            for key, value in list(draft.items()):
                if key in skip:
                    continue
                draft[key] = _walk_rename_strings(value, rewriter)
            field["name"] = new_name
            field["string"] = short_model_label(rel, plural=False)
            names.add(new_name)
            names.discard(fname)
            notes.append(f"app_bar: renamed {mid}.{fname} → {new_name}")
    return notes


def drop_foreign_role_fields(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """Drop attorney/solicitor FKs unless the prompt is actually a law firm."""
    notes: list[str] = []
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    if _prompt_keeps_legal_matter(draft, prompt):
        return notes
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        drop: set[str] = set()
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "many2one":
                continue
            fname = str(field.get("name") or "")
            match = re.match(r"^x_(.+)_id$", fname)
            if not match:
                continue
            if match.group(1) in _FOREIGN_ROLE_LEAVES:
                drop.add(fname)
        if not drop:
            continue
        _drop_named_fields(draft, mid, drop)
        notes.append(
            f"app_bar: dropped foreign role FK(s) {mid}.{', '.join(sorted(drop))}"
        )
    return notes


def collapse_typed_asset_foreign_keys(draft: dict[str, Any]) -> list[str]:
    """Drop exploded x_console_id / x_microphone_id FKs; gear belongs on equipment lines."""
    notes: list[str] = []
    by_id = _models_index(draft)
    assets = [mid for mid in by_id if _is_asset_catalog(mid)]
    if not assets:
        return notes
    type_leaves = set(_DEFAULT_ASSET_TYPE_LEAVES)
    brief = draft.get("_domain_briefing")
    if isinstance(brief, dict):
        for pair in brief.get("equipment_types") or []:
            if isinstance(pair, (list, tuple)) and pair:
                type_leaves.add(str(pair[0]))
    has_asset_lines = any(
        mid.endswith("_line") and any(tok in mid for tok in _ASSET_MODEL_TOKENS)
        for mid in by_id
    )
    for mid, model in list(by_id.items()):
        if mid in assets or mid.endswith("_line"):
            continue
        typed: list[str] = []
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "many2one":
                continue
            rel = str(field.get("relation") or "")
            if rel not in assets:
                continue
            match = re.match(r"^x_(.+)_id$", str(field.get("name") or ""))
            if match and match.group(1) in type_leaves:
                typed.append(str(field.get("name")))
        if len(typed) < 2:
            continue
        _drop_named_fields(draft, mid, set(typed))
        notes.append(
            f"app_bar: collapsed {len(typed)} typed {assets[0]} FKs on {mid}"
        )
        if has_asset_lines:
            continue
        keep = f"x_{assets[0].replace('x_', '', 1)}_id"
        if keep in _field_names(model):
            continue
        model.setdefault("fields", []).append(
            {
                "name": keep,
                "ttype": "many2one",
                "relation": assets[0],
                "string": short_model_label(assets[0], plural=False),
                "source": "odoo_app_bar",
            }
        )
        notes.append(f"app_bar: kept single {mid}.{keep} → {assets[0]}")
    return notes


def ensure_o2m_inverse_fields(draft: dict[str, Any]) -> list[str]:
    """Parent O2M relation_field must exist as a M2O on the child."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "one2many":
                continue
            child_id = str(field.get("relation") or "")
            inverse = str(field.get("relation_field") or "")
            child = by_id.get(child_id)
            if not child or not inverse:
                continue
            if not mid.startswith("x_"):
                continue
            names = _field_names(child)
            if inverse in names:
                continue
            child.setdefault("fields", []).append(
                {
                    "name": inverse,
                    "ttype": "many2one",
                    "relation": mid,
                    "string": short_model_label(mid, plural=False),
                    "source": "odoo_app_bar",
                }
            )
            notes.append(f"app_bar: added inverse {child_id}.{inverse} → {mid}")
    return notes


def strip_invalid_field_attrs(draft: dict[str, Any]) -> list[str]:
    """Selection literals belong on selection fields, not char/date/m2o."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        names = _field_names(model)
        drop: set[str] = set()
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            fname = str(field.get("name") or "")
            ttype = str(field.get("ttype") or "")
            if ttype != "selection" and "selection" in field:
                sel = field.pop("selection")
                if ttype == "many2one" and not field.get("relation") and isinstance(sel, str) and "." in sel:
                    field["relation"] = sel
                notes.append(f"app_bar: stripped selection on {mid}.{fname}")
            if (
                ttype == "char"
                and re.match(r"^x_.+_id$", fname)
                and fname.replace("_id", "")[2:] == mid.replace("x_", "")
                and "x_code" in names
            ):
                drop.add(fname)
        if drop:
            _drop_named_fields(draft, mid, drop)
            notes.append(f"app_bar: dropped duplicate char id {mid}.{', '.join(sorted(drop))}")
    return notes


def humanize_generic_site_labels(draft: dict[str, Any]) -> list[str]:
    """After x_site → x_studio, leftover 'Site' strings become Studio."""
    notes: list[str] = []
    by_id = _models_index(draft)
    site = next(
        (mid for mid in by_id if mid.replace("x_", "", 1) in {"studio", "facility", "clinic", "hotel"}),
        None,
    )
    if not site:
        return notes
    label = short_model_label(site, plural=False)
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            raw = str(field.get("string") or "").strip()
            fname = str(field.get("name") or "")
            rel = str(field.get("relation") or "")
            on_site = str(model.get("model") or "") == site
            if rel == site and raw.lower() in _GENERIC_SITE_STRINGS:
                field["string"] = f"{label} Name" if "name" in raw.lower() else label
            elif (
                rel == site
                and "site" in raw.lower()
                and label.lower() not in raw.lower()
            ):
                field["string"] = f"{label} Name" if "name" in raw.lower() else label
            elif on_site and fname == "x_name" and raw.lower() in _GENERIC_SITE_STRINGS:
                field["string"] = f"{label} Name" if "name" in raw.lower() else label
            elif raw.lower() == "site specialty":
                field["string"] = f"{label} Specialty"
            else:
                continue
            notes.append(f"app_bar: humanized label {model.get('model')}.{fname}")
    return notes


def strip_corrupt_field_strings(draft: dict[str, Any]) -> list[str]:
    """LLM field labels sometimes concatenate JSON fragments: `Duration (Hours)},{`."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            raw = str(field.get("string") or "")
            if not _CORRUPT_LABEL_RE.search(raw):
                continue
            fname = str(field.get("name") or "")
            cleaned = _CORRUPT_LABEL_RE.split(raw)[0].strip().rstrip(",")
            if not cleaned:
                cleaned = fname.replace("x_", "", 1).replace("_", " ").title()
            field["string"] = cleaned
            notes.append(f"app_bar: stripped corrupt label {mid}.{fname}")
    return notes


def retarget_staff_fks_to_employee(draft: dict[str, Any]) -> list[str]:
    """Crew/staff FKs are hr.employee, not res.users, when HR is in the stack."""
    notes: list[str] = []
    depends = {str(d) for d in (draft.get("depends") or [])}
    by_id = _models_index(draft)
    uses_employee = any(
        isinstance(f, dict) and str(f.get("relation") or "") == "hr.employee"
        for model in by_id.values()
        for f in (model.get("fields") or [])
    )
    if "hr" not in depends and not uses_employee:
        return notes
    for model in by_id.values():
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "many2one":
                continue
            if str(field.get("relation") or "") != "res.users":
                continue
            fname = str(field.get("name") or "")
            match = re.match(r"^x_(.+)_id$", fname)
            leaf = match.group(1) if match else ""
            if leaf not in _CREW_ROLE_LEAVES:
                continue
            field["relation"] = "hr.employee"
            if not str(field.get("string") or "").strip():
                field["string"] = "Employee"
            notes.append(
                f"app_bar: retargeted {model.get('model')}.{fname} → hr.employee"
            )
    return notes


def humanize_line_o2m_labels(draft: dict[str, Any]) -> list[str]:
    """O2M leftovers like `X Rate Line` become Lines; a second usage O2M keeps its noun."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        line_o2ms: list[dict[str, Any]] = []
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "one2many":
                continue
            rel = str(field.get("relation") or "")
            if not rel.endswith("_line"):
                continue
            line_o2ms.append(field)
            raw = str(field.get("string") or "").strip()
            if not (raw.startswith("X ") or raw.startswith("x ")):
                continue
            field["string"] = "Lines"
            notes.append(f"app_bar: humanized O2M {mid}.{field.get('name')}")
        labeled_lines = [
            f
            for f in line_o2ms
            if str(f.get("string") or "").strip().lower() in {"lines", "line"}
        ]
        if len(labeled_lines) < 2:
            continue
        for field in labeled_lines:
            rel = str(field.get("relation") or "")
            catalog = rel[: -len("_line")]
            if not any(tok in catalog for tok in _ASSET_LINE_PARENT_TOKENS):
                continue
            field["string"] = short_model_label(catalog, plural=True)
            notes.append(
                f"app_bar: disambiguated usage O2M {mid}.{field.get('name')} "
                f"→ {field['string']}"
            )
    return notes


def demote_line_model_chrome(draft: dict[str, Any]) -> list[str]:
    """sale.order.line has no chatter, kanban, sequences, or statusbar header."""
    notes: list[str] = []
    chatter = {"mail.thread", "mail.activity.mixin"}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.endswith("_line"):
            continue
        mixins = [m for m in (model.get("mixins") or []) if str(m) not in chatter]
        if mixins != list(model.get("mixins") or []):
            model["mixins"] = mixins
            notes.append(f"app_bar: stripped chatter mixins on {mid}")
        if model.get("sequence") or model.get("sequences"):
            model.pop("sequence", None)
            model.pop("sequences", None)
            notes.append(f"app_bar: dropped sequence chrome on {mid}")
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if field.get("name") not in {"x_code", "x_reference"}:
                continue
            help_txt = str(field.get("help") or "")
            if "ir.sequence" in help_txt.lower() or "/00001" in help_txt:
                field.pop("help", None)
                notes.append(f"app_bar: cleared line sequence help on {mid}.{field.get('name')}")
    seqs = draft.get("sequences")
    if isinstance(seqs, list):
        kept_seq = []
        for seq in seqs:
            if isinstance(seq, dict) and str(seq.get("model") or "").endswith("_line"):
                notes.append(f"app_bar: dropped sequence on {seq.get('model')}")
                continue
            kept_seq.append(seq)
        draft["sequences"] = kept_seq
    views = draft.get("views")
    if isinstance(views, list):
        kept_views = []
        for view in views:
            if not isinstance(view, dict):
                continue
            mid = str(view.get("model") or "")
            vtype = str(view.get("type") or "")
            if mid.endswith("_line") and vtype == "kanban":
                notes.append(f"app_bar: dropped kanban on line {mid}")
                continue
            if mid.endswith("_line") and vtype == "form":
                arch = str(view.get("arch") or "")
                new_arch, n_header = re.subn(
                    r"<header>.*?</header>", "", arch, count=1, flags=re.I | re.S
                )
                new_arch, n_chatter = re.subn(r"<chatter\s*/>", "", new_arch, flags=re.I)
                new_arch, n_oe = re.subn(
                    r"<div[^>]*oe_chatter[^>]*>.*?</div>",
                    "",
                    new_arch,
                    flags=re.I | re.S,
                )
                if n_header or n_chatter or n_oe:
                    view = {**view, "arch": new_arch}
                    notes.append(f"app_bar: stripped line form chrome on {mid}")
            kept_views.append(view)
        draft["views"] = kept_views
    for action in draft.get("actions") or []:
        if not isinstance(action, dict):
            continue
        if not str(action.get("model") or "").endswith("_line"):
            continue
        mode = str(action.get("view_mode") or "")
        new_mode = ",".join(p for p in mode.split(",") if p.strip() != "kanban")
        if new_mode != mode:
            action["view_mode"] = new_mode
            notes.append(f"app_bar: dropped kanban view_mode on {action.get('model')}")
    return notes


_SEARCH_FILTER_TAG = re.compile(r"<filter\b[^>]*/>", re.I)
_SEARCH_GROUP_BY = re.compile(
    r"""(['\"]group_by['\"]\s*:\s*['\"])([^'\"]+)(['\"])"""
)
_SEARCH_DOMAIN_FIELD = re.compile(r"""\(['\"]([A-Za-z_][\w.]*)['\"]\s*,""")
_SEARCH_FILTER_NAME = re.compile(r'\bname="([^"]+)"', re.I)
_SEARCH_OK_LEAVES = frozenset({"id", "display_name"})


def _repair_search_filter_arch(
    arch: str, names: set[str], mid: str, notes: list[str]
) -> str:
    """Drop or retarget search filters that name a field not on the model.

    Do not remap a missing group_by onto a random remaining M2O — that turned
    Company filters into parent-document group_bys. Prefer the field implied by
    the filter name (`group_x_company_id` → `x_company_id`) when it exists.
    """

    def _fix(match: re.Match[str]) -> str:
        tag = match.group(0)
        name_m = _SEARCH_FILTER_NAME.search(tag)
        intended = ""
        if name_m:
            fname = name_m.group(1)
            if fname.startswith("group_"):
                intended = fname[len("group_") :]
        for raw in _SEARCH_DOMAIN_FIELD.findall(tag):
            leaf = raw.split(".")[0]
            if leaf in _SEARCH_OK_LEAVES:
                continue
            if leaf not in names:
                notes.append(f"app_bar: dropped search filter on missing {mid}.{leaf}")
                return ""
        gb_m = _SEARCH_GROUP_BY.search(tag)
        if gb_m:
            grouped = gb_m.group(2)
            target = intended if intended in names else grouped
            if target not in names:
                notes.append(f"app_bar: dropped missing search group-by {mid} {grouped}")
                return ""
            if target != grouped:
                notes.append(f"app_bar: search group-by {mid} {grouped} → {target}")
                tag = tag[: gb_m.start(2)] + target + tag[gb_m.end(2) :]
        return tag

    cleaned = _SEARCH_FILTER_TAG.sub(_fix, arch)
    return re.sub(
        r'<filter\b[^>]*context="\{\s*\}"[^>]*/>',
        "",
        cleaned,
        flags=re.I,
    )


def repair_kanban_group_by(draft: dict[str, Any]) -> list[str]:
    """Kanban default_group_by and search filters must name a field on the model."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for view in draft.get("views") or []:
        if not isinstance(view, dict):
            continue
        mid = str(view.get("model") or "")
        model = by_id.get(mid)
        if not model:
            continue
        names = _field_names(model)
        arch = str(view.get("arch") or "")
        vtype = str(view.get("type") or "")
        if vtype == "kanban":
            match = re.search(r'default_group_by="([^"]+)"', arch)
            if not match:
                continue
            grouped = match.group(1)
            if grouped in names:
                continue
            replacement = next(
                (
                    str(f.get("name"))
                    for f in (model.get("fields") or [])
                    if isinstance(f, dict)
                    and f.get("ttype") == "selection"
                    and str(f.get("name") or "") in {"x_type", "x_status"}
                ),
                None,
            )
            if replacement:
                view["arch"] = arch.replace(
                    f'default_group_by="{grouped}"',
                    f'default_group_by="{replacement}"',
                    1,
                )
                notes.append(f"app_bar: kanban group-by {mid} {grouped} → {replacement}")
                continue
            view["arch"] = re.sub(r'\s*default_group_by="[^"]+"', "", arch, count=1)
            notes.append(f"app_bar: dropped missing kanban group-by on {mid}")
            continue
        if vtype != "search":
            continue
        cleaned = _repair_search_filter_arch(arch, names, mid, notes)
        if cleaned != arch:
            view["arch"] = cleaned
    return notes


def dedupe_record_rules(draft: dict[str, Any]) -> list[str]:
    """Keep one ir.rule per model+domain after crew/line retargets."""
    rules = draft.get("record_rules")
    if not isinstance(rules, list):
        return []
    seen: set[tuple[str, str]] = set()
    kept: list[Any] = []
    dropped = 0
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        key = (str(rule.get("model") or ""), str(rule.get("domain_force") or ""))
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        kept.append(rule)
    if dropped:
        draft["record_rules"] = kept
        return [f"app_bar: dropped {dropped} duplicate record rule(s)"]
    return []


def drop_invalid_smart_buttons(draft: dict[str, Any]) -> list[str]:
    """Smart-button relation_field must be a M2O on the related model."""
    notes: list[str] = []
    buttons = draft.get("smart_buttons")
    if not isinstance(buttons, list):
        return notes
    by_id = _models_index(draft)
    notebook_children = _notebook_child_ids(by_id)
    kept: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for btn in buttons:
        if not isinstance(btn, dict):
            continue
        rel_model = str(btn.get("related_model") or "")
        fk = str(btn.get("relation_field") or "")
        on_model = str(btn.get("on_model") or "")
        if on_model == "res.partner" and rel_model in notebook_children:
            notes.append(
                f"app_bar: dropped Contacts notebook-child button {rel_model}"
            )
            continue
        target = by_id.get(rel_model)
        field = next(
            (
                f
                for f in ((target or {}).get("fields") or [])
                if isinstance(f, dict) and str(f.get("name") or "") == fk
            ),
            None,
        )
        if (
            not field
            or field.get("ttype") != "many2one"
            or (on_model.startswith("x_") and str(field.get("relation") or "") != on_model)
        ):
            notes.append(f"app_bar: dropped invalid smart button {on_model} → {rel_model}.{fk}")
            continue
        key = (on_model, rel_model, fk)
        if key in seen:
            continue
        seen.add(key)
        if _is_notebook_duplicate_smart_button(on_model, rel_model, by_id):
            notes.append(
                f"app_bar: dropped notebook-duplicate smart button {on_model} → {rel_model}"
            )
            continue
        kept.append(btn)
    draft["smart_buttons"] = kept
    return notes


def _job_header_model_ids(draft: dict[str, Any]) -> list[str]:
    """Exact-leaf job headers only — x_job_cost is not x_job."""
    out: list[str] = []
    for mid in _models_index(draft):
        if mid.endswith("_line") or not mid.startswith("x_"):
            continue
        if mid.replace("x_", "", 1) in _JOB_HEADER_LEAVES:
            out.append(mid)
    return out


def _inbound_m2o_count(draft: dict[str, Any], target_id: str) -> int:
    n = 0
    for mid, model in _models_index(draft).items():
        if mid == target_id:
            continue
        for field in model.get("fields") or []:
            if (
                isinstance(field, dict)
                and field.get("ttype") == "many2one"
                and str(field.get("relation") or "") == target_id
            ):
                n += 1
    return n


def _prompt_leaf_hits(prompt: str, leaves: frozenset[str]) -> list[str]:
    from app.ai_domain_density import _prompt_token_hit

    return [leaf for leaf in leaves if _prompt_token_hit(prompt, (leaf,))]


def _prompt_keeps_legal_matter(draft: dict[str, Any], prompt: str) -> bool:
    if "law" in str(draft.get("domain_pack") or ""):
        return True
    return bool(
        re.search(r"\b(matter|hearing|law firm|attorney|solicitor)\b", prompt, re.I)
    )


def _pick_job_header_keeper(
    draft: dict[str, Any],
    members: list[str],
    prompt: str,
) -> str:
    if _prompt_keeps_legal_matter(draft, prompt):
        matter = next((m for m in members if m.replace("x_", "", 1) == "matter"), None)
        if matter:
            return matter
    hits = _prompt_leaf_hits(prompt, _JOB_HEADER_LEAVES)
    hit_models = [m for m in members if m.replace("x_", "", 1) in hits]
    if len(hit_models) == 1:
        return hit_models[0]

    def _key(mid: str) -> tuple[int, int, str]:
        leaf = mid.replace("x_", "", 1)
        pref = (
            _JOB_HEADER_PREFERENCE.index(leaf)
            if leaf in _JOB_HEADER_PREFERENCE
            else 99
        )
        return (-_inbound_m2o_count(draft, mid), pref, mid)

    return sorted(members, key=_key)[0]


def _dedupe_model_fields(model: dict[str, Any]) -> None:
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    for field in model.get("fields") or []:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "")
        if name in seen:
            continue
        seen.add(name)
        kept.append(field)
    model["fields"] = kept


def collapse_parallel_job_headers(
    draft: dict[str, Any], *, user_prompt: str = ""
) -> list[str]:
    """One operational job header. engagement/project/matter/case/stay/job are the same role.

    Skip curated packs. If the prompt names two of those leaves, keep both.
    """
    notes: list[str] = []
    if draft.get("domain_pack"):
        return notes
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    members = _job_header_model_ids(draft)
    if len(members) < 2:
        return notes
    hits = _prompt_leaf_hits(prompt, _JOB_HEADER_LEAVES)
    hit_models = [m for m in members if m.replace("x_", "", 1) in hits]
    if len(hit_models) >= 2:
        return notes
    keep = _pick_job_header_keeper(draft, members, prompt)
    doomed_ids = [m for m in members if m != keep]
    from app.ai_domain_packs import _purge_draft_artifacts_for_models

    for doomed in doomed_ids:
        by_id = _models_index(draft)
        keep_model = by_id.get(keep)
        src = by_id.get(doomed)
        if not keep_model or not src:
            continue
        keep_names = _field_names(keep_model)
        for field in src.get("fields") or []:
            if not isinstance(field, dict):
                continue
            fname = str(field.get("name") or "")
            if not fname or fname in keep_names:
                continue
            rel = str(field.get("relation") or "")
            if field.get("ttype") in {"many2one", "one2many"} and rel in {keep, doomed}:
                continue
            keep_model.setdefault("fields", []).append(dict(field))
            keep_names.add(fname)
            notes.append(f"app_bar: copied {doomed}.{fname} onto {keep}")
        notes.extend(
            _retarget_removed_relations(
                draft, {doomed}, extra_fallbacks={doomed: keep}
            )
        )
        _purge_draft_artifacts_for_models(draft, {doomed})
        rewriter = lambda s, old=doomed, new=keep: _rewrite_model_ident(s, old, new)
        skip = {"_user_prompt", "_domain_briefing", "display_name", "technical_name"}
        for key, value in list(draft.items()):
            if key in skip:
                continue
            draft[key] = _walk_rename_strings(value, rewriter)
        for model in draft.get("models") or []:
            if isinstance(model, dict):
                _dedupe_model_fields(model)
        notes.append(f"app_bar: collapsed parallel job header {doomed} → {keep}")
    return notes


def canonicalize_draft_selections(draft: dict[str, Any]) -> list[str]:
    """Snake-case selection keys and remap state_field / defaults."""
    from app.ai_selection import (
        canonicalize_selection_pairs,
        parse_selection_literal,
        serialize_selection,
    )

    notes: list[str] = []
    maps_by_model: dict[str, dict[str, str]] = {}

    def _remap_state(value: Any, mapping: dict[str, str]) -> Any:
        if isinstance(value, str):
            return mapping.get(value, value)
        if isinstance(value, list):
            return [_remap_state(v, mapping) for v in value]
        if isinstance(value, tuple):
            return tuple(_remap_state(v, mapping) for v in value)
        return value

    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        maps: dict[str, dict[str, str]] = {}
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "selection":
                continue
            pairs = parse_selection_literal(field.get("selection")) or []
            if not pairs:
                continue
            canonical, mapping, changed = canonicalize_selection_pairs(pairs)
            fname = str(field.get("name") or "")
            maps[fname] = mapping
            if changed:
                field["selection"] = serialize_selection(canonical)
                notes.append(f"app_bar: canonicalized selection {mid}.{fname}")
            default = field.get("default")
            if isinstance(default, str) and default in mapping:
                field["default"] = mapping[default]
        merged: dict[str, str] = {}
        for mapping in maps.values():
            merged.update(mapping)
        if merged:
            maps_by_model[mid] = merged
        sf = model.get("state_field")
        if not isinstance(sf, dict):
            continue
        fname = str(sf.get("field") or "x_status")
        mapping = maps.get(fname) or merged
        if not mapping:
            continue
        for key in ("states", "statusbar_visible"):
            if key in sf and isinstance(sf[key], list):
                remapped = _remap_state(sf[key], mapping)
                seen: list[Any] = []
                for item in remapped:
                    if item not in seen:
                        seen.append(item)
                sf[key] = seen
        if "transitions" in sf:
            sf["transitions"] = _remap_state(sf["transitions"], mapping)
        model["state_field"] = sf
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        mapping = maps_by_model.get(str(auto.get("model") or "")) or {}
        if not mapping:
            continue
        fd = auto.get("filter_domain")
        if isinstance(fd, str):
            for old, new in mapping.items():
                if old == new:
                    continue
                fd = fd.replace(f"'{old}'", f"'{new}'")
                fd = fd.replace(f'"{old}"', f'"{new}"')
            auto["filter_domain"] = fd
        for action in auto.get("safe_actions") or []:
            if not isinstance(action, dict):
                continue
            val = action.get("value")
            if isinstance(val, str) and val in mapping:
                action["value"] = mapping[val]
    return notes


def rename_selection_fields_dropping_id_suffix(draft: dict[str, Any]) -> list[str]:
    """x_specialty_id as selection is not a many2one — drop the false _id suffix."""
    notes: list[str] = []
    skip = {"_user_prompt", "_domain_briefing", "display_name", "technical_name"}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        names = _field_names(model)
        for field in list(model.get("fields") or []):
            if not isinstance(field, dict) or field.get("ttype") != "selection":
                continue
            fname = str(field.get("name") or "")
            if not fname.endswith("_id"):
                continue
            new_name = fname[: -len("_id")]
            if not new_name.startswith("x_") or new_name in names:
                continue
            rewriter = lambda s, old=fname, new=new_name: _rewrite_field_ident(s, old, new)
            for key, value in list(draft.items()):
                if key in skip:
                    continue
                draft[key] = _walk_rename_strings(value, rewriter)
            names.discard(fname)
            names.add(new_name)
            notes.append(f"app_bar: renamed selection {mid}.{fname} → {new_name}")
    return notes


def align_fk_field_names_to_relation(draft: dict[str, Any]) -> list[str]:
    """x_party_id → x_artist_id when the relation is already x_artist."""
    notes: list[str] = []
    known = set(_models_index(draft))
    skip = {"_user_prompt", "_domain_briefing", "display_name", "technical_name"}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        names = _field_names(model)
        for field in list(model.get("fields") or []):
            if not isinstance(field, dict) or field.get("ttype") != "many2one":
                continue
            fname = str(field.get("name") or "")
            match = re.match(r"^x_(.+)_id$", fname)
            if not match:
                continue
            rel = str(field.get("relation") or "")
            if not rel.startswith("x_") or rel not in known:
                continue
            leaf = match.group(1)
            if leaf in _DEFAULT_ASSET_TYPE_LEAVES:
                continue
            expected = f"x_{rel.replace('x_', '', 1)}_id"
            if expected == fname or expected in names:
                continue
            rewriter = lambda s, old=fname, new=expected: _rewrite_field_ident(s, old, new)
            for key, value in list(draft.items()):
                if key in skip:
                    continue
                draft[key] = _walk_rename_strings(value, rewriter)
            names.discard(fname)
            names.add(expected)
            notes.append(f"app_bar: renamed {mid}.{fname} → {expected} (relation {rel})")
    return notes


def demote_workflows_missing_status(draft: dict[str, Any]) -> list[str]:
    """is_workflow without a status selection is a register, not a document."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or not model.get("is_workflow"):
            continue
        sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
        fname = str(sf.get("field") or "x_status")
        has_status = any(
            isinstance(f, dict)
            and str(f.get("name") or "") == fname
            and f.get("ttype") == "selection"
            for f in (model.get("fields") or [])
        )
        if has_status:
            continue
        mid = str(model.get("model") or "")
        model["is_workflow"] = False
        model.pop("state_field", None)
        notes.append(f"app_bar: demoted workflow without status on {mid}")
    return notes


def _filter_domain_is_atom_list(fd: Any) -> bool:
    if not isinstance(fd, str) or not fd.strip():
        return False
    try:
        val = ast.literal_eval(fd.strip())
    except (ValueError, SyntaxError):
        return False
    return bool(isinstance(val, list) and val and all(isinstance(x, str) for x in val))


def _filter_domain_is_invalid(fd: Any) -> bool:
    """Python-shaped or non-tuple domains are not live-applyable."""
    if _filter_domain_is_atom_list(fd):
        return True
    if not isinstance(fd, str) or not fd.strip() or fd.strip() in {"[]", "False"}:
        return False
    raw = fd.strip()
    try:
        ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return " in (" in raw or bool(re.search(r"\bif\b", raw))
    return False


_FAKE_ACTION_VALUE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*\(")


def drop_invalid_automations(draft: dict[str, Any]) -> list[str]:
    """Drop automations whose filter names a missing field, is not a domain, or fakes Python."""
    notes: list[str] = []
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return notes
    by_id = _models_index(draft)
    kept: list[dict[str, Any]] = []
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        mid = str(auto.get("model") or "")
        model = by_id.get(mid)
        name = str(auto.get("name") or "")
        if not model:
            notes.append(f"app_bar: dropped automation {name!r} (missing model)")
            continue
        names = _field_names(model)
        fd = auto.get("filter_domain")
        if _filter_domain_is_invalid(fd):
            notes.append(f"app_bar: dropped automation {name!r} (invalid domain)")
            continue
        fd_s = str(fd or "")
        refs = re.findall(r"['\"](x_[a-z0-9_]+)['\"]", fd_s)
        if any(ref not in names for ref in refs):
            notes.append(f"app_bar: dropped automation {name!r} (missing field)")
            continue
        if "x_status" in names and "x_status" in fd_s:
            status = next(
                (
                    f
                    for f in (model.get("fields") or [])
                    if isinstance(f, dict) and f.get("name") == "x_status"
                ),
                None,
            )
            from app.ai_selection import parse_selection_literal

            keys = {
                k
                for k, _ in (parse_selection_literal((status or {}).get("selection")) or [])
            }
            mentioned = set(re.findall(r"['\"]([a-z_]+)['\"]", fd_s)) - {
                "x_status",
                "in",
                "not",
                "now",
            }
            mentioned = {k for k in mentioned if not k.startswith("x_")}
            if "done" in keys:
                rewritten = False
                for alias in ("completed", "complete"):
                    if alias not in mentioned:
                        continue
                    fd_s = fd_s.replace(f"'{alias}'", "'done'").replace(
                        f'"{alias}"', '"done"'
                    )
                    mentioned.discard(alias)
                    mentioned.add("done")
                    rewritten = True
                if rewritten:
                    auto["filter_domain"] = fd_s
                    notes.append(
                        f"app_bar: rewrote completed→done in automation {name!r}"
                    )
            if keys and mentioned and not (mentioned & keys):
                notes.append(f"app_bar: dropped automation {name!r} (status mismatch)")
                continue
        fake_action = False
        from app.ai_live_apply_contract import _action_is_unapplyable

        for action in auto.get("safe_actions") or []:
            if not isinstance(action, dict):
                continue
            field = str(action.get("field") or "")
            if field.startswith("x_") and field not in names:
                fake_action = True
                break
            if _action_is_unapplyable(action):
                fake_action = True
                break
            value = str(action.get("value") or "").strip()
            if value and _FAKE_ACTION_VALUE_RE.match(value):
                fake_action = True
                break
        if fake_action:
            notes.append(f"app_bar: dropped automation {name!r} (non-metadata action)")
            continue
        kept.append(auto)
    draft["automations"] = kept
    return notes


def close_odoo_architecture(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """Last-word graph repair — runs after critique/elite and as the Expert fixer."""
    notes: list[str] = []
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    from app.ai_stock_first import clip_to_stock_first_floor

    notes.extend(clip_to_stock_first_floor(draft, user_prompt=prompt))
    from app.ai_document_shape import honor_operator_brief

    notes.extend(honor_operator_brief(draft, user_prompt=prompt))
    notes.extend(prefer_prompt_model_names(draft, user_prompt=prompt))
    notes.extend(prune_stock_clone_models(draft, user_prompt=prompt))
    notes.extend(prune_generic_loop_models(draft, user_prompt=prompt))
    notes.extend(prune_leftover_specialty_satellites(draft))
    notes.extend(drop_orphan_relational_fields(draft))
    notes.extend(ensure_residual_satellites(draft))
    notes.extend(ensure_stock_inherit_bridges(draft))
    notes.extend(drop_stock_inverse_o2ms(draft))
    notes.extend(repair_named_foreign_keys(draft))
    notes.extend(ensure_site_fk_on_operations(draft))
    notes.extend(repair_named_foreign_keys(draft))
    notes.extend(ensure_o2m_inverse_fields(draft))
    notes.extend(reconcile_stale_o2ms(draft))
    notes.extend(ensure_reverse_o2ms(draft))
    notes.extend(promote_booking_headers(draft))
    notes.extend(demote_line_model_workflows(draft))
    notes.extend(demote_register_status_workflows(draft))
    notes.extend(scrub_selection_chrome_smart_buttons(draft))
    notes.extend(drop_leftover_state_fields(draft))
    notes.extend(repair_partner_smart_button_targets(draft))
    from app.ai_apply_readiness import (
        apply_line_subtotal_computes,
        apply_order_header_total_computes,
        ensure_header_line_subtotals,
        ensure_model_access_stubs,
        ensure_relation_module_depends,
        filter_stale_enrich_warnings,
        scrub_unknown_arch_field_refs,
        sync_company_fields_with_record_rules,
    )
    from app.ai_domain_briefing import apply_briefing_to_draft
    from app.ai_enrich import (
        collapse_header_o2ms_into_notebook,
        ensure_default_ui,
        sync_form_archs_to_models,
    )
    from app.ai_post_critique import (
        ensure_line_model_parent_links,
        ensure_workflow_models_have_state_field,
        verify_model_ui_completeness,
    )
    from app.ai_presentation import dedupe_smart_button_labels, group_menus_if_needed

    notes.extend(apply_briefing_to_draft(draft, user_prompt=prompt))
    notes.extend(canonicalize_draft_selections(draft))
    notes.extend(rename_selection_fields_dropping_id_suffix(draft))
    notes.extend(rewrite_foreign_lexicon_fks(draft, user_prompt=prompt))
    notes.extend(drop_foreign_role_fields(draft, user_prompt=prompt))
    notes.extend(collapse_parallel_job_headers(draft, user_prompt=prompt))
    notes.extend(collapse_typed_asset_foreign_keys(draft))
    notes.extend(align_fk_field_names_to_relation(draft))
    notes.extend(ensure_booking_engagement_fk(draft))
    notes.extend(ensure_revision_deliverable_fk(draft))
    notes.extend(ensure_job_header_children_fk(draft, user_prompt=prompt))
    notes.extend(collapse_duplicate_line_models(draft))
    notes.extend(collapse_hollow_cost_headers(draft))
    notes.extend(repair_agreement_party_shape(draft))
    notes.extend(relabel_company_fields(draft))
    notes.extend(ensure_asset_usage_line(draft))
    notes.extend(ensure_asset_line_on_booking(draft))
    notes.extend(collapse_parallel_asset_usage(draft))
    notes.extend(relax_copied_asset_line_requireds(draft))
    notes.extend(collapse_redundant_uom_register(draft))
    notes.extend(drop_duplicate_identical_selections(draft))
    notes.extend(stamp_session_sale_order_link_only(draft))
    notes.extend(drop_purchase_on_booking_headers(draft))
    notes.extend(strip_party_register_sellables(draft))
    notes.extend(prune_leftover_specialty_satellites(draft))
    notes.extend(fix_workflow_default_to_initial(draft))
    notes.extend(ensure_o2m_inverse_fields(draft))
    notes.extend(ensure_reverse_o2ms(draft))
    notes.extend(humanize_line_o2m_labels(draft))
    notes.extend(reconcile_stale_o2ms(draft))
    notes.extend(drop_stock_inverse_o2ms(draft))
    notes.extend(strip_invalid_field_attrs(draft))
    notes.extend(strip_corrupt_field_strings(draft))
    notes.extend(humanize_generic_site_labels(draft))
    notes.extend(retarget_staff_fks_to_employee(draft))
    notes.extend(drop_invalid_smart_buttons(draft))
    notes.extend(drop_hollow_automations(draft))
    notes.extend(drop_invalid_automations(draft))
    from app.ai_live_apply_contract import stamp_live_apply_contract

    notes.extend(stamp_live_apply_contract(draft))
    notes.extend(ensure_header_line_subtotals(draft))
    notes.extend(apply_line_subtotal_computes(draft))
    notes.extend(apply_order_header_total_computes(draft))
    notes.extend(relax_lined_header_rate_requireds(draft))
    notes.extend(ensure_relation_module_depends(draft))
    notes.extend(scrub_unknown_arch_field_refs(draft))
    notes.extend(ensure_line_model_parent_links(draft))
    notes.extend(trim_line_extra_parents(draft))
    notes.extend(drop_self_relations(draft))
    notes.extend(drop_parent_m2o_when_child_o2m_exists(draft))
    notes.extend(reconcile_stale_o2ms(draft))
    notes.extend(drop_invalid_smart_buttons(draft))
    notes.extend(drop_orphan_line_models(draft))
    notes.extend(demote_line_model_workflows(draft))
    notes.extend(demote_workflows_missing_status(draft))
    notes.extend(ensure_workflow_models_have_state_field(draft))
    from app.ai_model_quality import demote_spurious_link_workflows

    notes.extend(demote_spurious_link_workflows(draft))
    notes.extend(ensure_model_access_stubs(draft))

    notes.extend(ensure_default_ui(draft))
    notes.extend(demote_line_model_chrome(draft))
    notes.extend(sync_form_archs_to_models(draft))
    notes.extend(sync_company_fields_with_record_rules(draft))
    notes.extend(dedupe_record_rules(draft))
    notes.extend(repair_kanban_group_by(draft))
    notes.extend(scrub_unknown_arch_field_refs(draft))
    notes.extend(group_menus_if_needed(draft, threshold=4))
    notes.extend(drop_ghost_menus_and_actions(draft))
    notes.extend(_hide_line_model_menus(draft))
    from app.ai_approval_flow import apply_approval_flow

    notes.extend(apply_approval_flow(draft, prompt=prompt))
    notes.extend(rebuild_form_transition_headers(draft))
    notes.extend(strip_register_form_headers(draft))
    notes.extend(inject_chatter_on_forms(draft))
    notes.extend(humanize_app_surface(draft))
    notes.extend(dedupe_smart_button_labels(draft))
    notes.extend(apply_senior_sequence_prefixes(draft))
    ui_items = verify_model_ui_completeness(draft)
    comp = [
        c
        for c in (draft.get("_completeness") or [])
        if isinstance(c, dict) and not str(c.get("id") or "").startswith("model_ui:")
    ]
    comp.extend(ui_items)
    draft["_completeness"] = comp
    review = draft.get("review_notes")
    if isinstance(review, list) and review:
        draft["review_notes"] = filter_stale_enrich_warnings(
            [str(x) for x in review], draft
        )
    from app.ai_live_apply_contract import attach_live_apply_contract

    notes.extend(attach_live_apply_contract(draft))
    from app.ai_stock_first import clip_to_stock_first_floor, strip_stock_inherit_junk_fields

    notes.extend(strip_stock_inherit_junk_fields(draft))
    # Headers must match post-strip state_field (Confirm = intake→open)
    notes.extend(rebuild_form_transition_headers(draft))
    notes.extend(clip_to_stock_first_floor(draft, user_prompt=prompt))
    notes.extend(honor_operator_brief(draft, user_prompt=prompt))
    from app.ai_apply_readiness import dedupe_automations_by_signature

    notes.extend(dedupe_automations_by_signature(draft))
    from app.ai_production_shape import ensure_search_views

    notes.extend(ensure_search_views(draft))
    # Domain-agnostic Option A scaffolds (Paystack/QR/…) even on mixed live+capability briefs
    try:
        from app.ai_capability_gaps import stamp_capability_gaps

        notes.extend(stamp_capability_gaps(draft, prompt))
    except Exception as exc:  # noqa: BLE001
        notes.append(f"capability: stamp skipped ({exc})")
    notes.extend(collapse_header_o2ms_into_notebook(draft))
    try:
        from app.ai_operator_surface import attach_operator_surface

        notes.extend(attach_operator_surface(draft))
    except Exception as exc:  # noqa: BLE001
        notes.append(f"operator_surface: skipped ({exc})")
    return notes


def promote_booking_headers(draft: dict[str, Any]) -> list[str]:
    """Sessions/bookings are the document — not a flat register."""
    notes: list[str] = []
    from app.ai_workflow import apply_state_field_to_model

    for i, model in enumerate(list(draft.get("models") or [])):
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not any(tok in mid for tok in _BOOKING_TOKENS) or mid.endswith("_line"):
            continue
        if model.get("is_workflow") and isinstance(model.get("state_field"), dict):
            continue
        states = ["draft", "confirmed", "in_progress", "done", "cancelled"]
        transitions = [
            ["draft", "confirmed"],
            ["confirmed", "in_progress"],
            ["in_progress", "done"],
            ["draft", "cancelled"],
            ["confirmed", "cancelled"],
            ["in_progress", "cancelled"],
        ]
        updated = apply_state_field_to_model(
            model, states=states, transitions=transitions
        )
        updated["is_workflow"] = True
        sf = updated.get("state_field") if isinstance(updated.get("state_field"), dict) else {}
        sf["statusbar_visible"] = ["draft", "confirmed", "in_progress", "done"]
        updated["state_field"] = sf
        mixins = list(updated.get("mixins") or [])
        for mixin in ("mail.thread", "mail.activity.mixin"):
            if mixin not in mixins:
                mixins.append(mixin)
        updated["mixins"] = mixins
        draft["models"][i] = updated
        notes.append(f"app_bar: promoted booking header workflow on {mid}")
    return notes


def drop_leftover_state_fields(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or model.get("is_workflow"):
            continue
        if model.get("state_field"):
            model.pop("state_field", None)
            notes.append(
                f"app_bar: dropped leftover state_field on {model.get('model')}"
            )
    return notes


def _filter_is_only_terminal_status(filter_domain: str) -> bool:
    text = str(filter_domain or "").strip()
    if not text or text in {"[]", "False"}:
        return False
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return False
    if not isinstance(parsed, list):
        return False
    terms = [t for t in parsed if t not in ("&", "|", "!")]
    if len(terms) != 1:
        return False
    term = terms[0]
    if not isinstance(term, (list, tuple)) or len(term) < 3:
        return False
    field, op, val = term[0], term[1], term[2]
    if str(field) not in {"x_status", "state"}:
        return False
    if str(op) == "=":
        return str(val).lower() in _TERMINAL_STATUS_KEYS
    if str(op) == "in":
        vals = val if isinstance(val, (list, tuple)) else [val]
        return bool(vals) and all(str(v).lower() in _TERMINAL_STATUS_KEYS for v in vals)
    return False


def drop_hollow_automations(draft: dict[str, Any]) -> list[str]:
    """filter_domain [] + next_activity named after the rule is not an automation.

    Also drop write-triggered To-Dos whose only filter is ``x_status = done`` —
    the record is already terminal; keep real ``on_time`` deadline follow-ups.
    """
    notes: list[str] = []
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return notes
    kept: list[dict[str, Any]] = []
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        fd = str(auto.get("filter_domain") or "").strip()
        actions = [a for a in (auto.get("safe_actions") or []) if isinstance(a, dict)]
        name = str(auto.get("name") or "")
        trigger = str(auto.get("trigger") or auto.get("trg") or "on_write")
        hollow = fd in {"", "[]", "False"} and (
            not actions
            or all(
                a.get("kind") == "next_activity"
                and str(a.get("summary") or "") in {name, ""}
                for a in actions
            )
            or all(
                a.get("kind") == "object_write"
                and str(a.get("field") or "") == str(a.get("value") or "")
                for a in actions
            )
        )
        terminal_todo = (
            trigger in {"on_write", "on_create_or_write", "on_create", "write", "create"}
            and bool(actions)
            and all(a.get("kind") == "next_activity" for a in actions)
            and _filter_is_only_terminal_status(fd)
        )
        if hollow:
            notes.append(f"app_bar: dropped hollow automation {name!r}")
            continue
        if terminal_todo:
            notes.append(f"app_bar: dropped terminal-status To Do {name!r}")
            continue
        kept.append(auto)
    draft["automations"] = kept
    return notes


def ensure_invoice_link_on_headers(draft: dict[str, Any]) -> list[str]:
    """After dropping parallel x_bill, headers link account.move (PCM link-only)."""
    notes: list[str] = []
    from app.ai_document_shape import additive_model_growth_blocked

    if additive_model_growth_blocked(draft):
        return notes
    pruned = {str(x) for x in (draft.get("_app_bar_pruned") or [])}
    billing_dropped = any("bill" in m or "invoice" in m for m in pruned)
    if not billing_dropped:
        return notes
    by_id = _models_index(draft)
    added = False
    for mid, model in by_id.items():
        if mid.endswith("_line"):
            continue
        if not (
            _looks_like_header(model)
            or any(tok in mid for tok in ("session", "project", "booking"))
        ):
            continue
        names = _field_names(model)
        if names & {"x_invoice_id", "x_bill_id", "x_move_id"}:
            for field in model.get("fields") or []:
                if not isinstance(field, dict):
                    continue
                if str(field.get("name") or "") in {"x_invoice_id", "x_bill_id", "x_move_id"}:
                    if str(field.get("relation") or "") != "account.move":
                        field["relation"] = "account.move"
                        field["name"] = "x_invoice_id"
                        field["string"] = "Invoice"
                        notes.append(f"app_bar: invoice link on {mid} → account.move")
            continue
        model.setdefault("fields", []).append(
            {
                "name": "x_invoice_id",
                "ttype": "many2one",
                "relation": "account.move",
                "string": "Invoice",
                "source": "odoo_app_bar",
            }
        )
        added = True
        notes.append(f"app_bar: added x_invoice_id on {mid}")
    if added or billing_dropped:
        depends = list(draft.get("depends") or [])
        if "account" not in depends:
            depends.append("account")
            draft["depends"] = depends
            notes.append("app_bar: depends account")
        reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
        models_reuse = list(reuse.get("models") or [])
        if "account.move" not in models_reuse:
            models_reuse.append("account.move")
            draft["reuse"] = {**reuse, "models": models_reuse}
    return notes


def strip_register_form_headers(draft: dict[str, Any]) -> list[str]:
    """Registers may show a statusbar; they must not have Confirm/Done chrome."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for view in draft.get("views") or []:
        if not isinstance(view, dict) or str(view.get("type") or "") != "form":
            continue
        mid = str(view.get("model") or "")
        model = by_id.get(mid) or {}
        if model.get("is_workflow"):
            continue
        arch = str(view.get("arch") or "")
        if not re.search(r"<header>", arch, re.I):
            continue
        from app.ai_model_quality import is_embedded_line_model

        if is_embedded_line_model(mid):
            replacement = ""
        elif "x_status" in _field_names(model):
            replacement = '<header><field name="x_status" widget="statusbar"/></header>'
        else:
            replacement = ""
        new_arch, n = re.subn(
            r"<header>.*?</header>", replacement, arch, count=1, flags=re.I | re.S
        )
        if n and new_arch != arch:
            view["arch"] = new_arch
            notes.append(f"app_bar: stripped workflow chrome on {mid} form")
    return notes


def sync_security_groups_to_technical_name(draft: dict[str, Any]) -> list[str]:
    """Menus, ACL, and groups must share group_{technical_name}_{user,manager}."""
    notes: list[str] = []
    tech = str(draft.get("technical_name") or "").replace(".", "_")
    if not tech:
        return notes
    user_id = f"group_{tech}_user"
    mgr_id = f"group_{tech}_manager"
    display = str(draft.get("display_name") or tech.replace("_", " ").title())
    draft["groups"] = [
        {
            "id": user_id,
            "name": f"{display} User",
            "category_id": "base.module_category_custom",
        },
        {
            "id": mgr_id,
            "name": f"{display} Manager",
            "implied_ids": [user_id],
            "category_id": "base.module_category_custom",
        },
    ]
    rewritten = 0
    for rule in draft.get("access_rules") or []:
        if not isinstance(rule, dict):
            continue
        gid = str(rule.get("group") or "")
        if "manager" in gid.lower():
            if gid != mgr_id:
                rule["group"] = mgr_id
                rewritten += 1
        elif gid and gid != user_id:
            rule["group"] = user_id
            rewritten += 1
    for menu in draft.get("menus") or []:
        if not isinstance(menu, dict):
            continue
        groups = menu.get("groups")
        if isinstance(groups, list) and groups:
            menu["groups"] = [user_id]
            rewritten += 1
        elif isinstance(groups, str) and groups and groups != user_id:
            menu["groups"] = [user_id]
            rewritten += 1
    if rewritten:
        notes.append(f"app_bar: synced {rewritten} ACL/menu group ref(s) to {tech}")
    return notes


_WEB_ICON_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("music", "studio", "recording", "artist", "artiste"), "fa-music"),
    # Do not use bare "stay" — "Receipts stay stock POS" is Option-A deferral.
    (("hotel", "room", "guest", "lodging", "check-in"), "fa-bed"),
    (("hospital", "clinic", "patient", "ward"), "fa-stethoscope"),
    (("fleet", "vehicle", "truck", "van"), "fa-truck"),
    (("restaurant", "kitchen", "menu", "dining"), "fa-cutlery"),
    (("law", "legal", "matter", "attorney"), "fa-balance-scale"),
    (("library", "book", "loan"), "fa-book"),
    (("loyalty", "punch", "punchcard"), "fa-ticket"),
    (("retail", "store", "supermarket", "shop"), "fa-shopping-cart"),
    (("oil", "gas", "well", "rig", "drilling"), "fa-industry"),
    (("foundry", "furnace", "melt"), "fa-fire"),
)
_PACK_WEB_ICONS: dict[str, str] = {
    "law_firm": "fa-balance-scale",
    "hotel": "fa-bed",
    "restaurant": "fa-cutlery",
    "hospital": "fa-stethoscope",
    "clinic": "fa-stethoscope",
    "car_rental": "fa-truck",
    "library_management": "fa-book",
    "retail_supermarket": "fa-shopping-cart",
    "oil_gas_operations": "fa-industry",
}
_DEFAULT_WEB_ICON = "fa-th-large,#714B67"


def _web_icon_for_prompt(prompt: str, draft: dict[str, Any]) -> str:
    from app.text_negation import has_positive_needle

    pack_id = str(draft.get("domain_pack") or "")
    if pack_id in _PACK_WEB_ICONS:
        return f"{_PACK_WEB_ICONS[pack_id]},#714B67"
    hay = " ".join(
        [
            prompt,
            str(draft.get("display_name") or ""),
            str(draft.get("technical_name") or ""),
        ]
    )
    for tokens, icon in _WEB_ICON_HINTS:
        if any(has_positive_needle(hay, tok) for tok in tokens):
            return f"{icon},#714B67"
    return _DEFAULT_WEB_ICON


def ensure_root_web_icon(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """Odoo home-grid icon on the root menuitem (Font Awesome + brand purple)."""
    notes: list[str] = []
    menus = draft.get("menus")
    if not isinstance(menus, list):
        return notes
    root = next(
        (
            m
            for m in menus
            if isinstance(m, dict) and not m.get("parent_xml_id") and not m.get("action_xml_id")
        ),
        None,
    )
    if not root:
        return notes
    icon = _web_icon_for_prompt(
        user_prompt or str(draft.get("_user_prompt") or ""),
        draft,
    )
    if root.get("web_icon") == icon:
        return notes
    root["web_icon"] = icon
    notes.append(f"app_bar: root web_icon {icon}")
    return notes


def run_odoo_app_bar_pass(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """Raise any domain draft to Odoo Apps Store structural bar."""
    notes: list[str] = []
    if user_prompt:
        draft["_user_prompt"] = user_prompt
    if not draft.get("_ambition"):
        from app.ai_depth import classify_ambition

        draft["_ambition"] = classify_ambition(user_prompt or str(draft.get("_user_prompt") or ""))

    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    from app.ai_domain_briefing import attach_domain_briefing
    from app.ai_stock_first import clip_to_stock_first_floor

    attach_domain_briefing(draft, user_prompt=prompt)
    from app.ai_operator_brief import attach_operator_brief

    attach_operator_brief(draft, user_prompt=prompt)
    from app.ai_document_shape import honor_operator_brief

    notes.extend(honor_operator_brief(draft, user_prompt=prompt))
    notes.extend(clip_to_stock_first_floor(draft, user_prompt=prompt))
    notes.extend(prune_generic_loop_models(draft, user_prompt=prompt))
    notes.extend(prune_stock_clone_models(draft, user_prompt=prompt))
    from app.ai_domain_density import ensure_domain_density

    notes.extend(
        ensure_domain_density(
            draft,
            user_prompt=prompt,
            ambition=str(draft.get("_ambition") or ""),
        )
    )
    notes.extend(drop_orphan_relational_fields(draft))
    notes.extend(repair_named_foreign_keys(draft))
    notes.extend(ensure_site_fk_on_operations(draft))
    notes.extend(repair_named_foreign_keys(draft))
    notes.extend(ensure_o2m_inverse_fields(draft))
    notes.extend(reconcile_stale_o2ms(draft))
    notes.extend(promote_booking_headers(draft))
    notes.extend(demote_register_status_workflows(draft))
    notes.extend(scrub_selection_chrome_smart_buttons(draft))
    notes.extend(drop_leftover_state_fields(draft))
    notes.extend(ensure_mail_mixins(draft))
    notes.extend(ensure_header_line_models(draft))
    notes.extend(ensure_reverse_o2ms(draft))
    notes.extend(wire_stock_apps_from_depends(draft))
    notes.extend(ensure_residual_satellites(draft))
    notes.extend(ensure_stock_inherit_bridges(draft))
    notes.extend(ensure_invoice_link_on_headers(draft))
    notes.extend(ensure_relational_smart_buttons(draft))
    notes.extend(drop_hollow_automations(draft))
    notes.extend(ensure_lifecycle_automations(draft))
    notes.extend(humanize_app_surface(draft))

    from app.ai_post_critique import ensure_line_model_parent_links
    from app.ai_enrich import ensure_default_ui, sync_form_archs_to_models
    from app.ai_presentation import group_menus_if_needed

    notes.extend(ensure_line_model_parent_links(draft))
    notes.extend(ensure_default_ui(draft))
    notes.extend(sync_form_archs_to_models(draft))
    notes.extend(group_menus_if_needed(draft, threshold=4))
    notes.extend(humanize_app_surface(draft))
    notes.extend(rebuild_form_transition_headers(draft))
    notes.extend(strip_register_form_headers(draft))
    notes.extend(inject_chatter_on_forms(draft))
    notes.extend(enrich_kanban_cards(draft))
    notes.extend(_hide_line_model_menus(draft))
    notes.extend(sync_security_groups_to_technical_name(draft))
    notes.extend(ensure_root_web_icon(draft, user_prompt=prompt))
    notes.extend(close_odoo_architecture(draft, user_prompt=prompt))
    draft["_odoo_app_bar"] = {"applied": True, "notes": len(notes)}
    return notes


def _hide_line_model_menus(draft: dict[str, Any]) -> list[str]:
    """Line rows and party joins belong on the parent form — not as root app menus."""
    notes: list[str] = []
    action_model = {
        str(a.get("technical_name") or ""): str(a.get("model") or "")
        for a in (draft.get("actions") or [])
        if isinstance(a, dict)
    }
    menus = draft.get("menus")
    if not isinstance(menus, list):
        return notes
    notebook_children = _notebook_child_ids(_models_index(draft))
    kept: list[dict[str, Any]] = []
    for menu in menus:
        if not isinstance(menu, dict):
            continue
        mid = action_model.get(str(menu.get("action_xml_id") or ""), "")
        if mid.endswith("_line"):
            notes.append(f"app_bar: hid line menu for {mid}")
            continue
        if mid.endswith("_party") and mid in notebook_children:
            notes.append(f"app_bar: hid party-join menu for {mid}")
            continue
        kept.append(menu)
    draft["menus"] = kept
    return notes


__all__ = [
    "run_odoo_app_bar_pass",
    "close_odoo_architecture",
    "looks_like_register",
    "short_model_label",
    "senior_sequence_prefix",
    "GENERIC_LOOP_LEAVES",
    "prune_generic_loop_models",
    "prune_stock_clone_models",
    "repair_named_foreign_keys",
    "drop_ghost_menus_and_actions",
    "prefer_prompt_model_names",
    "rename_custom_model",
    "rewrite_foreign_lexicon_fks",
    "collapse_typed_asset_foreign_keys",
    "ensure_booking_engagement_fk",
    "ensure_revision_deliverable_fk",
    "ensure_job_header_children_fk",
    "trim_line_extra_parents",
    "drop_self_relations",
    "collapse_duplicate_line_models",
    "collapse_hollow_cost_headers",
    "collapse_parallel_asset_usage",
    "collapse_redundant_uom_register",
    "drop_duplicate_identical_selections",
    "drop_parent_m2o_when_child_o2m_exists",
    "repair_agreement_party_shape",
    "stamp_session_sale_order_link_only",
    "collapse_parallel_job_headers",
    "canonicalize_draft_selections",
    "demote_workflows_missing_status",
    "drop_foreign_role_fields",
    "_CORRUPT_LABEL_RE",
    "_JOB_HEADER_LEAVES",
    "_job_header_model_ids",
    "_line_primary_parent",
    "_generic_loop_leaf",
    "_is_asset_catalog",
]
