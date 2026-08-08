"""Domain-agnostic ModuleSpec depth: ambition, scoring, deterministic repair, LLM expand.

Domain packs remain a retrieval fallback. Consistent depth must not depend on matching
a curated pack — every NL draft is scored and expanded to the ambition floor.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Literal

Ambition = Literal["thin", "standard", "comprehensive"]

# Floors the draft must meet after generate/enrich (packs optional).
AMBITION_TARGETS: dict[Ambition, dict[str, float]] = {
    "thin": {
        "min_models": 2,
        "min_fields_avg": 3,
        "min_m2o": 1,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 0,
        "max_entities_staged": 6,
    },
    "standard": {
        "min_models": 5,
        "min_fields_avg": 5,
        "min_m2o": 4,
        "min_workflows": 1,
        "min_smart_buttons": 2,
        "min_automations": 1,
        "max_entities_staged": 12,
    },
    "comprehensive": {
        "min_models": 10,
        "min_fields_avg": 6,
        "min_m2o": 10,
        "min_workflows": 3,
        "min_smart_buttons": 6,
        "min_automations": 2,
        "max_entities_staged": 18,
    },
}

_COMPREHENSIVE_RE = re.compile(
    r"\b("
    r"comprehensive|world[\s-]?class|enterprise[\s-]?grade|production[\s-]?grade|"
    r"full[\s-]?scale|end[\s-]?to[\s-]?end|complete\s+system|"
    r"perfectly\s+models|internal\s+workings|robust|exhaustive|"
    r"large[\s-]?scale|mission[\s-]?critical"
    r")\b",
    re.I,
)

_THIN_HINT_RE = re.compile(
    r"\b(simple|minimal|tiny|quick|just\s+a|basic|small)\b",
    re.I,
)


_SCALE_RE = re.compile(
    r"\b(mega|large|multiple|multi[\s-]?branch|branches|chain|franchise|"
    r"nationwide|worldwide)\b",
    re.I,
)

_GLOBAL_PROMPT_RE = re.compile(
    r"\b("
    r"around\s+the\s+world|international|global|worldwide|multi[\s-]?country|"
    r"across\s+countries|multiple\s+countries"
    r")\b",
    re.I,
)


def classify_ambition(prompt: str) -> Ambition:
    """Infer how deep the ModuleSpec should be from the user prompt alone."""
    amb, _notes = classify_ambition_with_notes(prompt)
    return amb


def classify_ambition_with_notes(prompt: str) -> tuple[Ambition, list[str]]:
    """Return ambition plus optional auto-scale warnings."""
    text = (prompt or "").strip()
    notes: list[str] = []
    if not text:
        return "standard", notes
    if _COMPREHENSIVE_RE.search(text):
        return "comprehensive", notes
    if _SCALE_RE.search(text) and not _THIN_HINT_RE.search(text):
        notes.append(
            "ambition: prompt scale cues (mega/large/multiple branches/chain) "
            "→ comprehensive targets"
        )
        return "comprehensive", notes
    if _THIN_HINT_RE.search(text) and len(text.split()) < 16:
        return "thin", notes
    ops = re.findall(
        r"\b(manage|management|system|platform|operations|workflow|inventory|"
        r"billing|scheduling|crm|erp|portal)\b",
        text,
        flags=re.I,
    )
    if len(ops) >= 1 and len(text.split()) >= 8:
        return "standard", notes
    if len(text.split()) <= 5:
        return "thin", notes
    return "standard", notes


def _models(draft: dict[str, Any]) -> list[dict[str, Any]]:
    return [m for m in (draft.get("models") or []) if isinstance(m, dict) and m.get("model")]


def _field_names(model: dict[str, Any]) -> set[str]:
    return {
        str(f["name"])
        for f in (model.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }


def _is_hollow_model(model: dict[str, Any]) -> bool:
    """Catalog stubs (name+code only) inflate model_count without operational depth."""
    fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
    if len(fields) > 3:
        return False
    names = {str(f.get("name") or "") for f in fields}
    substantive_names = names - {"x_name", "x_code", "x_active", "x_sequence", "x_color"}
    if substantive_names:
        # Has a non-trivial field — not hollow even if small
        for f in fields:
            t = str(f.get("ttype") or "")
            if t in {"many2one", "one2many", "many2many", "selection", "monetary"} and f.get(
                "name"
            ) not in {"x_name", "x_code"}:
                return False
            if t in {"text", "html", "datetime", "date"}:
                return False
    return len(fields) <= 3 and not model.get("is_workflow")


def _is_safe_automation(auto: dict[str, Any]) -> bool:
    """Refuse Python/code server actions and empty/unsupported critique stubs."""
    if auto.get("action") and isinstance(auto["action"], dict):
        act = auto["action"]
        state = str(act.get("state") or "")
        if state in {"code", "call"} or act.get("code") or "python" in str(act).lower():
            return False
        if str(act.get("type") or "").startswith("ir.actions") and not auto.get("safe_actions"):
            return False
    actions = auto.get("safe_actions") or auto.get("actions") or []
    if not actions and auto.get("source") in {"critique", "depth_expand", "rules_engine"}:
        # Empty critique stub — not usable
        if not auto.get("action"):
            return False
    if isinstance(actions, list):
        for a in actions:
            if not isinstance(a, dict):
                continue
            kind = str(a.get("kind") or a.get("action_kind") or "")
            if kind in {"code", "email_send", "python"}:
                return False
            if a.get("code"):
                return False
    return True


def compute_depth_metrics(
    draft: dict[str, Any],
    *,
    exclude_depth_seed: bool = False,
) -> dict[str, Any]:
    models = _models(draft)
    if exclude_depth_seed:
        models = [
            m
            for m in models
            if not (isinstance(m, dict) and m.get("source") == "depth_seed")
        ]
    n_models = len(models)
    substantive = [m for m in models if not _is_hollow_model(m)]
    field_counts: list[int] = []
    m2o = 0
    workflows = 0
    for m in substantive:
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        field_counts.append(len(fields))
        for f in fields:
            if str(f.get("ttype") or "") == "many2one" and f.get("relation"):
                m2o += 1
        names = _field_names(m)
        if "x_status" in names or m.get("is_workflow"):
            workflows += 1
    avg_fields = (sum(field_counts) / len(substantive)) if substantive else 0.0
    buttons = [b for b in (draft.get("smart_buttons") or []) if isinstance(b, dict)]
    autos = [
        a
        for a in (draft.get("automations") or [])
        if isinstance(a, dict) and _is_safe_automation(a)
    ]
    hollow = n_models - len(substantive)
    return {
        "model_count": len(substantive),  # floors use substantive models only
        "model_count_raw": n_models,
        "hollow_model_count": hollow,
        "field_total": sum(field_counts),
        "fields_avg": round(avg_fields, 2),
        "m2o_count": m2o,
        "workflow_count": workflows,
        "smart_button_count": len(buttons),
        "automation_count": len(autos),
    }


def build_depth_block(
    draft: dict[str, Any],
    *,
    ambition: Ambition | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Single source of truth for _depth metrics (with/without seeds)."""
    amb: Ambition = ambition or draft.get("_ambition") or "standard"  # type: ignore[assignment]
    if amb not in AMBITION_TARGETS:
        amb = "standard"
    metrics = compute_depth_metrics(draft, exclude_depth_seed=False)
    metrics_no_seed = compute_depth_metrics(draft, exclude_depth_seed=True)
    gaps = depth_gaps(draft, amb)
    block: dict[str, Any] = {
        "ambition": amb,
        "metrics": metrics,
        "metrics_without_seeds": metrics_no_seed,
        "gaps": gaps,
        "targets": AMBITION_TARGETS[amb],
        "ok": not gaps,
        "seeded": False,
    }
    block.update(extra)
    return block


def depth_gaps(draft: dict[str, Any], ambition: Ambition | None = None) -> list[str]:
    """Return failed depth criterion ids (empty = meets floor)."""
    amb: Ambition = ambition or draft.get("_ambition") or "standard"  # type: ignore[assignment]
    if amb not in AMBITION_TARGETS:
        amb = "standard"
    t = AMBITION_TARGETS[amb]
    m = compute_depth_metrics(draft)
    m_real = compute_depth_metrics(draft, exclude_depth_seed=True)
    gaps: list[str] = []
    if m_real["model_count"] < t["min_models"]:
        gaps.append("depth_models")
    if m["fields_avg"] < t["min_fields_avg"]:
        gaps.append("depth_fields_avg")
    if m["m2o_count"] < t["min_m2o"]:
        gaps.append("depth_relations")
    if m["workflow_count"] < t["min_workflows"]:
        gaps.append("depth_workflows")
    if m["smart_button_count"] < t["min_smart_buttons"]:
        gaps.append("depth_smart_buttons")
    if m["automation_count"] < t["min_automations"]:
        gaps.append("depth_automations")
    return gaps


def depth_checklist(
    draft: dict[str, Any], ambition: Ambition | None = None
) -> list[dict[str, Any]]:
    amb: Ambition = ambition or draft.get("_ambition") or "standard"  # type: ignore[assignment]
    if amb not in AMBITION_TARGETS:
        amb = "standard"
    t = AMBITION_TARGETS[amb]
    m = compute_depth_metrics(draft)
    m_real = compute_depth_metrics(draft, exclude_depth_seed=True)
    gaps = set(depth_gaps(draft, amb))

    def row(key: str, ok: bool, detail: str) -> dict[str, Any]:
        return {"id": key, "ok": ok, "detail": detail}

    return [
        row(
            "depth_models",
            "depth_models" not in gaps,
            f"{m_real['model_count']}/{int(t['min_models'])} substantive models "
            f"(excl. depth_seed; raw={m.get('model_count_raw', m['model_count'])}, "
            f"seeded={m['model_count'] - m_real['model_count']})",
        ),
        row(
            "depth_fields_avg",
            "depth_fields_avg" not in gaps,
            f"avg {m['fields_avg']}/{t['min_fields_avg']} fields/model",
        ),
        row(
            "depth_relations",
            "depth_relations" not in gaps,
            f"{m['m2o_count']}/{int(t['min_m2o'])} many2one links",
        ),
        row(
            "depth_workflows",
            "depth_workflows" not in gaps,
            f"{m['workflow_count']}/{int(t['min_workflows'])} workflow models",
        ),
        row(
            "depth_smart_buttons",
            "depth_smart_buttons" not in gaps,
            f"{m['smart_button_count']}/{int(t['min_smart_buttons'])} smart buttons",
        ),
        row(
            "depth_automations",
            "depth_automations" not in gaps,
            f"{m['automation_count']}/{int(t['min_automations'])} automations",
        ),
    ]


def synthesize_smart_buttons_from_relations(draft: dict[str, Any]) -> list[str]:
    """For every child.x_* many2one → parent (x_*), add parent→child smart button."""
    notes: list[str] = []
    models = _models(draft)
    known = {str(m["model"]) for m in models}
    existing = {
        (b.get("on_model"), b.get("related_model"), b.get("relation_field"))
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    added = 0
    for child in models:
        child_id = str(child["model"])
        for f in child.get("fields") or []:
            if not isinstance(f, dict):
                continue
            if str(f.get("ttype") or "") != "many2one":
                continue
            parent = f.get("relation")
            fname = f.get("name")
            if not parent or not fname:
                continue
            parent_s, fname_s = str(parent), str(fname)
            if parent_s not in known or not parent_s.startswith("x_"):
                continue
            key = (parent_s, child_id, fname_s)
            if key in existing:
                continue
            label = str(
                child.get("description")
                or child_id.replace("x_", "").replace("_", " ").title()
            )
            draft.setdefault("smart_buttons", []).append(
                {
                    "on_model": parent_s,
                    "label": label,
                    "related_model": child_id,
                    "relation_field": fname_s,
                    "icon": "fa-list",
                    "source": "depth_synthesize",
                }
            )
            existing.add(key)
            added += 1
    if added:
        notes.append(f"depth: synthesized {added} smart button(s) from many2one graph")
    return notes


def _ensure_currency_on_amounts(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for m in _models(draft):
        names = _field_names(m)
        fields = list(m.get("fields") or [])
        has_amount = any(
            isinstance(f, dict)
            and str(f.get("ttype")) in {"float", "monetary"}
            and "amount" in str(f.get("name") or "").lower()
            for f in fields
        )
        if has_amount and "x_currency_id" not in names:
            fields.append(
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "string": "Currency",
                    "relation": "res.currency",
                }
            )
            m["fields"] = fields
            notes.append(f"depth: currency on {m.get('model')}")
    return notes


def _ensure_company_on_transactional(
    draft: dict[str, Any], ambition: Ambition
) -> list[str]:
    if ambition != "comprehensive":
        return []
    notes: list[str] = []
    for m in _models(draft):
        names = _field_names(m)
        fields = [f for f in (m.get("fields") or []) if isinstance(f, dict)]
        needs = (
            "x_status" in names
            or m.get("is_workflow")
            or any(f.get("relation") == "res.partner" for f in fields)
            or any("amount" in str(f.get("name") or "") for f in fields)
        )
        if needs and "x_company_id" not in names:
            fields.append(
                {
                    "name": "x_company_id",
                    "ttype": "many2one",
                    "string": "Company",
                    "relation": "res.company",
                }
            )
            m["fields"] = fields
            notes.append(f"depth: company on {m.get('model')}")
    return notes


def _ensure_workflow_minimum_fields(draft: dict[str, Any]) -> list[str]:
    """Workflow models should carry status + code."""
    notes: list[str] = []
    for m in _models(draft):
        names = _field_names(m)
        if "x_status" not in names and not m.get("is_workflow"):
            continue
        fields = list(m.get("fields") or [])
        if "x_status" not in names:
            fields.append(
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Status",
                    "selection": (
                        "[('draft','Draft'),('done','Done'),('cancelled','Cancelled')]"
                    ),
                    "required": True,
                }
            )
            notes.append(f"depth: status on {m.get('model')}")
            names.add("x_status")
        if "x_code" not in names and "x_reference" not in names:
            fields.insert(
                1 if fields and fields[0].get("name") == "x_name" else 0,
                {
                    "name": "x_code",
                    "ttype": "char",
                    "string": "Reference",
                    "help": "Sequence / reference — wire ir.sequence later",
                },
            )
            notes.append(f"depth: reference code on {m.get('model')}")
        m["fields"] = fields
        m["is_workflow"] = True
    return notes


def strip_unsafe_automations(draft: dict[str, Any]) -> list[str]:
    """Drop code/email_send/empty automations that cannot be applied safely."""
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return []
    kept: list[dict[str, Any]] = []
    notes: list[str] = []
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        if _is_safe_automation(auto):
            # Normalize list filter_domain → string for apply path
            fd = auto.get("filter_domain")
            if isinstance(fd, list):
                import json as _json

                try:
                    auto = {**auto, "filter_domain": _json.dumps(fd)}
                except TypeError:
                    pass
            # Fix object_write to values missing from selection → next_activity
            auto = _sanitize_automation_writes(draft, auto, notes)
            kept.append(auto)
        else:
            notes.append(
                f"depth: stripped unsafe/empty automation "
                f"{auto.get('name') or auto.get('action', {}).get('name') or '(unnamed)'!r}"
            )
    draft["automations"] = kept
    return notes


def _selection_keys(field: dict[str, Any]) -> set[str]:
    raw = str(field.get("selection") or "")
    return set(re.findall(r"\(\s*'([^']+)'\s*,", raw))


def _sanitize_automation_writes(
    draft: dict[str, Any], auto: dict[str, Any], notes: list[str]
) -> dict[str, Any]:
    """If object_write targets a selection value that doesn't exist, use next_activity."""
    mid = str(auto.get("model") or "")
    model = next((m for m in _models(draft) if m.get("model") == mid), None)
    if not model:
        return auto
    fields_by_name = {
        str(f.get("name")): f
        for f in (model.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }
    actions = list(auto.get("safe_actions") or [])
    if not actions:
        return auto
    new_actions: list[dict[str, Any]] = []
    changed = False
    for a in actions:
        if not isinstance(a, dict):
            continue
        kind = str(a.get("kind") or "")
        field = str(a.get("field") or "")
        if kind in {"object_write", "update_field"} and field in fields_by_name:
            fdef = fields_by_name[field]
            if str(fdef.get("ttype")) == "selection":
                keys = _selection_keys(fdef)
                val = str(a.get("value") or "")
                if keys and val and val not in keys:
                    new_actions.append(
                        {
                            "kind": "next_activity",
                            "summary": a.get("summary")
                            or auto.get("name")
                            or f"{field} follow-up",
                        }
                    )
                    changed = True
                    continue
        new_actions.append(a)
    if changed:
        notes.append(
            f"depth: sanitized automation write on {mid} → next_activity "
            "(value not in selection)"
        )
        return {**auto, "safe_actions": new_actions}
    return auto


def _primary_transaction_model(draft: dict[str, Any]) -> dict[str, Any] | None:
    candidates = []
    for m in _models(draft):
        mid = str(m.get("model") or "")
        if mid.endswith("_line") or mid.endswith("line"):
            continue
        names = _field_names(m)
        score = len([f for f in (m.get("fields") or []) if isinstance(f, dict)])
        if m.get("is_workflow") or "x_status" in names:
            score += 50
        if "x_partner_id" in names:
            score += 10
        candidates.append((score, mid, m))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (-t[0], t[1]))
    return candidates[0][2]


def _staff_model_id(draft: dict[str, Any], parent_id: str) -> str | None:
    keys = (
        "attorney",
        "doctor",
        "nurse",
        "staff",
        "practitioner",
        "technician",
        "teacher",
        "agent",
        "employee",
        "owner",
    )
    for m in _models(draft):
        mid = str(m.get("model") or "")
        if mid == parent_id:
            continue
        leaf = mid.replace("x_", "")
        if any(k in leaf for k in keys):
            return mid
    return None


def _role_already_present(draft: dict[str, Any], keywords: tuple[str, ...]) -> bool:
    for m in _models(draft):
        leaf = str(m.get("model") or "").replace("x_", "")
        desc = str(m.get("description") or "").lower()
        if any(k in leaf or k in desc for k in keywords):
            return True
    return False


def _parent_fk_name(parent_id: str) -> str:
    """x_matter → x_matter_id"""
    return f"{parent_id}_id" if parent_id.startswith("x_") else f"x_{parent_id}_id"


LAW_FIRM_SEED_LEXICON = frozenset(
    {
        "retainer",
        "appointment",
        "disbursement",
        "hearing",
        "matter",
        "attorney",
        "conflict",
        "trust",
        "escrow",
    }
)


_SEED_SCALE_WORDS = frozenset(
    {"super", "mega", "large", "multiple", "around", "world", "global", "chain"}
)
_SEED_DOMAIN_WORDS = frozenset(
    {
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
    }
)


def _neutral_seed_description(
    template_desc: str,
    *,
    parent_label: str,
    user_prompt: str = "",
) -> str:
    """Domain-neutral labels for depth_seed models (no law-firm jargon)."""
    role = template_desc.split("/")[0].strip()
    domain_word = ""
    for tok in re.findall(r"[a-zA-Z]+", user_prompt):
        low = tok.lower()
        if low in _SEED_SCALE_WORDS or low in {"the", "with", "and", "for"}:
            continue
        if low in _SEED_DOMAIN_WORDS or len(low) >= 5:
            domain_word = tok.title()
            break
    if domain_word:
        return f"{domain_word} {role}"
    if parent_label and parent_label not in {"Parent", "parent"}:
        return f"{parent_label} {role}"
    return f"Related {role}"


def _build_seed_fields(
    parent_id: str,
    staff_id: str | None,
    *,
    parent_label: str = "Parent",
    with_amount: bool = False,
    with_deadline: bool = False,
    with_location: bool = False,
    with_party_type: bool = False,
    with_file: bool = False,
    anchor_required: bool = True,
) -> list[dict[str, Any]]:
    fk = _parent_fk_name(parent_id)
    fields: list[dict[str, Any]] = [
        {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
        {
            "name": fk,
            "ttype": "many2one",
            "relation": parent_id,
            "string": parent_label,
            "required": anchor_required,
        },
    ]
    if with_deadline:
        fields.append(
            {
                "name": "x_date_deadline",
                "ttype": "date",
                "string": "Deadline",
                "required": True,
            }
        )
    else:
        fields.append(
            {"name": "x_date", "ttype": "date", "string": "Date", "required": True}
        )
    if with_location:
        fields.append({"name": "x_location", "ttype": "char", "string": "Location"})
    if with_amount:
        fields.extend(
            [
                {
                    "name": "x_amount",
                    "ttype": "float",
                    "string": "Amount",
                    "required": True,
                },
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "relation": "res.currency",
                    "string": "Currency",
                },
            ]
        )
    if with_party_type:
        fields.append(
            {
                "name": "x_role",
                "ttype": "selection",
                "string": "Role",
                "selection": (
                    "[('primary','Primary'),('related','Related'),"
                    "('opposing','Opposing'),('other','Other')]"
                ),
                "required": True,
            }
        )
    if with_file:
        fields.append({"name": "x_file", "ttype": "binary", "string": "File"})
    if staff_id:
        fields.append(
            {
                "name": "x_staff_id",
                "ttype": "many2one",
                "relation": staff_id,
                "string": "Assigned",
            }
        )
    # Tasks / compliance benefit from a simple status without forcing is_workflow
    if with_deadline or with_party_type:
        fields.append(
            {
                "name": "x_status",
                "ttype": "selection",
                "string": "Status",
                "selection": (
                    "[('draft','Draft'),('open','Open'),('done','Done'),"
                    "('cancelled','Cancelled')]"
                ),
            }
        )
    fields.extend(
        [
            {
                "name": "x_partner_id",
                "ttype": "many2one",
                "relation": "res.partner",
                "string": "Contact",
            },
            {
                "name": "x_company_id",
                "ttype": "many2one",
                "relation": "res.company",
                "string": "Company",
            },
            {"name": "x_notes", "ttype": "text", "string": "Notes"},
        ]
    )
    return fields


def seed_operational_loop_models(
    draft: dict[str, Any], ambition: Ambition, *, user_prompt: str = ""
) -> list[str]:
    """Deterministically add substantive ops-loop models when under the model floor.

    Does not invent domain jargon — generic roles renamed only by parent FK.
    Skips roles already present. Never adds type/tag/client mini-CRM stubs.
    """
    notes: list[str] = []
    need = int(AMBITION_TARGETS[ambition]["min_models"]) - int(
        compute_depth_metrics(draft)["model_count"]
    )
    if need <= 0:
        return notes
    from app.ai_vocab_scrub import find_hub_model

    parent = _primary_transaction_model(draft)
    anchor_required = True
    hub = find_hub_model(draft)
    if hub:
        parent = next((m for m in _models(draft) if m.get("model") == hub), parent)
        anchor_required = False
    if not parent:
        return notes
    parent_id = str(parent["model"])
    parent_label = str(parent.get("description") or parent_id).split("/")[0].strip() or "Parent"
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    staff_id = _staff_model_id(draft, parent_id)
    known = {str(m.get("model")) for m in _models(draft)}

    seeds: list[tuple[str, str, tuple[str, ...], dict[str, bool]]] = [
        (
            "x_event",
            "Event / Appointment",
            ("event", "hearing", "appointment", "schedule", "booking"),
            {"with_location": True},
        ),
        (
            "x_task",
            "Task / Deadline",
            ("task", "deadline", "todo", "activity"),
            {"with_deadline": True},
        ),
        (
            "x_expense",
            "Expense / Disbursement",
            ("expense", "disbursement", "cost"),
            {"with_amount": True},
        ),
        (
            "x_deposit",
            "Deposit / Retainer",
            ("deposit", "retainer", "trust", "escrow"),
            {"with_amount": True},
        ),
        (
            "x_compliance",
            "Compliance / Check",
            ("compliance", "conflict", "check", "clearance"),
            {},
        ),
        (
            "x_party",
            "Party / Role Link",
            ("party", "party_link", "participant", "stakeholder"),
            {"with_party_type": True},
        ),
        (
            "x_document",
            "Document / File",
            ("document", "attachment", "file", "evidence"),
            {"with_file": True},
        ),
        (
            "x_milestone",
            "Milestone / Checkpoint",
            ("milestone", "checkpoint", "phase_gate"),
            {"with_deadline": True},
        ),
        (
            "x_rate",
            "Rate / Price",
            ("rate_card", "price_card", "billing_rate"),
            {"with_amount": True},
        ),
    ]

    for mid, desc, keywords, opts in seeds:
        if need <= 0:
            break
        if _role_already_present(draft, keywords):
            continue
        model_name = mid if mid not in known else f"{parent_id}_{mid[2:]}"
        if model_name in known:
            continue
        fields = _build_seed_fields(
            parent_id,
            staff_id,
            parent_label=parent_label,
            anchor_required=anchor_required,
            **opts,
        )
        desc_neutral = _neutral_seed_description(
            desc, parent_label=parent_label, user_prompt=prompt
        )
        draft.setdefault("models", []).append(
            {
                "model": model_name,
                "description": desc_neutral,
                "mode": "new",
                "fields": fields,
                "source": "depth_seed",
            }
        )
        known.add(model_name)
        need -= 1
        notes.append(f"depth: seeded substantive model {model_name}")
    return notes


def _is_branch_model(model: dict[str, Any]) -> bool:
    mid = str(model.get("model") or "")
    if "transfer" in mid:
        return False
    if mid == "x_branch":
        return True
    desc = str(model.get("description") or "").lower()
    return (
        ("branch" in mid or "branch" in desc or "store location" in desc)
        and "transfer" not in desc
    )


def ensure_country_on_branch_for_global_prompt(
    draft: dict[str, Any], user_prompt: str
) -> list[str]:
    """Add x_country_id (res.country) on branch models when prompt implies multi-country ops."""
    if not _GLOBAL_PROMPT_RE.search(user_prompt or ""):
        return []
    notes: list[str] = []
    for m in _models(draft):
        if not _is_branch_model(m):
            continue
        names = _field_names(m)
        if "x_country_id" in names:
            continue
        m.setdefault("fields", [])
        if isinstance(m["fields"], list):
            m["fields"].append(
                {
                    "name": "x_country_id",
                    "ttype": "many2one",
                    "relation": "res.country",
                    "string": "Country",
                }
            )
            notes.append(f"depth: added x_country_id on {m.get('model')} (global prompt)")
    return notes


def _selection_keys_from_model(model: dict[str, Any]) -> list[str]:
    sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
    states = sf.get("states") if isinstance(sf.get("states"), list) else []
    keys: list[str] = []
    for st in states:
        if isinstance(st, dict) and st.get("key"):
            keys.append(str(st["key"]))
        elif isinstance(st, str):
            keys.append(st)
    if keys:
        return keys
    for f in model.get("fields") or []:
        if isinstance(f, dict) and f.get("name") == "x_status":
            sel = f.get("selection")
            if isinstance(sel, str):
                keys = re.findall(r"\('([^']+)'\s*,", sel)
            break
    return keys


def _workflow_automation_candidates(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Prefer per-workflow on_write automations over generic on_create fillers."""
    from app.ai_workflow_semantic import classify_state

    candidates: list[dict[str, Any]] = []
    for m in _models(draft):
        names = _field_names(m)
        if not (m.get("is_workflow") or "x_status" in names):
            continue
        mid = str(m["model"])
        keys = _selection_keys_from_model(m)
        terminals = [k for k in keys if classify_state(k) == "terminal_success"]
        if not terminals and keys:
            terminals = [keys[-1]]
        for term in terminals[:2]:
            label = str(m.get("description") or mid).replace("/", " ").strip()
            candidates.append(
                {
                    "name": f"Notify on {label} {term}",
                    "model": mid,
                    "trigger": "on_write",
                    "filter_domain": f"[('x_status','=','{term}')]",
                    "description": (
                        f"Depth floor: schedule follow-up when {mid} reaches {term!r}"
                    ),
                    "safe_actions": [
                        {"kind": "next_activity", "summary": f"Review {term} {label}"}
                    ],
                    "source": "depth_seed",
                }
            )
    return candidates


def ensure_min_automations(draft: dict[str, Any], ambition: Ambition) -> list[str]:
    """Add safe next_activity automations until the ambition floor is met."""
    notes: list[str] = []
    need = int(AMBITION_TARGETS[ambition]["min_automations"])
    autos = [
        a
        for a in (draft.get("automations") or [])
        if isinstance(a, dict) and _is_safe_automation(a)
    ]
    if len(autos) >= need:
        return notes
    parent = _primary_transaction_model(draft)
    if not parent:
        return notes
    parent_id = str(parent["model"])
    names = {str(a.get("name") or "") for a in autos}
    candidate_lists: list[list[dict[str, Any]]] = []
    if ambition == "comprehensive":
        candidate_lists.append(_workflow_automation_candidates(draft))
    candidate_lists.append(
        [
            {
                "name": f"Follow up on {parent_id} write",
                "model": parent_id,
                "trigger": "on_write",
                "description": "Depth floor: schedule a follow-up activity on change",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Review update"}
                ],
                "source": "depth_seed",
            },
            {
                "name": f"Activity on {parent_id} create",
                "model": parent_id,
                "trigger": "on_create",
                "description": "Depth floor: kick off activity when record is created",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "New record follow-up"}
                ],
                "source": "depth_seed",
            },
        ]
    )
    draft.setdefault("automations", [])
    for candidates in candidate_lists:
        for cand in candidates:
            if len(
                [
                    a
                    for a in draft["automations"]
                    if isinstance(a, dict) and _is_safe_automation(a)
                ]
            ) >= need:
                break
            if cand["name"] in names:
                continue
            draft["automations"].append(cand)
            names.add(cand["name"])
            notes.append(f"depth: seeded automation {cand['name']}")
    return notes


def apply_deterministic_depth(
    draft: dict[str, Any],
    ambition: Ambition | None = None,
    *,
    user_prompt: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Mutate draft toward ambition floor without an LLM."""
    out = copy.deepcopy(draft)
    if user_prompt:
        out["_user_prompt"] = user_prompt
    amb: Ambition = ambition or out.get("_ambition") or "standard"  # type: ignore[assignment]
    if amb not in AMBITION_TARGETS:
        amb = "standard"
    out["_ambition"] = amb
    notes: list[str] = []

    def _gaps_for_metrics(m: dict[str, Any]) -> list[str]:
        t = AMBITION_TARGETS[amb]
        gaps: list[str] = []
        if m["model_count"] < t["min_models"]:
            gaps.append("depth_models")
        if m["fields_avg"] < t["min_fields_avg"]:
            gaps.append("depth_fields_avg")
        if m["m2o_count"] < t["min_m2o"]:
            gaps.append("depth_relations")
        if m["workflow_count"] < t["min_workflows"]:
            gaps.append("depth_workflows")
        if m["smart_button_count"] < t["min_smart_buttons"]:
            gaps.append("depth_smart_buttons")
        if m["automation_count"] < t["min_automations"]:
            gaps.append("depth_automations")
        return gaps

    metrics_before_seed = compute_depth_metrics(out, exclude_depth_seed=True)
    gaps_before = _gaps_for_metrics(metrics_before_seed)
    notes.extend(strip_unsafe_automations(out))
    from app.ai_model_quality import (
        collapse_hollow_catalogs_to_selections,
        collapse_thin_padding_models,
    )

    notes.extend(collapse_hollow_catalogs_to_selections(out))
    notes.extend(collapse_thin_padding_models(out))
    notes.extend(seed_operational_loop_models(
        out, amb, user_prompt=user_prompt or str(out.get("_user_prompt") or "")
    ))
    notes.extend(
        ensure_country_on_branch_for_global_prompt(
            out, user_prompt or str(out.get("_user_prompt") or "")
        )
    )
    notes.extend(ensure_min_automations(out, amb))
    notes.extend(_ensure_workflow_minimum_fields(out))
    notes.extend(_ensure_currency_on_amounts(out))
    notes.extend(_ensure_company_on_transactional(out, amb))
    notes.extend(synthesize_smart_buttons_from_relations(out))
    out["_depth"] = build_depth_block(out, ambition=amb)
    gaps = out["_depth"]["gaps"]
    gaps_no_seed = _gaps_for_metrics(out["_depth"]["metrics_without_seeds"])
    has_depth_seeds = any(
        isinstance(m, dict) and m.get("source") == "depth_seed" for m in _models(out)
    )
    seeded_only = has_depth_seeds and bool(gaps_no_seed)
    out["_depth"]["seeded"] = seeded_only
    base = [c for c in (out.get("_completeness") or []) if isinstance(c, dict)]
    depth_ids = {c["id"] for c in depth_checklist(out, amb)}
    base = [c for c in base if c.get("id") not in depth_ids]
    out["_completeness"] = base + depth_checklist(out, amb)
    if seeded_only:
        notes.append("depth padded via generic seeds — regenerate recommended")
    if gaps:
        notes.append(f"depth: ambition={amb} still missing {', '.join(gaps)}")
    else:
        notes.append(f"depth: ambition={amb} met")
    return out, notes


def llm_expand_depth(
    provider: Any,
    draft: dict[str, Any],
    *,
    user_prompt: str,
    ambition: Ambition,
    gaps: list[str],
) -> tuple[dict[str, Any], list[str]]:
    """Ask the LLM to add models/fields/relations/autos to close depth gaps."""
    from app.llm_provider import LLMError

    notes: list[str] = []
    slim_models = [
        {
            "model": m.get("model"),
            "description": m.get("description"),
            "fields": [
                {
                    "name": f.get("name"),
                    "ttype": f.get("ttype"),
                    "relation": f.get("relation"),
                }
                for f in (m.get("fields") or [])[:25]
                if isinstance(f, dict)
            ],
        }
        for m in _models(draft)
    ]
    from app.ai_model_quality import MODEL_CREATION_RULES
    from app.ai_prompt_constants import STEP_TEMPERATURES, append_prompt_blocks
    from app.ai_prompt_constants import STEP_TEMPERATURES, append_prompt_blocks

    targets = AMBITION_TARGETS[ambition]
    metrics = compute_depth_metrics(draft)
    need_models = 0
    if "depth_models" in gaps:
        need_models = max(0, int(targets["min_models"]) - int(metrics["model_count"]))
        need_models = max(need_models, 2)  # always push at least 2 when under floor

    system = append_prompt_blocks(
        "You deepen an Odoo Community ModuleSpec that is too thin for the user request. "
        "Example output:\n"
        '{"missing_models":[{"model":"x_matter_event","description":"Hearing/event",'
        '"is_workflow":false,'
        '"fields":[{"name":"x_name","ttype":"char","string":"Event","required":true},'
        '{"name":"x_matter_id","ttype":"many2one","relation":"x_matter","string":"Matter"}]}],'
        '"missing_fields":[{"model":"x_matter","name":"x_lead_id","ttype":"many2one",'
        '"relation":"x_staff","string":"Lead"}],'
        '"missing_automations":[{"name":"Notify on status","model":"x_matter","trigger":"on_write",'
        '"safe_actions":[{"kind":"object_write","field":"x_status","value":"done"}]}],'
        '"notes":["Added event line model"]}\n'
        "Every missing_model must be SUBSTANTIVE (≥6 fields, ≥1 many2one to an EXISTING model). "
        "FORBIDDEN: type/category/tag/stage/priority name+code-only models — use selections. "
        "FORBIDDEN: duplicate billing models (if x_bill/x_charge exists, do not add x_invoice). "
        "FORBIDDEN: x_client mini-CRM when res.partner already links clients. "
        "No Python code automations.\n"
        + MODEL_CREATION_RULES,
    )
    loop_hints = (
        "Add operational roles NOT already covered (rename to THIS domain): "
        "events/hearings/appointments; tasks/deadlines; expenses/disbursements; "
        "trust/retainer/deposit; compliance/conflict check; multi-party links; "
        "staff rates — only if missing. Prefer NEW roles over cloning bill/invoice."
    )
    prompt = (
        f"User request (ambition={ambition}):\n{user_prompt}\n\n"
        f"Depth gaps: {gaps}\n"
        f"Targets: {json.dumps(targets)}\n"
        f"Current metrics: {json.dumps(metrics)}\n"
        f"Current models:\n{json.dumps(slim_models, default=str)[:6500]}\n"
        f"{loop_hints}\n"
        "Add enough missing_models / missing_fields / missing_automations to clear the gaps. "
        "Do not delete existing models."
    )
    if need_models:
        prompt += (
            f"\nCRITICAL: depth_models gap — missing_models MUST contain "
            f"at least {need_models} NEW substantive models (each ≥6 fields)."
        )
    try:
        from app.llm_provider import generate_json_with_timeout_retry

        raw = generate_json_with_timeout_retry(
            provider,
            prompt,
            system=system,
            timeout_s=240.0,
            reasoning=False,
            temperature=STEP_TEMPERATURES["depth.expand"],
        )
    except LLMError as exc:
        notes.append(f"depth: LLM expand skipped ({exc})")
        return draft, notes

    if isinstance(raw, dict):
        data = raw
    else:
        text = raw.strip() if isinstance(raw, str) else json.dumps(raw)
        try:
            from app.llm_json import parse_llm_json_object

            data = parse_llm_json_object(text)
        except ValueError as exc:
            notes.append(f"depth: LLM expand malformed JSON ({exc})")
            return draft, notes

    from app.ai_critique import apply_critique_repairs
    from app.ai_model_quality import filter_redundant_missing_models

    data["missing_models"] = filter_redundant_missing_models(
        draft, data.get("missing_models") or []
    )

    out, repair_notes = apply_critique_repairs(draft, data)
    notes.extend(repair_notes)
    notes.append("depth: LLM expand pass applied")
    return out, notes


def run_depth_pass(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    provider: Any | None = None,
    expand_llm: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """Classify ambition, deterministic repair, optional LLM expand (up to 2 rounds)."""
    warnings: list[str] = []
    ambition: Ambition
    if user_prompt:
        ambition = classify_ambition(user_prompt)
    else:
        raw_amb = draft.get("_ambition") or "standard"
        ambition = raw_amb if raw_amb in AMBITION_TARGETS else "standard"  # type: ignore[assignment]

    out, notes = apply_deterministic_depth(draft, ambition, user_prompt=user_prompt)
    warnings.extend(notes)

    if expand_llm and provider is not None:
        for round_i in range(2):
            gaps = depth_gaps(out, ambition)
            if not gaps:
                break
            # Only re-expand when still missing models/fields/workflows (not just soft gaps)
            hard = {
                g
                for g in gaps
                if g
                in {
                    "depth_models",
                    "depth_fields_avg",
                    "depth_workflows",
                    "depth_relations",
                    "depth_automations",
                }
            }
            if not hard and round_i > 0:
                break
            out, expand_notes = llm_expand_depth(
                provider,
                out,
                user_prompt=user_prompt,
                ambition=ambition,
                gaps=gaps,
            )
            warnings.extend(expand_notes)
            out, notes2 = apply_deterministic_depth(out, ambition)
            warnings.extend(notes2)

    return out, warnings


__all__ = [
    "AMBITION_TARGETS",
    "Ambition",
    "build_depth_block",
    "classify_ambition",
    "classify_ambition_with_notes",
    "compute_depth_metrics",
    "depth_gaps",
    "depth_checklist",
    "synthesize_smart_buttons_from_relations",
    "apply_deterministic_depth",
    "llm_expand_depth",
    "run_depth_pass",
    "strip_unsafe_automations",
    "seed_operational_loop_models",
    "ensure_min_automations",
]
