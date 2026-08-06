"""Doc-type registry — model targets, natural keys, classify signals."""

from __future__ import annotations

from app.ingest.schema import DocType

CLASSIFY_MIN_CONFIDENCE = 0.55

# Primary Odoo model per classified document type
DOC_TYPE_PRIMARY_MODEL: dict[DocType, str] = {
    "coa": "account.account",
    "bom": "mrp.bom",
    "product_catalog": "product.template",
    "customer_list": "res.partner",
    "vendor_list": "res.partner",
    "price_list": "product.pricelist.item",
    "employee_roster": "hr.employee",
    "opening_trial_balance": "account.move",
    "inventory_count": "stock.quant",
    "other": "res.partner",
}

NATURAL_KEY_FIELDS: dict[str, list[str]] = {
    "res.partner": ["email", "vat", "name"],
    "product.template": ["default_code", "barcode"],
    "product.product": ["default_code", "barcode"],
    "product.pricelist.item": ["product_id", "min_quantity"],
    "account.account": ["code"],
    "hr.employee": ["work_email", "name"],
    "mrp.bom": ["product_tmpl_id"],
}

# Header tokens (lowercase) that boost each doc type
CLASSIFY_HEADER_SIGNALS: dict[DocType, frozenset[str]] = {
    "coa": frozenset(
        {"account", "code", "gl", "ledger", "debit", "credit", "equity", "asset", "liability"}
    ),
    "bom": frozenset({"bom", "component", "assembly", "quantity", "uom", "part", "material"}),
    "product_catalog": frozenset(
        {"sku", "product", "default_code", "barcode", "list_price", "description", "type"}
    ),
    "customer_list": frozenset({"customer", "email", "phone", "contact", "client", "company"}),
    "vendor_list": frozenset({"vendor", "supplier", "email", "phone", "company"}),
    "price_list": frozenset({"price", "pricelist", "list_price", "qty", "quantity", "tier"}),
    "employee_roster": frozenset({"employee", "department", "manager", "hire", "role", "job"}),
    "opening_trial_balance": frozenset({"trial", "balance", "opening", "debit", "credit"}),
    "inventory_count": frozenset({"inventory", "onhand", "quantity", "location", "stock"}),
    "other": frozenset(),
}

WAGE_LIKE_HEADERS = frozenset(
    {
        "salary",
        "wage",
        "pay",
        "payroll",
        "compensation",
        "bonus",
        "tax",
        "net_pay",
        "gross_pay",
    }
)

# Dependency edges: parent model must exist before child model records
MODEL_DEPENDENCY_EDGES: list[tuple[str, str]] = [
    ("product.category", "product.template"),
    ("product.category", "product.product"),
    ("product.template", "product.product"),
    ("product.template", "product.pricelist.item"),
    ("product.product", "product.pricelist.item"),
    ("product.template", "mrp.bom"),
    ("product.product", "mrp.bom"),
    ("mrp.bom", "mrp.bom.line"),
    ("product.product", "mrp.bom.line"),
    ("res.partner", "account.move"),
    ("account.account", "account.move.line"),
    ("account.account", "account.move"),
    ("product.template", "stock.quant"),
]

FINANCIAL_DOC_TYPES: frozenset[DocType] = frozenset({"coa", "opening_trial_balance"})

# Doc types that must not use generic dry_run_or_commit
OPENING_TB_DOC_TYPE: DocType = "opening_trial_balance"

# Doc types with dedicated commit handlers (not generic dry_run_or_commit)
DEDICATED_COMMIT_DOC_TYPES: frozenset[DocType] = frozenset(
    {"opening_trial_balance", "inventory_count"}
)

# Kept for backward-compatible imports; inventory now has a real path
COMMIT_BLOCKED_DOC_TYPES: frozenset[DocType] = frozenset()

# hr.employee fields we allow from roster extract (org only)
EMPLOYEE_ORG_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "work_email",
        "work_phone",
        "mobile_phone",
        "department_id",
        "job_id",
        "parent_id",
        "coach_id",
        "company_id",
        "user_id",
        "work_contact_id",
        "address_id",
        "private_street",
        "private_city",
        "private_country_id",
        "resource_calendar_id",
    }
)

NotifyMode = str  # "batch_summary" | "individual"
DEFAULT_NOTIFY_MODE = "batch_summary"
