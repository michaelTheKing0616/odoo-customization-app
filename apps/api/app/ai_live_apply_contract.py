"""Live UI apply contract for ModuleSpec drafts.

Generation must stamp every field Community live-apply needs. Apply stays
defensive, but a finished draft is not 10.0-complete unless this contract is empty.

Domain-agnostic. Python / OWL / QWeb stay Option A (module → sandbox → promote). Elite tests and
i18n templates are zip hygiene, not a live-apply Option A surface.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

TRIGGER_ALIASES: dict[str, str] = {
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

DATE_FIELD_CANDIDATES = (
    "x_date_end",
    "x_date_due",
    "x_due_date",
    "x_end_date",
    "x_end_time",
    "x_deadline",
    "date_deadline",
    "x_date_start",
    "x_start_date",
    "create_date",
    "write_date",
)

MAIL_TODO_XML_ID = "mail.mail_activity_data_todo"
_ACTIVITY_KINDS = {"create_activity", "next_activity"}
_DATE_TOKENS = ("date", "time", "due", "deadline", "end", "start")
_ACTIVITY_MIXINS = ("mail.thread", "mail.activity.mixin")


def normalize_automation_trigger(raw: Any) -> str | None:
    """Map draft trigger aliases onto Odoo AutomationTrigger values."""
    if raw is None or raw is False:
        return "on_write"
    s = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in s:
        s = s.replace("__", "_")
    if not s.startswith("on_") and f"on_{s}" in TRIGGER_ALIASES:
        s = f"on_{s}"
    return TRIGGER_ALIASES.get(s)


def infer_trg_date_field(
    spec: dict[str, Any],
    auto: dict[str, Any],
    *,
    field_exists: Callable[[str, str], bool] | None = None,
) -> str | None:
    """on_time requires a date field; drafts often only put it in filter_domain."""
    for key in ("trg_date_field_name", "date_field", "trg_date_field"):
        raw = auto.get(key)
        if raw:
            return str(raw)

    fd = str(auto.get("filter_domain") or "")
    mentioned = re.findall(r"['\"]([a-z0-9_]+)['\"]", fd)
    mid = str(auto.get("model") or "")
    spec_names: set[str] = set()
    for model in spec.get("models") or []:
        if not isinstance(model, dict) or str(model.get("model") or "") != mid:
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or not field.get("name"):
                continue
            fname = str(field.get("name"))
            spec_names.add(fname)

    def _exists(name: str) -> bool:
        if name in spec_names:
            return True
        if field_exists and mid:
            try:
                return bool(field_exists(mid, name))
            except Exception:  # noqa: BLE001
                return False
        return False

    for fname in mentioned:
        low = fname.lower()
        if not any(tok in low for tok in _DATE_TOKENS):
            continue
        if _exists(fname) or not spec_names:
            return fname
    for hint in DATE_FIELD_CANDIDATES:
        if _exists(hint):
            return hint
    return "create_date" if mid else None


def _models_index(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for model in draft.get("models") or []:
        if isinstance(model, dict) and model.get("model"):
            out[str(model["model"])] = model
    return out


def _iter_actions(auto: dict[str, Any]) -> list[dict[str, Any]]:
    actions = auto.get("safe_actions") or auto.get("actions") or []
    if isinstance(auto.get("action"), dict):
        actions = [auto["action"], *list(actions or [])]
    return [a for a in actions if isinstance(a, dict)]


def _has_activity_action(auto: dict[str, Any]) -> bool:
    for action in _iter_actions(auto):
        kind = str(action.get("kind") or action.get("action_kind") or "")
        if kind in _ACTIVITY_KINDS:
            return True
    return False


def _ensure_mail_depends(draft: dict[str, Any]) -> bool:
    deps = list(draft.get("depends") or [])
    if "mail" in deps:
        return False
    deps.append("mail")
    draft["depends"] = deps
    return True


def _option_a_runtime_block(block: dict[str, Any]) -> bool:
    from app.ai_option_a_quality import is_option_a_runtime_block

    return is_option_a_runtime_block(block)


def _option_a_items(draft: dict[str, Any]) -> list[str]:
    from app.ai_option_a_quality import dedupe_option_a_items

    items: list[str] = []
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict) or not _option_a_runtime_block(block):
            continue
        path = str(
            block.get("source_file") or block.get("path") or block.get("filename") or ""
        )
        kind = str(block.get("kind") or block.get("language") or "python")
        reason = str(block.get("reason") or "")
        label = path or kind
        if reason:
            label = f"{label} — {reason}" if path else reason
        items.append(label)
    return dedupe_option_a_items(items)


def _field_names(model: dict[str, Any]) -> set[str]:
    return {
        str(f.get("name"))
        for f in (model.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }


_PYTHONISH_VALUE_RE = re.compile(r"\b(if|else|lambda)\b|[*/]")


def _is_currency_companion(field: dict[str, Any]) -> bool:
    """Stored currency M2O only — related x_currency_id is created after its hop."""
    if field.get("related"):
        return False
    name = str(field.get("name") or "")
    relation = str(field.get("relation") or "")
    ttype = str(field.get("ttype") or "").lower()
    return ttype == "many2one" and (
        relation == "res.currency" or name.endswith("currency_id")
    )


def _is_monetary_field(field: dict[str, Any]) -> bool:
    return str(field.get("ttype") or "").lower() == "monetary"


def _needs_currency_companion(field: dict[str, Any]) -> bool:
    return _is_monetary_field(field) or bool(field.get("currency_field"))


def _action_is_unapplyable(action: dict[str, Any]) -> bool:
    kind = str(action.get("kind") or action.get("action_kind") or "")
    field = str(action.get("field") or "")
    value = str(action.get("value") or "").strip()
    if kind == "mail_post":
        return True
    if kind == "object_write" and field and value == field:
        return True
    compact = value.replace(" ", "")
    if kind in {"mail_post", "object_write"} and "%(" in compact:
        return True
    if kind == "object_write" and value and _PYTHONISH_VALUE_RE.search(value):
        return True
    return False


def _stamp_currency_before_monetary(draft: dict[str, Any]) -> list[str]:
    """Odoo rejects monetary create when currency_field is not already on the model."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        monetary = [f for f in fields if _needs_currency_companion(f)]
        if not monetary:
            continue
        mid = str(model.get("model") or "")
        currency_name = next(
            (
                str(f.get("currency_field") or "").strip()
                for f in monetary
                if str(f.get("currency_field") or "").strip()
            ),
            "x_currency_id",
        )
        for field in monetary:
            if str(field.get("currency_field") or "").strip():
                continue
            field["currency_field"] = currency_name
            notes.append(
                f"live_apply: stamped currency_field on {mid}.{field.get('name')}"
            )
        names = _field_names(model)
        added_currency = False
        if currency_name not in names and not any(
            _is_currency_companion(f) for f in fields
        ):
            fields.insert(
                0,
                {
                    "name": currency_name,
                    "ttype": "many2one",
                    "relation": "res.currency",
                    "string": "Currency",
                },
            )
            added_currency = True
            notes.append(f"live_apply: added {mid}.{currency_name} for monetary fields")
        currency_fields = [f for f in fields if _is_currency_companion(f)]
        rest = [f for f in fields if not _is_currency_companion(f)]
        out: list[dict[str, Any]] = []
        inserted = False
        for field in rest:
            if not inserted and _needs_currency_companion(field):
                out.extend(currency_fields)
                inserted = True
            out.append(field)
        if not inserted:
            out = currency_fields + rest
        before_names = [str(f.get("name") or "") for f in (model.get("fields") or []) if isinstance(f, dict)]
        after_names = [str(f.get("name") or "") for f in out]
        model["fields"] = out
        if added_currency or before_names != after_names:
            notes.append(f"live_apply: {mid}.{currency_name} precedes monetary")
    return notes


def _stamp_drop_stock_o2ms(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        kept: list[dict[str, Any]] = []
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            rel = str(field.get("relation") or "")
            if field.get("ttype") == "one2many" and rel and not rel.startswith("x_"):
                notes.append(
                    f"live_apply: dropped O2M {mid}.{field.get('name')} "
                    f"(stock {rel} is a smart-button target, not a form O2M)"
                )
                continue
            kept.append(field)
        model["fields"] = kept
    return notes


def _stamp_related_after_hops(draft: dict[str, Any]) -> list[str]:
    """Drop related fields whose hop is missing; keep related after the hop field."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        names = {str(f.get("name") or "") for f in fields}
        kept: list[dict[str, Any]] = []
        related_rows: list[dict[str, Any]] = []
        for field in fields:
            related = str(field.get("related") or "").strip()
            if not related:
                kept.append(field)
                continue
            hop = related.split(".")[0]
            if hop not in names:
                notes.append(
                    f"live_apply: dropped {mid}.{field.get('name')} "
                    f"(related hop {hop} missing)"
                )
                continue
            related_rows.append(field)
        out: list[dict[str, Any]] = []
        pending = list(related_rows)
        for field in kept:
            out.append(field)
            fname = str(field.get("name") or "")
            still: list[dict[str, Any]] = []
            for related_field in pending:
                hop = str(related_field.get("related") or "").split(".")[0]
                if hop == fname:
                    out.append(related_field)
                else:
                    still.append(related_field)
            pending = still
        out.extend(pending)
        before = [str(f.get("name") or "") for f in fields]
        after = [str(f.get("name") or "") for f in out]
        model["fields"] = out
        if before != after:
            notes.append(f"live_apply: related fields after hops on {mid}")
    return notes


def stamp_live_apply_contract(draft: dict[str, Any]) -> list[str]:
    """Rewrite automations/models so live UI apply can succeed on the first try."""
    notes: list[str] = []
    notes.extend(_stamp_related_after_hops(draft))
    notes.extend(_stamp_currency_before_monetary(draft))
    notes.extend(_stamp_drop_stock_o2ms(draft))
    by_id = _models_index(draft)
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return notes

    kept: list[dict[str, Any]] = []
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        name = str(auto.get("name") or "")
        mid = str(auto.get("model") or "")
        if any(_action_is_unapplyable(a) for a in _iter_actions(auto)):
            notes.append(f"live_apply: dropped automation {name!r} (non-metadata action)")
            continue
        trigger_norm = normalize_automation_trigger(auto.get("trigger"))
        if not trigger_norm:
            notes.append(f"live_apply: dropped automation {name!r} (unsupported trigger)")
            continue
        if str(auto.get("trigger") or "") != trigger_norm:
            auto["trigger"] = trigger_norm
            notes.append(f"live_apply: canonical trigger {name!r} → {trigger_norm}")

        if trigger_norm.startswith("on_time"):
            date_field = infer_trg_date_field(draft, auto)
            if not date_field:
                notes.append(f"live_apply: dropped time automation {name!r} (no date field)")
                continue
            if auto.get("trg_date_field_name") != date_field:
                auto["trg_date_field_name"] = date_field
                notes.append(f"live_apply: stamped {date_field} on {name!r}")

        if _has_activity_action(auto):
            model = by_id.get(mid)
            if model is None:
                notes.append(f"live_apply: dropped automation {name!r} (missing model)")
                continue
            stock_inherit = str(model.get("mode") or "new") == "inherit" and not mid.startswith(
                "x_"
            )
            if not stock_inherit:
                mixins = [str(x) for x in (model.get("mixins") or [])]
                added = False
                for mixin in _ACTIVITY_MIXINS:
                    if mixin not in mixins:
                        mixins.append(mixin)
                        added = True
                if added:
                    model["mixins"] = mixins
                    notes.append(f"live_apply: mail.activity mixin on {mid}")
                model["is_mail_activity"] = True
                model["is_mail_thread"] = True
                if _ensure_mail_depends(draft):
                    notes.append("live_apply: added mail to depends")
            for action in _iter_actions(auto):
                kind = str(action.get("kind") or action.get("action_kind") or "")
                if kind not in _ACTIVITY_KINDS:
                    continue
                if not action.get("summary"):
                    action["summary"] = "Follow up"
                if not action.get("activity_type_id") and not action.get(
                    "activity_type_xml_id"
                ):
                    action["activity_type_xml_id"] = MAIL_TODO_XML_ID
                    notes.append(f"live_apply: To Do xml_id on {name!r}")
        kept.append(auto)

    draft["automations"] = kept
    return notes


def live_apply_contract_findings(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Read-only gaps that would skip or Fault on live UI apply."""
    findings: list[dict[str, Any]] = []
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        names = _field_names(model)
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            fname = str(field.get("name") or "")
            rel = str(field.get("relation") or "")
            related = str(field.get("related") or "").strip()
            if related:
                hop = related.split(".")[0]
                if hop and hop not in names:
                    findings.append(
                        {
                            "dimension": "hygiene",
                            "element": f"{mid}.{fname}",
                            "detail": f"live apply: related hop {hop} missing",
                        }
                    )
            if field.get("ttype") == "one2many" and rel and not rel.startswith("x_"):
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": f"{mid}.{fname}",
                        "detail": (
                            f"live apply: O2M onto stock {rel} has no inverse"
                        ),
                    }
                )
            if not _is_monetary_field(field):
                continue
            currency_name = str(field.get("currency_field") or "x_currency_id")
            has_currency = currency_name in names or any(
                _is_currency_companion(f)
                for f in (model.get("fields") or [])
                if isinstance(f, dict)
            )
            if not has_currency:
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": f"{mid}.{fname}",
                        "detail": (
                            f"live apply: monetary missing {currency_name}"
                        ),
                    }
                )
                continue
            ordered = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
            cur_i = next(
                (
                    i
                    for i, f in enumerate(ordered)
                    if str(f.get("name") or "") == currency_name or _is_currency_companion(f)
                ),
                -1,
            )
            mon_i = next(
                (i for i, f in enumerate(ordered) if str(f.get("name") or "") == fname),
                -1,
            )
            if 0 <= mon_i <= cur_i or cur_i < 0:
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": f"{mid}.{fname}",
                        "detail": (
                            f"live apply: {currency_name} must precede monetary"
                        ),
                    }
                )
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        name = str(auto.get("name") or "automation")
        mid = str(auto.get("model") or "")
        if any(_action_is_unapplyable(a) for a in _iter_actions(auto)):
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": name,
                    "detail": "live apply: identity or Python-shaped automation action",
                }
            )
            continue
        trigger_norm = normalize_automation_trigger(auto.get("trigger"))
        if not trigger_norm:
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": name,
                    "detail": "live apply: unsupported automation trigger",
                }
            )
            continue
        if trigger_norm.startswith("on_time") and not auto.get("trg_date_field_name"):
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": name,
                    "detail": "live apply: on_time missing trg_date_field_name",
                }
            )
        if not _has_activity_action(auto):
            continue
        model = by_id.get(mid)
        if model is None:
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": name,
                    "detail": "live apply: next_activity model missing from spec",
                }
            )
            continue
        mixins = {str(x) for x in (model.get("mixins") or [])}
        stock_inherit = str(model.get("mode") or "new") == "inherit" and not mid.startswith("x_")
        if (
            not stock_inherit
            and "mail.activity.mixin" not in mixins
            and not model.get("is_mail_activity")
        ):
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": mid,
                    "detail": "live apply: next_activity needs mail.activity.mixin",
                }
            )
    findings.extend(_search_arch_field_findings(draft, by_id))
    try:
        from app.ai_document_compiler import premium_surface_findings

        findings.extend(premium_surface_findings(draft))
    except Exception:  # noqa: BLE001
        pass
    return findings


_SEARCH_FILTER_TAG = re.compile(r"<filter\b[^>]*/>", re.I)
_SEARCH_DOMAIN_FIELD = re.compile(r"""\(['\"]([A-Za-z_][\w.]*)['\"]\s*,""")
_SEARCH_GROUP_BY_FIELD = re.compile(
    r"""['\"]group_by['\"]\s*:\s*['\"]([^'\"]+)['\"]"""
)
_SEARCH_OK_LEAVES = frozenset({"id", "display_name"})


def _search_arch_field_findings(
    draft: dict[str, Any], by_id: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Search filter domain/group_by must name a field on the model."""
    findings: list[dict[str, Any]] = []
    for view in draft.get("views") or []:
        if not isinstance(view, dict) or str(view.get("type") or "") != "search":
            continue
        mid = str(view.get("model") or "")
        model = by_id.get(mid)
        if not model:
            continue
        names = _field_names(model)
        arch = str(view.get("arch") or "")
        missing: list[str] = []
        for tag in _SEARCH_FILTER_TAG.findall(arch):
            for raw in _SEARCH_DOMAIN_FIELD.findall(tag):
                leaf = raw.split(".")[0]
                if leaf not in _SEARCH_OK_LEAVES and leaf not in names:
                    missing.append(leaf)
            gb = _SEARCH_GROUP_BY_FIELD.search(tag)
            if gb and gb.group(1) not in names:
                missing.append(gb.group(1))
        if missing:
            uniq = ", ".join(sorted(set(missing)))
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": f"{mid}.search",
                    "detail": f"live apply: search filter names missing field(s) {uniq}",
                }
            )
    return findings


def attach_live_apply_contract(draft: dict[str, Any]) -> list[str]:
    """Stamp, then record whether the draft is live-apply ready."""
    notes = stamp_live_apply_contract(draft)
    findings = live_apply_contract_findings(draft)
    option_a = _option_a_items(draft)
    from app.ai_option_a_quality import done_bar_for_draft

    done_bar = done_bar_for_draft(
        draft, prompt=str(draft.get("_user_prompt") or "")
    )
    draft["_done_bar"] = done_bar
    draft["_go_live_ready"] = bool(done_bar.get("go_live_ready"))
    from app.ai_generation_engine import is_stock_reuse_draft

    stock_reuse = is_stock_reuse_draft(draft)
    live_ready = False if stock_reuse else not findings
    draft["_live_apply"] = {
        "ready": live_ready,
        "findings": findings,
        "option_a": option_a,
        "done_bar": done_bar,
        "go_live_ready": bool(done_bar.get("go_live_ready")),
    }
    # Wire Certification beside done-bar (Phase 0/3) without redefining completeness
    try:
        from app.ai_certification import stamp_certification

        if isinstance(draft.get("_scorecard"), dict):
            stamp_certification(draft)
            draft["_live_apply"]["certification_tier"] = (
                draft.get("_certification") or {}
            ).get("tier")
    except Exception:  # noqa: BLE001
        pass
    meta = draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}
    models = [m for m in (draft.get("models") or []) if isinstance(m, dict)]
    draft["_meta"] = {
        **meta,
        "live_apply_ready": live_ready,
        "option_a_block_count": len(option_a),
        "go_live_ready": bool(done_bar.get("go_live_ready")),
        "done_bar_mode": done_bar.get("mode"),
        "certification_tier": (draft.get("_certification") or {}).get("tier")
        if isinstance(draft.get("_certification"), dict)
        else meta.get("certification_tier"),
        "model_count": len(models),
        "view_count": len(draft.get("views") or []),
        "menu_count": len(draft.get("menus") or []),
        "smart_button_count": len(draft.get("smart_buttons") or []),
        "automation_count": len(draft.get("automations") or []),
    }
    if stock_reuse:
        notes.append("live_apply: n/a — stock_reuse (use Job Autopilot)")
    elif findings:
        notes.append(f"live_apply: {len(findings)} remaining gap(s)")
    else:
        notes.append("live_apply: contract ready")
    return notes
