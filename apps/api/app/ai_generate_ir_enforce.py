"""Hard GenerateIR closure — handoff §3 invariants enforced at Generate finish.

After residual Generate, every spray-family field/M2O/O2M/menu must be
cue-traceable, approved_craft, structural default, or proposal-admitted.
Anything else is purged. Scrub mutate is obsolete — this is the spine.

LLM enrich may invent freely *as proposals*; only ``admit_and_apply`` /
``purge_unadmitted_spray`` decide what survives. Domain packs are not the
production default invent path — they seed a floor; the gate still applies.
"""

from __future__ import annotations

import re
from typing import Any

_SPRAY_FIELD_NAMES = frozenset(
    {
        "x_company_id",
        "company_id",
        "x_purchase_order_id",
        "x_po_id",
        "x_purchase_id",
        "x_invoice_id",
        "x_bill_id",
        "x_move_id",
        "x_currency_id",
        "x_partner_id",
        "x_contact_id",
        "x_customer_id",
        "x_client_id",
    }
)
_SPRAY_RELS = frozenset(
    {
        "res.company",
        "purchase.order",
        "account.move",
        "res.currency",
        "res.partner",
    }
)
_SEED_HUBS = frozenset({"x_party", "x_rate", "x_agreement", "x_deposit"})
_TIME_CUE_RE = re.compile(
    r"(?i)\b(?:"
    r"date\s*time|datetime|timestamp|time\s+slot|scheduled?\s+slot|"
    r"check[- ]?in|check[- ]?out|clock[- ]?in|clock[- ]?out|"
    r"appointment\s+time|start\s+time|end\s+time|"
    r"time\s+in|time\s+out"
    r")\b"
)


def _craft(draft: dict[str, Any]) -> dict[str, Any]:
    raw = draft.get("_approved_craft")
    return raw if isinstance(raw, dict) else {}


def _prompt(draft: dict[str, Any]) -> str:
    return str(draft.get("_user_prompt") or "")


_MONEY_AMOUNT_NAME_RE = re.compile(
    r"(?i)(?:amount|price|total|cost|fee|subtotal|balance|rate)"
)


def _draft_has_money_amounts(draft: dict[str, Any]) -> bool:
    """True when the draft already carries amount/price/monetary columns.

    Prompt-only money cues miss pack/fixture graphs that already invented totals —
    those graphs *are* the money cue (Wave 7 honesty: keep companion currency).
    """
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "")
            ttype = str(field.get("ttype") or "")
            if ttype == "monetary" or field.get("currency_field"):
                return True
            if ttype in {"float", "integer", "monetary"} and _MONEY_AMOUNT_NAME_RE.search(
                name
            ):
                return True
    return False


def _settings_craft(key: str) -> bool:
    try:
        from app.settings import settings

        return bool(getattr(settings, f"ai_craft_{key}", False))
    except Exception:  # noqa: BLE001
        return False


def _is_thin_residual(draft: dict[str, Any]) -> bool:
    """Thin residual full_app without a curated domain pack — closed-IR primary target.

    Empty/unstamped shape on a multi-model comprehensive draft is NOT thin —
    architecture-close and workspace graphs must keep company/currency/partner
    structure. Only positively thin shapes (or ambition=thin) get spray purge.
    """
    if draft.get("domain_pack") or draft.get("_component"):
        return False
    if str(draft.get("_ambition") or "") == "comprehensive":
        return False
    grain = str(draft.get("grain") or "").lower()
    if grain in {"field_pack", "feature_slice"}:
        return False
    shape = str(draft.get("_document_shape") or "")
    if shape == "workspace":
        return False
    if shape in {"register", "catalog", "transactional_header"}:
        return True
    if str(draft.get("_ambition") or "") == "thin":
        return True
    # Unstamped shape: only thin when a single custom header (true residual).
    customs = [
        m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    ]
    if len(customs) <= 2 and grain in {"", "full_app"}:
        return True
    return False


def _admitted_names(draft: dict[str, Any]) -> set[str]:
    """Names admitted via merge_proposals — not the full fields_by_model snapshot."""
    ir = draft.get("_generate_ir") if isinstance(draft.get("_generate_ir"), dict) else {}
    names: set[str] = set()
    for row in ir.get("admitted") or []:
        if isinstance(row, dict) and row.get("name"):
            names.add(str(row["name"]))
    return names


def _field_allowed(
    *,
    name: str,
    rel: str,
    draft: dict[str, Any],
    admitted: set[str],
) -> bool:
    if name in admitted:
        return True
    craft = _craft(draft)
    prompt = _prompt(draft)
    if name == "x_currency_id" or rel == "res.currency":
        return bool(
            craft.get("money_slots")
            or _settings_craft("money_slots")
            or re.search(
                r"(?i)\b(?:amount|currency|price|total|money|fee|payment|cost)\b",
                prompt,
            )
            or _draft_has_money_amounts(draft)
        )
    # Company→Contact uses technical name x_company_id with relation res.partner —
    # that is a party link, never multi-company scoping spray.
    if rel == "res.partner" or name in {
        "x_partner_id",
        "x_contact_id",
        "x_customer_id",
        "x_client_id",
    }:
        return bool(
            craft.get("partner_links")
            or _settings_craft("partner_links")
            or re.search(
                r"(?i)\b(?:customers?|vendors?|clients?)\b|"
                r"\b(?:linked?|related|optional)\s+(?:a\s+)?(?:contacts?|partners?|res\.partner)\b|"
                r"\bres\.partner\b|"
                r"\balready\s+a\s+contact\b|"
                r"\blink\s+to\s+(?:a\s+)?contacts?\b|"
                r"\bcompan(?:y|ies)\s*\(\s*link|"
                r"\bcompan(?:y|ies)\s*→\s*contact|"
                r"\b(?:contact|partner)\s+(?:link|field|m2o|many2one)\b|"
                r"\bpartner\s+id\b",
                prompt,
            )
        )
    if (name in {"x_company_id", "company_id"} or rel == "res.company") and rel != "res.partner":
        return bool(
            craft.get("company_scoping")
            or _settings_craft("company_scoping")
            or re.search(r"(?i)\bmulti[\s-]?compan|legal[\s-]?entit", prompt)
        )
    if name in {"x_purchase_order_id", "x_po_id", "x_purchase_id"} or rel == "purchase.order":
        return bool(
            craft.get("purchase_link")
            or _settings_craft("purchase_link")
            or re.search(
                r"(?i)\bpurchase\s+orders?\b|\blink(?:ed)?\s+(?:a\s+)?(?:purchase|PO)\b|\bRFQ\b",
                prompt,
            )
        )
    if name in {"x_invoice_id", "x_bill_id", "x_move_id"} or rel == "account.move":
        return bool(
            re.search(
                r"(?i)\b(?:related|linked|optional)\s+invoices?\b|"
                r"\binvoice\s+(?:link|field)|customer\s+invoices?\b",
                prompt,
            )
        )
    return True


def _datetime_allowed(label: str, draft: dict[str, Any]) -> bool:
    craft = _craft(draft)
    if craft.get("datetime_over_date") or _settings_craft("datetime_over_date"):
        return True
    prompt = _prompt(draft)
    blob = f"{label} {prompt}"
    if _TIME_CUE_RE.search(blob):
        return True
    try:
        from app.ai_field_ir import infer_date_or_datetime

        return infer_date_or_datetime(label, draft=draft) == "datetime"
    except Exception:  # noqa: BLE001
        return False


def _date_allowed(label: str, draft: dict[str, Any]) -> bool:
    craft = _craft(draft)
    if craft.get("date_slots") or _settings_craft("date_slots"):
        return True
    prompt = _prompt(draft)
    blob = f"{label} {prompt}"
    try:
        from app.ai_brief_cues import brief_has_date_cue

        return brief_has_date_cue(blob)
    except Exception:  # noqa: BLE001
        return False


def purge_unadmitted_spray(draft: dict[str, Any]) -> list[str]:
    """Remove spray-family fields/models not allowed by cue/craft/admission."""
    notes: list[str] = []
    from app.ai_generate_ir import stamp_generate_ir

    stamp_generate_ir(draft)
    admitted = _admitted_names(draft)
    craft = _craft(draft)
    prompt = _prompt(draft)
    thin = _is_thin_residual(draft)

    drop_mids: set[str] = set()
    # Depth-seed hubs only on thin residuals without craft (workspace/packs keep theirs).
    if thin and not (craft.get("depth_seeds") or _settings_craft("depth_seeds")):
        for m in draft.get("models") or []:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("model") or "")
            src = str(m.get("source") or "")
            if mid in _SEED_HUBS or src == "depth_seed":
                drop_mids.add(mid)

    if re.search(r"(?i)\bchecklist\b", prompt) and re.search(
        r"(?i)\bparts?\s+used\b|\bparts?\b.*\bqty\b", prompt
    ):
        by_rel: dict[str, set[str]] = {}
        for m in draft.get("models") or []:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("model") or "")
            for f in m.get("fields") or []:
                if isinstance(f, dict) and str(f.get("ttype")) == "one2many":
                    by_rel.setdefault(mid, set()).add(str(f.get("relation") or ""))
        for mid, rels in by_rel.items():
            if any("checklist" in r for r in rels) and any("parts" in r for r in rels):
                drop_mids.add(f"{mid}_line")

    if drop_mids:
        draft["models"] = [
            m
            for m in (draft.get("models") or [])
            if not (isinstance(m, dict) and str(m.get("model") or "") in drop_mids)
        ]
        notes.append(
            "generate_ir: purged unadmitted seed/generic models "
            + ", ".join(sorted(drop_mids))
        )

    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        # Party satellites may keep Contact when party was admitted; still gate spray.
        kept: list[dict[str, Any]] = []
        dropped: list[str] = []
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                continue
            name = str(f.get("name") or "")
            rel = str(f.get("relation") or "")
            ttype = str(f.get("ttype") or "")
            lab = str(f.get("string") or name)
            if ttype == "datetime" and not _datetime_allowed(lab, draft):
                f = {**f, "ttype": "date"}
                notes.append(f"generate_ir: coerced {mid}.{name} datetime→date")
            if (
                ttype == "date"
                and thin
                and name not in admitted
                and not _date_allowed(lab, draft)
            ):
                dropped.append(name or "date")
                continue
            if thin and (name in _SPRAY_FIELD_NAMES or rel in _SPRAY_RELS):
                # On party/line satellites, Contact M2O is structural when party exists.
                if (
                    rel == "res.partner"
                    and (mid.endswith("_party") or "party" in mid)
                    and name in {"x_partner_id", "x_contact_id"}
                ):
                    kept.append(f)
                    continue
                if not _field_allowed(name=name, rel=rel, draft=draft, admitted=admitted):
                    dropped.append(name or rel)
                    continue
            if rel in drop_mids:
                dropped.append(name or rel)
                continue
            kept.append(f)
        if dropped:
            m["fields"] = kept
            notes.append(
                f"generate_ir: purged unadmitted spray on {mid}: " + ", ".join(dropped)
            )
    return notes


def prune_menus_to_approved_models(draft: dict[str, Any]) -> list[str]:
    """L5 — root/document menus only for approved top-level models.

    Prefer closed GenerateIR model list when stamped; else live draft customs.
    """
    notes: list[str] = []
    top: set[str] = set()
    ir = draft.get("_generate_ir") if isinstance(draft.get("_generate_ir"), dict) else {}
    for row in ir.get("models") or []:
        if isinstance(row, dict) and str(row.get("model") or "").startswith("x_"):
            mid = str(row["model"])
            if mid.endswith(("_line", "_party", "_checklist_line", "_parts_line")):
                continue
            if str(row.get("source") or "") == "depth_seed":
                continue
            top.add(mid)
    if not top:
        for m in draft.get("models") or []:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("model") or "")
            if not mid.startswith("x_"):
                continue
            if mid.endswith("_line") or mid.endswith("_party") or mid.endswith(
                "_checklist_line"
            ) or mid.endswith("_parts_line"):
                continue
            if str(m.get("source") or "") == "depth_seed":
                continue
            top.add(mid)
    if not top:
        return notes

    actions = draft.get("actions") if isinstance(draft.get("actions"), list) else []
    action_model = {
        str(a.get("technical_name") or a.get("xml_id") or ""): str(a.get("model") or "")
        for a in actions
        if isinstance(a, dict)
    }
    menus = draft.get("menus")
    if not isinstance(menus, list):
        return notes
    kept: list[dict[str, Any]] = []
    dropped = 0
    for menu in menus:
        if not isinstance(menu, dict):
            continue
        act = str(menu.get("action_xml_id") or "")
        mid = action_model.get(act, "")
        if act and mid and mid.startswith("x_") and mid not in top:
            dropped += 1
            continue
        kept.append(menu)
    if dropped:
        draft["menus"] = kept
        notes.append(f"generate_ir: pruned {dropped} satellite menu(s) to approved models")

    ambition = str(draft.get("_ambition") or "")
    shape = str(draft.get("_document_shape") or "")
    if ambition == "thin" or shape in {"register", "catalog"} or (
        str(draft.get("grain") or "") == "full_app"
        and not draft.get("domain_pack")
        and shape != "workspace"
    ):
        new_menus: list[Any] = []
        seen_root = False
        for m in draft.get("menus") or []:
            if not isinstance(m, dict):
                continue
            is_root = not m.get("parent_xml_id") and not m.get("action_xml_id")
            if is_root:
                if seen_root:
                    continue
                new_menus.append(m)
                seen_root = True
            else:
                new_menus.append(m)
        before = len(draft.get("menus") or [])
        draft["menus"] = new_menus
        if len(new_menus) < before:
            notes.append("generate_ir: collapsed thin residual to one root menu")
    return notes


def gate_llm_draft_mutations(
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[str]:
    """Diff LLM enrich output vs prior IR; strip uncued spray invent (handoff §3).

    Call after Flash/LLM merge, before close. Ensures LLM invent cannot land
    company/PO/partner/currency without cue or approved_craft.
    """
    notes: list[str] = []
    if not isinstance(before, dict) or not isinstance(after, dict):
        return notes
    # Copy spray-relevant context onto after for allowance checks
    for key in ("_user_prompt", "_approved_craft", "_understanding", "_ambition", "grain", "_document_shape", "domain_pack"):
        if key in before and key not in after:
            after[key] = before[key]
    before_by = {
        str(m.get("model")): m
        for m in (before.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    admitted = _admitted_names(after)
    for model in after.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        prior = before_by.get(mid) or {}
        prior_names = {
            str(f.get("name"))
            for f in (prior.get("fields") or [])
            if isinstance(f, dict) and f.get("name")
        }
        kept: list[dict[str, Any]] = []
        dropped: list[str] = []
        for f in model.get("fields") or []:
            if not isinstance(f, dict):
                continue
            name = str(f.get("name") or "")
            rel = str(f.get("relation") or "")
            if name in prior_names:
                kept.append(f)
                continue
            if name in _SPRAY_FIELD_NAMES or rel in _SPRAY_RELS:
                if not _field_allowed(name=name, rel=rel, draft=after, admitted=admitted):
                    dropped.append(name or rel)
                    continue
            kept.append(f)
        if dropped:
            model["fields"] = kept
            notes.append(
                f"generate_ir: LLM gate dropped uncued spray on {mid}: "
                + ", ".join(dropped)
            )
    # New models invented by LLM with depth_seed-like hubs on thin residuals
    if _is_thin_residual(after) and not (
        _craft(after).get("depth_seeds") or _settings_craft("depth_seeds")
    ):
        drop = {
            str(m.get("model"))
            for m in (after.get("models") or [])
            if isinstance(m, dict)
            and str(m.get("model") or "") not in before_by
            and (
                str(m.get("model") or "") in _SEED_HUBS
                or str(m.get("source") or "") in {"llm", "flash", "depth_seed"}
                and str(m.get("model") or "") in _SEED_HUBS
            )
        }
        if drop:
            after["models"] = [
                m
                for m in (after.get("models") or [])
                if not (isinstance(m, dict) and str(m.get("model") or "") in drop)
            ]
            notes.append("generate_ir: LLM gate dropped hubs " + ", ".join(sorted(drop)))
    try:
        from app.ai_ir_trace import trace_ir

        trace_ir(after, stage="gate_llm_draft_mutations", notes=notes[-20:])
    except Exception:  # noqa: BLE001
        pass
    return notes


def enforce_closed_generate_ir(draft: dict[str, Any]) -> list[str]:
    """Single finish-gate: purge → prune menus → stamp closure (handoff §3.3)."""
    notes: list[str] = []
    notes.extend(purge_unadmitted_spray(draft))
    notes.extend(prune_menus_to_approved_models(draft))
    from app.ai_generate_ir import ir_closure_violations, stamp_generate_ir

    stamp_generate_ir(draft)
    left = ir_closure_violations(draft)
    try:
        from app.ai_generate_ir_lint import invent_outside_admit_violations

        left = left + invent_outside_admit_violations(draft)
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ai_generate_ir import draft_o2ms_outside_ir, o2ms_for_install

        o2ms_for_install(draft)
        outside = draft_o2ms_outside_ir(draft)
        if outside:
            left = left + [f"o2m_outside_ir:{h}" for h in outside[:20]]
    except Exception:  # noqa: BLE001
        pass
    scrub_hits: list[str] = []
    draft["_ir_scrub_violations"] = []

    ok = not left and not scrub_hits
    draft["_generate_ir_closure"] = {
        "ok": ok,
        "violations": left,
        "scrub_hits": scrub_hits,
        "notes": notes[-40:],
    }
    if not ok:
        notes.append(
            "generate_ir: CLOSURE FAIL " + "; ".join(left[:8] + scrub_hits[:8])
        )
        if _is_thin_residual(draft):
            try:
                gaps = draft.get("_studio_contract_gaps")
                if not isinstance(gaps, list):
                    gaps = []
                gaps.append(
                    {
                        "id": "generate_ir_closure",
                        "detail": "Unadmitted Generate invent survived finish gate",
                        "violations": left[:20],
                        "scrub_hits": scrub_hits[:20],
                    }
                )
                draft["_studio_contract_gaps"] = gaps
            except Exception:  # noqa: BLE001
                pass
    try:
        from app.ai_ir_trace import trace_ir

        trace_ir(
            draft,
            stage="enforce_closed_generate_ir",
            notes=notes[-20:],
            extra={"closure": draft.get("_generate_ir_closure")},
        )
    except Exception:  # noqa: BLE001
        pass
    return notes


__all__ = [
    "enforce_closed_generate_ir",
    "gate_llm_draft_mutations",
    "prune_menus_to_approved_models",
    "purge_unadmitted_spray",
]
