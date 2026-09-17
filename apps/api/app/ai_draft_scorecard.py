"""Deterministic draft quality scorecard (GEN2-12)."""

from __future__ import annotations

import re
from typing import Any

from app.ai_domain_nouns import domain_noun_coverage, extract_prompt_nouns
from app.ai_post_critique import verify_model_ui_completeness
from app.ai_workflow_semantic import (
    _ALLOWED_INITIAL_TERMINALS,
    _INITIAL_STATES,
    classify_state,
    is_reset_to_draft_edge,
    synthesize_semantic_transitions,
)
from app.module_spec_codec import merge_custom_code_blocks

_GLOBAL_PROMPT_RE = re.compile(
    r"\b("
    r"around\s+the\s+world|international|global|worldwide|multi[\s-]?country|"
    r"across\s+countries|multiple\s+countries|multiple\s+branches"
    r")\b",
    re.I,
)
_LINE_QTY_NAMES = ("x_qty", "x_quantity", "quantity", "x_hours", "x_units")
_LINE_PRICE_NAMES = ("x_price", "x_unit_price", "x_price_unit", "x_rate", "price_unit")
_LINE_TOTAL_NAMES = ("x_subtotal", "x_total", "x_amount")

_FOREIGN_LEXICON = frozenset(
    {
        "retainer",
        "trust account",
        "disbursement",
        "matter",
        "hearing",
        "conflict check",
        "multi-party",
        "attorney",
        "solicitor",
        "barrister",
        "paralegal",
    }
)


def _models_index(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def _blob(draft: dict[str, Any]) -> str:
    import json

    # Internal stamps (architecture forbidden_clones, planner patterns) are not
    # operator-facing lexicon. Scoring the whole JSON invented false industry leaks.
    payload = {
        k: v
        for k, v in draft.items()
        if not str(k).startswith("_")
    }
    return json.dumps(payload, default=str).lower()


def _score_domain_fit(draft: dict[str, Any], prompt: str) -> tuple[float, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 10.0
    from app.ai_domain_packs import load_domain_pack, foreign_models_in_draft

    from app.ai_domain_coherence import rank_domain_packs, should_apply_domain_pack

    ranked = rank_domain_packs(prompt)
    expected_id = ranked[0][0] if ranked else ""
    expected_score = ranked[0][1] if ranked else 0.0
    actual = str(draft.get("domain_pack") or "")
    if (
        expected_id
        and actual
        and expected_id != actual
        and expected_score >= 0.10
    ):
        score -= 7.0
        findings.append(
            {
                "dimension": "domain_fit",
                "element": "domain_pack",
                "detail": (
                    f"prompt best matches {expected_id!r} (Jaccard={expected_score:.2f}) "
                    f"but draft has {actual!r}"
                ),
            }
        )
    elif actual:
        pack_body = load_domain_pack(actual)
        if pack_body:
            ok, _notes = should_apply_domain_pack(
                prompt,
                actual,
                pack_body,
                retrieval_method="scorecard",
            )
            if not ok and expected_id and expected_id != actual:
                score -= 5.0
                findings.append(
                    {
                        "dimension": "domain_fit",
                        "element": "domain_pack",
                        "detail": f"domain_pack {actual!r} fails coherence gate for prompt",
                    }
                )
    pack_body = load_domain_pack(actual) if actual else None
    if pack_body:
        foreign = foreign_models_in_draft(draft, pack_body)
        if foreign:
            score -= min(5.0, len(foreign) * 1.0)
            for mid in foreign[:8]:
                findings.append(
                    {
                        "dimension": "domain_fit",
                        "element": mid,
                        "detail": f"foreign model for {actual} pack",
                    }
                )
            if len(foreign) > 8:
                findings.append(
                    {
                        "dimension": "domain_fit",
                        "element": "models",
                        "detail": f"{len(foreign) - 8} more foreign models omitted from findings",
                    }
                )
    items, uncovered, _w = domain_noun_coverage(draft, prompt)
    # Pack is the domain contract — bag-of-words (Adeyemi, Nigeria, sandbox) must
    # not collapse domain_fit to 3.0 on a matched law-firm / hotel / clinic pack.
    engine = draft.get("_generation_engine") if isinstance(draft.get("_generation_engine"), dict) else {}
    stock_reuse = engine.get("capability") == "stock_reuse"
    if uncovered and not actual and not stock_reuse:
        score -= min(4.0, len(uncovered) * 1.5)
        for n in uncovered:
            findings.append(
                {"dimension": "domain_fit", "element": f"noun:{n}", "detail": "uncovered prompt noun"}
            )
    from app.ai_odoo_app_bar import GENERIC_LOOP_LEAVES, _generic_loop_leaf
    from app.ai_domain_packs import match_domain_pack
    from app.ai_stock_first import list_stock_clone_models

    by_id = _models_index(draft)
    prompt_l = prompt.lower()
    pack_backed = bool(draft.get("domain_pack") or match_domain_pack(prompt))
    for mid in list_stock_clone_models(draft):
        score -= 1.5
        findings.append(
            {
                "dimension": "domain_fit",
                "element": mid,
                "detail": (
                    "stock clone on packed/reuse residual — "
                    "use Community Accounting/HR/Calendar/Project, not a parallel x_*"
                ),
            }
        )
    loop_hits = 0
    if not pack_backed:
        for mid in by_id:
            if not mid.startswith("x_") or mid.endswith("_line"):
                continue
            generic = _generic_loop_leaf(mid)
            if not generic or generic not in GENERIC_LOOP_LEAVES:
                continue
            if generic in prompt_l or f"{generic}s" in prompt_l:
                continue
            loop_hits += 1
            findings.append(
                {
                    "dimension": "domain_fit",
                    "element": mid,
                    "detail": f"generic ops-loop model {generic!r} not requested by prompt",
                }
            )
        if loop_hits:
            score -= min(5.0, loop_hits * 1.2)
    _stock_fk = {
        "partner",
        "user",
        "company",
        "currency",
        "country",
        "state",
        "uom",
        "product",
        "employee",
        "parent",
        "account",
    }
    for mid, model in by_id.items():
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "many2one":
                continue
            fname = str(field.get("name") or "")
            match = re.match(r"^x_(.+)_id$", fname)
            if not match:
                continue
            leaf = match.group(1)
            if leaf in _stock_fk:
                continue
            target = f"x_{leaf}"
            rel = str(field.get("relation") or "")
            if target in by_id and rel != target:
                score -= 1.5
                findings.append(
                    {
                        "dimension": "domain_fit",
                        "element": f"{mid}.{fname}",
                        "detail": f"FK should target {target}, got {rel}",
                    }
                )
    if not pack_backed:
        from app.ai_odoo_app_bar import _find_site_model, _NEEDS_SITE_TOKENS

        site = _find_site_model(draft)
        if site:
            for mid, model in by_id.items():
                if mid == site or mid.endswith("_line"):
                    continue
                if not any(tok in mid for tok in _NEEDS_SITE_TOKENS):
                    continue
                has_site = any(
                    isinstance(f, dict)
                    and f.get("ttype") == "many2one"
                    and str(f.get("relation") or "") == site
                    for f in (model.get("fields") or [])
                )
                if not has_site:
                    score -= 1.0
                    findings.append(
                        {
                            "dimension": "domain_fit",
                            "element": mid,
                            "detail": f"missing site FK to {site}",
                        }
                    )
        clone_ids = {"x_currency", "x_payment", "x_crew", "x_line_item"}
        for mid in clone_ids:
            if mid not in by_id:
                continue
            if mid == "x_line_item" and not any(
                m.endswith("_line") and m != "x_line_item" for m in by_id
            ):
                continue
            score -= 1.2
            findings.append(
                {
                    "dimension": "domain_fit",
                    "element": mid,
                    "detail": f"parallel stock clone {mid}",
                }
            )
    vocab = draft.get("vocab") if isinstance(draft.get("vocab"), dict) else {}
    vocab_keys = {str(k).lower() for k in vocab}
    anti = " ".join(str(x) for x in (draft.get("anti_patterns") or [])).lower()
    blob = _blob(draft)
    legal_native = actual == "law_firm" or bool(
        re.search(r"(?i)\b(law\s*firm|legal\s+practice|attorney|solicitor|matter\s+file)\b", prompt)
    )
    for term in _FOREIGN_LEXICON:
        if legal_native:
            continue
        if term in prompt.lower():
            continue
        if term in vocab_keys:
            continue
        if term in anti and ("not" in anti or "do not" in anti):
            continue
        if re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", blob):
            score -= 1.0
            findings.append(
                {"dimension": "domain_fit", "element": term, "detail": "foreign-domain lexicon leak"}
            )
    from app.ai_domain_briefing import briefing_from_dict, build_domain_briefing
    from app.ai_selection import parse_selection_literal

    brief = briefing_from_dict(
        draft.get("_domain_briefing")
        if isinstance(draft.get("_domain_briefing"), dict)
        else None
    ) or build_domain_briefing(prompt)
    if actual == "law_firm" and brief.collocation_id in {
        "farm",
        "restaurant",
        "hotel",
        "salon",
    }:
        score -= 4.0
        findings.append(
            {
                "dimension": "domain_fit",
                "element": "domain_briefing",
                "detail": (
                    f"law_firm pack stamped with {brief.collocation_id} collocation "
                    f"({brief.industry})"
                ),
            }
        )
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "selection":
                continue
            keys = {
                k for k, _ in (parse_selection_literal(field.get("selection")) or [])
            }
            hits = keys & brief.banned_selection_keys
            if not hits:
                continue
            score -= min(3.0, len(hits) * 1.5)
            findings.append(
                {
                    "dimension": "domain_fit",
                    "element": f"{mid}.{field.get('name')}",
                    "detail": (
                        "foreign-industry selection keys: "
                        + ", ".join(sorted(hits))
                    ),
                }
            )
    reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
    for row in reuse.get("catalog_suggestions") or []:
        if not isinstance(row, dict):
            continue
        model = str(row.get("model") or "")
        if not brief.bans_stock(model):
            continue
        score -= 2.0
        findings.append(
            {
                "dimension": "domain_fit",
                "element": model,
                "detail": "banned catalog reuse (false-friend stock model)",
            }
        )
    return max(0.0, score), findings


def _score_structure(draft: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 10.0
    ui_items = verify_model_ui_completeness(draft)
    bad = [c for c in ui_items if not c.get("ok")]
    if bad:
        score -= min(5.0, len(bad) * 1.2)
        for c in bad:
            findings.append(
                {
                    "dimension": "structure",
                    "element": c["id"],
                    "detail": c.get("detail") or "incomplete UI scaffold",
                }
            )
    by_id = _models_index(draft)
    for mid, model in by_id.items():
        if mid.endswith("_line"):
            parent_fk = any(
                isinstance(f, dict)
                and f.get("ttype") == "many2one"
                and str(f.get("relation") or "") in by_id
                and not str(f.get("relation") or "").endswith("_line")
                for f in (model.get("fields") or [])
            )
            if not parent_fk:
                score -= 1.5
                findings.append(
                    {
                        "dimension": "structure",
                        "element": mid,
                        "detail": "line model missing parent m2o",
                    }
                )
    if not draft.get("domain_pack"):
        from app.ai_odoo_app_bar import _JOB_HEADER_LEAVES, _job_header_model_ids
        from app.ai_domain_density import _prompt_token_hit

        headers = _job_header_model_ids(draft)
        prompt = str(draft.get("_user_prompt") or "")
        prompt_hits = [
            leaf
            for leaf in _JOB_HEADER_LEAVES
            if _prompt_token_hit(prompt, (leaf,))
        ]
        hit_models = [
            m for m in headers if m.replace("x_", "", 1) in prompt_hits
        ]
        if len(headers) >= 2 and len(hit_models) < 2:
            score -= 2.0
            findings.append(
                {
                    "dimension": "structure",
                    "element": ",".join(sorted(headers)),
                    "detail": "parallel job headers (engagement/project/matter/case) — keep one",
                }
            )
        header_set = set(headers)
        if header_set:
            for mid, model in by_id.items():
                if mid.endswith("_line") or mid in header_set:
                    continue
                parts = mid.replace("x_", "", 1).split("_")
                is_output = any(p in {"deliverable", "output"} for p in parts)
                is_cost = (
                    any(p in {"expense", "cost", "disbursement"} for p in parts)
                    and "rate" not in parts
                )
                if not (is_output or is_cost):
                    continue
                has_job = any(
                    isinstance(f, dict)
                    and f.get("ttype") == "many2one"
                    and str(f.get("relation") or "") in header_set
                    for f in (model.get("fields") or [])
                )
                if not has_job:
                    score -= 1.5
                    findings.append(
                        {
                            "dimension": "structure",
                            "element": mid,
                            "detail": "missing job-header FK on deliverable/cost",
                        }
                    )
    from app.ai_odoo_app_bar import _line_primary_parent

    line_groups: dict[str, list[str]] = {}
    for mid, model in by_id.items():
        parent = _line_primary_parent(mid, model, by_id)
        if not parent:
            continue
        line_groups.setdefault(parent, []).append(mid)
    for parent, lines in line_groups.items():
        unique = sorted(set(lines))
        if len(unique) < 2:
            continue
        score -= 1.5
        findings.append(
            {
                "dimension": "structure",
                "element": ",".join(unique),
                "detail": f"duplicate line models on {parent} — keep one",
            }
        )
    depends = {str(d) for d in (draft.get("depends") or [])}
    if "product" not in depends:
        uses_product = any(
            isinstance(f, dict)
            and str(f.get("relation") or "") in {"product.product", "product.template"}
            for model in by_id.values()
            for f in (model.get("fields") or [])
        )
        if uses_product:
            score -= 1.0
            findings.append(
                {
                    "dimension": "structure",
                    "element": "product.product",
                    "detail": "stock relation product.product without depends product",
                }
            )
    from app.ai_odoo_app_bar import (
        _ASSET_MODEL_TOKENS,
        _BOOKING_TOKENS,
        _CORRUPT_LABEL_RE,
        _cost_header_ids,
        _find_role_model,
        _header_has_lines,
        _is_asset_catalog,
        _is_rate_card_model,
        _is_uom_register_model,
        _model_has_uom_selection,
    )

    if not draft.get("domain_pack"):
        cost_ids = _cost_header_ids(draft)
        lined = [m for m in cost_ids if _header_has_lines(draft, m)]
        hollow = [m for m in cost_ids if m not in lined]
        if lined and hollow:
            score -= 1.5
            findings.append(
                {
                    "dimension": "structure",
                    "element": ",".join(sorted(hollow)),
                    "detail": "hollow duplicate cost header (no line child) — collapse into the lined cost document",
                }
            )
        assets = [mid for mid in by_id if _is_asset_catalog(mid)]
        booking = _find_role_model(draft, _BOOKING_TOKENS, skip=("line",))
        has_asset_line = any(
            mid.endswith("_line") and any(tok in mid for tok in _ASSET_MODEL_TOKENS)
            for mid in by_id
        )
        if assets and booking and not has_asset_line:
            score -= 1.0
            findings.append(
                {
                    "dimension": "structure",
                    "element": f"{assets[0]}_line",
                    "detail": "equipment catalog missing usage line on booking/session",
                }
            )
        for mid in by_id:
            if not mid.endswith("_usage"):
                continue
            stem = mid[: -len("_usage")]
            line_id = f"{stem}_line"
            if stem in by_id and line_id in by_id and any(
                tok in stem for tok in _ASSET_MODEL_TOKENS
            ):
                score -= 1.5
                findings.append(
                    {
                        "dimension": "structure",
                        "element": f"{mid},{line_id}",
                        "detail": "parallel asset usage and line — keep the booking-parented line",
                    }
                )
        cards = [mid for mid in by_id if _is_rate_card_model(mid)]
        units = [
            mid
            for mid in by_id
            if _is_uom_register_model(mid) and f"{mid}_line" not in by_id
        ]
        keep_card = next(
            (c for c in cards if _model_has_uom_selection(by_id[c])), None
        )
        if keep_card and units:
            score -= 1.0
            findings.append(
                {
                    "dimension": "structure",
                    "element": f"{units[0]},{keep_card}",
                    "detail": (
                        "duplicate UOM register beside a rate card that already "
                        "has a unit selection — fold the register into the card"
                    ),
                }
            )
    for mid, model in by_id.items():
        o2m_rels = {
            str(f.get("relation") or "")
            for f in (model.get("fields") or [])
            if isinstance(f, dict)
            and f.get("ttype") == "one2many"
            and str(f.get("relation") or "").startswith("x_")
        }
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            rel = str(field.get("relation") or "")
            if (
                field.get("ttype") == "many2one"
                and rel in o2m_rels
                and any(
                    p in {"role", "type", "category", "tag", "uom", "reason"}
                    for p in rel.replace("x_", "", 1).split("_")
                )
                and not any(
                    p in {"role", "type", "category", "tag", "uom", "reason"}
                    for p in mid.replace("x_", "", 1).split("_")
                )
            ):
                score -= 1.0
                findings.append(
                    {
                        "dimension": "structure",
                        "element": f"{mid}.{field.get('name')}",
                        "detail": "parent M2O plus O2M to the same model — drop the M2O",
                    }
                )
            raw = str(field.get("string") or "")
            if _CORRUPT_LABEL_RE.search(raw):
                score -= 0.8
                findings.append(
                    {
                        "dimension": "structure",
                        "element": f"{mid}.{field.get('name')}",
                        "detail": "corrupt field string (JSON fragment in label)",
                    }
                )
        if mid.endswith("_line"):
            mixins = {str(x) for x in (model.get("mixins") or [])}
            if mixins & {"mail.thread", "mail.activity.mixin"}:
                score -= 0.5
                findings.append(
                    {
                        "dimension": "structure",
                        "element": mid,
                        "detail": "line model has chatter chrome — demote to a line",
                    }
                )
            for view in draft.get("views") or []:
                if not isinstance(view, dict):
                    continue
                if str(view.get("model") or "") != mid or str(view.get("type") or "") != "form":
                    continue
                arch = str(view.get("arch") or "").lower()
                if (
                    'widget="statusbar"' in arch
                    or "<chatter" in arch
                    or "oe_chatter" in arch
                ):
                    score -= 0.5
                    findings.append(
                        {
                            "dimension": "structure",
                            "element": mid,
                            "detail": "line form has document chrome (statusbar/chatter)",
                        }
                    )
                    break
    return max(0.0, score), findings


def _selection_keys(selection: Any) -> list[str]:
    if isinstance(selection, list):
        return [str(x[0]) for x in selection if isinstance(x, (list, tuple)) and x]
    if isinstance(selection, str):
        return re.findall(r"\('([^']+)'\s*,", selection)
    return []


def _score_semantics(draft: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 10.0
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or not model.get("is_workflow"):
            continue
        mid = str(model.get("model") or "")
        sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
        keys = list(sf.get("states") or [])
        if not keys:
            for f in model.get("fields") or []:
                if isinstance(f, dict) and f.get("name") == "x_status":
                    keys = _selection_keys(f.get("selection"))
        transitions = sf.get("transitions") or []
        if keys and not transitions:
            transitions, _vis = synthesize_semantic_transitions(keys)
        terminal = {k for k in keys if classify_state(k) != "active"}
        visible = [str(s) for s in (sf.get("statusbar_visible") or []) if str(s) in set(keys)]
        for a, b in transitions:
            if str(a) not in terminal:
                continue
            if is_reset_to_draft_edge(str(a), str(b)):
                continue
            if (
                visible
                and str(a) in visible
                and str(b) in visible
                and visible.index(str(b)) == visible.index(str(a)) + 1
            ):
                continue
            score -= 1.5
            findings.append(
                {
                    "dimension": "semantics",
                    "element": f"{mid}.{a}",
                    "detail": "terminal state has outgoing edge",
                }
            )
        if model.get("is_workflow"):
            field_names = {str(f.get("name")) for f in (model.get("fields") or []) if isinstance(f, dict)}
            if "x_status" not in field_names:
                score -= 2.0
                findings.append(
                    {
                        "dimension": "semantics",
                        "element": mid,
                        "detail": "workflow flag without status field",
                    }
                )
        if "x_status" in {str(f.get("name")) for f in (model.get("fields") or [])} and not sf:
            score -= 2.0
            findings.append(
                {
                    "dimension": "semantics",
                    "element": mid,
                    "detail": "workflow model missing state_field",
                }
            )
        for a, b in transitions:
            if (
                str(a).lower() in _INITIAL_STATES
                and classify_state(str(b)) == "terminal_negative"
                and str(b).lower() not in _ALLOWED_INITIAL_TERMINALS
            ):
                score -= 1.5
                findings.append(
                    {
                        "dimension": "semantics",
                        "element": f"{mid}.{a}→{b}",
                        "detail": "draft/new skips to terminal without activation",
                    }
                )
        keyset = {str(k).lower() for k in keys}
        if ("completed" in keyset or "complete" in keyset) and "done" in keyset:
            score -= 1.0
            findings.append(
                {
                    "dimension": "semantics",
                    "element": f"{mid}.x_status",
                    "detail": "duplicate terminals completed and done — fold to done",
                }
            )
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        if str(auto.get("trigger")) == "on_write" and not str(auto.get("filter_domain") or "").strip():
            score -= 0.5
            findings.append(
                {
                    "dimension": "semantics",
                    "element": str(auto.get("name") or "automation"),
                    "detail": "on_write without filter_domain",
                }
            )
    from app.ai_odoo_app_bar import _BOOKING_TOKENS, _find_role_model

    by_id = _models_index(draft)
    engagement = _find_role_model(draft, ("engagement", "project", "matter", "case"))
    if engagement:
        for mid, model in by_id.items():
            if mid.endswith("_line") or not any(tok in mid for tok in _BOOKING_TOKENS):
                continue
            has = any(
                isinstance(f, dict)
                and f.get("ttype") == "many2one"
                and str(f.get("relation") or "") == engagement
                for f in (model.get("fields") or [])
            )
            if not has:
                score -= 1.0
                findings.append(
                    {
                        "dimension": "semantics",
                        "element": mid,
                        "detail": f"booking/session missing FK to {engagement}",
                    }
                )
    deliverable = _find_role_model(
        draft,
        ("deliverable", "output"),
        skip=("line", "cost", "rate", "card", "session", "booking"),
    )
    if deliverable:
        for mid, model in by_id.items():
            if mid.endswith("_line") or not any(
                tok in mid for tok in ("revision", "take", "version")
            ):
                continue
            has = any(
                isinstance(f, dict)
                and f.get("ttype") == "many2one"
                and str(f.get("relation") or "") == deliverable
                for f in (model.get("fields") or [])
            )
            if not has:
                score -= 1.0
                findings.append(
                    {
                        "dimension": "semantics",
                        "element": mid,
                        "detail": f"revision missing FK to {deliverable}",
                    }
                )
    for mid, model in by_id.items():
        if mid.endswith("_line") or not any(tok in mid for tok in _BOOKING_TOKENS):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if str(field.get("relation") or "") != "sale.order" and str(
                field.get("name") or ""
            ) != "x_sale_order_id":
                continue
            help_txt = str(field.get("help") or "").lower()
            if "link-only" not in help_txt and "link only" not in help_txt:
                score -= 0.8
                findings.append(
                    {
                        "dimension": "semantics",
                        "element": f"{mid}.x_sale_order_id",
                        "detail": "sale.order on session/booking must be link-only",
                    }
                )
    return max(0.0, score), findings


def _meaningful_search_filter_count(arch: str) -> int:
    count = 0
    for flt in re.findall(r"<filter\b[^>]*(?:/>|>[^<]*</filter>)", arch, flags=re.I):
        name_m = re.search(r'name="([^"]+)"', flt)
        name = (name_m.group(1) if name_m else "").lower()
        if name in {"all", "has_name"}:
            continue
        if "group_by" in flt or "groupby" in flt.lower():
            count += 1
            continue
        if re.search(r"x_status|x_date|x_time_|x_check_|x_.*_id", flt):
            count += 1
    return count


def _score_ux(draft: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 10.0
    by_id = _models_index(draft)
    action_models = {
        str(a.get("model"))
        for a in (draft.get("actions") or [])
        if isinstance(a, dict) and a.get("model")
    }
    search_by_model = {
        str(v.get("model")): str(v.get("arch") or "")
        for v in (draft.get("views") or [])
        if isinstance(v, dict) and str(v.get("type") or "") == "search"
    }
    missing_search = {
        m
        for m in action_models - set(search_by_model)
        if str((by_id.get(m) or {}).get("mode") or "new") != "inherit" and str(m).startswith("x_")
    }
    if missing_search:
        score -= min(3.0, len(missing_search) * 0.8)
        for m in sorted(missing_search):
            findings.append(
                {"dimension": "ux", "element": m, "detail": "missing search view"}
            )
    for mid in action_models:
        if mid.endswith("_line"):
            continue
        arch = search_by_model.get(mid, "")
        if not arch:
            continue
        meaningful = _meaningful_search_filter_count(arch)
        if meaningful < 2:
            score -= 0.6
            findings.append(
                {
                    "dimension": "ux",
                    "element": mid,
                    "detail": "search view lacks meaningful filters (status/date/m2o group-by)",
                }
            )
    line_models = {m for m in by_id if m.endswith("_line")}
    for menu in draft.get("menus") or []:
        if not isinstance(menu, dict):
            continue
        parent = str(menu.get("parent_xml_id") or menu.get("parent") or "")
        action_ref = str(menu.get("action_xml_id") or "")
        for a in draft.get("actions") or []:
            if not isinstance(a, dict):
                continue
            if str(a.get("technical_name") or "") in action_ref and str(a.get("model") or "") in line_models:
                if not parent or parent.endswith("_menu_root"):
                    score -= 1.0
                    findings.append(
                        {
                            "dimension": "ux",
                            "element": str(a.get("model")),
                            "detail": "root menu on line model (should be parent-only)",
                        }
                    )
    for seq in draft.get("sequences") or []:
        if not isinstance(seq, dict):
            continue
        prefix = str(seq.get("prefix") or "")
        model = str(seq.get("model") or "")
        token = prefix.rstrip("/")
        # Whole-word prefixes (ENGAGEMENT/, EVENT/) and canonical shorts (PROMO/, WO/)
        # are fine; flag only a truncated segment like ENGA/ for x_engagement.
        parts = [p.upper() for p in model.replace("x_", "").split("_") if p]
        canonical_shorts = {
            "PROMO",
            "WO",
            "PTW",
            "INC",
            "SO",
            "TR",
            "ADJ",
            "CNT",
            "LOAN",
            "RC",
            "REASON",
            "CHECK",
            "COUNT",
            "ORDER",
            "BR",
            "STAFF",
        }
        if (
            token
            and 3 <= len(token) < 8
            and token not in parts
            and token not in canonical_shorts
            and any(
                len(p) >= 8 and p.startswith(token) and token != p
                for p in parts
            )
        ):
            score -= 0.5
            findings.append(
                {
                    "dimension": "ux",
                    "element": model,
                    "detail": f"sequence prefix {prefix!r} looks truncated — use whole-word token",
                }
            )
    labels: dict[tuple[str, str], int] = {}
    for btn in draft.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        key = (str(btn.get("on_model")), str(btn.get("label") or ""))
        labels[key] = labels.get(key, 0) + 1
    for key, count in labels.items():
        if count > 1:
            score -= 0.8
            findings.append(
                {
                    "dimension": "ux",
                    "element": key[1],
                    "detail": f"duplicate smart button label on {key[0]}",
                }
            )
    from app.ai_presentation import _menu_category

    action_xml = {
        str(a.get("technical_name") or ""): str(a.get("model") or "")
        for a in (draft.get("actions") or [])
        if isinstance(a, dict)
    }
    for menu in draft.get("menus") or []:
        if not isinstance(menu, dict) or not menu.get("action_xml_id"):
            continue
        parent = str(menu.get("parent_xml_id") or "")
        if "menu_sub_other_" not in parent:
            continue
        mid = action_xml.get(str(menu.get("action_xml_id") or ""), "")
        cat = _menu_category(str(menu.get("name") or ""), mid)
        if cat != "Other":
            score -= 1.2
            findings.append(
                {
                    "dimension": "ux",
                    "element": mid or str(menu.get("name")),
                    "detail": f"core {cat} menu parked under Other",
                }
            )
    return max(0.0, score), findings


def _score_hygiene(draft: dict[str, Any], *, user_prompt: str = "") -> tuple[float, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 10.0
    if draft.get("error"):
        score -= 5.0
        findings.append({"dimension": "hygiene", "element": "error", "detail": "top-level error key"})
    by_id = _models_index(draft)
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        names = {str(f.get("name")) for f in (model.get("fields") or []) if isinstance(f, dict)}
        if "x_address" in names and "x_address_id" in names:
            score -= 1.0
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": mid,
                    "detail": "duplicate address char + address_id",
                }
            )
        if "x_qty_adjusted" in names and "x_quantity" in names:
            score -= 0.8
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": mid,
                    "detail": "duplicate quantity fields (x_qty_adjusted + x_quantity)",
                }
            )
        for f in model.get("fields") or []:
            if not isinstance(f, dict):
                continue
            rel = str(f.get("relation") or "")
            ttype = str(f.get("ttype") or "")
            if rel and ttype not in {"many2one", "one2many", "many2many", "reference"}:
                score -= 1.0
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": f"{mid}.{f.get('name')}",
                        "detail": f"relation on non-relational field ({ttype})",
                    }
                )
            if rel == "hr.employee" and "hr" not in set(draft.get("depends") or []):
                score -= 1.5
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": mid,
                        "detail": "hr.employee relation without hr in depends",
                    }
                )
            if f.get("ttype") != "selection":
                continue
            sel = f.get("selection")
            if isinstance(sel, list):
                score -= 1.0
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": f"{mid}.{f.get('name')}",
                        "detail": "non-string selection",
                    }
                )
            elif isinstance(sel, str):
                from app.ai_selection import parse_selection_literal

                keys = _selection_keys(sel)
                if not keys and parse_selection_literal(sel) is None:
                    score -= 2.0
                    findings.append(
                        {
                            "dimension": "hygiene",
                            "element": f"{mid}.{f.get('name')}",
                            "detail": "unparsable selection literal",
                        }
                    )
                elif any(re.match(r"^option_[a-z]$", k, re.I) for k in keys):
                    score -= 0.8
                    findings.append(
                        {
                            "dimension": "hygiene",
                            "element": f"{mid}.{f.get('name')}",
                            "detail": "placeholder selection keys",
                        }
                    )
                pairs = parse_selection_literal(sel) or []
                if len(pairs) == 1:
                    from app.ai_selection import snake_selection_key

                    key, label = pairs[0]
                    label_s = str(label or "").strip()
                    if (
                        snake_selection_key(label_s) != snake_selection_key(key)
                        and " " not in label_s
                    ):
                        score -= 1.0
                        findings.append(
                            {
                                "dimension": "hygiene",
                                "element": f"{mid}.{f.get('name')}",
                                "detail": "collapsed selection pair (one option, label looks like a second key)",
                            }
                        )
                from app.ai_apply_readiness import _parse_field_domain_keys

                dom_keys = _parse_field_domain_keys(f.get("domain"))
                if dom_keys and dom_keys != set(keys):
                    score -= 1.0
                    findings.append(
                        {
                            "dimension": "semantics",
                            "element": f"{mid}.{f.get('name')}",
                            "detail": "selection keys disagree with field domain allowlist",
                        }
                    )
        from app.ai_odoo_app_bar import (
            _CRM_PARTY_FIELDS,
            _KEEP_SELECTION_NAMES,
            _selection_key_set,
        )

        sel_groups: dict[frozenset[str], list[str]] = {}
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "selection":
                continue
            fname = str(field.get("name") or "")
            if not fname or fname in _KEEP_SELECTION_NAMES:
                continue
            keys = _selection_key_set(field)
            if len(keys) >= 2:
                sel_groups.setdefault(keys, []).append(fname)
        for dup_names in sel_groups.values():
            if len(dup_names) >= 2:
                score -= 0.8
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": f"{mid}.{dup_names[0]}",
                        "detail": (
                            "duplicate identical selections "
                            f"({', '.join(dup_names)}) — keep the unit/uom field"
                        ),
                    }
                )
        field_names = {
            str(f.get("name") or "")
            for f in (model.get("fields") or [])
            if isinstance(f, dict)
        }
        leftover_crm = field_names & _CRM_PARTY_FIELDS
        if leftover_crm and (
            any(
                tok in mid
                for tok in ("artist", "guest", "patient", "member", "tenant")
            )
            or "_role" in mid
        ):
            score -= 0.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": f"{mid}.{next(iter(leftover_crm))}",
                    "detail": "party register still has CRM leftover last_interaction",
                }
            )
    prefixes: dict[str, str] = {}
    for seq in draft.get("sequences") or []:
        if not isinstance(seq, dict):
            continue
        prefix = str(seq.get("prefix") or "")
        model = str(seq.get("model") or "")
        if prefix and model:
            if prefix in prefixes and prefixes[prefix] != model:
                score -= 0.8
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": prefix,
                        "detail": "duplicate sequence prefix",
                    }
                )
            prefixes[prefix] = model
    for rule in draft.get("record_rules") or []:
        if not isinstance(rule, dict):
            continue
        dom = str(rule.get("domain_force") or "")
        model = str(rule.get("model") or "")
        mdef = by_id.get(model) or {}
        mnames = {str(f.get("name")) for f in (mdef.get("fields") or []) if isinstance(f, dict)}
        uses_module_company = bool(re.search(r"\(['\"]company_id['\"]\s*,", dom))
        uses_live_company = bool(re.search(r"\(['\"]x_company_id['\"]\s*,", dom))
        if uses_module_company and not uses_live_company and "x_company_id" in mnames:
            score -= 2.0
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": model,
                    "detail": "record rule uses company_id but model has x_company_id",
                }
            )
        if uses_live_company and "company_id" in mnames and "x_company_id" not in mnames:
            score -= 2.0
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": model,
                    "detail": "record rule uses x_company_id but model has company_id",
                }
            )
        if uses_module_company and not uses_live_company and "company_id" not in mnames and "x_company_id" not in mnames:
            score -= 2.0
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": model,
                    "detail": "record rule references company_id but model lacks field",
                }
            )
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    if _GLOBAL_PROMPT_RE.search(prompt):
        for model in draft.get("models") or []:
            if not isinstance(model, dict):
                continue
            mid = str(model.get("model") or "")
            desc = str(model.get("description") or "").lower()
            if "transfer" in mid or "transfer" in desc:
                continue
            if mid != "x_branch" and "branch" not in mid and "branch" not in desc:
                continue
            names = {str(f.get("name")) for f in (model.get("fields") or []) if isinstance(f, dict)}
            if "x_country_id" not in names:
                score -= 1.5
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": mid,
                        "detail": "global prompt but branch model missing x_country_id",
                    }
                )
    compute_models = {
        str(b.get("model"))
        for b in merge_custom_code_blocks(draft)
        if isinstance(b, dict) and b.get("model")
    }
    for btn in draft.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        if (
            str(btn.get("on_model") or "") == "x_staff_shift"
            and str(btn.get("related_model") or "") in {"x_event", "x_task"}
            and str(btn.get("relation_field") or "") == "x_staff_id"
        ):
            score -= 1.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": str(btn.get("label") or "smart_button"),
                    "detail": "shift smart button uses x_staff_id after assignee→employee fix",
                }
            )
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or "line" not in mid.lower():
            continue
        fields = {str(f.get("name")) for f in (model.get("fields") or []) if isinstance(f, dict)}
        qty = any(n in fields for n in _LINE_QTY_NAMES)
        price = any(n in fields for n in _LINE_PRICE_NAMES)
        total = any(n in fields for n in _LINE_TOTAL_NAMES)
        if qty and price and total and mid not in compute_models:
            score -= 1.0
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": mid,
                    "detail": "line qty×price without stored subtotal compute",
                }
            )
        for f in model.get("fields") or []:
            if not isinstance(f, dict) or f.get("name") != "x_staff_id":
                continue
            rel = str(f.get("relation") or "")
            if rel == "x_staff_shift" and mid in {"x_event", "x_task"}:
                score -= 1.0
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": f"{mid}.x_staff_id",
                        "detail": "assignee points to shift row not employee/user",
                    }
                )
    header_models = {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and any(
            isinstance(f, dict) and str(f.get("name")) in {
                "x_amount_total",
                "x_total_cost",
                "x_total",
                "x_amount",
            }
            for f in (m.get("fields") or [])
        )
        and any(
            isinstance(f, dict)
            and f.get("ttype") == "one2many"
            and "line" in str(f.get("relation") or "").lower()
            for f in (m.get("fields") or [])
        )
    }
    for mid in header_models:
        if mid not in compute_models:
            score -= 0.8
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": mid,
                    "detail": "order header total not computed from line subtotals",
                }
            )
    anti = list(draft.get("anti_patterns") or [])
    forbid_capture = any(
        re.search(r"payment capture|recurring billing engines|folio settlement", str(p), re.I)
        for p in anti
    )
    if forbid_capture:
        from app.ai_apply_readiness import (
            _HEADER_TAX_FIELDS,
            _SHADOW_HEADER_TOTALS,
            _field_implies_payment_capture,
            _header_primary_total,
        )

        for model in draft.get("models") or []:
            if not isinstance(model, dict):
                continue
            mid = str(model.get("model") or "")
            if not mid.startswith("x_"):
                continue
            for f in model.get("fields") or []:
                if not isinstance(f, dict):
                    continue
                if _field_implies_payment_capture(f):
                    score -= 1.5
                    findings.append(
                        {
                            "dimension": "hygiene",
                            "element": f"{mid}.{f.get('name')}",
                            "detail": "payment capture field violates pack anti-pattern (link stock docs only)",
                        }
                    )
            if "invoice" in mid.lower() and model.get("is_workflow"):
                score -= 2.0
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": mid,
                        "detail": "parallel billing workflow violates pack anti-pattern (link account.move only)",
                    }
                )
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if mid not in compute_models:
            continue
        from app.ai_apply_readiness import (
            _HEADER_TAX_FIELDS,
            _SHADOW_HEADER_TOTALS,
            _header_primary_total,
        )

        fields = {
            str(f.get("name")): f for f in (model.get("fields") or []) if isinstance(f, dict)
        }
        primary = _header_primary_total(fields, compute_models, mid)
        if not primary:
            continue
        for shadow in _SHADOW_HEADER_TOTALS:
            if shadow in fields and shadow != primary:
                score -= 0.8
                findings.append(
                    {
                        "dimension": "hygiene",
                        "element": f"{mid}.{shadow}",
                        "detail": "shadow header total duplicates computed primary total",
                    }
                )
        if any(n in fields for n in _HEADER_TAX_FIELDS):
            score -= 0.6
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": mid,
                    "detail": "header tax amount without tax compute or line tax fields",
                }
            )
    from app.ai_apply_readiness import (
        _field_names as _apply_field_names,
        _is_procurement_header,
        _is_sales_header,
        _pick_campaign_model,
        _pick_sales_order_header,
    )

    by_id = {
        str(m.get("model")): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        names = _apply_field_names(model)
        if "x_purchase_order_id" in names and _is_sales_header(model):
            score -= 0.8
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": f"{mid}.x_purchase_order_id",
                    "detail": "purchase.order link on sales-shaped header",
                }
            )
        if "x_sale_order_id" in names and _is_procurement_header(model):
            score -= 0.8
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": f"{mid}.x_sale_order_id",
                    "detail": "sale.order link on procurement-shaped header",
                }
            )
    campaign_id = _pick_campaign_model(by_id)
    order_id = _pick_sales_order_header(by_id)
    if campaign_id and order_id:
        order = by_id.get(order_id) or {}
        campaign = by_id.get(campaign_id) or {}
        order_names = _apply_field_names(order)
        campaign_suffix = campaign_id.removeprefix("x_")
        m2o_name = f"x_{campaign_suffix}_id"
        alt_m2o = ("x_discount_id", "x_campaign_id", "x_coupon_id", "x_voucher_id")
        has_order_link = m2o_name in order_names or any(name in order_names for name in alt_m2o)
        if not has_order_link:
            score -= 0.4
            findings.append(
                {
                    "dimension": "semantics",
                    "element": order_id,
                    "detail": "campaign/order models exist but order header lacks promotion link",
                }
            )
        has_reverse = any(
            isinstance(field, dict)
            and field.get("ttype") == "one2many"
            and str(field.get("relation") or "") == order_id
            for field in (campaign.get("fields") or [])
        )
        if not has_reverse:
            score -= 0.3
            findings.append(
                {
                    "dimension": "semantics",
                    "element": campaign_id,
                    "detail": "campaign model lacks reverse order relation",
                }
            )
    from app.ai_apply_readiness import _automation_signature, _selection_keys as _apply_selection_keys

    auto_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        sig = _automation_signature(auto)
        if sig[0] and sig[1]:
            auto_groups.setdefault(sig, []).append(auto)
    for sig, group in auto_groups.items():
        if len(group) > 1:
            score -= 0.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": sig[0],
                    "detail": "duplicate automation signature (model/trigger/domain)",
                }
            )
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        mid = str(auto.get("model") or "")
        model = by_id.get(mid)
        if not model:
            continue
        from app.ai_odoo_app_bar import _filter_is_only_terminal_status

        actions = [a for a in (auto.get("safe_actions") or []) if isinstance(a, dict)]
        trigger = str(auto.get("trigger") or auto.get("trg") or "on_write")
        if (
            trigger in {"on_write", "on_create_or_write", "on_create", "write", "create"}
            and actions
            and all(a.get("kind") == "next_activity" for a in actions)
            and _filter_is_only_terminal_status(str(auto.get("filter_domain") or ""))
        ):
            score -= 0.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": str(auto.get("name") or mid),
                    "detail": "hollow To Do on terminal status (record is already done)",
                }
            )
        fields_by_name = {
            str(field.get("name")): field
            for field in (model.get("fields") or [])
            if isinstance(field, dict) and field.get("name")
        }
        for action in auto.get("safe_actions") or []:
            if not isinstance(action, dict):
                continue
            kind = str(action.get("kind") or "")
            field = str(action.get("field") or "")
            if kind not in {"object_write", "update_field"} or field not in fields_by_name:
                continue
            fdef = fields_by_name[field]
            if str(fdef.get("ttype")) != "selection":
                continue
            keys = _apply_selection_keys(fdef.get("selection"))
            val = str(action.get("value") or "")
            if keys and val and val not in keys:
                score -= 0.8
                findings.append(
                    {
                        "dimension": "semantics",
                        "element": f"{mid}.{field}",
                        "detail": f"automation writes invalid selection value {val!r}",
                    }
                )
    for v in draft.get("views") or []:
        if not isinstance(v, dict) or str(v.get("type") or "") != "search":
            continue
        arch = str(v.get("arch") or "")
        names = re.findall(r'name="([^"]+)"', arch)
        if len(names) != len(set(names)):
            score -= 0.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": str(v.get("model") or "search"),
                    "detail": "duplicate search filter names",
                }
            )
    for model in draft.get("models") or []:
        if isinstance(model, dict) and str(model.get("description") or "").startswith("Super "):
            score -= 0.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": str(model.get("model") or ""),
                    "detail": "generic depth_seed label (Super *)",
                }
            )
    meta = draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}
    if meta:
        actual = len(draft.get("smart_buttons") or [])
        if meta.get("smart_button_count") not in (None, actual):
            score -= 0.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": "_meta.smart_button_count",
                    "detail": "count drift",
                }
            )
    status = draft.get("_llm_status") if isinstance(draft.get("_llm_status"), dict) else {}
    if status.get("step") == 0 and status.get("completed_steps"):
        score -= 0.5
        findings.append(
            {
                "dimension": "hygiene",
                "element": "_llm_status",
                "detail": "step not finalized after completion",
            }
        )
    tech = str(draft.get("technical_name") or "").replace(".", "_")
    expected_user = f"group_{tech}_user" if tech else ""
    stale_groups = 0
    for rule in draft.get("access_rules") or []:
        if not isinstance(rule, dict):
            continue
        gid = str(rule.get("group") or "")
        if expected_user and gid and expected_user not in gid and "manager" not in gid:
            stale_groups += 1
        elif expected_user and "manager" in gid and f"group_{tech}_manager" != gid:
            stale_groups += 1
    if stale_groups:
        score -= min(2.0, 0.4 * stale_groups)
        findings.append(
            {
                "dimension": "hygiene",
                "element": "access_rules",
                "detail": "ACL groups do not match technical_name",
            }
        )
    group_ids = {
        str(g.get("id") or "")
        for g in (draft.get("groups") or [])
        if isinstance(g, dict)
    }
    if expected_user and group_ids and expected_user not in group_ids:
        score -= 1.0
        findings.append(
            {
                "dimension": "hygiene",
                "element": "groups",
                "detail": "stale/duplicate security groups vs technical_name",
            }
        )
    hollow = 0
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        fd = str(auto.get("filter_domain") or "").strip()
        actions = [a for a in (auto.get("safe_actions") or []) if isinstance(a, dict)]
        name = str(auto.get("name") or "")
        if fd in {"", "[]", "False"} and (
            not actions
            or all(
                a.get("kind") == "next_activity"
                and str(a.get("summary") or "") in {name, ""}
                for a in actions
            )
        ):
            hollow += 1
    if hollow:
        score -= min(2.0, hollow * 1.0)
        findings.append(
            {
                "dimension": "hygiene",
                "element": "automations",
                "detail": f"{hollow} hollow automation(s) with empty filter_domain",
            }
        )
    from app.ai_odoo_app_bar import _FAKE_ACTION_VALUE_RE, _filter_domain_is_atom_list
    from app.ai_selection import canonicalize_selection_pairs, parse_selection_literal

    fake_autos = 0
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        if _filter_domain_is_atom_list(auto.get("filter_domain")):
            fake_autos += 1
            continue
        for action in auto.get("safe_actions") or []:
            if not isinstance(action, dict):
                continue
            value = str(action.get("value") or "").strip()
            if value and _FAKE_ACTION_VALUE_RE.match(value):
                fake_autos += 1
                break
    if fake_autos:
        score -= min(2.0, fake_autos * 1.0)
        findings.append(
            {
                "dimension": "hygiene",
                "element": "automations",
                "detail": f"{fake_autos} automation(s) with invalid domain or non-metadata action",
            }
        )
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        for field in model.get("fields") or []:
            if not isinstance(field, dict) or field.get("ttype") != "selection":
                continue
            pairs = parse_selection_literal(field.get("selection")) or []
            _, _, changed = canonicalize_selection_pairs(pairs)
            if not changed:
                continue
            score -= 0.5
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": f"{mid}.{field.get('name')}",
                    "detail": "selection keys need snake_case / case-fold / antonym repair",
                }
            )
    by_id = _models_index(draft)
    has_move = any(
        isinstance(f, dict) and str(f.get("relation") or "") == "account.move"
        for m in by_id.values()
        for f in (m.get("fields") or [])
    )
    parallel_bill = [
        mid
        for mid, model in by_id.items()
        if model.get("is_workflow")
        and ("bill" in mid or "invoice" in mid)
        and not mid.endswith("_line")
    ]
    if has_move and parallel_bill:
        score -= 2.0
        findings.append(
            {
                "dimension": "hygiene",
                "element": parallel_bill[0],
                "detail": "parallel x_* invoice workflow wrapping account.move",
            }
        )
    from app.ai_live_apply_contract import live_apply_contract_findings

    contract = live_apply_contract_findings(draft)
    if contract:
        score -= min(3.0, 1.0 * len(contract))
        findings.extend(contract)

    # Phase 1 / 6 — architecture fit, security, minimality (scorecard findings)
    from app.ai_architecture_plan import architecture_plan_drift, stamp_architecture_plan

    if not isinstance(draft.get("_architecture_plan"), dict):
        stamp_architecture_plan(draft, prompt=user_prompt)
    drift = architecture_plan_drift(draft)
    draft["_architecture_drift"] = drift
    if drift:
        score -= min(2.5, 0.6 * len(drift))
        findings.append(
            {
                "dimension": "hygiene",
                "element": "architecture_fit",
                "detail": "; ".join(drift[:6]),
            }
        )

    x_new = [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and str(m.get("mode") or "") != "inherit"
    ]
    acl_models: set[str] = set()
    for r in draft.get("access_rules") or []:
        if not isinstance(r, dict):
            continue
        raw = str(r.get("model") or r.get("model_id") or "").strip()
        if not raw:
            continue
        acl_models.add(raw)
        # Pack stubs use ir.model.access style model_x_matter
        if raw.startswith("model_"):
            acl_models.add(raw[len("model_") :])
        elif not raw.startswith("model_"):
            acl_models.add(f"model_{raw.replace('.', '_')}")
            acl_models.add(f"model_{raw}")
    missing_acl = [
        mid
        for mid in x_new
        if mid
        and mid not in acl_models
        and f"model_{mid}" not in acl_models
        and f"model_{mid.replace('.', '_')}" not in acl_models
    ]
    if missing_acl and len(x_new) > 0:
        score -= min(2.0, 0.5 * len(missing_acl))
        findings.append(
            {
                "dimension": "hygiene",
                "element": "security_acl",
                "detail": f"new x_* missing access_rules: {', '.join(missing_acl[:6])}",
            }
        )

    multi_co = bool(draft.get("multi_company"))
    if multi_co and x_new:
        rules = draft.get("record_rules") or draft.get("ir_rule") or []
        if not rules:
            score -= 0.8
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": "security_record_rule",
                    "detail": "multi-company hinted but no record rules on custom models",
                }
            )

    static = draft.get("_static_odoo") if isinstance(draft.get("_static_odoo"), dict) else {}
    sudo_hits = [
        f
        for f in (static.get("findings") or [])
        if isinstance(f, dict) and f.get("rule") == "sudo_call"
    ]
    if sudo_hits:
        score -= min(1.5, 0.5 * len(sudo_hits))
        findings.append(
            {
                "dimension": "hygiene",
                "element": "security_sudo",
                "detail": f"{len(sudo_hits)} unjustified sudo() in custom_code_blocks",
            }
        )

    plan = draft.get("_architecture_plan") if isinstance(draft.get("_architecture_plan"), dict) else {}
    budget = plan.get("surface_budget") if isinstance(plan.get("surface_budget"), dict) else {}
    if budget:
        actual_models = len(x_new)
        try:
            lim = int(budget.get("new_models") or 99)
        except (TypeError, ValueError):
            lim = 99
        if actual_models > lim:
            score -= min(2.0, 0.4 * (actual_models - lim))
            findings.append(
                {
                    "dimension": "hygiene",
                    "element": "minimality",
                    "detail": f"new_models {actual_models} exceeds surface_budget {lim}",
                }
            )

    return max(0.0, score), findings


def draft_scorecard(
    spec: dict[str, Any],
    *,
    user_prompt: str = "",
) -> dict[str, Any]:
    """Score draft 0–10 across five weighted dimensions."""
    from app.ai_draft_validators import run_draft_validators

    prompt = user_prompt or str(spec.get("_user_prompt") or "")
    from app.ai_operator_brief import intent_corpus

    nouns_src = intent_corpus(prompt) or prompt
    weights = {
        "domain_fit": 0.25,
        "structure": 0.25,
        "semantics": 0.20,
        "ux": 0.15,
        "hygiene": 0.15,
    }
    dim_scores: dict[str, float] = {}
    findings: list[dict[str, Any]] = []
    for name, fn in (
        ("domain_fit", lambda: _score_domain_fit(spec, prompt)),
        ("structure", lambda: _score_structure(spec)),
        ("semantics", lambda: _score_semantics(spec)),
        ("ux", lambda: _score_ux(spec)),
        ("hygiene", lambda: _score_hygiene(spec, user_prompt=prompt)),
    ):
        s, f = fn()
        dim_scores[name] = round(s, 2)
        findings.extend(f)
    score_0_10 = round(
        sum(dim_scores[k] * weights[k] for k in weights),
        2,
    )
    validators = run_draft_validators(spec)
    for vf in validators["xml_findings"]:
        findings.append(
            {
                "dimension": "validators",
                "element": vf.get("element"),
                "detail": vf.get("detail"),
            }
        )
    for vf in validators["consistency_findings"]:
        findings.append(
            {
                "dimension": "validators",
                "element": vf.get("element"),
                "detail": vf.get("detail"),
            }
        )
    if validators["xml_findings"]:
        score_0_10 = min(score_0_10, 6.0)
    elif validators["consistency_findings"]:
        score_0_10 = min(score_0_10, 7.0)
    pack_mismatch = any(
        f.get("dimension") == "domain_fit" and f.get("element") == "domain_pack"
        for f in findings
    )
    if pack_mismatch:
        score_0_10 = min(score_0_10, 4.0)
    extraneous = [
        f
        for f in findings
        if "foreign model for" in str(f.get("detail", ""))
        or "incoherent" in str(f.get("detail", ""))
        or "stock clone" in str(f.get("detail", ""))
    ]
    if len(extraneous) >= 3:
        score_0_10 = min(score_0_10, 5.0)
    card = {
        "score_0_10": score_0_10,
        "dimensions": dim_scores,
        "findings": findings,
        "prompt_nouns": extract_prompt_nouns(nouns_src),
        "validators": validators,
    }
    from app.ai_option_a_quality import apply_option_a_score_cap

    apply_option_a_score_cap(card, spec)
    return card


def attach_scorecard(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    catalog: list[dict[str, Any]] | None = None,
    installed_modules: list[str] | None = None,
) -> dict[str, Any]:
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    from app.ai_architecture_plan import stamp_architecture_plan
    from app.ai_planner_tools import stamp_planner_grounding
    from app.ai_static_odoo import stamp_static_odoo
    from app.ai_stock_first import connection_catalog_from_draft

    ctx = connection_catalog_from_draft(draft)
    cat = catalog if catalog is not None else ctx.get("stock")
    installed = installed_modules if installed_modules is not None else ctx.get("installed_modules")

    stamp_architecture_plan(draft, prompt=prompt)
    stamp_planner_grounding(draft, catalog=cat, installed_modules=installed)
    if draft.get("custom_code_blocks") or draft.get("_capability_primary_option_a"):
        stamp_static_odoo(draft)

    draft["_scorecard"] = draft_scorecard(draft, user_prompt=prompt)
    # Studio Contract scorecard — deterministic gate, independent of LLM tier.
    try:
        from app.ai_studio_contract import evaluate_studio_contract, attach_studio_contract

        if not isinstance(draft.get("_studio_contract"), dict):
            attach_studio_contract(draft, prompt)
        contract_score = evaluate_studio_contract(draft)
        draft["_contract_scorecard"] = contract_score
        sc = draft["_scorecard"]
        if isinstance(sc, dict):
            sc["studio_contract"] = {
                "pass": contract_score.get("pass"),
                "blocking": contract_score.get("blocking"),
                "repairs": contract_score.get("repairs") or [],
                "summary": contract_score.get("summary"),
            }
            if contract_score.get("blocking"):
                findings = list(sc.get("findings") or [])
                for f in contract_score.get("findings") or []:
                    if isinstance(f, dict) and f.get("severity") == "error":
                        findings.append(
                            {
                                "dimension": "studio_contract",
                                "element": f.get("code") or "contract",
                                "detail": f.get("detail") or "",
                                "severity": "error",
                            }
                        )
                sc["findings"] = findings
                sc["studio_contract_blocks_apply"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ai_rules import completeness_checklist

        draft["_completeness"] = completeness_checklist(draft, user_prompt=prompt)
    except Exception:  # noqa: BLE001
        pass
    from app.ai_option_a_quality import stamp_done_bar

    stamp_done_bar(draft, prompt=prompt)
    # Re-apply cap after done_bar in case smoke was stamped earlier in the same call.
    from app.ai_option_a_quality import apply_option_a_score_cap

    apply_option_a_score_cap(draft["_scorecard"], draft)

    from app.ai_certification import stamp_certification

    stamp_certification(draft)
    live = draft.get("_live_apply")
    cert = draft.get("_certification")
    if isinstance(live, dict) and isinstance(cert, dict) and cert.get("tier"):
        live["certification_tier"] = cert["tier"]
    return draft["_scorecard"]


def scorecard_required_repairs(scorecard: dict[str, Any]) -> list[str]:
    """Map scorecard findings to critique-style repair hints."""
    out: list[str] = []
    for f in scorecard.get("findings") or []:
        if not isinstance(f, dict):
            continue
        dim = f.get("dimension")
        el = f.get("element")
        detail = f.get("detail")
        out.append(f"scorecard({dim}): {el} — {detail}")
    return out


__all__ = [
    "attach_scorecard",
    "draft_scorecard",
    "scorecard_required_repairs",
]
