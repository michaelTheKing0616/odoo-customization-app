"""Deterministic fixes that block Apply-to-Odoo / module export (GEN2-11+)."""

from __future__ import annotations

import re
from typing import Any

from app.module_spec_codec import merge_custom_code_blocks
from app.multi_company_pack import (
    COMPANY_FIELD_LIVE,
    COMPANY_FIELD_MODULE,
    COMPANY_RULE_DOMAIN_LIVE,
    apply_multi_company_to_live_draft,
)

_MODULE_COMPANY_FIELD = "company_id"
_LIVE_COMPANY_FIELD = "x_company_id"
_INITIAL_STATES = frozenset({"draft", "new"})
_ALLOWED_INITIAL_TERMINALS = frozenset({"cancelled", "canceled", "rejected"})
_BAD_ASSIGNEE_RELATIONS = frozenset({"x_staff_shift"})
_LINE_QTY_NAMES = ("x_qty", "x_quantity", "quantity", "x_hours", "x_units")
_LINE_PRICE_NAMES = ("x_price", "x_unit_price", "x_price_unit", "x_rate", "price_unit")
_LINE_TOTAL_NAMES = ("x_subtotal", "x_total", "x_amount")

_SCALE_WORDS = frozenset({"super", "mega", "large", "multiple", "around", "world", "global"})
_DOMAIN_WORDS = (
    "market",
    "store",
    "shop",
    "retail",
    "branch",
    "grocery",
    "supermarket",
    "hospital",
    "clinic",
    "hotel",
    "restaurant",
)


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


def _replace_in_arch(draft: dict[str, Any], old: str, new: str) -> None:
    if old == new:
        return
    for v in draft.get("views") or []:
        if not isinstance(v, dict):
            continue
        arch = str(v.get("arch") or "")
        if old in arch:
            v["arch"] = arch.replace(old, new)


def scrub_unknown_arch_field_refs(draft: dict[str, Any]) -> list[str]:
    """Drop arch nodes that reference fields removed from the model (e.g. moved to lines)."""
    notes: list[str] = []
    by_id = _models_index(draft)

    def _scrub(arch: str, names: set[str]) -> tuple[str, int]:
        removed = 0

        def repl(match: re.Match[str]) -> str:
            nonlocal removed
            fname = match.group(1)
            if fname in names:
                return match.group(0)
            removed += 1
            return ""

        cleaned = re.sub(r'<field\b[^>]*\bname="([^"]+)"[^>]*/>', repl, arch, flags=re.I)
        cleaned = re.sub(
            r"<field\b[^>]*\bname=\"([^\"]+)\"[^>]*>\s*</field>",
            repl,
            cleaned,
            flags=re.I,
        )
        return cleaned, removed

    for v in draft.get("views") or []:
        if not isinstance(v, dict):
            continue
        mid = str(v.get("model") or "")
        model = by_id.get(mid)
        if not model:
            continue
        arch = str(v.get("arch") or "")
        cleaned, n = _scrub(arch, _field_names(model))
        if n:
            v["arch"] = cleaned
            notes.append(f"apply: scrubbed {n} stale arch field ref(s) on {mid}")
    return notes


def sanitize_empty_field_tags(draft: dict[str, Any]) -> list[str]:
    """Remove empty <field/> nodes left when columns were dropped from list archs (GEN2-13 A1)."""
    notes: list[str] = []
    for v in draft.get("views") or []:
        if not isinstance(v, dict):
            continue
        arch = str(v.get("arch") or "")
        if not arch or "<field" not in arch:
            continue
        cleaned = _EMPTY_FIELD_TAG_RE.sub("", arch)
        cleaned = re.sub(
            r"<field\b(?![^>]*\bname=)[^>]*>\s*</field>",
            "",
            cleaned,
            flags=re.I,
        )
        if cleaned != arch:
            v["arch"] = cleaned
            notes.append(f"apply: stripped empty field tags on {v.get('model') or '?'}")
    return notes


def _replace_field_name_in_archs(draft: dict[str, Any], old: str, new: str) -> None:
    token = f'name="{old}"'
    repl = f'name="{new}"'
    for v in draft.get("views") or []:
        if not isinstance(v, dict):
            continue
        arch = str(v.get("arch") or "")
        if token in arch:
            v["arch"] = arch.replace(token, repl)


def _repair_corrupted_company_arch_refs(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    bad = re.compile(r'name="x+(?:x_)*company_id"')
    for v in draft.get("views") or []:
        if not isinstance(v, dict):
            continue
        arch = str(v.get("arch") or "")
        if bad.search(arch):
            v["arch"] = bad.sub('name="x_company_id"', arch)
            notes.append(f"apply: repaired corrupted company field arch on {v.get('model')}")
    return notes


_MODULE_COMPANY_IN_DOM = re.compile(r"\(['\"]company_id['\"]\s*,")
_LIVE_COMPANY_IN_DOM = re.compile(r"\(['\"]x_company_id['\"]\s*,")


def normalize_company_fields_for_live(draft: dict[str, Any]) -> list[str]:
    """Live apply uses x_company_id + x_-prefixed record-rule domains (GEN2-13 A2)."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        names = _field_names(model)
        fields = model.get("fields") or []
        if _MODULE_COMPANY_FIELD in names and _LIVE_COMPANY_FIELD not in names:
            for f in fields:
                if isinstance(f, dict) and f.get("name") == _MODULE_COMPANY_FIELD:
                    f["name"] = _LIVE_COMPANY_FIELD
                    f.setdefault("string", "Company")
                    notes.append(f"apply: {_MODULE_COMPANY_FIELD}→{_LIVE_COMPANY_FIELD} on {mid}")
            _replace_field_name_in_archs(draft, _MODULE_COMPANY_FIELD, _LIVE_COMPANY_FIELD)
        elif _MODULE_COMPANY_FIELD in names and _LIVE_COMPANY_FIELD in names:
            model["fields"] = [
                f
                for f in fields
                if not (isinstance(f, dict) and f.get("name") == _MODULE_COMPANY_FIELD)
            ]
            notes.append(f"apply: dropped duplicate {_MODULE_COMPANY_FIELD} on {mid}")

    for rule in draft.get("record_rules") or []:
        if not isinstance(rule, dict):
            continue
        dom = str(rule.get("domain_force") or "")
        if _MODULE_COMPANY_IN_DOM.search(dom) and not _LIVE_COMPANY_IN_DOM.search(dom):
            rule["domain_force"] = _MODULE_COMPANY_IN_DOM.sub("('x_company_id',", dom)
            notes.append(f"apply: record rule domain uses {_LIVE_COMPANY_FIELD}")

    enriched = apply_multi_company_to_live_draft(draft)
    if enriched.get("record_rules"):
        draft["record_rules"] = enriched["record_rules"]
    for rule in draft.get("record_rules") or []:
        if isinstance(rule, dict):
            dom = str(rule.get("domain_force") or "")
            if _LIVE_COMPANY_IN_DOM.search(dom) or _MODULE_COMPANY_IN_DOM.search(dom):
                rule["domain_force"] = COMPANY_RULE_DOMAIN_LIVE
    draft["multi_company"] = True
    return notes


def normalize_company_fields_for_export(draft: dict[str, Any]) -> list[str]:
    """Backward-compatible alias — live path keeps x_company_id."""
    return normalize_company_fields_for_live(draft)


def resolve_duplicate_address_fields(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        names = _field_names(model)
        if "x_address" in names and "x_address_id" in names:
            model["fields"] = [
                f
                for f in (model.get("fields") or [])
                if not (isinstance(f, dict) and f.get("name") == "x_address")
            ]
            mid = str(model.get("model") or "")
            _replace_in_arch(draft, 'name="x_address"', 'name="x_address_id"')
            notes.append(f"apply: dropped redundant x_address char on {mid} (keep x_address_id)")
    return notes


def ensure_relation_module_depends(draft: dict[str, Any]) -> list[str]:
    """Add depends when models reference stock/hr/etc."""
    notes: list[str] = []
    relation_modules = {
        "hr.employee": "hr",
        "hr.contract": "hr",
        "stock.quant": "stock",
        "stock.picking": "stock",
        "sale.order": "sale",
        "purchase.order": "purchase",
    }
    found: set[str] = set()
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for f in model.get("fields") or []:
            if not isinstance(f, dict):
                continue
            rel = str(f.get("relation") or "")
            mod = relation_modules.get(rel)
            if mod:
                found.add(mod)
    depends = list(draft.get("depends") or [])
    dep_set = set(depends)
    for mod in sorted(found):
        if mod not in dep_set:
            depends.append(mod)
            dep_set.add(mod)
            notes.append(f"apply: added depends {mod}")
    if notes:
        draft["depends"] = depends
    return notes


def _pack_reuse_stock_rows(draft: dict[str, Any]) -> list[dict[str, Any]]:
    rows = draft.get("_pack_reuse_stock") or draft.get("reuse_stock") or []
    if isinstance(rows, list) and rows:
        return [r for r in rows if isinstance(r, dict)]
    if draft.get("domain_pack"):
        from app.ai_domain_packs import match_domain_pack

        prompt = str(draft.get("_user_prompt") or "")
        matched = match_domain_pack(prompt)
        if matched and isinstance(matched[1], dict):
            stock = matched[1].get("reuse_stock")
            if isinstance(stock, list):
                return [r for r in stock if isinstance(r, dict)]
    return []


def _draft_anti_patterns(draft: dict[str, Any]) -> list[str]:
    patterns = list(draft.get("anti_patterns") or [])
    if patterns:
        return [str(p) for p in patterns]
    if draft.get("domain_pack"):
        from app.ai_domain_packs import match_domain_pack

        matched = match_domain_pack(str(draft.get("_user_prompt") or ""))
        if matched and isinstance(matched[1], dict):
            return [str(p) for p in (matched[1].get("anti_patterns") or [])]
    return []


_PAYMENT_CAPTURE_FORBIDDEN_RE = re.compile(
    r"payment capture|recurring billing engines|folio settlement", re.I
)
_PARALLEL_BILLING_MODEL_RE = re.compile(r"x_.*(?:invoice|bill)(?:_line)?$", re.I)
_PAYMENT_WORKFLOW_STATES = frozenset({"paid", "overdue", "sent", "partial", "posted"})
_PAYMENT_CAPTURE_FIELD_RE = re.compile(
    r"^x_(?:payment_(?:status|state|method|ref)|is_paid|paid(?:\b|_))", re.I
)
_PAYMENT_SELECTION_KEYS = frozenset({"paid", "unpaid", "partial", "refunded", "overdue"})
_EMPTY_FIELD_TAG_RE = re.compile(r"<field\b(?![^>]*\bname=)[^>]*/>", re.I)
_PRIMARY_HEADER_TOTALS = ("x_amount_total", "x_total", "x_amount")
_SHADOW_HEADER_TOTALS = ("x_total_amount", "x_amount_untaxed", "x_grand_total", "x_amount_gross")
_HEADER_TAX_FIELDS = ("x_tax_amount", "x_amount_tax", "x_tax_total")
_TRANSACTION_HEADER_TOKENS = ("order", "matter", "case", "job", "booking", "reservation", "quote")
_PROCUREMENT_HEADER_TOKENS = ("supplier", "purchase", "procurement", "vendor", "rfq", "requisition")
_SALES_HEADER_TOKENS = ("order", "sale", "booking", "reservation", "quote")
_INTERNAL_HEADER_TOKENS = (
    "transfer",
    "adjustment",
    "task",
    "event",
    "shift",
    "registration",
)
_CAMPAIGN_MODEL_TOKENS = ("promotion", "campaign", "coupon", "discount", "voucher")
_STOCK_DOCUMENT_LINKS: tuple[tuple[str, str, str, str], ...] = (
    ("account.move", "x_invoice_id", "Invoice", "account"),
    ("sale.order", "x_sale_order_id", "Sales order", "sale"),
    ("purchase.order", "x_purchase_order_id", "Purchase order", "purchase"),
)


def _forbids_payment_capture(draft: dict[str, Any]) -> bool:
    anti = _draft_anti_patterns(draft)
    return any(_PAYMENT_CAPTURE_FORBIDDEN_RE.search(p) for p in anti)


def _reuse_models(draft: dict[str, Any]) -> set[str]:
    reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
    models = set(reuse.get("models") or [])
    plan = reuse.get("plan")
    if isinstance(plan, dict):
        for d in plan.get("decisions") or []:
            if isinstance(d, dict) and d.get("model"):
                models.add(str(d["model"]))
    return models


def _selection_keys(selection: Any) -> set[str]:
    if not isinstance(selection, str):
        return set()
    return set(re.findall(r"\('([^']+)'", selection))


def _field_implies_payment_capture(field: dict[str, Any]) -> bool:
    name = str(field.get("name") or "")
    if _PAYMENT_CAPTURE_FIELD_RE.match(name):
        return True
    if str(field.get("ttype") or "") != "selection":
        return False
    keys = _selection_keys(field.get("selection"))
    if keys & _PAYMENT_SELECTION_KEYS and "payment" in name.lower():
        return True
    if keys <= _PAYMENT_SELECTION_KEYS and name.lower().endswith("_status"):
        return True
    return False


def _model_name_tokens(model: dict[str, Any]) -> set[str]:
    mid = str(model.get("model") or "").lower()
    return set(re.split(r"[_\s]+", mid))


def _is_transaction_header(model: dict[str, Any]) -> bool:
    mid = str(model.get("model") or "")
    if not mid.startswith("x_") or "line" in mid.lower():
        return False
    desc = str(model.get("description") or "").lower()
    if "supplier" in desc and "agreement" in desc:
        return True
    if "supplier" in mid and "agreement" in mid:
        return True
    fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
    if any(
        f.get("ttype") == "one2many" and "line" in str(f.get("relation") or "").lower()
        for f in fields
    ):
        return True
    if model.get("is_workflow") and any(tok in mid for tok in _TRANSACTION_HEADER_TOKENS):
        return True
    return False


def _is_procurement_header(model: dict[str, Any]) -> bool:
    if not _is_transaction_header(model):
        return False
    tokens = _model_name_tokens(model)
    desc = str(model.get("description") or "").lower()
    if tokens & set(_PROCUREMENT_HEADER_TOKENS):
        return True
    if any(tok in desc for tok in _PROCUREMENT_HEADER_TOKENS):
        return True
    for field in model.get("fields") or []:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").lower()
        if "supplier" in name or "vendor" in name:
            return True
    return False


def _is_sales_header(model: dict[str, Any]) -> bool:
    if not _is_transaction_header(model) or _is_procurement_header(model):
        return False
    tokens = _model_name_tokens(model)
    desc = str(model.get("description") or "").lower()
    if tokens & set(_SALES_HEADER_TOKENS):
        return True
    return any(word in desc for word in ("sales", "customer order", "retail", "pos"))


def _stock_link_applies(stock_model: str, model: dict[str, Any]) -> bool:
    if stock_model == "purchase.order":
        return _is_procurement_header(model)
    if stock_model == "sale.order":
        return _is_sales_header(model)
    if stock_model == "account.move":
        mid = str(model.get("model") or "").lower()
        if any(tok in mid for tok in _INTERNAL_HEADER_TOKENS):
            return False
        return _is_sales_header(model) or _is_procurement_header(model)
    return False


def _is_campaign_model(model: dict[str, Any]) -> bool:
    mid = str(model.get("model") or "")
    if not mid.startswith("x_"):
        return False
    if not (_model_name_tokens(model) & set(_CAMPAIGN_MODEL_TOKENS)):
        return False
    names = _field_names(model)
    if model.get("is_workflow"):
        return True
    return any(
        name.startswith(("x_discount", "x_date_start", "x_date_end")) for name in names
    )


def _pick_campaign_model(by_id: dict[str, dict[str, Any]]) -> str | None:
    candidates = [mid for mid, model in by_id.items() if _is_campaign_model(model)]
    if not candidates:
        return None
    for preferred in ("x_promotion", "x_campaign", "x_discount", "x_coupon", "x_voucher"):
        if preferred in candidates:
            return preferred
    for mid in sorted(candidates, key=len):
        if "promotion" in mid or "campaign" in mid:
            return mid
    return candidates[0]


def _pick_sales_order_header(by_id: dict[str, dict[str, Any]]) -> str | None:
    candidates = [mid for mid, model in by_id.items() if _is_sales_header(model)]
    if not candidates:
        return None
    for mid in candidates:
        if "order" in mid.lower():
            return mid
    return candidates[0]


def _header_primary_total(fields: dict[str, dict[str, Any]], compute_models: set[str], mid: str) -> str | None:
    if mid in compute_models:
        for name in _PRIMARY_HEADER_TOTALS:
            if name in fields:
                return name
    return None


def _purge_draft_models(draft: dict[str, Any], removed: set[str]) -> None:
    if not removed:
        return
    draft["models"] = [
        m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "") not in removed
    ]
    for key in ("actions", "views", "menus", "sequences", "automations"):
        rows = draft.get(key)
        if not isinstance(rows, list):
            continue
        kept = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            mid = row.get("model")
            if key == "menus":
                action_id = str(row.get("action_xml_id") or "")
                if any(action_id == f"action_{r}" for r in removed):
                    continue
            if key == "access_rules" and isinstance(mid, str) and mid.startswith("model_"):
                leaf = mid[len("model_") :]
                if leaf in removed:
                    continue
            if mid in removed:
                continue
            kept.append(row)
        draft[key] = kept
    draft["smart_buttons"] = [
        b
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
        and b.get("related_model") not in removed
        and b.get("on_model") not in removed
    ]
    blocks = draft.get("custom_code_blocks")
    if isinstance(blocks, list):
        draft["custom_code_blocks"] = [
            b
            for b in blocks
            if not (isinstance(b, dict) and str(b.get("model") or "") in removed)
        ]
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        model["fields"] = [
            f
            for f in (model.get("fields") or [])
            if not (
                isinstance(f, dict)
                and str(f.get("relation") or "") in removed
            )
        ]


def demote_parallel_billing_models(draft: dict[str, Any]) -> list[str]:
    """Drop parallel x_* invoice/bill workflows when pack forbids payment capture."""
    notes: list[str] = []
    forbid_capture = _forbids_payment_capture(draft)
    reuse_models = _reuse_models(draft)
    if not forbid_capture and "account.move" not in reuse_models:
        return notes

    removed: set[str] = set()
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        if mid == "x_bill" and not model.get("is_workflow"):
            continue
        if not (_PARALLEL_BILLING_MODEL_RE.match(mid) or "invoice" in mid.lower()):
            if "bill" not in mid.lower():
                continue
        if model.get("is_workflow"):
            sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
            sel = str(sf.get("selection") or "")
            states = set(re.findall(r"\('([^']+)'", sel))
            if states & _PAYMENT_WORKFLOW_STATES or "invoice" in mid.lower():
                removed.add(mid)
                continue
        if "invoice" in mid.lower() and any(
            isinstance(f, dict)
            and str(f.get("ttype") or "") in {"monetary", "float"}
            and "amount" in str(f.get("name") or "").lower()
            for f in (model.get("fields") or [])
        ):
            removed.add(mid)

    if not removed:
        return notes

    _purge_draft_models(draft, removed)
    notes.append(f"apply: demoted parallel billing model(s) {', '.join(sorted(removed))}")

    line_drop = {"x_bill_id", "x_invoice_id"}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if "line" not in mid.lower():
            continue
        before = len(model.get("fields") or [])
        model["fields"] = [
            f
            for f in (model.get("fields") or [])
            if not (isinstance(f, dict) and str(f.get("name") or "") in line_drop)
        ]
        if len(model.get("fields") or []) < before:
            notes.append(f"apply: removed line billing link field(s) on {mid}")

    draft.setdefault("review_notes", [])
    if isinstance(draft["review_notes"], list):
        note = (
            "Billing: parallel x_* invoice models removed — use link-only account.move "
            "fields; no payment capture in metadata export."
        )
        if note not in draft["review_notes"]:
            draft["review_notes"].append(note)
    return notes


def scrub_payment_capture_fields(draft: dict[str, Any]) -> list[str]:
    """Remove pseudo payment-tracking fields when pack forbids payment capture."""
    notes: list[str] = []
    if not _forbids_payment_capture(draft):
        return notes
    drop: dict[str, set[str]] = {}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        for f in model.get("fields") or []:
            if isinstance(f, dict) and _field_implies_payment_capture(f):
                drop.setdefault(mid, set()).add(str(f.get("name") or ""))
    for mid, names in drop.items():
        _drop_model_fields(draft, mid, names)
        notes.append(f"apply: removed payment capture field(s) on {mid}: {', '.join(sorted(names))}")
    return notes


def consolidate_header_monetary_fields(draft: dict[str, Any]) -> list[str]:
    """Drop shadow header totals/taxes when a computed primary total exists."""
    notes: list[str] = []
    compute_models = {
        str(b.get("model"))
        for b in merge_custom_code_blocks(draft)
        if isinstance(b, dict) and b.get("model")
    }
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or not _is_transaction_header(model):
            continue
        mid = str(model.get("model") or "")
        fields = {
            str(f.get("name")): f for f in (model.get("fields") or []) if isinstance(f, dict)
        }
        primary = _header_primary_total(fields, compute_models, mid)
        if not primary:
            continue
        drop: set[str] = set()
        for name in _SHADOW_HEADER_TOTALS:
            if name in fields and name != primary:
                drop.add(name)
        line_models = {
            str(fields[f].get("relation") or "")
            for f in fields
            if fields[f].get("ttype") == "one2many"
        }
        line_has_tax = any(
            any(
                isinstance(lf, dict)
                and str(lf.get("name") or "").startswith("x_tax")
                for lf in (_models_index(draft).get(lm) or {}).get("fields") or []
            )
            for lm in line_models
            if lm in _models_index(draft)
        )
        tax_computed = mid in compute_models and any(
            "tax" in str(b.get("content") or "").lower()
            for b in merge_custom_code_blocks(draft)
            if isinstance(b, dict) and str(b.get("model") or "") == mid
        )
        if not line_has_tax and not tax_computed:
            for name in _HEADER_TAX_FIELDS:
                if name in fields:
                    drop.add(name)
        if drop:
            _drop_model_fields(draft, mid, drop)
            notes.append(f"apply: consolidated header monetary fields on {mid} (keep {primary})")
    return notes


def scrub_misapplied_stock_document_links(draft: dict[str, Any]) -> list[str]:
    """Drop stock-document M2O fields on semantically wrong header models."""
    notes: list[str] = []
    checks = (
        ("x_purchase_order_id", lambda model: _is_procurement_header(model)),
        ("x_sale_order_id", lambda model: _is_sales_header(model)),
        ("x_invoice_id", lambda model: _stock_link_applies("account.move", model)),
    )
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        names = _field_names(model)
        drop = {fname for fname, ok in checks if fname in names and not ok(model)}
        if drop:
            _drop_model_fields(draft, mid, drop)
            notes.append(f"apply: removed misapplied stock document link(s) on {mid}")
    return notes


def ensure_transaction_document_links(draft: dict[str, Any]) -> list[str]:
    """Link-only M2O to stock Odoo documents on semantically matching transactional headers."""
    notes: list[str] = []
    reuse = _reuse_models(draft)
    depends = set(draft.get("depends") or [])
    for stock_model, fname, label, dep_module in _STOCK_DOCUMENT_LINKS:
        if stock_model not in reuse and dep_module not in depends:
            continue
        for model in draft.get("models") or []:
            if not isinstance(model, dict) or not _stock_link_applies(stock_model, model):
                continue
            mid = str(model.get("model") or "")
            names = _field_names(model)
            if fname in names:
                continue
            alt = {
                "x_invoice_id": "x_move_id",
                "x_sale_order_id": "x_order_id",
            }.get(fname)
            if alt and alt in names:
                continue
            model.setdefault("fields", []).append(
                {
                    "name": fname,
                    "ttype": "many2one",
                    "relation": stock_model,
                    "string": label,
                    "help": f"Link-only — wire to {stock_model} manually",
                    "source": "apply_readiness",
                }
            )
            notes.append(f"apply: link-only {fname} on {mid} ({stock_model})")
    if notes:
        draft.setdefault("review_notes", [])
        if isinstance(draft["review_notes"], list):
            link_note = (
                "Transactional headers include link-only stock Odoo document fields — "
                "wire in Odoo before go-live; metadata export does not post moves/orders."
            )
            if link_note not in draft["review_notes"]:
                draft["review_notes"].append(link_note)
    return notes


def ensure_campaign_order_links(draft: dict[str, Any]) -> list[str]:
    """Restore campaign/promotion ↔ sales-order links when both model families exist."""
    notes: list[str] = []
    by_id = _models_index(draft)
    campaign_id = _pick_campaign_model(by_id)
    order_id = _pick_sales_order_header(by_id)
    if not campaign_id or not order_id:
        return notes

    campaign = by_id[campaign_id]
    order = by_id[order_id]
    campaign_suffix = campaign_id.removeprefix("x_")
    order_suffix = order_id.removeprefix("x_")
    m2o_name = f"x_{campaign_suffix}_id"
    o2m_name = f"x_{order_suffix}_ids"
    order_names = _field_names(order)
    campaign_names = _field_names(campaign)
    alt_m2o = ("x_discount_id", "x_campaign_id", "x_coupon_id", "x_voucher_id")

    link_field = next((name for name in alt_m2o if name in order_names), None)
    if link_field is None and m2o_name not in order_names:
        order.setdefault("fields", []).append(
            {
                "name": m2o_name,
                "ttype": "many2one",
                "relation": campaign_id,
                "string": str(campaign.get("description") or "Promotion").split("/")[0].strip(),
                "source": "apply_readiness",
            }
        )
        link_field = m2o_name
        notes.append(f"apply: {m2o_name} on {order_id} → {campaign_id}")
    elif link_field is None:
        link_field = m2o_name

    has_o2m = any(
        isinstance(field, dict)
        and field.get("ttype") == "one2many"
        and str(field.get("relation") or "") == order_id
        for field in (campaign.get("fields") or [])
    )
    if o2m_name not in campaign_names and not has_o2m:
        campaign.setdefault("fields", []).append(
            {
                "name": o2m_name,
                "ttype": "one2many",
                "relation": order_id,
                "relation_field": link_field,
                "string": str(order.get("description") or "Orders").split("/")[0].strip(),
                "source": "apply_readiness",
            }
        )
        notes.append(f"apply: {o2m_name} on {campaign_id} → {order_id}")
    return notes


_REUSE_STOCK_DOCUMENT_TARGETS: tuple[tuple[str, str, str], ...] = (
    ("sale.order", "sale", "Sales orders (link-only)"),
    ("account.move", "account", "Invoices / bills (link-only)"),
    ("purchase.order", "purchase", "Purchase orders (link-only)"),
)


def _needs_reuse_stock_document(model: str, by_id: dict[str, dict[str, Any]]) -> bool:
    if model == "sale.order":
        return any(_is_sales_header(m) for m in by_id.values())
    if model == "account.move":
        return any(
            _is_sales_header(m) or _is_procurement_header(m) for m in by_id.values()
        )
    if model == "purchase.order":
        return any(_is_procurement_header(m) for m in by_id.values())
    return False


def wire_reuse_stock_documents(draft: dict[str, Any]) -> list[str]:
    """Auto-confirm link-only reuse of sale.order / account.move (+ purchase) for retail drafts."""
    notes: list[str] = []
    by_id = _models_index(draft)
    if not by_id:
        return notes

    pack_rows = {
        str(row.get("model") or ""): row
        for row in _pack_reuse_stock_rows(draft)
        if row.get("model")
    }
    reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
    plan = reuse.get("plan") if isinstance(reuse.get("plan"), dict) else {}
    decisions = list(plan.get("decisions") or []) if isinstance(plan.get("decisions"), list) else []
    decision_by_model = {
        str(d.get("model") or ""): d for d in decisions if isinstance(d, dict) and d.get("model")
    }
    models_reuse = set(reuse.get("models") or [])
    depends = list(draft.get("depends") or [])

    for stock_model, dep_module, default_reason in _REUSE_STOCK_DOCUMENT_TARGETS:
        if not _needs_reuse_stock_document(stock_model, by_id):
            continue
        pack_row = pack_rows.get(stock_model, {})
        reason = str(pack_row.get("reason") or default_reason)
        if dep_module not in depends:
            depends.append(dep_module)
            notes.append(f"apply: added depends {dep_module!r} for {stock_model} reuse")
        if stock_model not in models_reuse:
            models_reuse.add(stock_model)
            notes.append(f"apply: reuse wired {stock_model} (link-only)")
        decision = decision_by_model.get(stock_model)
        if decision is None:
            decision = {
                "model": stock_model,
                "source": "pack_reuse_stock" if pack_row else "apply_readiness",
                "reason": reason,
            }
            decisions.append(decision)
            decision_by_model[stock_model] = decision
        if not decision.get("confirmed"):
            decision["confirmed"] = True
            notes.append(f"apply: confirmed reuse {stock_model}")
        if pack_row.get("link_only") or stock_model in {
            "sale.order",
            "account.move",
            "purchase.order",
        }:
            decision["link_only"] = True

    if notes:
        draft["depends"] = depends
        draft["reuse"] = {
            **reuse,
            "models": sorted(models_reuse),
            "plan": {**plan, "decisions": decisions},
        }
    return notes


def apply_promotion_discount_line_computes(draft: dict[str, Any]) -> list[str]:
    """Apply promotion x_discount_pct to order line subtotals (qty × price × (1 − pct/100))."""
    notes: list[str] = []
    by_id = _models_index(draft)
    campaign_id = _pick_campaign_model(by_id)
    order_id = _pick_sales_order_header(by_id)
    if not campaign_id or not order_id:
        return notes

    campaign = by_id[campaign_id]
    order = by_id[order_id]
    campaign_names = _field_names(campaign)
    discount_field = next(
        (name for name in ("x_discount_pct", "x_discount", "x_percent") if name in campaign_names),
        None,
    )
    if not discount_field:
        return notes

    order_names = _field_names(order)
    campaign_suffix = campaign_id.removeprefix("x_")
    alt_m2o = ("x_discount_id", "x_campaign_id", "x_coupon_id", "x_voucher_id")
    promo_field = next(
        (name for name in (*alt_m2o, f"x_{campaign_suffix}_id") if name in order_names),
        None,
    )
    if not promo_field:
        return notes

    line_field = next(
        (
            str(f.get("name"))
            for f in (order.get("fields") or [])
            if isinstance(f, dict)
            and f.get("ttype") == "one2many"
            and str(f.get("relation") or "") in by_id
            and "line" in str(f.get("relation") or "").lower()
        ),
        None,
    )
    if not line_field:
        return notes
    line_model = str(
        next(
            f.get("relation")
            for f in (order.get("fields") or [])
            if isinstance(f, dict) and str(f.get("name") or "") == line_field
        )
        or ""
    )
    line_def = by_id.get(line_model) or {}
    line_fields = {
        str(f.get("name")): f for f in (line_def.get("fields") or []) if isinstance(f, dict)
    }
    qty = next((n for n in _LINE_QTY_NAMES if n in line_fields), None)
    price = next((n for n in _LINE_PRICE_NAMES if n in line_fields), None)
    total = next((n for n in _LINE_TOTAL_NAMES if n in line_fields), None)
    if not qty or not price or not total:
        return notes

    parent_field = next(
        (
            str(f.get("name"))
            for f in (line_def.get("fields") or [])
            if isinstance(f, dict)
            and f.get("ttype") == "many2one"
            and str(f.get("relation") or "") == order_id
        ),
        None,
    )
    if not parent_field:
        return notes

    total_label = str(line_fields[total].get("string") or "Subtotal")
    class_name = f"{_model_class_token(line_model)}PromoSubtotal"
    method = f"_compute_{total}"
    basename = _model_module_basename(line_model)
    source_file = f"models/{basename}.py"
    curr = _currency_field_name(line_fields)
    if _field_ttype(line_fields, total) == "monetary" or curr:
        field_lines = (
            f"    {total} = fields.Monetary(\n"
            f"        string={total_label!r},\n"
            f"        compute={method!r},\n"
            f"        store=True,\n"
            f"        currency_field={curr!r},\n"
            f"    )\n"
        )
    else:
        field_lines = (
            f"    {total} = fields.Float(\n"
            f"        string={total_label!r},\n"
            f"        compute={method!r},\n"
            f"        store=True,\n"
            f"    )\n"
        )
    depends = (
        f"'{qty}', '{price}', "
        f"'{parent_field}.{promo_field}.{discount_field}'"
    )
    content = (
        "from odoo import api, fields, models\n\n\n"
        f"class {class_name}(models.Model):\n"
        f"    _inherit = {line_model!r}\n\n"
        f"{field_lines}\n"
        f"    @api.depends({depends})\n"
        f"    def {method}(self):\n"
        f"        for rec in self:\n"
        f"            base = (rec.{qty} or 0.0) * (rec.{price} or 0.0)\n"
        f"            promo = rec.{parent_field}.{promo_field}\n"
        f"            pct = promo.{discount_field} if promo else 0.0\n"
        f"            rec.{total} = base * (1.0 - (pct or 0.0) / 100.0)\n"
    )
    _upsert_custom_code_block(
        draft,
        model=line_model,
        source_file=source_file,
        content=content,
        reason="apply_readiness: promotion discount line subtotal compute",
    )
    notes.append(
        f"apply: promotion discount compute on {line_model} "
        f"({parent_field}.{promo_field}.{discount_field})"
    )
    return notes


def prepare_spec_for_live_apply(spec: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalize draft JSON before live Odoo RPC apply (readiness + live company naming)."""
    import copy

    out = copy.deepcopy(spec)
    notes = run_apply_readiness_pass(out)
    return out, notes


def fix_reuse_link_only_consistency(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    link_only: dict[str, bool] = {}
    for row in _pack_reuse_stock_rows(draft):
        if row.get("model"):
            link_only[str(row["model"])] = bool(row.get("link_only"))
    plan = (draft.get("reuse") or {}).get("plan") if isinstance(draft.get("reuse"), dict) else {}
    decisions = plan.get("decisions") if isinstance(plan, dict) else None
    if not isinstance(decisions, list):
        return notes
    for d in decisions:
        if not isinstance(d, dict):
            continue
        model = str(d.get("model") or "")
        if model in link_only and link_only[model] and not d.get("link_only"):
            d["link_only"] = True
            notes.append(f"apply: reuse {model} marked link_only (pack contract)")
    return notes


def ensure_search_filter_names(draft: dict[str, Any]) -> list[str]:
    """Odoo search filters require unique ``name`` attrs — group_by filters often omit them."""
    notes: list[str] = []
    for v in draft.get("views") or []:
        if not isinstance(v, dict) or str(v.get("type") or "") != "search":
            continue
        arch = str(v.get("arch") or "")
        if not arch:
            continue
        filters = re.findall(r"<filter\b[^>]*/>", arch, flags=re.I)
        if not filters or all('name="' in flt for flt in filters):
            continue
        used: set[str] = set(re.findall(r'name="([^"]+)"', arch))
        changed = False

        def _inject_name(match: re.Match[str]) -> str:
            nonlocal changed
            tag = match.group(0)
            if 'name="' in tag:
                return tag
            ctx_m = re.search(r"context=\"(\{[^\"]+\})\"", tag)
            dom_m = re.search(r'domain="([^"]+)"', tag)
            string_m = re.search(r'string="([^"]+)"', tag)
            if ctx_m and "group_by" in ctx_m.group(1):
                gb_m = re.search(r"'group_by':\s*'([^']+)'", ctx_m.group(1))
                base = gb_m.group(1) if gb_m else "group"
                name = f"group_{base}"
            elif dom_m:
                status_m = re.search(r"\('x_status',\s*'=',\s*'([^']+)'\)", dom_m.group(1))
                base = status_m.group(1) if status_m else (
                    string_m.group(1).lower().replace(" ", "_") if string_m else "filter"
                )
                name = f"status_{base}" if status_m else f"filter_{base}"
            else:
                base = string_m.group(1).lower().replace(" ", "_") if string_m else "filter"
                name = f"filter_{base}"
            n = 2
            candidate = name
            while candidate in used:
                candidate = f"{name}_{n}"
                n += 1
            used.add(candidate)
            changed = True
            if tag.endswith("/>"):
                return tag[:-2] + f' name="{candidate}"/>'
            return tag.replace("<filter ", f'<filter name="{candidate}" ', 1)

        new_arch = re.sub(r"<filter\b[^>]*/>", _inject_name, arch, flags=re.I)
        if changed and new_arch != arch:
            v["arch"] = new_arch
            notes.append(f"apply: named search filters on {v.get('model') or '?'}")
    return notes


def dedupe_search_view_filters(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for v in draft.get("views") or []:
        if not isinstance(v, dict) or str(v.get("type") or "") != "search":
            continue
        arch = str(v.get("arch") or "")
        if not arch:
            continue
        filters = re.findall(r"<filter\b[^>]*(?:/>|>[^<]*</filter>)", arch, flags=re.I)
        seen: set[str] = set()
        keep: list[str] = []
        for flt in filters:
            name_m = re.search(r'name="([^"]+)"', flt)
            ctx_m = re.search(r"context=\"(\{[^\"]+\})\"", flt)
            key = name_m.group(1) if name_m else flt
            if ctx_m:
                key = f"{key}|{ctx_m.group(1)}"
            if key in seen:
                continue
            seen.add(key)
            keep.append(flt)
        if len(keep) < len(filters):
            mid = str(v.get("model") or "")
            open_tag = re.match(r"(<search[^>]*>)", arch, flags=re.I)
            close_tag = "</search>"
            if open_tag:
                v["arch"] = open_tag.group(1) + "".join(keep) + close_tag
                notes.append(f"apply: deduped search filters on {mid}")
    return notes


_SEQUENCE_WORD_PREFIXES: tuple[tuple[str, str], ...] = (
    ("promotion", "PROMO"),
    ("transfer", "TRANSFER"),
    ("compliance", "CHECK"),
    ("inventory_count", "COUNT"),
    ("adjustment", "ADJ"),
    ("order", "ORDER"),
    ("branch", "BR"),
    ("staff", "STAFF"),
    ("event", "EVENT"),
    ("task", "TASK"),
)


def _sequence_prefix_for_model(model: str) -> str:
    slug = model.replace("x_", "").replace(".", "_").lower()
    for token, prefix in _SEQUENCE_WORD_PREFIXES:
        if token in slug:
            return f"{prefix}/"
    parts = [p for p in slug.split("_") if p and p not in {"line", "store"}]
    word = parts[0] if parts else slug
    return f"{word.upper()}/"


def ensure_unique_sequence_prefixes(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    seqs = draft.get("sequences") or []
    if not isinstance(seqs, list):
        return notes
    used: dict[str, str] = {}
    for seq in seqs:
        if not isinstance(seq, dict):
            continue
        model = str(seq.get("model") or "")
        if not model:
            continue
        canonical = _sequence_prefix_for_model(model)
        prefix = str(seq.get("prefix") or "")
        if prefix != canonical:
            seq["prefix"] = canonical
            notes.append(f"apply: sequence prefix {prefix or '?'}→{canonical} for {model}")
            prefix = canonical
        if prefix not in used:
            used[prefix] = model
            continue
        if used[prefix] == model:
            continue
        base = canonical.rstrip("/")
        new_prefix = f"{base}2/"
        n = 2
        while new_prefix in used:
            n += 1
            new_prefix = f"{base}{n}/"
        seq["prefix"] = new_prefix
        used[new_prefix] = model
        notes.append(f"apply: sequence prefix collision {prefix}→{new_prefix} for {model}")
    return notes


def fix_branch_transfer_incoming_o2m(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    by_id = _models_index(draft)
    branch = by_id.get("x_branch")
    transfer = by_id.get("x_branch_transfer")
    if not branch or not transfer:
        return notes
    names = _field_names(branch)
    if "x_branch_transfer_in_ids" in names:
        return notes
    if not any(
        isinstance(f, dict) and f.get("name") == "x_branch_to_id"
        for f in (transfer.get("fields") or [])
    ):
        return notes
    branch.setdefault("fields", []).append(
        {
            "name": "x_branch_transfer_in_ids",
            "ttype": "one2many",
            "string": "Incoming transfers",
            "relation": "x_branch_transfer",
            "relation_field": "x_branch_to_id",
            "source": "apply_readiness",
        }
    )
    notes.append("apply: x_branch incoming transfer o2m (x_branch_to_id)")
    return notes


def _domain_label_word(user_prompt: str) -> str:
    tokens = re.findall(r"[a-zA-Z]+", user_prompt.lower())
    for tok in tokens:
        if tok in _SCALE_WORDS:
            continue
        if tok in _DOMAIN_WORDS or len(tok) >= 4:
            return tok.replace("_", " ").title()
    return "Store"


def normalize_depth_seed_naming(draft: dict[str, Any]) -> list[str]:
    """Replace generic 'Super Event/Task' depth_seed labels with domain wording."""
    notes: list[str] = []
    prompt = str(draft.get("_user_prompt") or "")
    word = _domain_label_word(prompt)
    replacements = {
        "Super Event": f"{word} Event",
        "Super Task": f"{word} Task",
    }
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or model.get("source") != "depth_seed":
            continue
        desc = str(model.get("description") or "")
        for old, new in replacements.items():
            if old in desc:
                model["description"] = desc.replace(old, new)
                notes.append(f"apply: renamed depth_seed {model.get('model')} description")
    for key in ("actions", "menus", "smart_buttons"):
        rows = draft.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for field in ("name", "label", "string"):
                val = str(row.get(field) or "")
                for old, new in replacements.items():
                    if old in val:
                        row[field] = val.replace(old, new)
    for v in draft.get("views") or []:
        if not isinstance(v, dict):
            continue
        arch = str(v.get("arch") or "")
        name = str(v.get("name") or "")
        for old, new in replacements.items():
            if old in arch:
                v["arch"] = arch.replace(old, new)
                arch = v["arch"]
            if old in name:
                v["name"] = name.replace(old, new)
    for g in draft.get("groups") or []:
        if isinstance(g, dict):
            nm = str(g.get("name") or "")
            for old, new in replacements.items():
                if old in nm:
                    g["name"] = nm.replace(old, new)
    return notes


_RETAIL_DEPTH_LABELS: dict[str, str] = {
    "x_event": "In-store marketing event",
    "x_task": "Replenishment / shelf task",
}

_HEADER_LINE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "parent": "x_branch_transfer",
        "line": "x_branch_transfer_line",
        "description": "Transfer line",
        "move_fields": ("x_product_id", "x_qty"),
        "extra_line_fields": (
            {"name": "x_unit_price", "ttype": "float", "string": "Unit price"},
        ),
        "o2m_name": "x_line_ids",
        "o2m_string": "Lines",
        "fk_name": "x_transfer_id",
    },
    {
        "parent": "x_inventory_count",
        "line": "x_inventory_count_line",
        "description": "Count line",
        "move_fields": ("x_product_id", "x_qty_system", "x_qty_counted"),
        "extra_line_fields": (),
        "o2m_name": "x_line_ids",
        "o2m_string": "Count lines",
        "fk_name": "x_count_id",
    },
)


def promote_retail_depth_seeds(draft: dict[str, Any]) -> list[str]:
    """Promote generic depth_seed ops models to substantive retail_depth for supermarket packs."""
    if str(draft.get("domain_pack") or "") != "retail_supermarket":
        return []
    notes: list[str] = []
    label_map = {
        "Market Event": _RETAIL_DEPTH_LABELS["x_event"],
        "Market Task": _RETAIL_DEPTH_LABELS["x_task"],
        "Super Event": _RETAIL_DEPTH_LABELS["x_event"],
        "Super Task": _RETAIL_DEPTH_LABELS["x_task"],
    }
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if mid not in _RETAIL_DEPTH_LABELS or model.get("source") != "depth_seed":
            continue
        model["source"] = "retail_depth"
        model["description"] = _RETAIL_DEPTH_LABELS[mid]
        notes.append(f"apply: promoted depth_seed {mid} → retail_depth")
    for key in ("actions", "menus", "smart_buttons"):
        rows = draft.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for field in ("name", "label", "string"):
                val = str(row.get(field) or "")
                for old, new in label_map.items():
                    if old in val:
                        row[field] = val.replace(old, new.split("/")[0].strip())
    for v in draft.get("views") or []:
        if not isinstance(v, dict):
            continue
        arch = str(v.get("arch") or "")
        for old, new in label_map.items():
            short = new.split("/")[0].strip()
            if old in arch:
                v["arch"] = arch.replace(old, short)
                arch = v["arch"]
    return notes


def prune_transfer_country_field(draft: dict[str, Any]) -> list[str]:
    """Country belongs on branch master data, not inter-branch transfer headers."""
    notes: list[str] = []
    by_id = _models_index(draft)
    transfer = by_id.get("x_branch_transfer")
    if not transfer:
        return notes
    if "x_country_id" not in _field_names(transfer):
        return notes
    _drop_model_fields(draft, "x_branch_transfer", {"x_country_id"})
    for v in draft.get("views") or []:
        if not isinstance(v, dict) or str(v.get("model") or "") != "x_branch_transfer":
            continue
        arch = str(v.get("arch") or "")
        cleaned = re.sub(r'<field\b[^>]*name="x_country_id"[^>]*/>', "", arch)
        if cleaned != arch:
            v["arch"] = cleaned
    notes.append("apply: removed x_country_id from x_branch_transfer")
    return notes


def ensure_model_access_stubs(draft: dict[str, Any]) -> list[str]:
    """Add user/manager ACL rows for new x_* models (e.g. scaffolded line models)."""
    notes: list[str] = []
    existing = {
        str(r.get("model") or "").replace("model_", "", 1)
        for r in (draft.get("access_rules") or [])
        if isinstance(r, dict)
    }
    user_group = mgr_group = ""
    for group in draft.get("groups") or []:
        if not isinstance(group, dict):
            continue
        gid = str(group.get("id") or "")
        if "manager" in gid.lower():
            mgr_group = gid
        elif "user" in gid.lower():
            user_group = gid
    if not user_group or not mgr_group:
        return notes
    rules = list(draft.get("access_rules") or [])
    added = 0
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or mid in existing:
            continue
        xml = "model_" + mid.replace(".", "_")
        label = str(model.get("description") or mid)
        rules.append(
            {
                "id": f"access_{mid.replace('.', '_')}_user",
                "name": f"{label} user",
                "model": xml,
                "group": user_group,
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 0,
            }
        )
        rules.append(
            {
                "id": f"access_{mid.replace('.', '_')}_manager",
                "name": f"{label} manager",
                "model": xml,
                "group": mgr_group,
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 1,
            }
        )
        existing.add(mid)
        added += 1
    if added:
        draft["access_rules"] = rules
        notes.append(f"apply: added access stubs for {added} model(s)")
    return notes


def _copy_field_stub(parent: dict[str, Any], fname: str) -> dict[str, Any] | None:
    for field in parent.get("fields") or []:
        if isinstance(field, dict) and str(field.get("name") or "") == fname:
            return {k: v for k, v in field.items() if k != "source"}
    return None


def ensure_header_line_models(draft: dict[str, Any]) -> list[str]:
    """Scaffold *_line models when headers still carry single-product qty fields."""
    notes: list[str] = []
    by_id = _models_index(draft)
    added = False
    for spec in _HEADER_LINE_SPECS:
        parent_id = str(spec["parent"])
        line_id = str(spec["line"])
        parent = by_id.get(parent_id)
        if not parent or line_id in by_id:
            continue
        parent_names = _field_names(parent)
        move_fields = tuple(spec["move_fields"])
        if not any(fname in parent_names for fname in move_fields):
            continue
        if any(
            isinstance(f, dict)
            and f.get("ttype") == "one2many"
            and str(f.get("relation") or "").endswith("_line")
            for f in parent.get("fields") or []
        ):
            continue
        fk_name = str(spec["fk_name"])
        line_fields: list[dict[str, Any]] = [
            {"name": "x_name", "ttype": "char", "string": "Line", "required": True},
            {
                "name": fk_name,
                "ttype": "many2one",
                "relation": parent_id,
                "string": str(parent.get("description") or parent_id),
                "required": True,
            },
        ]
        for fname in move_fields:
            stub = _copy_field_stub(parent, fname)
            if stub:
                line_fields.append({**stub, "source": "apply_readiness"})
        for extra in spec.get("extra_line_fields") or ():
            if isinstance(extra, dict):
                line_fields.append({**extra, "source": "apply_readiness"})
        if _LIVE_COMPANY_FIELD not in {str(f.get("name")) for f in line_fields}:
            line_fields.append(dict(COMPANY_FIELD_LIVE))
        line_model = {
            "model": line_id,
            "description": str(spec["description"]),
            "mode": "new",
            "fields": line_fields,
            "source": "apply_readiness",
        }
        draft.setdefault("models", []).append(line_model)
        by_id[line_id] = line_model
        parent.setdefault("fields", []).append(
            {
                "name": str(spec["o2m_name"]),
                "ttype": "one2many",
                "relation": line_id,
                "relation_field": fk_name,
                "string": str(spec["o2m_string"]),
                "source": "apply_readiness",
            }
        )
        _drop_model_fields(draft, parent_id, set(move_fields))
        notes.append(f"apply: scaffolded {line_id} from header fields on {parent_id}")
        added = True
    if added:
        from app.ai_enrich import ensure_default_ui
        from app.ai_post_critique import ensure_line_model_parent_links

        notes.extend(ensure_line_model_parent_links(draft))
        notes.extend(ensure_default_ui(draft))
        notes.extend(ensure_model_access_stubs(draft))
    return notes


def strip_branch_manager_scope_rules(draft: dict[str, Any]) -> list[str]:
    """Remove USER-group branch-manager rules that lock out plain staff (GEN2-13 A3)."""
    notes: list[str] = []
    kept: list[dict[str, Any]] = []
    for rule in draft.get("record_rules") or []:
        if not isinstance(rule, dict):
            continue
        dom = str(rule.get("domain_force") or "")
        tech = str(rule.get("technical_name") or "")
        groups = rule.get("group_xml_ids") or []
        user_group = not groups or any(
            "user" in str(g).lower() and "manager" not in str(g).lower() for g in groups
        )
        if (
            user_group
            and (
                "x_branch_id.x_manager_id" in dom
                or tech.endswith("_branch_manager_scope")
                or "Branch manager scope" in str(rule.get("name") or "")
            )
        ):
            notes.append(f"apply: removed branch-manager scope rule on {rule.get('model')}")
            continue
        kept.append(rule)
    if len(kept) != len(draft.get("record_rules") or []):
        draft["record_rules"] = kept
    if str(draft.get("domain_pack") or "") == "retail_supermarket" and "x_branch" in _models_index(draft):
        suggestions = draft.setdefault("_branch_scope_suggestions", [])
        hint = (
            "Optional branch scoping: attach manager-only record rules to the manager group, "
            "or use user⇄branch membership — never manager-of-branch on the USER group."
        )
        if hint not in suggestions:
            suggestions.append(hint)
    return notes


def ensure_branch_scoped_record_rules(draft: dict[str, Any]) -> list[str]:
    """Deprecated — strips incorrect auto rules; opt-in only via suggestions."""
    return strip_branch_manager_scope_rules(draft)


def ensure_retail_comprehensive_floor(draft: dict[str, Any]) -> list[str]:
    """Close comprehensive depth gaps for retail_supermarket after apply fixes."""
    if str(draft.get("domain_pack") or "") != "retail_supermarket":
        return []
    amb = str(draft.get("_ambition") or "standard")
    if amb not in {"comprehensive", "standard", "focused"}:
        return []
    from app.ai_depth import AMBITION_TARGETS, ensure_min_automations

    if amb not in AMBITION_TARGETS:
        return []
    notes: list[str] = list(ensure_min_automations(draft, amb))  # type: ignore[arg-type]
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        if len(fields) >= 6:
            continue
        names = {str(f.get("name")) for f in fields}
        for fname, ttype, label in (
            ("x_notes", "text", "Notes"),
            ("x_sequence", "integer", "Sequence"),
        ):
            if fname not in names:
                model.setdefault("fields", []).append(
                    {
                        "name": fname,
                        "ttype": ttype,
                        "string": label,
                        "source": "apply_readiness",
                    }
                )
                notes.append(f"apply: padded {fname} on {mid} (depth floor)")
    return notes


def consolidate_redundant_inventory_models(draft: dict[str, Any]) -> list[str]:
    """Drop x_store_inventory when stock + x_inventory_count already cover inventory."""
    notes: list[str] = []
    depends = set(draft.get("depends") or [])
    if "stock" not in depends:
        return notes
    by_id = _models_index(draft)
    if "x_store_inventory" not in by_id or "x_inventory_count" not in by_id:
        return notes
    drop = "x_store_inventory"
    draft["models"] = [m for m in (draft.get("models") or []) if m.get("model") != drop]
    draft["actions"] = [
        a for a in (draft.get("actions") or []) if isinstance(a, dict) and a.get("model") != drop
    ]
    draft["menus"] = [
        m
        for m in (draft.get("menus") or [])
        if isinstance(m, dict) and str(m.get("action_xml_id") or "") != f"action_{drop}"
    ]
    draft["views"] = [
        v for v in (draft.get("views") or []) if isinstance(v, dict) and v.get("model") != drop
    ]
    draft["smart_buttons"] = [
        b
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict) and b.get("related_model") != drop and b.get("on_model") != drop
    ]
    draft["sequences"] = [
        s for s in (draft.get("sequences") or []) if isinstance(s, dict) and s.get("model") != drop
    ]
    branch = by_id.get("x_branch")
    if branch:
        branch["fields"] = [
            f
            for f in (branch.get("fields") or [])
            if not (isinstance(f, dict) and str(f.get("relation") or "") == drop)
        ]
    notes.append("apply: removed x_store_inventory (stock + x_inventory_count sufficient)")
    return notes


def sync_company_fields_with_record_rules(draft: dict[str, Any]) -> list[str]:
    """Every multi-company record rule must match an x_company_id field on the model."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for rule in draft.get("record_rules") or []:
        if not isinstance(rule, dict):
            continue
        dom = str(rule.get("domain_force") or "")
        if not _MODULE_COMPANY_IN_DOM.search(dom) and not _LIVE_COMPANY_IN_DOM.search(dom):
            continue
        model_id = str(rule.get("model") or "")
        model = by_id.get(model_id)
        if not model or str(model.get("mode") or "new") != "new":
            continue
        names = _field_names(model)
        if _LIVE_COMPANY_FIELD in names or _MODULE_COMPANY_FIELD in names:
            continue
        model.setdefault("fields", []).append(dict(COMPANY_FIELD_LIVE))
        notes.append(f"apply: added x_company_id on {model_id} (record rule alignment)")
    return notes


def ensure_global_branch_fields(draft: dict[str, Any]) -> list[str]:
    """Country (+ timezone) on branch/transfer models for global-scale prompts."""
    prompt = str(draft.get("_user_prompt") or "")
    from app.ai_depth import ensure_country_on_branch_for_global_prompt

    notes = list(ensure_country_on_branch_for_global_prompt(draft, prompt))
    if not re.search(
        r"\b(around\s+the\s+world|international|global|worldwide|multi[\s-]?country|"
        r"across\s+countries|multiple\s+countries|multiple\s+branches)\b",
        prompt,
        re.I,
    ):
        return notes
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        desc = str(model.get("description") or "").lower()
        if mid != "x_branch" and "branch" not in mid and "branch" not in desc:
            continue
        if mid == "x_branch_transfer":
            continue
        names = _field_names(model)
        if "x_timezone" not in names:
            model.setdefault("fields", []).append(
                {
                    "name": "x_timezone",
                    "ttype": "char",
                    "string": "Timezone",
                    "source": "apply_readiness",
                }
            )
            notes.append(f"apply: added x_timezone on {mid} (global prompt)")
    return notes


def polish_branch_address_fields(draft: dict[str, Any]) -> list[str]:
    """Prefer structured street/city or partner link over a lone x_address char."""
    notes: list[str] = []
    by_id = _models_index(draft)
    branch = by_id.get("x_branch")
    if not branch:
        return notes
    names = _field_names(branch)
    if "x_address_id" in names:
        return notes
    if "x_address" not in names:
        return notes
    for f in branch.get("fields") or []:
        if isinstance(f, dict) and f.get("name") == "x_address":
            f["name"] = "x_street"
            f["string"] = "Street"
            notes.append("apply: renamed x_address→x_street on x_branch")
            break
    _replace_in_arch(draft, 'name="x_address"', 'name="x_street"')
    if "x_city" not in names:
        branch.setdefault("fields", []).append(
            {"name": "x_city", "ttype": "char", "string": "City", "source": "apply_readiness"}
        )
        notes.append("apply: added x_city on x_branch")
    return notes


def _remove_transition_buttons(arch: str, from_state: str, to_state: str) -> str:
    pattern = rf'<button\b[^>]*/>'

    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        if f'data-transition-to="{to_state}"' not in tag and f"data-transition-to='{to_state}'" not in tag:
            return tag
        if (
            f"x_status != '{from_state}'" in tag
            or f'x_status != "{from_state}"' in tag
        ):
            return ""
        return tag

    return re.sub(pattern, repl, arch, flags=re.I)


def fix_workflow_skip_terminal_transitions(draft: dict[str, Any]) -> list[str]:
    """Draft/new must not skip directly to expired/failed — only cancel is allowed."""
    from app.ai_workflow_semantic import classify_state

    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or not model.get("is_workflow"):
            continue
        sf = model.get("state_field")
        if not isinstance(sf, dict):
            continue
        transitions = sf.get("transitions")
        if not isinstance(transitions, list):
            continue
        mid = str(model.get("model") or "")
        kept: list[Any] = []
        removed: list[tuple[str, str]] = []
        for tr in transitions:
            if not isinstance(tr, (list, tuple)) or len(tr) < 2:
                kept.append(tr)
                continue
            a, b = str(tr[0]), str(tr[1])
            if (
                a.lower() in _INITIAL_STATES
                and classify_state(b) == "terminal_negative"
                and b.lower() not in _ALLOWED_INITIAL_TERMINALS
            ):
                removed.append((a, b))
                continue
            kept.append(tr)
        if not removed:
            continue
        sf["transitions"] = kept
        model["state_field"] = sf
        notes.append(
            f"apply: pruned skip transitions on {mid}: "
            + ", ".join(f"{a}→{b}" for a, b in removed)
        )
        for v in draft.get("views") or []:
            if not isinstance(v, dict) or str(v.get("model") or "") != mid:
                continue
            if str(v.get("type") or "") != "form":
                continue
            arch = str(v.get("arch") or "")
            for a, b in removed:
                arch = _remove_transition_buttons(arch, a, b)
            v["arch"] = arch
    return notes


def _currency_field_name(fields: dict[str, dict[str, Any]]) -> str:
    for name in ("x_currency_id", "currency_id"):
        f = fields.get(name)
        if isinstance(f, dict) and f.get("ttype") == "many2one":
            return name
    return "x_currency_id"


def _field_ttype(fields: dict[str, dict[str, Any]], name: str) -> str:
    f = fields.get(name)
    if not isinstance(f, dict):
        return "float"
    ttype = str(f.get("ttype") or "float")
    if ttype == "float" and (
        f.get("currency_field")
        or any(
            isinstance(other, dict)
            and other.get("ttype") == "many2one"
            and other.get("relation") == "res.currency"
            for other in fields.values()
        )
    ):
        if any(k in name for k in ("amount", "price", "total", "cost", "fee", "subtotal")):
            return "monetary"
    return ttype


def _upsert_custom_code_block(
    draft: dict[str, Any],
    *,
    model: str,
    source_file: str,
    content: str,
    reason: str,
) -> None:
    blocks = draft.setdefault("custom_code_blocks", [])
    if not isinstance(blocks, list):
        draft["custom_code_blocks"] = blocks = []
    payload = {
        "source_file": source_file,
        "kind": "python",
        "content": content,
        "reason": reason,
        "model": model,
    }
    for i, block in enumerate(blocks):
        if isinstance(block, dict) and str(block.get("model") or "") == model:
            blocks[i] = {**block, **payload}
            return
    blocks.append(payload)


def _drop_model_fields(draft: dict[str, Any], model_id: str, drop: set[str]) -> None:
    by_id = _models_index(draft)
    model = by_id.get(model_id)
    if not model or not drop:
        return
    model["fields"] = [
        f
        for f in (model.get("fields") or [])
        if not (isinstance(f, dict) and str(f.get("name") or "") in drop)
    ]
    for name in drop:
        _replace_in_arch(draft, f'name="{name}"', "")


def fix_broken_shift_assignee_smart_buttons(draft: dict[str, Any]) -> list[str]:
    """Shift rows must not stat-link events/tasks via x_staff_id (now hr.employee)."""
    notes: list[str] = []
    kept: list[dict[str, Any]] = []
    for btn in draft.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        if (
            str(btn.get("on_model") or "") == "x_staff_shift"
            and str(btn.get("related_model") or "") in {"x_event", "x_task"}
            and str(btn.get("relation_field") or "") == "x_staff_id"
        ):
            notes.append(
                f"apply: dropped broken shift smart button → {btn.get('related_model')}"
            )
            continue
        kept.append(btn)
    if len(kept) != len(draft.get("smart_buttons") or []):
        draft["smart_buttons"] = kept
    return notes


def fix_assignee_staff_relations(draft: dict[str, Any]) -> list[str]:
    """Event/task assignee should point to hr.employee or res.users — not shift rows."""
    notes: list[str] = []
    depends = set(draft.get("depends") or [])
    target = "hr.employee" if "hr" in depends else "res.users"
    label = "Employee" if target == "hr.employee" else "Assigned user"
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if mid not in {"x_event", "x_task"}:
            continue
        for f in model.get("fields") or []:
            if not isinstance(f, dict) or f.get("name") != "x_staff_id":
                continue
            rel = str(f.get("relation") or "")
            if rel not in _BAD_ASSIGNEE_RELATIONS:
                continue
            f["relation"] = target
            f["string"] = label
            notes.append(f"apply: x_staff_id on {mid} → {target}")
    notes.extend(fix_broken_shift_assignee_smart_buttons(draft))
    return notes


def _model_module_basename(model: str) -> str:
    return model.replace(".", "_")


def _model_class_token(model: str) -> str:
    return "".join(p.title() for p in _model_module_basename(model).split("_") if p)


def ensure_line_currency_fields(draft: dict[str, Any]) -> list[str]:
    """Propagate order currency onto line models for monetary computes."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or "line" not in mid.lower():
            continue
        names = _field_names(model)
        if "x_currency_id" in names:
            continue
        order_field = next(
            (
                f
                for f in (model.get("fields") or [])
                if isinstance(f, dict)
                and f.get("ttype") == "many2one"
                and str(f.get("relation") or "") in by_id
                and "line" not in str(f.get("relation") or "").lower()
            ),
            None,
        )
        if not order_field:
            continue
        order = by_id.get(str(order_field.get("relation") or "")) or {}
        order_names = _field_names(order)
        if "x_currency_id" not in order_names:
            continue
        model.setdefault("fields", []).append(
            {
                "name": "x_currency_id",
                "ttype": "many2one",
                "relation": "res.currency",
                "string": "Currency",
                "related": f"{order_field.get('name')}.x_currency_id",
                "readonly": True,
                "source": "apply_readiness",
            }
        )
        notes.append(f"apply: related x_currency_id on {mid}")
    return notes


def normalize_line_monetary_fields(draft: dict[str, Any]) -> list[str]:
    """Align line amount fields with x_currency_id when present; staff rate pairs (A6)."""
    notes: list[str] = []
    amount_names = {
        "x_subtotal",
        "x_total",
        "x_amount",
        "x_price_unit",
        "x_tax_amount",
        "x_total_amount",
        "x_rate",
    }
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        names = _field_names(model)
        currency_field = "x_currency_id" if "x_currency_id" in names else None
        if mid == "x_staff_rate" and "x_rate" in names and not currency_field:
            model.setdefault("fields", []).append(
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "relation": "res.currency",
                    "string": "Currency",
                    "source": "apply_readiness",
                }
            )
            currency_field = "x_currency_id"
            notes.append("apply: added x_currency_id on x_staff_rate for monetary pairing")
        if not currency_field:
            continue
        for f in model.get("fields") or []:
            if not isinstance(f, dict):
                continue
            fname = str(f.get("name") or "")
            if fname not in amount_names:
                continue
            if str(f.get("ttype") or "") in {"float", "monetary"}:
                f["ttype"] = "monetary"
                f["currency_field"] = currency_field
                f.setdefault("widget", "monetary")
                notes.append(f"apply: monetary field {mid}.{fname}")
    return notes


def apply_line_subtotal_computes(draft: dict[str, Any]) -> list[str]:
    """Stored qty × unit-price compute for line subtotals (module export via custom_code_blocks)."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or "line" not in mid.lower():
            continue
        fields = {
            str(f.get("name")): f for f in (model.get("fields") or []) if isinstance(f, dict)
        }
        qty = next((n for n in _LINE_QTY_NAMES if n in fields), None)
        price = next((n for n in _LINE_PRICE_NAMES if n in fields), None)
        total = next((n for n in _LINE_TOTAL_NAMES if n in fields), None)
        if not qty or not price or not total:
            continue
        total_label = str(fields[total].get("string") or "Subtotal")
        class_name = f"{_model_class_token(mid)}LineSubtotal"
        method = f"_compute_{total}"
        basename = _model_module_basename(mid)
        source_file = f"models/{basename}.py"
        if _field_ttype(fields, total) == "monetary":
            curr = _currency_field_name(fields)
            field_lines = (
                f"    {total} = fields.Monetary(\n"
                f"        string={total_label!r},\n"
                f"        compute={method!r},\n"
                f"        store=True,\n"
                f"        currency_field={curr!r},\n"
                f"    )\n"
            )
        else:
            field_lines = (
                f"    {total} = fields.Float(\n"
                f"        string={total_label!r},\n"
                f"        compute={method!r},\n"
                f"        store=True,\n"
                f"    )\n"
            )
        content = (
            "from odoo import api, fields, models\n\n\n"
            f"class {class_name}(models.Model):\n"
            f"    _inherit = {mid!r}\n\n"
            f"{field_lines}\n"
            f"    @api.depends({qty!r}, {price!r})\n"
            f"    def {method}(self):\n"
            f"        for rec in self:\n"
            f"            rec.{total} = (rec.{qty} or 0.0) * (rec.{price} or 0.0)\n"
        )
        _upsert_custom_code_block(
            draft,
            model=mid,
            source_file=source_file,
            content=content,
            reason="apply_readiness: line subtotal compute",
        )
        notes.append(f"apply: line subtotal compute on {mid} ({qty}×{price}→{total})")
    return notes


def apply_order_header_total_computes(draft: dict[str, Any]) -> list[str]:
    """Roll up line subtotals into header x_amount_total on order models."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        fields = {
            str(f.get("name")): f for f in (model.get("fields") or []) if isinstance(f, dict)
        }
        line_field = next(
            (
                f
                for f in fields
                if fields[f].get("ttype") == "one2many"
                and str(fields[f].get("relation") or "") in by_id
                and "line" in str(fields[f].get("relation") or "").lower()
            ),
            None,
        )
        total_field = next(
            (n for n in ("x_amount_total", "x_total", "x_amount") if n in fields),
            None,
        )
        if not line_field or not total_field:
            continue
        line_model = str(fields[line_field].get("relation") or "")
        line_def = by_id.get(line_model) or {}
        line_names = _field_names(line_def)
        subtotal = next((n for n in _LINE_TOTAL_NAMES if n in line_names), None)
        if not subtotal:
            continue
        total_label = str(fields[total_field].get("string") or "Total")
        class_name = f"{_model_class_token(mid)}HeaderTotal"
        method = f"_compute_{total_field}"
        basename = _model_module_basename(mid)
        source_file = f"models/{basename}.py"
        if _field_ttype(fields, total_field) == "monetary":
            curr = _currency_field_name(fields)
            field_lines = (
                f"    {total_field} = fields.Monetary(\n"
                f"        string={total_label!r},\n"
                f"        compute={method!r},\n"
                f"        store=True,\n"
                f"        currency_field={curr!r},\n"
                f"    )\n"
            )
        else:
            field_lines = (
                f"    {total_field} = fields.Float(\n"
                f"        string={total_label!r},\n"
                f"        compute={method!r},\n"
                f"        store=True,\n"
                f"    )\n"
            )
        content = (
            "from odoo import api, fields, models\n\n\n"
            f"class {class_name}(models.Model):\n"
            f"    _inherit = {mid!r}\n\n"
            f"{field_lines}\n"
            f"    @api.depends('{line_field}.{subtotal}')\n"
            f"    def {method}(self):\n"
            f"        for rec in self:\n"
            f"            rec.{total_field} = sum(rec.{line_field}.mapped('{subtotal}'))\n"
        )
        _upsert_custom_code_block(
            draft,
            model=mid,
            source_file=source_file,
            content=content,
            reason="apply_readiness: order header total compute",
        )
        notes.append(f"apply: header total compute on {mid} (sum {line_model}.{subtotal})")
    return notes


def clear_resolved_compute_suggestions(draft: dict[str, Any]) -> list[str]:
    """Drop line-total suggestions once custom compute blocks exist; dedupe leftovers."""
    notes: list[str] = []
    computed_models = {
        str(b.get("model"))
        for b in merge_custom_code_blocks(draft)
        if isinstance(b, dict) and b.get("model")
    }
    raw = draft.get("_compute_suggestions")
    if not isinstance(raw, list):
        draft["_compute_suggestions"] = []
        return notes
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    dropped = 0
    for row in raw:
        if not isinstance(row, dict):
            continue
        model = str(row.get("model") or "")
        if model in computed_models:
            dropped += 1
            continue
        if model in seen:
            dropped += 1
            continue
        seen.add(model)
        kept.append(row)
    draft["_compute_suggestions"] = kept
    if dropped:
        notes.append(f"apply: cleared {dropped} resolved compute suggestion(s)")
    return notes


def fix_inventory_adjustment_workflow(draft: dict[str, Any]) -> list[str]:
    """Ensure rejected terminal is reachable from draft on adjustment workflows."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or str(model.get("model") or "") != "x_inventory_adjustment":
            continue
        if not model.get("is_workflow"):
            continue
        sf = model.get("state_field")
        if not isinstance(sf, dict):
            continue
        states = [str(s) for s in (sf.get("states") or [])]
        if "rejected" not in states:
            continue
        transitions = list(sf.get("transitions") or [])
        pairs: set[tuple[str, str]] = set()
        for tr in transitions:
            if isinstance(tr, (list, tuple)) and len(tr) >= 2:
                pairs.add((str(tr[0]), str(tr[1])))
        added: list[tuple[str, str]] = []
        if "draft" in states and "rejected" in states and ("draft", "rejected") not in pairs:
            transitions.append(["draft", "rejected"])
            pairs.add(("draft", "rejected"))
            added.append(("draft", "rejected"))
        if not added:
            continue
        sf["transitions"] = transitions
        model["state_field"] = sf
        mid = str(model.get("model") or "")
        for v in draft.get("views") or []:
            if not isinstance(v, dict) or str(v.get("model") or "") != mid:
                continue
            if str(v.get("type") or "") != "form":
                continue
            arch = str(v.get("arch") or "")
            if 'data-transition-to="rejected"' in arch:
                continue
            header_close = "</header>"
            if header_close in arch:
                btn = (
                    '<button string="Reject" type="object" class="oe_highlight" '
                    'invisible="x_status != \'draft\'" data-transition-to="rejected"/>'
                )
                v["arch"] = arch.replace(header_close, btn + header_close, 1)
        notes.append(
            "apply: inventory adjustment rejected transitions: "
            + ", ".join(f"{a}→{b}" for a, b in added)
        )
    return notes


def consolidate_inventory_count_fields(draft: dict[str, Any]) -> list[str]:
    """Remove redundant count columns; compute variance from system vs counted."""
    notes: list[str] = []
    by_id = _models_index(draft)
    model = by_id.get("x_inventory_count")
    if not model:
        return notes
    names = _field_names(model)
    if "x_qty_system" not in names or "x_qty_counted" not in names:
        return notes
    drop = {n for n in ("x_actual_qty",) if n in names}
    if drop:
        _drop_model_fields(draft, "x_inventory_count", drop)
        notes.append("apply: dropped redundant x_actual_qty on x_inventory_count")
        names -= drop
    if "x_variance" in names or "x_variance_percent" in names:
        class_name = "XInventoryCountVariance"
        content = (
            "from odoo import api, fields, models\n\n\n"
            "class XInventoryCountVariance(models.Model):\n"
            "    _inherit = 'x_inventory_count'\n\n"
            "    x_variance = fields.Float(\n"
            "        string='Variance',\n"
            "        compute='_compute_x_variance_fields',\n"
            "        store=True,\n"
            "    )\n"
            "    x_variance_percent = fields.Float(\n"
            "        string='Variance %',\n"
            "        compute='_compute_x_variance_fields',\n"
            "        store=True,\n"
            "    )\n\n"
            "    @api.depends('x_qty_system', 'x_qty_counted')\n"
            "    def _compute_x_variance_fields(self):\n"
            "        for rec in self:\n"
            "            system = rec.x_qty_system or 0.0\n"
            "            counted = rec.x_qty_counted or 0.0\n"
            "            rec.x_variance = counted - system\n"
            "            rec.x_variance_percent = (\n"
            "                (rec.x_variance / system * 100.0) if system else 0.0\n"
            "            )\n"
        )
        _upsert_custom_code_block(
            draft,
            model="x_inventory_count",
            source_file="models/x_inventory_count.py",
            content=content,
            reason="apply_readiness: inventory count variance compute",
        )
        notes.append("apply: inventory count variance compute")
    return notes


def wire_stock_document_links(draft: dict[str, Any]) -> list[str]:
    """Link-only stock.picking / warehouse hooks for transfer + adjustment models."""
    notes: list[str] = []
    depends = set(draft.get("depends") or [])
    if "stock" not in depends:
        return notes
    by_id = _models_index(draft)
    link_fields = {
        "x_branch_transfer": ("x_picking_id", "stock.picking", "Stock transfer"),
        "x_inventory_adjustment": ("x_picking_id", "stock.picking", "Stock picking"),
    }
    for mid, (fname, relation, label) in link_fields.items():
        model = by_id.get(mid)
        if not model:
            continue
        names = _field_names(model)
        if fname not in names:
            model.setdefault("fields", []).append(
                {
                    "name": fname,
                    "ttype": "many2one",
                    "relation": relation,
                    "string": label,
                    "source": "apply_readiness",
                }
            )
            notes.append(f"apply: added {fname} on {mid} (stock link-only)")
    buttons = draft.get("smart_buttons")
    if not isinstance(buttons, list):
        buttons = []
        draft["smart_buttons"] = buttons
    existing = {
        (
            str(b.get("on_model") or ""),
            str(b.get("related_model") or ""),
            str(b.get("relation_field") or ""),
        )
        for b in buttons
        if isinstance(b, dict)
    }
    for mid, (fname, relation, label) in link_fields.items():
        if mid not in by_id:
            continue
        key = (mid, relation, fname)
        if key in existing:
            continue
        buttons.append(
            {
                "on_model": mid,
                "label": label,
                "related_model": relation,
                "relation_field": fname,
                "icon": "fa-truck",
                "source": "apply_readiness",
                "link_only": True,
            }
        )
        notes.append(f"apply: stock smart button on {mid}")
    branch = by_id.get("x_branch")
    if branch and ("x_branch", "stock.warehouse", "x_warehouse_id") not in existing:
        names = _field_names(branch)
        if "x_warehouse_id" not in names:
            branch.setdefault("fields", []).append(
                {
                    "name": "x_warehouse_id",
                    "ttype": "many2one",
                    "relation": "stock.warehouse",
                    "string": "Warehouse",
                    "source": "apply_readiness",
                }
            )
            notes.append("apply: added x_warehouse_id on x_branch (stock link-only)")
        buttons.append(
            {
                "on_model": "x_branch",
                "label": "Warehouse",
                "related_model": "stock.warehouse",
                "relation_field": "x_warehouse_id",
                "icon": "fa-archive",
                "source": "apply_readiness",
                "link_only": True,
            }
        )
    draft.setdefault("review_notes", [])
    if isinstance(draft["review_notes"], list):
        note = (
            "Stock: x_picking_id / x_warehouse_id are link-only — wire to stock.picking "
            "in Odoo before go-live; no automatic quant moves from metadata export."
        )
        if note not in draft["review_notes"]:
            draft["review_notes"].append(note)
    return notes


def prune_transfer_timezone_field(draft: dict[str, Any]) -> list[str]:
    """Timezone belongs on branch master data, not inter-branch transfers."""
    notes: list[str] = []
    by_id = _models_index(draft)
    transfer = by_id.get("x_branch_transfer")
    if not transfer:
        return notes
    names = _field_names(transfer)
    if "x_timezone" not in names:
        return notes
    _drop_model_fields(draft, "x_branch_transfer", {"x_timezone"})
    notes.append("apply: removed x_timezone from x_branch_transfer")
    return notes


def scrub_unused_domain_tags(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    tags = draft.get("tags")
    if not isinstance(tags, list) or "pos" not in tags:
        return notes
    models = draft.get("models") or []
    has_pos = any(
        isinstance(m, dict)
        and (
            "pos" in str(m.get("model") or "").lower()
            or "pos" in str(m.get("description") or "").lower()
        )
        for m in models
    )
    if has_pos:
        return notes
    draft["tags"] = [t for t in tags if str(t).lower() != "pos"]
    notes.append("apply: removed unused pos domain tag")
    return notes


def ensure_operational_companion_models(draft: dict[str, Any]) -> list[str]:
    """Restore x_task when x_event exists — common depth floor after reuse merge."""
    notes: list[str] = []
    by_id = _models_index(draft)
    if "x_event" not in by_id or "x_task" in by_id:
        return notes
    prompt = str(draft.get("_user_prompt") or "")
    word = _domain_label_word(prompt)
    branch_id = "x_branch" if "x_branch" in by_id else None
    fields: list[dict[str, Any]] = [
        {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
        {"name": "x_code", "ttype": "char", "string": "Reference"},
        {
            "name": "x_date_deadline",
            "ttype": "date",
            "string": "Deadline",
            "required": True,
        },
        {
            "name": "x_status",
            "ttype": "selection",
            "string": "Status",
            "selection": "[('draft','Draft'),('open','Open'),('done','Done'),('cancelled','Cancelled')]",
        },
        {"name": "x_notes", "ttype": "text", "string": "Notes"},
    ]
    if branch_id:
        fields.insert(
            2,
            {
                "name": "x_branch_id",
                "ttype": "many2one",
                "relation": branch_id,
                "string": "Branch",
            },
        )
    if "hr" in set(draft.get("depends") or []):
        fields.append(
            {
                "name": "x_staff_id",
                "ttype": "many2one",
                "relation": "hr.employee",
                "string": "Assigned",
            }
        )
    draft.setdefault("models", []).append(
        {
            "model": "x_task",
            "description": f"{word} Task",
            "mode": "new",
            "fields": fields,
            "source": "apply_readiness",
        }
    )
    notes.append("apply: restored x_task companion for x_event (depth floor)")
    return notes


def dedupe_line_parent_m2o_fields(draft: dict[str, Any]) -> list[str]:
    """Keep one parent m2o on line models; prefer scaffold canonical names (GEN2-13 A4)."""
    notes: list[str] = []
    by_id = _models_index(draft)
    canonical = {str(spec["line"]): str(spec["fk_name"]) for spec in _HEADER_LINE_SPECS}
    for mid, model in by_id.items():
        if not mid.endswith("_line"):
            continue
        parent_m2os = [
            f
            for f in (model.get("fields") or [])
            if isinstance(f, dict)
            and f.get("ttype") == "many2one"
            and str(f.get("relation") or "") in by_id
            and not str(f.get("relation") or "").endswith("_line")
        ]
        if len(parent_m2os) <= 1:
            continue
        keep_name = canonical.get(mid) or str(parent_m2os[0].get("name") or "")
        drop_names = {str(f.get("name")) for f in parent_m2os if str(f.get("name")) != keep_name}
        if not drop_names:
            continue
        model["fields"] = [
            f
            for f in (model.get("fields") or [])
            if not (isinstance(f, dict) and str(f.get("name")) in drop_names)
        ]
        for drop in drop_names:
            _replace_in_arch(draft, f'name="{drop}"', "")
            _replace_in_arch(draft, drop, keep_name)
        for btn in draft.get("smart_buttons") or []:
            if not isinstance(btn, dict):
                continue
            if str(btn.get("related_model") or "") == mid and str(btn.get("relation_field") or "") in drop_names:
                btn["relation_field"] = keep_name
        notes.append(f"apply: deduped parent m2o on {mid} (keep {keep_name})")
    return notes


def prune_filler_search_filters(draft: dict[str, Any]) -> list[str]:
    """Drop generic All / Has name search filters (GEN2-13 A6)."""
    notes: list[str] = []
    for v in draft.get("views") or []:
        if not isinstance(v, dict) or str(v.get("type") or "") != "search":
            continue
        arch = str(v.get("arch") or "")
        if not arch:
            continue
        filters = re.findall(r"<filter\b[^>]*(?:/>|>[^<]*</filter>)", arch, flags=re.I)
        keep: list[str] = []
        removed = 0
        for flt in filters:
            name_m = re.search(r'name="([^"]+)"', flt)
            string_m = re.search(r'string="([^"]+)"', flt)
            name = (name_m.group(1) if name_m else "").lower()
            label = (string_m.group(1) if string_m else "").lower()
            if name in _FILLER_FILTER_NAMES or label in {"all", "has name"}:
                removed += 1
                continue
            keep.append(flt)
        if removed:
            open_tag = re.match(r"(<search[^>]*>)", arch, flags=re.I)
            if open_tag:
                v["arch"] = open_tag.group(1) + "".join(keep) + "</search>"
                notes.append(f"apply: pruned filler search filters on {v.get('model')}")
    return notes


_FILLER_FILTER_NAMES = frozenset({"all", "has_name"})


def remove_line_model_root_menus(draft: dict[str, Any]) -> list[str]:
    """Line models are reachable via parent forms — drop root menus (GEN2-13 A6)."""
    notes: list[str] = []
    line_models = {m for m in _models_index(draft) if m.endswith("_line")}
    if not line_models:
        return notes
    action_models = {
        str(a.get("technical_name") or a.get("id") or ""): str(a.get("model") or "")
        for a in (draft.get("actions") or [])
        if isinstance(a, dict)
    }
    kept: list[dict[str, Any]] = []
    for menu in draft.get("menus") or []:
        if not isinstance(menu, dict):
            kept.append(menu)
            continue
        action_ref = str(menu.get("action_xml_id") or menu.get("action") or "")
        model = action_models.get(action_ref.split(".")[-1], "")
        if not model:
            for a in draft.get("actions") or []:
                if isinstance(a, dict) and str(a.get("technical_name") or "") in action_ref:
                    model = str(a.get("model") or "")
                    break
        parent = str(menu.get("parent_xml_id") or menu.get("parent") or "")
        if model in line_models and (not parent or parent.endswith("_menu_root")):
            notes.append(f"apply: removed root menu for line model {model}")
            continue
        kept.append(menu)
    draft["menus"] = kept
    return notes


def prune_link_table_sequences(draft: dict[str, Any]) -> list[str]:
    """Link/junction tables should not carry ir.sequence specs."""
    notes: list[str] = []
    linkish = {
        mid
        for mid in _models_index(draft)
        if "link" in mid or mid.endswith("_rel")
    }
    seqs = draft.get("sequences") or []
    if not isinstance(seqs, list) or not linkish:
        return notes
    kept = [s for s in seqs if isinstance(s, dict) and str(s.get("model") or "") not in linkish]
    if len(kept) != len(seqs):
        draft["sequences"] = kept
        notes.append("apply: dropped sequences on link/junction models")
    return notes


def reconcile_depth_metadata(draft: dict[str, Any]) -> list[str]:
    """Recompute depth block after apply passes; clear stale regenerate flags."""
    notes: list[str] = []
    from app.ai_depth import build_depth_block, depth_checklist

    amb = draft.get("_ambition") or "standard"
    block = build_depth_block(draft, ambition=amb)
    seeded = any(
        isinstance(m, dict) and m.get("source") == "depth_seed" for m in (draft.get("models") or [])
    )
    gaps_no_seed = block["metrics_without_seeds"]
    from app.ai_depth import AMBITION_TARGETS

    t = AMBITION_TARGETS.get(amb, AMBITION_TARGETS["standard"])
    seeded_only = seeded and int(gaps_no_seed.get("model_count") or 0) < int(t["min_models"])
    block["seeded"] = seeded_only
    block["checklist"] = depth_checklist(draft, amb)
    draft["_depth"] = {
        **(draft.get("_depth") if isinstance(draft.get("_depth"), dict) else {}),
        **block,
    }
    if not block["gaps"] and seeded:
        draft["_depth"]["seeded"] = False
        notes.append("apply: depth targets met — cleared seed regenerate flag")
    elif not block["gaps"]:
        notes.append("apply: depth targets met")
    return notes


def finalize_draft_readiness_metadata(draft: dict[str, Any]) -> list[str]:
    """Align critique readiness with scorecard after apply passes."""
    from app.ai_draft_scorecard import draft_scorecard

    notes: list[str] = []
    prompt = str(draft.get("_user_prompt") or "")
    scored = draft_scorecard(draft, user_prompt=prompt)
    draft["_scorecard"] = scored
    score = float(scored.get("score_0_10") or 0)
    findings = scored.get("findings") or []
    crit = draft.get("_critique")
    if isinstance(crit, dict) and score >= 9.9 and not findings:
        crit["ready"] = True
        stale = "Critique flagged not ready but gave no details"
        crit_notes = [n for n in (crit.get("notes") or []) if stale not in str(n)]
        crit["notes"] = crit_notes
        # Scorecard is authoritative after apply passes — drop stale repair suggestions.
        crit["suggestions"] = [
            s
            for s in (crit.get("suggestions") or [])
            if str(s).startswith("unapplied:")
        ]
        draft["_critique"] = crit
        notes.append("apply: critique marked ready (scorecard clean)")
    draft["_meta"] = {
        **(draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}),
        "score_0_10": score,
    }
    return notes


def dedupe_enrich_warnings(warnings: list[str]) -> list[str]:
    """Drop exact duplicate enrich warning lines before UI display."""
    seen: set[str] = set()
    kept: list[str] = []
    for warning in warnings:
        text = str(warning or "")
        if not text or text in seen:
            continue
        seen.add(text)
        kept.append(text)
    return kept


def filter_stale_enrich_warnings(warnings: list[str], draft: dict[str, Any]) -> list[str]:
    """Drop enrich warnings superseded by apply-readiness fixes."""
    by_id = _models_index(draft)
    depth = draft.get("_depth") if isinstance(draft.get("_depth"), dict) else {}
    kept: list[str] = []
    for warning in warnings:
        w = str(warning or "")
        if w.startswith("depth: company on "):
            model = w.replace("depth: company on ", "", 1).strip()
            names = _field_names(by_id.get(model) or {})
            if "company_id" in names or "x_company_id" in names:
                continue
        if w == "depth padded via generic seeds — regenerate recommended":
            if depth.get("ok") and not depth.get("gaps"):
                continue
        if w.startswith("depth: ambition=") and "still missing" in w:
            if depth.get("ok") and not depth.get("gaps"):
                continue
        if w.startswith("presentation:") and "line-total compute suggestion" in w:
            computed = {
                str(b.get("model"))
                for b in merge_custom_code_blocks(draft)
                if isinstance(b, dict) and b.get("model")
            }
            if computed:
                continue
        if w.startswith("quality: dropped orphan field "):
            tail = w.replace("quality: dropped orphan field ", "", 1)
            if "." in tail:
                mid, rest = tail.split(".", 1)
                fname = rest.split(" ", 1)[0].strip()
                names = _field_names(by_id.get(mid) or {})
                if fname in names:
                    continue
        if w.startswith("quality: remapped orphan "):
            tail = w.replace("quality: remapped orphan ", "", 1)
            token = tail.split(" ", 1)[0].strip()
            if "." in token:
                mid, fname = token.split(".", 1)
                if fname in _field_names(by_id.get(mid) or {}):
                    continue
        kept.append(w)
    return dedupe_enrich_warnings(kept)


def sanitize_automation_names(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        for key in ("name", "description"):
            val = str(auto.get(key) or "")
            cleaned = re.sub(r"\s+", " ", val).strip()
            if cleaned and cleaned != val:
                auto[key] = cleaned
                notes.append(f"apply: sanitized automation {key}")
        actions = auto.get("safe_actions")
        if isinstance(actions, list):
            for action in actions:
                if not isinstance(action, dict):
                    continue
                summary = str(action.get("summary") or "")
                cleaned = re.sub(r"\s+", " ", summary).strip()
                if cleaned and cleaned != summary:
                    action["summary"] = cleaned
                    notes.append("apply: sanitized automation action summary")
    return notes


def sanitize_automation_state_references(draft: dict[str, Any]) -> list[str]:
    """Align automation labels/domains with actual workflow states on the target model."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        mid = str(auto.get("model") or "")
        model = by_id.get(mid)
        if not model:
            continue
        status_field = next(
            (
                f
                for f in (model.get("fields") or [])
                if isinstance(f, dict) and str(f.get("name") or "") == "x_status"
            ),
            None,
        )
        states = _selection_keys(status_field.get("selection")) if status_field else set()
        name = str(auto.get("name") or "")
        desc = str(auto.get("description") or "")
        if states and "overdue" not in states and re.search(r"\boverdue\b", f"{name} {desc}", re.I):
            auto["name"] = re.sub(r"\boverdue\b", "deadline", name, flags=re.I)
            auto["description"] = re.sub(
                r"\boverdue\b",
                "past deadline",
                desc,
                flags=re.I,
            )
            notes.append(f"apply: renamed automation on {mid} (no overdue state)")
        actions = auto.get("safe_actions")
        if isinstance(actions, list):
            for action in actions:
                if not isinstance(action, dict):
                    continue
                summary = str(action.get("summary") or "")
                cleaned = re.sub(r"\s+", " ", summary).strip()
                if states and "overdue" not in states and re.search(r"\boverdue\b", cleaned, re.I):
                    cleaned = re.sub(r"\boverdue\b", "deadline", cleaned, flags=re.I)
                if cleaned and cleaned != summary:
                    action["summary"] = cleaned
                    notes.append(f"apply: sanitized automation action summary on {mid}")
        dom = str(auto.get("filter_domain") or "")
        if dom and states and "'x_status'" in dom:
            in_match = re.search(r"\('x_status',\s*'in',\s*\[(.*?)\]\)", dom)
            if in_match:
                vals = set(re.findall(r"'([^']+)'", in_match.group(1)))
                invalid = vals - states
                if invalid:
                    cleaned_vals = sorted(vals & states)
                    if cleaned_vals:
                        replacement = ", ".join(f"'{v}'" for v in cleaned_vals)
                        auto["filter_domain"] = (
                            dom[: in_match.start(1)] + replacement + dom[in_match.end(1) :]
                        )
                        notes.append(f"apply: trimmed invalid x_status values on {mid} automation")
    return notes


def _automation_signature(auto: dict[str, Any]) -> tuple[str, str, str]:
    mid = str(auto.get("model") or "")
    trigger = str(auto.get("trigger") or "")
    dom = re.sub(r"\s+", "", str(auto.get("filter_domain") or ""))
    return (mid, trigger, dom)


def _automation_keep_rank(auto: dict[str, Any]) -> tuple[int, int, int, str]:
    actions = auto.get("safe_actions") or []
    has_write = any(
        isinstance(action, dict)
        and str(action.get("kind") or "") in {"object_write", "update_field"}
        for action in actions
    )
    activity_only = bool(actions) and not has_write
    src = str(auto.get("source") or "")
    src_pri = {"rules_engine": 0, "depth_seed": 1, "depth_floor": 1, "critique": 2}.get(src, 5)
    return (0 if activity_only else 1, len(actions), src_pri, str(auto.get("name") or ""))


def sanitize_automation_object_writes(draft: dict[str, Any]) -> list[str]:
    """Drop object_write values that are not valid selection keys on the target model."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        mid = str(auto.get("model") or "")
        model = by_id.get(mid)
        if not model:
            continue
        fields_by_name = {
            str(field.get("name")): field
            for field in (model.get("fields") or [])
            if isinstance(field, dict) and field.get("name")
        }
        actions = auto.get("safe_actions")
        if not isinstance(actions, list):
            continue
        kept: list[dict[str, Any]] = []
        dropped = False
        for action in actions:
            if not isinstance(action, dict):
                continue
            kind = str(action.get("kind") or "")
            field = str(action.get("field") or "")
            if kind in {"object_write", "update_field"} and field in fields_by_name:
                fdef = fields_by_name[field]
                if str(fdef.get("ttype")) == "selection":
                    keys = _selection_keys(fdef.get("selection"))
                    val = str(action.get("value") or "")
                    if keys and val and val not in keys:
                        dropped = True
                        notes.append(
                            f"apply: dropped invalid {field}={val!r} write on {mid} automation"
                        )
                        continue
            kept.append(action)
        if dropped:
            if not kept:
                kept.append(
                    {
                        "kind": "next_activity",
                        "summary": str(auto.get("name") or f"{mid} follow-up"),
                    }
                )
            auto["safe_actions"] = kept
    return notes


def dedupe_automations_by_signature(draft: dict[str, Any]) -> list[str]:
    """Keep one automation per (model, trigger, filter_domain) — prefer activity-only rules."""
    notes: list[str] = []
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return notes
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        sig = _automation_signature(auto)
        if not sig[0] or not sig[1]:
            passthrough.append(auto)
            continue
        groups.setdefault(sig, []).append(auto)
    kept: list[dict[str, Any]] = list(passthrough)
    for sig, group in groups.items():
        if len(group) == 1:
            kept.append(group[0])
            continue
        group.sort(key=_automation_keep_rank)
        kept.append(group[0])
        notes.append(
            f"apply: deduped {len(group) - 1} automation(s) on {sig[0]} ({sig[1]})"
        )
    draft["automations"] = kept
    return notes


def run_apply_readiness_pass(draft: dict[str, Any]) -> list[str]:
    """Fix blockers before Apply / template export."""
    notes: list[str] = []
    notes.extend(demote_parallel_billing_models(draft))
    notes.extend(scrub_payment_capture_fields(draft))
    notes.extend(normalize_depth_seed_naming(draft))
    notes.extend(promote_retail_depth_seeds(draft))
    notes.extend(resolve_duplicate_address_fields(draft))
    notes.extend(polish_branch_address_fields(draft))
    notes.extend(fix_branch_transfer_incoming_o2m(draft))
    notes.extend(consolidate_redundant_inventory_models(draft))
    notes.extend(ensure_relation_module_depends(draft))
    notes.extend(fix_assignee_staff_relations(draft))
    notes.extend(fix_reuse_link_only_consistency(draft))
    notes.extend(wire_reuse_stock_documents(draft))
    notes.extend(normalize_company_fields_for_live(draft))
    notes.extend(sync_company_fields_with_record_rules(draft))
    notes.extend(strip_branch_manager_scope_rules(draft))
    notes.extend(ensure_global_branch_fields(draft))
    notes.extend(prune_transfer_timezone_field(draft))
    notes.extend(prune_transfer_country_field(draft))
    notes.extend(ensure_header_line_models(draft))
    notes.extend(dedupe_line_parent_m2o_fields(draft))
    notes.extend(fix_workflow_skip_terminal_transitions(draft))
    notes.extend(fix_inventory_adjustment_workflow(draft))
    notes.extend(consolidate_inventory_count_fields(draft))
    notes.extend(wire_stock_document_links(draft))
    notes.extend(scrub_unused_domain_tags(draft))
    notes.extend(ensure_line_currency_fields(draft))
    notes.extend(normalize_line_monetary_fields(draft))
    notes.extend(apply_line_subtotal_computes(draft))
    notes.extend(apply_promotion_discount_line_computes(draft))
    notes.extend(apply_order_header_total_computes(draft))
    notes.extend(consolidate_header_monetary_fields(draft))
    notes.extend(scrub_misapplied_stock_document_links(draft))
    notes.extend(ensure_transaction_document_links(draft))
    notes.extend(ensure_campaign_order_links(draft))
    notes.extend(clear_resolved_compute_suggestions(draft))
    notes.extend(sanitize_automation_names(draft))
    notes.extend(sanitize_automation_object_writes(draft))
    notes.extend(sanitize_automation_state_references(draft))
    notes.extend(dedupe_automations_by_signature(draft))
    from app.ai_model_quality import dedupe_automation_safe_actions

    notes.extend(dedupe_automation_safe_actions(draft))
    notes.extend(ensure_search_filter_names(draft))
    notes.extend(dedupe_search_view_filters(draft))
    notes.extend(prune_filler_search_filters(draft))
    notes.extend(remove_line_model_root_menus(draft))
    notes.extend(prune_link_table_sequences(draft))
    notes.extend(scrub_unknown_arch_field_refs(draft))
    notes.extend(sanitize_empty_field_tags(draft))
    notes.extend(_repair_corrupted_company_arch_refs(draft))
    notes.extend(ensure_operational_companion_models(draft))
    notes.extend(ensure_retail_comprehensive_floor(draft))
    notes.extend(reconcile_depth_metadata(draft))
    return notes


__all__ = [
    "apply_line_subtotal_computes",
    "apply_order_header_total_computes",
    "apply_promotion_discount_line_computes",
    "clear_resolved_compute_suggestions",
    "consolidate_header_monetary_fields",
    "consolidate_inventory_count_fields",
    "consolidate_redundant_inventory_models",
    "ensure_search_filter_names",
    "dedupe_search_view_filters",
    "dedupe_automations_by_signature",
    "dedupe_enrich_warnings",
    "demote_parallel_billing_models",
    "ensure_campaign_order_links",
    "ensure_branch_scoped_record_rules",
    "ensure_header_line_models",
    "ensure_model_access_stubs",
    "ensure_global_branch_fields",
    "ensure_operational_companion_models",
    "ensure_transaction_document_links",
    "ensure_line_currency_fields",
    "ensure_retail_comprehensive_floor",
    "ensure_relation_module_depends",
    "ensure_unique_sequence_prefixes",
    "filter_stale_enrich_warnings",
    "finalize_draft_readiness_metadata",
    "fix_assignee_staff_relations",
    "fix_branch_transfer_incoming_o2m",
    "fix_broken_shift_assignee_smart_buttons",
    "fix_inventory_adjustment_workflow",
    "fix_reuse_link_only_consistency",
    "fix_workflow_skip_terminal_transitions",
    "normalize_company_fields_for_export",
    "normalize_line_monetary_fields",
    "polish_branch_address_fields",
    "prepare_spec_for_live_apply",
    "promote_retail_depth_seeds",
    "prune_transfer_country_field",
    "reconcile_depth_metadata",
    "resolve_duplicate_address_fields",
    "run_apply_readiness_pass",
    "sanitize_automation_names",
    "sanitize_automation_object_writes",
    "sanitize_automation_state_references",
    "scrub_misapplied_stock_document_links",
    "scrub_payment_capture_fields",
    "scrub_unused_domain_tags",
    "sync_company_fields_with_record_rules",
    "wire_reuse_stock_documents",
    "wire_stock_document_links",
]
