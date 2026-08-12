"""Curated vertical catalog for Odoo Expert — stock modules, custom hints, retrieval keywords."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class VerticalEntry:
    id: str
    title: str
    pattern: re.Pattern[str]
    domain_pack_id: str | None
    stock_modules: tuple[str, ...]
    keywords: tuple[str, ...]
    summary: str


def _pat(expr: str) -> re.Pattern[str]:
    return re.compile(expr, re.I)


VERTICAL_CATALOG: tuple[VerticalEntry, ...] = (
    VerticalEntry(
        id="school_education",
        title="School / Education",
        pattern=_pat(
            r"\b(school|schools|education|student|students|university|college|academy|"
            r"kindergarten|enrollment|enrolment|tuition|gradebook|classroom|teacher|"
            r"campus|sis|learning\s+management|lms|admissions|parent\s+portal)\b"
        ),
        domain_pack_id=None,
        stock_modules=(
            "base",
            "web",
            "contacts",
            "mail",
            "website",
            "website_slides",
            "event",
            "calendar",
            "crm",
            "sale",
            "account",
            "hr",
            "project",
            "survey",
        ),
        keywords=(
            "school",
            "education",
            "student",
            "enrollment",
            "tuition",
            "website_slides",
            "elearning",
            "class",
            "grade",
            "teacher",
            "parent",
            "admissions",
        ),
        summary=(
            "Schools combine Contacts (students/parents/staff), Website + eLearning slides, "
            "CRM for admissions, Sales/Accounting for fees, Events/Calendar for scheduling, "
            "and custom x_ models for classes, grades, and attendance."
        ),
    ),
    VerticalEntry(
        id="car_rental",
        title="Car Rental / Fleet",
        pattern=_pat(
            r"\b(car[\s-]?rental|vehicle[\s-]?rental|fleet[\s-]?rental|"
            r"rent[\s-]?a[\s-]?car|auto[\s-]?hire|car[\s-]?hire)\b"
        ),
        domain_pack_id="car_rental",
        stock_modules=("base", "contacts", "mail", "fleet", "sale", "account"),
        keywords=("car rental", "vehicle", "fleet", "contract", "branch", "odometer"),
        summary="Fleet + Contacts + rental contracts; use the car_rental domain pack for x_ models.",
    ),
    VerticalEntry(
        id="library_management",
        title="Library Management",
        pattern=_pat(
            r"\b(library|libraries|book[\s-]?loan|book[\s-]?catalog|isbn|"
            r"library\s+management|overdue\s+loan|library\s+member|"
            r"circulation|library\s+catalog|book\s+circulation)\b"
        ),
        domain_pack_id="library_management",
        stock_modules=("base", "contacts", "mail", "product"),
        keywords=(
            "library",
            "book",
            "loan",
            "isbn",
            "barcode",
            "overdue",
            "fine",
            "reservation",
            "member",
            "catalog",
            "author",
            "branch",
            "circulation",
            "x_lib_book",
            "x_lib_loan",
            "res.partner",
        ),
        summary=(
            "No stock Library app on Community — Contacts for members (res.partner link-only), "
            "custom x_lib_* models for catalog/circulation; Wizard Library template or "
            "library_management domain pack with fines, reminders, and QWeb receipt."
        ),
    ),
    VerticalEntry(
        id="hospital",
        title="Hospital / Inpatient",
        pattern=_pat(
            r"\b(hospital|inpatient|ward|icu|emergency\s+room|\ber\b|operating\s+theatre|"
            r"pharmacy|radiology|triage|admission|hospital\s+management)\b"
        ),
        domain_pack_id="hospital",
        stock_modules=("base", "contacts", "mail", "hr", "stock", "purchase", "account"),
        keywords=("hospital", "patient", "admission", "ward", "bed", "clinical"),
        summary="Inpatient workflows need custom patient/admission models; hospital domain pack scaffolds them.",
    ),
    VerticalEntry(
        id="clinic",
        title="Clinic / Outpatient",
        pattern=_pat(
            r"\b(clinic|outpatient\s+clinic|medical\s+practice|"
            r"healthcare\s+booking|appointment\s+booking|doctor\s+office)\b"
        ),
        domain_pack_id="clinic",
        stock_modules=("base", "contacts", "mail", "calendar", "crm", "website"),
        keywords=("clinic", "appointment", "patient", "practitioner", "booking"),
        summary="Outpatient clinics lean on Calendar/CRM/Website plus clinic pack models for appointments.",
    ),
    VerticalEntry(
        id="law_firm",
        title="Law Firm / Legal Practice",
        pattern=_pat(
            r"\b(law\s*firm|legal\s+practice|attorney|lawyer|litigation|counsel|"
            r"matter\s+management|billable\s+hour|retainer|trust\s+account)\b"
        ),
        domain_pack_id="law_firm",
        stock_modules=("base", "contacts", "mail", "crm", "project", "sale", "account", "hr_timesheet"),
        keywords=("law firm", "matter", "billable", "retainer", "trust account", "legal"),
        summary="Matters, time entries, and billing — law_firm domain pack plus Project/Timesheet/Accounting.",
    ),
    VerticalEntry(
        id="hotel",
        title="Hotel / Lodging",
        pattern=_pat(
            r"\b(hotel|pms|check[\s-]?in|check[\s-]?out|housekeeping|front\s+desk|"
            r"room\s+booking|lodging|guest\s+folio)\b"
        ),
        domain_pack_id="hotel",
        stock_modules=("base", "contacts", "mail", "sale", "account", "website"),
        keywords=("hotel", "room", "reservation", "folio", "housekeeping", "guest"),
        summary="Room inventory, reservations, and folios — hotel domain pack on Sales/Contacts.",
    ),
    VerticalEntry(
        id="restaurant",
        title="Restaurant / Food Service",
        pattern=_pat(
            r"\b(restaurant|dining|menu|kitchen|food\s+service|table\s+reservation|"
            r"waiter|bistro|cafe|dining\s+order)\b"
        ),
        domain_pack_id="restaurant",
        stock_modules=("base", "contacts", "mail", "sale", "stock", "point_of_sale", "website"),
        keywords=("restaurant", "menu", "table", "order", "kitchen", "pos"),
        summary="POS + inventory for dining; restaurant pack for tables/menus/orders.",
    ),
    VerticalEntry(
        id="real_estate",
        title="Real Estate / Property Rental",
        pattern=_pat(
            r"\b(real\s*estate|rental\s+property|lease\s+management|tenant\s+portal|"
            r"property\s+listing|unit\s+lease|landlord|apartment\s+rental)\b"
        ),
        domain_pack_id="real_estate",
        stock_modules=("base", "contacts", "mail", "crm", "sale", "account", "website"),
        keywords=("real estate", "property", "lease", "tenant", "unit", "listing"),
        summary="Listings, leases, and rent invoicing — real_estate pack plus CRM/Sales.",
    ),
    VerticalEntry(
        id="subscription",
        title="Subscription / Membership",
        pattern=_pat(
            r"\b(subscription|membership\s+plan|renewal\s+workflow|saas\s+plan|"
            r"usage[\s-]?based|member\s+portal|recurring\s+billing)\b"
        ),
        domain_pack_id="subscription",
        stock_modules=("base", "contacts", "mail", "sale", "account", "website"),
        keywords=("subscription", "membership", "renewal", "recurring", "plan"),
        summary="Recurring plans and member portal — subscription pack; verify billing features on Community.",
    ),
    VerticalEntry(
        id="project_tracker",
        title="Professional Services / Project Tracker",
        pattern=_pat(
            r"\b(project\s+tracker|project\s+management|task\s+tracker|milestone|"
            r"time\s+entry|timesheet|pm\s+tool|professional\s+services)\b"
        ),
        domain_pack_id="project_tracker",
        stock_modules=("base", "contacts", "mail", "project", "hr_timesheet", "sale", "account"),
        keywords=("project", "milestone", "timesheet", "task", "billable"),
        summary="Project + timesheets + invoicing from timesheets; project_tracker pack for templates.",
    ),
    VerticalEntry(
        id="field_service",
        title="Field Service / Dispatch",
        pattern=_pat(
            r"\b(field\s+service|job\s+dispatch|work\s*order|technician\s+dispatch|"
            r"service\s+call|maintenance\s+visit)\b"
        ),
        domain_pack_id="field_service",
        stock_modules=("base", "contacts", "mail", "project", "calendar", "sale", "stock"),
        keywords=("field service", "dispatch", "technician", "work order", "job"),
        summary="Dispatch jobs to technicians — field_service pack plus Project/Calendar.",
    ),
    VerticalEntry(
        id="retail_ecommerce",
        title="Retail / eCommerce",
        pattern=_pat(
            r"\b(retail|e[\s-]?commerce|online\s+store|shop|webshop|product\s+catalog|"
            r"point\s+of\s+sale|pos\b|boutique)\b"
        ),
        domain_pack_id=None,
        stock_modules=(
            "base",
            "web",
            "website_sale",
            "sale",
            "stock",
            "purchase",
            "account",
            "contacts",
            "mail",
            "point_of_sale",
        ),
        keywords=("retail", "ecommerce", "website sale", "product", "inventory", "pos"),
        summary="Website Sale + Inventory + POS for retail; standard Odoo stack with minimal custom models.",
    ),
    VerticalEntry(
        id="manufacturing",
        title="Manufacturing / MRP",
        pattern=_pat(
            r"\b(manufacturing|mrp|production\s+order|bill\s+of\s+materials|\bbom\b|"
            r"work\s+center|assembly|factory)\b"
        ),
        domain_pack_id=None,
        stock_modules=(
            "base",
            "stock",
            "purchase",
            "mrp",
            "sale",
            "account",
            "quality",
            "maintenance",
        ),
        keywords=("manufacturing", "mrp", "bom", "production", "work order", "inventory"),
        summary="MRP + Inventory + Purchase; BoMs and work orders are stock Odoo manufacturing apps.",
    ),
    VerticalEntry(
        id="nonprofit",
        title="Nonprofit / NGO",
        pattern=_pat(
            r"\b(nonprofit|non[\s-]?profit|ngo|charity|donation|grant|fundraising|"
            r"volunteer|donor)\b"
        ),
        domain_pack_id=None,
        stock_modules=(
            "base",
            "contacts",
            "mail",
            "crm",
            "website",
            "sale",
            "account",
            "event",
            "survey",
        ),
        keywords=("nonprofit", "donation", "donor", "grant", "fundraising", "volunteer"),
        summary="Donors as Contacts, CRM for grants, Events/Survey for campaigns, Accounting for funds.",
    ),
    VerticalEntry(
        id="logistics",
        title="Logistics / Delivery",
        pattern=_pat(
            r"\b(logistics|warehouse|delivery|shipping|courier|fulfillment|"
            r"distribution|3pl|supply\s+chain)\b"
        ),
        domain_pack_id=None,
        stock_modules=(
            "base",
            "stock",
            "delivery",
            "purchase",
            "sale",
            "account",
            "contacts",
            "fleet",
        ),
        keywords=("logistics", "warehouse", "delivery", "shipping", "inventory", "carrier"),
        summary="Inventory + Delivery carriers + Purchase/Sales; Fleet optional for own trucks.",
    ),
)


def match_verticals(query: str, *, limit: int = 3) -> list[VerticalEntry]:
    """Return catalog entries whose pattern matches the user question."""
    q = (query or "").strip()
    if not q:
        return []
    hits: list[VerticalEntry] = []
    for entry in VERTICAL_CATALOG:
        if entry.pattern.search(q):
            hits.append(entry)
            if len(hits) >= limit:
                break
    return hits


# Odoo developer synonyms appended to retrieval queries (embedding + Jaccard).
_ODOO_TERM_EXPANSIONS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"(?i)\bxpath|view inherit|inheritance"), ("xpath", "ir.ui.view", "position", "inherit")),
    (re.compile(r"(?i)\bmany2one|many2many|one2many|field type"), ("fields", "relation", "comodel")),
    (re.compile(r"(?i)\bautomation|base\.automation|trigger"), ("base.automation", "on_create", "on_write")),
    (re.compile(r"(?i)\baccess rule|ir\.model\.access|record rule"), ("security", "ir.model.access", "groups")),
    (re.compile(r"(?i)\bqweb|report template|pdf report"), ("ir.actions.report", "QWeb", "report")),
    (re.compile(r"(?i)\bcontact|partner|res\.partner"), ("res.partner", "contacts", "partner")),
    (re.compile(r"(?i)\bcomputed|onchange|constraint"), ("computed field", "store", "api.constrains")),
    (re.compile(r"(?i)\bmenu|act_window|window action"), ("ir.ui.menu", "ir.actions.act_window", "action")),
    (re.compile(r"(?i)\bserver action|ir\.actions\.server"), ("server action", "code", "python")),
    (re.compile(r"(?i)\bbulk|mass edit|dedupe|transition"), ("bulk suite", "mass edit", "RPC")),
    (
        re.compile(r"(?i)\bgovernorate|capital governorate|fed\.?\s*states|res\.country\.state"),
        ("res.country.state", "localization", "Jordan", "Kuwait", "l10n_jo", "l10n_kw"),
    ),
    (re.compile(r"(?i)\bstate|province|country states"), ("res.country", "address", "partner")),
)


def _expand_odoo_terms(query: str) -> str:
    extras: list[str] = []
    for pattern, terms in _ODOO_TERM_EXPANSIONS:
        if pattern.search(query):
            extras.extend(terms)
    if not extras:
        return query
    seen: set[str] = set()
    unique: list[str] = []
    for term in extras:
        if term not in seen:
            seen.add(term)
            unique.append(term)
    return f"{query.strip()} {' '.join(unique)}"


def expand_expert_query(query: str) -> str:
    """Append vertical keywords and Odoo developer synonyms for retrieval."""
    base = _expand_odoo_terms(query)
    matches = match_verticals(base, limit=2)
    if not matches:
        return base
    extras: list[str] = []
    for entry in matches:
        extras.append(entry.title)
        extras.extend(entry.keywords[:10])
        extras.append(entry.summary)
    return f"{base.strip()} {' '.join(extras)}"


def catalog_by_id(vertical_id: str) -> VerticalEntry | None:
    for entry in VERTICAL_CATALOG:
        if entry.id == vertical_id:
            return entry
    return None


__all__ = [
    "VerticalEntry",
    "VERTICAL_CATALOG",
    "catalog_by_id",
    "expand_expert_query",
    "match_verticals",
]
