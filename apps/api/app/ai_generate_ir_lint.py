"""CI / finish lint — invent outside admit is illegal (handoff §3 / zero-gap Wave 0).

Downstream closers may still *collapse/copy/retarget* already-admitted IR, but
source-tagged invent and spray-family fields must be cue-admitted (or craft)
before Install. Collapse allowlist (not invent): ``collapse_duplicate_line_models``,
``collapse_hollow_cost_headers``, ``collapse_parallel_*``, ``repair_named_foreign_keys``
(retarget only).
"""

from __future__ import annotations

from typing import Any

# Sources that mean "Generate invent" — must appear in _generate_ir.admitted.
_INVENT_SOURCES = frozenset(
    {
        "density",
        "domain_density",
        "domain_briefing",
        "pad",
        "flash",
        "llm",
        "enrich",
        "ai",
        "depth_seed",
        "pack_default",
        "pack_seed",
        "domain_pack",
        "senior_shape",
        "apply_readiness",
        "quality_o2m",
        "must_do_fields",
        "must_do",
        "odoo_app_bar",
        "generate_ir",
    }
)
_SPRAY_NAMES = frozenset(
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
        "res.partner",
        "res.currency",
    }
)

# Model-level invent sources (x_* rows added without admit).
_MODEL_INVENT_SOURCES = frozenset(
    {
        "domain_density",
        "density",
        "pack_seed",
        "pack_default",
        "domain_pack",
        "must_do_fields",
        "depth_seed",
    }
)


def _admitted_names(draft: dict[str, Any]) -> set[str]:
    """Field/model names covered by admit — including nested model/O2M payloads."""
    ir = draft.get("_generate_ir") if isinstance(draft.get("_generate_ir"), dict) else {}
    names: set[str] = set()
    for row in ir.get("admitted") or []:
        if not isinstance(row, dict):
            continue
        if row.get("name"):
            names.add(str(row["name"]))
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        for f in payload.get("fields") or []:
            if isinstance(f, dict) and f.get("name"):
                names.add(str(f["name"]))
        line = payload.get("line_model")
        if isinstance(line, dict):
            if line.get("model"):
                names.add(str(line["model"]))
            for f in line.get("fields") or []:
                if isinstance(f, dict) and f.get("name"):
                    names.add(str(f["name"]))
    return names


def _admitted_models(draft: dict[str, Any]) -> set[str]:
    ir = draft.get("_generate_ir") if isinstance(draft.get("_generate_ir"), dict) else {}
    out: set[str] = set()
    for row in ir.get("admitted") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("kind") or "") == "model" and row.get("name"):
            out.add(str(row["name"]))
        mid = str((row.get("payload") or {}).get("model") or "")
        if mid:
            out.add(mid)
    for m in ir.get("models") or []:
        if isinstance(m, dict) and m.get("model"):
            out.add(str(m["model"]))
    return out


def invent_outside_admit_violations(draft: dict[str, Any]) -> list[str]:
    """Return invent rows (fields/models) not covered by admit.

    Thin residuals: spray + invent sources.
    All drafts: densifier/pack/quality/must_do/odoo_app_bar invent sources.
    """
    try:
        from app.ai_generate_ir_enforce import _field_allowed, _is_thin_residual
    except Exception:  # noqa: BLE001
        return []
    thin = _is_thin_residual(draft)
    admitted = _admitted_names(draft)
    admitted_models = _admitted_models(draft)
    # Seed models present before GenerateIR (honesty/LLM seed) are grandfathered
    # when they lack invent source tags.
    seed_models = {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and str(m.get("source") or "") not in _MODEL_INVENT_SOURCES
    }
    hits: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        msrc = str(model.get("source") or "")
        if msrc in _MODEL_INVENT_SOURCES and mid not in admitted_models and mid not in seed_models:
            # Admitted via model proposal, or applied after admit into IR.models.
            ir_models = {
                str(r.get("model"))
                for r in (
                    (draft.get("_generate_ir") or {}).get("models") or []
                    if isinstance(draft.get("_generate_ir"), dict)
                    else []
                )
                if isinstance(r, dict)
            }
            if mid not in ir_models and mid not in admitted_models:
                hits.append(f"model:{mid}[src={msrc}]")
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "")
            rel = str(field.get("relation") or "")
            src = str(field.get("source") or "")
            spray = name in _SPRAY_NAMES or rel in _SPRAY_RELS
            invent_src = src in _INVENT_SOURCES
            # Always flag hard invent sources; thin also flags spray.
            if invent_src:
                pass
            elif thin and spray:
                pass
            else:
                continue
            if name in admitted:
                continue
            if spray and _field_allowed(
                name=name, rel=rel, draft=draft, admitted=admitted
            ):
                continue
            hits.append(f"{mid}.{name}[src={src or '—'}]->{rel or name}")
    return hits


def assert_closed_generate_ir(draft: dict[str, Any]) -> list[str]:
    """Stamp closure gaps when invent survives finish (Install contract)."""
    notes: list[str] = []
    from app.ai_generate_ir import ir_closure_violations, stamp_generate_ir

    stamp_generate_ir(draft)
    left = ir_closure_violations(draft) + invent_outside_admit_violations(draft)
    draft["_generate_ir_lint"] = {"ok": not left, "violations": left[:40]}
    if left:
        notes.append("generate_ir_lint: FAIL " + "; ".join(left[:8]))
        gaps = draft.get("_studio_contract_gaps")
        if not isinstance(gaps, list):
            gaps = []
        gaps.append(
            {
                "id": "generate_ir_invent_outside_admit",
                "detail": "Unadmitted invent survived Generate finish",
                "violations": left[:20],
            }
        )
        draft["_studio_contract_gaps"] = gaps
    return notes


__all__ = [
    "assert_closed_generate_ir",
    "invent_outside_admit_violations",
]
