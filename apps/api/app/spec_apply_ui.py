"""Apply ModuleSpec-like JSON to live Odoo: models, fields, views, menus, smart buttons."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from odoo_client import CreateFieldRequest, FieldType, OdooClient
from odoo_client.actions import CreateSmartButtonBundle
from odoo_client.blueprint import auto_form_layout_for_model
from odoo_client.models import CreateViewRequest
from odoo_client.view_arch import (
    ButtonNode,
    FieldNode,
    FormViewSpec,
    GroupNode,
    render_form_arch,
)

from app.project_apply import ApplyResult, apply_project_spec


@dataclass
class UiApplyResult(ApplyResult):
    views_created: int = 0
    views_updated: int = 0
    menus_created: int = 0
    smart_buttons: int = 0
    automations_noted: int = 0
    automations_created: int = 0
    access_rights_created: int = 0
    record_rules_created: int = 0


def _selection_keys(selection: Any) -> list[str]:
    if not isinstance(selection, str):
        return []
    import re

    return re.findall(r"\('([^']+)'\s*,", selection)


def _apply_explicit_views(client: OdooClient, spec: dict[str, Any], result: UiApplyResult) -> None:
    views = spec.get("views") or []
    if not isinstance(views, list):
        return
    for view in views:
        if not isinstance(view, dict):
            continue
        model = view.get("model")
        vtype = view.get("type")
        arch = view.get("arch")
        name = view.get("name") or f"{model}.{vtype}"
        if not model or not vtype or not isinstance(arch, str) or not arch.strip():
            continue
        # Never overwrite stock module primary arches (Contacts phone xpath, etc.).
        if not str(model).startswith("x_"):
            result.warnings.append(
                f"Skip view {name}: refusing to rewrite stock model {model} "
                "(use Designer inherit / smart-button inject)"
            )
            continue
        if not client.model_exists(str(model)):
            result.warnings.append(f"Skip view {name}: model {model} missing")
            continue
        try:
            existing = client.find_view(str(model), str(vtype), primary_only=True)
            if existing is None:
                existing = client.find_view(str(model), str(vtype))
            if existing is None:
                client.create_view(
                    CreateViewRequest(
                        name=str(name),
                        model=str(model),
                        type=str(vtype),  # type: ignore[arg-type]
                        arch=arch,
                    )
                )
                result.views_created += 1
            else:
                client.update_view_arch(existing.id, arch)
                result.views_updated += 1
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"View {name} failed: {exc}")


def _polish_forms_with_statusbar(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    """If draft has no form arch for a model, apply heuristic layout + statusbar."""
    models = spec.get("models") or []
    if not isinstance(models, list):
        return
    views = spec.get("views") or []
    form_models = {
        v.get("model")
        for v in views
        if isinstance(v, dict) and v.get("type") == "form" and v.get("arch")
    }
    smart_by_model: dict[str, list[dict[str, Any]]] = {}
    for btn in spec.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        norm = _normalize_smart_button(btn)
        if norm.get("on_model"):
            smart_by_model.setdefault(str(norm["on_model"]), []).append(norm)

    for model_entry in models:
        if not isinstance(model_entry, dict):
            continue
        model = model_entry.get("model")
        if not model or not isinstance(model, str):
            continue
        if not model.startswith("x_"):
            continue
        if model in form_models:
            continue
        if not client.model_exists(model):
            continue
        try:
            layout = auto_form_layout_for_model(
                client, model, string=str(model_entry.get("description") or model)
            )
            if layout is None:
                continue
            # Rebuild with statusbar via FormViewSpec when x_status exists
            field_rows = client.execute_kw(
                "ir.model.fields",
                "search_read",
                [[("model", "=", model), ("name", "=", "x_status")]],
                {"fields": ["selection"], "limit": 1},
            )
            button_box: list[ButtonNode] = []
            # Smart buttons injected after bundles created — polish here without actions
            statusbar = "x_status" if field_rows else None
            statusbar_visible = None
            if field_rows:
                # selection on ir.model.fields may be list of tuples already
                sel = field_rows[0].get("selection")
                if isinstance(sel, list):
                    keys = [str(t[0]) for t in sel if isinstance(t, (list, tuple)) and t]
                    statusbar_visible = ",".join(keys[:6]) if keys else None
                elif isinstance(sel, str):
                    keys = _selection_keys(sel)
                    statusbar_visible = ",".join(keys[:6]) if keys else None

            children: list[Any] = []
            for group in layout.groups:
                nodes = [FieldNode(name=f) for f in group.fields if f != "x_status"]
                if nodes:
                    children.append(GroupNode(string=group.string, children=nodes))

            arch = render_form_arch(
                FormViewSpec(
                    string=layout.string,
                    statusbar_field=statusbar,
                    statusbar_visible=statusbar_visible,
                    button_box=button_box,
                    children=children,
                )
            )
            primary = client.find_view(model, "form", primary_only=True) or client.find_view(
                model, "form"
            )
            if primary is None:
                client.create_view(
                    CreateViewRequest(
                        name=f"{model}.form",
                        model=model,
                        type="form",
                        arch=arch,
                    )
                )
                result.views_created += 1
            else:
                client.update_view_arch(primary.id, arch)
                result.views_updated += 1
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Form polish {model} failed: {exc}")


def _ensure_menus(client: OdooClient, spec: dict[str, Any], result: UiApplyResult) -> None:
    display = str(spec.get("display_name") or spec.get("technical_name") or "Custom App")
    models = [
        m
        for m in (spec.get("models") or [])
        if isinstance(m, dict)
        and m.get("model")
        and (m.get("mode") or "new") == "new"
        and str(m["model"]).startswith("x_")
    ]
    if not models:
        return
    entries = [
        (str(m["model"]), str(m.get("description") or m["model"])) for m in models
    ]
    try:
        menu_ids = client.ensure_app_menus(root_name=display, model_entries=entries)
        result.menus_created = len(menu_ids)
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Menus skipped: {exc}")


# AI / client aliases → ModuleSpec smart-button keys
_SMART_BUTTON_KEY_ALIASES: dict[str, str] = {
    "source_model": "on_model",
    "target_model": "related_model",
    "field": "relation_field",
    "m2o_field": "relation_field",
}


def _normalize_smart_button(btn: dict[str, Any]) -> dict[str, Any]:
    """Map draft/API key aliases onto on_model / related_model / relation_field."""
    out = dict(btn)
    for alias, canonical in _SMART_BUTTON_KEY_ALIASES.items():
        if out.get(canonical) in (None, "") and out.get(alias) not in (None, ""):
            out[canonical] = out[alias]
    return out


def _default_inverse_m2o_name(source_model: str) -> str:
    stem = str(source_model).replace(".", "_")
    if stem.startswith("x_"):
        stem = stem[2:]
    return f"x_{stem}_id"


def _ensure_m2o_on_target_for_smart_button(
    client: OdooClient,
    btn: dict[str, Any],
    result: UiApplyResult,
) -> str | None:
    """Ensure relation_field is a Many2one on *target* pointing at *source*.

    Odoo related-window domain is ``[('relation_field','=',active_id)]`` on the
    target model. AI drafts often put the M2O on the source (button host) or omit
    it — create / remap so apply does not skip the button.
    """
    source = btn.get("on_model")
    target = btn.get("related_model")
    rel = btn.get("relation_field")
    if not source or not target or not rel:
        return None
    source_s, target_s, rel_s = str(source), str(target), str(rel)

    if client.field_exists(target_s, rel_s):
        return rel_s

    # AI put FK on the button host instead of the related list model → create inverse.
    if client.field_exists(source_s, rel_s):
        inverse = _default_inverse_m2o_name(source_s)
        if client.field_exists(target_s, inverse):
            result.warnings.append(
                f"Smart button {source_s}→{target_s}: used {target_s}.{inverse} "
                f"(draft relation_field {rel_s!r} is on source, not target)"
            )
            return inverse
        try:
            client.create_field(
                CreateFieldRequest(
                    model=target_s,
                    name=inverse,
                    field_description=str(btn.get("label") or source_s),
                    ttype=FieldType.MANY2ONE,
                    relation=source_s,
                    on_delete="set_null",
                )
            )
            result.fields_created += 1
            result.warnings.append(
                f"Created {target_s}.{inverse} → {source_s} for smart button "
                f"(draft had {rel_s!r} on {source_s})"
            )
            return inverse
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(
                f"Smart button M2O on {target_s} failed (needed inverse of "
                f"{source_s}.{rel_s}): {exc}"
            )
            return None

    # Missing entirely — create the named M2O on target.
    try:
        name = rel_s if rel_s.startswith("x_") else f"x_{rel_s}"
        if not client.field_exists(target_s, name):
            client.create_field(
                CreateFieldRequest(
                    model=target_s,
                    name=name,
                    field_description=str(btn.get("label") or source_s),
                    ttype=FieldType.MANY2ONE,
                    relation=source_s,
                    on_delete="set_null",
                )
            )
            result.fields_created += 1
            result.warnings.append(
                f"Created {target_s}.{name} → {source_s} for smart button"
            )
        return name
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Smart button M2O on {target_s} failed: {exc}")
        return None


def _ensure_o2m_for_smart_button(
    client: OdooClient,
    btn: dict[str, Any],
    result: UiApplyResult,
) -> str | None:
    o2m = btn.get("one2many_field")
    source = btn.get("on_model")
    target = btn.get("related_model")
    rel = btn.get("relation_field")
    if not source or not target or not rel:
        return None
    if o2m and client.field_exists(str(source), str(o2m)):
        return str(o2m)
    # Create O2M if missing
    name = str(o2m or f"x_{str(target).replace('x_', '').replace('.', '_')}_ids")
    if not name.startswith("x_"):
        name = f"x_{name}"
    try:
        if not client.field_exists(str(source), name):
            client.create_field(
                CreateFieldRequest(
                    model=str(source),
                    name=name,
                    field_description=str(btn.get("label") or "Related"),
                    ttype=FieldType.ONE2MANY,
                    relation=str(target),
                    relation_field=str(rel),
                )
            )
            result.fields_created += 1
        return name
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"O2M for smart button skipped: {exc}")
        return None


def _apply_smart_buttons(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    buttons = spec.get("smart_buttons") or []
    if not isinstance(buttons, list):
        return
    # Collect button specs per source model then rewrite forms
    by_model: dict[str, list[ButtonNode]] = {}
    for raw_btn in buttons:
        if not isinstance(raw_btn, dict):
            continue
        btn = _normalize_smart_button(raw_btn)
        source = btn.get("on_model")
        target = btn.get("related_model")
        rel = btn.get("relation_field")
        if not source or not target or not rel:
            result.warnings.append(
                "Smart button skipped (need on_model/related_model/relation_field "
                f"or source_model/target_model aliases): {raw_btn!r}"
            )
            continue
        if not client.model_exists(str(source)) or not client.model_exists(str(target)):
            result.warnings.append(
                f"Smart button skipped (missing model): {source} → {target}"
            )
            continue
        resolved_rel = _ensure_m2o_on_target_for_smart_button(client, btn, result)
        if not resolved_rel:
            result.warnings.append(
                f"Smart button skipped (no M2O on {target} → {source}): "
                f"{btn.get('label') or rel}"
            )
            continue
        btn = {**btn, "relation_field": resolved_rel}
        o2m = _ensure_o2m_for_smart_button(client, btn, result)
        try:
            bundle = client.create_smart_button_bundle(
                CreateSmartButtonBundle(
                    name=str(btn.get("label") or "Open"),
                    source_model=str(source),
                    target_model=str(target),
                    relation_field=str(resolved_rel),
                    one2many_field=o2m,
                    create_count_field=bool(o2m),
                    icon=str(btn.get("icon") or "fa-list"),
                )
            )
            node = ButtonNode(
                string=str(btn.get("label") or "Open"),
                name=str(bundle.window_action.id),
                type="action",
                class_name="oe_stat_button",
                icon=str(btn.get("icon") or "fa-list"),
                count_field=bundle.count_field,
            )
            by_model.setdefault(str(source), []).append(node)
            result.smart_buttons += 1
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Smart button failed: {exc}")

    for model, nodes in by_model.items():
        try:
            _inject_button_box(client, model, nodes, result)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Inject smart buttons on {model}: {exc}")

def _inject_button_box(
    client: OdooClient,
    model: str,
    nodes: list[ButtonNode],
    result: UiApplyResult,
) -> None:
    """Inject smart buttons via a stable inherit view — never mutate the primary form.

    Stock forms (res.partner, …) keep their fields/xpaths intact; custom x_ forms
    get a button_box created if missing.
    """
    if not nodes:
        return
    info = client.inject_smart_buttons_into_form(model, nodes)
    result.views_updated += 1
    if not model.startswith("x_"):
        result.warnings.append(
            f"Smart buttons on {model} added via inherit view "
            f"{getattr(info, 'name', model + '.studio.smart_buttons')!s} "
            "(primary Contacts/stock form unchanged)"
        )


def _iter_safe_actions(auto: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize ModuleSpec automation shapes into action dicts."""
    actions: list[dict[str, Any]] = []
    for key in ("safe_actions", "actions"):
        raw = auto.get(key)
        if isinstance(raw, list):
            actions.extend([a for a in raw if isinstance(a, dict)])
    # Flat single-action drafts from older generators
    kind = auto.get("action_kind") or auto.get("kind")
    if kind and not actions:
        flat = {k: v for k, v in auto.items() if k not in {"name", "model", "trigger", "description"}}
        flat["kind"] = kind
        actions.append(flat)
    return actions


# LLM / Studio-ish trigger labels → AutomationTrigger values
_TRIGGER_ALIASES: dict[str, str] = {
    "create": "on_create",
    "oncreate": "on_create",
    "on_create": "on_create",
    "write": "on_write",
    "update": "on_write",
    "onwrite": "on_write",
    "on_write": "on_write",
    "create_or_write": "on_create_or_write",
    "create_write": "on_create_or_write",
    "on_create_or_write": "on_create_or_write",
    "unlink": "on_unlink",
    "delete": "on_unlink",
    "on_unlink": "on_unlink",
    "archive": "on_archive",
    "on_archive": "on_archive",
    "unarchive": "on_unarchive",
    "on_unarchive": "on_unarchive",
    "time": "on_time",
    "on_time": "on_time",
    "on_time_created": "on_time_created",
    "on_time_updated": "on_time_updated",
    "message_received": "on_message_received",
    "on_message_received": "on_message_received",
    "message_sent": "on_message_sent",
    "on_message_sent": "on_message_sent",
    "webhook": "on_webhook",
    "on_webhook": "on_webhook",
}


def _normalize_automation_trigger(raw: Any) -> str | None:
    """Map draft trigger aliases (create/write/…) onto AutomationTrigger values."""
    if raw is None or raw is False:
        return "on_write"
    s = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in s:
        s = s.replace("__", "_")
    if s.startswith("on_") is False and f"on_{s}" in _TRIGGER_ALIASES:
        s = f"on_{s}"
    return _TRIGGER_ALIASES.get(s)


def _action_from_spec(action: dict[str, Any]) -> Any | None:
    """Map draft action → typed safe action, or None if unsupported."""
    from odoo_client import (
        CreateActivityAction,
        RelatedWriteAction,
        UpdateFieldAction,
    )

    kind = str(action.get("kind") or action.get("action_kind") or "").strip()
    field = action.get("field_name") or action.get("field")
    value = action.get("value")
    # Kind omitted but field+value present → assume update / related write
    if not kind and field is not None and value is not None:
        if action.get("relation_field") or "." in str(field):
            kind = "related_write"
        else:
            kind = "update_field"
    if kind in {"related_write"}:
        relation = action.get("relation_field")
        if not relation and field and "." in str(field):
            relation, _, field = str(field).partition(".")
        if not relation or not field or value is None:
            return None
        return RelatedWriteAction(
            relation_field=str(relation),
            field_name=str(field),
            value=str(value),
        )
    if kind in {"update_field", "object_write", "set", "write_field"}:
        if not field or value is None:
            return None
        # Dotted path without explicit related_write → treat as related_write
        if "." in str(field) and not action.get("relation_field"):
            rel, _, fname = str(field).partition(".")
            if rel and fname:
                return RelatedWriteAction(
                    relation_field=rel, field_name=fname, value=str(value)
                )
        return UpdateFieldAction(field_name=str(field), value=str(value))
    if kind in {"create_activity", "next_activity"}:
        type_id = action.get("activity_type_id")
        if not type_id:
            return None
        return CreateActivityAction(
            activity_type_id=int(type_id),
            summary=str(action.get("summary") or "Follow up"),
            note=action.get("note"),
        )
    return None


def _apply_safe_automations(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    """Create safe automations from ModuleSpec (related_write, update_field, activity)."""
    from odoo_client import CreateAutomationRequest
    from odoo_client.automation import AutomationTrigger

    autos = spec.get("automations") or []
    if not isinstance(autos, list):
        return

    for auto in autos:
        if not isinstance(auto, dict):
            continue
        name = auto.get("name")
        model = auto.get("model")
        trigger_raw = auto.get("trigger") or "on_write"
        if not name or not model:
            result.warnings.append(f"Skipped automation missing name/model: {auto!r}")
            result.automations_noted += 1
            continue
        if not client.model_exists(str(model)):
            result.warnings.append(
                f"Skipped automation {name!r}: model {model} not found"
            )
            result.automations_noted += 1
            continue
        trigger_norm = _normalize_automation_trigger(trigger_raw)
        if not trigger_norm:
            result.warnings.append(
                f"Skipped automation {name!r}: unsupported trigger {trigger_raw!r}"
            )
            result.automations_noted += 1
            continue
        try:
            trigger = AutomationTrigger(trigger_norm)
        except ValueError:
            result.warnings.append(
                f"Skipped automation {name!r}: unsupported trigger {trigger_raw!r}"
            )
            result.automations_noted += 1
            continue

        actions = _iter_safe_actions(auto)
        if not actions:
            result.warnings.append(f"Automation {name!r} has no safe_actions")
            result.automations_noted += 1
            continue

        created_any = False
        for idx, action_spec in enumerate(actions):
            typed = _action_from_spec(action_spec)
            if typed is None:
                kind = action_spec.get("kind") or action_spec.get("action_kind")
                result.warnings.append(
                    f"Automation {name!r}: skipped unsupported/incomplete action {kind!r}"
                )
                result.automations_noted += 1
                continue
            auto_name = str(name) if idx == 0 else f"{name} ({idx + 1})"
            try:
                kwargs: dict[str, Any] = {
                    "name": auto_name,
                    "model": str(model),
                    "trigger": trigger,
                    "action": typed,
                    "filter_domain": auto.get("filter_domain"),
                    "active": bool(auto.get("active", True)),
                }
                if trigger.value.startswith("on_time"):
                    date_field = (
                        auto.get("trg_date_field_name")
                        or auto.get("date_field")
                        or action_spec.get("trg_date_field_name")
                    )
                    if not date_field:
                        result.warnings.append(
                            f"Skipped time automation {auto_name!r}: needs trg_date_field_name"
                        )
                        result.automations_noted += 1
                        continue
                    kwargs["trg_date_field_name"] = str(date_field)
                client.create_automation(CreateAutomationRequest(**kwargs))
                result.automations_created += 1
                created_any = True
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"Automation {auto_name!r} failed: {exc}")
                result.automations_noted += 1
        if not created_any and actions:
            pass  # warnings already recorded


def _resolve_draft_model_name(client: OdooClient, raw: Any) -> str | None:
    """Map access_rules model stubs (model_x_patient or x_patient) → live technical name."""
    if raw in (None, False, ""):
        return None
    m = str(raw).strip()
    if client.model_exists(m):
        return m
    if m.startswith("model_"):
        cand = m[len("model_") :]
        if client.model_exists(cand):
            return cand
    return None


def _apply_access_rules(
    client: OdooClient, spec: dict[str, Any], result: UiApplyResult
) -> None:
    """Apply draft access_rules: ir.model.access stubs and ir.rule when domain present."""
    from odoo_client.security import CreateAccessRightRequest, CreateRecordRuleRequest

    rules = spec.get("access_rules") or []
    if not isinstance(rules, list):
        return

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        model = _resolve_draft_model_name(client, rule.get("model"))
        if not model:
            result.warnings.append(
                f"Access rule skipped (unknown model): {rule.get('model')!r}"
            )
            continue
        name = str(rule.get("name") or f"access_{model.replace('.', '_')}")
        domain = rule.get("domain_force") or rule.get("domain")
        try:
            if domain not in (None, False, ""):
                client.create_record_rule(
                    CreateRecordRuleRequest(
                        model=model,
                        name=name,
                        domain_force=str(domain),
                        perm_read=bool(rule.get("perm_read", True)),
                        perm_write=bool(rule.get("perm_write", True)),
                        perm_create=bool(rule.get("perm_create", True)),
                        perm_unlink=bool(rule.get("perm_unlink", True)),
                        active=bool(rule.get("active", True)),
                    )
                )
                result.record_rules_created += 1
                continue

            group_ref = str(rule.get("group") or rule.get("group_xml_id") or "base.group_user")
            group_id = None
            if group_ref:
                try:
                    group_id = client.resolve_xml_id(group_ref)
                except Exception as exc:  # noqa: BLE001
                    result.warnings.append(
                        f"Access {name!r}: group {group_ref!r} unresolved ({exc}); "
                        "creating without group"
                    )
            # Idempotent: skip if same group already has a row
            existing = client.execute_kw(
                "ir.model.access",
                "search",
                [
                    [
                        ("model_id.model", "=", model),
                        ("group_id", "=", group_id) if group_id else ("group_id", "=", False),
                    ]
                ],
                {"limit": 1},
            )
            if existing:
                continue
            client.create_access_right(
                CreateAccessRightRequest(
                    model=model,
                    name=name,
                    group_id=group_id,
                    perm_read=bool(rule.get("perm_read", 1)),
                    perm_write=bool(rule.get("perm_write", 1)),
                    perm_create=bool(rule.get("perm_create", 1)),
                    perm_unlink=bool(rule.get("perm_unlink", 1)),
                    active=bool(rule.get("active", True)),
                )
            )
            result.access_rights_created += 1
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Access rule {name!r} failed: {exc}")


def _note_automations(spec: dict[str, Any], result: UiApplyResult) -> None:
    """Legacy note path — prefer _apply_safe_automations when apply_automations=True."""
    autos = spec.get("automations") or []
    if not isinstance(autos, list):
        return
    result.automations_noted = len([a for a in autos if isinstance(a, dict)])
    if result.automations_noted:
        result.warnings.append(
            f"{result.automations_noted} automation(s) in draft — not applied "
            "(apply_automations=false). Review Automations page or re-run with apply."
        )


def apply_module_spec_ui(
    client: OdooClient,
    spec: dict[str, Any],
    *,
    apply_views: bool = True,
    apply_menus: bool = True,
    apply_smart_buttons: bool = True,
    apply_automations: bool = True,
    apply_access: bool = True,
) -> UiApplyResult:
    """Create models/fields then generate UI from ModuleSpec JSON."""
    base = apply_project_spec(client, spec)
    result = UiApplyResult(
        models_created=base.models_created,
        fields_created=base.fields_created,
        skipped=base.skipped,
        warnings=list(base.warnings),
        message="",
    )

    if apply_views:
        _apply_explicit_views(client, spec, result)
        _polish_forms_with_statusbar(client, spec, result)
    if apply_menus:
        _ensure_menus(client, spec, result)
    if apply_smart_buttons:
        _apply_smart_buttons(client, spec, result)
    if apply_automations:
        _apply_safe_automations(client, spec, result)
    else:
        _note_automations(spec, result)
    if apply_access:
        _apply_access_rules(client, spec, result)

    result.message = (
        f"UI apply: {len(result.models_created)} model(s), {result.fields_created} field(s), "
        f"{result.views_created} view(s) created, {result.views_updated} updated, "
        f"{result.menus_created} menu(s), {result.smart_buttons} smart button(s), "
        f"{result.automations_created} automation(s), "
        f"{result.access_rights_created} access + {result.record_rules_created} record rule(s)"
    )
    return result


__all__ = ["UiApplyResult", "apply_module_spec_ui"]
