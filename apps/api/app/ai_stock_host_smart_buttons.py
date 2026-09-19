"""Stock-host smart buttons — stamp useful button_box links when residual M2Os justify them.

When an x_* residual many2one points at a stock host (Contacts, Employees, Orders, …)
and the brief (or field presence) makes navigation useful, ensure a smart button on that
host. Visitor-style paper logs stay off Contacts (not a second Contacts app).

Completeness ≠ Cert ≠ Autopilot. Promote stays human.
"""

from __future__ import annotations

import re
from typing import Any

# Hosts we will inherit-button onto. Expand when UAT shows a useful navigation gap.
STOCK_HOST_BUTTON_BY_MODEL: dict[str, dict[str, Any]] = {
    "res.partner": {
        "icon": "fa-id-card-o",
        "note": "Applied as inherit on Contacts button_box",
        "require": "partner_tie",
        "depends": "contacts",
    },
    "hr.employee": {
        "icon": "fa-id-badge",
        "note": "Applied as inherit on Employees button_box",
        "require": "employee_tie",
        "depends": "hr",
    },
    # Related stock documents → button_box (sale.order shape), not header Identity.
    "crm.lead": {
        "icon": "fa-bullseye",
        "note": "Applied as inherit on CRM lead button_box",
        "require": "m2o_present",
        "depends": "crm",
    },
    "sale.order": {
        "icon": "fa-shopping-cart",
        "note": "Applied as inherit on Sales order button_box",
        "require": "m2o_present",
        "depends": "sale",
    },
    "account.move": {
        "icon": "fa-file-text-o",
        "note": "Applied as inherit on Invoice button_box",
        "require": "m2o_present",
        "depends": "account",
    },
    "account.payment": {
        "icon": "fa-money",
        "note": "Applied as inherit on Payment button_box",
        "require": "m2o_present",
        "depends": "account",
    },
    "purchase.order": {
        "icon": "fa-credit-card",
        "note": "Applied as inherit on Purchase order button_box",
        "require": "m2o_present",
        "depends": "purchase",
    },
    "calendar.event": {
        "icon": "fa-calendar",
        "note": "Applied as inherit on Calendar button_box",
        "require": "m2o_present",
        "depends": "calendar",
    },
    "project.task": {
        "icon": "fa-tasks",
        "note": "Applied as inherit on Project task button_box",
        "require": "m2o_present",
        "depends": "project",
    },
    "project.project": {
        "icon": "fa-folder-open",
        "note": "Applied as inherit on Project button_box",
        "require": "m2o_present",
        "depends": "project",
    },
    "stock.picking": {
        "icon": "fa-truck",
        "note": "Applied as inherit on Transfer button_box",
        "require": "m2o_present",
        "depends": "stock",
    },
    "hr.expense": {
        "icon": "fa-ticket",
        "note": "Applied as inherit on Expense button_box",
        "require": "m2o_present",
        "depends": "hr_expense",
    },
    "pos.order": {
        "icon": "fa-shopping-bag",
        "note": "Applied as inherit on PoS order button_box",
        "require": "m2o_present",
        "depends": "point_of_sale",
    },
    "pos.session": {
        "icon": "fa-desktop",
        "note": "Applied as inherit on PoS session button_box",
        "require": "m2o_present",
        "depends": "point_of_sale",
    },
}

_PARTNER_TIE_RE = re.compile(
    r"(?i)\b(?:loyalty\s+)?punch\s*cards?|loyalty\s+cards?|"
    r"\btied to the customer|\bcustomer\s*\(\s*contacts\s*\)|"
    r"\blink(?:ed)?\s+to\s+(?:the\s+)?(?:customer|contact|partner)|"
    r"\b(?:on|from)\s+contacts\b|\bcontacts?\s+form\b"
)
_PARTNER_SKIP_RE = re.compile(
    r"(?i)\b(?:visitor|guest)\s+logs?|\bkey\s+logs?|\bcall\s+logs?|"
    r"\bsign[- ]?in\s+(?:sheet|log|book)|\battendance\s+logs?\b|"
    r"\bvisitor\s+(?:book|register|sheet)\b"
)
_EMPLOYEE_TIE_RE = re.compile(
    r"(?i)\b(?:employees?|staff|hr\.employee|human\s+resources?)\b"
)


def _forbidden_hosts(draft: dict[str, Any]) -> set[str]:
    brief = draft.get("_operator_brief") if isinstance(draft.get("_operator_brief"), dict) else {}
    forbidden_apps = {
        str(x).strip().lower() for x in (brief.get("forbidden_bridges") or []) if x
    }
    out: set[str] = set()
    app_to_models = {
        "crm": {"crm.lead"},
        "account": {"account.move", "account.payment"},
        "sale": {"sale.order"},
        "calendar": {"calendar.event"},
        "project": {"project.task", "project.project"},
        "purchase": {"purchase.order"},
        "stock": {"stock.picking"},
    }
    for app, models in app_to_models.items():
        if app in forbidden_apps:
            out.update(models)
    return out


def _prompt_allows_host(host: str, *, prompt: str, policy: dict[str, Any]) -> bool:
    require = str(policy.get("require") or "m2o_present")
    text = prompt or ""
    if require == "partner_tie":
        if _PARTNER_SKIP_RE.search(text) and not _PARTNER_TIE_RE.search(text):
            return False
        return bool(_PARTNER_TIE_RE.search(text))
    if require == "employee_tie":
        return bool(_EMPLOYEE_TIE_RE.search(text))
    return True


def _is_lineish(mid: str) -> bool:
    leaf = mid.replace("x_", "")
    return leaf.endswith("_line") or leaf.endswith("line") or "_line_" in leaf


def _header_models(draft: dict[str, Any]) -> list[dict[str, Any]]:
    models = [m for m in (draft.get("models") or []) if isinstance(m, dict)]
    headers = [
        m
        for m in models
        if str(m.get("model") or "").startswith("x_")
        and str(m.get("mode") or "new") != "inherit"
        and not _is_lineish(str(m.get("model") or ""))
    ]
    return headers or [
        m
        for m in models
        if str(m.get("model") or "").startswith("x_")
        and str(m.get("mode") or "new") != "inherit"
    ]


def _existing_keys(draft: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (
            str(b.get("on_model") or ""),
            str(b.get("related_model") or ""),
            str(b.get("relation_field") or ""),
        )
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }


def partner_tie_allows_contacts_button(prompt: str) -> bool:
    """True when the brief explicitly ties the residual to Contacts (punch / loyalty)."""
    text = prompt or ""
    if _PARTNER_SKIP_RE.search(text) and not _PARTNER_TIE_RE.search(text):
        return False
    return bool(_PARTNER_TIE_RE.search(text))


def _is_residual_full_app(draft: dict[str, Any]) -> bool:
    """True for residual new-app drafts — not Prefer/inherit field packs."""
    grain = str(draft.get("grain") or "").strip()
    if grain in {"field_pack", "feature_slice"}:
        return False
    if draft.get("_component"):
        return False
    engine = draft.get("_generation_engine")
    if isinstance(engine, dict):
        eg = str(engine.get("grain") or "")
        if eg in {"field_pack", "feature_slice"}:
            return False
        if engine.get("capability") in {"option_a_authored", "option_a_standalone", "stock_reuse"}:
            return False
    # Inherit-only drafts are field packs even when grain unset.
    models = [m for m in (draft.get("models") or []) if isinstance(m, dict)]
    x_new = [
        m
        for m in models
        if str(m.get("model") or "").startswith("x_")
        and str(m.get("mode") or "new") != "inherit"
    ]
    inherit_only = models and not x_new and any(
        str(m.get("mode") or "") == "inherit" or not str(m.get("model") or "").startswith("x_")
        for m in models
    )
    if inherit_only:
        return False
    return bool(x_new) or grain in {"", "full_app"}


def _drop_disallowed_partner_buttons(draft: dict[str, Any], *, prompt: str) -> list[str]:
    """Drop invented Contacts host buttons for visitor registers and residual full_app.

    Prefer Contacts inherit (field_pack) and explicit punch/loyalty partner_tie keep them.
    Residual M2Os to res.partner stay form fields — not «{app}» smart buttons on Contacts.
    """
    notes: list[str] = []
    text = prompt or ""
    if partner_tie_allows_contacts_button(text):
        return notes
    # Visitor-style OR residual full_app without partner_tie: no Contacts host invent.
    drop = bool(_PARTNER_SKIP_RE.search(text)) or _is_residual_full_app(draft)
    if not drop:
        return notes
    btns = list(draft.get("smart_buttons") or [])
    filtered = [
        b
        for b in btns
        if not (isinstance(b, dict) and str(b.get("on_model") or "") == "res.partner")
    ]
    if len(filtered) != len(btns):
        draft["smart_buttons"] = filtered
        reason = (
            "visitor-style register"
            if _PARTNER_SKIP_RE.search(text)
            else "residual full_app (M2O≠smart button)"
        )
        notes.append(f"stock_host_btn: dropped Contacts smart button ({reason})")
    return notes


def apply_stock_host_smart_buttons(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Stamp missing stock-host smart buttons; drop visitor Contacts noise."""
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    notes.extend(_drop_disallowed_partner_buttons(draft, prompt=text))

    forbidden = _forbidden_hosts(draft)
    existing = _existing_keys(draft)
    added: list[str] = []
    display = str(draft.get("display_name") or "").strip()

    for model in _header_models(draft):
        mid = str(model.get("model") or "")
        label = (
            display
            or str(model.get("description") or "")
            or mid.replace("x_", "").replace("_", " ").title()
        )
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if str(field.get("ttype") or "") != "many2one":
                continue
            rel = str(field.get("relation") or "")
            fname = str(field.get("name") or "")
            if not rel or not fname or rel not in STOCK_HOST_BUTTON_BY_MODEL:
                continue
            if rel in forbidden:
                continue
            policy = STOCK_HOST_BUTTON_BY_MODEL[rel]
            if not _prompt_allows_host(rel, prompt=text, policy=policy):
                # Employee: field presence on residual is enough when name signals staff.
                if not (
                    str(policy.get("require")) == "employee_tie"
                    and ("employee" in fname or "staff" in fname)
                ):
                    continue
            key = (rel, mid, fname)
            if key in existing:
                continue
            # Prefer one button per host↔residual (first FK wins).
            if any(k[0] == rel and k[1] == mid for k in existing):
                continue
            draft.setdefault("smart_buttons", []).append(
                {
                    "on_model": rel,
                    "label": label,
                    "related_model": mid,
                    "relation_field": fname,
                    "icon": str(policy.get("icon") or "fa-list"),
                    "requires_inherit_view": True,
                    "note": str(policy.get("note") or ""),
                    "source": "stock_host_smart_button",
                }
            )
            existing.add(key)
            added.append(f"{rel}←{mid}.{fname}")
            dep = str(policy.get("depends") or "")
            if dep:
                depends = [str(x) for x in (draft.get("depends") or []) if x]
                if dep not in depends:
                    depends.append(dep)
                    draft["depends"] = depends

    if added:
        notes.append(
            "stock_host_btn: ensured "
            + ", ".join(added[:8])
            + " (navigation from stock host → residual)"
        )
    return notes


def draft_missing_stock_host_smart_buttons(
    draft: dict[str, Any], *, prompt: str = ""
) -> bool:
    """True when a justified stock-host button is absent (Retry/Expert hygiene)."""
    text = prompt or str(draft.get("_user_prompt") or "")
    forbidden = _forbidden_hosts(draft)
    existing = _existing_keys(draft)
    for model in _header_models(draft):
        mid = str(model.get("model") or "")
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if str(field.get("ttype") or "") != "many2one":
                continue
            rel = str(field.get("relation") or "")
            fname = str(field.get("name") or "")
            if not rel or not fname or rel not in STOCK_HOST_BUTTON_BY_MODEL:
                continue
            if rel in forbidden:
                continue
            policy = STOCK_HOST_BUTTON_BY_MODEL[rel]
            if not _prompt_allows_host(rel, prompt=text, policy=policy):
                if not (
                    str(policy.get("require")) == "employee_tie"
                    and ("employee" in fname or "staff" in fname)
                ):
                    continue
            if any(k[0] == rel and k[1] == mid for k in existing):
                continue
            return True
    if _PARTNER_SKIP_RE.search(text) and not _PARTNER_TIE_RE.search(text):
        for b in draft.get("smart_buttons") or []:
            if isinstance(b, dict) and str(b.get("on_model") or "") == "res.partner":
                return True
    return False




def scrub_residual_contacts_host_buttons(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Drop invented Contacts host buttons; do not stamp new stock-host buttons."""
    text = prompt or str(draft.get("_user_prompt") or "")
    return _drop_disallowed_partner_buttons(draft, prompt=text)


__all__ = [
    "STOCK_HOST_BUTTON_BY_MODEL",
    "apply_stock_host_smart_buttons",
    "draft_missing_stock_host_smart_buttons",
    "partner_tie_allows_contacts_button",
    "scrub_residual_contacts_host_buttons",
]
