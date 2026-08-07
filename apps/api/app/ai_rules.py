"""Deterministic validation + enrichment rules for ModuleSpec drafts.

LLM proposes; this layer disposes — referential integrity, statusbar/sequence
hints, partner back-refs, overdue automation safety net.
"""

from __future__ import annotations

import copy
from typing import Any


from app.ai_reuse_planner import REUSE_BUILTIN_MODELS

_BUILTIN_MODELS = set(REUSE_BUILTIN_MODELS) | {
    "res.partner",
    "res.users",
    "res.company",
    "res.currency",
    "product.product",
    "product.template",
    "account.move",
    "mail.thread",
    "ir.attachment",
    "calendar.event",
    "project.project",
    "project.task",
    "hr.employee",
    "uom.uom",
}

# Draft filter_domain / action fields often omit the x_ prefix — repair when possible.
_TRIGGER_NORMALIZE = {
    "create": "on_create",
    "write": "on_write",
    "update": "on_write",
    "unlink": "on_unlink",
    "delete": "on_unlink",
    "create_or_write": "on_create_or_write",
}


def _models_index(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for m in draft.get("models") or []:
        if isinstance(m, dict) and m.get("model"):
            out[str(m["model"])] = m
    return out


def _field_names(model: dict[str, Any]) -> set[str]:
    return {
        str(f["name"])
        for f in (model.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }


def check_referential_integrity(draft: dict[str, Any]) -> list[str]:
    """Every relation must point at a declared or known stock model."""
    errors: list[str] = []
    known = set(_models_index(draft)) | _BUILTIN_MODELS
    # Also allow reuse.models
    reuse = draft.get("reuse") or {}
    if isinstance(reuse, dict):
        for m in reuse.get("models") or []:
            if isinstance(m, str):
                known.add(m)
    for hint in draft.get("reuse_hints") or []:
        if isinstance(hint, dict) and hint.get("model"):
            known.add(str(hint["model"]))

    for mid, model in _models_index(draft).items():
        for f in model.get("fields") or []:
            if not isinstance(f, dict):
                continue
            rel = f.get("relation")
            if not rel:
                continue
            if str(rel) not in known:
                errors.append(
                    f"orphan relation {mid}.{f.get('name')} → {rel} "
                    "(not in draft models / builtins / reuse)"
                )
    for btn in draft.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        for key in ("on_model", "related_model"):
            m = btn.get(key)
            if m and str(m) not in known and not str(m).startswith("x_"):
                # x_ models should be in draft; if missing, flag
                pass
            if m and str(m) not in known:
                errors.append(f"smart_button {key}={m} not in known models")
    return errors


def _ensure_sequence_field(model: dict[str, Any]) -> bool:
    """Add x_code sequence-style field on workflow models if missing."""
    names = _field_names(model)
    if "x_code" in names or "x_reference" in names or "x_name" in names:
        # Prefer dedicated code when status workflow present and no x_code
        if "x_status" in names and "x_code" not in names:
            fields = list(model.get("fields") or [])
            # Insert after x_name if present
            code = {
                "name": "x_code",
                "ttype": "char",
                "string": "Reference",
                "help": "Wire ir.sequence (e.g. REC/00001) — configure sequence on apply",
            }
            insert_at = 1 if fields and fields[0].get("name") == "x_name" else 0
            fields.insert(insert_at, code)
            model["fields"] = fields
            return True
    return False


def _ensure_partner_backref_smart_button(
    draft: dict[str, Any], model: dict[str, Any]
) -> bool:
    """If model M2Os to res.partner, suggest smart button metadata on partner reuse."""
    mid = model.get("model")
    leaf = str(mid or "").replace("x_", "")
    # Skip seed noise / pure child lines — Contacts stays focused
    if model.get("source") == "depth_seed" and not model.get("is_workflow"):
        return False
    if leaf.endswith("_line") or leaf.endswith("line"):
        return False
    partner_fields = [
        f
        for f in (model.get("fields") or [])
        if isinstance(f, dict)
        and f.get("relation") == "res.partner"
        and f.get("name")
    ]
    if not partner_fields or not mid:
        return False
    existing = {
        (b.get("on_model"), b.get("related_model"), b.get("relation_field"))
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    # Already have several partner buttons — don't pile on
    partner_count = sum(
        1
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict) and b.get("on_model") == "res.partner"
    )
    if partner_count >= 4:
        return False
    added = False
    for f in partner_fields[:1]:  # one back-ref per model
        key = ("res.partner", mid, f["name"])
        if key in existing:
            continue
        draft.setdefault("smart_buttons", []).append(
            {
                "on_model": "res.partner",
                "label": str(model.get("description") or mid),
                "related_model": mid,
                "relation_field": f["name"],
                "icon": "fa-list",
                "requires_inherit_view": True,
                "note": "Applied as inherit on Contacts button_box",
            }
        )
        added = True
    return added


def _ensure_overdue_automation(draft: dict[str, Any], model: dict[str, Any]) -> bool:
    from app.ai_workflow import active_states_from_transitions, parse_selection_keys

    mid = str(model.get("model") or "")
    names = _field_names(model)
    if "x_status" not in names:
        return False
    due_fields = [
        n
        for n in names
        if any(k in n for k in ("return", "due", "expiry", "deadline"))
    ]
    if not due_fields:
        return False
    autos = draft.get("automations") or []
    if not isinstance(autos, list):
        autos = []
    blob = json_dumps_lower(autos)
    if "overdue" in blob:
        return False
    sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
    states = sf.get("states") or parse_selection_keys(
        next(
            (f.get("selection") for f in (model.get("fields") or []) if isinstance(f, dict) and f.get("name") == "x_status"),
            None,
        )
    )
    transitions = sf.get("transitions") or []
    active = active_states_from_transitions(
        [str(s) for s in states] if states else [],
        transitions if isinstance(transitions, list) else [],
    )
    status_clause = ""
    if active:
        status_clause = f", ('x_status', 'in', {active!r})"
    draft.setdefault("automations", []).append(
        {
            "name": f"Flag overdue on {mid}",
            "model": mid,
            "trigger": "on_time",
            "description": (
                f"Safety-net: when {due_fields[0]} is past and still in active states → overdue"
            ),
            "filter_domain": f"[('{due_fields[0]}', '<', 'now'){status_clause}]",
            "safe_actions": [
                {"kind": "object_write", "field": "x_status", "value": "overdue"},
                {"kind": "next_activity", "summary": "Overdue follow-up"},
            ],
            "source": "rules_engine",
        }
    )
    return True


def json_dumps_lower(obj: Any) -> str:
    import json

    try:
        return json.dumps(obj).lower()
    except TypeError:
        return str(obj).lower()


def _known_field_names(draft: dict[str, Any]) -> dict[str, set[str]]:
    return {mid: _field_names(m) for mid, m in _models_index(draft).items()}


def repair_smart_buttons_and_automations(draft: dict[str, Any]) -> list[str]:
    """Fix common LLM slips: missing x_ on relation_field, bare create/write triggers."""
    notes: list[str] = []
    fields_by_model = _known_field_names(draft)
    buttons = draft.get("smart_buttons")
    if isinstance(buttons, list):
        cleaned: list[dict[str, Any]] = []
        for btn in buttons:
            if not isinstance(btn, dict):
                continue
            b = dict(btn)
            target = str(b.get("related_model") or "")
            rel = b.get("relation_field")
            if isinstance(rel, str) and rel and target:
                names = fields_by_model.get(target) or set()
                if rel not in names and f"x_{rel}" in names:
                    b["relation_field"] = f"x_{rel}"
                    notes.append(
                        f"rules: smart_button relation_field {rel!r} → {b['relation_field']!r} "
                        f"on {target}"
                    )
                elif rel not in names and not rel.startswith("x_"):
                    # Prefer inventing x_ prefix when target model exists in draft
                    if target in fields_by_model:
                        b["relation_field"] = f"x_{rel}"
                        notes.append(
                            f"rules: prefixed smart_button relation_field → {b['relation_field']!r}"
                        )
            cleaned.append(b)
        draft["smart_buttons"] = cleaned

    autos = draft.get("automations")
    if isinstance(autos, list):
        for auto in autos:
            if not isinstance(auto, dict):
                continue
            trig = auto.get("trigger")
            if isinstance(trig, str):
                key = trig.strip().lower().replace("-", "_").replace(" ", "_")
                mapped = _TRIGGER_NORMALIZE.get(key)
                if mapped:
                    auto["trigger"] = mapped
                    notes.append(f"rules: automation trigger {trig!r} → {mapped!r}")
            # Prefer x_status in filter_domain when status used
            fd = auto.get("filter_domain")
            if isinstance(fd, str) and "'status'" in fd and "'x_status'" not in fd:
                model = str(auto.get("model") or "")
                names = fields_by_model.get(model) or set()
                if "x_status" in names:
                    auto["filter_domain"] = fd.replace("'status'", "'x_status'")
                    notes.append(
                        f"rules: filter_domain status → x_status on automation "
                        f"{auto.get('name')!r}"
                    )
    return notes


def apply_pattern_rules(draft: dict[str, Any]) -> list[str]:
    """Mutate draft with deterministic enrichments. Returns warning notes."""
    notes: list[str] = []
    out = draft
    notes.extend(repair_smart_buttons_and_automations(out))
    for model in out.get("models") or []:
        if not isinstance(model, dict):
            continue
        names = _field_names(model)
        if "x_status" in names:
            from app.ai_model_quality import is_party_link_model

            if not is_party_link_model(model):
                model["is_workflow"] = True
            if _ensure_sequence_field(model):
                notes.append(
                    f"rules: added x_code reference on workflow model {model.get('model')}"
                )
            if _ensure_overdue_automation(out, model):
                notes.append(
                    f"rules: suggested overdue automation for {model.get('model')}"
                )
        if _ensure_partner_backref_smart_button(out, model):
            notes.append(
                f"rules: partner back-ref smart button for {model.get('model')}"
            )

        # mail.thread mixin hint for workflow / transactional models
        if model.get("is_workflow") or "x_status" in names:
            mixins = list(model.get("mixins") or [])
            if "mail.thread" not in mixins:
                mixins.append("mail.thread")
                notes.append(f"rules: mail.thread mixin on {model.get('model')}")
            if "mail.activity.mixin" not in mixins and model.get("is_workflow"):
                mixins.append("mail.activity.mixin")
            model["mixins"] = mixins
            depends = list(out.get("depends") or ["base"])
            if "mail" not in depends:
                depends.append("mail")
                out["depends"] = depends

    # Default access stubs — user (no unlink) + manager (full) per x_* model
    existing_access = {
        str(r.get("model") or "").replace("model_", "", 1)
        for r in (out.get("access_rules") or [])
        if isinstance(r, dict)
    }
    rules = list(out.get("access_rules") or []) if isinstance(out.get("access_rules"), list) else []
    tech = str(out.get("technical_name") or "custom_app")
    user_group = f"group_{tech}_user"
    mgr_group = f"group_{tech}_manager"
    groups = list(out.get("groups") or []) if isinstance(out.get("groups"), list) else []
    group_ids = {g.get("id") for g in groups if isinstance(g, dict)}
    if user_group not in group_ids:
        groups.append(
            {
                "id": user_group,
                "name": f"{out.get('display_name') or tech} User",
                "category_id": "base.module_category_custom",
            }
        )
    if mgr_group not in group_ids:
        groups.append(
            {
                "id": mgr_group,
                "name": f"{out.get('display_name') or tech} Manager",
                "implied_ids": [user_group],
                "category_id": "base.module_category_custom",
            }
        )
    out["groups"] = groups
    added_acl = 0
    for model in out.get("models") or []:
        if not isinstance(model, dict) or not model.get("model"):
            continue
        mid = str(model["model"])
        if not mid.startswith("x_"):
            continue
        xml = "model_" + mid.replace(".", "_")
        if mid in existing_access or xml.replace("model_", "", 1) in existing_access:
            continue
        if any(isinstance(r, dict) and r.get("model") == xml for r in rules):
            continue
        rules.append(
            {
                "id": f"access_{mid.replace('.', '_')}_user",
                "name": f"{model.get('description') or mid} user",
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
                "name": f"{model.get('description') or mid} manager",
                "model": xml,
                "group": mgr_group,
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 1,
            }
        )
        added_acl += 2
    if added_acl:
        out["access_rules"] = rules
        notes.append(
            f"rules: added {added_acl // 2} model(s) with user (no unlink) + manager access"
        )
    elif not out.get("access_rules") and out.get("models"):
        rules = []
        for model in out["models"]:
            if not isinstance(model, dict) or not model.get("model"):
                continue
            mid = str(model["model"])
            if not mid.startswith("x_"):
                continue
            xml = "model_" + mid.replace(".", "_")
            rules.append(
                {
                    "id": f"access_{mid.replace('.', '_')}_user",
                    "name": f"{model.get('description') or mid} user",
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
                    "name": f"{model.get('description') or mid} manager",
                    "model": xml,
                    "group": mgr_group,
                    "perm_read": 1,
                    "perm_write": 1,
                    "perm_create": 1,
                    "perm_unlink": 1,
                }
            )
        if rules:
            out["access_rules"] = rules
            notes.append(
                f"rules: added {len(rules) // 2} default user/manager access rule pair(s)"
            )

    menus = list(out.get("menus") or []) if isinstance(out.get("menus"), list) else []
    root_updated = 0
    for menu in menus:
        if not isinstance(menu, dict):
            continue
        is_root = not menu.get("parent_xml_id") and not menu.get("action_xml_id")
        if is_root or str(menu.get("xml_id") or "").startswith("menu_root_"):
            existing = list(menu.get("groups") or menu.get("group_xml_ids") or [])
            if user_group not in existing:
                menu["groups"] = [user_group]
                root_updated += 1
    if root_updated:
        out["menus"] = menus
        notes.append(f"rules: root menu restricted to {user_group}")

    return notes


def completeness_checklist(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    reuse_models: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Non-LLM production-readiness checklist (yes/no items) + depth floors."""
    from app.ai_depth import classify_ambition, depth_checklist
    from app.ai_domain_nouns import domain_noun_coverage

    models = _models_index(draft)
    items: list[dict[str, Any]] = []

    def add(key: str, ok: bool, detail: str = "") -> None:
        items.append({"id": key, "ok": ok, "detail": detail})

    add("has_models", bool(models), f"{len(models)} model(s)")
    add("has_menus", bool(draft.get("menus")), "")
    by_id = _models_index(draft)
    view_types: dict[str, set[str]] = {}
    for v in draft.get("views") or []:
        if isinstance(v, dict) and v.get("model"):
            view_types.setdefault(str(v["model"]), set()).add(str(v.get("type") or ""))
    models_missing_views = [
        mid
        for mid in by_id
        if not (
            ("list" in view_types.get(mid, set()) or "tree" in view_types.get(mid, set()))
            and "form" in view_types.get(mid, set())
        )
    ]
    add(
        "has_views",
        not models_missing_views,
        ",".join(models_missing_views) if models_missing_views else f"{len(view_types)} model view sets",
    )
    workflow_models = [
        mid for mid, m in models.items() if "x_status" in _field_names(m)
    ]
    workflow = [models[mid] for mid in workflow_models]
    add(
        "has_workflow",
        bool(workflow_models),
        ",".join(workflow_models) if workflow_models else "none",
    )
    has_kanban = any(
        isinstance(v, dict) and v.get("type") == "kanban" for v in (draft.get("views") or [])
    )
    add(
        "kanban_for_workflow",
        (not workflow) or has_kanban,
        "kanban present" if has_kanban else "missing kanban",
    )
    has_mail = any(
        "mail.thread" in (m.get("mixins") or []) for m in models.values() if isinstance(m, dict)
    )
    add("mail_thread", has_mail or not workflow, "")
    has_seq = any("x_code" in _field_names(m) for m in workflow) if workflow else True
    add("sequence_on_workflow", has_seq, "")
    add("has_access_stubs", bool(draft.get("access_rules")), "")
    add("has_smart_buttons", bool(draft.get("smart_buttons")), "")
    partner_links = any(
        isinstance(f, dict) and f.get("relation") == "res.partner"
        for m in models.values()
        for f in (m.get("fields") or [])
    )
    add("contacts_link", partner_links, "res.partner M2O present" if partner_links else "none")

    if user_prompt.strip():
        noun_items, _uncovered, _noun_w = domain_noun_coverage(
            draft, user_prompt, reuse_models=reuse_models
        )
        items.extend(noun_items)

    ambition = draft.get("_ambition")
    if ambition not in {"thin", "standard", "comprehensive"}:
        ambition = classify_ambition(user_prompt) if user_prompt else "standard"
    items.extend(depth_checklist(draft, ambition))  # type: ignore[arg-type]
    return items


def validate_and_enrich_draft(
    draft: dict[str, Any],
    *,
    apply_rules: bool = True,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Return (draft, warnings, errors). Errors are soft unless caller raises."""
    out = copy.deepcopy(draft)
    warnings: list[str] = []
    errors = check_referential_integrity(out)
    if apply_rules:
        warnings.extend(apply_pattern_rules(out))
        # Re-check after rules may add partner smart buttons pointing at known models
        errors = check_referential_integrity(out)
    checklist = completeness_checklist(out)
    out["_completeness"] = checklist
    missing = [c["id"] for c in checklist if not c["ok"]]
    if missing:
        warnings.append(f"completeness gaps: {', '.join(missing)}")
    for err in errors:
        warnings.append(f"integrity: {err}")
    return out, warnings, errors


def strip_protected_module_effects(
    draft: dict[str, Any],
    *,
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Remove tier-1 effects; return (cleaned, refusals, warnings)."""
    from app.protected_enforcement import (
        check_automation_create,
        pcm_refusal,
        scrub_spec_for_protected_apply,
    )

    out, skips = scrub_spec_for_protected_apply(draft, manifest)
    refusals: list[dict[str, Any]] = []
    warnings: list[str] = list(skips)

    for skip in skips:
        if skip.startswith("automation:"):
            mod = "tier-1"
            if "protected:tier_1:" in skip:
                mod = skip.split("protected:tier_1:", 1)[1].split(":", 1)[0]
            refusals.append(
                pcm_refusal(
                    requested_capability="automation with tier-1 write effect",
                    protected_module=mod,
                    kind="automation_strip",
                    reason=skip,
                )
            )
        elif skip.startswith("model:"):
            mod = skip.split(":", 2)[1].split(":")[0] if skip.count(":") >= 2 else "tier-1"
            refusals.append(
                pcm_refusal(
                    requested_capability=f"inherit or mutate tier-1 model {mod}",
                    protected_module=mod,
                    kind="inherit_strip",
                    model=mod,
                    reason=skip,
                )
            )
        elif skip.startswith("field:") or skip.startswith("smart_button:"):
            target = skip.split(":", 2)[1] if skip.count(":") >= 2 else "tier-1"
            mod = target.split(".")[0] if "." in target else target
            refusals.append(
                pcm_refusal(
                    requested_capability="protected field or smart button mutation",
                    protected_module=mod,
                    kind="spec_strip",
                    reason=skip,
                )
            )

    autos = out.get("automations")
    if isinstance(autos, list):
        kept_autos: list[Any] = []
        for auto in autos:
            if not isinstance(auto, dict):
                kept_autos.append(auto)
                continue
            auto_model = str(auto.get("model") or auto.get("res_model") or "")
            actions = auto.get("safe_actions") or auto.get("actions") or []
            kind = "update_field"
            target: str | None = None
            if isinstance(actions, list) and actions and isinstance(actions[0], dict):
                kind = str(actions[0].get("kind") or actions[0].get("type") or "update_field")
                for tk in ("target_model", "model", "res_model", "relation"):
                    if actions[0].get(tk):
                        target = str(actions[0].get(tk))
                        break
            kind_map = {
                "next_activity": "create_activity",
                "object_write": "update_field",
                "object_create": "create_record",
            }
            kind = kind_map.get(kind, kind)
            viol = check_automation_create(
                manifest,
                model=auto_model,
                action_kind=kind,
                target_model=target,
            )
            if viol:
                refusals.append(
                    pcm_refusal(
                        requested_capability=f"automation {kind!r}",
                        protected_module=viol.model,
                        safe_alternative=viol.safe_alternative,
                        kind="automation_strip",
                        model=viol.model,
                        reason=viol.reason,
                    )
                )
                warnings.append(f"PCM: removed automation on {viol.model}")
                continue
            kept_autos.append(auto)
        out["automations"] = kept_autos

    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for r in refusals:
        key = (str(r.get("protected_module", "")), str(r.get("requested_capability", "")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    return out, unique, warnings


__all__ = [
    "validate_and_enrich_draft",
    "check_referential_integrity",
    "apply_pattern_rules",
    "completeness_checklist",
    "repair_smart_buttons_and_automations",
    "strip_protected_module_effects",
]
