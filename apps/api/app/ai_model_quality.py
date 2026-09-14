"""Generation-time model quality — prompts, exemplars, hollow collapse, field deepen.

Post-hoc depth floors are not enough: the LLM must be steered to create substantive
models on the first pass, and expand must deepen fields — not invent catalog stubs.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

# Shared with system / staged / expand prompts so every path says the same thing.
MODEL_CREATION_RULES = """
MODEL CREATION QUALITY (mandatory — every domain):
0) OPERATOR BRIEF IS LAW. Unknowns listed in the brief are omitted — never filled with
   CE-19 defaults (currency, company name, industry, multi-company). Out of scope and
   forbidden bridges are never inherited. Field labels copy the brief's words
   (time in ≠ check-in unless the brief said check-in). Do not add models, fields, or
   automations the brief did not ask for. Document shape overrides ambition floors:
   - register: exactly one x_* header; list+form; no workflow/kanban/x_status/x_code
     unless named; no x_company_id / x_currency_id unless the brief named a legal-entity
     split or a currency; at most one on_time duration alert, clocked on the header
     datetime (not create_date).
   - field_pack: inherit the named stock model only; no new app menu.
   - stock_reuse: models: [] — Job Autopilot is the done-bar.
   Ambition floors (thin ≥2 models, etc.) apply only to workspace / transactional_header.
1) Every custom model must be SUBSTANTIVE — typically ≥6 fields (≥8 if is_workflow).
   Required pattern: x_name + domain attributes + ≥1 many2one (peer or res.partner)
   + dates/status when lifecycle exists. Never ship x_name+x_code only.
   Register exception: the stated columns only — do not pad to 6 with company/notes/status.
2) Taxonomy (type / category / tag / stage / priority / status / specialty) = selection
   fields on the parent. NEVER create separate name+code catalog models for those.
3) Name models for THIS domain (e.g. x_order, x_vehicle, x_patient, x_student). NEVER keep
   exemplar placeholders (x_ex_*, x_resource, x_transaction) in the final draft.
4) Prefer res.partner for people/org contacts — do not invent a parallel x_client / x_customer
   mini-CRM unless the domain needs multi-role parties (then a party-link model, not a duplicate CRM).
5) many2one: name ends with _id; relation MUST exist in the same draft (or stock model).
   Never leave orphan relations. O2M needs relation + relation_field.
6) Workflows: x_status with real stages + x_code help matching THIS domain (never RNT/00001)
   — only when the brief named a lifecycle. Registers are not workflows.
7) Amounts: float + x_currency_id ONLY if the brief named money/currency.
   Multi-company: x_company_id → res.company ONLY if the brief named a legal-entity split.
   Unknown currency / multi-company slots stay empty.
8) smart_buttons shape: {on_model, label, related_model, relation_field} only.
9) Prefer fewer rich models over generic filler (random x_project trees) unless the user
   asked for project management.
10) Obey the REUSE PLAN only for hosts the brief actually uses. Do not add fields just
    because CE-19 listed res.company / res.currency / res.users. Never recreate forbidden
    parallels (x_client, x_invoice when account.move is reused, etc.). Domain residual still becomes x_*.

WORLD-CLASS OPS DEPTH (comprehensive / world-class prompts — meet this bar):
11) Residual custom models cover what stock apps do not. Link CRM/Sale/Account/HR/
    Timesheet/Calendar/Project when the brief uses them — do NOT clone those as
    x_lead / x_bill / x_attorney / x_task / x_event / x_payment.
12) Line/time models link stock account.move (x_invoice_id, PCM link-only) when
    invoicing is in the stack. Invent x_bill only if the brief forbids Accounting.
13) Selection keys must be meaningful domain words (litigation/corporate/advisory or
    intake/open/billed/closed) — NEVER specialty_a, option_a, area_b placeholders.
14) Automations only on models that exist in the draft; safe_actions only
    (object_write / related_write / next_activity). Values must be valid selection keys.
15) When a domain scaffold is provided, match its stock-first residual — do not pad
    model count with a second ERP. Deepen fields and stock links instead.
16) Staff/fee-earner/counsel many2ones relation hr.employee when HR is in depends.
    res.users is only the login (x_user_id). Do not invent x_attorney / x_doctor / x_staff.
17) Party/role-link models are NOT is_workflow. Header workflows include terminal
    statuses (closed/done/cancelled/on_hold).

PROTECTED MODULES (PCM — effect not mechanism):
18) Tier-1 (account, payment, payroll, sign, subscriptions, stock valuation, IAP): never
    generate writes, automations, or field mutations ON those models. Link-only many2one/
    one2many FROM custom x_* models INTO tier-1 is allowed. Chatter/activity on tier-1 OK.
19) Tier-2 (l10n_*, base, web, auth_*, mail): extend via additive x_* fields only — never
    delete/rename stock fields or replace core behaviour.
""".strip()

_FEW_SHOT_EXEMPLAR = {
    "note": (
        "PLACEHOLDER exemplar only — RENAME every x_ex_* model to THIS domain's residual. "
        "Staff/fee-earners are hr.employee links, not x_ex_staff clones. "
        "Invoices are account.move, not x_bill. Residual job/matter/enrollment stays x_*. "
        "Never leave x_ex_* or generic x_resource/x_transaction names in the final draft."
    ),
    "models": [
        {
            "model": "x_ex_staff",
            "description": "Staff / fee-earner / practitioner (RENAME)",
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                {
                    "name": "x_partner_id",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "string": "Contact",
                },
                {
                    "name": "x_user_id",
                    "ttype": "many2one",
                    "relation": "res.users",
                    "string": "User",
                },
                {
                    "name": "x_practice",
                    "ttype": "selection",
                    "string": "Practice / Specialty",
                    "selection": (
                        "[('general','General'),('corporate','Corporate'),"
                        "('litigation','Litigation'),('family','Family'),"
                        "('other','Other')]"
                    ),
                },
                {"name": "x_active", "ttype": "boolean", "string": "Active"},
                {
                    "name": "x_company_id",
                    "ttype": "many2one",
                    "relation": "res.company",
                    "string": "Company",
                },
            ],
        },
        {
            "model": "x_ex_job",
            "description": "Core transactional document (RENAME: matter/order/job)",
            "is_workflow": True,
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Title", "required": True},
                {
                    "name": "x_code",
                    "ttype": "char",
                    "string": "Reference",
                    "help": "Wire ir.sequence (e.g. JOB/00001)",
                },
                {
                    "name": "x_partner_id",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "string": "Customer / Client",
                    "required": True,
                },
                {
                    "name": "x_ex_staff_id",
                    "ttype": "many2one",
                    "relation": "x_ex_staff",
                    "string": "Owner",
                },
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Status",
                    "selection": (
                        "[('intake','Intake'),('open','Open'),('in_progress','In progress'),"
                        "('done','Done'),('on_hold','On hold'),('cancelled','Cancelled')]"
                    ),
                    "required": True,
                },
                {
                    "name": "x_priority",
                    "ttype": "selection",
                    "string": "Priority",
                    "selection": (
                        "[('low','Low'),('normal','Normal'),('high','High'),"
                        "('critical','Critical')]"
                    ),
                },
                {"name": "x_open_date", "ttype": "date", "string": "Opened"},
                {"name": "x_due_date", "ttype": "date", "string": "Due"},
                {"name": "x_notes", "ttype": "text", "string": "Notes"},
                {
                    "name": "x_company_id",
                    "ttype": "many2one",
                    "relation": "res.company",
                    "string": "Company",
                },
                {
                    "name": "x_ex_line_ids",
                    "ttype": "one2many",
                    "relation": "x_ex_job_line",
                    "relation_field": "x_ex_job_id",
                    "string": "Lines",
                },
                {
                    "name": "x_ex_event_ids",
                    "ttype": "one2many",
                    "relation": "x_ex_event",
                    "relation_field": "x_ex_job_id",
                    "string": "Events",
                },
            ],
        },
        {
            "model": "x_ex_job_line",
            "description": "Line / time / detail (RENAME)",
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Description", "required": True},
                {
                    "name": "x_ex_job_id",
                    "ttype": "many2one",
                    "relation": "x_ex_job",
                    "string": "Parent",
                    "required": True,
                },
                {
                    "name": "x_ex_staff_id",
                    "ttype": "many2one",
                    "relation": "x_ex_staff",
                    "string": "Performed by",
                },
                {"name": "x_date", "ttype": "date", "string": "Date"},
                {"name": "x_qty", "ttype": "float", "string": "Quantity / Hours"},
                {"name": "x_amount", "ttype": "float", "string": "Amount"},
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "relation": "res.currency",
                    "string": "Currency",
                },
                {
                    "name": "x_ex_bill_id",
                    "ttype": "many2one",
                    "relation": "x_ex_bill",
                    "string": "Bill",
                },
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Status",
                    "selection": (
                        "[('draft','Draft'),('submitted','Submitted'),"
                        "('approved','Approved'),('billed','Billed')]"
                    ),
                },
            ],
        },
        {
            "model": "x_ex_bill",
            "description": "Billing stub (RENAME: charge/invoice)",
            "is_workflow": True,
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Label", "required": True},
                {
                    "name": "x_code",
                    "ttype": "char",
                    "string": "Reference",
                    "help": "Wire ir.sequence (e.g. INV/00001)",
                },
                {
                    "name": "x_ex_job_id",
                    "ttype": "many2one",
                    "relation": "x_ex_job",
                    "string": "Parent job",
                    "required": True,
                },
                {
                    "name": "x_partner_id",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "string": "Bill To",
                },
                {"name": "x_amount", "ttype": "float", "string": "Amount", "required": True},
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "relation": "res.currency",
                    "string": "Currency",
                },
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Status",
                    "selection": (
                        "[('draft','Draft'),('sent','Sent'),('partial','Partial'),"
                        "('paid','Paid'),('void','Void')]"
                    ),
                    "required": True,
                },
                {"name": "x_date", "ttype": "date", "string": "Date"},
                {
                    "name": "x_company_id",
                    "ttype": "many2one",
                    "relation": "res.company",
                    "string": "Company",
                },
            ],
        },
        {
            "model": "x_ex_event",
            "description": "Event / appointment / hearing (RENAME)",
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                {
                    "name": "x_ex_job_id",
                    "ttype": "many2one",
                    "relation": "x_ex_job",
                    "string": "Parent",
                    "required": True,
                },
                {"name": "x_date", "ttype": "date", "string": "Date", "required": True},
                {"name": "x_location", "ttype": "char", "string": "Location"},
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Status",
                    "selection": (
                        "[('scheduled','Scheduled'),('completed','Completed'),"
                        "('adjourned','Adjourned'),('cancelled','Cancelled')]"
                    ),
                },
            ],
        },
        {
            "model": "x_ex_party",
            "description": "Party / role link (RENAME) — not a mini-CRM",
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Label", "required": True},
                {
                    "name": "x_ex_job_id",
                    "ttype": "many2one",
                    "relation": "x_ex_job",
                    "string": "Parent",
                    "required": True,
                },
                {
                    "name": "x_partner_id",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "string": "Contact",
                    "required": True,
                },
                {
                    "name": "x_role",
                    "ttype": "selection",
                    "string": "Role",
                    "selection": (
                        "[('primary','Primary'),('related','Related'),"
                        "('opposing','Opposing'),('other','Other')]"
                    ),
                    "required": True,
                },
            ],
        },
        {
            "model": "x_ex_deposit",
            "description": "Deposit / retainer / hold (RENAME)",
            "is_workflow": True,
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Label", "required": True},
                {
                    "name": "x_ex_job_id",
                    "ttype": "many2one",
                    "relation": "x_ex_job",
                    "string": "Parent",
                    "required": True,
                },
                {
                    "name": "x_partner_id",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "string": "Payer",
                },
                {"name": "x_amount", "ttype": "float", "string": "Amount", "required": True},
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "relation": "res.currency",
                    "string": "Currency",
                },
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Status",
                    "selection": (
                        "[('held','Held'),('applied','Applied'),('refunded','Refunded')]"
                    ),
                    "required": True,
                },
            ],
        },
    ],
    "anti_patterns": [
        "Do NOT keep x_ex_* / x_resource / x_transaction names in the final JSON",
        "Do NOT add type/tag/stage/specialty as separate name+code models",
        "Do NOT emit Python code automations or broken smart_button shapes",
        "People/orgs = res.partner (or a party-link model), not a duplicate mini-CRM",
        "Do NOT use specialty_a / option_a selection placeholders",
    ],
}

_REGISTER_FEW_SHOT_EXEMPLAR = {
    "technical_name": "paper_register",
    "display_name": "Paper Register",
    "depends": ["base", "mail", "hr"],
    "models": [
        {
            "model": "x_paper_register",
            "description": "Paper Register",
            "mode": "new",
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                {
                    "name": "x_employee_id",
                    "ttype": "many2one",
                    "relation": "hr.employee",
                    "string": "Employee",
                    "required": True,
                },
                {"name": "x_purpose", "ttype": "char", "string": "Purpose", "required": True},
                {
                    "name": "x_time_in",
                    "ttype": "datetime",
                    "string": "Time in",
                    "required": True,
                },
                {"name": "x_time_out", "ttype": "datetime", "string": "Time out"},
            ],
        }
    ],
    "smart_buttons": [],
    "automations": [],
    "anti_patterns": [
        "Do NOT add party/line satellites or inherit crm.lead / account.move",
        "Do NOT invent a second Contacts app",
        "Do NOT add x_company_id or x_currency_id unless the brief named them",
        "Do NOT relabel time in/out as check-in/check-out unless the brief said check-in",
        "One x_* header — fill the stated columns; do not architect an ERP",
        "Duration on_time uses the header datetime, never create_date",
    ],
}


def few_shot_exemplar_json(*, max_chars: int = 6500, document_shape: str | None = None) -> str:
    if document_shape == "register":
        return json.dumps(_REGISTER_FEW_SHOT_EXEMPLAR, indent=None)[:max_chars]
    return json.dumps(_FEW_SHOT_EXEMPLAR, indent=None)[:max_chars]


def llm_emit_missing_scaffold_models(
    provider: Any,
    draft: dict[str, Any],
    scaffold: dict[str, Any],
    *,
    user_prompt: str,
) -> tuple[dict[str, Any], list[str]]:
    """Ask the LLM to emit scaffold models it omitted — pack merge is the fallback only."""
    from app.ai_prompt_constants import STEP_TEMPERATURES, append_prompt_blocks
    from app.llm_provider import LLMError
    from app.ai_prompt_constants import STEP_TEMPERATURES, append_prompt_blocks
    from app.ai_prompt_constants import STEP_TEMPERATURES, append_prompt_blocks

    notes: list[str] = []
    have = {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    missing_defs = [
        m
        for m in (scaffold.get("models") or [])
        if isinstance(m, dict)
        and m.get("model")
        and str(m["model"]) not in have
    ]
    if not missing_defs or provider is None:
        return draft, notes

    # Prioritize core masters first (staff / billing / compliance)
    def _core_rank(m: dict[str, Any]) -> int:
        leaf = str(m.get("model") or "").replace("x_", "")
        for i, k in enumerate(
            ("attorney", "staff", "doctor", "bill", "invoice", "compliance", "deposit")
        ):
            if k in leaf:
                return i
        return 50

    missing_defs = sorted(missing_defs, key=_core_rank)[:6]
    missing_ids = [str(m["model"]) for m in missing_defs]
    sketches = []
    for m in missing_defs:
        sketches.append(
            {
                "model": m.get("model"),
                "description": m.get("description"),
                "is_workflow": bool(m.get("is_workflow")),
                "field_hints": [
                    {
                        "name": f.get("name"),
                        "ttype": f.get("ttype"),
                        "string": f.get("string"),
                        "relation": f.get("relation"),
                    }
                    for f in (m.get("fields") or [])[:14]
                    if isinstance(f, dict)
                ],
            }
        )
    system = append_prompt_blocks(
        "You repair a ModuleSpec that omitted required ops models. "
        "Example output:\n"
        '{"models":[{"model":"x_matter_bill","description":"Client bill",'
        '"fields":[{"name":"x_name","ttype":"char","string":"Reference","required":true},'
        '{"name":"x_matter_id","ttype":"many2one","relation":"x_matter","string":"Matter"}]}]}\n'
        "Return ONLY the missing models in {\"models\":[...]}. "
        "Each model needs ≥6 substantive fields (x_name + relations + domain attrs). "
        "Fee-earner/counsel M2Os must relation the staff model, not res.users. "
        "Party/role-link models must NOT set is_workflow.\n"
        + MODEL_CREATION_RULES,
        user_prompt=user_prompt,
    )
    prompt = (
        f"User request:\n{user_prompt}\n\n"
        f"Already present models: {sorted(have)}\n"
        f"You MUST emit these missing models (use these technical names): {missing_ids}\n"
        f"Field hints from the world-class scaffold (adapt/deepen, do not thin):\n"
        f"{json.dumps(sketches)[:5000]}"
    )
    try:
        from app.ai_llm_budget import llm_json_with_budget

        raw, _ = llm_json_with_budget(
            provider,
            "quality",
            prompt,
            system=system,
            reasoning=False,
            temperature=STEP_TEMPERATURES["quality.scaffold_gap"],
        )
        data = raw if isinstance(raw, dict) else json.loads(raw)
    except (LLMError, TypeError, ValueError, json.JSONDecodeError) as exc:
        notes.append(f"quality: scaffold-gap LLM repair failed ({exc})")
        return draft, notes

    added = 0
    for m in data.get("models") or []:
        if not isinstance(m, dict) or not m.get("model"):
            continue
        mid = str(m["model"])
        if mid not in missing_ids or mid in have:
            continue
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        if len(fields) < 4:
            continue
        m = {**m, "source": "scaffold_gap_llm"}
        # Party links never workflows
        leaf = mid.replace("x_", "")
        if any(k in leaf for k in ("party", "role_link", "participant")):
            m["is_workflow"] = False
        draft.setdefault("models", []).append(m)
        have.add(mid)
        added += 1
        notes.append(f"quality: LLM emitted missing scaffold model {mid}")
    if added:
        notes.append(
            f"quality: scaffold-gap repair added {added}/{len(missing_ids)} model(s)"
        )
    elif missing_ids:
        notes.append(
            f"quality: scaffold-gap repair emitted none of {missing_ids} "
            "(pack merge may fill)"
        )
    return draft, notes


_CORE_SCAFFOLD_LEAF_KEYS = (
    "attorney",
    "doctor",
    "staff",
    "bill",
    "invoice",
    "compliance",
    "deposit",
    "trust",
)

_PACK_SCAFFOLD_LEAF_KEYS: dict[str, tuple[str, ...]] = {
    "law_firm": ("matter",),
    "retail_supermarket": ("staff", "compliance", "deposit"),
    "oil_gas_operations": ("facility", "asset", "work_order", "permit", "staff", "compliance"),
    "hospital": ("doctor", "staff", "compliance", "deposit"),
    "clinic": ("doctor", "staff", "compliance"),
}


def seed_missing_core_scaffold_models(
    draft: dict[str, Any],
    scaffold: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Pre-merge deterministic floor for core ops masters the LLM still omitted.

    Generation-gap warnings fire only when merge_domain_pack adds these models.
    Seeding here preserves pack merge as field-upgrade only — no gap warnings.
    Only seeds models that exist in the matched pack scaffold (never cross-industry).
    """
    notes: list[str] = []
    have = {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    scaffold_by_id = {
        str(m["model"]): m
        for m in (scaffold.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    pack_id = str(scaffold.get("domain_pack") or "")
    allowed_keys = _PACK_SCAFFOLD_LEAF_KEYS.get(pack_id, ("staff", "compliance", "deposit"))
    for mid, sm in scaffold_by_id.items():
        if mid in have:
            continue
        leaf = mid.replace("x_", "")
        if not any(k in leaf for k in allowed_keys):
            continue
        seeded = copy.deepcopy(sm)
        seeded["source"] = "scaffold_core_seed"
        draft.setdefault("models", []).append(seeded)
        have.add(mid)
        notes.append(
            f"quality: seeded core scaffold model {mid} before pack merge (LLM omitted)"
        )
    return draft, notes


def strip_invalid_relational_keys(draft: dict[str, Any]) -> list[str]:
    """Remove relation/relation_field on non-relational field types."""
    notes: list[str] = []
    rel_types = {"many2one", "one2many", "many2many", "reference"}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            ttype = str(field.get("ttype") or "")
            if ttype in rel_types:
                continue
            fname = str(field.get("name") or "")
            if field.pop("relation", None) is not None:
                notes.append(f"quality: stripped relation on {mid}.{fname} ({ttype})")
            if field.pop("relation_field", None) is not None:
                notes.append(f"quality: stripped relation_field on {mid}.{fname} ({ttype})")
    return notes


def repair_company_fk_targets(draft: dict[str, Any]) -> list[str]:
    """x_company_id must point at res.company, never a parallel x_company model."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if str(field.get("name") or "") != "x_company_id":
                continue
            if str(field.get("ttype") or "") != "many2one":
                continue
            rel = str(field.get("relation") or "")
            if rel and rel != "res.company":
                field["relation"] = "res.company"
                notes.append(f"quality: fixed {mid}.x_company_id → res.company (was {rel})")
    return notes


def min_fields_for_ambition(ambition: str, *, workflow: bool = False) -> int:
    base = {"thin": 3, "standard": 5, "comprehensive": 7}.get(ambition, 5)
    return base + (2 if workflow and ambition != "thin" else 0)


_CATALOG_HINT = re.compile(
    r"(^|_)(type|category|tag|stage|priority|status|kind)s?$",
    re.I,
)


def _looks_like_catalog_name(model_name: str) -> bool:
    leaf = model_name.replace("x_", "").split("_")[-1]
    return bool(_CATALOG_HINT.search(leaf)) or bool(
        _CATALOG_HINT.search(model_name.replace("x_", ""))
    )


def collapse_hollow_catalogs_to_selections(draft: dict[str, Any]) -> list[str]:
    """Rewrite hollow name+code lookup models into selection fields on parents."""
    from app.ai_depth import _is_hollow_model, _models

    notes: list[str] = []
    models = _models(draft)
    hollow = [
        m
        for m in models
        if _is_hollow_model(m)
        or (_looks_like_catalog_name(str(m["model"])) and len(m.get("fields") or []) <= 3)
    ]
    hollow_ids = {str(m["model"]) for m in hollow}
    if not hollow_ids:
        return notes

    default_sel = (
        "[('general','General'),('option_a','Option A'),('option_b','Option B'),"
        "('other','Other')]"
    )
    specialty_sel = (
        "[('general','General Practice'),('litigation','Litigation'),"
        "('corporate','Corporate'),('other','Other')]"
    )

    for parent in models:
        if str(parent["model"]) in hollow_ids:
            continue
        new_fields: list[dict[str, Any]] = []
        changed = False
        for f in parent.get("fields") or []:
            if not isinstance(f, dict):
                continue
            rel = str(f.get("relation") or "")
            ttype = str(f.get("ttype") or "")
            if ttype == "many2one" and rel in hollow_ids:
                fname = str(f.get("name") or "x_type")
                if fname.endswith("_id"):
                    fname = fname[: -len("_id")]
                if not fname.startswith("x_"):
                    fname = f"x_{fname}"
                sel = specialty_sel if "special" in fname or "practice" in fname else default_sel
                new_fields.append(
                    {
                        "name": fname,
                        "ttype": "selection",
                        "string": str(f.get("string") or "Type"),
                        "selection": sel,
                    }
                )
                changed = True
                notes.append(
                    f"quality: collapsed hollow {rel} → selection {parent.get('model')}.{fname}"
                )
            elif ttype == "many2many" and rel in hollow_ids:
                fname = str(f.get("name") or "x_tags")
                new_fields.append(
                    {
                        "name": fname,
                        "ttype": "char",
                        "string": str(f.get("string") or "Tags"),
                        "help": "Comma-separated tags (replaced hollow catalog model)",
                    }
                )
                changed = True
                notes.append(
                    f"quality: collapsed hollow M2M {rel} → char tags on {parent.get('model')}"
                )
            else:
                new_fields.append(f)
        if changed:
            parent["fields"] = new_fields

    draft["models"] = [m for m in models if str(m["model"]) not in hollow_ids]
    if hollow_ids:
        notes.append(f"quality: removed {len(hollow_ids)} hollow catalog model(s)")
    buttons = draft.get("smart_buttons")
    if isinstance(buttons, list):
        draft["smart_buttons"] = [
            b
            for b in buttons
            if isinstance(b, dict)
            and b.get("on_model") not in hollow_ids
            and b.get("related_model") not in hollow_ids
        ]
    return notes


def llm_deepen_model_fields(
    provider: Any,
    draft: dict[str, Any],
    *,
    user_prompt: str,
    ambition: str,
    min_fields: int,
) -> tuple[dict[str, Any], list[str]]:
    """Ask the LLM to add fields (and only substantive models) to thin drafts."""
    from app.ai_critique import apply_critique_repairs
    from app.ai_depth import _is_hollow_model, _models, compute_depth_metrics
    from app.ai_prompt_constants import STEP_TEMPERATURES, append_prompt_blocks
    from app.llm_provider import LLMError

    notes: list[str] = []
    thin = []
    for m in _models(draft):
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        need = min_fields + (2 if m.get("is_workflow") else 0)
        if len(fields) < need or _is_hollow_model(m):
            thin.append(
                {
                    "model": m.get("model"),
                    "description": m.get("description"),
                    "is_workflow": m.get("is_workflow"),
                    "field_count": len(fields),
                    "fields": [
                        {
                            "name": f.get("name"),
                            "ttype": f.get("ttype"),
                            "relation": f.get("relation"),
                        }
                        for f in fields
                    ],
                }
            )
    metrics = compute_depth_metrics(draft)
    if not thin and metrics.get("fields_avg", 0) >= float(min_fields):
        return draft, notes

    system = append_prompt_blocks(
        "You improve ModuleSpec MODEL QUALITY for Odoo Community. Example output:\n"
        '{"missing_fields":[{"model":"x_matter","name":"x_client_id","ttype":"many2one",'
        '"relation":"res.partner","string":"Client"}],'
        '"missing_models":[{"model":"x_matter_task","description":"Task line","is_workflow":false,'
        '"fields":[{"name":"x_name","ttype":"char","string":"Task","required":true},'
        '{"name":"x_matter_id","ttype":"many2one","relation":"x_matter","string":"Matter"}]}],'
        '"notes":["Deepened thin matter model"]}\n'
        + MODEL_CREATION_RULES
        + "\nNever add hollow catalog models (type/tag/stage/priority name+code only). "
        "Deepen listed thin models first. Triggers/automations are out of scope here.",
        user_prompt=user_prompt,
    )
    from app.ai_domain_briefing import attach_domain_briefing, briefing_prompt_block

    briefing = attach_domain_briefing(draft, user_prompt=user_prompt)
    brief_block = briefing_prompt_block(briefing)
    try:
        from app.ai_operator_brief import prompt_for_generators

        user_block = prompt_for_generators(user_prompt, draft)
    except Exception:
        user_block = user_prompt
    prompt = (
        f"{brief_block}\n\n" if brief_block else ""
    ) + (
        f"User request (ambition={ambition}):\n{user_block}\n\n"
        f"Thin / hollow models to deepen (min ~{min_fields} fields):\n"
        f"{json.dumps(thin, default=str)[:5000]}\n\n"
        f"All models:\n{json.dumps([m.get('model') for m in _models(draft)])}\n"
        "Add missing_fields on existing models; only add missing_models if the operational "
        "loop is missing a substantive role (lines, events, billing, checks)."
    )
    try:
        from app.ai_llm_budget import llm_json_with_budget

        raw, _ = llm_json_with_budget(
            provider,
            "quality",
            prompt,
            system=system,
            reasoning=False,
            temperature=STEP_TEMPERATURES["quality.field_deepen"],
        )
    except LLMError as exc:
        notes.append(f"quality: field-deepen skipped ({exc})")
        return draft, notes

    text = raw.strip() if isinstance(raw, str) else json.dumps(raw)
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            notes.append("quality: field-deepen non-JSON")
            return draft, notes
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            notes.append(f"quality: field-deepen malformed JSON ({exc})")
            return draft, notes
    if not isinstance(data, dict):
        notes.append("quality: field-deepen not an object")
        return draft, notes

    clean_models = []
    for row in data.get("missing_models") or []:
        if not isinstance(row, dict):
            continue
        fields = row.get("fields") if isinstance(row.get("fields"), list) else []
        probe = {"fields": fields, "is_workflow": row.get("is_workflow")}
        if _is_hollow_model(probe) or len(fields) < 5:
            notes.append(
                f"quality: rejected thin missing_model {row.get('model')!r}"
            )
            continue
        if _looks_like_catalog_name(str(row.get("model") or "")) and len(fields) < 6:
            notes.append(
                f"quality: rejected catalog-shaped missing_model {row.get('model')!r}"
            )
            continue
        clean_models.append(row)
    data = {**data, "missing_models": clean_models}
    data.pop("missing_automations", None)

    out, repair_notes = apply_critique_repairs(draft, data)
    notes.extend(repair_notes)
    notes.append("quality: field-deepen pass applied")
    return out, notes


def _model_ids(draft: dict[str, Any]) -> set[str]:
    return {
        str(m["model"])
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def _pick_model_by_keywords(model_ids: set[str], keywords: tuple[str, ...]) -> str | None:
    scored: list[tuple[int, int, str]] = []
    for mid in model_ids:
        leaf = mid.replace("x_", "").lower()
        score = sum(1 for k in keywords if k in leaf)
        if score:
            # Prefer custom draft models over stock builtins (hr.employee etc.)
            custom = 0 if mid.startswith("x_") else 1
            scored.append((score, custom, mid))
    if not scored:
        return None
    scored.sort(key=lambda t: (-t[0], t[1], t[2]))
    return scored[0][2]


_ORPHAN_REMAP_KEYWORDS: dict[str, tuple[str, ...]] = {
    # Exemplar / leak names → match any existing domain staff-like model
    "x_resource": (
        "attorney",
        "staff",
        "doctor",
        "nurse",
        "practitioner",
        "technician",
        "employee",
        "teacher",
        "agent",
        "driver",
        "fee",
    ),
    "x_ex_staff": (
        "attorney",
        "staff",
        "doctor",
        "nurse",
        "practitioner",
        "technician",
        "employee",
        "teacher",
        "agent",
        "driver",
    ),
    "x_transaction": (
        "matter",
        "case",
        "order",
        "job",
        "contract",
        "booking",
        "work",
        "enrollment",
        "appointment",
        "ticket",
        "claim",
    ),
    "x_ex_job": (
        "matter",
        "case",
        "order",
        "job",
        "contract",
        "booking",
        "enrollment",
        "appointment",
        "ticket",
        "claim",
    ),
    "x_transaction_line": (
        "matter_line",
        "time_entry",
        "order_line",
        "line",
        "task",
        "session",
        "item",
    ),
    "x_ex_job_line": (
        "matter_line",
        "time_entry",
        "order_line",
        "line",
        "task",
        "session",
        "item",
    ),
}


def repair_orphan_relations(draft: dict[str, Any]) -> list[str]:
    """Remap exemplar-leak / missing relations onto existing draft models."""
    from app.ai_rules import _BUILTIN_MODELS

    notes: list[str] = []
    draft_ids = _model_ids(draft)
    reuse_known: set[str] = set()
    reuse = draft.get("reuse")
    if isinstance(reuse, dict):
        for mid in reuse.get("models") or []:
            if mid:
                reuse_known.add(str(mid))
        plan = reuse.get("plan")
        if isinstance(plan, dict):
            for mid in plan.get("models") or []:
                if mid:
                    reuse_known.add(str(mid))
    catalog = draft.get("_connection_catalog")
    if isinstance(catalog, dict):
        for mid in catalog.get("available_models") or []:
            if mid:
                reuse_known.add(str(mid))
        for entry in catalog.get("stock") or []:
            if isinstance(entry, dict) and entry.get("model"):
                reuse_known.add(str(entry["model"]))
    known = draft_ids | set(_BUILTIN_MODELS) | reuse_known
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        fields = list(m.get("fields") or [])
        new_fields: list[Any] = []
        for f in fields:
            if not isinstance(f, dict):
                new_fields.append(f)
                continue
            rel = f.get("relation")
            if rel in (None, False, ""):
                # Drop spurious null relation keys on non-relational fields
                cleaned = {k: v for k, v in f.items() if k != "relation" or v}
                new_fields.append(cleaned)
                continue
            rel_s = str(rel)
            if not rel_s.startswith("x_"):
                # Stock Community relations are never spec orphans.
                new_fields.append(f)
                continue
            if rel_s in known:
                new_fields.append(f)
                continue
            # Prefer remapping onto draft x_* models, not stock HR/Project
            target = None
            for orphan, keys in _ORPHAN_REMAP_KEYWORDS.items():
                if rel_s == orphan or rel_s.startswith("x_ex_"):
                    target = _pick_model_by_keywords(draft_ids, keys) or _pick_model_by_keywords(
                        known, keys
                    )
                    if target:
                        break
            if target is None and rel_s.startswith("x_"):
                # Last resort: staff-like field names
                fname = str(f.get("name") or "")
                if any(k in fname for k in ("resource", "staff", "perform", "owner", "assignee")):
                    staff_keys = (
                        "attorney",
                        "staff",
                        "doctor",
                        "nurse",
                        "practitioner",
                        "technician",
                        "teacher",
                        "agent",
                        "driver",
                        "employee",
                    )
                    target = _pick_model_by_keywords(
                        draft_ids, staff_keys
                    ) or _pick_model_by_keywords(known, staff_keys)
            if target:
                new_fields.append({**f, "relation": target})
                notes.append(f"quality: remapped orphan {mid}.{f.get('name')} {rel_s}→{target}")
            else:
                notes.append(
                    f"quality: dropped orphan field {mid}.{f.get('name')} → {rel_s}"
                )
                # skip field
        m["fields"] = new_fields
    return notes


def purge_ghost_ui(draft: dict[str, Any]) -> list[str]:
    """Remove actions/menus/views/access for models that no longer exist."""
    notes: list[str] = []
    known = _model_ids(draft)
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
                mid = mid[len("model_") :]
            if mid and str(mid) not in known and str(mid).startswith("x_"):
                notes.append(f"quality: purged ghost {key} for {mid}")
                continue
            kept.append(row)
        draft[key] = kept

    menus = draft.get("menus")
    if isinstance(menus, list):
        # Drop leaf menus whose action points at purged technical names
        action_models = {
            a.get("technical_name"): a.get("model")
            for a in (draft.get("actions") or [])
            if isinstance(a, dict)
        }
        kept_menus = []
        for menu in menus:
            if not isinstance(menu, dict):
                continue
            act = menu.get("action_xml_id") or menu.get("action")
            if act and act in action_models and action_models[act] not in known:
                notes.append(f"quality: purged ghost menu {menu.get('name')}")
                continue
            # Also drop menus named for missing models via technical_name menu_x_specialty
            tech = str(menu.get("technical_name") or "")
            if tech.startswith("menu_x_"):
                mid = tech[len("menu_") :]
                if mid.startswith("x_") and mid not in known and menu.get("action_xml_id"):
                    notes.append(f"quality: purged ghost menu {tech}")
                    continue
            kept_menus.append(menu)
        draft["menus"] = kept_menus
    return notes


def normalize_smart_button_shapes(draft: dict[str, Any]) -> list[str]:
    """Fix LLM shapes like {model, button_name, relation_field} into apply-ready buttons."""
    notes: list[str] = []
    models = {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    buttons = draft.get("smart_buttons")
    if not isinstance(buttons, list):
        return notes
    fixed: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for btn in buttons:
        if not isinstance(btn, dict):
            continue
        if btn.get("on_model") and btn.get("related_model") and btn.get("relation_field"):
            key = (btn.get("on_model"), btn.get("related_model"), btn.get("relation_field"))
            if key not in seen:
                fixed.append(btn)
                seen.add(key)
            continue
        # Broken aliases: model / model_name + relation_field (+ button_name)
        parent = btn.get("on_model") or btn.get("model") or btn.get("model_name")
        rel = btn.get("relation_field")
        # Server-action style stubs without FK — try first child M2O pointing at parent
        if parent and not rel and btn.get("action_type") in {
            "server_action",
            "object",
            "action",
            None,
        }:
            child = None
            child_rel = None
            for mid, m in models.items():
                for f in m.get("fields") or []:
                    if (
                        isinstance(f, dict)
                        and f.get("ttype") == "many2one"
                        and str(f.get("relation") or "") == str(parent)
                    ):
                        child = mid
                        child_rel = str(f.get("name") or "")
                        break
                if child:
                    break
            if child and child_rel:
                label = str(
                    btn.get("label")
                    or btn.get("button_name")
                    or models[child].get("description")
                    or child
                )
                key = (str(parent), child, child_rel)
                if key not in seen:
                    fixed.append(
                        {
                            "on_model": str(parent),
                            "label": label,
                            "related_model": child,
                            "relation_field": child_rel,
                            "icon": btn.get("icon") or "fa-list",
                            "source": "quality_normalize",
                        }
                    )
                    seen.add(key)
                    notes.append(
                        f"quality: normalized action-stub smart_button {parent}→{child}"
                    )
                continue
        if not parent or not rel:
            notes.append(f"quality: dropped incomplete smart_button {btn!r}")
            continue
        child = None
        for mid, m in models.items():
            for f in m.get("fields") or []:
                if (
                    isinstance(f, dict)
                    and f.get("name") == rel
                    and str(f.get("relation") or "") == str(parent)
                ):
                    child = mid
                    break
            if child:
                break
        if not child:
            notes.append(
                f"quality: dropped smart_button on {parent} (no child with {rel})"
            )
            continue
        label = str(btn.get("label") or btn.get("button_name") or models[child].get("description") or child)
        key = (str(parent), child, str(rel))
        if key in seen:
            continue
        fixed.append(
            {
                "on_model": str(parent),
                "label": label,
                "related_model": child,
                "relation_field": str(rel),
                "icon": btn.get("icon") or "fa-list",
                "source": "quality_normalize",
            }
        )
        seen.add(key)
        notes.append(f"quality: normalized smart_button {parent}→{child}")
    draft["smart_buttons"] = fixed
    return notes


def dedupe_fields_by_name(draft: dict[str, Any]) -> list[str]:
    """Keep one field per name; prefer richer selection / more keys."""
    notes: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        if not fields:
            continue
        best: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for f in fields:
            name = str(f.get("name") or "")
            if not name:
                continue
            if name not in best:
                best[name] = f
                order.append(name)
                continue
            prev = best[name]
            prev_sel = len(str(prev.get("selection") or ""))
            new_sel = len(str(f.get("selection") or ""))
            prev_keys = len(prev)
            new_keys = len(f)
            if new_sel > prev_sel or (new_sel == prev_sel and new_keys > prev_keys):
                best[name] = f
            notes.append(f"quality: deduped duplicate field {m.get('model')}.{name}")
        m["fields"] = [best[n] for n in order if n in best]
    return notes


def repair_incomplete_relational_fields(draft: dict[str, Any]) -> list[str]:
    """Infer missing relation= on M2O/O2M, or drop unrecoverable stubs."""
    notes: list[str] = []
    known = _model_ids(draft)
    # Pass 1: many2one name → model
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        kept: list[Any] = []
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                kept.append(f)
                continue
            ttype = str(f.get("ttype") or "")
            if ttype != "many2one" or f.get("relation") not in (None, False, ""):
                kept.append(f)
                continue
            fname = str(f.get("name") or "")
            if fname.endswith("_id"):
                guess = fname[:-3]
                if guess in known:
                    kept.append({**f, "relation": guess})
                    notes.append(
                        f"quality: inferred relation {mid}.{fname} → {guess}"
                    )
                    continue
            notes.append(f"quality: dropped incomplete relational field {mid}.{fname}")
        m["fields"] = kept

    # Pass 2: one2many / many2many — fill relation + relation_field
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        kept = []
        seen_child: set[str] = set()
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                kept.append(f)
                continue
            ttype = str(f.get("ttype") or "")
            if ttype not in {"one2many", "many2many"}:
                kept.append(f)
                continue
            fname = str(f.get("name") or "")
            rel = f.get("relation")
            inverse = f.get("relation_field")
            if rel in (None, False, ""):
                child = None
                inverse = None
                for other in draft.get("models") or []:
                    if not isinstance(other, dict):
                        continue
                    oid = str(other.get("model") or "")
                    if oid == mid:
                        continue
                    for of in other.get("fields") or []:
                        if (
                            isinstance(of, dict)
                            and of.get("ttype") == "many2one"
                            and str(of.get("relation") or "") == mid
                        ):
                            child = oid
                            inverse = str(of.get("name") or "")
                            if "line" in oid or fname.endswith("_ids"):
                                break
                    if child and ("line" in (child or "") or fname.endswith("_ids")):
                        break
                if child and inverse:
                    rel = child
                    notes.append(
                        f"quality: inferred O2M {mid}.{fname} → {child}.{inverse}"
                    )
                else:
                    notes.append(
                        f"quality: dropped incomplete relational field {mid}.{fname}"
                    )
                    continue
            else:
                rel = str(rel)
                if not inverse:
                    # Find inverse M2O on child
                    for other in draft.get("models") or []:
                        if not isinstance(other, dict):
                            continue
                        if str(other.get("model") or "") != rel:
                            continue
                        for of in other.get("fields") or []:
                            if (
                                isinstance(of, dict)
                                and of.get("ttype") == "many2one"
                                and str(of.get("relation") or "") == mid
                            ):
                                inverse = str(of.get("name") or "")
                                notes.append(
                                    f"quality: filled relation_field "
                                    f"{mid}.{fname} → {inverse}"
                                )
                                break
            if not inverse and ttype == "one2many":
                notes.append(
                    f"quality: dropped O2M {mid}.{fname} (no inverse on {rel})"
                )
                continue
            # Dedupe multiple O2Ms to the same child model
            if ttype == "one2many" and rel in seen_child:
                notes.append(
                    f"quality: dropped duplicate O2M {mid}.{fname} → {rel}"
                )
                continue
            if ttype == "one2many":
                seen_child.add(str(rel))
            row = {**f, "relation": rel}
            if inverse:
                row["relation_field"] = inverse
            kept.append(row)
        m["fields"] = kept
    return notes


def filter_redundant_missing_models(
    draft: dict[str, Any], missing: list[Any]
) -> list[dict[str, Any]]:
    """Drop expand/critique suggestions that are catalogs, mini-CRMs, or too thin."""
    known = _model_ids(draft)
    billing = known & {"x_bill", "x_charge", "x_invoice"}
    has_partner_client = False
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        for f in m.get("fields") or []:
            if (
                isinstance(f, dict)
                and f.get("relation") == "res.partner"
                and any(
                    k in str(f.get("name") or "")
                    for k in ("partner", "client", "customer")
                )
            ):
                has_partner_client = True
                break
        if has_partner_client:
            break
    catalog_leaf = re.compile(
        r"(^type$|_type$|category|tag|stage|priority|specialty|case_type|"
        r"matter_type|client_contact|^client$|^customer$|^contact$)",
        re.I,
    )
    from app.ai_stock_first import (
        STAFF_ROLE_LEAVES,
        STOCK_CLONE_LEAVES,
        is_reuse_rich,
        stock_ops_reused,
    )

    out: list[dict[str, Any]] = []
    for row in missing:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("model") or "")
        if mid in known or not mid.startswith("x_"):
            continue
        leaf = mid.replace("x_", "")
        if catalog_leaf.search(leaf):
            continue
        if is_reuse_rich(draft):
            if leaf in STAFF_ROLE_LEAVES:
                continue
            ops = stock_ops_reused(draft)
            skip_clone = False
            for stock, leaves in STOCK_CLONE_LEAVES.items():
                if stock in ops and leaf in leaves:
                    skip_clone = True
                    break
            if skip_clone:
                continue
            pack_keep = {str(x) for x in (draft.get("_pack_model_ids") or []) if x}
            if pack_keep and mid not in pack_keep and not mid.endswith("_line") and not mid.endswith("_party"):
                continue
        if billing and leaf in {"invoice", "bill", "charge"}:
            continue
        if leaf in {"client", "customer", "contact", "client_contact"} and has_partner_client:
            continue
        fields = [f for f in (row.get("fields") or []) if isinstance(f, dict)]
        if len(fields) < 4:
            continue
        # Must link into the existing graph
        has_m2o = any(
            f.get("ttype") == "many2one" and f.get("relation") for f in fields
        )
        if not has_m2o:
            continue
        out.append(row)
    return out


def collapse_thin_padding_models(draft: dict[str, Any]) -> list[str]:
    """Remove known thin padding models (mini-CRM contacts, type catalogs, bare fee tables)."""
    notes: list[str] = []
    pad_leaf = re.compile(
        r"(client_contact|case_type|matter_type|_type$|_category|_tag|_stage|"
        r"specialty|fee_schedule|^client$|^customer$)",
        re.I,
    )
    remove: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict) or not m.get("model"):
            continue
        mid = str(m["model"])
        leaf = mid.replace("x_", "")
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        # Only strip known padding roles when thin — never drop arbitrary short models
        if pad_leaf.search(leaf) and len(fields) < 6:
            remove.append(mid)
    if not remove:
        return notes
    draft["models"] = [
        m
        for m in (draft.get("models") or [])
        if not (isinstance(m, dict) and str(m.get("model")) in remove)
    ]
    notes.append(f"quality: removed thin padding model(s) {', '.join(remove)}")
    for key in ("actions", "views", "access_rules"):
        rows = draft.get(key)
        if not isinstance(rows, list):
            continue
        draft[key] = [
            r
            for r in rows
            if not (
                isinstance(r, dict)
                and (
                    r.get("model") in remove
                    or (
                        key == "access_rules"
                        and str(r.get("model") or "").replace("model_", "", 1) in remove
                    )
                )
            )
        ]
    buttons = draft.get("smart_buttons")
    if isinstance(buttons, list):
        draft["smart_buttons"] = [
            b
            for b in buttons
            if isinstance(b, dict)
            and b.get("on_model") not in remove
            and b.get("related_model") not in remove
        ]
    return notes


def scrub_invalid_related_writes(draft: dict[str, Any]) -> list[str]:
    """Drop related_write actions that target O2M or missing fields / nonsense values."""
    notes: list[str] = []
    by_id = {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return notes
    kept_autos: list[dict[str, Any]] = []
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        mid = str(auto.get("model") or "")
        model = by_id.get(mid)
        if not model:
            # Critique often invents collapsed roles (x_hearing) after merge
            alias = {
                "x_hearing": "x_event",
                "x_appointment": "x_event",
                "x_schedule": "x_event",
            }
            remapped = alias.get(mid)
            if remapped and remapped not in by_id:
                remapped = next(
                    (
                        kid
                        for kid in by_id
                        if any(
                            k in kid.replace("x_", "")
                            for k in ("event", "hearing", "appointment")
                        )
                    ),
                    None,
                ) if "hearing" in mid or "appoint" in mid else None
            if remapped and remapped in by_id:
                notes.append(
                    f"quality: remapped automation model {mid} → {remapped}"
                )
                auto = {**auto, "model": remapped}
                mid = remapped
                model = by_id[mid]
            elif mid.startswith("x_"):
                notes.append(
                    f"quality: dropped automation on missing model {mid}"
                )
                continue
            else:
                kept_autos.append(auto)
                continue
        if not auto.get("safe_actions"):
            notes.append(
                f"quality: dropped empty automation {auto.get('name')}"
            )
            continue
        fields = {
            str(f.get("name")): f
            for f in (model.get("fields") or [])
            if isinstance(f, dict) and f.get("name")
        }
        clean: list[dict[str, Any]] = []
        for a in auto["safe_actions"]:
            if not isinstance(a, dict):
                continue
            if str(a.get("kind") or "") != "related_write":
                clean.append(a)
                continue
            rel_name = str(a.get("relation_field") or "")
            rel_def = fields.get(rel_name)
            if not rel_def or str(rel_def.get("ttype")) != "many2one":
                notes.append(
                    f"quality: dropped related_write on {mid} "
                    f"(need many2one {rel_name!r})"
                )
                continue
            target_model = str(rel_def.get("relation") or "")
            target = by_id.get(target_model)
            tfield = str(a.get("field") or "")
            if not target:
                notes.append(
                    f"quality: dropped related_write on {mid} (unknown {target_model})"
                )
                continue
            target_fields = {
                str(f.get("name"))
                for f in (target.get("fields") or [])
                if isinstance(f, dict)
            }
            if tfield not in target_fields:
                notes.append(
                    f"quality: dropped related_write {mid}.{rel_name}.{tfield} "
                    "(field missing on target)"
                )
                continue
            val = a.get("value")
            if val in {"default", "none", "null", None, ""}:
                notes.append(
                    f"quality: dropped related_write {mid}.{rel_name}.{tfield} "
                    f"(placeholder value {val!r})"
                )
                continue
            tdef = next(
                (
                    f
                    for f in (target.get("fields") or [])
                    if isinstance(f, dict) and f.get("name") == tfield
                ),
                None,
            )
            if tdef and str(tdef.get("ttype")) == "selection":
                keys = set(
                    re.findall(r"\(\s*'([^']+)'\s*,", str(tdef.get("selection") or ""))
                )
                if keys and str(val) not in keys:
                    notes.append(
                        f"quality: dropped related_write {mid}.{rel_name}.{tfield} "
                        f"(value {val!r} not in selection)"
                    )
                    continue
            clean.append(a)
        if not clean:
            notes.append(
                f"quality: dropped empty automation {auto.get('name')} after scrub"
            )
            continue
        kept_autos.append({**auto, "safe_actions": clean})
    draft["automations"] = kept_autos
    return notes


_PLACEHOLDER_SELECTION_RE = re.compile(
    r"^(option_[a-z]|specialty_[a-z]|area_[a-z]|type_[a-z])$",
    re.I,
)
_DEFAULT_SPRAY_RE = re.compile(r"^x_default_.+_(pct|percent|rate|amount)$", re.I)


def gate_llm_field_quality(draft: dict[str, Any]) -> list[str]:
    """Reject placeholder selections, duplicate sprays, and near-duplicate fields."""
    notes: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        kept: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        spray_groups: dict[str, list[dict[str, Any]]] = {}
        for f in fields:
            fname = str(f.get("name") or "")
            ttype = str(f.get("ttype") or "")
            if ttype == "selection":
                sel = str(f.get("selection") or "")
                keys = re.findall(r"\('([^']+)'\s*,", sel)
                if any(_PLACEHOLDER_SELECTION_RE.match(k) for k in keys):
                    notes.append(
                        f"quality: placeholder selection keys on {mid}.{fname} "
                        "(will be normalized)"
                    )
            if fname in seen_names:
                notes.append(f"quality: dropped duplicate field {mid}.{fname}")
                continue
            if _DEFAULT_SPRAY_RE.match(fname):
                base = fname.replace("x_default_", "x_", 1)
                if base in {str(x.get("name")) for x in fields} or any(
                    str(x.get("name")) == base for x in kept
                ):
                    notes.append(
                        f"quality: dropped duplicate spray {mid}.{fname} (≈ {base})"
                    )
                    continue
                spray_groups.setdefault("default_spray", []).append(f)
            if fname == "x_default_currency_id":
                if any(
                    str(x.get("name")) == "x_currency_id"
                    for x in fields + kept
                ):
                    notes.append(
                        f"quality: dropped {mid}.x_default_currency_id (x_currency_id exists)"
                    )
                    continue
            kept.append(f)
            seen_names.add(fname)
        # Collapse excessive default_*_pct sprays — keep first two
        sprays = [
            f
            for f in kept
            if _DEFAULT_SPRAY_RE.match(str(f.get("name") or ""))
            and str(f.get("ttype") or "") in {"float", "integer", "monetary"}
        ]
        if len(sprays) > 2:
            drop = {id(f) for f in sprays[2:]}
            kept = [f for f in kept if id(f) not in drop]
            notes.append(
                f"quality: collapsed {len(sprays) - 2} near-duplicate default pct field(s) on {mid}"
            )
        if len(kept) != len(fields):
            m["fields"] = kept
    return notes


def scrub_placeholder_selections(draft: dict[str, Any]) -> list[str]:
    """Replace specialty_a / option_a style selection keys with usable labels."""
    notes: list[str] = []
    placeholder = re.compile(
        r"specialty_[a-z]|option_[a-z]|area_[a-z]|type_[a-z]", re.I
    )
    practice_sel = (
        "[('general','General'),('corporate','Corporate'),"
        "('litigation','Litigation'),('family','Family'),('other','Other')]"
    )
    generic_sel = (
        "[('standard','Standard'),('premium','Premium'),"
        "('custom','Custom'),('other','Other')]"
    )
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        for f in m.get("fields") or []:
            if not isinstance(f, dict) or f.get("ttype") != "selection":
                continue
            sel = str(f.get("selection") or "")
            if not placeholder.search(sel):
                continue
            fname = str(f.get("name") or "")
            if any(k in fname for k in ("practice", "specialty", "area")):
                f["selection"] = practice_sel
            else:
                f["selection"] = generic_sel
            notes.append(
                f"quality: replaced placeholder selection "
                f"{m.get('model')}.{fname}"
            )
    return notes


def odoo_o2m_field_name(child_model: str) -> str:
    """Legal ``x_*_ids`` name — stock models must not keep dots (``x_calendar.event_ids``)."""
    leaf = str(child_model or "").replace("x_", "", 1).replace(".", "_")
    leaf = re.sub(r"[^a-zA-Z0-9_]", "_", leaf).strip("_")
    return f"x_{leaf or 'related'}_ids"


def ensure_parent_o2ms_for_children(
    draft: dict[str, Any], *, max_o2m_per_parent: int = 8
) -> list[str]:
    """Add missing one2many on custom parents for each child M2O pointing at them."""
    notes: list[str] = []
    by_id = {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    # Only custom x_* headers. Stock inherit (sale.order, project.task) is not a
    # parent to decorate — inverse of inherit x_matter_id lives on the residual.
    parents = [
        m
        for m in by_id.values()
        if str(m.get("model") or "").startswith("x_")
        and (
            m.get("is_workflow")
            or any(
                k in str(m.get("model") or "")
                for k in ("matter", "order", "job", "case", "project", "workorder")
            )
        )
    ]
    if not parents:
        return notes

    for parent in parents:
        pid = str(parent["model"])
        fields = list(parent.get("fields") or [])
        existing_rels = {
            str(f.get("relation"))
            for f in fields
            if isinstance(f, dict) and f.get("ttype") == "one2many"
        }
        existing_names = {
            str(f.get("name")) for f in fields if isinstance(f, dict)
        }
        # Drop illegal dotted O2M names left by earlier passes
        cleaned: list[dict[str, Any]] = []
        for f in fields:
            if not isinstance(f, dict):
                continue
            fname = str(f.get("name") or "")
            if f.get("ttype") == "one2many" and "." in fname:
                notes.append(f"quality: dropped illegal O2M name {pid}.{fname}")
                existing_rels.discard(str(f.get("relation") or ""))
                existing_names.discard(fname)
                continue
            cleaned.append(f)
        fields = cleaned
        existing_names = {str(f.get("name")) for f in fields if isinstance(f, dict)}
        existing_rels = {
            str(f.get("relation"))
            for f in fields
            if isinstance(f, dict) and f.get("ttype") == "one2many"
        }
        added = 0
        for child in by_id.values():
            cid = str(child["model"])
            if cid == pid or cid in existing_rels:
                continue
            # Stock inherit (sale.order, calendar.event) is a smart-button
            # target. Nested O2M lists would emit x_name, which those models
            # do not have. Inverse M2O already lives on the inherit.
            if not cid.startswith("x_"):
                continue
            inverse = None
            for f in child.get("fields") or []:
                if (
                    isinstance(f, dict)
                    and f.get("ttype") == "many2one"
                    and str(f.get("relation") or "") == pid
                ):
                    inverse = str(f.get("name") or "")
                    break
            if not inverse:
                continue
            fname = odoo_o2m_field_name(cid)
            if fname in existing_names:
                continue
            label = str(child.get("description") or cid).split("/")[0].strip()
            fields.append(
                {
                    "name": fname,
                    "ttype": "one2many",
                    "string": label or cid,
                    "relation": cid,
                    "relation_field": inverse,
                    "source": "quality_o2m",
                }
            )
            existing_rels.add(cid)
            existing_names.add(fname)
            added += 1
            notes.append(f"quality: added O2M {pid}.{fname} → {cid}.{inverse}")
            if len(existing_rels) >= max_o2m_per_parent:
                break
        if added or len(cleaned) != len(list(parent.get("fields") or [])):
            parent["fields"] = fields
    notes.extend(drop_illegal_o2ms(draft))
    return notes


def drop_illegal_o2ms(draft: dict[str, Any]) -> list[str]:
    """Drop dotted O2M names and inverses whose FK is missing on the related model."""
    notes: list[str] = []
    by_id = {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    for mid, model in by_id.items():
        kept: list[dict[str, Any]] = []
        changed = False
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if field.get("ttype") != "one2many":
                kept.append(field)
                continue
            fname = str(field.get("name") or "")
            child_id = str(field.get("relation") or "")
            inverse = str(field.get("relation_field") or "")
            if "." in fname:
                notes.append(f"quality: dropped illegal O2M name {mid}.{fname}")
                changed = True
                continue
            child = by_id.get(child_id)
            if child and inverse:
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
                        f"quality: dropped O2M {mid}.{fname} "
                        f"(missing inverse {child_id}.{inverse})"
                    )
                    changed = True
                    continue
            kept.append(field)
        if changed:
            model["fields"] = kept
    return notes


def ensure_line_bill_link(draft: dict[str, Any]) -> list[str]:
    """Connect time/line models to bill/invoice when both exist."""
    notes: list[str] = []
    by_id = {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    bill = next(
        (
            m
            for mid, m in by_id.items()
            if any(k in mid for k in ("bill", "invoice"))
        ),
        None,
    )
    if not bill:
        return notes
    bill_id = str(bill["model"])
    for mid, line in by_id.items():
        if not any(k in mid for k in ("line", "time", "entry", "timesheet")):
            continue
        names = {
            str(f.get("name"))
            for f in (line.get("fields") or [])
            if isinstance(f, dict)
        }
        if "x_bill_id" in names:
            continue
        line.setdefault("fields", []).append(
            {
                "name": "x_bill_id",
                "ttype": "many2one",
                "relation": bill_id,
                "string": "Bill",
            }
        )
        notes.append(f"quality: linked {mid}.x_bill_id → {bill_id}")
        # O2M on bill if missing
        bill_fields = bill.get("fields") or []
        if not any(
            isinstance(f, dict)
            and f.get("ttype") == "one2many"
            and f.get("relation") == mid
            for f in bill_fields
        ):
            leaf = mid.replace("x_", "")
            bill_fields.append(
                {
                    "name": f"x_{leaf}_ids",
                    "ttype": "one2many",
                    "string": str(line.get("description") or leaf),
                    "relation": mid,
                    "relation_field": "x_bill_id",
                    "source": "quality_o2m",
                }
            )
            bill["fields"] = bill_fields
            notes.append(f"quality: added O2M {bill_id}.x_{leaf}_ids → {mid}")
    return notes


def dedupe_redundant_automations(draft: dict[str, Any]) -> list[str]:
    """Keep one next_activity-only automation per model (prefer rules/depth)."""
    notes: list[str] = []
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return notes

    def is_followup_only(auto: dict[str, Any]) -> bool:
        actions = auto.get("safe_actions") or []
        if not actions:
            return False
        return all(
            isinstance(a, dict) and str(a.get("kind")) == "next_activity"
            for a in actions
        )

    def rank(auto: dict[str, Any]) -> tuple[int, str]:
        src = str(auto.get("source") or "")
        pri = {"rules_engine": 0, "depth_seed": 1, "depth_floor": 1}.get(src, 5)
        if "overdue" in str(auto.get("name") or "").lower():
            pri -= 1  # keep overdue distinct via name — handled separately
        return (pri, str(auto.get("name") or ""))

    # Separate overdue / timed from generic follow-ups
    kept: list[dict[str, Any]] = []
    followups_by_model: dict[str, list[dict[str, Any]]] = {}
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        mid = str(auto.get("model") or "")
        name_l = str(auto.get("name") or "").lower()
        trigger = str(auto.get("trigger") or "")
        if (
            is_followup_only(auto)
            and trigger in {"on_write", "on_create", "on_create_or_write", ""}
            and "overdue" not in name_l
        ):
            followups_by_model.setdefault(mid, []).append(auto)
            continue
        kept.append(auto)

    for mid, group in followups_by_model.items():
        group.sort(key=rank)
        kept.append(group[0])
        if len(group) > 1:
            notes.append(
                f"quality: deduped {len(group) - 1} follow-up automation(s) on {mid}"
            )
    draft["automations"] = kept
    return notes


def scrub_exemplar_help_text(draft: dict[str, Any]) -> list[str]:
    """Remove few-shot leaks like RNT/00001 from field help strings."""
    notes: list[str] = []
    leak = re.compile(r"\b(RNT|REC|JOB|EX)/\d+\b", re.I)
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "x")
        leaf = mid.replace("x_", "")
        # Prefer first token: matter_line → MAT, bill → BIL
        token = leaf.split("_")[0].upper()[:3] or "REC"
        for f in m.get("fields") or []:
            if not isinstance(f, dict) or not f.get("help"):
                continue
            help_s = str(f["help"])
            if leak.search(help_s) or (
                f.get("name") in {"x_code", "x_reference"}
                and "wire ir.sequence" in help_s.lower()
                and token not in help_s.upper()
            ):
                if f.get("name") in {"x_code", "x_reference"}:
                    f["help"] = f"Wire ir.sequence (e.g. {token}/00001)"
                else:
                    f["help"] = leak.sub(f"{token}/00001", help_s)
                notes.append(f"quality: scrubbed help on {mid}.{f.get('name')}")
    return notes


def cap_partner_smart_buttons(draft: dict[str, Any], *, max_partner: int = 4) -> list[str]:
    """Keep Contacts button_box focused — prefer header/workflow models."""
    notes: list[str] = []
    buttons = draft.get("smart_buttons")
    if not isinstance(buttons, list):
        return notes
    notebook_children = {
        str(f.get("relation") or "")
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and str(m.get("mode") or "new") != "inherit"
        for f in (m.get("fields") or [])
        if isinstance(f, dict)
        and f.get("ttype") == "one2many"
        and str(f.get("relation") or "").startswith("x_")
    }
    pruned = [
        b
        for b in buttons
        if not (
            isinstance(b, dict)
            and b.get("on_model") == "res.partner"
            and str(b.get("related_model") or "") in notebook_children
        )
    ]
    if len(pruned) != len(buttons):
        dropped_nb = len(buttons) - len(pruned)
        draft["smart_buttons"] = pruned
        buttons = pruned
        notes.append(
            f"quality: dropped {dropped_nb} Contacts notebook-child smart button(s)"
        )
    partner_btns = [
        b
        for b in buttons
        if isinstance(b, dict) and b.get("on_model") == "res.partner"
    ]
    if len(partner_btns) <= max_partner:
        return notes
    by_id = {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }

    def score(btn: dict[str, Any]) -> tuple[int, str]:
        mid = str(btn.get("related_model") or "")
        m = by_id.get(mid) or {}
        s = 0
        if m.get("is_workflow"):
            s += 50
        leaf = mid.replace("x_", "")
        if any(
            k in leaf for k in ("matter", "order", "job", "bill", "invoice", "case")
        ):
            s += 30
        if leaf.endswith("line") or "line" in leaf:
            s -= 20
        if leaf.endswith("party") or "party" in leaf:
            s -= 40
        if m.get("source") == "depth_seed":
            s -= 5
        return (-s, mid)

    partner_btns.sort(key=score)
    keep = {id(b) for b in partner_btns[:max_partner]}
    dropped = len(partner_btns) - max_partner
    draft["smart_buttons"] = [
        b
        for b in buttons
        if not (isinstance(b, dict) and b.get("on_model") == "res.partner")
        or id(b) in keep
    ]
    notes.append(
        f"quality: capped res.partner smart buttons to {max_partner} (−{dropped})"
    )
    return notes


def refresh_forms_missing_relational_fields(draft: dict[str, Any]) -> list[str]:
    """Rebuild form arches that omit stored model fields or stale statusbars."""
    from app.ai_enrich import sync_form_archs_to_models

    return sync_form_archs_to_models(draft)


def normalize_automation_shapes(draft: dict[str, Any]) -> list[str]:
    """Convert incomplete LLM automation stubs into safe_actions or drop them."""
    notes: list[str] = []
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return notes
    kept: list[dict[str, Any]] = []
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        if auto.get("safe_actions"):
            # Fix dotted object_write field → related_write
            actions = []
            for a in auto["safe_actions"]:
                if not isinstance(a, dict):
                    continue
                field = str(a.get("field") or a.get("field_name") or "")
                kind = str(a.get("kind") or "")
                if kind in {"object_write", "update_field"} and "." in field:
                    rel, _, fname = field.partition(".")
                    actions.append(
                        {
                            "kind": "related_write",
                            "relation_field": rel,
                            "field": fname,
                            "value": a.get("value"),
                        }
                    )
                else:
                    actions.append(a)
            auto = {**auto, "safe_actions": actions}
            kept.append(auto)
            continue
        # Flat broken: action="object_write", fields=["x_status"] without value
        action = auto.get("action")
        if isinstance(action, str) and action in {"object_write", "related_write", "next_activity"}:
            fields = auto.get("fields") or []
            if action == "next_activity":
                kept.append(
                    {
                        "name": auto.get("name") or "Follow-up activity",
                        "model": auto.get("model"),
                        "trigger": auto.get("trigger") or "on_write",
                        "safe_actions": [
                            {"kind": "next_activity", "summary": "Follow up"}
                        ],
                        "source": "quality_normalize",
                    }
                )
                notes.append("quality: normalized bare next_activity automation")
                continue
            if action == "object_write" and fields and auto.get("value") is not None:
                kept.append(
                    {
                        "name": auto.get("name") or "Update field",
                        "model": auto.get("model"),
                        "trigger": auto.get("trigger") or "on_write",
                        "safe_actions": [
                            {
                                "kind": "object_write",
                                "field": fields[0],
                                "value": auto["value"],
                            }
                        ],
                        "source": "quality_normalize",
                    }
                )
                notes.append("quality: normalized bare object_write automation")
                continue
            notes.append(
                f"quality: dropped incomplete automation on {auto.get('model')} ({action})"
            )
            continue
        if isinstance(action, dict):
            # unsafe server action — leave for strip_unsafe later
            kept.append(auto)
            continue
        notes.append(f"quality: dropped incomplete automation {auto.get('name') or auto}")
    draft["automations"] = kept
    return notes


def drop_redundant_role_name_fields(draft: dict[str, Any]) -> list[str]:
    """Remove x_<role>_name char fields when x_<role>_id many2one exists on the same model."""
    from app.ai_enrich import drop_redundant_role_name_fields as _prune_fields

    notes: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        pruned = _prune_fields(fields)
        if len(pruned) == len(fields):
            continue
        dropped = {str(f.get("name")) for f in fields} - {str(f.get("name")) for f in pruned}
        m["fields"] = pruned
        mid = str(m.get("model") or "")
        notes.append(
            f"quality: dropped redundant name field(s) on {mid}: {', '.join(sorted(dropped))}"
        )
        for v in draft.get("views") or []:
            if not isinstance(v, dict) or v.get("model") != mid:
                continue
            arch = str(v.get("arch") or "")
            for name in dropped:
                arch = re.sub(
                    rf'<field name="{re.escape(name)}"(?:[^>]*)?/?>',
                    "",
                    arch,
                )
            v["arch"] = arch
    return notes


def dedupe_redundant_partner_fields(draft: dict[str, Any]) -> list[str]:
    """Canonicalize res.partner links to x_partner_id (views/buttons stay in sync)."""
    notes: list[str] = []
    _LABEL_ALIASES = frozenset({"customer", "contact", "partner", "client"})
    _NAME_ALIASES = frozenset(
        {"x_partner_id", "x_client_id", "x_customer_id", "x_contact_id"}
    )

    def _is_partner_alias(field: dict[str, Any], *, model_name: str) -> bool:
        if field.get("relation") != "res.partner":
            return False
        name = str(field.get("name") or "")
        if name in _NAME_ALIASES:
            return True
        # Flash often names the M2O after the model (x_punch_card → Customer).
        if name and name == model_name:
            return True
        label = str(field.get("string") or "").strip().lower()
        return label in _LABEL_ALIASES

    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        aliases = [f for f in fields if _is_partner_alias(f, model_name=mid)]
        if not aliases:
            continue
        label = next(
            (str(f.get("string") or "") for f in aliases if f.get("string")),
            "Contact",
        )
        kept: list[dict[str, Any]] = []
        wrote_partner = False
        renamed = False
        dropped_names: list[str] = []
        for f in fields:
            name = str(f.get("name") or "")
            if _is_partner_alias(f, model_name=mid):
                if wrote_partner:
                    renamed = True
                    dropped_names.append(name)
                    continue
                if name != "x_partner_id":
                    renamed = True
                    dropped_names.append(name)
                kept.append(
                    {
                        **f,
                        "name": "x_partner_id",
                        "string": f.get("string") or label,
                        "relation": "res.partner",
                    }
                )
                wrote_partner = True
                continue
            kept.append(f)
        if renamed or any(f.get("name") != "x_partner_id" for f in aliases):
            m["fields"] = kept
            notes.append(
                f"quality: normalized partner link on {mid} → x_partner_id"
                + (f" (dropped {', '.join(dropped_names)})" if dropped_names else "")
            )
            for btn in draft.get("smart_buttons") or []:
                if (
                    isinstance(btn, dict)
                    and btn.get("related_model") == mid
                    and btn.get("relation_field") in (_NAME_ALIASES | {mid})
                ):
                    btn["relation_field"] = "x_partner_id"
            for v in draft.get("views") or []:
                if not isinstance(v, dict) or v.get("model") != mid:
                    continue
                arch = str(v.get("arch") or "")
                new_arch = arch
                for old in dropped_names:
                    if old and old != "x_partner_id":
                        new_arch = new_arch.replace(old, "x_partner_id")
                for old in ("x_client_id", "x_customer_id", "x_contact_id"):
                    new_arch = new_arch.replace(old, "x_partner_id")
                if new_arch != arch:
                    v["arch"] = new_arch
    return notes


def fill_empty_selection_fields(draft: dict[str, Any]) -> list[str]:
    """Give empty selection fields a usable default set."""
    notes: list[str] = []
    from app.ai_domain_briefing import briefing_from_dict
    from app.ai_selection import serialize_selection

    brief = briefing_from_dict(
        draft.get("_domain_briefing")
        if isinstance(draft.get("_domain_briefing"), dict)
        else None
    )
    defaults = {
        "x_status": (
            "[('draft','Draft'),('open','Open'),('done','Done'),"
            "('cancelled','Cancelled')]"
        ),
        "x_priority": "[('low','Low'),('normal','Normal'),('high','High')]",
        "x_rate_type": (
            "[('hourly','Hourly'),('daily','Daily'),('fixed','Fixed'),"
            "('other','Other')]"
        ),
    }
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        for f in m.get("fields") or []:
            if not isinstance(f, dict) or f.get("ttype") != "selection":
                continue
            if f.get("selection") not in (None, False, "", []):
                continue
            name = str(f.get("name") or "")
            sel = defaults.get(name)
            if (
                not sel
                and brief
                and brief.equipment_types
                and any(tok in mid for tok in ("equipment", "asset", "gear"))
                and "type" in name
            ):
                sel = serialize_selection(brief.equipment_types)
            if (
                not sel
                and brief
                and brief.rate_uoms
                and any(tok in mid for tok in ("rate", "tariff"))
                and any(tok in name for tok in ("uom", "unit", "rate_type"))
            ):
                sel = serialize_selection(brief.rate_uoms)
            if not sel and "status" in name:
                sel = defaults["x_status"]
            if not sel and "rate" in name:
                sel = defaults["x_rate_type"]
            if not sel:
                sel = "[('a','Option A'),('b','Option B'),('other','Other')]"
            f["selection"] = sel
            notes.append(
                f"quality: filled empty selection {m.get('model')}.{name}"
            )
    return notes


def dedupe_automation_safe_actions(draft: dict[str, Any]) -> list[str]:
    """Drop duplicate safe_actions rows inside an automation."""
    notes: list[str] = []
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        actions = auto.get("safe_actions")
        if not isinstance(actions, list) or len(actions) < 2:
            continue
        seen: set[tuple[Any, ...]] = set()
        kept: list[dict[str, Any]] = []
        for a in actions:
            if not isinstance(a, dict):
                continue
            kind = str(a.get("kind") or "")
            # Collapse multiple next_activity rows into one
            if kind == "next_activity":
                key = ("next_activity",)
            else:
                key = (
                    kind,
                    a.get("field"),
                    a.get("value"),
                    a.get("relation_field"),
                    a.get("summary"),
                )
            if key in seen:
                continue
            seen.add(key)
            kept.append(a)
        if len(kept) < len(actions):
            auto["safe_actions"] = kept
            notes.append(
                f"quality: deduped safe_actions on automation {auto.get('name')}"
            )
    return notes


def deepen_thin_ops_children(draft: dict[str, Any]) -> list[str]:
    """Add status to deadline/party-style seed children when missing."""
    notes: list[str] = []
    status_sel = (
        "[('draft','Draft'),('open','Open'),('done','Done'),"
        "('cancelled','Cancelled')]"
    )
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        if not mid.startswith("x_") or str(m.get("mode") or "") == "inherit":
            continue
        leaf = mid.replace("x_", "")
        names = {
            str(f.get("name"))
            for f in (m.get("fields") or [])
            if isinstance(f, dict)
        }
        # Join tables (party/role) are not ops children — a role column is not a workflow.
        if any(k in leaf for k in ("party", "role_link", "participant", "stakeholder")):
            continue
        wants_status = any(
            k in leaf for k in ("task", "compliance", "milestone")
        ) or "x_date_deadline" in names
        if not wants_status or "x_status" in names:
            continue
        m.setdefault("fields", []).append(
            {
                "name": "x_status",
                "ttype": "selection",
                "string": "Status",
                "selection": status_sel,
            }
        )
        notes.append(f"quality: added x_status on ops child {mid}")
    return notes


def deepen_thin_rate_models(draft: dict[str, Any]) -> list[str]:
    """Ensure rate/price models have currency + company + filled rate_type."""
    notes: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        if "rate" not in mid.replace("x_", ""):
            continue
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        names = {str(f.get("name")) for f in fields}
        changed = False
        if "x_currency_id" not in names:
            fields.append(
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "relation": "res.currency",
                    "string": "Currency",
                }
            )
            changed = True
        if "x_company_id" not in names:
            fields.append(
                {
                    "name": "x_company_id",
                    "ttype": "many2one",
                    "relation": "res.company",
                    "string": "Company",
                }
            )
            changed = True
        for f in fields:
            if f.get("name") == "x_rate_type" and not f.get("selection"):
                f["selection"] = (
                    "[('hourly','Hourly'),('daily','Daily'),"
                    "('fixed','Fixed'),('other','Other')]"
                )
                changed = True
        if changed:
            m["fields"] = fields
            notes.append(f"quality: deepened rate model {mid}")
    return notes


def ensure_terminal_workflow_statuses(draft: dict[str, Any]) -> list[str]:
    """Primary transaction header must include a terminal stage (closed/done/…)."""
    from app.ai_depth import _primary_transaction_model
    from app.ai_selection import parse_selection_literal, selection_keys, serialize_selection
    from app.ai_workflow import derive_default_transitions

    notes: list[str] = []
    parent = _primary_transaction_model(draft)
    if not parent:
        return notes
    mid = str(parent.get("model") or "")
    leaf = mid.replace("x_", "")
    # Never touch child lines / party links even if leaf contains the header token
    if any(
        leaf.endswith(s)
        for s in ("_line", "_party", "_item", "_detail", "_payment", "_move")
    ):
        return notes
    status = next(
        (
            f
            for f in (parent.get("fields") or [])
            if isinstance(f, dict) and f.get("name") == "x_status"
        ),
        None,
    )
    if not status or not status.get("selection"):
        return notes
    pairs = parse_selection_literal(status.get("selection")) or []
    keys = {k for k, _ in pairs}
    terminals = {"closed", "done", "cancelled", "void", "on_hold"}
    terminal_append = [
        ("closed", "Closed"),
        ("on_hold", "On hold"),
        ("cancelled", "Cancelled"),
    ]
    if keys & terminals:
        sf = parent.get("state_field")
        ordered = selection_keys(status.get("selection"))
        if isinstance(sf, dict):
            sf_states = [str(s) for s in (sf.get("states") or [])]
            flow = [k for k in ordered if k not in terminals]
            if flow and sf_states and set(sf_states) <= terminals:
                sf["states"] = ordered
                sf["transitions"] = derive_default_transitions(ordered)
                notes.append(
                    f"quality: restored flow states on {mid}.state_field (was terminals-only)"
                )
        return notes
    for key, label in terminal_append:
        if key not in keys:
            pairs.append((key, label))
            keys.add(key)
    status["selection"] = serialize_selection(pairs)
    ordered = [k for k, _ in pairs]
    parent["state_field"] = {
        "field": "x_status",
        "states": ordered,
        "transitions": derive_default_transitions(ordered),
    }
    notes.append(f"quality: added terminal statuses on {mid}.x_status")
    return notes


def scrub_polluted_line_statuses(draft: dict[str, Any]) -> list[str]:
    """Remove header terminal keys wrongly appended onto line/time selections."""
    notes: list[str] = []
    line_markers = {"submitted", "approved", "billed", "written_off", "todo", "in_progress"}
    header_pollution = {"closed", "on_hold"}
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        leaf = mid.replace("x_", "")
        if not (
            leaf.endswith("_line")
            or "line" in leaf
            or leaf.endswith("_time")
            or "time_entry" in leaf
        ):
            continue
        for f in m.get("fields") or []:
            if not isinstance(f, dict) or f.get("name") != "x_status":
                continue
            sel = str(f.get("selection") or "")
            keys = set(re.findall(r"\(\s*'([^']+)'\s*,", sel))
            if not (keys & line_markers) or not (keys & header_pollution):
                continue
            # Drop polluted pairs from selection string
            new_sel = sel
            for bad in header_pollution:
                new_sel = re.sub(
                    rf",?\s*\(\s*'{bad}'\s*,\s*'[^']*'\s*\)",
                    "",
                    new_sel,
                )
            new_sel = re.sub(r"\[\s*,", "[", new_sel)
            new_sel = re.sub(r",\s*\]", "]", new_sel)
            if new_sel != sel:
                f["selection"] = new_sel
                notes.append(f"quality: scrubbed header statuses off {mid}.x_status")
    return notes


def collapse_parallel_party_models(draft: dict[str, Any]) -> list[str]:
    """Prefer x_matter_party / x_*_party over bare x_party when both exist."""
    notes: list[str] = []
    by_id = {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    if "x_party" not in by_id:
        return notes
    keep = next(
        (
            mid
            for mid in by_id
            if mid != "x_party" and mid.endswith("_party")
        ),
        None,
    )
    if not keep:
        return notes
    # Remap relations x_party → keep, drop x_party
    for m in by_id.values():
        for f in m.get("fields") or []:
            if isinstance(f, dict) and f.get("relation") == "x_party":
                f["relation"] = keep
    draft["models"] = [m for m in draft["models"] if m.get("model") != "x_party"]
    for key in ("actions", "views", "access_rules", "smart_buttons", "automations"):
        rows = draft.get(key)
        if not isinstance(rows, list):
            continue
        if key == "smart_buttons":
            draft[key] = [
                b
                for b in rows
                if not (
                    isinstance(b, dict)
                    and (
                        b.get("on_model") == "x_party"
                        or b.get("related_model") == "x_party"
                    )
                )
            ]
            continue
        if key == "automations":
            for a in rows:
                if isinstance(a, dict) and a.get("model") == "x_party":
                    a["model"] = keep
            continue
        draft[key] = [
            r
            for r in rows
            if not (
                isinstance(r, dict)
                and (
                    r.get("model") == "x_party"
                    or str(r.get("model") or "").replace("model_", "", 1) == "x_party"
                )
            )
        ]
    notes.append(f"quality: collapsed x_party → {keep}")
    return notes


def remap_staff_fks_from_users(draft: dict[str, Any]) -> list[str]:
    """When a domain staff model exists, fee-earner FKs should not point at res.users."""
    from app.ai_depth import _staff_model_id, _primary_transaction_model

    notes: list[str] = []
    parent = _primary_transaction_model(draft)
    parent_id = str(parent["model"]) if parent else ""
    staff_id = _staff_model_id(draft, parent_id)
    if not staff_id:
        return notes
    staff_hints = (
        "attorney",
        "counsel",
        "doctor",
        "nurse",
        "staff",
        "practitioner",
        "technician",
        "teacher",
        "responsible",
        "fee_earner",
        "appearing",
    )
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        for f in m.get("fields") or []:
            if not isinstance(f, dict) or f.get("ttype") != "many2one":
                continue
            if str(f.get("relation") or "") != "res.users":
                continue
            fname = str(f.get("name") or "").lower()
            label = str(f.get("string") or "").lower()
            # Generic assignee/user login stays on res.users
            if fname in {"x_assignee_id", "x_user_id", "assignee_id", "user_id"}:
                continue
            if label.strip() in {"assignee", "assigned user", "login user", "user"}:
                continue
            if any(h in fname or h in label for h in staff_hints):
                f["relation"] = staff_id
                notes.append(
                    f"quality: remapped {mid}.{f.get('name')} "
                    f"res.users → {staff_id}"
                )
    return notes


def is_embedded_line_model(model: dict[str, Any] | str) -> bool:
    """Nested document line (sale.order.line): scalar row, not a header.

    Billing ``x_status`` stays a column. No statusbar, chatter, kanban, or Confirm.
    """
    if isinstance(model, dict):
        mid = str(model.get("model") or "")
    else:
        mid = str(model or "")
    return mid.endswith("_line")


def is_party_link_model(model: dict[str, Any]) -> bool:
    """Party/role-link models are relational join rows, not header workflows."""
    if not isinstance(model, dict):
        return False
    mid = str(model.get("model") or "")
    leaf = mid.replace("x_", "")
    desc = str(model.get("description") or "").lower()
    return any(
        k in leaf or k in desc
        for k in ("party", "role_link", "participant", "stakeholder")
    )


def demote_spurious_link_workflows(draft: dict[str, Any]) -> list[str]:
    """Party/role-link models are not workflows — drop is_workflow + generic status."""
    notes: list[str] = []
    generic_status = {
        "draft",
        "open",
        "done",
        "cancelled",
    }
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        if not is_party_link_model(m):
            continue
        mid = str(m.get("model") or "")
        status = next(
            (
                f
                for f in (m.get("fields") or [])
                if isinstance(f, dict) and f.get("name") == "x_status"
            ),
            None,
        )
        keys = set(
            re.findall(r"\(\s*'([^']+)'\s*,", str((status or {}).get("selection") or ""))
        )
        # Domain-specific status (pending/cleared/…) → keep workflow; generic → demote
        if keys and not (keys <= generic_status):
            continue
        changed = False
        if m.get("is_workflow"):
            m["is_workflow"] = False
            changed = True
        if isinstance(m.get("state_field"), dict):
            m.pop("state_field", None)
            changed = True
        if status is not None:
            m["fields"] = [
                f
                for f in (m.get("fields") or [])
                if not (isinstance(f, dict) and f.get("name") == "x_status")
            ]
            changed = True
        if not changed:
            continue
        notes.append(f"quality: demoted link model {mid} from is_workflow")
        views = draft.get("views")
        if isinstance(views, list):
            draft["views"] = [
                v
                for v in views
                if not (
                    isinstance(v, dict)
                    and v.get("model") == mid
                    and v.get("type") == "kanban"
                )
            ]
        for a in draft.get("actions") or []:
            if isinstance(a, dict) and a.get("model") == mid:
                mode = str(a.get("view_mode") or "list,form")
                a["view_mode"] = ",".join(
                    p for p in mode.split(",") if p.strip() != "kanban"
                ) or "list,form"
    return notes


def scrub_automation_filter_domains(draft: dict[str, Any]) -> list[str]:
    """Drop or fix filter_domain status keys that are not on the model selection."""
    notes: list[str] = []
    by_id = {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return notes
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        domain = auto.get("filter_domain")
        if not isinstance(domain, str) or "x_status" not in domain:
            continue
        mid = str(auto.get("model") or "")
        model = by_id.get(mid)
        if not model:
            continue
        status = next(
            (
                f
                for f in (model.get("fields") or [])
                if isinstance(f, dict) and f.get("name") == "x_status"
            ),
            None,
        )
        if not status:
            continue
        keys = set(
            re.findall(r"\(\s*'([^']+)'\s*,", str(status.get("selection") or ""))
        )
        if not keys:
            continue
        list_vals = re.findall(
            r"\('x_status'\s*,\s*'not in'\s*,\s*\[([^\]]*)\]\)", domain
        )
        if not list_vals:
            list_vals = re.findall(
                r"x_status['\"]?\s*,\s*'not in'\s*,\s*\[([^\]]*)\]", domain
            )
        bad_in_list: set[str] = set()
        for chunk in list_vals:
            bad_in_list |= set(re.findall(r"'([^']+)'", chunk))
        invalid = {v for v in bad_in_list if v not in keys}
        if not invalid:
            continue
        new_domain = domain
        for inv in invalid:
            replacement = None
            if inv == "closed" and "done" in keys:
                replacement = "done"
            elif inv == "closed":
                replacement = next(
                    (k for k in ("cancelled", "void", "paid") if k in keys), None
                )
            if replacement:
                new_domain = new_domain.replace(f"'{inv}'", f"'{replacement}'")
                notes.append(
                    f"quality: fixed automation domain {auto.get('name')} "
                    f"{inv}→{replacement}"
                )
            else:
                new_domain = re.sub(rf",?\s*'{re.escape(inv)}'\s*", "", new_domain)
                notes.append(
                    f"quality: removed invalid status {inv!r} from "
                    f"automation {auto.get('name')}"
                )
        auto["filter_domain"] = new_domain
        # Empty not-in list is meaningless — drop the filter
        if re.search(r"'not in'\s*,\s*\[\s*\]", new_domain):
            auto["filter_domain"] = None
            notes.append(
                f"quality: cleared empty filter_domain on automation {auto.get('name')}"
            )
    return notes


def ensure_required_on_name_fields(draft: dict[str, Any]) -> list[str]:
    """x_name should be required on new x_* models — never on stock inherits."""
    notes: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        mode = str(m.get("mode") or "new")
        if mode == "inherit" and not mid.startswith("x_"):
            continue
        for f in m.get("fields") or []:
            if (
                isinstance(f, dict)
                and f.get("name") == "x_name"
                and f.get("ttype") == "char"
                and not f.get("required")
            ):
                f["required"] = True
                notes.append(f"quality: required x_name on {m.get('model')}")
    return notes


def ensure_min_workflows(draft: dict[str, Any], ambition: str) -> list[str]:
    """Promote substantive models to workflows when comprehensive floor not met."""
    from app.ai_depth import AMBITION_TARGETS, compute_depth_metrics

    notes: list[str] = []
    if ambition not in AMBITION_TARGETS:
        return notes
    need = int(AMBITION_TARGETS[ambition]["min_workflows"])  # type: ignore[index]
    metrics = compute_depth_metrics(draft)
    if metrics["workflow_count"] >= need:
        return notes
    candidates = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict) or m.get("is_workflow"):
            continue
        mid = str(m.get("model") or "")
        leaf = mid.replace("x_", "")
        # Never promote party/role-link models into workflows
        if is_party_link_model(m):
            continue
        from app.ai_odoo_app_bar import looks_like_register

        if looks_like_register(mid):
            continue
        names = {
            str(f.get("name") or "")
            for f in (m.get("fields") or [])
            if isinstance(f, dict)
        }
        if "x_status" in names:
            candidates.append(m)
            continue
        # Prefer event/task/document/line models
        if any(k in mid for k in ("event", "task", "hearing", "document", "time", "line")):
            candidates.append(m)
    for m in candidates:
        if metrics["workflow_count"] >= need:
            break
        fields = list(m.get("fields") or [])
        names = {str(f.get("name") or "") for f in fields if isinstance(f, dict)}
        if "x_status" not in names:
            fields.append(
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Status",
                    "selection": (
                        "[('draft','Draft'),('open','Open'),('done','Done'),"
                        "('cancelled','Cancelled')]"
                    ),
                    "required": True,
                }
            )
            m["fields"] = fields
        m["is_workflow"] = True
        notes.append(f"quality: promoted {m.get('model')} to workflow")
        metrics = compute_depth_metrics(draft)
    return notes


def normalize_selection_field_shapes(draft: dict[str, Any]) -> list[str]:
    """Convert selection_values lists into Odoo-style selection strings; dedupe keys."""
    from app.ai_selection import normalize_selection_field

    notes: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "?")
        for f in m.get("fields") or []:
            if not isinstance(f, dict) or f.get("ttype") != "selection":
                continue
            fname = str(f.get("name") or "?")
            notes.extend(
                normalize_selection_field(f, context=f"{mid}.{fname}")
            )
    return notes


def collapse_duplicate_role_models(draft: dict[str, Any]) -> list[str]:
    """Merge near-duplicate ops models (e.g. x_hearing + x_event) into one."""
    notes: list[str] = []
    clusters = (
        ("hearing", "event", "appointment"),
    )
    models = [m for m in (draft.get("models") or []) if isinstance(m, dict) and m.get("model")]
    by_id = {str(m["model"]): m for m in models}
    drop_map: dict[str, str] = {}
    for cluster in clusters:
        members: list[str] = []
        for mid in by_id:
            leaf = mid.replace("x_", "")
            if leaf.endswith("_registration") or leaf.endswith("_line") or leaf.endswith("_attendee"):
                continue
            if any(k in leaf for k in cluster):
                members.append(mid)
        if len(members) < 2:
            continue
        members.sort(
            key=lambda mid: (
                -len([f for f in (by_id[mid].get("fields") or []) if isinstance(f, dict)]),
                mid,
            )
        )
        keep = members[0]
        for doomed in members[1:]:
            drop_map[doomed] = keep
    if not drop_map:
        return notes
    draft["models"] = [m for m in models if str(m.get("model")) not in drop_map]
    for m in draft["models"]:
        fields = []
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                fields.append(f)
                continue
            rel = str(f.get("relation") or "")
            if rel in drop_map:
                fields.append({**f, "relation": drop_map[rel]})
            else:
                fields.append(f)
        m["fields"] = fields
    for doomed, keep in drop_map.items():
        notes.append(f"quality: merged duplicate role {doomed} → {keep}")
    # Drop UI / buttons for removed models
    for key in ("actions", "views", "access_rules"):
        rows = draft.get(key)
        if not isinstance(rows, list):
            continue
        draft[key] = [
            r
            for r in rows
            if not (
                isinstance(r, dict)
                and (
                    r.get("model") in drop_map
                    or (
                        key == "access_rules"
                        and str(r.get("model") or "").replace("model_", "", 1) in drop_map
                    )
                )
            )
        ]
    buttons = draft.get("smart_buttons")
    if isinstance(buttons, list):
        draft["smart_buttons"] = [
            b
            for b in buttons
            if isinstance(b, dict)
            and b.get("on_model") not in drop_map
            and b.get("related_model") not in drop_map
        ]
    autos = draft.get("automations")
    if isinstance(autos, list):
        remapped_autos: list[dict[str, Any]] = []
        for a in autos:
            if not isinstance(a, dict):
                continue
            mid = str(a.get("model") or "")
            if mid in drop_map:
                remapped_autos.append({**a, "model": drop_map[mid]})
                notes.append(
                    f"quality: remapped automation {a.get('name')} "
                    f"{mid} → {drop_map[mid]}"
                )
            else:
                remapped_autos.append(a)
        draft["automations"] = remapped_autos
    return notes


def strip_partner_on_child_lines(draft: dict[str, Any]) -> list[str]:
    """Remove redundant x_partner_id on *_line models that already parent to a header."""
    notes: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        leaf = mid.replace("x_", "")
        if not (leaf.endswith("_line") or leaf.endswith("line")):
            continue
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        has_parent = any(
            f.get("ttype") == "many2one"
            and str(f.get("relation") or "").startswith("x_")
            and str(f.get("name") or "").endswith("_id")
            and f.get("name") != "x_partner_id"
            for f in fields
        )
        if not has_parent:
            continue
        kept = [f for f in fields if f.get("name") != "x_partner_id"]
        if len(kept) < len(fields):
            m["fields"] = kept
            notes.append(f"quality: stripped x_partner_id from child line {mid}")
    return notes


def strip_internal_scaffold(draft: dict[str, Any]) -> list[str]:
    """Remove teaching blobs that must never ship in API responses."""
    notes: list[str] = []
    if "json" in draft:
        draft.pop("json", None)
        notes.append("quality: stripped internal json scaffold from draft")
    return notes


def enforce_on_write_filter_domains(draft: dict[str, Any]) -> list[str]:
    """Drop on_write automations that fire on every write (missing filter_domain)."""
    notes: list[str] = []
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return notes
    exempt_sources = {"depth_seed", "rules_engine", "quality_normalize"}
    kept: list[dict[str, Any]] = []
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        trigger = str(auto.get("trigger") or "")
        domain = auto.get("filter_domain")
        source = str(auto.get("source") or "")
        if trigger == "on_write" and not (
            isinstance(domain, str) and domain.strip()
        ):
            if source in exempt_sources:
                kept.append(auto)
                continue
            notes.append(
                f"quality: dropped automation without filter_domain: {auto.get('name')!r}"
            )
            continue
        kept.append(auto)
    draft["automations"] = kept
    return notes


def repair_draft_integrity(draft: dict[str, Any], *, ambition: str = "standard") -> list[str]:
    """Deterministic integrity + shape repairs after LLM generation."""
    notes: list[str] = []
    notes.extend(strip_internal_scaffold(draft))
    notes.extend(strip_invalid_relational_keys(draft))
    notes.extend(repair_company_fk_targets(draft))
    notes.extend(dedupe_fields_by_name(draft))
    notes.extend(gate_llm_field_quality(draft))
    notes.extend(normalize_selection_field_shapes(draft))
    notes.extend(fill_empty_selection_fields(draft))
    notes.extend(scrub_placeholder_selections(draft))
    notes.extend(repair_incomplete_relational_fields(draft))
    notes.extend(repair_orphan_relations(draft))
    notes.extend(drop_redundant_role_name_fields(draft))
    notes.extend(dedupe_redundant_partner_fields(draft))
    notes.extend(collapse_duplicate_role_models(draft))
    notes.extend(collapse_parallel_party_models(draft))
    notes.extend(collapse_thin_padding_models(draft))
    notes.extend(strip_partner_on_child_lines(draft))
    notes.extend(deepen_thin_rate_models(draft))
    notes.extend(deepen_thin_ops_children(draft))
    notes.extend(ensure_line_bill_link(draft))
    notes.extend(ensure_parent_o2ms_for_children(draft))
    notes.extend(remap_staff_fks_from_users(draft))
    notes.extend(demote_spurious_link_workflows(draft))
    notes.extend(ensure_terminal_workflow_statuses(draft))
    notes.extend(scrub_polluted_line_statuses(draft))
    notes.extend(ensure_required_on_name_fields(draft))
    notes.extend(scrub_exemplar_help_text(draft))
    notes.extend(normalize_smart_button_shapes(draft))
    notes.extend(normalize_automation_shapes(draft))
    notes.extend(scrub_invalid_related_writes(draft))
    notes.extend(scrub_automation_filter_domains(draft))
    notes.extend(dedupe_automation_safe_actions(draft))
    notes.extend(enforce_on_write_filter_domains(draft))
    notes.extend(dedupe_redundant_automations(draft))
    notes.extend(cap_partner_smart_buttons(draft))
    notes.extend(ensure_min_workflows(draft, ambition))
    from app.ai_workflow import ensure_workflow_transitions_on_draft

    notes.extend(ensure_workflow_transitions_on_draft(draft))
    from app.ai_workflow_semantic import apply_semantic_workflow_pass

    notes.extend(apply_semantic_workflow_pass(draft))
    try:
        from app.ai_domain_packs import match_domain_pack

        pack_id = str(draft.get("domain_pack") or "")
        pack = match_domain_pack(str(draft.get("_user_prompt") or ""))
        pack_body = pack[1] if pack else None
        from app.ai_vocab_scrub import scrub_draft_vocabulary

        notes.extend(scrub_draft_vocabulary(draft, pack=pack_body))
    except Exception:  # noqa: BLE001
        pass
    from app.ai_presentation import (
        dedupe_smart_button_labels,
        group_menus_if_needed,
        suggest_line_total_compute,
    )

    notes.extend(group_menus_if_needed(draft))
    notes.extend(dedupe_smart_button_labels(draft))
    notes.extend(suggest_line_total_compute(draft))
    # Re-demote after promote pass so party links never stay workflows
    notes.extend(demote_spurious_link_workflows(draft))
    notes.extend(purge_ghost_ui(draft))
    notes.extend(refresh_forms_missing_relational_fields(draft))
    prompt = str(draft.get("_user_prompt") or "")
    if prompt.strip() and not str(draft.get("domain_pack") or ""):
        from app.ai_domain_nouns import expand_uncovered_noun_models

        reuse = []
        if isinstance(draft.get("reuse"), dict):
            reuse = list(draft["reuse"].get("models") or [])
        notes.extend(
            expand_uncovered_noun_models(draft, prompt, reuse_models=reuse)
        )
    return notes


def run_model_quality_pass(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    ambition: str = "standard",
    provider: Any | None = None,
    expand_llm: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """Collapse hollow catalogs, deepen fields, repair orphans/shapes/ghost UI."""
    out = copy.deepcopy(draft)
    notes: list[str] = []
    notes.extend(collapse_hollow_catalogs_to_selections(out))
    notes.extend(repair_draft_integrity(out, ambition=ambition))
    min_f = min_fields_for_ambition(ambition)
    if expand_llm and provider is not None:
        out, deepen_notes = llm_deepen_model_fields(
            provider,
            out,
            user_prompt=user_prompt,
            ambition=ambition,
            min_fields=min_f,
        )
        notes.extend(deepen_notes)
        notes.extend(collapse_hollow_catalogs_to_selections(out))
        notes.extend(repair_draft_integrity(out, ambition=ambition))
    return out, notes


__all__ = [
    "MODEL_CREATION_RULES",
    "few_shot_exemplar_json",
    "min_fields_for_ambition",
    "collapse_hollow_catalogs_to_selections",
    "llm_deepen_model_fields",
    "llm_emit_missing_scaffold_models",
    "seed_missing_core_scaffold_models",
    "run_model_quality_pass",
    "repair_draft_integrity",
    "is_embedded_line_model",
    "is_party_link_model",
    "demote_spurious_link_workflows",
    "repair_orphan_relations",
    "normalize_smart_button_shapes",
    "purge_ghost_ui",
    "dedupe_fields_by_name",
    "repair_incomplete_relational_fields",
    "filter_redundant_missing_models",
    "collapse_thin_padding_models",
]
