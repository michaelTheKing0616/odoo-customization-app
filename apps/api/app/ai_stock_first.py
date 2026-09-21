"""Stock-first residual contract — domain-agnostic, pack-optional.

Stock Community apps own contacts, quotations, invoices, employees, calendar,
tasks, products, and expenses. Custom ``x_*`` is only the document those apps
do not cover, plus ``_line`` / ``_party`` satellites.

Packs remain a retrieval floor when they match. This module is the strategy
for every other domain, and the teaching signal for a later frontier model.
"""

from __future__ import annotations

import re
from typing import Any

from app.text_negation import span_is_negated

# Prompt nouns that are stock documents — never a custom residual header.
STOCK_DOCUMENT_LEAVES: frozenset[str] = frozenset(
    {
        "invoice",
        "bill",
        "payment",
        "client",
        "customer",
        "contact",
        "partner",
        "employee",
        "staff",
        "product",
        "sku",
        "warehouse",
        "quotation",
        "quote",
        "order",
        "lead",
        "task",
        "event",
        "user",
        "company",
        "currency",
        "timesheet",
        "expense",
        "meeting",
    }
)

# Staff / fee-earner roles → hr.employee, not a custom roster.
STAFF_ROLE_LEAVES: frozenset[str] = frozenset(
    {
        "attorney",
        "lawyer",
        "counsel",
        "doctor",
        "nurse",
        "teacher",
        "practitioner",
        "technician",
        "employee",
        "staff",
        "crew",
        "associate",
        "fee_earner",
    }
)

# When this stock model is reused, collapse x_* whose leaf is in the set.
STOCK_CLONE_LEAVES: dict[str, frozenset[str]] = {
    "res.partner": frozenset({"client", "customer", "contact", "client_contact"}),
    "account.move": frozenset({"invoice", "bill", "payment", "receivable", "payable"}),
    "hr.employee": STAFF_ROLE_LEAVES,
    "calendar.event": frozenset({"event", "meeting", "hearing"}),
    "project.task": frozenset({"task", "todo"}),
    "sale.order": frozenset({"sale_order", "quotation", "quote"}),
    "product.product": frozenset({"product", "sku"}),
    "hr.expense": frozenset({"expense"}),
    "crm.lead": frozenset({"lead", "opportunity", "pipeline"}),
}

_STOCK_OPS_MODELS: frozenset[str] = frozenset(
    {
        "account.move",
        "sale.order",
        "hr.employee",
        "calendar.event",
        "project.task",
        "project.project",
        "hr.expense",
        "crm.lead",
        "purchase.order",
        "account.analytic.line",
    }
)

_EXPLICIT_RESIDUAL = re.compile(
    r"(?i)(?:custom\s+residual|the\s+residual)\s+is\s+(?:the\s+)?"
    r"(?:x_)?([a-z][a-z0-9]+(?:[\s_-][a-z0-9]+){0,4})"
)

_RESIDUAL_STOP = frozenset(
    {
        "file",
        "document",
        "record",
        "model",
        "app",
        "only",
        "the",
        "a",
        "an",
        "custom",
        "residual",
        "is",
        "header",
    }
)

_LEAF_RE = re.compile(r"[a-z0-9]+")


def normalize_residual_leaf(raw: str) -> str:
    """Turn 'matter file only' / 'policy document' into a model leaf."""
    words = [
        w
        for w in _LEAF_RE.findall((raw or "").lower())
        if w not in _RESIDUAL_STOP and len(w) >= 3
    ]
    if not words:
        return ""
    leaf = "_".join(words[:2])
    if leaf in STOCK_DOCUMENT_LEAVES or leaf in STAFF_ROLE_LEAVES:
        return ""
    return leaf


def extract_explicit_residuals(text: str) -> list[tuple[str, str, str]]:
    """Parse 'Custom residual is the X' / ## Custom residual into (key, x_model, reason)."""
    found: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    blob = text or ""
    for match in _EXPLICIT_RESIDUAL.finditer(blob):
        if span_is_negated(blob, match.start()):
            continue
        leaf = normalize_residual_leaf(match.group(1))
        if not leaf or leaf in seen:
            continue
        seen.add(leaf)
        found.append(
            (
                leaf,
                f"x_{leaf}",
                (
                    f"{leaf.replace('_', ' ').title()} document — "
                    "stock Community apps do not replace this residual."
                ),
            )
        )
    try:
        from app.ai_operator_brief import stated_residual_kind

        kind, body = stated_residual_kind(blob)
    except Exception:  # noqa: BLE001
        kind, body = "unstated", ""
    if kind == "named" and body:
        leaf = normalize_residual_leaf(body)
        if leaf and leaf not in seen:
            seen.add(leaf)
            found.append(
                (
                    leaf,
                    f"x_{leaf}",
                    (
                        f"{leaf.replace('_', ' ').title()} document — "
                        "stock Community apps do not replace this residual."
                    ),
                )
            )
    return found


def reuse_models_from_draft(draft: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    blob = draft.get("reuse")
    if isinstance(blob, dict):
        out.update(str(x) for x in (blob.get("models") or []) if x)
        plan = blob.get("plan")
        if isinstance(plan, dict):
            out.update(str(x) for x in (plan.get("models") or []) if x)
            for row in plan.get("decisions") or []:
                if isinstance(row, dict) and row.get("model"):
                    out.add(str(row["model"]))
    return out


def forbid_new_models_from_draft(draft: dict[str, Any]) -> set[str]:
    blob = draft.get("reuse")
    if not isinstance(blob, dict):
        return set()
    plan = blob.get("plan")
    if not isinstance(plan, dict):
        return set()
    return {str(x) for x in (plan.get("forbid_new_models") or []) if x}


def stock_ops_reused(draft: dict[str, Any]) -> set[str]:
    """Stock operational models (or module depends) the draft already reuses."""
    models = reuse_models_from_draft(draft)
    depends = {str(x) for x in (draft.get("depends") or []) if x}
    if "account" in depends:
        models.add("account.move")
    if "sale" in depends:
        models.add("sale.order")
    if "hr" in depends:
        models.add("hr.employee")
    if "calendar" in depends:
        models.add("calendar.event")
    if "project" in depends:
        models.add("project.project")
    if "crm" in depends:
        models.add("crm.lead")
    if "hr_timesheet" in depends:
        models.add("account.analytic.line")
    if "hr_expense" in depends:
        models.add("hr.expense")
    return models & _STOCK_OPS_MODELS


def is_reuse_rich(draft: dict[str, Any]) -> bool:
    """True when a reuse plan already covers two+ operational stock apps.

    Packs are always reuse-rich (explicit floor). Depends alone do not count —
    unpacked seeds used to list ``hr``/``account`` by default.
    """
    if draft.get("domain_pack"):
        return True
    return len(reuse_models_from_draft(draft) & _STOCK_OPS_MODELS) >= 2


def attach_reuse_plan_to_draft(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    available_models: list[str] | None = None,
    installed_modules: list[str] | None = None,
    stock_catalog: list[dict[str, Any]] | None = None,
    rejected_reuse_models: list[str] | None = None,
) -> list[str]:
    """Always stamp a reuse plan (pack seed, unpacked seed, closer)."""
    from app.ai_reuse_planner import apply_reuse_plan, plan_reuse

    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    pack_stock = draft.get("reuse_stock")
    if not isinstance(pack_stock, list):
        pack_stock = draft.get("_pack_reuse_stock")
    ctx = connection_catalog_from_draft(draft)
    available = available_models if available_models is not None else ctx.get("available_models")
    installed = installed_modules if installed_modules is not None else ctx.get("installed_modules")
    catalog = stock_catalog if stock_catalog is not None else ctx.get("stock")
    plan = plan_reuse(
        prompt,
        available_models=available,
        installed_modules=installed,
        pack_reuse_stock=pack_stock if isinstance(pack_stock, list) else None,
        stock_catalog=catalog,
        rejected_reuse_models=rejected_reuse_models,
    )
    return apply_reuse_plan(draft, plan)


def connection_catalog_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    raw = draft.get("_connection_catalog")
    if not isinstance(raw, dict):
        return {}
    return raw


def stamp_connection_catalog(
    draft: dict[str, Any],
    *,
    available_models: list[str] | None = None,
    installed_modules: list[str] | None = None,
    stock_catalog: list[dict[str, Any]] | None = None,
) -> None:
    """Remember live ir.model catalog so pack-seed / closer stay connection-aware."""
    if available_models is None and installed_modules is None and not stock_catalog:
        return
    draft["_connection_catalog"] = {
        "available_models": list(available_models or []),
        "installed_modules": list(installed_modules or []),
        "stock": [
            {
                "model": str(e.get("model") or ""),
                "name": str(e.get("name") or e.get("model") or ""),
                "app": str(e.get("app") or ""),
            }
            for e in (stock_catalog or [])
            if isinstance(e, dict) and e.get("model")
        ],
    }


def restore_pack_identity(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
) -> list[str]:
    """Restamp ``_pack_model_ids`` from the current factory when ``domain_pack`` is set.

    Does not infer a pack from the prompt — tests and unpacked drafts may stamp
    ``domain_pack`` as a closer flag without meaning "replace models".
    Clears pack authority when residual brief noun diverges (Visitor Log ≠ Restaurant).
    """
    notes: list[str] = []
    pack_id = str(draft.get("domain_pack") or "")
    if not pack_id:
        return notes
    try:
        from app.ai_residual_identity import draft_mismatches_residual_identity

        if draft_mismatches_residual_identity(draft, prompt=user_prompt):
            draft.pop("domain_pack", None)
            draft.pop("_pack_model_ids", None)
            draft.pop("_pack_reuse_stock", None)
            notes.append(
                f"stock_first: cleared divergent pack {pack_id} for residual identity"
            )
            return notes
    except Exception:  # noqa: BLE001
        pass
    from app.ai_domain_packs import load_domain_pack

    pack = load_domain_pack(pack_id)
    if not pack:
        return notes
    pack_ids = [
        str(m["model"])
        for m in (pack.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    ]
    if pack_ids and list(draft.get("_pack_model_ids") or []) != pack_ids:
        notes.append(f"stock_first: restamped _pack_model_ids ({len(pack_ids)})")
    if pack_ids:
        draft["_pack_model_ids"] = pack_ids
    if pack.get("reuse_stock") and not draft.get("_pack_reuse_stock"):
        draft["_pack_reuse_stock"] = list(pack.get("reuse_stock") or [])
    if "multi_company" in pack:
        draft["multi_company"] = bool(pack.get("multi_company"))
        if not draft["multi_company"]:
            from app.multi_company_pack import strip_multi_company_record_rules

            notes.extend(strip_multi_company_record_rules(draft))
    return notes


def _is_pack_satellite(mid: str, allowed: set[str]) -> bool:
    if not mid.startswith("x_"):
        return False
    if mid in allowed:
        return True
    for suffix in ("_line", "_party"):
        if mid.endswith(suffix):
            parent = mid[: -len(suffix)]
            if parent in allowed:
                return True
    return False


_CLIP_LOOP_LEAVES: frozenset[str] = frozenset(
    {
        "deposit",
        "bill",
        "invoice",
        "task",
        "event",
        "milestone",
        "compliance",
        "fee",
        "staff",
        "staffing",
        "payment",
        "document",
        "expense",
    }
)


_PACKED_ACCOUNTING_LEAVES: frozenset[str] = frozenset(
    {
        "bill",
        "invoice",
        "payment",
        "deposit",
        "receivable",
        "payable",
    }
)


def _leaf_is_stock_clone(mid: str, ops: set[str], *, packed: bool) -> bool:
    if not mid.startswith("x_"):
        return False
    leaf = mid[2:]
    if leaf.endswith("_line") or leaf.endswith("_party"):
        return False
    if leaf in STAFF_ROLE_LEAVES:
        return True
    if packed and leaf in _CLIP_LOOP_LEAVES:
        return True
    for stock, leaves in STOCK_CLONE_LEAVES.items():
        if stock in ops and leaf in leaves:
            return True
    return False


def _leaf_is_scorecard_clone(mid: str, ops: set[str], *, packed: bool) -> bool:
    """Scorecard clones — staff + parallel accounting, not every packed task/event.

    Packed CLIP_LOOP still clips in ``clip_to_stock_first_floor``. Scoring every
    ``x_task`` on a retail pack would 10.0-wash a supermarket fixture that still
    carries calendar leftovers, or fail a 9.9 hygiene gate for the wrong reason.
    """
    if not mid.startswith("x_"):
        return False
    leaf = mid[2:]
    if leaf.endswith("_line") or leaf.endswith("_party"):
        return False
    if leaf in STAFF_ROLE_LEAVES:
        return True
    if packed and leaf in _PACKED_ACCOUNTING_LEAVES:
        return True
    for stock, leaves in STOCK_CLONE_LEAVES.items():
        if stock in ops and leaf in leaves:
            return True
    return False


def _pack_keep_ids(draft: dict[str, Any]) -> set[str]:
    """Allowlist for clip/scorecard. Does not mutate the draft."""
    keep = {str(x) for x in (draft.get("_pack_model_ids") or []) if x}
    pack_id = str(draft.get("domain_pack") or "")
    if keep or not pack_id:
        return keep
    from app.ai_domain_packs import load_domain_pack

    pack = load_domain_pack(pack_id)
    if not pack:
        return keep
    return {
        str(m["model"])
        for m in (pack.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def list_stock_clone_models(draft: dict[str, Any]) -> list[str]:
    """Staff / parallel-accounting clones that must not score 10.0."""
    pack_keep = _pack_keep_ids(draft)
    packed = bool(pack_keep) or bool(draft.get("domain_pack"))
    ops = stock_ops_reused(draft)
    found: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        if _is_pack_satellite(mid, pack_keep):
            continue
        if _leaf_is_scorecard_clone(mid, ops, packed=packed):
            found.append(mid)
    return sorted(found)


_STAFF_FK_ALIASES = frozenset(
    {
        "x_attorney_id",
        "x_lawyer_id",
        "x_counsel_id",
        "x_doctor_id",
        "x_nurse_id",
        "x_practitioner_id",
    }
)


def _collapse_duplicate_employee_fks(draft: dict[str, Any]) -> list[str]:
    """After retarget, keep one hr.employee M2O (x_employee_id)."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        fields = model.get("fields") or []
        if not isinstance(fields, list):
            continue
        has_employee = any(
            isinstance(f, dict)
            and f.get("name") == "x_employee_id"
            and str(f.get("relation") or "") == "hr.employee"
            for f in fields
        )
        kept: list[Any] = []
        for field in fields:
            if not isinstance(field, dict):
                kept.append(field)
                continue
            fname = str(field.get("name") or "")
            if (
                fname in _STAFF_FK_ALIASES
                and str(field.get("relation") or "") == "hr.employee"
            ):
                if has_employee:
                    notes.append(
                        f"stock_first: dropped duplicate {model.get('model')}.{fname}"
                    )
                    continue
                field = dict(field)
                field["name"] = "x_employee_id"
                field["string"] = field.get("string") or "Employee"
                has_employee = True
                notes.append(
                    f"stock_first: renamed {model.get('model')}.{fname} → x_employee_id"
                )
            kept.append(field)
        model["fields"] = kept
    return notes


def _drop_orphan_custom_code(draft: dict[str, Any]) -> list[str]:
    """Drop Python blocks whose model was clipped or never existed."""
    notes: list[str] = []
    known = {
        str(m.get("model") or "")
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    blocks = draft.get("custom_code_blocks")
    if not isinstance(blocks, list):
        return notes
    kept: list[Any] = []
    for block in blocks:
        if not isinstance(block, dict):
            kept.append(block)
            continue
        mid = str(block.get("model") or "")
        if mid.startswith("x_") and mid not in known:
            notes.append(f"stock_first: dropped orphan code block {mid}")
            continue
        kept.append(block)
    draft["custom_code_blocks"] = kept
    return notes


def clip_to_stock_first_floor(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
) -> list[str]:
    """Drop LLM stock-document clones. Pack models on ``_pack_model_ids`` stay.

    Does not replace the draft with the pack factory — domain_pack on a closer
    test means "skip this rewrite", not "install the clinic pack".
    """
    notes: list[str] = []
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    notes.extend(restore_pack_identity(draft, user_prompt=prompt))
    pack_keep = {str(x) for x in (draft.get("_pack_model_ids") or []) if x}

    notes.extend(attach_reuse_plan_to_draft(draft, user_prompt=prompt))

    from app.ai_domain_briefing import attach_domain_briefing

    attach_domain_briefing(draft, user_prompt=prompt)

    ops = stock_ops_reused(draft)
    packed = bool(pack_keep) or bool(draft.get("domain_pack"))
    known = {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    removed: set[str] = set()
    for mid in known:
        if not mid.startswith("x_"):
            continue
        if _is_pack_satellite(mid, pack_keep):
            continue
        if _leaf_is_stock_clone(mid, ops, packed=packed):
            removed.add(mid)

    if removed:
        for mid in list(removed):
            for other in known:
                if other == f"{mid}_line" or other == f"{mid}_party":
                    removed.add(other)
        from app.ai_domain_packs import _purge_draft_artifacts_for_models
        from app.ai_odoo_app_bar import _retarget_removed_relations

        notes.extend(_retarget_removed_relations(draft, removed))
        _purge_draft_artifacts_for_models(draft, removed)
        notes.append(
            "stock_first: clipped LLM inventions " + ", ".join(sorted(removed))
        )

    notes.extend(_collapse_duplicate_employee_fks(draft))
    notes.extend(_drop_orphan_custom_code(draft))

    pack_id = str(draft.get("domain_pack") or "")
    comp = draft.get("_completeness")
    if pack_id and isinstance(comp, list):
        draft["_completeness"] = [
            row
            for row in comp
            if not (
                isinstance(row, dict)
                and str(row.get("id") or "").startswith("noun_uncovered:")
            )
        ]
    return notes


# Stock hosts already have ``name`` / sequences — LLM/closer must not inject identity clones.
_STOCK_INHERIT_JUNK_FIELD_NAMES = frozenset(
    {
        "x_name",
        "x_code",  # stock docs use their own sequences
    }
)


def strip_stock_inherit_junk_fields(draft: dict[str, Any]) -> list[str]:
    """Drop padding on ``mode=inherit`` stock models (never required x_name on sale.order)."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if str(model.get("mode") or "") != "inherit":
            continue
        if mid.startswith("x_"):
            continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        kept: list[dict[str, Any]] = []
        dropped: list[str] = []
        for f in fields:
            name = str(f.get("name") or "")
            # Bridge / domain fields stay (x_matter_id, x_bar_number, rates, …)
            if name in _STOCK_INHERIT_JUNK_FIELD_NAMES:
                dropped.append(name)
                continue
            # Never mark identity clones required on stock
            if name.startswith("x_") and name.endswith("_name") and f.get("required"):
                f = {**f, "required": False}
                notes.append(f"stock_first: cleared required on inherit {mid}.{name}")
            kept.append(f)
        if dropped:
            notes.append(
                f"stock_first: stripped junk inherit fields on {mid}: {', '.join(dropped)}"
            )
        model["fields"] = kept
        # Parallel workflow chrome on stock hosts (e.g. project.task x_status) is not residual
        if model.get("is_workflow") or model.get("state_field"):
            model.pop("is_workflow", None)
            model.pop("state_field", None)
            model["fields"] = [
                f
                for f in (model.get("fields") or [])
                if not (
                    isinstance(f, dict)
                    and str(f.get("name")) == "x_status"
                    and str(f.get("ttype")) == "selection"
                )
            ]
            notes.append(f"stock_first: demoted stock-host workflow chrome on {mid}")
            mixins = [m for m in (model.get("mixins") or []) if m]
            # mail.thread on stock host inherit is usually already there — drop duplicate stamp
            if "mail.thread" in mixins or "mail.activity.mixin" in mixins:
                model["mixins"] = [
                    m
                    for m in mixins
                    if m not in {"mail.thread", "mail.activity.mixin"}
                ]
    # Drop sequences targeting stock inherit models
    seqs = draft.get("sequences")
    if isinstance(seqs, list):
        kept_seq = []
        for s in seqs:
            if not isinstance(s, dict):
                continue
            sm = str(s.get("model") or "")
            if sm and not sm.startswith("x_") and str(s.get("field") or "") in {
                "x_code",
                "x_name",
            }:
                notes.append(f"stock_first: dropped stock-host sequence on {sm}")
                continue
            kept_seq.append(s)
        draft["sequences"] = kept_seq
    return notes


__all__ = [
    "STAFF_ROLE_LEAVES",
    "STOCK_CLONE_LEAVES",
    "STOCK_DOCUMENT_LEAVES",
    "attach_reuse_plan_to_draft",
    "clip_to_stock_first_floor",
    "extract_explicit_residuals",
    "forbid_new_models_from_draft",
    "is_reuse_rich",
    "list_stock_clone_models",
    "normalize_residual_leaf",
    "restore_pack_identity",
    "reuse_models_from_draft",
    "stock_ops_reused",
    "strip_stock_inherit_junk_fields",
]
