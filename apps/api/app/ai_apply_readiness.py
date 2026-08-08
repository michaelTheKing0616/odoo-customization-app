"""Deterministic fixes that block Apply-to-Odoo / module export (GEN2-11+)."""

from __future__ import annotations

import re
from typing import Any

from app.module_spec_codec import merge_custom_code_blocks
from app.multi_company_pack import COMPANY_FIELD_MODULE, COMPANY_RULE_DOMAIN_MODULE

_MODULE_COMPANY_FIELD = "company_id"
_LIVE_COMPANY_FIELD = "x_company_id"
_INITIAL_STATES = frozenset({"draft", "new"})
_ALLOWED_INITIAL_TERMINALS = frozenset({"cancelled", "canceled", "rejected"})
_BAD_ASSIGNEE_RELATIONS = frozenset({"x_staff_shift"})
_LINE_QTY_NAMES = ("x_qty", "x_quantity", "quantity", "x_hours", "x_units")
_LINE_PRICE_NAMES = ("x_price", "x_unit_price", "x_price_unit", "x_rate", "price_unit")
_LINE_TOTAL_NAMES = ("x_subtotal", "x_total", "x_amount")

_SCALE_WORDS = frozenset({"super", "mega", "large", "multiple", "around", "world", "global"})
_DOMAIN_WORDS = (
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
)


def _models_index(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def _field_names(model: dict[str, Any]) -> set[str]:
    return {
        str(f.get("name"))
        for f in (model.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }


def _replace_in_arch(draft: dict[str, Any], old: str, new: str) -> None:
    if old == new:
        return
    for v in draft.get("views") or []:
        if not isinstance(v, dict):
            continue
        arch = str(v.get("arch") or "")
        if old in arch:
            v["arch"] = arch.replace(old, new)


def normalize_company_fields_for_export(draft: dict[str, Any]) -> list[str]:
    """Module export uses company_id + company_ids domain — not x_company_id."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        names = _field_names(model)
        fields = model.get("fields") or []
        if _LIVE_COMPANY_FIELD in names and _MODULE_COMPANY_FIELD not in names:
            for f in fields:
                if isinstance(f, dict) and f.get("name") == _LIVE_COMPANY_FIELD:
                    f["name"] = _MODULE_COMPANY_FIELD
                    f.setdefault("string", "Company")
                    notes.append(f"apply: {_LIVE_COMPANY_FIELD}→{_MODULE_COMPANY_FIELD} on {mid}")
            _replace_in_arch(draft, _LIVE_COMPANY_FIELD, _MODULE_COMPANY_FIELD)
        elif _LIVE_COMPANY_FIELD in names and _MODULE_COMPANY_FIELD in names:
            model["fields"] = [
                f
                for f in fields
                if not (isinstance(f, dict) and f.get("name") == _LIVE_COMPANY_FIELD)
            ]
            notes.append(f"apply: dropped duplicate {_LIVE_COMPANY_FIELD} on {mid}")

    rules = draft.get("record_rules") or []
    if isinstance(rules, list):
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            dom = str(rule.get("domain_force") or "")
            if _LIVE_COMPANY_FIELD in dom:
                rule["domain_force"] = dom.replace(_LIVE_COMPANY_FIELD, _MODULE_COMPANY_FIELD)
                notes.append(f"apply: record rule domain uses {_MODULE_COMPANY_FIELD}")

    from app.multi_company_pack import apply_multi_company_to_draft

    enriched = apply_multi_company_to_draft(draft)
    if enriched.get("record_rules"):
        draft["record_rules"] = enriched["record_rules"]
    for rule in draft.get("record_rules") or []:
        if isinstance(rule, dict):
            rule["domain_force"] = COMPANY_RULE_DOMAIN_MODULE
    return notes


def resolve_duplicate_address_fields(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        names = _field_names(model)
        if "x_address" in names and "x_address_id" in names:
            model["fields"] = [
                f
                for f in (model.get("fields") or [])
                if not (isinstance(f, dict) and f.get("name") == "x_address")
            ]
            mid = str(model.get("model") or "")
            _replace_in_arch(draft, 'name="x_address"', 'name="x_address_id"')
            notes.append(f"apply: dropped redundant x_address char on {mid} (keep x_address_id)")
    return notes


def ensure_relation_module_depends(draft: dict[str, Any]) -> list[str]:
    """Add depends when models reference stock/hr/etc."""
    notes: list[str] = []
    relation_modules = {
        "hr.employee": "hr",
        "hr.contract": "hr",
        "stock.quant": "stock",
        "stock.picking": "stock",
        "sale.order": "sale",
        "purchase.order": "purchase",
    }
    found: set[str] = set()
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for f in model.get("fields") or []:
            if not isinstance(f, dict):
                continue
            rel = str(f.get("relation") or "")
            mod = relation_modules.get(rel)
            if mod:
                found.add(mod)
    depends = list(draft.get("depends") or [])
    dep_set = set(depends)
    for mod in sorted(found):
        if mod not in dep_set:
            depends.append(mod)
            dep_set.add(mod)
            notes.append(f"apply: added depends {mod}")
    if notes:
        draft["depends"] = depends
    return notes


def _pack_reuse_stock_rows(draft: dict[str, Any]) -> list[dict[str, Any]]:
    rows = draft.get("_pack_reuse_stock") or draft.get("reuse_stock") or []
    if isinstance(rows, list) and rows:
        return [r for r in rows if isinstance(r, dict)]
    if draft.get("domain_pack"):
        from app.ai_domain_packs import match_domain_pack

        prompt = str(draft.get("_user_prompt") or "")
        matched = match_domain_pack(prompt)
        if matched and isinstance(matched[1], dict):
            stock = matched[1].get("reuse_stock")
            if isinstance(stock, list):
                return [r for r in stock if isinstance(r, dict)]
    return []


def _draft_anti_patterns(draft: dict[str, Any]) -> list[str]:
    patterns = list(draft.get("anti_patterns") or [])
    if patterns:
        return [str(p) for p in patterns]
    if draft.get("domain_pack"):
        from app.ai_domain_packs import match_domain_pack

        matched = match_domain_pack(str(draft.get("_user_prompt") or ""))
        if matched and isinstance(matched[1], dict):
            return [str(p) for p in (matched[1].get("anti_patterns") or [])]
    return []


_PAYMENT_CAPTURE_FORBIDDEN_RE = re.compile(
    r"payment capture|recurring billing engines|folio settlement", re.I
)
_PARALLEL_BILLING_MODEL_RE = re.compile(r"x_.*(?:invoice|bill)(?:_line)?$", re.I)
_PAYMENT_WORKFLOW_STATES = frozenset({"paid", "overdue", "sent", "partial", "posted"})


def _purge_draft_models(draft: dict[str, Any], removed: set[str]) -> None:
    if not removed:
        return
    draft["models"] = [
        m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "") not in removed
    ]
    for key in ("actions", "views", "menus", "sequences", "automations"):
        rows = draft.get(key)
        if not isinstance(rows, list):
            continue
        kept = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            mid = row.get("model")
            if key == "menus":
                action_id = str(row.get("action_xml_id") or "")
                if any(action_id == f"action_{r}" for r in removed):
                    continue
            if key == "access_rules" and isinstance(mid, str) and mid.startswith("model_"):
                leaf = mid[len("model_") :]
                if leaf in removed:
                    continue
            if mid in removed:
                continue
            kept.append(row)
        draft[key] = kept
    draft["smart_buttons"] = [
        b
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
        and b.get("related_model") not in removed
        and b.get("on_model") not in removed
    ]
    blocks = draft.get("custom_code_blocks")
    if isinstance(blocks, list):
        draft["custom_code_blocks"] = [
            b
            for b in blocks
            if not (isinstance(b, dict) and str(b.get("model") or "") in removed)
        ]
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        model["fields"] = [
            f
            for f in (model.get("fields") or [])
            if not (
                isinstance(f, dict)
                and str(f.get("relation") or "") in removed
            )
        ]


def demote_parallel_billing_models(draft: dict[str, Any]) -> list[str]:
    """Drop parallel x_* invoice/bill workflows when pack forbids payment capture."""
    notes: list[str] = []
    anti = _draft_anti_patterns(draft)
    forbid_capture = any(_PAYMENT_CAPTURE_FORBIDDEN_RE.search(p) for p in anti)
    reuse_models = set((draft.get("reuse") or {}).get("models") or [])
    if not forbid_capture and "account.move" not in reuse_models:
        return notes

    removed: set[str] = set()
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        if mid == "x_bill" and not model.get("is_workflow"):
            continue
        if not (_PARALLEL_BILLING_MODEL_RE.match(mid) or "invoice" in mid.lower()):
            if "bill" not in mid.lower():
                continue
        if model.get("is_workflow"):
            sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
            sel = str(sf.get("selection") or "")
            states = set(re.findall(r"\('([^']+)'", sel))
            if states & _PAYMENT_WORKFLOW_STATES or "invoice" in mid.lower():
                removed.add(mid)
                continue
        if "invoice" in mid.lower() and any(
            isinstance(f, dict)
            and str(f.get("ttype") or "") in {"monetary", "float"}
            and "amount" in str(f.get("name") or "").lower()
            for f in (model.get("fields") or [])
        ):
            removed.add(mid)

    if not removed:
        return notes

    _purge_draft_models(draft, removed)
    notes.append(f"apply: demoted parallel billing model(s) {', '.join(sorted(removed))}")

    line_drop = {"x_bill_id", "x_invoice_id"}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if "line" not in mid.lower():
            continue
        before = len(model.get("fields") or [])
        model["fields"] = [
            f
            for f in (model.get("fields") or [])
            if not (isinstance(f, dict) and str(f.get("name") or "") in line_drop)
        ]
        if len(model.get("fields") or []) < before:
            notes.append(f"apply: removed line billing link field(s) on {mid}")

    depends = set(draft.get("depends") or [])
    reuse = set((draft.get("reuse") or {}).get("models") or [])
    if "account" in depends or "account.move" in reuse:
        by_id = _models_index(draft)
        for model in draft.get("models") or []:
            if not isinstance(model, dict):
                continue
            mid = str(model.get("model") or "")
            if "line" in mid.lower() or "order" not in mid.lower():
                continue
            names = _field_names(model)
            if "x_invoice_id" in names or "x_move_id" in names:
                continue
            model.setdefault("fields", []).append(
                {
                    "name": "x_invoice_id",
                    "ttype": "many2one",
                    "relation": "account.move",
                    "string": "Invoice",
                    "help": "Link-only — wire to account.move manually",
                    "source": "apply_readiness",
                }
            )
            notes.append(f"apply: link-only x_invoice_id on {mid} (account.move)")

    draft.setdefault("review_notes", [])
    if isinstance(draft["review_notes"], list):
        note = (
            "Billing: parallel x_* invoice models removed — use link-only account.move "
            "fields; no payment capture in metadata export."
        )
        if note not in draft["review_notes"]:
            draft["review_notes"].append(note)
    return notes


def fix_reuse_link_only_consistency(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    link_only: dict[str, bool] = {}
    for row in _pack_reuse_stock_rows(draft):
        if row.get("model"):
            link_only[str(row["model"])] = bool(row.get("link_only"))
    plan = (draft.get("reuse") or {}).get("plan") if isinstance(draft.get("reuse"), dict) else {}
    decisions = plan.get("decisions") if isinstance(plan, dict) else None
    if not isinstance(decisions, list):
        return notes
    for d in decisions:
        if not isinstance(d, dict):
            continue
        model = str(d.get("model") or "")
        if model in link_only and link_only[model] and not d.get("link_only"):
            d["link_only"] = True
            notes.append(f"apply: reuse {model} marked link_only (pack contract)")
    return notes


def dedupe_search_view_filters(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for v in draft.get("views") or []:
        if not isinstance(v, dict) or str(v.get("type") or "") != "search":
            continue
        arch = str(v.get("arch") or "")
        if not arch:
            continue
        filters = re.findall(r"<filter\b[^>]*(?:/>|>[^<]*</filter>)", arch, flags=re.I)
        seen: set[str] = set()
        keep: list[str] = []
        for flt in filters:
            name_m = re.search(r'name="([^"]+)"', flt)
            ctx_m = re.search(r"context=\"(\{[^\"]+\})\"", flt)
            key = name_m.group(1) if name_m else flt
            if ctx_m:
                key = f"{key}|{ctx_m.group(1)}"
            if key in seen:
                continue
            seen.add(key)
            keep.append(flt)
        if len(keep) < len(filters):
            mid = str(v.get("model") or "")
            open_tag = re.match(r"(<search[^>]*>)", arch, flags=re.I)
            close_tag = "</search>"
            if open_tag:
                v["arch"] = open_tag.group(1) + "".join(keep) + close_tag
                notes.append(f"apply: deduped search filters on {mid}")
    return notes


def ensure_unique_sequence_prefixes(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    seqs = draft.get("sequences") or []
    if not isinstance(seqs, list):
        return notes
    used: dict[str, str] = {}
    for seq in seqs:
        if not isinstance(seq, dict):
            continue
        prefix = str(seq.get("prefix") or "")
        model = str(seq.get("model") or "")
        if not prefix or not model:
            continue
        if prefix not in used:
            used[prefix] = model
            continue
        if used[prefix] == model:
            continue
        slug = model.replace("x_", "").replace(".", "_").upper()[:8]
        new_prefix = f"{slug}/"
        n = 2
        while new_prefix in used:
            new_prefix = f"{slug[:6]}{n}/"
            n += 1
        seq["prefix"] = new_prefix
        used[new_prefix] = model
        for m in draft.get("models") or []:
            if not isinstance(m, dict) or str(m.get("model")) != model:
                continue
            for f in m.get("fields") or []:
                if isinstance(f, dict) and f.get("name") in {"x_code", "x_reference"}:
                    token = new_prefix.rstrip("/")
                    f["help"] = f"Auto-numbered via ir.sequence ({token}/00001)"
        notes.append(f"apply: sequence prefix {prefix}→{new_prefix} for {model}")
    return notes


def fix_branch_transfer_incoming_o2m(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    by_id = _models_index(draft)
    branch = by_id.get("x_branch")
    transfer = by_id.get("x_branch_transfer")
    if not branch or not transfer:
        return notes
    names = _field_names(branch)
    if "x_branch_transfer_in_ids" in names:
        return notes
    if not any(
        isinstance(f, dict) and f.get("name") == "x_branch_to_id"
        for f in (transfer.get("fields") or [])
    ):
        return notes
    branch.setdefault("fields", []).append(
        {
            "name": "x_branch_transfer_in_ids",
            "ttype": "one2many",
            "string": "Incoming transfers",
            "relation": "x_branch_transfer",
            "relation_field": "x_branch_to_id",
            "source": "apply_readiness",
        }
    )
    notes.append("apply: x_branch incoming transfer o2m (x_branch_to_id)")
    return notes


def _domain_label_word(user_prompt: str) -> str:
    tokens = re.findall(r"[a-zA-Z]+", user_prompt.lower())
    for tok in tokens:
        if tok in _SCALE_WORDS:
            continue
        if tok in _DOMAIN_WORDS or len(tok) >= 4:
            return tok.replace("_", " ").title()
    return "Store"


def normalize_depth_seed_naming(draft: dict[str, Any]) -> list[str]:
    """Replace generic 'Super Event/Task' depth_seed labels with domain wording."""
    notes: list[str] = []
    prompt = str(draft.get("_user_prompt") or "")
    word = _domain_label_word(prompt)
    replacements = {
        "Super Event": f"{word} Event",
        "Super Task": f"{word} Task",
    }
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or model.get("source") != "depth_seed":
            continue
        desc = str(model.get("description") or "")
        for old, new in replacements.items():
            if old in desc:
                model["description"] = desc.replace(old, new)
                notes.append(f"apply: renamed depth_seed {model.get('model')} description")
    for key in ("actions", "menus", "smart_buttons"):
        rows = draft.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for field in ("name", "label", "string"):
                val = str(row.get(field) or "")
                for old, new in replacements.items():
                    if old in val:
                        row[field] = val.replace(old, new)
    for v in draft.get("views") or []:
        if not isinstance(v, dict):
            continue
        arch = str(v.get("arch") or "")
        name = str(v.get("name") or "")
        for old, new in replacements.items():
            if old in arch:
                v["arch"] = arch.replace(old, new)
                arch = v["arch"]
            if old in name:
                v["name"] = name.replace(old, new)
    for g in draft.get("groups") or []:
        if isinstance(g, dict):
            nm = str(g.get("name") or "")
            for old, new in replacements.items():
                if old in nm:
                    g["name"] = nm.replace(old, new)
    return notes


def consolidate_redundant_inventory_models(draft: dict[str, Any]) -> list[str]:
    """Drop x_store_inventory when stock + x_inventory_count already cover inventory."""
    notes: list[str] = []
    depends = set(draft.get("depends") or [])
    if "stock" not in depends:
        return notes
    by_id = _models_index(draft)
    if "x_store_inventory" not in by_id or "x_inventory_count" not in by_id:
        return notes
    drop = "x_store_inventory"
    draft["models"] = [m for m in (draft.get("models") or []) if m.get("model") != drop]
    draft["actions"] = [
        a for a in (draft.get("actions") or []) if isinstance(a, dict) and a.get("model") != drop
    ]
    draft["menus"] = [
        m
        for m in (draft.get("menus") or [])
        if isinstance(m, dict) and str(m.get("action_xml_id") or "") != f"action_{drop}"
    ]
    draft["views"] = [
        v for v in (draft.get("views") or []) if isinstance(v, dict) and v.get("model") != drop
    ]
    draft["smart_buttons"] = [
        b
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict) and b.get("related_model") != drop and b.get("on_model") != drop
    ]
    draft["sequences"] = [
        s for s in (draft.get("sequences") or []) if isinstance(s, dict) and s.get("model") != drop
    ]
    branch = by_id.get("x_branch")
    if branch:
        branch["fields"] = [
            f
            for f in (branch.get("fields") or [])
            if not (isinstance(f, dict) and str(f.get("relation") or "") == drop)
        ]
    notes.append("apply: removed x_store_inventory (stock + x_inventory_count sufficient)")
    return notes


def sync_company_fields_with_record_rules(draft: dict[str, Any]) -> list[str]:
    """Every multi-company record rule must match a company_id field on the model."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for rule in draft.get("record_rules") or []:
        if not isinstance(rule, dict):
            continue
        dom = str(rule.get("domain_force") or "")
        if _MODULE_COMPANY_FIELD not in dom and _LIVE_COMPANY_FIELD not in dom:
            continue
        model_id = str(rule.get("model") or "")
        model = by_id.get(model_id)
        if not model or str(model.get("mode") or "new") != "new":
            continue
        names = _field_names(model)
        if _MODULE_COMPANY_FIELD in names:
            continue
        if _LIVE_COMPANY_FIELD in names:
            continue
        model.setdefault("fields", []).append(dict(COMPANY_FIELD_MODULE))
        notes.append(f"apply: added company_id on {model_id} (record rule alignment)")
    return notes


def ensure_global_branch_fields(draft: dict[str, Any]) -> list[str]:
    """Country (+ timezone) on branch/transfer models for global-scale prompts."""
    prompt = str(draft.get("_user_prompt") or "")
    from app.ai_depth import ensure_country_on_branch_for_global_prompt

    notes = list(ensure_country_on_branch_for_global_prompt(draft, prompt))
    if not re.search(
        r"\b(around\s+the\s+world|international|global|worldwide|multi[\s-]?country|"
        r"across\s+countries|multiple\s+countries|multiple\s+branches)\b",
        prompt,
        re.I,
    ):
        return notes
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        desc = str(model.get("description") or "").lower()
        if mid != "x_branch" and "branch" not in mid and "branch" not in desc:
            continue
        if mid == "x_branch_transfer":
            continue
        names = _field_names(model)
        if "x_timezone" not in names:
            model.setdefault("fields", []).append(
                {
                    "name": "x_timezone",
                    "ttype": "char",
                    "string": "Timezone",
                    "source": "apply_readiness",
                }
            )
            notes.append(f"apply: added x_timezone on {mid} (global prompt)")
    return notes


def polish_branch_address_fields(draft: dict[str, Any]) -> list[str]:
    """Prefer structured street/city or partner link over a lone x_address char."""
    notes: list[str] = []
    by_id = _models_index(draft)
    branch = by_id.get("x_branch")
    if not branch:
        return notes
    names = _field_names(branch)
    if "x_address_id" in names:
        return notes
    if "x_address" not in names:
        return notes
    for f in branch.get("fields") or []:
        if isinstance(f, dict) and f.get("name") == "x_address":
            f["name"] = "x_street"
            f["string"] = "Street"
            notes.append("apply: renamed x_address→x_street on x_branch")
            break
    _replace_in_arch(draft, 'name="x_address"', 'name="x_street"')
    if "x_city" not in names:
        branch.setdefault("fields", []).append(
            {"name": "x_city", "ttype": "char", "string": "City", "source": "apply_readiness"}
        )
        notes.append("apply: added x_city on x_branch")
    return notes


def _remove_transition_buttons(arch: str, from_state: str, to_state: str) -> str:
    pattern = rf'<button\b[^>]*/>'

    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        if f'data-transition-to="{to_state}"' not in tag and f"data-transition-to='{to_state}'" not in tag:
            return tag
        if (
            f"x_status != '{from_state}'" in tag
            or f'x_status != "{from_state}"' in tag
        ):
            return ""
        return tag

    return re.sub(pattern, repl, arch, flags=re.I)


def fix_workflow_skip_terminal_transitions(draft: dict[str, Any]) -> list[str]:
    """Draft/new must not skip directly to expired/failed — only cancel is allowed."""
    from app.ai_workflow_semantic import classify_state

    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or not model.get("is_workflow"):
            continue
        sf = model.get("state_field")
        if not isinstance(sf, dict):
            continue
        transitions = sf.get("transitions")
        if not isinstance(transitions, list):
            continue
        mid = str(model.get("model") or "")
        kept: list[Any] = []
        removed: list[tuple[str, str]] = []
        for tr in transitions:
            if not isinstance(tr, (list, tuple)) or len(tr) < 2:
                kept.append(tr)
                continue
            a, b = str(tr[0]), str(tr[1])
            if (
                a.lower() in _INITIAL_STATES
                and classify_state(b) == "terminal_negative"
                and b.lower() not in _ALLOWED_INITIAL_TERMINALS
            ):
                removed.append((a, b))
                continue
            kept.append(tr)
        if not removed:
            continue
        sf["transitions"] = kept
        model["state_field"] = sf
        notes.append(
            f"apply: pruned skip transitions on {mid}: "
            + ", ".join(f"{a}→{b}" for a, b in removed)
        )
        for v in draft.get("views") or []:
            if not isinstance(v, dict) or str(v.get("model") or "") != mid:
                continue
            if str(v.get("type") or "") != "form":
                continue
            arch = str(v.get("arch") or "")
            for a, b in removed:
                arch = _remove_transition_buttons(arch, a, b)
            v["arch"] = arch
    return notes


def _currency_field_name(fields: dict[str, dict[str, Any]]) -> str:
    for name in ("x_currency_id", "currency_id"):
        f = fields.get(name)
        if isinstance(f, dict) and f.get("ttype") == "many2one":
            return name
    return "x_currency_id"


def _field_ttype(fields: dict[str, dict[str, Any]], name: str) -> str:
    f = fields.get(name)
    if not isinstance(f, dict):
        return "float"
    ttype = str(f.get("ttype") or "float")
    if ttype == "float" and (
        f.get("currency_field")
        or any(
            isinstance(other, dict)
            and other.get("ttype") == "many2one"
            and other.get("relation") == "res.currency"
            for other in fields.values()
        )
    ):
        if any(k in name for k in ("amount", "price", "total", "cost", "fee", "subtotal")):
            return "monetary"
    return ttype


def _upsert_custom_code_block(
    draft: dict[str, Any],
    *,
    model: str,
    source_file: str,
    content: str,
    reason: str,
) -> None:
    blocks = draft.setdefault("custom_code_blocks", [])
    if not isinstance(blocks, list):
        draft["custom_code_blocks"] = blocks = []
    payload = {
        "source_file": source_file,
        "kind": "python",
        "content": content,
        "reason": reason,
        "model": model,
    }
    for i, block in enumerate(blocks):
        if isinstance(block, dict) and str(block.get("model") or "") == model:
            blocks[i] = {**block, **payload}
            return
    blocks.append(payload)


def _drop_model_fields(draft: dict[str, Any], model_id: str, drop: set[str]) -> None:
    by_id = _models_index(draft)
    model = by_id.get(model_id)
    if not model or not drop:
        return
    model["fields"] = [
        f
        for f in (model.get("fields") or [])
        if not (isinstance(f, dict) and str(f.get("name") or "") in drop)
    ]
    for name in drop:
        _replace_in_arch(draft, f'name="{name}"', "")


def fix_broken_shift_assignee_smart_buttons(draft: dict[str, Any]) -> list[str]:
    """Shift rows must not stat-link events/tasks via x_staff_id (now hr.employee)."""
    notes: list[str] = []
    kept: list[dict[str, Any]] = []
    for btn in draft.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        if (
            str(btn.get("on_model") or "") == "x_staff_shift"
            and str(btn.get("related_model") or "") in {"x_event", "x_task"}
            and str(btn.get("relation_field") or "") == "x_staff_id"
        ):
            notes.append(
                f"apply: dropped broken shift smart button → {btn.get('related_model')}"
            )
            continue
        kept.append(btn)
    if len(kept) != len(draft.get("smart_buttons") or []):
        draft["smart_buttons"] = kept
    return notes


def fix_assignee_staff_relations(draft: dict[str, Any]) -> list[str]:
    """Event/task assignee should point to hr.employee or res.users — not shift rows."""
    notes: list[str] = []
    depends = set(draft.get("depends") or [])
    target = "hr.employee" if "hr" in depends else "res.users"
    label = "Employee" if target == "hr.employee" else "Assigned user"
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if mid not in {"x_event", "x_task"}:
            continue
        for f in model.get("fields") or []:
            if not isinstance(f, dict) or f.get("name") != "x_staff_id":
                continue
            rel = str(f.get("relation") or "")
            if rel not in _BAD_ASSIGNEE_RELATIONS:
                continue
            f["relation"] = target
            f["string"] = label
            notes.append(f"apply: x_staff_id on {mid} → {target}")
    notes.extend(fix_broken_shift_assignee_smart_buttons(draft))
    return notes


def _model_module_basename(model: str) -> str:
    return model.replace(".", "_")


def _model_class_token(model: str) -> str:
    return "".join(p.title() for p in _model_module_basename(model).split("_") if p)


def ensure_line_currency_fields(draft: dict[str, Any]) -> list[str]:
    """Propagate order currency onto line models for monetary computes."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or "line" not in mid.lower():
            continue
        names = _field_names(model)
        if "x_currency_id" in names:
            continue
        order_field = next(
            (
                f
                for f in (model.get("fields") or [])
                if isinstance(f, dict)
                and f.get("ttype") == "many2one"
                and str(f.get("relation") or "") in by_id
                and "line" not in str(f.get("relation") or "").lower()
            ),
            None,
        )
        if not order_field:
            continue
        order = by_id.get(str(order_field.get("relation") or "")) or {}
        order_names = _field_names(order)
        if "x_currency_id" not in order_names:
            continue
        model.setdefault("fields", []).append(
            {
                "name": "x_currency_id",
                "ttype": "many2one",
                "relation": "res.currency",
                "string": "Currency",
                "related": f"{order_field.get('name')}.x_currency_id",
                "readonly": True,
                "source": "apply_readiness",
            }
        )
        notes.append(f"apply: related x_currency_id on {mid}")
    return notes


def normalize_line_monetary_fields(draft: dict[str, Any]) -> list[str]:
    """Align line amount fields with x_currency_id when present."""
    notes: list[str] = []
    amount_names = {"x_subtotal", "x_total", "x_amount", "x_price_unit", "x_tax_amount", "x_total_amount"}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or "line" not in mid.lower():
            continue
        names = _field_names(model)
        if "x_currency_id" not in names:
            continue
        for f in model.get("fields") or []:
            if not isinstance(f, dict):
                continue
            fname = str(f.get("name") or "")
            if fname not in amount_names:
                continue
            if str(f.get("ttype") or "") in {"float", "monetary"}:
                f["ttype"] = "monetary"
                f["currency_field"] = "x_currency_id"
                f.setdefault("widget", "monetary")
                notes.append(f"apply: monetary line field {mid}.{fname}")
    return notes


def apply_line_subtotal_computes(draft: dict[str, Any]) -> list[str]:
    """Stored qty × unit-price compute for line subtotals (module export via custom_code_blocks)."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or "line" not in mid.lower():
            continue
        fields = {
            str(f.get("name")): f for f in (model.get("fields") or []) if isinstance(f, dict)
        }
        qty = next((n for n in _LINE_QTY_NAMES if n in fields), None)
        price = next((n for n in _LINE_PRICE_NAMES if n in fields), None)
        total = next((n for n in _LINE_TOTAL_NAMES if n in fields), None)
        if not qty or not price or not total:
            continue
        total_label = str(fields[total].get("string") or "Subtotal")
        class_name = f"{_model_class_token(mid)}LineSubtotal"
        method = f"_compute_{total}"
        basename = _model_module_basename(mid)
        source_file = f"models/{basename}.py"
        if _field_ttype(fields, total) == "monetary":
            curr = _currency_field_name(fields)
            field_lines = (
                f"    {total} = fields.Monetary(\n"
                f"        string={total_label!r},\n"
                f"        compute={method!r},\n"
                f"        store=True,\n"
                f"        currency_field={curr!r},\n"
                f"    )\n"
            )
        else:
            field_lines = (
                f"    {total} = fields.Float(\n"
                f"        string={total_label!r},\n"
                f"        compute={method!r},\n"
                f"        store=True,\n"
                f"    )\n"
            )
        content = (
            "from odoo import api, fields, models\n\n\n"
            f"class {class_name}(models.Model):\n"
            f"    _inherit = {mid!r}\n\n"
            f"{field_lines}\n"
            f"    @api.depends({qty!r}, {price!r})\n"
            f"    def {method}(self):\n"
            f"        for rec in self:\n"
            f"            rec.{total} = (rec.{qty} or 0.0) * (rec.{price} or 0.0)\n"
        )
        _upsert_custom_code_block(
            draft,
            model=mid,
            source_file=source_file,
            content=content,
            reason="apply_readiness: line subtotal compute",
        )
        notes.append(f"apply: line subtotal compute on {mid} ({qty}×{price}→{total})")
    return notes


def apply_order_header_total_computes(draft: dict[str, Any]) -> list[str]:
    """Roll up line subtotals into header x_amount_total on order models."""
    notes: list[str] = []
    by_id = _models_index(draft)
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        fields = {
            str(f.get("name")): f for f in (model.get("fields") or []) if isinstance(f, dict)
        }
        line_field = next(
            (
                f
                for f in fields
                if fields[f].get("ttype") == "one2many"
                and str(fields[f].get("relation") or "") in by_id
                and "line" in str(fields[f].get("relation") or "").lower()
            ),
            None,
        )
        total_field = next(
            (n for n in ("x_amount_total", "x_total", "x_amount") if n in fields),
            None,
        )
        if not line_field or not total_field:
            continue
        line_model = str(fields[line_field].get("relation") or "")
        line_def = by_id.get(line_model) or {}
        line_names = _field_names(line_def)
        subtotal = next((n for n in _LINE_TOTAL_NAMES if n in line_names), None)
        if not subtotal:
            continue
        total_label = str(fields[total_field].get("string") or "Total")
        class_name = f"{_model_class_token(mid)}HeaderTotal"
        method = f"_compute_{total_field}"
        basename = _model_module_basename(mid)
        source_file = f"models/{basename}.py"
        if _field_ttype(fields, total_field) == "monetary":
            curr = _currency_field_name(fields)
            field_lines = (
                f"    {total_field} = fields.Monetary(\n"
                f"        string={total_label!r},\n"
                f"        compute={method!r},\n"
                f"        store=True,\n"
                f"        currency_field={curr!r},\n"
                f"    )\n"
            )
        else:
            field_lines = (
                f"    {total_field} = fields.Float(\n"
                f"        string={total_label!r},\n"
                f"        compute={method!r},\n"
                f"        store=True,\n"
                f"    )\n"
            )
        content = (
            "from odoo import api, fields, models\n\n\n"
            f"class {class_name}(models.Model):\n"
            f"    _inherit = {mid!r}\n\n"
            f"{field_lines}\n"
            f"    @api.depends('{line_field}.{subtotal}')\n"
            f"    def {method}(self):\n"
            f"        for rec in self:\n"
            f"            rec.{total_field} = sum(rec.{line_field}.mapped('{subtotal}'))\n"
        )
        _upsert_custom_code_block(
            draft,
            model=mid,
            source_file=source_file,
            content=content,
            reason="apply_readiness: order header total compute",
        )
        notes.append(f"apply: header total compute on {mid} (sum {line_model}.{subtotal})")
    return notes


def clear_resolved_compute_suggestions(draft: dict[str, Any]) -> list[str]:
    """Drop line-total suggestions once custom compute blocks exist; dedupe leftovers."""
    notes: list[str] = []
    computed_models = {
        str(b.get("model"))
        for b in merge_custom_code_blocks(draft)
        if isinstance(b, dict) and b.get("model")
    }
    raw = draft.get("_compute_suggestions")
    if not isinstance(raw, list):
        draft["_compute_suggestions"] = []
        return notes
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    dropped = 0
    for row in raw:
        if not isinstance(row, dict):
            continue
        model = str(row.get("model") or "")
        if model in computed_models:
            dropped += 1
            continue
        if model in seen:
            dropped += 1
            continue
        seen.add(model)
        kept.append(row)
    draft["_compute_suggestions"] = kept
    if dropped:
        notes.append(f"apply: cleared {dropped} resolved compute suggestion(s)")
    return notes


def fix_inventory_adjustment_workflow(draft: dict[str, Any]) -> list[str]:
    """Ensure rejected terminal is reachable from draft on adjustment workflows."""
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or str(model.get("model") or "") != "x_inventory_adjustment":
            continue
        if not model.get("is_workflow"):
            continue
        sf = model.get("state_field")
        if not isinstance(sf, dict):
            continue
        states = [str(s) for s in (sf.get("states") or [])]
        if "rejected" not in states:
            continue
        transitions = list(sf.get("transitions") or [])
        pairs: set[tuple[str, str]] = set()
        for tr in transitions:
            if isinstance(tr, (list, tuple)) and len(tr) >= 2:
                pairs.add((str(tr[0]), str(tr[1])))
        added: list[tuple[str, str]] = []
        if "draft" in states and "rejected" in states and ("draft", "rejected") not in pairs:
            transitions.append(["draft", "rejected"])
            pairs.add(("draft", "rejected"))
            added.append(("draft", "rejected"))
        if not added:
            continue
        sf["transitions"] = transitions
        model["state_field"] = sf
        mid = str(model.get("model") or "")
        for v in draft.get("views") or []:
            if not isinstance(v, dict) or str(v.get("model") or "") != mid:
                continue
            if str(v.get("type") or "") != "form":
                continue
            arch = str(v.get("arch") or "")
            if 'data-transition-to="rejected"' in arch:
                continue
            header_close = "</header>"
            if header_close in arch:
                btn = (
                    '<button string="Reject" type="object" class="oe_highlight" '
                    'invisible="x_status != \'draft\'" data-transition-to="rejected"/>'
                )
                v["arch"] = arch.replace(header_close, btn + header_close, 1)
        notes.append(
            "apply: inventory adjustment rejected transitions: "
            + ", ".join(f"{a}→{b}" for a, b in added)
        )
    return notes


def consolidate_inventory_count_fields(draft: dict[str, Any]) -> list[str]:
    """Remove redundant count columns; compute variance from system vs counted."""
    notes: list[str] = []
    by_id = _models_index(draft)
    model = by_id.get("x_inventory_count")
    if not model:
        return notes
    names = _field_names(model)
    if "x_qty_system" not in names or "x_qty_counted" not in names:
        return notes
    drop = {n for n in ("x_actual_qty",) if n in names}
    if drop:
        _drop_model_fields(draft, "x_inventory_count", drop)
        notes.append("apply: dropped redundant x_actual_qty on x_inventory_count")
        names -= drop
    if "x_variance" in names or "x_variance_percent" in names:
        class_name = "XInventoryCountVariance"
        content = (
            "from odoo import api, fields, models\n\n\n"
            "class XInventoryCountVariance(models.Model):\n"
            "    _inherit = 'x_inventory_count'\n\n"
            "    x_variance = fields.Float(\n"
            "        string='Variance',\n"
            "        compute='_compute_x_variance_fields',\n"
            "        store=True,\n"
            "    )\n"
            "    x_variance_percent = fields.Float(\n"
            "        string='Variance %',\n"
            "        compute='_compute_x_variance_fields',\n"
            "        store=True,\n"
            "    )\n\n"
            "    @api.depends('x_qty_system', 'x_qty_counted')\n"
            "    def _compute_x_variance_fields(self):\n"
            "        for rec in self:\n"
            "            system = rec.x_qty_system or 0.0\n"
            "            counted = rec.x_qty_counted or 0.0\n"
            "            rec.x_variance = counted - system\n"
            "            rec.x_variance_percent = (\n"
            "                (rec.x_variance / system * 100.0) if system else 0.0\n"
            "            )\n"
        )
        _upsert_custom_code_block(
            draft,
            model="x_inventory_count",
            source_file="models/x_inventory_count.py",
            content=content,
            reason="apply_readiness: inventory count variance compute",
        )
        notes.append("apply: inventory count variance compute")
    return notes


def wire_stock_document_links(draft: dict[str, Any]) -> list[str]:
    """Link-only stock.picking / warehouse hooks for transfer + adjustment models."""
    notes: list[str] = []
    depends = set(draft.get("depends") or [])
    if "stock" not in depends:
        return notes
    by_id = _models_index(draft)
    link_fields = {
        "x_branch_transfer": ("x_picking_id", "stock.picking", "Stock transfer"),
        "x_inventory_adjustment": ("x_picking_id", "stock.picking", "Stock picking"),
    }
    for mid, (fname, relation, label) in link_fields.items():
        model = by_id.get(mid)
        if not model:
            continue
        names = _field_names(model)
        if fname not in names:
            model.setdefault("fields", []).append(
                {
                    "name": fname,
                    "ttype": "many2one",
                    "relation": relation,
                    "string": label,
                    "source": "apply_readiness",
                }
            )
            notes.append(f"apply: added {fname} on {mid} (stock link-only)")
    buttons = draft.get("smart_buttons")
    if not isinstance(buttons, list):
        buttons = []
        draft["smart_buttons"] = buttons
    existing = {
        (
            str(b.get("on_model") or ""),
            str(b.get("related_model") or ""),
            str(b.get("relation_field") or ""),
        )
        for b in buttons
        if isinstance(b, dict)
    }
    for mid, (fname, relation, label) in link_fields.items():
        if mid not in by_id:
            continue
        key = (mid, relation, fname)
        if key in existing:
            continue
        buttons.append(
            {
                "on_model": mid,
                "label": label,
                "related_model": relation,
                "relation_field": fname,
                "icon": "fa-truck",
                "source": "apply_readiness",
                "link_only": True,
            }
        )
        notes.append(f"apply: stock smart button on {mid}")
    branch = by_id.get("x_branch")
    if branch and ("x_branch", "stock.warehouse", "x_warehouse_id") not in existing:
        names = _field_names(branch)
        if "x_warehouse_id" not in names:
            branch.setdefault("fields", []).append(
                {
                    "name": "x_warehouse_id",
                    "ttype": "many2one",
                    "relation": "stock.warehouse",
                    "string": "Warehouse",
                    "source": "apply_readiness",
                }
            )
            notes.append("apply: added x_warehouse_id on x_branch (stock link-only)")
        buttons.append(
            {
                "on_model": "x_branch",
                "label": "Warehouse",
                "related_model": "stock.warehouse",
                "relation_field": "x_warehouse_id",
                "icon": "fa-archive",
                "source": "apply_readiness",
                "link_only": True,
            }
        )
    draft.setdefault("review_notes", [])
    if isinstance(draft["review_notes"], list):
        note = (
            "Stock: x_picking_id / x_warehouse_id are link-only — wire to stock.picking "
            "in Odoo before go-live; no automatic quant moves from metadata export."
        )
        if note not in draft["review_notes"]:
            draft["review_notes"].append(note)
    return notes


def prune_transfer_timezone_field(draft: dict[str, Any]) -> list[str]:
    """Timezone belongs on branch master data, not inter-branch transfers."""
    notes: list[str] = []
    by_id = _models_index(draft)
    transfer = by_id.get("x_branch_transfer")
    if not transfer:
        return notes
    names = _field_names(transfer)
    if "x_timezone" not in names:
        return notes
    _drop_model_fields(draft, "x_branch_transfer", {"x_timezone"})
    notes.append("apply: removed x_timezone from x_branch_transfer")
    return notes


def scrub_unused_domain_tags(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    tags = draft.get("tags")
    if not isinstance(tags, list) or "pos" not in tags:
        return notes
    models = draft.get("models") or []
    has_pos = any(
        isinstance(m, dict)
        and (
            "pos" in str(m.get("model") or "").lower()
            or "pos" in str(m.get("description") or "").lower()
        )
        for m in models
    )
    if has_pos:
        return notes
    draft["tags"] = [t for t in tags if str(t).lower() != "pos"]
    notes.append("apply: removed unused pos domain tag")
    return notes


def ensure_operational_companion_models(draft: dict[str, Any]) -> list[str]:
    """Restore x_task when x_event exists — common depth floor after reuse merge."""
    notes: list[str] = []
    by_id = _models_index(draft)
    if "x_event" not in by_id or "x_task" in by_id:
        return notes
    prompt = str(draft.get("_user_prompt") or "")
    word = _domain_label_word(prompt)
    branch_id = "x_branch" if "x_branch" in by_id else None
    fields: list[dict[str, Any]] = [
        {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
        {"name": "x_code", "ttype": "char", "string": "Reference"},
        {
            "name": "x_date_deadline",
            "ttype": "date",
            "string": "Deadline",
            "required": True,
        },
        {
            "name": "x_status",
            "ttype": "selection",
            "string": "Status",
            "selection": "[('draft','Draft'),('open','Open'),('done','Done'),('cancelled','Cancelled')]",
        },
        {"name": "x_notes", "ttype": "text", "string": "Notes"},
    ]
    if branch_id:
        fields.insert(
            2,
            {
                "name": "x_branch_id",
                "ttype": "many2one",
                "relation": branch_id,
                "string": "Branch",
            },
        )
    if "hr" in set(draft.get("depends") or []):
        fields.append(
            {
                "name": "x_staff_id",
                "ttype": "many2one",
                "relation": "hr.employee",
                "string": "Assigned",
            }
        )
    draft.setdefault("models", []).append(
        {
            "model": "x_task",
            "description": f"{word} Task",
            "mode": "new",
            "fields": fields,
            "source": "apply_readiness",
        }
    )
    notes.append("apply: restored x_task companion for x_event (depth floor)")
    return notes


def reconcile_depth_metadata(draft: dict[str, Any]) -> list[str]:
    """Recompute depth block after apply passes; clear stale regenerate flags."""
    notes: list[str] = []
    from app.ai_depth import compute_depth_metrics, depth_checklist, depth_gaps

    gaps = depth_gaps(draft)
    metrics = compute_depth_metrics(draft, exclude_depth_seed=True)
    checklist = depth_checklist(draft)
    seeded = any(
        isinstance(m, dict) and m.get("source") == "depth_seed" for m in (draft.get("models") or [])
    )
    draft["_depth"] = {
        **(draft.get("_depth") if isinstance(draft.get("_depth"), dict) else {}),
        "ok": not gaps,
        "gaps": gaps,
        "checklist": checklist,
        "metrics_without_seeds": metrics,
        "seeded": seeded and bool(gaps),
    }
    if not gaps and seeded:
        draft["_depth"]["seeded"] = False
        notes.append("apply: depth targets met — cleared seed regenerate flag")
    elif not gaps:
        notes.append("apply: depth targets met")
    return notes


def finalize_draft_readiness_metadata(draft: dict[str, Any]) -> list[str]:
    """Align critique readiness with scorecard after apply passes."""
    from app.ai_draft_scorecard import draft_scorecard

    notes: list[str] = []
    prompt = str(draft.get("_user_prompt") or "")
    scored = draft_scorecard(draft, user_prompt=prompt)
    draft["_scorecard"] = scored
    score = float(scored.get("score_0_10") or 0)
    findings = scored.get("findings") or []
    crit = draft.get("_critique")
    if isinstance(crit, dict) and score >= 9.9 and not findings:
        crit["ready"] = True
        stale = "Critique flagged not ready but gave no details"
        crit_notes = [n for n in (crit.get("notes") or []) if stale not in str(n)]
        crit["notes"] = crit_notes
        # Scorecard is authoritative after apply passes — drop stale repair suggestions.
        crit["suggestions"] = [
            s
            for s in (crit.get("suggestions") or [])
            if str(s).startswith("unapplied:")
        ]
        draft["_critique"] = crit
        notes.append("apply: critique marked ready (scorecard clean)")
    draft["_meta"] = {
        **(draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}),
        "score_0_10": score,
    }
    return notes


def filter_stale_enrich_warnings(warnings: list[str], draft: dict[str, Any]) -> list[str]:
    """Drop enrich warnings superseded by apply-readiness fixes."""
    by_id = _models_index(draft)
    depth = draft.get("_depth") if isinstance(draft.get("_depth"), dict) else {}
    kept: list[str] = []
    for warning in warnings:
        w = str(warning or "")
        if w.startswith("depth: company on "):
            model = w.replace("depth: company on ", "", 1).strip()
            names = _field_names(by_id.get(model) or {})
            if "company_id" in names or "x_company_id" in names:
                continue
        if w == "depth padded via generic seeds — regenerate recommended":
            if depth.get("ok") and not depth.get("gaps"):
                continue
        if w.startswith("depth: ambition=") and "still missing" in w:
            if depth.get("ok") and not depth.get("gaps"):
                continue
        if w.startswith("presentation:") and "line-total compute suggestion" in w:
            computed = {
                str(b.get("model"))
                for b in merge_custom_code_blocks(draft)
                if isinstance(b, dict) and b.get("model")
            }
            if computed:
                continue
        kept.append(w)
    return kept


def sanitize_automation_names(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        for key in ("name", "description"):
            val = str(auto.get(key) or "")
            cleaned = re.sub(r"\s+", " ", val).strip()
            if cleaned and cleaned != val:
                auto[key] = cleaned
                notes.append(f"apply: sanitized automation {key}")
        actions = auto.get("safe_actions")
        if isinstance(actions, list):
            for action in actions:
                if not isinstance(action, dict):
                    continue
                summary = str(action.get("summary") or "")
                cleaned = re.sub(r"\s+", " ", summary).strip()
                if cleaned and cleaned != summary:
                    action["summary"] = cleaned
                    notes.append("apply: sanitized automation action summary")
    return notes


def run_apply_readiness_pass(draft: dict[str, Any]) -> list[str]:
    """Fix blockers before Apply / template export."""
    notes: list[str] = []
    notes.extend(demote_parallel_billing_models(draft))
    notes.extend(normalize_depth_seed_naming(draft))
    notes.extend(resolve_duplicate_address_fields(draft))
    notes.extend(polish_branch_address_fields(draft))
    notes.extend(fix_branch_transfer_incoming_o2m(draft))
    notes.extend(consolidate_redundant_inventory_models(draft))
    notes.extend(ensure_relation_module_depends(draft))
    notes.extend(fix_assignee_staff_relations(draft))
    notes.extend(fix_reuse_link_only_consistency(draft))
    notes.extend(normalize_company_fields_for_export(draft))
    notes.extend(sync_company_fields_with_record_rules(draft))
    notes.extend(ensure_global_branch_fields(draft))
    notes.extend(prune_transfer_timezone_field(draft))
    notes.extend(fix_workflow_skip_terminal_transitions(draft))
    notes.extend(fix_inventory_adjustment_workflow(draft))
    notes.extend(consolidate_inventory_count_fields(draft))
    notes.extend(wire_stock_document_links(draft))
    notes.extend(scrub_unused_domain_tags(draft))
    notes.extend(ensure_line_currency_fields(draft))
    notes.extend(normalize_line_monetary_fields(draft))
    notes.extend(apply_line_subtotal_computes(draft))
    notes.extend(apply_order_header_total_computes(draft))
    notes.extend(clear_resolved_compute_suggestions(draft))
    notes.extend(sanitize_automation_names(draft))
    notes.extend(dedupe_search_view_filters(draft))
    notes.extend(ensure_operational_companion_models(draft))
    notes.extend(reconcile_depth_metadata(draft))
    return notes


__all__ = [
    "apply_line_subtotal_computes",
    "apply_order_header_total_computes",
    "clear_resolved_compute_suggestions",
    "consolidate_inventory_count_fields",
    "consolidate_redundant_inventory_models",
    "dedupe_search_view_filters",
    "demote_parallel_billing_models",
    "ensure_global_branch_fields",
    "ensure_operational_companion_models",
    "ensure_line_currency_fields",
    "ensure_relation_module_depends",
    "ensure_unique_sequence_prefixes",
    "filter_stale_enrich_warnings",
    "finalize_draft_readiness_metadata",
    "fix_assignee_staff_relations",
    "fix_branch_transfer_incoming_o2m",
    "fix_broken_shift_assignee_smart_buttons",
    "fix_inventory_adjustment_workflow",
    "fix_reuse_link_only_consistency",
    "fix_workflow_skip_terminal_transitions",
    "normalize_company_fields_for_export",
    "normalize_line_monetary_fields",
    "polish_branch_address_fields",
    "prune_transfer_timezone_field",
    "reconcile_depth_metadata",
    "resolve_duplicate_address_fields",
    "run_apply_readiness_pass",
    "sanitize_automation_names",
    "scrub_unused_domain_tags",
    "sync_company_fields_with_record_rules",
    "wire_stock_document_links",
]
