"""Post-critique pipeline — scaffold critique-added models (GEN2-10)."""

from __future__ import annotations

import copy
import re
from typing import Any

# Shared with derive_draft_naming_from_prompt slug stop-words.
NOUN_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "with",
        "for",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "from",
        "around",
        "world",
        "that",
        "this",
        "our",
        "your",
        "my",
        "i",
        "we",
        "want",
        "need",
        "build",
        "create",
        "make",
        "large",
        "mega",
        "multiple",
        "full",
        "simple",
        "basic",
        "management",
        "system",
        "app",
        "application",
        "module",
        "custom",
        "odoo",
        "super",
        "market",
        "store",
    }
)

_LINE_PARENT_DUP_FIELDS = frozenset(
    {
        "x_from_branch_id",
        "x_to_branch_id",
        "x_branch_from_id",
        "x_branch_to_id",
        "x_transfer_date",
        "x_date",
        "x_country_id",
        "x_company_id",
    }
)


def _models_index(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def _infer_line_parent_model(line_id: str, by_id: dict[str, dict[str, Any]]) -> str | None:
    """x_branch_transfer_line → x_branch_transfer when present."""
    if not line_id.endswith("_line"):
        return None
    base = line_id[: -len("_line")]
    if base in by_id:
        return base
    # x_order_line may parent to x_store_order via existing m2o
    for mid, model in by_id.items():
        if mid == line_id:
            continue
        for f in model.get("fields") or []:
            if not isinstance(f, dict):
                continue
            if f.get("ttype") == "one2many" and f.get("relation") == line_id:
                return mid
    return None


def ensure_line_model_parent_links(draft: dict[str, Any]) -> list[str]:
    """Line models must m2o their parent; drop duplicated header fields."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for mid, model in list(by_id.items()):
        if not mid.endswith("_line"):
            continue
        parent_id = _infer_line_parent_model(mid, by_id)
        if not parent_id:
            continue
        parent = by_id.get(parent_id)
        if not parent:
            continue
        parent_leaf = parent_id.replace("x_", "")
        fk_name = f"x_{parent_leaf}_id"
        if parent_leaf.endswith("_line"):
            fk_name = f"x_{parent_leaf.rsplit('_', 1)[0]}_id"
        # Standard: x_branch_transfer → x_transfer_id on line
        if parent_id.endswith("_transfer"):
            fk_name = "x_transfer_id"
        elif parent_id.endswith("_order"):
            fk_name = "x_order_id"
        elif parent_id == "x_inventory_count":
            fk_name = "x_count_id"

        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        names = {str(f.get("name")) for f in fields}
        kept = [
            f
            for f in fields
            if str(f.get("name")) not in _LINE_PARENT_DUP_FIELDS
            or str(f.get("name")) == fk_name
        ]
        if len(kept) != len(fields):
            notes.append(f"post_critique: stripped duplicate header fields on {mid}")
            model["fields"] = kept
            names = {str(f.get("name")) for f in kept}

        if fk_name not in names:
            model.setdefault("fields", []).append(
                {
                    "name": fk_name,
                    "ttype": "many2one",
                    "relation": parent_id,
                    "string": str(parent.get("description") or parent_id),
                    "required": False,
                    "source": "post_critique_line",
                }
            )
            notes.append(f"post_critique: linked {mid}.{fk_name} → {parent_id}")

        o2m_name = f"x_{mid.replace('x_', '')}_ids"
        if mid.startswith("x_") and mid.endswith("_line"):
            short = mid.replace("x_", "").replace("_line", "")
            o2m_name = f"x_{short}_line_ids"
        parent_fields = list(parent.get("fields") or [])
        if not any(
            isinstance(f, dict)
            and f.get("ttype") == "one2many"
            and f.get("relation") == mid
            for f in parent_fields
        ):
            parent_fields.append(
                {
                    "name": o2m_name,
                    "ttype": "one2many",
                    "relation": mid,
                    "relation_field": fk_name,
                    "string": str(model.get("description") or "Lines"),
                    "source": "post_critique_line",
                }
            )
            parent["fields"] = parent_fields
            notes.append(f"post_critique: added O2M {parent_id}.{o2m_name} → {mid}")

        existing_btns = {
            (b.get("on_model"), b.get("related_model"))
            for b in (draft.get("smart_buttons") or [])
            if isinstance(b, dict)
        }
        if (parent_id, mid) not in existing_btns:
            draft.setdefault("smart_buttons", []).append(
                {
                    "on_model": parent_id,
                    "label": str(model.get("description") or "Lines"),
                    "related_model": mid,
                    "relation_field": fk_name,
                    "icon": "fa-list",
                }
            )
            notes.append(f"post_critique: smart button {parent_id} → {mid}")
    return notes


def rewrite_critique_automations(draft: dict[str, Any]) -> list[str]:
    """Fix on_create auto-confirm combos; humanize names; fill empty descriptions."""
    notes: list[str] = []
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return notes
    kept: list[dict[str, Any]] = []
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        name = str(auto.get("name") or "")
        if "_" in name and name == name.lower():
            human = name.replace("_", " ").strip().title()
            auto["name"] = human
            notes.append(f"post_critique: humanized automation name → {human!r}")
        if not str(auto.get("description") or "").strip():
            auto["description"] = str(auto.get("name") or "Automation")
        trigger = str(auto.get("trigger") or "")
        actions = auto.get("safe_actions") or []
        if trigger == "on_create" and isinstance(actions, list):
            writes_status = any(
                isinstance(a, dict)
                and str(a.get("kind") or "") in {"object_write", "update_field"}
                and str(a.get("field") or a.get("target_field") or "") in {"x_status", "status"}
                for a in actions
            )
            if writes_status:
                auto["safe_actions"] = [
                    {
                        "kind": "mail_post",
                        "body": f"Record created ({auto.get('name')})",
                    }
                ]
                notes.append(
                    f"post_critique: rewrote on_create status-write automation {auto.get('name')!r}"
                )
        kept.append(auto)
    draft["automations"] = kept
    return notes


def ensure_workflow_models_have_state_field(draft: dict[str, Any]) -> list[str]:
    """Workflow models with x_status must carry state_field + is_workflow."""
    notes: list[str] = []
    from app.ai_workflow import ensure_workflow_transitions_on_draft

    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        names = {
            str(f.get("name"))
            for f in (model.get("fields") or [])
            if isinstance(f, dict)
        }
        if "x_status" not in names:
            continue
        if not model.get("is_workflow"):
            model["is_workflow"] = True
            notes.append(f"post_critique: promoted {mid} to workflow (x_status)")
        if not isinstance(model.get("state_field"), dict):
            model["state_field"] = {"field": "x_status"}
            notes.append(f"post_critique: added state_field on {mid}")
    notes.extend(ensure_workflow_transitions_on_draft(draft))
    from app.ai_workflow_semantic import apply_semantic_workflow_pass

    notes.extend(apply_semantic_workflow_pass(draft))
    return notes


def flag_near_duplicate_label_fields(draft: dict[str, Any]) -> list[str]:
    """Warn when same label maps to char + m2o (x_address vs x_address_id)."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        by_label: dict[str, list[str]] = {}
        for f in model.get("fields") or []:
            if not isinstance(f, dict):
                continue
            label = str(f.get("string") or "").strip().lower()
            if not label:
                continue
            by_label.setdefault(label, []).append(str(f.get("ttype") or ""))
        for label, ttypes in by_label.items():
            if len(ttypes) >= 2 and "char" in ttypes and "many2one" in ttypes:
                notes.append(
                    f"post_critique: near-dup label {label!r} char+m2o on {mid}"
                )
    return notes


def preserve_prompt_derived_names(
    draft: dict[str, Any], *, original: dict[str, Any] | None = None
) -> list[str]:
    """Keep prompt-derived technical_name/display_name after pack merge."""
    notes: list[str] = []
    if not original:
        return notes
    for key in ("technical_name", "display_name"):
        orig = original.get(key)
        cur = draft.get(key)
        if (
            orig
            and cur
            and str(orig) != str(cur)
            and str(cur) in {"retail_supermarket", "custom_app"}
        ):
            draft[key] = orig
            notes.append(f"post_critique: preserved {key} {orig!r} over pack {cur!r}")
    return notes


def verify_model_ui_completeness(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-model checklist: list+form views, action, menu, access."""
    by_id = _models_index(draft)
    actions = {
        str(a.get("model"))
        for a in (draft.get("actions") or [])
        if isinstance(a, dict) and a.get("model")
    }
    view_types: dict[str, set[str]] = {}
    for v in draft.get("views") or []:
        if isinstance(v, dict) and v.get("model"):
            view_types.setdefault(str(v["model"]), set()).add(str(v.get("type") or ""))
    access_models = {
        str(r.get("model") or "").replace("model_", "")
        for r in (draft.get("access_rules") or [])
        if isinstance(r, dict)
    }
    menu_actions = {
        str(m.get("action_xml_id") or "")
        for m in (draft.get("menus") or [])
        if isinstance(m, dict)
    }
    action_xml = {
        str(a.get("technical_name") or ""): str(a.get("model") or "")
        for a in (draft.get("actions") or [])
        if isinstance(a, dict)
    }
    items: list[dict[str, Any]] = []
    for mid in sorted(by_id):
        vt = view_types.get(mid, set())
        has_lf = "list" in vt or "tree" in vt
        has_form = "form" in vt
        has_views = has_lf and has_form
        act = mid in actions
        act_xml_id = next(
            (xml for xml, m in action_xml.items() if m == mid),
            f"action_{mid.replace('x_', '')}",
        )
        has_menu = act_xml_id in menu_actions
        has_access = mid in access_models or f"model_{mid.replace('.', '_')}" in access_models
        ok = has_views and act and has_access
        detail_parts = []
        if not has_views:
            detail_parts.append("missing list/form views")
        if not act:
            detail_parts.append("missing action")
        if not has_menu:
            detail_parts.append("missing menu")
        if not has_access:
            detail_parts.append("missing access")
        items.append(
            {
                "id": f"model_ui:{mid}",
                "ok": ok,
                "detail": "; ".join(detail_parts) if detail_parts else "complete",
            }
        )
    return items


def run_post_critique_pipeline(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    original_names: dict[str, Any] | None = None,
) -> list[str]:
    """Full post-critique pass: normalize → line links → scaffold UI."""
    notes: list[str] = []
    from app.ai_model_quality import (
        normalize_selection_field_shapes,
        repair_draft_integrity,
    )

    notes.extend(normalize_selection_field_shapes(draft))
    notes.extend(ensure_workflow_models_have_state_field(draft))
    notes.extend(ensure_line_model_parent_links(draft))
    notes.extend(rewrite_critique_automations(draft))
    notes.extend(flag_near_duplicate_label_fields(draft))
    if original_names:
        notes.extend(preserve_prompt_derived_names(draft, original=original_names))
    notes.extend(
        repair_draft_integrity(draft, ambition=str(draft.get("_ambition") or "standard"))
    )
    from app.ai_enrich import ensure_default_ui, sync_form_archs_to_models
    from app.ai_rules import apply_pattern_rules, validate_and_enrich_draft

    notes.extend(ensure_default_ui(draft))
    notes.extend(apply_pattern_rules(draft))
    notes.extend(sync_form_archs_to_models(draft))
    _out, rule_w, _errs = validate_and_enrich_draft(draft)
    notes.extend(rule_w)
    ui_items = verify_model_ui_completeness(draft)
    comp = list(draft.get("_completeness") or [])
    comp = [c for c in comp if not str(c.get("id", "")).startswith("model_ui:")]
    comp.extend(ui_items)
    draft["_completeness"] = comp
    missing_ui = [c["id"] for c in ui_items if not c.get("ok")]
    if missing_ui:
        notes.append(f"post_critique: UI gaps remain: {', '.join(missing_ui)}")
    return notes


__all__ = [
    "NOUN_STOPWORDS",
    "ensure_line_model_parent_links",
    "flag_near_duplicate_label_fields",
    "preserve_prompt_derived_names",
    "rewrite_critique_automations",
    "run_post_critique_pipeline",
    "verify_model_ui_completeness",
]
