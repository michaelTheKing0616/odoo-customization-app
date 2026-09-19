"""Grain classification + host discovery for component-grain AI (AI-8)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

Grain = Literal["field_pack", "feature_slice", "full_app"]

# Depth floors scaled to grain — field_pack gets minimal scaffolding.
GRAIN_TARGETS: dict[Grain, dict[str, float]] = {
    "field_pack": {
        "min_models": 0,
        "min_fields_avg": 3,
        "min_m2o": 0,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 0,
        "max_entities_staged": 2,
        "allow_root_menu": 0,
        "allow_new_app": 0,
    },
    "feature_slice": {
        "min_models": 0,
        "min_fields_avg": 3,
        "min_m2o": 0,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 1,
        "max_entities_staged": 4,
        "allow_root_menu": 0,
        "allow_sub_menu": 1,
    },
    "full_app": {
        "min_models": 2,
        "min_fields_avg": 3,
        "min_m2o": 1,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 0,
        "max_entities_staged": 6,
        "allow_root_menu": 1,
        "allow_new_app": 1,
    },
}

_STOCK_HOST_WORDS = (
    r"sale|sales|order|orders|quotation|quote|"
    r"task|tasks|project|"
    r"contact|partner|customer|"
    r"invoice|invoices|bill|bills|"
    r"employee|employees|staff|"
    r"calendar|meeting|hearing|"
    r"lead|leads|opportunit(?:y|ies)|crm|"
    r"purchase|po|picking|delivery"
)

_COMPONENT_RE = re.compile(
    r"\b("
    r"add(?:\s+a|\s+an|\s+the|\s+my)?|attach|extend|plug(?:\s+into)?|inherit|"
    r"on\s+(?:my\s+)?(?:" + _STOCK_HOST_WORDS + r")s?|"
    r"to\s+(?:my\s+)?(?:" + _STOCK_HOST_WORDS + r")s?|"
    r"tracker|checklist|warranty|inspection|compliance|expiry|component|"
    r"field\s+pack|smart\s+button"
    r")\b",
    re.I,
)

_FULL_APP_RE = re.compile(
    r"\b("
    r"build\s+(?:an?\s+)?(?:\w+\s+){0,5}app|"
    r"create\s+(?:an?\s+)?(?:\w+\s+){0,5}app|"
    r"tiny\s+(?:\w+\s+){0,3}app|small\s+(?:\w+\s+){0,3}app|"
    r"full\s+app|standalone\s+app|new\s+application|from\s+scratch|"
    r"entire\s+system|complete\s+platform|"
    r"menu\s+under\s+\w+|"
    r"library\s+management|car\s+rental|law\s+firm|hospital|clinic"
    r")\b",
    re.I,
)

_FIELD_PACK_RE = re.compile(
    r"\b("
    r"add\s+(?:an?\s+)?(?:\w+\s+)?field|"
    r"single\s+(?:extra\s+)?field|just\s+(?:a\s+)?field|"
    r"track\s+\w+\s+on|put\s+(?:an?\s+)?\w+\s+on|"
    r"column\s+on|attribute\s+on"
    r")\b",
    re.I,
)

HOST_ALIASES: dict[str, str] = {
    # Technical names first (also matched explicitly below).
    "res.partner": "res.partner",
    "stock.picking": "stock.picking",
    "sale.order": "sale.order",
    "purchase.order": "purchase.order",
    "account.move": "account.move",
    "hr.employee": "hr.employee",
    "calendar.event": "calendar.event",
    "crm.lead": "crm.lead",
    "project.task": "project.task",
    "sale order": "sale.order",
    "sale orders": "sale.order",
    "sales order": "sale.order",
    "sales orders": "sale.order",
    "every sale": "sale.order",
    "each sale": "sale.order",
    "for sales": "sale.order",
    "order": "sale.order",
    "orders": "sale.order",
    "quotation": "sale.order",
    "quotations": "sale.order",
    "quote": "sale.order",
    "sales": "sale.order",
    "project task": "project.task",
    "project tasks": "project.task",
    "task": "project.task",
    "tasks": "project.task",
    "contact": "res.partner",
    "contacts": "res.partner",
    "partner": "res.partner",
    "partners": "res.partner",
    "customer": "res.partner",
    "customers": "res.partner",
    "invoice": "account.move",
    "invoices": "account.move",
    "customer invoice": "account.move",
    "vendor bill": "account.move",
    "vendor bills": "account.move",
    "supplier bill": "account.move",
    "supplier bills": "account.move",
    "bills": "account.move",
    "bill": "account.move",
    "employee": "hr.employee",
    "employees": "hr.employee",
    "calendar": "calendar.event",
    "meeting": "calendar.event",
    "meetings": "calendar.event",
    "hearing": "calendar.event",
    "lead": "crm.lead",
    "leads": "crm.lead",
    "opportunity": "crm.lead",
    "opportunities": "crm.lead",
    "purchase order": "purchase.order",
    "purchase orders": "purchase.order",
    "picking": "stock.picking",
    "delivery": "stock.picking",
}

MODEL_MODULE: dict[str, str] = {
    "sale.order": "sale",
    "project.task": "project",
    "res.partner": "base",
    "account.move": "account",
    "hr.employee": "hr",
    "calendar.event": "calendar",
    "crm.lead": "crm",
    "purchase.order": "purchase",
    "stock.picking": "stock",
}

# Odoo 17–19 root app menus (public xml ids; sale/crm/project differ from menu_{mod}_root).
MODULE_PARENT_MENU: dict[str, str] = {
    "sale": "sale.sale_menu_root",
    "crm": "crm.crm_menu_root",
    "project": "project.menu_main_pm",
    "stock": "stock.menu_stock_root",
    "purchase": "purchase.menu_purchase_root",
    "account": "account.menu_finance",
    "hr": "hr.menu_hr_root",
    "calendar": "calendar.mail_menu_calendar",
}


def parent_menu_xml_id_for_module(mod: str) -> str | None:
    """Return parent ir.ui.menu xml id for a sub-menu under a standard Odoo app."""
    if not mod or mod == "base":
        return None
    if mod in MODULE_PARENT_MENU:
        return MODULE_PARENT_MENU[mod]
    return f"{mod}.menu_{mod}_root"

INHERIT_FORM_XML: dict[str, str] = {
    "sale.order": "sale.view_order_form",
    "project.task": "project.view_task_form2",
    "res.partner": "base.view_partner_form",
    "account.move": "account.view_move_form",
    "hr.employee": "hr.view_employee_form",
    "calendar.event": "calendar.view_calendar_event_form",
    "crm.lead": "crm.crm_lead_view_form",
    "purchase.order": "purchase.purchase_order_form",
    "stock.picking": "stock.view_picking_form",
}

# Prefer a labeled header group so inherit fields are visible (not dumped at sheet end).
INHERIT_FORM_XPATH: dict[str, str] = {
    "account.move": "//group[@id='header_right_group']",
    "sale.order": "//sheet/group[1]",
    "res.partner": "//sheet/group[1]",
    "project.task": "//sheet/group[1]",
    "hr.employee": "//sheet/group[1]",
    "calendar.event": "//sheet/group[1]",
    "crm.lead": "//sheet/group[1]",
    "purchase.order": "//sheet/group[1]",
    "stock.picking": "//sheet/group[1]",
}

HOST_LABELS: dict[str, str] = {
    "sale.order": "Sales",
    "project.task": "Project",
    "res.partner": "Contacts",
    "account.move": "Invoicing",
    "hr.employee": "Employees",
    "calendar.event": "Calendar",
    "crm.lead": "CRM",
    "purchase.order": "Purchase",
    "stock.picking": "Inventory",
}

# Stock act_window xml ids — Open in Odoo after a field pack (no new app tile).
HOST_WINDOW_ACTIONS: dict[str, tuple[str, ...]] = {
    "account.move": (
        "account.action_move_out_invoice_type",
        "account.action_move_out_invoice",
    ),
    "sale.order": (
        "sale.action_quotations_with_onboarding",
        "sale.action_quotations",
        "sale.action_orders",
    ),
    "purchase.order": ("purchase.purchase_rfq", "purchase.purchase_form_action"),
    "res.partner": ("contacts.action_contacts", "base.action_partner_form"),
    "project.task": ("project.action_view_all_task", "project.action_view_task"),
    "hr.employee": ("hr.open_view_employee_list_my", "hr.act_hr_employee"),
    "calendar.event": ("calendar.action_calendar_event",),
    "crm.lead": ("crm.crm_lead_action_pipeline", "crm.action_your_pipeline"),
    "stock.picking": (
        "stock.action_picking_tree_ready",
        "stock.stock_picking_action_picking_type",
    ),
}

_VENDOR_BILL_ACTIONS: tuple[str, ...] = (
    "account.action_move_in_invoice_type",
    "account.action_move_in_invoice",
)


def inherit_open_xml_ids(model: str, prompt: str = "") -> tuple[str, ...]:
    """Window actions that open the stock host — vendor bills vs customer invoices."""
    if model == "account.move":
        text = (prompt or "").lower()
        if re.search(r"\b(vendor\s+bills?|supplier\s+bills?)\b", text):
            return _VENDOR_BILL_ACTIONS
        return HOST_WINDOW_ACTIONS["account.move"]
    return HOST_WINDOW_ACTIONS.get(model, ())



@dataclass
class HostCandidate:
    model: str
    label: str
    score: float
    module: str
    reason: str


_SLICE_RE = re.compile(
    r"\b("
    r"tracker|checklist|register|warranty|inspection|compliance|expiry|"
    r"component|smart\s+button|plug"
    r")\b",
    re.I,
)

# Inherit-only ops extension: reuse stock/existing fields and wire into workflows —
# never a new app tile or companion model, even when "smart button" appears.
_INHERIT_ONLY_OPS_RE = re.compile(
    r"(?i)\b(?:"
    r"no\s+new\s+(?:home[- ]?screen\s+)?app(?:\s+tile)?|"
    r"still\s+inherit[- ]only|inherit[- ]only|"
    r"do\s+not\s+create\s+a\s+new\s+(?:home[- ]?screen\s+)?app|"
    r"already\s+(?:persist|exist)|reuse\s+existing|"
    r"do\s+not\s+recreate|don'?t\s+recreate"
    r")\b"
)
_WIRING_VERBS_RE = re.compile(
    r"(?i)\b(?:"
    r"surface|smart\s+button|domain|filter|automation|"
    r"pickings?|transfers?|wire|extend\s+so"
    r")\b"
)


def is_inherit_only_ops(prompt: str) -> bool:
    """True when the brief reuses/extends a stock host without a new app tile."""
    text = (prompt or "").strip()
    if not text:
        return False
    if not _INHERIT_ONLY_OPS_RE.search(text):
        return False
    # Prefer an explicit host or wiring verbs so we do not swallow unrelated "no new app" notes.
    return bool(named_host_from_prompt(text) or _WIRING_VERBS_RE.search(text))


def classify_grain(prompt: str) -> Grain:
    """Classify prompt grain: field_pack | feature_slice | full_app."""
    text = (prompt or "").strip().lower()
    # New app / menu-under-X briefs win before inherit-slice heuristics.
    if _FULL_APP_RE.search(text) and not is_inherit_only_ops(text):
        return "full_app"
    named = named_host_from_prompt(text)
    # Ops-extension / reuse briefs stay field_pack even when "smart button" matches _SLICE_RE.
    if is_inherit_only_ops(text) and not _FULL_APP_RE.search(text):
        return "field_pack"
    if named and re.search(r"\badd\b", text) and not _FULL_APP_RE.search(text):
        if not _SLICE_RE.search(text):
            return "field_pack"
    if _FIELD_PACK_RE.search(text) and not _COMPONENT_RE.search(text):
        return "field_pack"
    if _COMPONENT_RE.search(text):
        if _FIELD_PACK_RE.search(text) and len(text.split()) < 12:
            return "field_pack"
        # "Add SLA due date on invoices" is inherit-and-wire, not a second Invoices menu.
        if not _SLICE_RE.search(text):
            return "field_pack"
        return "feature_slice"
    # "workflow(s)" / "inventory" as list labels must not force a full app.
    if re.search(
        r"\b(?:manage|management|system|platform)\b|"
        r"\b(?:full\s+)?workflows?\s+(?:app|system|platform)\b|"
        r"\binventory\s+(?:app|system|management)\b",
        text,
    ):
        return "full_app"
    return "full_app"


_SELECTION_OPTIONS_NOISE_RE = re.compile(
    # "selection: Meeting / Delivery / Other" — option labels are not hosts
    r"(?i)selection\s*:\s*[^.;\n]{0,80}"
)
_FIELD_RELATION_NOISE_RE = re.compile(
    r"(?i)(?:"
    r"\bhost\s*\(\s*employees?\s*\)|"
    r"\bcompany\s*\(\s*link\s+to\s+contacts?\s*\)|"
    r"\blink\s+to\s+(?:contacts?|employees?|partners?)\b|"
    r"\(\s*(?:link\s+to\s+)?(?:contacts?|employees?|partners?)\s*\)|"
    r"\b(?:many2one|m2o)\s+to\s+(?:res\.partner|hr\.employee)\b"
    r")"
)
_FIELD_DELIVERY_NOISE_RE = re.compile(
    r"(?i)\b(?:prefer(?:red)?\s+for\s+delivery|delivery\s+notes?|delivery\s+group|"
    r"delivery\s+preferences?)\b"
)
_BARE_DELIVERY_HOST_RE = re.compile(r"(?i)\bdelivery\b")


def named_host_from_prompt(prompt: str) -> str | None:
    """Stock host the operator named — wins over a stale connect-points approval."""
    text = (prompt or "").lower()
    if not text:
        return None
    # Technical models always win when spelled (res.partner, stock.picking, …).
    for model in (
        "res.partner",
        "stock.picking",
        "sale.order",
        "purchase.order",
        "account.move",
        "hr.employee",
        "calendar.event",
        "crm.lead",
        "project.task",
    ):
        if model in text:
            return model
    # Field targets are not the form host: "Host (Employee)", "link to Contact".
    text = _FIELD_RELATION_NOISE_RE.sub(" ", text)
    text = _SELECTION_OPTIONS_NOISE_RE.sub(" ", text)

    # Correction clauses ("wait — actually … on Contacts") — last strong host wins.
    for m in re.finditer(
        r"(?i)(?:wait\s*[—\-–,.]?\s*)?(?:actually|instead)\b(.{0,120})",
        text,
    ):
        tail = m.group(1)
        for phrase, model in sorted(HOST_ALIASES.items(), key=lambda kv: -len(kv[0])):
            if phrase in ("delivery", "picking"):
                continue
            if phrase in tail:
                return model
    scrubbed = _FIELD_DELIVERY_NOISE_RE.sub(" ", text)
    for phrase, model in sorted(HOST_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if phrase == "delivery":
            # Bare "delivery" → picking only when not field-label noise and not
            # already about Contacts/partners.
            if not _BARE_DELIVERY_HOST_RE.search(scrubbed):
                continue
            if re.search(r"(?i)\b(?:contacts?|res\.partner|partners?)\b", text):
                continue
        if phrase == "picking" and "stock.picking" in text:
            return "stock.picking"
        # Word-ish match: avoid 'order' inside 'border'
        if re.search(rf"(?<![a-z0-9_.]){re.escape(phrase)}(?![a-z0-9_])", scrubbed if phrase == "delivery" else text):
            return model
    return None


_MARKUP_HOST_RE = re.compile(r"(?i)mark-?up|withh?olding\s+tax|\bwht\b")
_SALE_DOC_RE = re.compile(
    r"(?i)\b(every\s+sale|each\s+sale|for\s+sales|on\s+sales|sale\s+they|sales?\s+order|quotation)\b"
)
_DELIVERY_HOST_RE = re.compile(
    r"(?i)delivery\s+(?:note|slip)|shipping\s+address"
)


def preferred_inherit_host(prompt: str) -> str | None:
    """Host for Option A inherit seeds — prefer the document, not incidental 'customer'."""
    text = prompt or ""
    named = named_host_from_prompt(text)
    # Explicit partner/Contacts host always wins over delivery-slip / picking noise.
    if named == "res.partner":
        # Markup/sales docs may still redirect below; field-pack partner stays.
        if not (_MARKUP_HOST_RE.search(text) or _SALE_DOC_RE.search(text)):
            return "res.partner"
    # Prefer-for-delivery / Contacts field packs that also mention stock.picking
    # filters still live on Contacts — picking is the list surface, not the form host.
    if re.search(r"(?i)\b(?:contacts?|res\.partner)\b", text) and re.search(
        r"(?i)\bprefer(?:red)?\s+for\s+delivery\b", text
    ):
        if named in {None, "stock.picking", "res.partner"}:
            if not (_MARKUP_HOST_RE.search(text) or _SALE_DOC_RE.search(text)):
                return "res.partner"
    # Explicit host (e.g. Contacts / res.partner) beats delivery-slip heuristic —
    # "Delivery notes" on a partner form is not stock.picking.
    if (
        _DELIVERY_HOST_RE.search(text)
        and named in {None, "stock.picking"}
        and not re.search(r"(?i)\b(?:contacts?|res\.partner|partners?)\b", text)
        and not _FIELD_DELIVERY_NOISE_RE.search(text)
    ):
        return "stock.picking"
    if _MARKUP_HOST_RE.search(text) or _SALE_DOC_RE.search(text):
        if re.search(r"(?i)purchase\s+order", text) and not re.search(r"(?i)\bsales?\b", text):
            return named_host_from_prompt(text)
        return "sale.order"
    if named == "res.partner" and re.search(r"(?i)\b(sales?|quotation|invoices?)\b", text):
        if re.search(r"(?i)\binvoices?\b", text) and not re.search(r"(?i)\bsales?\b", text):
            return "account.move"
        return "sale.order"
    return named


def module_for_model(model: str) -> str:
    if model in MODEL_MODULE:
        return MODEL_MODULE[model]
    if model.startswith("x_"):
        return "base"
    parts = model.split(".")
    return parts[0] if parts else "base"


def discover_hosts(
    prompt: str,
    *,
    available_models: list[str] | None = None,
    saved_specs: list[dict[str, Any]] | None = None,
) -> list[HostCandidate]:
    """Rank candidate host models from prompt + introspection."""
    text = (prompt or "").lower()
    catalog = set(available_models or [])
    for spec in saved_specs or []:
        for m in spec.get("models") or []:
            if isinstance(m, dict) and m.get("model"):
                catalog.add(str(m["model"]))

    candidates: list[HostCandidate] = []

    def add(model: str, score: float, reason: str, *, require_catalog: bool = True) -> None:
        missing = bool(catalog) and model not in catalog
        if missing and require_catalog:
            return
        if missing:
            reason = (
                f"{reason} (not on this database — install "
                f"{module_for_model(model)} before Apply)"
            )
        mod = module_for_model(model)
        candidates.append(
            HostCandidate(
                model=model,
                label=HOST_LABELS.get(model, model),
                score=score,
                module=mod,
                reason=reason,
            )
        )

    for phrase, model in sorted(HOST_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if phrase in text:
            add(model, 0.95, f"prompt mentions {phrase!r}", require_catalog=False)

    for model in catalog:
        if not model or model.startswith("ir."):
            continue
        slug = model.replace(".", " ")
        if slug in text or model.replace(".", "_") in text:
            add(model, 0.7, "technical name in prompt")
        if model.startswith("x_") and any(tok in model for tok in text.split() if len(tok) > 3):
            add(model, 0.55, "custom model fuzzy match")

    # Default stock hosts when component phrasing but no explicit host
    if _COMPONENT_RE.search(text):
        for model in (
            "sale.order",
            "account.move",
            "project.task",
            "res.partner",
            "hr.employee",
            "calendar.event",
            "crm.lead",
        ):
            if model not in {c.model for c in candidates}:
                add(model, 0.35, "default stock host candidate")

    candidates.sort(key=lambda c: -c.score)
    dedup: dict[str, HostCandidate] = {}
    for c in candidates:
        if c.model not in dedup or c.score > dedup[c.model].score:
            dedup[c.model] = c
    return list(dedup.values())[:8]


def grain_display(grain: Grain, host: HostCandidate | None) -> str:
    if grain == "full_app":
        return "Full app"
    host_part = host.label if host else "host TBD"
    if grain == "field_pack":
        return f"Field pack for {host_part}"
    return f"Component for {host_part}"


def architecture_strategy_for_grain(grain: Grain, *, option_a: bool = False) -> str:
    """Map grain (+ Option A) to ``_architecture_plan.strategy`` before model expand."""
    if option_a:
        return "option_a_module"
    if grain == "field_pack":
        return "field_pack"
    if grain == "feature_slice":
        return "feature_slice"
    return "residual_app"


def seed_architecture_plan_stub(
    draft: dict[str, Any],
    *,
    grain: Grain | str,
    prompt: str = "",
    host: HostCandidate | None = None,
    option_a: bool = False,
) -> dict[str, Any]:
    """Early plan IR before LLM expand — refreshed later by ``stamp_architecture_plan``."""
    from app.ai_architecture_plan import stamp_architecture_plan

    g = grain if grain in GRAIN_TARGETS else "full_app"
    draft["grain"] = g
    plan = stamp_architecture_plan(draft, prompt=prompt, rebuild=True)
    plan["strategy"] = architecture_strategy_for_grain(
        g, option_a=option_a  # type: ignore[arg-type]
    )
    if host and host.model:
        hosts = list(plan.get("stock_hosts") or [])
        if host.model not in hosts:
            hosts.insert(0, host.model)
        plan["stock_hosts"] = hosts
    draft["_architecture_plan"] = plan
    return plan
