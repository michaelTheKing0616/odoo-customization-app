"""Self-critique pass — evaluate ModuleSpec against production checklist, then repair.

Small models are more reliable at yes/no evaluation than open-ended generation.
Deterministic completeness gaps always run; LLM critique is optional enrichment.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any

from app.ai_rules import completeness_checklist
from app.ai_depth import classify_ambition, depth_gaps
from app.ai_prompt_constants import STEP_TEMPERATURES, append_prompt_blocks
from app.llm_provider import LLMError, LLMProvider, get_llm_provider
from app.ai_prompt_constants import STEP_TEMPERATURES, append_prompt_blocks
from app.settings import settings

logger = logging.getLogger(__name__)

_FIELD_RE = re.compile(r"^x_[A-Za-z0-9_]+$")
_REPAIR_ADDED_FIELD = re.compile(r"^critique: added field ([^.]+)\.(\S+)$")
_REPAIR_ADDED_MODEL = re.compile(r"^critique: added model (\S+)$")
_REPAIR_ADDED_AUTO = re.compile(r"^critique: added automation (.+)$")
_INVENTORY_NOTE_RE = re.compile(
    r"lacks inventory|inventory management|inventory tracking", re.I
)


def critique_enabled() -> bool:
    return settings.ai_critique.strip().lower() in {"on", "true", "1", "yes", "auto"}


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def llm_critique(
    provider: LLMProvider,
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
) -> dict[str, Any]:
    """Ask the model to score readiness and list concrete missing pieces."""
    slim = {
        "technical_name": draft.get("technical_name"),
        "display_name": draft.get("display_name"),
        "models": [
            {
                "model": m.get("model"),
                "description": m.get("description"),
                "mixins": m.get("mixins"),
                "fields": [
                    {
                        "name": f.get("name"),
                        "ttype": f.get("ttype"),
                        "string": f.get("string"),
                        "relation": f.get("relation"),
                    }
                    for f in (m.get("fields") or [])
                    if isinstance(f, dict)
                ][:40],
            }
            for m in (draft.get("models") or [])
            if isinstance(m, dict)
        ],
        "smart_buttons": draft.get("smart_buttons"),
        "automations": [
            {"name": a.get("name"), "model": a.get("model"), "trigger": a.get("trigger")}
            for a in (draft.get("automations") or [])
            if isinstance(a, dict)
        ],
        "completeness": draft.get("_completeness"),
    }
    system = (
        "You evaluate Odoo Community ModuleSpec drafts for PRODUCTION DEPTH, not just "
        "whether menus exist. Reply ONLY with JSON:\n"
        "{"
        '"ready": false, '
        '"checklist": [{"id":"audit_trail","ok":true,"note":"..."}], '
        '"missing_fields": [{"model":"x_thing","name":"x_field","ttype":"char","string":"Label"}], '
        '"missing_models": [{"model":"x_thing","description":"Thing","fields":['
        '{"name":"x_name","ttype":"char","string":"Name","required":true},'
        '{"name":"x_parent_id","ttype":"many2one","relation":"x_existing","string":"Parent"}]}], '
        '"missing_automations": [{"name":"...","model":"x_...","trigger":"on_write",'
        '"safe_actions":[{"kind":"next_activity","summary":"Follow up"}]}], '
        '"notes": ["..."]'
        "}\n"
        "RULES for missing_models (mandatory):\n"
        "- Every model ≥5 fields and ≥1 many2one to an EXISTING draft model.\n"
        "- Prefer ops-loop roles: events/appointments, tasks/deadlines, expenses, "
        "deposits/retainers, compliance checks, party-links, documents.\n"
        "- FORBIDDEN: type/category/tag/stage/priority/specialty/case_type catalogs "
        "(use selections on parents).\n"
        "- FORBIDDEN: x_client / x_client_contact / mini-CRM when res.partner is used.\n"
        "- FORBIDDEN: second invoice/bill header when one billing model exists.\n"
        "- Automations must include non-empty safe_actions (object_write or next_activity). "
        "No Python/email_send.\n"
        "If comprehensive and <10 models, ready=false and propose substantive missing_models. "
        "Custom fields/models must start with x_. Triggers must be on_*. No markdown."
    )
    prompt = (
        f"Original user request:\n{user_prompt or '(n/a)'}\n\n"
        f"Draft ModuleSpec:\n{json.dumps(slim, default=str)[:7000]}"
    )
    from app.ai_domain_nouns import domain_noun_coverage

    _items, uncovered, noun_warnings = domain_noun_coverage(
        draft, user_prompt or str(draft.get("_user_prompt") or "")
    )
    if uncovered:
        prompt += (
            "\n\nMANDATORY REPAIRS — prompt nouns without models (add substantive models):\n"
            + ", ".join(uncovered)
        )
    raw = provider.generate_json(
        prompt,
        system=system,
        timeout_s=90.0,
        reasoning=True,
        temperature=STEP_TEMPERATURES["critique"],
    )
    data = _extract_json(raw)
    if not isinstance(data, dict):
        raise ValueError("critique response was not a JSON object")
    return data


def _apply_missing_fields(draft: dict[str, Any], missing: list[Any]) -> list[str]:
    notes: list[str] = []
    by_model = {
        m.get("model"): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    for row in missing:
        if not isinstance(row, dict):
            continue
        mid = row.get("model")
        fname = row.get("name")
        if not mid or not fname or mid not in by_model:
            continue
        fname = str(fname)
        if not _FIELD_RE.fullmatch(fname):
            continue
        model = by_model[mid]
        existing = {
            f.get("name")
            for f in (model.get("fields") or [])
            if isinstance(f, dict)
        }
        if fname in existing:
            notes.append(f"critique: merged (already present) {mid}.{fname}")
            continue
        field: dict[str, Any] = {
            "name": fname,
            "ttype": str(row.get("ttype") or "char"),
            "string": str(row.get("string") or fname),
        }
        if row.get("required"):
            field["required"] = True
        if row.get("relation"):
            field["relation"] = row["relation"]
        if row.get("selection"):
            field["selection"] = row["selection"]
        model.setdefault("fields", []).append(field)
        notes.append(f"critique: added field {mid}.{fname}")
    return notes


def _apply_missing_models(draft: dict[str, Any], missing: list[Any]) -> list[str]:
    notes: list[str] = []
    existing = {
        m.get("model")
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
    }
    for row in missing:
        if not isinstance(row, dict) or not row.get("model"):
            continue
        mid = str(row["model"])
        if not mid.startswith("x_") or mid in existing:
            continue
        fields = row.get("fields") if isinstance(row.get("fields"), list) else []
        clean_fields = []
        for f in fields:
            if isinstance(f, dict) and isinstance(f.get("name"), str) and _FIELD_RE.fullmatch(f["name"]):
                clean_fields.append(f)
        if not any(f.get("name") == "x_name" for f in clean_fields):
            clean_fields.insert(
                0,
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
            )
        draft.setdefault("models", []).append(
            {
                "model": mid,
                "description": str(row.get("description") or mid),
                "mode": "new",
                "fields": clean_fields,
            }
        )
        existing.add(mid)
        notes.append(f"critique: added model {mid}")
    return notes


def _apply_missing_automations(draft: dict[str, Any], missing: list[Any]) -> list[str]:
    notes: list[str] = []
    known_models = {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    names = {
        a.get("name")
        for a in (draft.get("automations") or [])
        if isinstance(a, dict)
    }
    allowed_kinds = {
        "object_write",
        "update_field",
        "related_write",
        "next_activity",
        "create_activity",
        "mail_post",
    }
    alias = {
        "x_hearing": "x_event",
        "x_appointment": "x_event",
        "x_schedule": "x_event",
    }
    for row in missing:
        if not isinstance(row, dict) or not row.get("name") or not row.get("model"):
            continue
        if row["name"] in names:
            continue
        mid = str(row["model"])
        if mid not in known_models:
            mid = alias.get(mid, mid)
        if mid not in known_models and mid.startswith("x_"):
            notes.append(
                f"critique: skipped automation {row['name']} (unknown model {row['model']})"
            )
            continue
        trigger = str(row.get("trigger") or "on_write")
        domain = row.get("filter_domain")
        if trigger == "on_write" and not (
            isinstance(domain, str) and domain.strip()
        ):
            notes.append(
                f"critique: skipped automation {row['name']} "
                "(on_write requires filter_domain)"
            )
            continue
        raw_actions = row.get("safe_actions") or []
        if not isinstance(raw_actions, list) or not raw_actions:
            notes.append(f"critique: skipped empty automation {row['name']}")
            continue
        clean_actions = []
        for a in raw_actions:
            if not isinstance(a, dict):
                continue
            kind = str(a.get("kind") or a.get("action_kind") or "")
            if kind in {"code", "email_send", "python"} or a.get("code"):
                continue
            if kind and kind not in allowed_kinds:
                continue
            clean_actions.append(a)
        if not clean_actions:
            notes.append(f"critique: skipped unsafe automation {row['name']}")
            continue
        draft.setdefault("automations", []).append(
            {
                "name": row["name"],
                "model": mid,
                "trigger": trigger,
                "description": row.get("description") or "",
                "filter_domain": domain,
                "safe_actions": clean_actions,
                "source": "critique",
            }
        )
        names.add(row["name"])
        notes.append(f"critique: added automation {row['name']}")
    return notes


def _verify_repair_in_spec(draft: dict[str, Any], repair: str) -> bool:
    """Return True when a logged repair is present in the final ModuleSpec."""
    m = _REPAIR_ADDED_FIELD.match(repair)
    if m:
        mid, fname = m.group(1), m.group(2)
        for model in draft.get("models") or []:
            if not isinstance(model, dict) or str(model.get("model")) != mid:
                continue
            return fname in {
                str(f.get("name"))
                for f in (model.get("fields") or [])
                if isinstance(f, dict)
            }
        return False
    m = _REPAIR_ADDED_MODEL.match(repair)
    if m:
        mid = m.group(1)
        return mid in {
            str(x.get("model"))
            for x in (draft.get("models") or [])
            if isinstance(x, dict)
        }
    m = _REPAIR_ADDED_AUTO.match(repair)
    if m:
        name = m.group(1)
        return name in {
            str(a.get("name"))
            for a in (draft.get("automations") or [])
            if isinstance(a, dict)
        }
    return True


def _draft_has_inventory_coverage(draft: dict[str, Any]) -> bool:
    inv = ("inventory", "stock", "warehouse", "replenish", "count")
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        blob = f"{model.get('model')} {model.get('description')}".lower()
        if any(k in blob for k in inv):
            return True
    reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
    for mid in reuse.get("models") or []:
        if any(k in str(mid).lower() for k in inv):
            return True
    return False


def _scrub_stale_critique_notes(
    draft: dict[str, Any], notes_list: list[str]
) -> list[str]:
    if not _draft_has_inventory_coverage(draft):
        return notes_list
    return [n for n in notes_list if not _INVENTORY_NOTE_RE.search(str(n))]


def _filter_off_schema_checklist(checklist: list[Any]) -> list[Any]:
    allowed = {
        "audit_trail",
        "data_export",
        "access_rules",
        "menus",
        "views",
        "automations",
        "workflows",
        "depth",
        "reuse",
        "smart_buttons",
    }
    kept: list[Any] = []
    for row in checklist:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "")
        if cid and cid not in allowed:
            continue
        kept.append(row)
    return kept


def finalize_critique_block(draft: dict[str, Any]) -> list[str]:
    """Reconcile `_critique.repairs` with the final spec after post-repair passes."""
    crit = draft.get("_critique")
    if not isinstance(crit, dict):
        return []
    warnings: list[str] = []
    raw_repairs = list(crit.get("repairs") or [])
    verified: list[str] = []
    suggestions = list(crit.get("suggestions") or [])
    for repair in raw_repairs:
        if repair.startswith("critique: added") and not _verify_repair_in_spec(
            draft, repair
        ):
            suggestion = repair.replace("critique: ", "unapplied: ", 1)
            if suggestion not in suggestions:
                suggestions.append(suggestion)
            warnings.append(f"critique: ghost repair removed — {repair}")
            continue
        if repair.startswith(("critique: skipped", "shape:")):
            if repair not in suggestions:
                suggestions.append(repair)
            continue
        verified.append(repair)
    notes_list = _scrub_stale_critique_notes(
        draft, list(crit.get("notes") or [])
    )
    checklist = _filter_off_schema_checklist(list(crit.get("checklist") or []))
    ready = bool(crit.get("ready"))
    if suggestions and ready:
        ready = False
    if not notes_list and verified and not suggestions:
        ready = True
    crit["repairs"] = verified
    crit["suggestions"] = suggestions
    crit["notes"] = notes_list
    crit["checklist"] = checklist
    crit["ready"] = ready
    draft["_critique"] = crit
    return warnings


def _normalize_critique_block(
    critique: dict[str, Any],
    applied_repairs: list[str],
    *,
    suggestions: list[str] | None = None,
) -> dict[str, Any]:
    ready = bool(critique.get("ready"))
    notes_list = list(critique.get("notes") or [])
    raw_checklist = list(critique.get("checklist") or [])
    checklist = _filter_off_schema_checklist(raw_checklist)
    sug = list(suggestions or [])
    if (
        not ready
        and not notes_list
        and not raw_checklist
        and not applied_repairs
        and not sug
    ):
        ready = True
    if not ready and not notes_list:
        notes_list = [
            "Critique flagged not ready but gave no details — review completeness/depth gaps"
        ]
    return {
        "ready": ready,
        "checklist": checklist,
        "notes": notes_list,
        "repairs": [r for r in applied_repairs if r.startswith("critique: added")],
        "suggestions": [
            *sug,
            *(r for r in applied_repairs if not r.startswith("critique: added")),
        ],
    }


def apply_critique_repairs(
    draft: dict[str, Any], critique: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    from app.ai_llm_status import validate_draft_response_shape

    out = copy.deepcopy(draft)
    out, shape_w = validate_draft_response_shape(out)
    applied: list[str] = []
    suggestions: list[str] = list(shape_w)
    # LLM enrichment steps occasionally return a bare model object — never splice at root.
    if isinstance(critique.get("model"), str) and str(critique.get("model", "")).startswith("x_"):
        if not critique.get("missing_models") and isinstance(critique.get("fields"), list):
            critique = {
                "missing_models": [critique],
                "missing_fields": critique.get("missing_fields") or [],
                "missing_automations": critique.get("missing_automations") or [],
                "notes": critique.get("notes") or [],
            }
            suggestions.append("shape: wrapped bare model LLM response into missing_models")
    from app.ai_model_quality import filter_redundant_missing_models

    applied.extend(_apply_missing_fields(out, critique.get("missing_fields") or []))
    filtered = filter_redundant_missing_models(
        out, critique.get("missing_models") or []
    )
    skipped = len(critique.get("missing_models") or []) - len(filtered)
    if skipped:
        suggestions.append(
            f"critique: skipped {skipped} hollow/thin/redundant missing_model(s)"
        )
    applied.extend(_apply_missing_models(out, filtered))
    applied.extend(_apply_missing_automations(out, critique.get("missing_automations") or []))
    if any(n.startswith("critique: added") for n in applied):
        from app.ai_post_critique import run_post_critique_pipeline

        applied.extend(
            run_post_critique_pipeline(
                out,
                user_prompt=str(out.get("_user_prompt") or ""),
                original_names=draft,
            )
        )
    out["_critique"] = _normalize_critique_block(
        critique, applied, suggestions=suggestions
    )
    notes = applied + suggestions
    return out, notes


def run_self_critique(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    provider: LLMProvider | None = None,
    repair: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """Evaluate draft; optionally repair gaps. Always safe if LLM unavailable."""
    warnings: list[str] = []
    out = copy.deepcopy(draft)
    from app.ai_domain_nouns import domain_noun_coverage

    # Deterministic baseline always
    checklist = completeness_checklist(out, user_prompt=user_prompt)
    out["_completeness"] = checklist
    gaps = [c["id"] for c in checklist if not c.get("ok")]
    _noun_items, uncovered, noun_warnings = domain_noun_coverage(out, user_prompt)
    warnings.extend(noun_warnings)
    ambition = out.get("_ambition") or classify_ambition(user_prompt)
    d_gaps = depth_gaps(out, ambition if ambition in {"thin", "standard", "comprehensive"} else "standard")  # type: ignore[arg-type]
    if d_gaps:
        warnings.append(f"critique(depth) gaps: {', '.join(d_gaps)}")
    if gaps:
        warnings.append(f"critique(deterministic) gaps: {', '.join(gaps)}")

    if not critique_enabled():
        return out, warnings

    provider = provider if provider is not None else get_llm_provider()
    if provider is None:
        warnings.append("critique: LLM unavailable — deterministic checklist only")
        out["_critique"] = {
            "ready": not gaps and not d_gaps,
            "checklist": checklist,
            "mode": "deterministic",
            "depth_gaps": d_gaps,
        }
        return out, warnings

    # Skip LLM only when structural + depth floors both pass
    if (
        not gaps
        and not d_gaps
        and settings.ai_critique.strip().lower() == "auto"
    ):
        out["_critique"] = {
            "ready": True,
            "checklist": checklist,
            "mode": "skipped_complete",
            "depth_gaps": [],
        }
        return out, warnings

    try:
        critique = llm_critique(provider, out, user_prompt=user_prompt)
        if repair:
            out, repair_notes = apply_critique_repairs(out, critique)
            warnings.extend(repair_notes)
            # Refresh completeness after repairs
            out["_completeness"] = completeness_checklist(out, user_prompt=user_prompt)
        else:
            out["_critique"] = _normalize_critique_block(critique, [])
        warnings.append(
            "critique: LLM pass "
            + ("ready" if critique.get("ready") else "needs_work")
        )
    except (LLMError, ValueError, json.JSONDecodeError) as exc:
        logger.info("LLM critique skipped: %s", exc)
        warnings.append(f"critique: LLM pass skipped ({exc})")
        out["_critique"] = {
            "ready": not gaps,
            "checklist": checklist,
            "mode": "deterministic_fallback",
            "error": str(exc),
        }

    return out, warnings


__all__ = [
    "critique_enabled",
    "run_self_critique",
    "apply_critique_repairs",
    "finalize_critique_block",
    "llm_critique",
]
