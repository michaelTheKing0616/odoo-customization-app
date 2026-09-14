"""Generation Engine — classify any prompt, stamp IR, map operator progress.

Odoo-quality = Community shape + stock reuse + residual completeness + gates
that can fail. Not Apps Store specialist OWL (GM / Receipt Studio).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.ai_capability_gaps import assess_capability_gaps
from app.ai_grain import classify_grain
from app.ai_operator_brief import (
    build_operator_brief,
    is_cbn_currency_rates_prompt,
    is_pos_receipt_prompt,
    stated_residual_kind,
    wants_stock_reuse,
)

Capability = Literal[
    "residual_app",
    "option_a_standalone",
    "option_a_authored",
    "mixed",
    "stock_reuse",
    "refuse_clone",
]

UserPhase = Literal["building", "codegen", "checking", "review", "failed"]

USER_PHASE_LABELS: dict[UserPhase, str] = {
    "building": "Building your app…",
    "codegen": "Generating the code, tests, and documentation…",
    "checking": "Checking everything works…",
    "review": "Review your app",
    "failed": "Generation did not pass quality checks",
}

_CLONE_RE = re.compile(
    r"(?i)\b("
    r"clone\s+(?:the\s+)?(?:gm|apps?\s+store)|"
    r"clone\s+(?:this|that|the)\s+module|"
    r"same\s+as\s+(?:the\s+)?(?:odoo\s+)?apps?\s+store|"
    r"copy\s+(?:this|that)\s+module|"
    r"reverse[\s-]?engineer"
    r")\b"
)

_STANDALONE_RE = re.compile(
    r"(?i)\b("
    r"standalone\s+app|\[custom\]\s*app|custom\s+app|"
    r"installable\s+module|apps?\s+store[\s-]?ready"
    r")\b"
)

_BARE_RENTAL_RE = re.compile(
    r"(?i)^\s*rental\s*(?:app|management|system)?\s*$"
)

_STOCK_APP_LABELS = {
    "point_of_sale": "Point of Sale",
    "sale": "Sales",
    "account": "Invoicing",
    "contacts": "Contacts",
    "mail": "Discuss",
    "hr": "Employees",
    "stock": "Inventory",
    "purchase": "Purchase",
    "crm": "CRM",
    "project": "Project",
    "calendar": "Calendar",
    "mrp": "Manufacturing",
    "website": "Website",
    "product": "Products",
}


def labeled_stock_apps(module_ids: list[str]) -> list[dict[str, str]]:
    return [
        {"id": mid, "label": _STOCK_APP_LABELS.get(mid, mid.replace("_", " "))}
        for mid in module_ids
        if mid
    ]


_CLARIFY_RENTAL = {
    "question": "What are you renting?",
    "options": [
        {"id": "cars", "label": "Vehicles / car hire"},
        {"id": "equipment", "label": "Equipment"},
        {"id": "property", "label": "Real estate / event space"},
    ],
    "default_id": "cars",
}


@dataclass
class GenerationPlan:
    capability: Capability
    grain: str
    gold_artifact_id: str | None = None
    module_delivery: bool = False
    needs_clarification: dict[str, Any] | None = None
    honesty: str = ""
    refuse_reason: str = ""
    user_phase: UserPhase = "building"
    notes: list[str] = field(default_factory=list)


def is_clone_request(prompt: str) -> bool:
    return bool(_CLONE_RE.search(prompt or ""))


def wants_module_delivery(prompt: str) -> bool:
    return bool(_STANDALONE_RE.search(prompt or ""))


_AUTHORED_GAP_IDS = frozenset(
    {
        "python_logic",
        "webhook_inbound",
        "owl_widget",
        "website_controller",
        "http_integration",
        "qweb_inherit",
    }
)


def _invoice_qweb_gold(prompt: str, gap_ids: set[str]) -> bool:
    if gap_ids & {"qr_on_document", "click_to_pay"}:
        return True
    if "pdf_report" in gap_ids and re.search(r"(?i)\binvoices?\b", prompt or ""):
        if gap_ids & _AUTHORED_GAP_IDS:
            return False
        return True
    return False


def _needs_authored_module(gap_ids: set[str], *, primary: bool) -> bool:
    layout = gap_ids & {
        "qweb_inherit",
        "webhook_inbound",
        "owl_widget",
        "website_controller",
        "http_integration",
    }
    if layout:
        return True
    if primary and "python_logic" in gap_ids:
        return True
    return False


def classify_generation(prompt: str) -> GenerationPlan:
    """Map any operator prompt onto the capability table."""
    text = (prompt or "").strip()
    from app.ai_operator_brief import intent_corpus

    grain = classify_grain(intent_corpus(text) or text)
    if is_clone_request(text):
        return GenerationPlan(
            capability="refuse_clone",
            grain=grain,
            honesty=(
                "This platform does not clone Apps Store / GM modules. "
                "Describe the residual process, or ask for the honest POS receipt "
                "options template (toggles on pos.config — not a live thermal studio)."
            ),
            refuse_reason="clone_apps_store",
            notes=["refuse: apps-store clone"],
        )

    clarify: dict[str, Any] | None = None
    if _BARE_RENTAL_RE.match(text):
        clarify = dict(_CLARIFY_RENTAL)

    gaps = assess_capability_gaps(text)
    pos = is_pos_receipt_prompt(text) or any(
        g.id == "pos_receipt_designer" for g in gaps.gaps
    )
    module = wants_module_delivery(text)
    cbn = is_cbn_currency_rates_prompt(text)

    if cbn:
        return GenerationPlan(
            capability="option_a_standalone",
            grain="full_app",
            gold_artifact_id="currency_rate_cbn",
            module_delivery=True,
            needs_clarification=clarify,
            honesty=(
                "Community Accounting does not ship a live-rate Service dropdown "
                "(Automatic Currency Rates is an Enterprise upgrade tease — no ECB). "
                "This selects the gold CBN module: inherit Settings, Service = "
                "Central Bank of Nigeria, write stock res.currency.rate for "
                "USD/GBP/EUR. Set company currency to NGN (Autopilot can). "
                "No x_* FX app. Module → sandbox → Promote."
            ),
            notes=["gold: currency_rate_cbn"],
        )

    if wants_stock_reuse(text):
        brief = build_operator_brief(text)
        apps = ", ".join(brief.stock_reuse) or "the named Community apps"
        return GenerationPlan(
            capability="stock_reuse",
            grain="full_app",
            module_delivery=False,
            needs_clarification=clarify,
            honesty=(
                f"This brief is stock-first with no custom residual. "
                f"Community {apps} already cover cashiers, quotations, and invoices. "
                "Draft Studio will not invent x_receipt, invoice Pay/QR, or a POS print "
                "module until you explicitly ask. Use Job Autopilot for sandbox install "
                "and quote→invoice RPC smoke. Completeness ≠ Cert. Promote stays human."
            ),
            notes=["stock_reuse: residual none"],
        )

    if pos:
        return GenerationPlan(
            capability="option_a_standalone",
            grain="full_app",
            gold_artifact_id="pos_receipt_options",
            module_delivery=True,
            needs_clarification=clarify,
            honesty=(
                "Community POS print is OWL/QWeb on point_of_sale. "
                "This selects the gold POS receipt *options* template "
                "(header/footer, paper width, logo toggle) — not a drag-drop "
                "thermal studio and not an x_receipt app."
            ),
            notes=["gold: pos_receipt_options"],
        )

    gap_ids = {g.id for g in gaps.gaps}
    invoice_gold = _invoice_qweb_gold(text, gap_ids)
    if _needs_authored_module(gap_ids, primary=gaps.primary_option_a) and not invoice_gold:
        return GenerationPlan(
            capability="option_a_authored",
            grain="full_app",
            module_delivery=True,
            needs_clarification=clarify,
            honesty=(
                "This ask needs an installable module (Python / QWeb / HTTP / OWL). "
                "The LLM authors the module; zip and sandbox stay locked until the "
                "authoring gate passes. Completeness ≠ Cert. Promote stays human."
            ),
            notes=["option_a_authored"],
        )

    if gaps.primary_option_a:
        gold = "invoice_qweb" if invoice_gold else None
        if gold:
            return GenerationPlan(
                capability="option_a_standalone",
                grain=grain,
                gold_artifact_id=gold,
                module_delivery=True,
                needs_clarification=clarify,
                honesty=(
                    "This ask is Option A gold invoice extras (Pay now + QR). "
                    "Module → sandbox prove → human Promote."
                ),
                notes=["gold: invoice_qweb"],
            )
        return GenerationPlan(
            capability="option_a_authored",
            grain="full_app",
            module_delivery=True,
            needs_clarification=clarify,
            honesty=(
                "This ask is Option A (module → sandbox prove → human Promote). "
                "Live Apply will not finish OWL/QWeb/Python by itself. "
                "Zip stays locked until the authoring gate passes."
            ),
            notes=["option_a_authored"],
        )

    if gaps.gaps:
        if _needs_authored_module(gap_ids, primary=gaps.primary_option_a) and not invoice_gold:
            return GenerationPlan(
                capability="option_a_authored",
                grain="full_app",
                module_delivery=True,
                needs_clarification=clarify,
                honesty=(
                    "This ask needs an installable module. The LLM authors Python/QWeb; "
                    "zip and sandbox stay locked until the authoring gate passes."
                ),
                notes=["option_a_authored: mixed signals"],
            )
        return GenerationPlan(
            capability="mixed",
            grain=grain,
            gold_artifact_id="invoice_qweb" if invoice_gold else None,
            module_delivery=module or invoice_gold,
            needs_clarification=clarify,
            honesty="Custom residual plus Option A surfaces. Completeness can be 10.0; Cert stays Reject until sandbox prove.",
            notes=["mixed live+option_a"],
        )

    residual_kind, residual_text = stated_residual_kind(text)
    honesty = ""
    notes = ["residual_app"]
    if residual_kind == "named":
        honesty = (
            f"Stock Community apps first; custom residual is {residual_text}. "
            "Inherit stock hosts when a field/process fits; new x_* only when stock "
            "cannot carry the document. No parallel invoice/partner/employee. "
            "Completeness ≠ Cert. Promote stays human."
        )
        notes = ["residual_app: named residual"]
    elif grain in {"field_pack", "feature_slice"}:
        honesty = (
            "This is an inherit-and-wire ask on a stock host (not a new app). "
            "Live Apply lands metadata; Option A stays module → sandbox → promote."
        )
        notes = [f"residual_app: {grain}"]
    return GenerationPlan(
        capability="residual_app",
        grain=grain,
        module_delivery=module,
        needs_clarification=clarify,
        honesty=honesty,
        notes=notes,
    )


def plan_to_ir(plan: GenerationPlan, *, user_phase: UserPhase = "building") -> dict[str, Any]:
    return {
        "capability": plan.capability,
        "grain": plan.grain,
        "gold_artifact_id": plan.gold_artifact_id,
        "module_delivery": plan.module_delivery,
        "needs_clarification": plan.needs_clarification,
        "honesty": plan.honesty,
        "refuse_reason": plan.refuse_reason,
        "user_phase": user_phase,
        "user_phase_label": USER_PHASE_LABELS[user_phase],
        "notes": list(plan.notes),
        "promote_human": True,
        "scorecard_is_not_cert": True,
        "studio_parity_deferred": plan.gold_artifact_id == "pos_receipt_options",
    }


def attach_generation_engine(
    draft: dict[str, Any],
    prompt: str,
    *,
    user_phase: UserPhase = "building",
) -> dict[str, Any]:
    plan = classify_generation(prompt)
    ir = plan_to_ir(plan, user_phase=user_phase)
    prior = draft.get("_generation_engine")
    if (
        isinstance(prior, dict)
        and prior.get("gold_artifact_id")
        and plan.capability != "stock_reuse"
        and prior.get("capability") != "stock_reuse"
    ):
        ir["gold_artifact_id"] = prior.get("gold_artifact_id")
        ir["capability"] = prior.get("capability") or ir["capability"]
        ir["honesty"] = prior.get("honesty") or ir["honesty"]
    if isinstance(prior, dict) and prior.get("capability") == "stock_reuse":
        ir["capability"] = "stock_reuse"
        ir["gold_artifact_id"] = None
        ir["honesty"] = prior.get("honesty") or ir["honesty"]
        ir["module_delivery"] = False
        ir["notes"] = list(prior.get("notes") or ir.get("notes") or [])
        if prior.get("stock_apps"):
            ir["stock_apps"] = prior.get("stock_apps")
    if ir.get("capability") == "stock_reuse" and not ir.get("stock_apps"):
        from app.ai_operator_brief import build_operator_brief as _brief

        depends = draft.get("depends") or []
        if not depends:
            depends = ["mail", "contacts", *_brief(prompt).stock_reuse]
        ir["stock_apps"] = labeled_stock_apps([str(x) for x in depends if x])
    draft["_generation_engine"] = ir
    from app.preview_views import build_preview_views

    previews = build_preview_views(draft)
    if previews.get("form"):
        ir["form_preview"] = previews["form"]
    elif isinstance(prior, dict) and prior.get("form_preview"):
        ir["form_preview"] = prior["form_preview"]
    if previews.get("list"):
        ir["list_preview"] = previews["list"]
    elif isinstance(prior, dict) and prior.get("list_preview"):
        ir["list_preview"] = prior["list_preview"]
    if previews.get("kanban"):
        ir["kanban_preview"] = previews["kanban"]
    elif isinstance(prior, dict) and prior.get("kanban_preview"):
        ir["kanban_preview"] = prior["kanban_preview"]
    settings = option_a_settings_from_draft(draft)
    if settings:
        ir["option_a_settings"] = settings
    if plan.module_delivery or ir.get("module_delivery"):
        draft["_delivery_preference"] = "module_zip"
    return ir


def user_phase_for_step(step: int, *, total: int = 7) -> UserPhase:
    if step <= 2:
        return "building"
    if step < total - 1:
        return "codegen"
    return "checking"


def is_gold_option_a_draft(draft: dict[str, Any]) -> bool:
    ir = draft.get("_generation_engine")
    if not isinstance(ir, dict):
        return False
    return ir.get("capability") == "option_a_standalone" and bool(ir.get("gold_artifact_id"))


def is_option_a_authored_draft(draft: dict[str, Any]) -> bool:
    ir = draft.get("_generation_engine")
    return isinstance(ir, dict) and ir.get("capability") == "option_a_authored"


def is_refuse_draft(draft: dict[str, Any]) -> bool:
    ir = draft.get("_generation_engine")
    return isinstance(ir, dict) and ir.get("capability") == "refuse_clone"


def is_stock_reuse_draft(draft: dict[str, Any]) -> bool:
    ir = draft.get("_generation_engine")
    return isinstance(ir, dict) and ir.get("capability") == "stock_reuse"


def is_component_grain_draft(draft: dict[str, Any]) -> bool:
    """Inherit-and-wire seeds (field_pack / feature_slice) — not a vertical pack."""
    grain = str(draft.get("grain") or "")
    if grain in {"field_pack", "feature_slice"}:
        return True
    ir = draft.get("_generation_engine")
    return isinstance(ir, dict) and ir.get("grain") in {"field_pack", "feature_slice"}


def maybe_seed_from_capability(prompt: str) -> dict[str, Any] | None:
    """Short-circuit pack/LLM when the capability map already knows the artifact."""
    plan = classify_generation(prompt)
    if plan.capability == "refuse_clone":
        from app.ai_llm_status import attach_llm_status
        from app.ai_operator_brief import attach_operator_brief

        draft: dict[str, Any] = {
            "technical_name": "refused_clone",
            "display_name": "Request not generated",
            "depends": ["base"],
            "models": [],
            "grain": plan.grain,
            "_user_prompt": prompt,
            "_pipeline": "generation_engine_refuse",
        }
        attach_operator_brief(draft, user_prompt=prompt)
        attach_llm_status(draft, mode="seed_fallback", reason="refuse_clone")
        attach_generation_engine(draft, prompt, user_phase="review")
        draft["_generation_engine"]["honesty"] = plan.honesty
        return draft

    if plan.gold_artifact_id in {"pos_receipt_options", "currency_rate_cbn"}:
        from app.option_a_templates import apply_gold_template

        return apply_gold_template(prompt, plan.gold_artifact_id, plan=plan)

    if plan.capability == "option_a_authored":
        from app.ai_option_a_author import seed_option_a_authored

        return seed_option_a_authored(prompt, plan)

    if plan.capability == "stock_reuse":
        return _seed_stock_reuse(prompt, plan)
    return None


def _seed_stock_reuse(prompt: str, plan: GenerationPlan) -> dict[str, Any]:
    from app.ai_llm_status import attach_llm_status
    from app.ai_operator_brief import attach_operator_brief, build_operator_brief

    brief = build_operator_brief(prompt)
    depends = list(dict.fromkeys(["mail", "contacts", *brief.stock_reuse]))
    draft: dict[str, Any] = {
        "technical_name": "stock_reuse",
        "display_name": "Community stock apps",
        "depends": depends,
        "models": [],
        "views": [],
        "menus": [],
        "actions": [],
        "automations": [],
        "smart_buttons": [],
        "grain": "full_app",
        "grain_label": "Stock-first — no custom residual",
        "_component": False,
        "_ambition": "thin",
        "_user_prompt": prompt,
        "_pipeline": "generation_engine_stock_reuse",
        "_capability_primary_option_a": False,
        "_architecture_plan": {
            "strategy": "stock_reuse",
            "stock_hosts": depends,
            "new_x_models": [],
            "forbidden_clones": [
                "x_receipt",
                "x_pos_config",
                "x_invoice",
                "x_client",
            ],
            "customization_needed": False,
            "reason": "Named Community apps cover the brief; no x_* residual",
            "surface_budget": {"new_models": 0, "new_js": 0, "new_controllers": 0},
            "ambiguities": [],
            "grain": "full_app",
        },
        "_architecture_drift": [],
    }
    attach_operator_brief(draft, user_prompt=prompt)
    attach_llm_status(draft, mode="seed_fallback", reason="stock_reuse")
    attach_generation_engine(draft, prompt, user_phase="review")
    ir = draft["_generation_engine"]
    ir["honesty"] = plan.honesty
    ir["capability"] = "stock_reuse"
    ir["gold_artifact_id"] = None
    ir["module_delivery"] = False
    ir["notes"] = list(plan.notes)
    ir["stock_apps"] = labeled_stock_apps(depends)
    draft.pop("_delivery_preference", None)
    return draft


def option_a_settings_from_draft(draft: dict[str, Any]) -> dict[str, Any] | None:
    """Inherit-host fields for the Option A honesty pane (not an x_receipt form)."""
    ir = draft.get("_generation_engine")
    if not isinstance(ir, dict):
        return None
    if ir.get("capability") not in {"option_a_standalone", "option_a_authored"}:
        return None
    for row in draft.get("models") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("mode") or "") != "inherit":
            continue
        fields = [
            {
                "name": str(f.get("name") or ""),
                "string": str(f.get("string") or f.get("name") or ""),
                "help": str(f.get("help") or ""),
            }
            for f in (row.get("fields") or [])
            if isinstance(f, dict) and f.get("name")
        ]
        if fields:
            return {
                "model": str(row.get("model") or ""),
                "fields": fields,
            }
    return None


def residual_form_preview(draft: dict[str, Any]) -> dict[str, Any] | None:
    """First custom header form for Stage H — delegates to preview_views."""
    from app.preview_views import residual_form_preview as _build

    return _build(draft)
