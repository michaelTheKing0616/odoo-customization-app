"""BOT-RISK-CLASSIFIER: RF-* refusal engine, caps and approval tiers.

Pure policy, no I/O. A Decision (from classifier.classify) plus a GateCtx (what has been
proven for this run) yields Allowed or a Refusal that names the rule and the missing control.
Unknown or unchecked state always refuses (fail-closed).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

Route = Literal["A", "B"]  # A = RPC-only (Odoo Online, hosted); B = direct DB + filestore access

CLASSES = ("R0", "R1", "R2", "R2W", "R3", "R4", "R5", "R6", "R7", "R8", "R8C", "R9")
# R8/R8C rank above R6 so a delete/merge/archive verb never lowers a security/company floor
# (the verb survives as the subkind and keeps its delete checks).
# Severity order used when a task resolves to several effects (wizard chains, server actions).
RANK = {
    c: i
    for i, c in enumerate(
        ("R0", "R1", "R2", "R2W", "R7", "R3", "R6", "R8", "R8C", "R5", "R4", "R9")
    )
}
IRRECOVERABLE = ("R3", "R4", "R5", "R6", "R8", "R8C", "R9")
SUPPORTED_VERSIONS = (17, 18, 19, 20)
BATCH_CAP, RUN_CAP, RATE_CAP_PER_MIN, CLONE_MAX_AGE_H = 50, 500, 10, 24.0

# Controls checked after execution (listed in the decision, never pre-gated).
POST_CONTROLS = frozenset(
    {
        "readback",
        "readback-login-test",
        "rollback-auto",
        "rollback-by-snapshot",
        "rollback-from-snapshot",
        "rollback-from-before-image",
        "no-auto-rollback",
    }
)
# Controls evaluated from GateCtx facts instead of the proven set.
POLICY_CONTROLS = frozenset(
    {
        "audit",
        "kill-switch",
        "size-cap",
        "rate-cap",
        "period-lock-check",
        "transaction-existence-check",
        "prefer-archive",
        "idempotency-key",
        "typed-confirmation",
        "stated-limit",
    }
)
# Route A: these classes/subkinds are undoable by reverse writes from a stored before-image.
_A_REVERSIBLE = {
    ("R2W", None),
    ("R3", None),
    ("R6", "archive"),
    ("R7", None),
    ("R8", None),
    ("R8C", None),
    ("R9", "metadata"),
}
# Route A: kept irreversible -> L3 + typed confirmation + stated limit, strict copy rehearsal.
_A_IRREVERSIBLE = {
    ("R4", None),
    ("R5", None),
    ("R6", "delete"),
    ("R6", "merge"),
    ("R9", "uninstall"),
    ("R7", "module"),
    ("R8", "irr"),
    ("R8C", "irr"),
}
_A_EXTRA = {
    "R5": ("outbox-hold", "mail-server-inactive-on-copy"),
    "R8": ("bot-apikey-kept",),
}


# ---------------------------------------------------------------- sensitivity floor
# One layer applied on every classification path: explicit model and field floors, never
# a model-name prefix. fields=None means "unknown field set" (assume the sensitive one).
MODEL_FLOOR: dict[str, tuple[str, str]] = {
    **{
        m: ("R8", "security")
        for m in (
            "res.users",
            "res.groups",
            "ir.access",
            "ir.model.access",
            "ir.rule",
            "res.users.apikeys",
            "res.users.apikeys.description",
            "res.groups.privilege",
            "res.users.deletion",
            # code that runs later, or auth settings: creation by the Bot needs L3
            "ir.cron",
            "ir.actions.actions",
            "ir.actions.server",
            "ir.actions.act_window",
            "ir.actions.act_window.view",
            "ir.actions.act_url",
            "ir.actions.client",
            "ir.actions.report",
            "ir.actions.todo",
            "base.automation",
            "ir.config_parameter",
            "ir.ui.menu",
        )
    },
    **{
        m: ("R8C", "company")
        for m in (
            "res.company",
            "account.tax",
            "account.tax.repartition.line",
            "account.journal",
            "ir.sequence",
            "ir.sequence.date_range",
            "res.currency",
            "account.fiscal.position",
            "account.fiscal.position.tax",
            "account.fiscal.position.account",
            "account.fiscal.year",
            "account.account",
            "account.account.tag",
            "account.tax.group",
            "account.journal.group",
            "account.lock_exception",
            "account.report",
            "account.report.line",
            "account.report.expression",
            "account.report.column",
            "account.report.external.value",
            "res.country",
            "res.country.state",
            "res.country.group",
            "res.company.ldap",
        )
    },
    "account.chart.template": ("R8C", "irr"),
    **{m: ("R5", "send") for m in ("mail.mail", "sms.sms", "mail.message", "mail.mail.queue")},
}
SECURITY_FIELDS = frozenset(
    {
        "groups_id",
        "group_ids",
        "all_group_ids",
        "users",
        "user_ids",
        "implied_ids",
        "implied_by_ids",
        "password",
        "new_password",
        "login",
        "share",
        "api_key_ids",
        "totp_secret",
        "totp_enabled",
    }
)
SETTINGS_R8C = frozenset(
    {
        "account_fiscal_country_id",
        "chart_template",
        "chart_template_id",
        "currency_id",
        "company_currency_id",
        "currency_exchange_journal_id",
        "country_code",
        "company_country_code",
        "fiscalyear_last_day",
        "fiscalyear_last_month",
        "account_default_credit_limit",
    }
)
# Chart / fiscal-country changes: reverse writes cannot undo them (route A irreversible).
SETTINGS_R8C_IRR = frozenset({"account_fiscal_country_id", "chart_template", "chart_template_id"})
# Valuation / cost posting fields (journal entries follow from them).
FIELD_FLOOR: dict[tuple[str, str], tuple[str, str]] = {
    ("product.product", "standard_price"): ("R4", "valuation"),
    ("product.template", "standard_price"): ("R4", "valuation"),
    ("product.category", "property_cost_method"): ("R4", "valuation"),
    ("product.category", "property_valuation"): ("R4", "valuation"),
}
SETTINGS_R4 = frozenset(
    {
        "fiscalyear_lock_date",
        "period_lock_date",
        "tax_lock_date",
        "sale_lock_date",
        "purchase_lock_date",
        "hard_lock_date",
    }
)
# Models whose `state` write is posting / validation.
STATE_POSTING = frozenset(
    {
        "account.move",
        "account.move.line",
        "account.payment",
        "account.bank.statement.line",
        "stock.picking",
        "stock.move",
        "stock.move.line",
        "stock.scrap",
        "stock.quant",
        "mrp.production",
        "mrp.unbuild",
        "pos.session",
        "pos.order",
        "repair.order",
        "stock.landed.cost",
        "hr.expense",
        "hr.expense.sheet",
        "hr.payslip",
        "hr.payslip.run",
    }
)
POSTING_FIELDS = frozenset(
    {"state", "posted_before", "reconciled", "inventory_quantity", "quantity", "qty_done"}
)


# ---------------------------------------------------------------- derived floors
# Generated into catalogue_rows.json["floors"] by gen_risk_rows.py (which calls
# derive_floors); a test recomputes it and fails on drift. Hand tables above only ADD.
DERIVE_CLASSES = ("R4", "R5", "R6", "R8", "R8C", "R9")
_DEFAULT_SUB = {
    "R4": "post",
    "R5": "send",
    "R6": "delete",
    "R8": "security",
    "R8C": "company",
    "R9": "uninstall",
}
_BULK_VERBS = ("delete", "import", "mass-write")  # verb paths with their own controls


def derive_floors(groups: Mapping[str, list[str]], irreversible: Iterable[str]) -> dict[str, Any]:
    """Every catalogue row of class R4/R5/R6/R8/R8C/R9 floors its model/method/key."""
    irr = set(irreversible)
    out: dict[str, dict[str, list[Any]]] = {
        k: {} for k in ("model", "unlink", "method", "param", "module")
    }
    top: dict[str, str] = {}
    state_models: set[str] = set()
    posting_models: set[str] = set()

    def put(tab: str, key: str, cls: str, rid: str) -> None:
        cur = out[tab].get(key)
        if cur is None or RANK[cls] > RANK[cur[0]]:
            out[tab][key] = [cls, rid in irr]
        elif cls == cur[0] and rid in irr:
            cur[1] = True

    for gk, ids in groups.items():
        cls = gk.split("|")[0]
        high = cls in DERIVE_CLASSES
        for rid in ids:
            kind, _, rest = rid.partition(":")
            if kind == "m":
                model, _, verb = rest.partition(":")
                if verb == "workflow:state":
                    state_models.add(model)
                if verb not in _BULK_VERBS and RANK[cls] > RANK[top.get(model, "R0")]:
                    top[model] = cls
                top.setdefault(model, "R0")
                if high:
                    put("unlink" if verb == "delete" else "model", model, cls, rid)
            elif not high:
                continue
            elif kind in ("b", "wiz"):
                model, _, meth = rest.rpartition(":")
                put("method", f"{model}:{meth}", cls, rid)
                if kind == "b" and cls == "R4":
                    posting_models.add(model)
            elif kind == "g":
                put("model", "res.groups", cls, rid)
            elif kind == "seq":
                put("model", "ir.sequence", cls, rid)
            elif kind == "param":
                put("param", rest, cls, rid)
            elif kind == "mod":
                put("module", rest, cls, rid)
    doc: dict[str, Any] = {k: dict(sorted(v.items())) for k, v in out.items()}
    doc["state_posting"] = sorted(state_models & posting_models)
    doc["low_risk_models"] = sorted(
        m for m, c in top.items() if RANK[c] <= RANK["R2W"] and m not in out["model"]
    )
    return doc


# ---------------------------------------------------------------- field floors (live metadata)
# Derived from fields_inventory.csv (every field of every version) by structure: comodel,
# type, mail.thread membership, and a short reviewed list of identity / valuation fields.
R8_COMODELS = frozenset(
    {
        "res.users",
        "res.groups",
        "ir.rule",
        "ir.model.access",
        "ir.access",
        "ir.cron",
        "res.users.apikeys",
        "ir.config_parameter",
    }
)
R8C_COMODELS = frozenset({"res.company", "res.currency", "account.tax", "ir.sequence"})
MAIL_COMODELS = frozenset({"mail.activity", "mail.followers", "mail.message", "mail.mail"})
MAGIC_FIELDS = frozenset({"create_uid", "write_uid", "create_date", "write_date", "id"})
PUBLISH_FIELDS = frozenset({"is_published", "website_published"})
IDENTITY_FIELDS: dict[str, frozenset[str]] = {
    "res.partner": frozenset(
        {
            "email",
            "email_normalized",
            "phone",
            "mobile",
            "phone_sanitized",
            "user_ids",
            "vat",
            "bank_ids",
        }
    ),
    "res.partner.bank": frozenset(
        {
            "acc_number",
            "sanitized_acc_number",
            "bank_id",
            "partner_id",
            "acc_holder_name",
            "allow_out_payment",
        }
    ),
    "hr.employee": frozenset(
        {"user_id", "work_email", "private_email", "bank_account_id", "work_contact_id"}
    ),
}
VALUATION_FIELDS: dict[str, frozenset[str]] = {
    "stock.location": frozenset(
        {"usage", "valuation_in_account_id", "valuation_out_account_id", "scrap_location"}
    ),
    "uom.uom": frozenset(
        {"factor", "factor_inv", "rounding", "uom_type", "relative_factor", "relative_uom_id"}
    ),
}
# Credential / secret / environment fields, matched on whole name tokens (structure of the
# inventory name, not the model): e.g. stripe_secret_key, provider_ref, prod_environment.
CREDENTIAL_TOKENS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "key",
        "token",
        "credential",
        "credentials",
        "api",
        "apikey",
        "oauth",
        "otp",
        "totp",
        "environment",
        "terminal",
        "webhook",
    }
)
# Fail-closed stem match on the lowercased field name (substring, not words).
CREDENTIAL_STEMS = (
    "pass",
    "pwd",
    "secret",
    "token",
    "key",
    "cert",
    "pem",
    "signature",
    "otp",
    "bic",
    "iban",
    "swift",
    "acc_number",
    "account_number",
    "client_id",
    "client_identifier",
    "endpoint",
    "cdn",
    "smtp_user",
    "smtp_ssl",
    # round 6: security switches / irreversible integrity
    "auth_",
    "authoriz",
    "signup",
    "invite",
    "sid",
    "redirect",
    "force_",
    "lock",
    "hash",
    "totp",
    "2fa",
    "portal",
    "public",
    "private_",
)
# Stems that only count on security-config models.
SCOPED_STEMS = {
    "domain": ("website", "mail", "res.config.settings"),
    "session": ("res.users", "ir.", "auth", "res.config.settings"),
    "allow_": ("res.config.settings",),
    "enable_": ("res.config.settings",),
}
URL_SENSITIVE_MODELS = ("ir.mail_server", "website", "ir.attachment")
# Reviewed SAFE exceptions to the stem match: (model prefixes or () for any, stem, reason).
CREDENTIAL_SAFE: tuple[tuple[tuple[str, ...], str, str], ...] = (
    ((), "website_meta_keywords", "SEO keywords text"),
    (
        ("hr.", "slide.", "survey.", "digest.", "res.partner"),
        "certif",
        "skill/course certification or education level, not a crypto certificate",
    ),
    ((), "delay_pass", "report delay metric"),
    ((), "deadline_passed", "lunch deadline flag"),
    ((), "cubic", "volume unit setting (cu-bic)"),
    ((), "_count", "computed counter"),
    ((), "kpi_", "digest KPI toggle"),
    (("account.",), "_key", "computed grouping/allocation key on accounting lines"),
    (("pos.printer",), "paper_size_keys", "printer paper sizes"),
    (("discuss.",), "avatar_cache_key", "avatar cache buster"),
    ((), "residual", "accounting residual amount (re-sid-ual)"),
    ((), "side", "UI layout/sidebar flag"),
    ((), "are_you_inside", "survey answer flag"),
    (
        ("mrp.", "project.", "hr.", "crm.", "mail.", "sale.", "purchase.", "helpdesk."),
        "block",
        "kanban/workorder blocked state, not access",
    ),
    ((), "legend_blocked", "kanban legend label"),
    ((), "force_send", "send-now toggle on composer"),
    ((), "enforce_cities", "address form option"),
    ((), "force_tax_included", "tax display option"),
    ((), "force_assignment", "planning assignment option"),
    ((), "public_holiday", "leave computation option"),
    ((), "birthday_public", "employee birthday display"),
    ((), "public_categ", "eCommerce category link"),
    ((), "public_description", "public product/job text"),
    ((), "authorized_amount", "payment amount figure"),
    ((), "amount_authorized", "payment amount figure"),
    ((), "pos_session", "POS session link on settings"),
)
# Models where every field takes the model floor unless reviewed SAFE (labels/display).
SENSITIVE_MODELS = frozenset(
    {
        "ir.mail_server",
        "fetchmail.server",
        "res.partner.bank",
        "res.bank",
        "payment.provider",
        "payment.token",
        "auth.oauth.provider",
        "auth.passkey.key",
        "delivery.carrier",
        "pos.payment.method",
        "website.rewrite",
        "google.calendar.credentials",
        "microsoft.calendar.credentials",
        "calendar.provider.config",
        "mail.push.device",
        "mail.partner.device",
        "iap.account",
        "res.company.ldap",
        "res.users.settings",
    }
)
SENSITIVE_SAFE_FIELDS = frozenset({"name", "sequence", "active", "display_name", "color"})


def credential_safe(model: str, field: str) -> str | None:
    """Reviewed reason a stem-matched field is not a credential, or None."""
    lf = field.lower()
    for prefixes, stem, reason in CREDENTIAL_SAFE:
        if stem in lf and (not prefixes or model.startswith(prefixes)) and "smtp" not in lf:
            return reason
    return None


def known_unsafe(fields: frozenset[str]) -> bool:
    return bool(fields - SENSITIVE_SAFE_FIELDS)


def credential_match(model: str, field: str) -> bool:
    lf = field.lower()
    if any(st in lf for st in CREDENTIAL_STEMS):
        return True
    if any(st in lf and model.startswith(pre) for st, pre in SCOPED_STEMS.items()):
        return True
    return "url" in lf and (model in URL_SENSITIVE_MODELS or "peppol" in model)


def is_sensitive_model(model: str) -> bool:
    return model in SENSITIVE_MODELS or "peppol" in model


CREDENTIAL_FIELDS = frozenset({"provider_ref", "acquirer_ref", "client_id", "smtp_host"})
REDIRECT_FIELDS = frozenset({"url_from", "url_to", "redirect_type"})
PRODUCT_VALUATION_FIELDS = frozenset(
    {
        "standard_price",
        "cost_method",
        "valuation",
        "property_cost_method",
        "property_valuation",
        "property_stock_valuation_account_id",
        "property_stock_account_input_categ_id",
        "property_stock_account_output_categ_id",
    }
)


def field_rule(model: str, field: str, ftype: str, rel: str) -> tuple[str, str] | None:
    """The structural floor of one inventory field (None = no sensitive rule matches)."""
    if field in MAGIC_FIELDS:
        return None
    c: list[tuple[str, str]] = []
    if rel in R8_COMODELS or rel.startswith("ir.actions."):
        c.append(("R8", "security"))
    if rel in R8C_COMODELS:
        c.append(("R8C", "company"))
    if rel in MAIL_COMODELS or rel.startswith("mail.alias"):
        c.append(("R5", "send"))
    if model in MAIL_COMODELS:
        c.append(("R5", "send"))
    if model.startswith(("mail.alias", "fetchmail.")):  # inbound routing / mail credentials
        c.append(("R8", "security"))
    if model == "mail.template" and ftype in ("html", "char", "text"):  # rendered QWeb
        c.append(("R8", "security"))
    if model == "website" or model.startswith("website."):
        if field in ("domain", "url"):
            c.append(("R8", "security"))
        if ftype in ("html", "binary"):
            c.append(("R5", "send"))
    if set(field.split("_")) & CREDENTIAL_TOKENS or field in CREDENTIAL_FIELDS:
        c.append(("R8", "security"))
    if "hash" in field and field.startswith("force_"):
        c.append(("R4", "irr"))
    elif credential_match(model, field) and not credential_safe(model, field):
        c.append(("R8", "security"))
    if is_sensitive_model(model) and field not in SENSITIVE_SAFE_FIELDS:
        c.append(("R8", "security"))
    if model == "website.rewrite" and field in REDIRECT_FIELDS:  # redirect hijack
        c.append(("R8", "security"))
    if field in PUBLISH_FIELDS:
        c.append(("R8", "security"))
    if field in IDENTITY_FIELDS.get(model, ()):
        c.append(("R8", "security"))
    if field in VALUATION_FIELDS.get(model, ()) or (
        model.startswith("product.") and field in PRODUCT_VALUATION_FIELDS
    ):
        c.append(("R4", "valuation"))
    out: tuple[str, str] | None = None
    for x in c:
        out = max_floor(out, x)
    return out


def derive_field_floors(rows: Iterable[Mapping[str, str]]) -> dict[str, Any]:
    fields: dict[str, list[str]] = {}
    threads: set[str] = set()
    inv: dict[str, set[str]] = {}
    for r in rows:
        m, f = r["model"], r["field"]
        inv.setdefault(m, set()).add(f)
        if f in ("message_ids", "message_follower_ids", "activity_ids"):
            threads.add(m)
        fl = field_rule(m, f, r["type"], r.get("relation") or "")
        if fl:
            k = f"{m}:{f}"
            cur = fields.get(k)
            fields[k] = list(max_floor(tuple(cur) if cur else None, fl))  # type: ignore[arg-type]
    # provider-style state: `state` on a model that holds credentials (enabled/test/prod)
    cred = {k.split(":")[0] for k, v in fields.items() if v[1] == "security"}
    for m in cred:
        if "state" in inv[m] and f"{m}:state" not in fields:
            fields[f"{m}:state"] = ["R8", "security"]
    return {
        "fields": dict(sorted(fields.items())),
        "mail_thread": sorted(threads),
        "models": sorted(inv),
        "inventory": {m: " ".join(sorted(v)) for m, v in sorted(inv.items())},
    }


def _fl(entry: list[Any]) -> tuple[str, str]:
    cls, irr = entry
    return cls, "irr" if irr and cls in ("R8", "R8C") else _DEFAULT_SUB[cls]


def max_floor(a: tuple[str, str] | None, b: tuple[str, str]) -> tuple[str, str]:
    if a is None or RANK[b[0]] > RANK[a[0]]:
        return b
    return b if RANK[b[0]] == RANK[a[0]] and b[1] == "irr" else a


DERIVED: dict[str, Any] = json.loads(Path(__file__).with_name("catalogue_rows.json").read_text())[
    "floors"
]
MODEL_FLOORS: dict[str, tuple[str, str]] = {m: _fl(e) for m, e in DERIVED["model"].items()}
for _m, _f in MODEL_FLOOR.items():
    MODEL_FLOORS[_m] = max_floor(MODEL_FLOORS.get(_m), _f)
UNLINK_FLOORS = {m: _fl(e) for m, e in DERIVED["unlink"].items()}
METHOD_FLOORS = {k: _fl(e) for k, e in DERIVED["method"].items()}
PARAM_FLOORS = {k: _fl(e) for k, e in DERIVED["param"].items()}
MODULE_FLOORS = {k: _fl(e) for k, e in DERIVED["module"].items()}
STATE_POSTING_ALL = STATE_POSTING | frozenset(DERIVED["state_posting"])
# Default-deny for code paths: OPT-IN reviewed allowlist, one rationale per model. Each
# entry must pass structurally_low_risk (tested); grows only via regression fixtures.
REVIEWED_LOW_RISK: dict[str, str] = {
    "res.partner.category": "contact tag label",
    "res.partner.industry": "industry label",
    "res.partner.title": "salutation label",
    "product.tag": "product tag label",
    "product.attribute": "variant attribute name/display",
    "product.attribute.value": "attribute value label",
    "crm.tag": "lead tag label",
    "crm.stage": "pipeline stage label/sequence",
    "crm.lost.reason": "lost-reason label",
    "project.tags": "task tag label",
    "hr.employee.category": "employee tag label",
    "hr.skill": "skill name",
    "hr.skill.level": "skill level label",
    "hr.skill.type": "skill type label",
    "fleet.vehicle.tag": "vehicle tag label",
    "repair.tags": "repair tag label",
    "slide.tag": "course tag label",
    "blog.tag": "blog tag label (not published content)",
    "event.stage": "event stage label",
    "maintenance.stage": "maintenance stage label",
    "pos.category": "POS menu category label",
    "calendar.event.type": "meeting tag label",
    "return.reason": "return reason label",
    "mrp.workcenter.tag": "work-centre tag label",
}
FIELD_DERIVED: dict[str, Any] = json.loads(
    Path(__file__).with_name("catalogue_rows.json").read_text()
)["field_floors"]
FIELD_FLOORS: dict[str, tuple[str, str]] = {
    k: (v[0], v[1]) for k, v in FIELD_DERIVED["fields"].items()
}
for (_m, _f), _v in FIELD_FLOOR.items():  # hand extras only add
    FIELD_FLOORS[f"{_m}:{_f}"] = max_floor(FIELD_FLOORS.get(f"{_m}:{_f}"), _v)
MODEL_FIELD_MAX: dict[str, tuple[str, str]] = {}
for _k, _v in FIELD_FLOORS.items():
    _mm = _k.split(":")[0]
    MODEL_FIELD_MAX[_mm] = max_floor(MODEL_FIELD_MAX.get(_mm), _v)
MAIL_THREAD = frozenset(FIELD_DERIVED["mail_thread"])
INVENTORY_MODELS = frozenset(FIELD_DERIVED["models"])
INVENTORY_FIELDS: dict[str, frozenset[str]] = {
    m: frozenset(v.split()) for m, v in FIELD_DERIVED["inventory"].items()
}


def unknown_fields(model: str, fields: frozenset[str]) -> frozenset[str]:
    """Fields not in the live inventory for the model (any version): never classified."""
    return fields - INVENTORY_FIELDS.get(model, frozenset())


def structurally_low_risk(model: str) -> bool:
    """No sensitive field, not a mail.thread model, no model/state floor; known to inventory."""
    return (
        model in INVENTORY_MODELS
        and model not in MODEL_FIELD_MAX
        and model not in MAIL_THREAD
        and model not in MODEL_FLOORS
        and model not in STATE_POSTING_ALL
        and model != "res.config.settings"
    )


# Regression-fixture additions only (each needs a fixture proving it low-risk).
EXTRA_LOW_RISK: frozenset[str] = frozenset()
LOW_RISK_MODELS = frozenset(REVIEWED_LOW_RISK) | EXTRA_LOW_RISK


def sensitivity_floor(
    model: str, fields: frozenset[str] | None, verb: str | None = None
) -> tuple[str, str] | None:
    """fields=None means 'unknown field set' (assume the sensitive one)."""
    cands: list[tuple[str, str]] = []
    if model in MODEL_FLOORS:
        cands.append(MODEL_FLOORS[model])
    if is_sensitive_model(model) and (fields is None or known_unsafe(fields)):
        cands.append(("R8", "security"))
    if verb == "unlink" and model in UNLINK_FLOORS:
        cands.append(UNLINK_FLOORS[model])
    known = fields or frozenset()
    if known & SECURITY_FIELDS:
        cands.append(("R8", "security"))
    if fields is None:
        # unknown field set: worst field floor, unless an explicit model floor already
        # names the model's risk (keeps e.g. R8 lockout controls on res.users)
        if model in MODEL_FIELD_MAX and model not in MODEL_FLOORS:
            cands.append(MODEL_FIELD_MAX[model])
    else:
        cands += [FIELD_FLOORS[f"{model}:{f}"] for f in known if f"{model}:{f}" in FIELD_FLOORS]
    if model == "res.config.settings":
        if fields is None:
            cands += [("R8C", "irr"), ("R4", "lock-date")]
        if known & SETTINGS_R8C:
            cands.append(("R8C", "company"))
        if known & SETTINGS_R8C_IRR:
            cands.append(("R8C", "irr"))
        if any(f.startswith("group_") for f in known):  # implies groups for every user
            cands.append(("R8", "security"))
        if known & SETTINGS_R4:
            cands.append(("R4", "lock-date"))
    if model in STATE_POSTING_ALL and (fields is None or known & POSTING_FIELDS):
        cands.append(("R4", "post"))
    out: tuple[str, str] | None = None
    for c in cands:
        out = max_floor(out, c)
    return out


def method_floor(model: str, method: str) -> tuple[str, str] | None:
    return METHOD_FLOORS.get(f"{model}:{method}")


_KEEP_SUB = ("delete", "merge", "archive", "reset-draft", "uninstall")


def apply_floor(cls: str, sub: str | None, floor: tuple[str, str] | None) -> tuple[str, str | None]:
    """MAX(path class, floor); the path's verb subkind survives so its checks still run."""
    if floor is None or RANK[floor[0]] <= RANK[cls]:
        return cls, sub
    return floor[0], sub if sub in _KEEP_SUB else floor[1]


def rank(cls: str) -> int:
    return RANK[cls]


def worst(classes: list[str]) -> str:
    return max(classes, key=rank)


@dataclass(frozen=True)
class Refusal:
    rule: str
    missing: str
    reason: str
    allowed: bool = False

    def text(self) -> str:
        return f"{self.rule} [{self.missing}] {self.reason}"[:200]


@dataclass(frozen=True)
class Allowed:
    task_id: str
    tier: int
    allowed: bool = True


@dataclass(frozen=True)
class Policy:
    batch_cap: int = BATCH_CAP
    run_cap: int = RUN_CAP
    tiers: Mapping[str, int] = field(default_factory=dict)  # per-class tier raise/lower


DEFAULT_POLICY = Policy()


def apply_override(base: Policy, override: Mapping[str, Any], approval: int) -> Policy | Refusal:
    """Per-client override: may only tighten, unless the override itself is approved at L3."""
    unknown = set(override) - {"batch_cap", "run_cap", "tiers"}
    if unknown:
        return Refusal("RF-POLICY", "override", f"unknown keys {sorted(unknown)}")
    new, loosen = base, []
    for key in ("batch_cap", "run_cap"):
        if key in override:
            v = override[key]
            if not isinstance(v, int) or isinstance(v, bool) or v < 1:
                return Refusal("RF-POLICY", "override", f"{key} must be a positive int")
            if v > getattr(base, key):
                loosen.append(key)
            new = replace(new, **{key: v})
    tiers = dict(base.tiers)
    for cls, t in dict(override.get("tiers") or {}).items():
        if cls not in CLASSES or t not in (1, 2, 3):
            return Refusal("RF-POLICY", "override", f"bad tier {cls}={t}")
        if t < tiers.get(cls, base_tier(cls)):
            loosen.append(f"tier {cls}")
        tiers[cls] = t
    if loosen and approval < 3:
        return Refusal("RF-POLICY", "human-approve-L3", f"override loosens {loosen} without L3")
    return replace(new, tiers=tiers)


_CATALOGUE_TIER = {
    "R0": 1,
    "R1": 1,
    "R2": 1,
    "R2W": 1,
    "R3": 2,
    "R4": 2,
    "R5": 2,
    "R6": 3,
    "R7": 2,
    "R8": 3,
    "R8C": 3,
    "R9": 3,
}


def base_tier(cls: str) -> int:
    return _CATALOGUE_TIER[cls]


def a_kind(cls: str, subkind: str | None) -> str:
    """Route A: 'rev' = undoable by reverse writes from a before-image; 'irr' = not."""
    if subkind in ("delete", "merge"):
        return "irr"
    for key in ((cls, subkind), (cls, None)):
        if key in _A_REVERSIBLE:
            return "rev"
        if key in _A_IRREVERSIBLE:
            return "irr"
    return "irr" if cls in IRRECOVERABLE else "rev"


def strict_copy(cls: str, subkind: str | None, route: Route) -> bool:
    """Must the rehearsal run on a copy, or may a proven batch-1 undo stand in (route A)?"""
    return route == "B" or a_kind(cls, subkind) == "irr" or cls in ("R8", "R8C")


def hard_floor(cls: str, subkind: str | None, route: Route) -> int:
    """Tier no override can lower: RF rules that demand L3, and route-A irreversibles."""
    if cls in ("R6", "R8", "R8C", "R9"):
        return 3
    if route == "A" and a_kind(cls, subkind) == "irr":
        return 3
    return 1


def route_controls(cls: str, subkind: str | None, route: Route, base: list[str]) -> list[str]:
    """Catalogue controls for the class, rewritten for the route (BOT-SNAPSHOT/CLONE cards)."""
    out = [c for c in base if not c.startswith("human-approve-")]
    if subkind in ("delete", "merge"):
        out += ["cascade-graph-count", "prefer-archive"]
    if cls == "R9" and subkind == "uninstall":
        out.append("uninstall-preview")
    if route == "B":
        return _dedupe(out)
    reversible = a_kind(cls, subkind) == "rev"
    res: list[str] = []
    for c in out:
        if c == "clone-rehearsal":
            res.append("copy-rehearsal")
        elif c == "snapshot-proof":
            if reversible:
                res += ["before-image", "batch1-undo-proof"]
        elif c in ("rollback-by-snapshot", "rollback-from-snapshot"):
            res.append("rollback-from-before-image" if reversible else "no-auto-rollback")
        else:
            res.append(c)
    if cls in ("R2W", "R3", "R7", "R8", "R8C") or (cls, subkind) in _A_REVERSIBLE:
        if reversible and "before-image" not in res:
            res += ["before-image", "batch1-undo-proof"]
    res += list(_A_EXTRA.get(cls, ()))
    if not reversible:
        res += ["typed-confirmation", "stated-limit"]
    return _dedupe(res)


def required_tier(cls: str, subkind: str | None, route: Route, policy: Policy) -> int:
    return max(policy.tiers.get(cls, base_tier(cls)), hard_floor(cls, subkind, route))


def _dedupe(xs: list[str]) -> list[str]:
    seen: list[str] = []
    for x in xs:
        if x not in seen:
            seen.append(x)
    return seen


@dataclass(frozen=True)
class GateCtx:
    """Facts for one run. None means 'not checked' and refuses for the control that needs it."""

    route: Route
    version: int
    connection_id: str | None = None
    db_name: str = ""
    is_prod: bool = True
    kill_switch: bool | None = None
    fingerprint_ok: bool = False
    proven: frozenset[str] = frozenset()
    outside_plan_fields: frozenset[str] = frozenset()  # RouteA.outside_plan (rule OPR)
    approval: int = 0
    typed_confirmation: str | None = None
    stated_limit_ack: bool = False
    blast_count: int | None = None
    batch_size: int | None = None
    run_size: int | None = None
    rate_per_min: int | None = None
    clone_age_h: float | None = None
    period_locked: bool | None = None
    transactions_exist: bool | None = None
    data_impact_report: bool = False
    archive_possible: bool | None = None
    has_dependents: bool | None = None
    admins_after: int | None = None
    removes_bot_access: bool | None = None
    duplicate_db_route: bool = False  # a full DB duplicate exists to fall back to
    idempotency_key: str | None = None
    policy: Policy = DEFAULT_POLICY


def _looser(p: Policy) -> bool:
    return (
        p.batch_cap > BATCH_CAP
        or p.run_cap > RUN_CAP
        or any(t < base_tier(c) for c, t in p.tiers.items() if c in _CATALOGUE_TIER)
    )


def _evaluate(decision: Any, ctx: GateCtx) -> Allowed | Refusal:
    """Evaluate every RF rule for a classified Decision. First failing rule wins. Private:
    callers use ``gate_with_proofs`` (proof-backed controls need a verifier, never a name)."""
    cls, sub = decision.cls, decision.subkind
    rf = f"RF-{cls}" if cls in IRRECOVERABLE else "RF-CTRL"
    # RF-ANY
    if ctx.version not in SUPPORTED_VERSIONS:
        return Refusal("RF-ANY", "version", f"Odoo {ctx.version} outside 17-20")
    if ctx.version != decision.version or ctx.route != decision.route:
        return Refusal("RF-ANY", "fingerprint", "decision was classified for another target")
    if ctx.kill_switch is None:
        return Refusal("RF-ANY", "kill-switch", "kill switch state not checked")
    if ctx.kill_switch:
        return Refusal("RF-ANY", "kill-switch", "kill switch is on")
    if not ctx.fingerprint_ok:
        return Refusal("RF-ANY", "fingerprint", "DB fingerprint does not match approved target")
    if decision.mitigation_refusal:
        return Refusal(rf, "counter-document", decision.mitigation_refusal)
    if _looser(ctx.policy) and ctx.approval < 3:
        return Refusal("RF-POLICY", "human-approve-L3", "policy looser than default without L3")
    # Class-specific facts (each refusal names the missing control or the violated limit)
    if cls == "R4":
        if sub == "reset-draft" and ctx.is_prod:
            return Refusal("RF-R4", "counter-document", "never reset posted entries on prod")
        if ctx.period_locked is None:
            return Refusal("RF-R4", "period-lock-check", "lock dates not checked")
        if ctx.period_locked:
            return Refusal("RF-R4", "period-lock-check", "target date is in a locked period")
    if cls == "R5":
        if ctx.rate_per_min is None:
            return Refusal("RF-R5", "rate-cap", "send rate not declared")
        if ctx.rate_per_min > RATE_CAP_PER_MIN:
            return Refusal("RF-R5", "rate-cap", f"rate {ctx.rate_per_min}/min > {RATE_CAP_PER_MIN}")
    if sub in ("delete", "merge"):
        if ctx.archive_possible is None:
            return Refusal("RF-R6", "prefer-archive", "archive possibility not checked")
        if ctx.archive_possible:
            return Refusal("RF-R6", "prefer-archive", "hard delete refused: archive is possible")
        if ctx.route == "A" and ctx.has_dependents is not False:
            return Refusal(
                "RF-R6", "cascade-graph-count", "hard delete with dependents (or unknown)"
            )
    if cls == "R8":
        if ctx.admins_after is None or ctx.removes_bot_access is None:
            return Refusal("RF-R8", "lockout-simulation", "admin/Bot access after change unknown")
        if ctx.admins_after < 1:
            return Refusal("RF-R8", "lockout-simulation", "would leave no working admin")
        if ctx.removes_bot_access:
            return Refusal("RF-R8", "lockout-simulation", "removes the Bot's own access")
    if cls == "R8C" and sub == "irr" and decision.route == "A" and not ctx.duplicate_db_route:
        return Refusal(
            "RF-R8C", "duplicate-db-route", "chart/fiscal-country change on RPC-only target"
        )
    if cls == "R8C":
        if ctx.transactions_exist is None:
            return Refusal("RF-R8C", "transaction-existence-check", "transactions not checked")
        if ctx.transactions_exist and not (ctx.approval >= 3 and ctx.data_impact_report):
            return Refusal("RF-R8C", "data-impact-report", "transactions exist; needs L3 + report")
    # Rule OPR (outside-plan review): an apply that changed stored fields outside the planned
    # set (write overrides, stored computes) stays fully undoable but needs a human at L2+.
    if ctx.outside_plan_fields and ctx.approval < 2:
        fs = ", ".join(sorted(ctx.outside_plan_fields)[:5])
        return Refusal(rf, "outside-plan-review", f"apply changed fields outside plan: {fs}")
    if "idempotency-key" in decision.controls and not ctx.idempotency_key:
        return Refusal(rf, "idempotency-key", "no idempotency key")
    # Proven controls
    for c in decision.controls:
        if c in POST_CONTROLS or c in POLICY_CONTROLS:
            continue
        if (
            c == "copy-rehearsal"
            and not decision.strict_copy
            and {"batch1-undo-proof", "full-image-proof"} <= ctx.proven
        ):  # only a full-image proof (nothing outside the plan, all restorable) stands in
            continue
        if c not in ctx.proven:
            return Refusal(rf, c, f"control {c} not proven")
        if (
            c in ("clone-rehearsal", "copy-rehearsal")
            and cls in ("R4", "R8C", "R9")
            and (ctx.clone_age_h is None or ctx.clone_age_h > CLONE_MAX_AGE_H)
        ):
            return Refusal(rf, c, f"rehearsal copy older than {CLONE_MAX_AGE_H:g}h or undated")
    # Size caps (batch cap is absolute; run cap needs L3 to exceed)
    needs_size = cls in ("R3", "R4", "R6") or "size-cap" in decision.controls
    if needs_size or ctx.batch_size is not None:
        if ctx.batch_size is None or ctx.run_size is None:
            return Refusal(rf, "size-cap", "batch/run size not declared")
        if ctx.batch_size > ctx.policy.batch_cap:
            return Refusal(rf, "size-cap", f"batch {ctx.batch_size} > {ctx.policy.batch_cap}")
    tier = required_tier(cls, sub, decision.route, ctx.policy)
    if ctx.run_size is not None and ctx.run_size > ctx.policy.run_cap:
        tier = 3
        if ctx.approval < 3:
            return Refusal(rf, "size-cap", f"run {ctx.run_size} > {ctx.policy.run_cap} without L3")
    if ctx.approval < tier:
        return Refusal(rf, f"human-approve-L{tier}", f"approval L{ctx.approval} < L{tier}")
    if tier >= 3:
        if ctx.blast_count is None or ctx.typed_confirmation != str(ctx.blast_count):
            return Refusal(rf, "typed-confirmation", "typed confirmation of blast count missing")
    if "stated-limit" in decision.controls and not ctx.stated_limit_ack:
        return Refusal(rf, "stated-limit", "irreversibility limit not acknowledged")
    return Allowed(decision.task_id, tier)


# Controls that need a verifiable proof object, not just a name in ``ctx.proven``.
PROOF_CONTROLS = frozenset(
    {"before-image", "batch1-undo-proof", "full-image-proof", "snapshot-proof"}
)


def gate_with_proofs(
    decision: Any, ctx: GateCtx, check: Callable[[str], bool] | None
) -> Allowed | Refusal:
    """The only RF gate: a proof-backed control counts only if ``check`` (a
    before_image.RouteA / snapshot verifier bound to this plan) confirms it. No check = none."""
    keep = frozenset(
        c for c in ctx.proven if c not in PROOF_CONTROLS or (check is not None and _ok(check, c))
    )
    return _evaluate(decision, replace(ctx, proven=keep))


def _ok(check: Callable[[str], bool], c: str) -> bool:
    try:
        return check(c) is True
    except Exception:  # noqa: BLE001 - unverifiable proof = not proven
        return False


# --------------------------------------------------------------------------- BOT-DIFF-BLAST
# Tier the owner approves at, chosen from the class AND the counted blast. Caps are pacing:
# > batch_cap splits into batches; > run_cap per run needs L3. Each tier names its controls.
TIER_CONTROLS: dict[int, tuple[str, ...]] = {
    1: ("quick-tap",),
    2: ("diff-preview", "blast-count"),
    3: ("diff-preview", "blast-count", "clone-rehearsal", "snapshot", "typed-blast-count"),
}


@dataclass(frozen=True)
class TierPlan:
    tier: int
    batches: int
    batch_size: int
    blast_count: int
    controls: tuple[str, ...]
    reasons: tuple[str, ...]


def plan_tier(
    cls: str,
    subkind: str | None,
    route: Route,
    policy: Policy,
    blast_count: int,
    low_count: Iterable[str] = (),
) -> TierPlan | Refusal:
    """Fail closed: unknown class or a non-positive/non-int count refuses."""
    if cls not in CLASSES:
        return Refusal("RF-ANY", "risk-class", f"unknown class {cls!r}")
    if not isinstance(blast_count, int) or isinstance(blast_count, bool) or blast_count < 1:
        return Refusal("RF-ANY", "blast-count", "blast count missing or not positive")
    tier = required_tier(cls, subkind, route, policy)
    reasons = [f"class {cls}: L{tier} by catalogue tier and hard floor"]
    if blast_count > policy.run_cap:
        tier = 3
        reasons.append(f"blast {blast_count} > run cap {policy.run_cap}: L3")
    low = [r for r in low_count if r]
    if low:
        tier = 3
        reasons += [f"count may be low: {r}: L3" for r in low]
    batches = -(-blast_count // policy.batch_cap)
    if batches > 1:
        reasons.append(f"blast {blast_count} > batch cap {policy.batch_cap}: {batches} batches")
    return TierPlan(
        tier, batches, policy.batch_cap, blast_count, TIER_CONTROLS[tier], tuple(reasons)
    )


# ---------------------------------------------------------------- BOT-V20-ACCESS (append-only)
# Reviewed: an access change touching one of these groups changes who can do anything at all.
ACCESS_CORE_GROUPS: dict[str, str] = {
    "base.group_system": "Settings/administrator: holders control every other access",
    "base.group_erp_manager": "Access Rights: holders can grant any group",
    "base.group_user": "internal user: every employee's base access",
    "base.group_portal": "portal: every customer/vendor login",
    "base.group_public": "public: anonymous website visitors",
    "base.group_no_one": "technical features: debug menus, raw models and access screens",
}
# Reviewed: any other access change still alters what people can see or do -> at least L2.
ACCESS_MIN_TIER = 2


def access_tier(
    floor_tier: int, *, core: set[str], global_rule: bool, security_model: bool
) -> tuple[int, list[str]]:
    """Tier for a Bot access change: the classifier's floor, raised by the reviewed rules."""
    why = [f"risk floor L{floor_tier}"]
    tier = max(floor_tier, ACCESS_MIN_TIER)
    for x in sorted(core):
        why.append(f"touches {x}: {ACCESS_CORE_GROUPS[x]}")
    if global_rule:
        why.append("global row: applies to every user")
    if security_model:
        why.append("row grants access to a security model")
    if core or global_rule or security_model:
        tier = 3
    return tier, why
