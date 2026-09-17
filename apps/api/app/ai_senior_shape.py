"""Senior Community implementation bar — every grain, not only packed full apps.

Stitch analog: the operator describes a field pack, a feature under a stock app,
or a full residual workspace. This module finishes the draft the way a senior
Odoo team would: inherit the host, real fields, an extension view, a date
activity when there is a date, a companion document only when the brief asks
for a register/checklist — never a parallel invoice/employee/event.
"""

from __future__ import annotations

import re
from typing import Any

from app.ai_grain import Grain

_CLONE_LEAVES = frozenset(
    {
        "bill",
        "invoice",
        "attorney",
        "lawyer",
        "task",
        "event",
        "payment",
        "deposit",
        "client",
        "customer",
    }
)
_COMPANION_RE = re.compile(
    r"\b(checklist|register|log|line\s+items?|cases?|matters?)\b",
    re.I,
)
_DATE_RE = re.compile(r"\b(due|expir|deadline|start|end|date)\b", re.I)
_STATUS_RE = re.compile(r"\b(status|state|stage|lifecycle)\b", re.I)
_AMOUNT_RE = re.compile(r"\b(amount|fee|rate|value)\b", re.I)
_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "my",
        "our",
        "to",
        "on",
        "for",
        "with",
        "and",
        "of",
        "add",
        "attach",
        "extend",
        "plug",
        "into",
        "field",
        "fields",
        "tracker",
        "tracking",
        "component",
        "app",
        "system",
        "sale",
        "sales",
        "order",
        "orders",
        "invoice",
        "invoices",
        "task",
        "tasks",
        "project",
        "contact",
        "contacts",
        "partner",
        "customer",
        "employee",
        "calendar",
        "lead",
        "just",
        "single",
        "please",
        "need",
        "want",
        "only",
        "show",
        "it",
        "this",
        "that",
        "them",
        "required",
        "before",
        "confirm",
        "do",
        "not",
        "form",
        "already",
        "use",
        "existing",
        "extra",
        "extras",
        "should",
        "must",
        "will",
        "people",
        "vendor",
        "customer",
        "bills",
        "bill",
        "checkbox",
        "boolean",
        "text",
        "group",
        "under",
        "create",
        "new",
        "home",
        "screen",
        "res",  # never invent x_res from (res.partner)
        "account",
        "move",
        "stock",
        "picking",
        "purchase",
        "hr",
        "crm",
        "product",
        "template",
    }
)


def _models(draft: dict[str, Any]) -> list[dict[str, Any]]:
    return [m for m in (draft.get("models") or []) if isinstance(m, dict) and m.get("model")]


def _inherit_row(draft: dict[str, Any]) -> dict[str, Any] | None:
    for model in _models(draft):
        if str(model.get("mode") or "new") == "inherit" and not str(model.get("model")).startswith("x_"):
            return model
    return None


def _field_names(model: dict[str, Any]) -> set[str]:
    return {
        str(f.get("name"))
        for f in (model.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }


def _slug(text: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return raw[:40] or "custom"


_CHECKBOX_BRIEF_RE = re.compile(
    r"(?i)\bcheckbox\s+[\"']?([^\"',.;]+?)[\"']?"
    r"(?=\s+and\b|\s+under\b|\s+on\b|,|\.|$)"
)
_TYPED_TEXT_BRIEF_RE = re.compile(
    r"(?i)(?:\badd\b|\band\b|,)\s+(?:(?:a|an|the)\s+)?"
    r"([A-Za-z][\w /&-]{1,40}?)\s+text(?:\s+field)?\b"
)
_TECH_MODEL_PAREN_RE = re.compile(r"\(\s*[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\s*\)", re.I)
_STUDIO_PREFIX_RE = re.compile(r"^x_studio_", re.I)


def _human_field_label(label: str) -> str:
    from app.ai_field_ir import human_field_label

    return human_field_label(label)


def _ingenium_field_name(label: str, *, ttype: str) -> str:
    """Prefer x_* Ingenium names — never x_studio_*."""
    slug = _slug(label)
    if slug.startswith("studio_"):
        slug = slug[len("studio_") :]
    if not slug or slug in {"custom", "it", "res", "checkbox"}:
        slug = "flag" if ttype == "boolean" else "notes" if ttype == "text" else "value"
    name = f"x_{slug}"[:40]
    return _STUDIO_PREFIX_RE.sub("x_", name)


def _typed_fields_from_brief(prompt: str) -> list[dict[str, Any]]:
    """Parse checkbox / text asks from a clear brief (Contacts S1 shape)."""
    text = _TECH_MODEL_PAREN_RE.sub(" ", prompt or "")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for match in _CHECKBOX_BRIEF_RE.finditer(text):
        label = _human_field_label(match.group(1))
        if not label:
            continue
        name = _ingenium_field_name(label, ttype="boolean")
        if name in seen:
            continue
        seen.add(name)
        out.append({"name": name, "ttype": "boolean", "string": label})

    for match in _TYPED_TEXT_BRIEF_RE.finditer(text):
        label = _human_field_label(match.group(1))
        if not label:
            continue
        low = label.lower()
        if low.startswith("checkbox"):
            continue
        name = _ingenium_field_name(label, ttype="text")
        if name in seen:
            continue
        seen.add(name)
        out.append({"name": name, "ttype": "text", "string": label})

    return out


def infer_extension_fields(prompt: str, *, pad: bool = True) -> list[dict[str, Any]]:
    """Deterministic inherit fields from NL — never a lone x_extension_note stub.

    ``pad=False`` for field packs: do not invent Notes / Active / Reference.
    """
    from app.ai_capability_gaps import (
        CAPABILITY_NOISE_NOUNS,
        assess_capability_gaps,
        stub_fields_for_gaps,
    )

    text = prompt or ""
    low = text.lower()
    single_field = bool(
        re.search(
            r"\b(?:a\s+)?(?:single|one)\s+(?:extra\s+)?field\b|"
            r"\bjust\s+(?:inherit|one\s+field)\b",
            low,
        )
    )
    assessment = assess_capability_gaps(text)
    # Primary PDF/QR/pay asks: honest stubs only — never x_dynamic / notes padding.
    if assessment.primary_option_a:
        return stub_fields_for_gaps(assessment)[:12]

    # Clear typed briefs / Must-do constraints win over head-noun heuristics.
    from app.ai_field_ir import extract_field_ir

    typed = extract_field_ir(text)
    if typed:
        return typed[:12]

    fields: list[dict[str, Any]] = []

    if "warranty" in low:
        fields.extend(
            [
                {"name": "x_warranty_start", "ttype": "date", "string": "Warranty Start"},
                {"name": "x_warranty_end", "ttype": "date", "string": "Warranty End"},
                {
                    "name": "x_warranty_status",
                    "ttype": "selection",
                    "string": "Warranty Status",
                    "selection": "[('active','Active'),('expired','Expired'),('void','Void')]",
                },
            ]
        )
    if "inspection" in low or "checklist" in low:
        fields.extend(
            [
                {
                    "name": "x_inspection_state",
                    "ttype": "selection",
                    "string": "Inspection",
                    "selection": "[('todo','To Do'),('pass','Pass'),('fail','Fail')]",
                },
                {"name": "x_inspection_due", "ttype": "date", "string": "Inspection Due"},
            ]
        )
    if "compliance" in low or "expiry" in low or "expir" in low:
        fields.extend(
            [
                {
                    "name": "x_compliance_status",
                    "ttype": "selection",
                    "string": "Compliance Status",
                    "selection": "[('ok','OK'),('review','Review'),('blocked','Blocked')]",
                },
                {"name": "x_compliance_expiry", "ttype": "date", "string": "Expiry Date"},
            ]
        )
    if re.search(r"\bsla\b", low):
        datetime_ask = bool(
            re.search(r"date\s+and\s+time|\bdatetime\b|due\s+date\s+and\s+time", low)
        )
        fields.append(
            {
                "name": "x_sla_due",
                "ttype": "datetime" if datetime_ask else "date",
                "string": "SLA Due Date" if datetime_ask else "SLA due date",
            }
        )
        if not single_field:
            fields.extend(
                [
                    {
                        "name": "x_sla_status",
                        "ttype": "selection",
                        "string": "SLA status",
                        "selection": (
                            "[('on_track','On track'),('at_risk','At risk'),"
                            "('breached','Breached')]"
                        ),
                        "default": "on_track",
                    },
                    {"name": "x_sla_hours", "ttype": "float", "string": "SLA hours"},
                ]
            )

    names = _names(fields)
    if not fields:
        named = _named_field_from_add(text)
        if named:
            fields.append(named)
            names.add(str(named["name"]))
        else:
            head = _head_noun(low)
            from app.ai_field_ir import is_banned_slug

            if head and not is_banned_slug(head) and head not in CAPABILITY_NOISE_NOUNS:
                fields.append(
                    {
                        "name": f"x_{head}",
                        "ttype": "char",
                        "string": head.replace("_", " ").title(),
                    }
                )
                names.add(f"x_{head}")
            elif re.search(r"\bfields?\b", low):
                # Bare "add a field" — honest generic column, not mechanism junk.
                fields.append(
                    {
                        "name": "x_extra_info",
                        "ttype": "char",
                        "string": "Extra info",
                    }
                )
                names.add("x_extra_info")
    if _DATE_RE.search(low) and not any(
        f.get("ttype") in ("date", "datetime") for f in fields
    ):
        fields.append({"name": "x_due_date", "ttype": "date", "string": "Due date"})
        names.add("x_due_date")
    if not single_field and _STATUS_RE.search(low) and "x_status" not in names and not any(
        "status" in str(f.get("name") or "") for f in fields
    ):
        fields.append(
            {
                "name": "x_status",
                "ttype": "selection",
                "string": "Status",
                "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                "default": "draft",
            }
        )
        names.add("x_status")
    if not single_field and _AMOUNT_RE.search(low) and "x_amount" not in names:
        fields.append({"name": "x_amount", "ttype": "float", "string": "Amount"})
        names.add("x_amount")
    if (
        not single_field
        and re.search(r"\b(assigned|owner|responsible|fee\s*earner)\b", low)
        and "x_employee_id" not in names
    ):
        fields.append(
            {
                "name": "x_employee_id",
                "ttype": "many2one",
                "relation": "hr.employee",
                "string": "Responsible",
            }
        )
        names.add("x_employee_id")

    head = _head_noun(low)
    from app.ai_field_ir import is_banned_slug, typed_fields_from_brief

    if (
        not single_field
        and head
        and not is_banned_slug(head)
        and head not in CAPABILITY_NOISE_NOUNS
        and f"x_{head}" not in names
        and not any(head in str(f.get("name") or "") for f in fields)
        and not typed_fields_from_brief(text)
    ):
        fields.insert(
            0,
            {
                "name": f"x_{head}",
                "ttype": "char",
                "string": head.replace("_", " ").title(),
            },
        )
        names.add(f"x_{head}")

    # Only pad when we already have a real inferred field (not capability chrome).
    # A "single extra field" ask must stay one column — do not invent notes/active.
    # Field packs pass pad=False so Vendor TIN is not dumped next to Active.
    if pad and fields and not assessment.gaps and not single_field:
        if "x_notes" not in names and len(fields) < 3:
            fields.append({"name": "x_notes", "ttype": "text", "string": "Notes"})
            names.add("x_notes")
        if len(fields) < 3 and "x_active" not in names:
            fields.append(
                {"name": "x_active", "ttype": "boolean", "string": "Active", "default": True}
            )
            names.add("x_active")
        if len(fields) < 3 and "x_ref" not in names:
            fields.append({"name": "x_ref", "ttype": "char", "string": "Reference"})
    # Mixed ask (SLA + QR): append honest stubs without padding junk.
    for stub in stub_fields_for_gaps(assessment):
        name = str(stub.get("name") or "")
        if name and name not in names:
            fields.append(dict(stub))
            names.add(name)
    return fields[:12]


def _names(fields: list[dict[str, Any]]) -> set[str]:
    return {str(f.get("name")) for f in fields if isinstance(f, dict) and f.get("name")}


def _named_field_from_add(text: str) -> dict[str, Any] | None:
    """Prefer ‘add Vendor TIN’ over the first leftover adverb (only/show)."""
    match = re.search(
        r"\badd(?:\s+a|\s+an|\s+the)?\s+"
        r"([A-Za-z][A-Za-z0-9]*(?:\s+[A-Za-z][A-Za-z0-9]*)*?)"
        r"(?:\s+field|\s+column)?(?=\s+on\b|\s+to\b|[.,;:]|$)",
        text or "",
        re.I,
    )
    if not match:
        return None
    tokens = [
        tok
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9]*", match.group(1))
        if tok.lower() not in _STOP
    ]
    if not tokens:
        return None
    label = " ".join(tokens)
    low_label = label.lower()
    if low_label.startswith("checkbox"):
        label = _human_field_label(re.sub(r"(?i)^checkbox\s+", "", label))
        if not label:
            return None
        return {
            "name": _ingenium_field_name(label, ttype="boolean"),
            "ttype": "boolean",
            "string": label,
        }
    # Drop technical host leftovers (Res from res.partner) and studio prefixes.
    if low_label in {"res", "partner", "checkbox"} or low_label.startswith("studio"):
        return None
    slug = _slug(label)
    if not slug or slug in {"custom", "it", "res"}:
        return None
    return {
        "name": _ingenium_field_name(label, ttype="char"),
        "ttype": "char",
        "string": label if any(ch.isupper() for ch in label) else label.title(),
    }


def _head_noun(low: str) -> str:
    from app.ai_capability_gaps import CAPABILITY_NOISE_NOUNS

    cleaned = _TECH_MODEL_PAREN_RE.sub(" ", low or "")
    cleaned = re.sub(r"\b[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]+)+\b", " ", cleaned)
    cleaned = re.sub(
        r"\b(sale orders?|sales orders?|invoices?|vendor bills?|project tasks?|"
        r"contacts?|partners?|employees?|calendar|leads?)\b",
        " ",
        cleaned,
    )
    tokens = [t for t in re.findall(r"[a-z][a-z0-9]+", cleaned) if t not in _STOP]
    skip_tail = {
        "date",
        "status",
        "state",
        "amount",
        "due",
        "field",
        "column",
        *CAPABILITY_NOISE_NOUNS,
    }
    meaningful = [t for t in tokens if t not in skip_tail]
    if not meaningful:
        return ""
    return _slug(meaningful[0])



_OPS_PICKING_RE = re.compile(
    r"(?i)\b(?:pickings?|transfers?|delivery\s*/\s*inventory|inventory\s+lists?)\b"
)
_OPS_FILTER_RE = re.compile(r"(?i)\b(?:filter|domain)\b")
_OPS_AUTO_RE = re.compile(
    r"(?i)\b(?:automation|automat(?:e|ed|ion)|when\s+the\s+box\s+is\s+checked)\b"
)
_PREFER_FIELD_RE = re.compile(r"(?i)prefer|preferred")


def _prefer_boolean_field(inherit: dict[str, Any]) -> dict[str, Any] | None:
    for field in inherit.get("fields") or []:
        if not isinstance(field, dict):
            continue
        if str(field.get("ttype") or field.get("type") or "") != "boolean":
            continue
        blob = f"{field.get('name') or ''} {field.get('string') or ''}"
        if _PREFER_FIELD_RE.search(blob) and re.search(r"(?i)deliver", blob):
            return field
    return None


def _ensure_inherit_ops_wiring(draft: dict[str, Any], prompt: str) -> list[str]:
    """Author pickings filter + light automation for inherit-only ops field_packs.

    field_pack skips feature_slice smart-button/companion wiring; ops briefs still
    need Delivery/Inventory list filters and a safe on_write activity when Prefer
    for delivery is checked. Search filter inherits stock.picking; automation stays
    on res.partner (public ORM only).
    """
    notes: list[str] = []
    from app.ai_grain import is_inherit_only_ops

    if not is_inherit_only_ops(prompt or ""):
        return notes
    # S1-style "add fields, no new app" is inherit-only but not ops — require
    # pickings/filter/automation themes before authoring workflow surfaces.
    if not (
        _OPS_PICKING_RE.search(prompt or "")
        or _OPS_FILTER_RE.search(prompt or "")
        or _OPS_AUTO_RE.search(prompt or "")
    ):
        return notes
    inherit = _inherit_row(draft)
    if inherit is None:
        return notes
    host = str(inherit.get("model") or "")
    if host != "res.partner":
        return notes
    prefer = _prefer_boolean_field(inherit)
    if prefer is None:
        return notes
    fname = str(prefer.get("name") or "")
    if not fname:
        return notes

    want_filter = bool(
        _OPS_PICKING_RE.search(prompt or "") or _OPS_FILTER_RE.search(prompt or "")
    )
    want_auto = bool(
        _OPS_AUTO_RE.search(prompt or "") or _OPS_PICKING_RE.search(prompt or "")
    )
    # At least one theme matched; author every surface the brief named, and
    # always include the light automation when pickings/filter are in play.
    if want_filter and not want_auto:
        want_auto = True

    if want_filter:
        views = [v for v in (draft.get("views") or []) if isinstance(v, dict)]
        already = any(
            str(v.get("model") or "") == "stock.picking"
            and str(v.get("type") or "") == "search"
            and "preferred" in str(v.get("arch") or "").lower()
            for v in views
        )
        if not already:
            arch = (
                "<data>\n"
                '  <xpath expr="//search" position="inside">\n'
                f'    <filter string="Preferred delivery contact" '
                f'name="ingenium_preferred_delivery_partner" '
                f"domain=\"[('partner_id.{fname}', '=', True)]\"/>\n"
                "  </xpath>\n"
                "</data>"
            )
            draft.setdefault("views", []).append(
                {
                    "name": "stock.picking.search.preferred_delivery",
                    "model": "stock.picking",
                    "type": "search",
                    "mode": "extension",
                    "inherit_xml_id": "stock.view_picking_internal_search",
                    "arch": arch,
                    "source": "senior_ops",
                }
            )
            deps = list(draft.get("depends") or [])
            if "stock" not in deps:
                deps.append("stock")
                draft["depends"] = deps
            notes.append(
                "senior: stock.picking search filter for preferred delivery contacts"
            )

    if want_auto:
        autos = [a for a in (draft.get("automations") or []) if isinstance(a, dict)]
        already_auto = any(
            str(a.get("model") or "") == "res.partner"
            and fname in str(a.get("filter_domain") or "")
            for a in autos
        )
        if not already_auto:
            label = str(prefer.get("string") or "Preferred for delivery")
            draft.setdefault("automations", []).append(
                {
                    "name": f"{label} — follow up",
                    "model": "res.partner",
                    "trigger": "on_write",
                    "trigger_field_names": [fname],
                    "filter_domain": f"[('{fname}', '=', True)]",
                    "description": "Light ops automation when Prefer for delivery is checked",
                    "safe_actions": [
                        {
                            "kind": "next_activity",
                            "summary": f"{label}: confirm delivery notes for logistics",
                            "activity_type_xml_id": "mail.mail_activity_data_todo",
                        }
                    ],
                    "source": "senior_ops",
                }
            )
            notes.append(f"senior: on_write activity when {fname} is set")

    if _OPS_PICKING_RE.search(prompt or ""):
        existing = {
            (str(b.get("on_model")), str(b.get("related_model")))
            for b in (draft.get("smart_buttons") or [])
            if isinstance(b, dict)
        }
        key = ("res.partner", "stock.picking")
        if key not in existing:
            draft.setdefault("smart_buttons", []).append(
                {
                    "on_model": "res.partner",
                    "related_model": "stock.picking",
                    "relation_field": "partner_id",
                    "label": "Transfers",
                    "icon": "fa-truck",
                    "requires_inherit_view": True,
                    "source": "senior_ops",
                }
            )
            notes.append("senior: smart button Contacts → Transfers (stock.picking)")

    return notes


def finish_senior_component(
    draft: dict[str, Any],
    *,
    prompt: str,
    grain: Grain,
) -> list[str]:
    """Raise a field_pack / feature_slice to senior inherit-and-wire quality."""
    notes: list[str] = []
    if grain == "full_app" or not _models(draft):
        return notes
    notes.extend(_ensure_inherit_field_floor(draft, prompt, grain=grain))
    notes.extend(_ensure_date_activity(draft, grain=grain))
    if grain == "feature_slice":
        notes.extend(_ensure_slice_companion(draft, prompt))
        notes.extend(_ensure_host_smart_button(draft))
        notes.extend(_ensure_slice_access(draft))
    # Inherit-only ops field_packs still need pickings filter / light automation.
    notes.extend(_ensure_inherit_ops_wiring(draft, prompt))
    notes.extend(_drop_clone_companions(draft))
    from app.ai_capability_gaps import stamp_capability_gaps

    notes.extend(stamp_capability_gaps(draft, prompt))
    from app.ai_architecture_plan import stamp_architecture_plan
    from app.ai_option_a_quality import apply_option_a_grain_label, stamp_done_bar

    stamp_architecture_plan(draft, prompt=prompt, rebuild=True)
    apply_option_a_grain_label(draft)
    stamp_done_bar(draft, prompt=prompt)
    draft["_user_prompt"] = prompt or str(draft.get("_user_prompt") or "")
    from app.ai_field_ir import sanitize_inherit_extension_fields
    from app.ai_form_slots import apply_form_slots

    notes.extend(sanitize_inherit_extension_fields(draft, prompt=prompt))
    notes.extend(apply_form_slots(draft, prompt=prompt))
    draft["_senior_shape"] = {"grain": grain, "applied": True, "notes": len(notes)}
    return notes


def _ensure_inherit_field_floor(
    draft: dict[str, Any],
    prompt: str,
    *,
    grain: Grain | None = None,
) -> list[str]:
    notes: list[str] = []
    inherit = _inherit_row(draft)
    if inherit is None:
        return notes
    existing = _field_names(inherit)
    from app.ai_field_ir import extract_field_ir

    constraints: list[str] = []
    understanding = draft.get("_understanding")
    if isinstance(understanding, dict) and isinstance(understanding.get("constraints"), list):
        constraints = [str(x) for x in understanding["constraints"]]
    explicit = extract_field_ir(prompt, constraints=constraints or None)
    inferred = explicit if explicit else infer_extension_fields(
        prompt, pad=grain != "field_pack"
    )
    added = 0
    for field in inferred:
        name = str(field.get("name") or "")
        if not name or name in existing:
            continue
        inherit.setdefault("fields", []).append(field)
        existing.add(name)
        added += 1
    # Do not force a 3-field floor for Option A–primary prompts (no junk padding)
    # or an explicit single-field inherit.
    from app.ai_capability_gaps import assess_capability_gaps

    single_field = bool(
        re.search(
            r"\b(?:a\s+)?(?:single|one)\s+(?:extra\s+)?field\b|"
            r"\bjust\s+(?:inherit|one\s+field)\b",
            (prompt or "").lower(),
        )
    )
    if (
        grain != "field_pack"
        and not explicit
        and not single_field
        and not assess_capability_gaps(prompt).primary_option_a
        and len(_field_names(inherit)) < 3
    ):
        for field in inferred:
            name = str(field.get("name") or "")
            if name and name not in existing:
                inherit.setdefault("fields", []).append(field)
                existing.add(name)
    if added:
        notes.append(f"senior: inherit fields +{added} on {inherit.get('model')}")
    return notes


def _ensure_extension_view(draft: dict[str, Any]) -> list[str]:
    """Rebuild inherit form chrome via named slots (never a nested EXTENSION group)."""
    from app.ai_form_slots import apply_form_slots

    return apply_form_slots(draft, prompt=str(draft.get("_user_prompt") or ""))


def _ensure_slice_companion(draft: dict[str, Any], prompt: str) -> list[str]:
    notes: list[str] = []
    if not _COMPANION_RE.search(prompt or ""):
        return notes
    if any(str(m.get("model") or "").startswith("x_") for m in _models(draft)):
        return notes
    inherit = _inherit_row(draft)
    if inherit is None:
        return notes
    host = str(inherit.get("model") or "")
    leaf = _head_noun((prompt or "").lower()) or "item"
    if leaf in _CLONE_LEAVES:
        return notes
    mid = f"x_{leaf}"
    if not mid.endswith("_line") and "checklist" in (prompt or "").lower():
        mid = f"x_{leaf}_line"
    fk = "x_task_id" if host == "project.task" else f"x_{host.replace('.', '_')}_id"
    o2m = f"{mid}_ids" if mid.startswith("x_") else f"x_{leaf}_ids"
    companion = {
        "model": mid,
        "mode": "new",
        "description": leaf.replace("_", " ").title(),
        "source": "senior_shape",
        "fields": [
            {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
            {
                "name": fk,
                "ttype": "many2one",
                "relation": host,
                "string": host,
                "required": True,
            },
            {"name": "x_notes", "ttype": "text", "string": "Notes"},
            {
                "name": "x_company_id",
                "ttype": "many2one",
                "relation": "res.company",
                "string": "Company",
            },
        ],
    }
    draft.setdefault("models", []).append(companion)
    if o2m not in _field_names(inherit):
        inherit.setdefault("fields", []).append(
            {
                "name": o2m,
                "ttype": "one2many",
                "relation": mid,
                "relation_field": fk,
                "string": leaf.replace("_", " ").title(),
                "source": "senior_shape",
            }
        )
    notes.append(f"senior: companion {mid} on {host}")
    return notes


def _ensure_host_smart_button(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    inherit = _inherit_row(draft)
    if inherit is None:
        return notes
    host = str(inherit.get("model") or "")
    existing = {
        (str(b.get("on_model")), str(b.get("related_model")))
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    for field in inherit.get("fields") or []:
        if not isinstance(field, dict) or field.get("ttype") != "one2many":
            continue
        rel = str(field.get("relation") or "")
        fk = str(field.get("relation_field") or "")
        if not rel.startswith("x_") or not fk:
            continue
        key = (host, rel)
        if key in existing:
            continue
        draft.setdefault("smart_buttons", []).append(
            {
                "on_model": host,
                "related_model": rel,
                "relation_field": fk,
                "label": str(field.get("string") or rel),
                "icon": "fa-list",
                "requires_inherit_view": True,
                "source": "senior_shape",
            }
        )
        existing.add(key)
        notes.append(f"senior: smart button {host} → {rel}")
    return notes


def _ensure_date_activity(draft: dict[str, Any], *, grain: Grain = "feature_slice") -> list[str]:
    notes: list[str] = []
    autos = [a for a in (draft.get("automations") or []) if isinstance(a, dict)]
    if any(str(a.get("trigger") or "") == "on_time" for a in autos):
        return notes
    for model in _models(draft):
        mid = str(model.get("model") or "")
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or str(field.get("ttype") or "") != "date":
                continue
            fname = str(field.get("name") or "")
            if not fname:
                continue
            draft.setdefault("automations", []).append(
                {
                    "name": f"Activity before {field.get('string') or fname}",
                    "model": mid,
                    "trigger": "on_time",
                    "trg_date_field_name": fname,
                    "description": "Senior default — remind before the date",
                    "safe_actions": [
                        {
                            "kind": "next_activity",
                            "summary": f"{field.get('string') or fname} approaching",
                            "activity_type_xml_id": "mail.mail_activity_data_todo",
                        }
                    ],
                    "source": "senior_shape",
                }
            )
            notes.append(f"senior: date activity on {mid}.{fname}")
            return notes
    if not autos and grain == "feature_slice":
        inherit = _inherit_row(draft)
        if inherit is None:
            return notes
        draft.setdefault("automations", []).append(
            {
                "name": "Activity on create",
                "model": str(inherit.get("model")),
                "trigger": "on_create",
                "description": "Kick off the extension checklist",
                "safe_actions": [
                    {
                        "kind": "next_activity",
                        "summary": "Complete extension follow-up",
                        "activity_type_xml_id": "mail.mail_activity_data_todo",
                    }
                ],
                "source": "senior_shape",
            }
        )
        notes.append("senior: on_create activity on host")
    return notes


def _ensure_slice_access(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    existing = {
        str(r.get("model") or "").replace("model_", "", 1)
        for r in (draft.get("access_rules") or [])
        if isinstance(r, dict)
    }
    tech = str(draft.get("technical_name") or "component").replace(".", "_")
    user_g = f"group_{tech}_user"
    mgr_g = f"group_{tech}_manager"
    if not any(isinstance(g, dict) and g.get("id") == user_g for g in (draft.get("groups") or [])):
        draft.setdefault("groups", []).extend(
            [
                {"id": user_g, "name": "Extension User", "category_id": "base.module_category_custom"},
                {
                    "id": mgr_g,
                    "name": "Extension Manager",
                    "implied_ids": [user_g],
                    "category_id": "base.module_category_custom",
                },
            ]
        )
    for model in _models(draft):
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        if mid in existing:
            continue
        draft.setdefault("access_rules", []).extend(
            [
                {
                    "id": f"access_{mid}_user",
                    "name": f"{mid} user",
                    "model": f"model_{mid}",
                    "group": user_g,
                    "perm_read": 1,
                    "perm_write": 1,
                    "perm_create": 1,
                    "perm_unlink": 0,
                },
                {
                    "id": f"access_{mid}_manager",
                    "name": f"{mid} manager",
                    "model": f"model_{mid}",
                    "group": mgr_g,
                    "perm_read": 1,
                    "perm_write": 1,
                    "perm_create": 1,
                    "perm_unlink": 1,
                },
            ]
        )
        existing.add(mid)
        notes.append(f"senior: access on {mid}")
    return notes


def _drop_clone_companions(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    removed: set[str] = set()
    kept: list[dict[str, Any]] = []
    for model in _models(draft):
        mid = str(model.get("model") or "")
        leaf = mid[2:] if mid.startswith("x_") else ""
        if leaf in _CLONE_LEAVES:
            removed.add(mid)
            continue
        kept.append(model)
    if not removed:
        return notes
    draft["models"] = kept
    notes.append("senior: dropped stock clones " + ", ".join(sorted(removed)))
    return notes


__all__ = ["finish_senior_component", "infer_extension_fields"]  # field IR: app.ai_field_ir
