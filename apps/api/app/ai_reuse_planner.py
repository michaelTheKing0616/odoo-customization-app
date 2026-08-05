"""Reuse planner — prefer stock Odoo models over parallel x_* clones.

Two modes:
- **offline** (no connection): CE 19 allowlist — always-safe builtins + intent-matched
  optional apps assumed present for *linking* (not claimed installed).
- **connection-aware**: only optional targets confirmed via live ``ir.model`` catalog
  and/or installed modules.

Never auto-applies to Odoo; only steers ModuleSpec drafts + prompts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal


ReuseSource = Literal[
    "offline_ce19",
    "connection",
    "operator",
    "inferred",
    "pack_reuse_stock",
    "installable",
    "catalog",
]


@dataclass(frozen=True)
class ReuseCandidate:
    model: str
    modules: tuple[str, ...]
    intent: re.Pattern[str]
    reason: str
    offline_assume: bool = True
    forbid_parallel: tuple[str, ...] = ()
    always: bool = False


_ALWAYS: tuple[ReuseCandidate, ...] = (
    ReuseCandidate(
        model="res.partner",
        modules=("base", "contacts"),
        intent=re.compile(r".*", re.I),
        reason="People and organizations (Contacts)",
        forbid_parallel=("x_client", "x_customer", "x_contact", "x_client_contact"),
        always=True,
    ),
    ReuseCandidate(
        model="res.users",
        modules=("base",),
        intent=re.compile(r".*", re.I),
        reason="Assignees / internal users",
        always=True,
    ),
    ReuseCandidate(
        model="res.company",
        modules=("base",),
        intent=re.compile(r".*", re.I),
        reason="Multi-company",
        always=True,
    ),
    ReuseCandidate(
        model="res.currency",
        modules=("base",),
        intent=re.compile(r".*", re.I),
        reason="Monetary amounts",
        always=True,
    ),
    ReuseCandidate(
        model="ir.attachment",
        modules=("base",),
        intent=re.compile(
            r"\b(document|attachment|file|upload|evidence|record)\b", re.I
        ),
        reason="Binary files / attachments",
        always=False,
    ),
)

_OPTIONAL: tuple[ReuseCandidate, ...] = (
    ReuseCandidate(
        model="account.move",
        modules=("account",),
        intent=re.compile(
            r"\b(invoice|invoicing|billing|accounting|accounts?\s*receivable|"
            r"accounts?\s*payable)\b",
            re.I,
        ),
        reason="Customer/vendor invoices (Accounting)",
        forbid_parallel=("x_invoice",),
        offline_assume=True,
    ),
    ReuseCandidate(
        model="product.product",
        modules=("product",),
        intent=re.compile(
            r"\b(product|sku|inventory|catalog|sellable|billable\s+item)\b", re.I
        ),
        reason="Products / variants",
        forbid_parallel=("x_product",),
        offline_assume=True,
    ),
    ReuseCandidate(
        model="product.template",
        modules=("product",),
        intent=re.compile(r"\b(product\s+template|product\s+catalog)\b", re.I),
        reason="Product templates",
        offline_assume=True,
    ),
    ReuseCandidate(
        model="calendar.event",
        modules=("calendar",),
        intent=re.compile(
            r"\b(calendar|appointment|hearing|schedule|meeting|event|"
            r"booking|reservation)\b",
            re.I,
        ),
        reason="Calendar events / appointments",
        offline_assume=True,
    ),
    ReuseCandidate(
        model="project.project",
        modules=("project",),
        intent=re.compile(r"\b(project\s+management|projects?\b)", re.I),
        reason="Projects (link when user asked for PM; domain entities may still be x_*)",
        offline_assume=True,
    ),
    ReuseCandidate(
        model="project.task",
        modules=("project",),
        intent=re.compile(r"\b(project\s+task|kanban\s+task)\b", re.I),
        reason="Project tasks",
        offline_assume=True,
    ),
    ReuseCandidate(
        model="hr.employee",
        modules=("hr",),
        intent=re.compile(r"\b(employee|human\s*resources|\bhr\b|payroll)\b", re.I),
        reason="Employees (HR)",
        forbid_parallel=("x_employee",),
        offline_assume=True,
    ),
    ReuseCandidate(
        model="uom.uom",
        modules=("uom",),
        intent=re.compile(r"\b(uom|unit\s+of\s+measure)\b", re.I),
        reason="Units of measure",
        offline_assume=True,
    ),
)

_DEPENDS_FOR_MODEL: dict[str, tuple[str, ...]] = {
    "res.partner": ("base", "contacts"),
    "account.move": ("account",),
    "product.product": ("product",),
    "product.template": ("product",),
    "calendar.event": ("calendar",),
    "project.project": ("project",),
    "project.task": ("project",),
    "hr.employee": ("hr",),
    "uom.uom": ("uom",),
    "ir.attachment": ("base",),
    "purchase.order": ("purchase",),
    "sale.order": ("sale",),
    "stock.warehouse": ("stock",),
    "stock.quant": ("stock",),
    "hr.expense": ("hr_expense",),
}

REUSE_BUILTIN_MODELS: frozenset[str] = frozenset(
    {c.model for c in (*_ALWAYS, *_OPTIONAL)}
    | {"mail.thread", "mail.activity.mixin"}
)

_PARALLEL_REMAP = {
    "x_client": "res.partner",
    "x_customer": "res.partner",
    "x_contact": "res.partner",
    "x_invoice": "account.move",
    "x_product": "product.product",
    "x_employee": "hr.employee",
}


@dataclass
class ReuseDecision:
    model: str
    reason: str
    source: ReuseSource
    confirmed: bool
    forbid_parallel: tuple[str, ...] = ()
    link_only: bool = False
    required_module: str | None = None


@dataclass
class ReusePlan:
    source: ReuseSource
    decisions: list[ReuseDecision] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)
    forbid_new_models: list[str] = field(default_factory=list)
    catalog_suggestions: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def prompt_block(self) -> str:
        lines = [
            f"REUSE PLAN (source={self.source}):",
            "Link these existing Odoo models — do NOT recreate them as x_*:",
        ]
        for d in self.decisions:
            flag = "confirmed" if d.confirmed else "suggested"
            suffix = " (link-only)" if d.link_only else ""
            lines.append(f"- {d.model} ({flag}{suffix}): {d.reason}")
        if self.forbid_new_models:
            lines.append(
                "FORBIDDEN new models (use stock instead): "
                + ", ".join(self.forbid_new_models)
            )
        lines.append(
            "Domain entities with unique workflows/fields still become x_* "
            "(e.g. matter, attorney) and many2one to the reused stock models."
        )
        if self.source == "offline_ce19":
            lines.append(
                "Offline CE-19 allowlist: optional apps are assumed for linking only; "
                "confirm on a live connection before apply."
            )
        return "\n".join(lines)

    def to_draft_meta(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "models": list(self.models),
            "depends": list(self.depends),
            "forbid_new_models": list(self.forbid_new_models),
            "decisions": [
                {
                    "model": d.model,
                    "reason": d.reason,
                    "source": d.source,
                    "confirmed": d.confirmed,
                    "forbid_parallel": list(d.forbid_parallel),
                    "link_only": d.link_only,
                    **({"module": d.required_module} if d.required_module else {}),
                }
                for d in self.decisions
            ],
        }


def _module_installed(modules: set[str] | None, needed: tuple[str, ...]) -> bool:
    if not modules or not needed:
        return False
    return any(m in modules for m in needed)


def _model_available(
    model: str,
    *,
    available: set[str] | None,
    modules: set[str] | None,
    cand_modules: tuple[str, ...],
) -> bool:
    if available is not None and model in available:
        return True
    if _module_installed(modules, cand_modules):
        return True
    return False


def plan_reuse(
    user_prompt: str,
    *,
    available_models: list[str] | None = None,
    installed_modules: list[str] | None = None,
    operator_reuse: list[str] | None = None,
    pack_reuse_stock: list[dict[str, Any]] | None = None,
    rejected_reuse_models: list[str] | None = None,
    stock_catalog: list[dict[str, Any]] | None = None,
) -> ReusePlan:
    """Build a reuse plan from prompt intent + offline allowlist or live catalog."""
    from app.ai_stock_reuse import infer_stock_reuse

    text = (user_prompt or "").strip()
    available = set(available_models) if available_models is not None else None
    modules = set(installed_modules) if installed_modules else None
    # Connection mode only when we actually queried an instance
    connection = available is not None or modules is not None
    source: ReuseSource = "connection" if connection else "offline_ce19"

    decisions: list[ReuseDecision] = []
    seen: set[str] = set()
    notes: list[str] = []

    def add(cand: ReuseCandidate, *, confirmed: bool, src: ReuseSource) -> None:
        if cand.model in seen:
            return
        seen.add(cand.model)
        decisions.append(
            ReuseDecision(
                model=cand.model,
                reason=cand.reason,
                source=src,
                confirmed=confirmed,
                forbid_parallel=cand.forbid_parallel,
            )
        )

    for mid in operator_reuse or []:
        if not isinstance(mid, str) or not mid.strip() or mid in seen:
            continue
        confirmed = True
        if connection and available is not None:
            confirmed = mid in available or _module_installed(
                modules, _DEPENDS_FOR_MODEL.get(mid, ())
            )
        forbid = next(
            (c.forbid_parallel for c in (*_ALWAYS, *_OPTIONAL) if c.model == mid),
            (),
        )
        seen.add(mid)
        decisions.append(
            ReuseDecision(
                model=mid,
                reason="Operator selected",
                source="operator",
                confirmed=confirmed,
                forbid_parallel=forbid,
            )
        )

    if source == "offline_ce19":
        notes.append("reuse: offline CE-19 allowlist (no connection)")
    else:
        notes.append("reuse: connection-aware plan")

    for cand in _ALWAYS:
        if not (cand.always or cand.intent.search(text)):
            continue
        if connection:
            ok = _model_available(
                cand.model,
                available=available,
                modules=modules,
                cand_modules=cand.modules,
            )
            if not ok and cand.model.startswith("res."):
                ok = True  # base models always present
            if ok:
                add(cand, confirmed=True, src="connection")
        else:
            add(cand, confirmed=False, src="offline_ce19")

    for cand in _OPTIONAL:
        if not cand.intent.search(text):
            continue
        if connection:
            ok = _model_available(
                cand.model,
                available=available,
                modules=modules,
                cand_modules=cand.modules,
            )
            if ok:
                add(cand, confirmed=True, src="connection")
            else:
                notes.append(
                    f"reuse: skipped {cand.model} "
                    "(not on instance / module not installed)"
                )
        elif cand.offline_assume:
            add(cand, confirmed=False, src="offline_ce19")

    inferred_rows, infer_notes, catalog_suggestions = infer_stock_reuse(
        text,
        available_models=available_models,
        installed_modules=installed_modules,
        pack_reuse_stock=pack_reuse_stock,
        rejected_models=rejected_reuse_models,
        stock_catalog=stock_catalog,
    )
    notes.extend(infer_notes)
    operator_set = set(operator_reuse or [])
    for row in inferred_rows:
        mid = str(row.get("model") or "")
        if not mid or mid in seen:
            continue
        src: ReuseSource = (
            "pack_reuse_stock"
            if row.get("source") == "pack_reuse_stock"
            else "installable"
            if row.get("source") == "installable"
            else "inferred"
        )
        confirmed = mid in operator_set
        seen.add(mid)
        link_only = bool(row.get("link_only"))
        if src == "pack_reuse_stock" and pack_reuse_stock:
            for ps in pack_reuse_stock:
                if isinstance(ps, dict) and ps.get("model") == mid:
                    link_only = bool(ps.get("link_only")) or link_only
                    break
        decisions.append(
            ReuseDecision(
                model=mid,
                reason=str(row.get("reason") or "Inferred stock model"),
                source=src,
                confirmed=confirmed,
                forbid_parallel=tuple(str(x) for x in (row.get("forbid_parallel") or [])),
                link_only=link_only,
                required_module=str(row["module"]) if row.get("module") else None,
            )
        )

    models = [
        d.model
        for d in decisions
        if d.confirmed or d.source != "installable"
    ]
    forbid: list[str] = []
    for d in decisions:
        if d.source in {"inferred", "pack_reuse_stock", "installable"} and not d.confirmed:
            continue
        for f in d.forbid_parallel:
            if f not in forbid:
                forbid.append(f)

    depends: list[str] = ["base"]
    for mid in models:
        for dep in _DEPENDS_FOR_MODEL.get(mid, ()):
            if dep not in depends:
                depends.append(dep)
    if "mail" not in depends:
        depends.append("mail")

    return ReusePlan(
        source=source,
        decisions=decisions,
        models=models,
        depends=depends,
        forbid_new_models=forbid,
        catalog_suggestions=catalog_suggestions,
        notes=notes,
    )


def collapse_forbidden_parallel_models(
    draft: dict[str, Any], forbid: list[str]
) -> list[str]:
    """Remove mini-CRM / duplicate invoice models banned by the reuse plan."""
    notes: list[str] = []
    if not forbid:
        return notes
    forbid_set = set(forbid)
    models = [m for m in (draft.get("models") or []) if isinstance(m, dict)]
    removed = [str(m.get("model")) for m in models if str(m.get("model")) in forbid_set]
    if not removed:
        return notes
    draft["models"] = [m for m in models if str(m.get("model")) not in forbid_set]
    notes.append(f"reuse: collapsed parallel models {', '.join(removed)}")

    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        fields: list[Any] = []
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                fields.append(f)
                continue
            rel = str(f.get("relation") or "")
            if rel in removed and rel in _PARALLEL_REMAP:
                fields.append({**f, "relation": _PARALLEL_REMAP[rel]})
                notes.append(
                    f"reuse: remapped {m.get('model')}.{f.get('name')} "
                    f"{rel}→{_PARALLEL_REMAP[rel]}"
                )
            elif rel in removed:
                notes.append(
                    f"reuse: dropped field {m.get('model')}.{f.get('name')} → {rel}"
                )
            else:
                fields.append(f)
        m["fields"] = fields

    for key in ("actions", "views", "access_rules"):
        rows = draft.get(key)
        if not isinstance(rows, list):
            continue
        kept = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            mid = row.get("model")
            if key == "access_rules" and isinstance(mid, str) and mid.startswith("model_"):
                leaf = mid[len("model_") :]
                if leaf in removed:
                    continue
            if mid in removed:
                continue
            kept.append(row)
        draft[key] = kept

    buttons = draft.get("smart_buttons")
    if isinstance(buttons, list):
        draft["smart_buttons"] = [
            b
            for b in buttons
            if isinstance(b, dict)
            and b.get("related_model") not in removed
            and b.get("on_model") not in removed
        ]
    return notes


def ensure_partner_links_on_transactional(draft: dict[str, Any]) -> list[str]:
    """If res.partner is reused, ensure header/workflow models have a partner M2O."""
    notes: list[str] = []
    reuse = draft.get("reuse") or {}
    models_reuse = set(reuse.get("models") or []) if isinstance(reuse, dict) else set()
    if "res.partner" not in models_reuse:
        return notes
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        if not mid.startswith("x_"):
            continue
        leaf = mid.replace("x_", "")
        # Never force partner onto line/child rows (time entries, bill lines, …)
        if leaf.endswith("_line") or leaf.endswith("_lines") or leaf.endswith("line"):
            continue
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        if any(f.get("relation") == "res.partner" for f in fields):
            continue
        if not (
            m.get("is_workflow")
            or any(
                k in mid
                for k in (
                    "matter",
                    "order",
                    "job",
                    "case",
                    "bill",
                    "invoice",
                    "patient",
                    "appointment",
                    "enrollment",
                )
            )
        ):
            continue
        fields.append(
            {
                "name": "x_partner_id",
                "ttype": "many2one",
                "relation": "res.partner",
                "string": "Contact",
            }
        )
        m["fields"] = fields
        notes.append(f"reuse: added x_partner_id on {mid}")
    return notes


def apply_reuse_plan(draft: dict[str, Any], plan: ReusePlan) -> list[str]:
    """Attach plan metadata, merge depends, collapse forbidden parallels.

    Idempotent: repeated calls do not re-emit the same plan banner notes.
    """
    notes: list[str] = []
    reuse_prev = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
    first_apply = not (isinstance(reuse_prev, dict) and reuse_prev.get("plan"))
    if first_apply:
        notes.extend(plan.notes)

    reuse = dict(reuse_prev or {})
    confirmed_models = [d.model for d in plan.decisions if d.confirmed]
    reuse["models"] = list(
        dict.fromkeys([*(reuse.get("models") or []), *confirmed_models])
    )
    reuse["plan"] = plan.to_draft_meta()
    if plan.catalog_suggestions:
        reuse["catalog_suggestions"] = list(plan.catalog_suggestions)
    draft["reuse"] = reuse

    depends = list(draft.get("depends") or [])
    for dep in plan.depends:
        if dep not in depends:
            depends.append(dep)
    draft["depends"] = depends

    hints = list(draft.get("reuse_hints") or [])
    existing = {str(h.get("model")) for h in hints if isinstance(h, dict)}
    for d in plan.decisions:
        if d.model not in existing:
            hints.append({"model": d.model, "reason": d.reason})
    draft["reuse_hints"] = hints

    # Also collapse x_invoice when a domain bill header already exists (even without Accounting)
    forbid = list(plan.forbid_new_models)
    model_ids = {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    if "x_bill" in model_ids and "x_invoice" in model_ids and "x_invoice" not in forbid:
        forbid.append("x_invoice")

    notes.extend(collapse_forbidden_parallel_models(draft, forbid))
    notes.extend(ensure_partner_links_on_transactional(draft))
    if first_apply:
        notes.append(
            f"reuse: plan applied ({plan.source}) → {', '.join(plan.models) or '(none)'}"
        )
    elif notes:
        notes.append(f"reuse: re-applied collapses ({plan.source})")
    return notes


__all__ = [
    "REUSE_BUILTIN_MODELS",
    "ReusePlan",
    "ReuseDecision",
    "plan_reuse",
    "apply_reuse_plan",
    "collapse_forbidden_parallel_models",
]
