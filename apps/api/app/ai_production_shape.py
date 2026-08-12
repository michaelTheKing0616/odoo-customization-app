"""Production-shaped draft polish — search, sequences, money, rules, arch (GEN2-11)."""

from __future__ import annotations

import re
from html import escape
from typing import Any


def _models_index(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def _field_list(model: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in (model.get("fields") or []) if isinstance(f, dict)]


def _selection_keys(selection: Any) -> list[str]:
    if not isinstance(selection, str):
        return []
    return re.findall(r"\('([^']+)'\s*,", selection)


def ensure_search_views(draft: dict[str, Any]) -> list[str]:
    """Every actioned model gets a search arch with ≥2 filters."""
    notes: list[str] = []
    by_id = _models_index(draft)
    action_models = {
        str(a.get("model"))
        for a in (draft.get("actions") or [])
        if isinstance(a, dict) and a.get("model")
    }
    views = list(draft.get("views") or []) if isinstance(draft.get("views"), list) else []
    have_search = {
        str(v.get("model"))
        for v in views
        if isinstance(v, dict) and str(v.get("type") or "") == "search"
    }
    added = 0
    for mid in sorted(action_models):
        if mid in have_search or mid not in by_id:
            continue
        model = by_id[mid]
        fields = _field_list(model)
        names = {str(f.get("name")) for f in fields}
        filters: list[str] = []
        if "x_status" in names:
            status = next(f for f in fields if f.get("name") == "x_status")
            for key in _selection_keys(status.get("selection"))[:4]:
                filters.append(
                    f'<filter string="{escape(key.replace("_", " ").title())}" '
                    f'name="status_{key}" domain="[(\'x_status\',\'=\',\'{key}\')]"/>'
                )
        for df in ("x_date", "x_date_order", "x_date_due", "x_date_start"):
            if df in names:
                filters.append(
                    f'<filter string="This month" name="month_{df}" '
                    f'domain="[(\'{df}\',\'&gt;=\', (context_today().replace(day=1)).strftime(\'%Y-%m-%d\'))]"/>'
                )
                break
        for uf in ("x_user_id", "x_manager_id", "x_assigned_id"):
            if uf in names:
                filters.append(
                    f'<filter string="My records" name="my_{uf}" '
                    f'domain="[(\'{uf}\',\'=\', uid)]"/>'
                )
                break
        groupbys: list[str] = []
        for f in fields:
            if f.get("ttype") == "many2one":
                fname = str(f.get("name") or "")
                rel = str(f.get("relation") or "")
                if rel.startswith("x_") or rel in {
                    "res.partner",
                    "res.users",
                    "res.country",
                    "res.company",
                }:
                    groupbys.append(
                        f'<filter string="{escape(str(f.get("string") or fname))}" '
                        f'name="group_{fname}" '
                        f'context="{{\'group_by\': \'{fname}\'}}"/>'
                    )
        if "x_status" in names:
            groupbys.append(
                '<filter string="Status" name="group_x_status" '
                'context="{\'group_by\': \'x_status\'}"/>'
            )
        if len(filters) < 2:
            filters.append(
                f'<filter string="All" name="all" domain="[]"/>'
            )
            filters.append(
                f'<filter string="Has name" name="has_name" domain="[(\'x_name\',\'!=\',False)]"/>'
            )
        extra_groupbys = list(groupbys)
        if len(filters) < 2 and extra_groupbys:
            need = max(0, 2 - len(filters))
            filters.extend(extra_groupbys[:need])
            extra_groupbys = extra_groupbys[need:]
        arch = (
            f'<search string="{escape(str(model.get("description") or mid))}">'
            f"{''.join(filters[:6])}"
            f"{''.join(extra_groupbys[:4])}"
            f"</search>"
        )
        views.append(
            {
                "name": f"{mid}.search",
                "model": mid,
                "type": "search",
                "arch": arch,
                "mode": "primary",
            }
        )
        have_search.add(mid)
        added += 1
    if added:
        draft["views"] = views
        notes.append(f"production: added {added} search view(s)")
    return notes


def ensure_sequence_specs(draft: dict[str, Any]) -> list[str]:
    """Emit ir.sequence specs for x_code fields; replace wire-later help."""
    notes: list[str] = []
    from module_generator import sequence_prefix_for_model

    seqs = list(draft.get("sequences") or []) if isinstance(draft.get("sequences"), list) else []
    have = {s.get("model") for s in seqs if isinstance(s, dict)}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        names = {str(f.get("name")) for f in _field_list(model)}
        if "x_code" not in names and "x_reference" not in names:
            continue
        if mid in have:
            continue
        prefix = sequence_prefix_for_model(mid)
        seqs.append(
            {
                "model": mid,
                "field": "x_code" if "x_code" in names else "x_reference",
                "name": f"{model.get('description') or mid} Sequence",
                "prefix": prefix,
                "padding": 5,
                "implementation": "base_automation_on_create",
            }
        )
        have.add(mid)
        for f in _field_list(model):
            if f.get("name") in {"x_code", "x_reference"}:
                token = prefix.rstrip("/")
                f["help"] = f"Auto-numbered via ir.sequence ({token}/00001)"
        notes.append(f"production: sequence spec for {mid}")
    if seqs:
        draft["sequences"] = seqs
    return notes


def apply_money_and_tracking_defaults(draft: dict[str, Any]) -> list[str]:
    """Monetary widget hints, tracking on status, sensible defaults."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        fields = _field_list(model)
        currency_fields = {
            str(f.get("name"))
            for f in fields
            if f.get("ttype") == "many2one" and f.get("relation") == "res.currency"
        }
        default_currency = "x_currency_id" if "x_currency_id" in currency_fields else None
        for f in fields:
            fname = str(f.get("name") or "")
            ttype = str(f.get("ttype") or "")
            if ttype in {"float", "monetary"} and any(
                k in fname for k in ("amount", "price", "total", "cost", "fee")
            ):
                f["ttype"] = "monetary"
                if default_currency:
                    f["currency_field"] = default_currency
                    f.setdefault("widget", "monetary")
            if fname == "x_status" and ttype == "selection":
                f["tracking"] = True
                keys = _selection_keys(f.get("selection"))
                if keys and not f.get("default"):
                    f["default"] = keys[0]
            if fname in {"x_date", "x_date_order", "x_date_start"} and ttype == "date":
                f.setdefault("default", "today")
    notes.append("production: monetary/tracking/defaults applied")
    return notes


def ensure_multi_company_record_rules(draft: dict[str, Any]) -> list[str]:
    """Standard company ir.rule on live path (x_company_id + company_ids domain)."""
    from app.ai_apply_readiness import normalize_company_fields_for_live, sync_company_fields_with_record_rules

    notes = list(normalize_company_fields_for_live(draft))
    notes.extend(sync_company_fields_with_record_rules(draft))
    if notes:
        return ["production: multi-company live record rules"] + notes[-3:]
    return notes


def polish_arch_richness(draft: dict[str, Any]) -> list[str]:
    """Notebook o2m columns, rich kanban, button-box smart buttons, widgets."""
    notes: list[str] = []
    from app.ai_enrich import sync_form_archs_to_models

    by_id = _models_index(draft)
    for v in draft.get("views") or []:
        if not isinstance(v, dict):
            continue
        mid = str(v.get("model") or "")
        vtype = str(v.get("type") or "")
        model = by_id.get(mid)
        if not model:
            continue
        fields = _field_list(model)
        names = {str(f.get("name")) for f in fields}
        arch = str(v.get("arch") or "")
        if vtype == "kanban" and "x_status" in names:
            extras = []
            for fn in ("x_date", "x_date_order", "x_branch_id", "x_partner_id"):
                if fn in names and fn not in arch:
                    extras.append(f'<field name="{fn}"/>')
            if extras and "<templates>" in arch:
                arch = arch.replace("</t></templates>", f"{''.join(extras)}</t></templates>")
                v["arch"] = arch
                notes.append(f"production: enriched kanban for {mid}")
        if vtype == "form" and "notebook" not in arch.lower():
            for f in fields:
                if f.get("ttype") != "one2many":
                    continue
                fname = str(f.get("name") or "")
                if fname not in arch:
                    continue
                rel = by_id.get(str(f.get("relation") or ""))
                rel_fields = _field_list(rel) if rel else []
                cols = ["x_name"]
                for rf in rel_fields:
                    rfn = str(rf.get("name") or "")
                    if rfn in {"x_qty", "x_price_unit", "x_unit_price", "x_total", "x_status", "x_date"}:
                        cols.append(rfn)
                col_xml = "".join(f'<field name="{c}"/>' for c in cols[:5])
                old = f'<field name="{fname}"><list><field name="x_name"/></list></field>'
                new = (
                    f'<notebook><page string="{escape(str(f.get("string") or "Lines"))}">'
                    f'<field name="{fname}"><list>{col_xml}</list></field>'
                    f"</page></notebook>"
                )
                if old in arch:
                    arch = arch.replace(old, new)
                    v["arch"] = arch
                    notes.append(f"production: notebook o2m for {mid}.{fname}")
        for f in fields:
            if f.get("ttype") == "many2one" and f.get("relation") == "res.users":
                fname = str(f.get("name") or "")
                if fname in arch and "many2one_avatar_user" not in arch:
                    arch = arch.replace(
                        f'<field name="{fname}"/>',
                        f'<field name="{fname}" widget="many2one_avatar_user"/>',
                    )
                    v["arch"] = arch
    notes.extend(sync_form_archs_to_models(draft))
    return notes


def _pack_body_for_draft(draft: dict[str, Any]) -> dict[str, Any] | None:
    vocab = draft.get("vocab")
    if isinstance(vocab, dict):
        return {"vocab": vocab}
    from app.ai_domain_packs import match_domain_pack

    pack_id = str(draft.get("domain_pack") or "")
    matched = match_domain_pack(str(draft.get("_user_prompt") or ""))
    if matched and (not pack_id or matched[0] == pack_id):
        return matched[1]
    return None


def run_production_shape_pass(draft: dict[str, Any]) -> list[str]:
    """Full GEN2-11 production finisher."""
    notes: list[str] = []
    from app.ai_apply_readiness import ensure_unique_sequence_prefixes, run_apply_readiness_pass
    from app.ai_presentation import dedupe_smart_button_labels
    from app.ai_vocab_scrub import scrub_draft_vocabulary

    pack_body = _pack_body_for_draft(draft)
    notes.extend(run_apply_readiness_pass(draft))
    try:
        notes.extend(scrub_draft_vocabulary(draft, pack=pack_body))
    except Exception:  # noqa: BLE001
        pass
    from app.ai_apply_readiness import polish_retail_surface_labels

    notes.extend(polish_retail_surface_labels(draft))
    notes.extend(dedupe_smart_button_labels(draft))
    notes.extend(ensure_search_views(draft))
    notes.extend(ensure_sequence_specs(draft))
    notes.extend(ensure_unique_sequence_prefixes(draft))
    from app.ai_apply_readiness import reorganize_branch_form_relations, sync_sequence_field_help

    notes.extend(sync_sequence_field_help(draft))
    notes.extend(apply_money_and_tracking_defaults(draft))
    notes.extend(ensure_multi_company_record_rules(draft))
    notes.extend(polish_arch_richness(draft))
    notes.extend(reorganize_branch_form_relations(draft))
    from app.ai_llm_status import finalize_llm_status

    status = draft.get("_llm_status") if isinstance(draft.get("_llm_status"), dict) else {}
    mode = status.get("mode") or "llm_full"
    finalize_llm_status(draft, mode=mode)  # type: ignore[arg-type]
    draft["_meta"] = {
        **(draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}),
        "model_count": len(draft.get("models") or []),
        "view_count": len(draft.get("views") or []),
        "menu_count": len(draft.get("menus") or []),
        "smart_button_count": len(draft.get("smart_buttons") or []),
        "automation_count": len(draft.get("automations") or []),
    }
    from app.ai_apply_readiness import finalize_draft_readiness_metadata

    notes.extend(finalize_draft_readiness_metadata(draft))
    return notes


__all__ = [
    "apply_money_and_tracking_defaults",
    "ensure_search_views",
    "ensure_sequence_specs",
    "polish_arch_richness",
    "run_production_shape_pass",
]
