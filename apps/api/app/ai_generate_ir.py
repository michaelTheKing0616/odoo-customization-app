"""GenerateIR — closed IR for residual Generate (handoff §3).

Additive spine: ``build_ir`` seeds from constraint AST / Must-do cues.
Passes may ``propose()``; only ``merge_proposals`` + ``apply_ir_to_draft``
may admit semantic content into the draft. Downstream compile/layout must
not invent fields/M2Os/O2Ms/menus beyond the closed IR.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ProposalKind = Literal["field", "model", "menu", "o2m", "m2o", "smart_button"]


@dataclass
class Proposal:
    kind: ProposalKind
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    source_cue: str | None = None
    confidence: float = 0.0
    rationale: str = ""
    proposer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GenerateIR:
    """Authoritative residual Generate IR — closed after ``build_ir`` / merge."""

    host_model: str | None = None
    display_name: str = ""
    technical_name: str = ""
    models: list[dict[str, Any]] = field(default_factory=list)
    fields_by_model: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    o2ms: list[dict[str, Any]] = field(default_factory=list)
    menus: list[dict[str, Any]] = field(default_factory=list)
    cues: dict[str, Any] = field(default_factory=dict)
    approved_craft: dict[str, Any] = field(default_factory=dict)
    structural_defaults: list[str] = field(default_factory=list)
    rejected_proposals: list[dict[str, Any]] = field(default_factory=list)
    admitted: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Cue-independent allowlist — keep short; review every addition (handoff §3.2b).
STRUCTURAL_DEFAULT_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Intentionally near-empty: force cue or approved_craft for craft fields.
    }
)


def _seed_spray_allowed(
    *, name: str, rel: str, prompt: str, craft: dict[str, Any]
) -> bool:
    """Cue check for first-stamp spray admit — keep in sync with enforce._field_allowed."""
    import re

    if rel == "res.partner" or name in {
        "x_partner_id",
        "x_contact_id",
        "x_customer_id",
        "x_client_id",
    }:
        return bool(
            craft.get("partner_links")
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
            or re.search(r"(?i)\bmulti[\s-]?compan|legal[\s-]?entit", prompt)
        )
    if name == "x_currency_id" or rel == "res.currency":
        return bool(
            craft.get("money_slots")
            or re.search(
                r"(?i)\b(?:amount|currency|price|total|money|fee|payment|cost)\b",
                prompt,
            )
        )
    if name in {"x_purchase_order_id", "x_po_id", "x_purchase_id"} or rel == "purchase.order":
        return bool(
            craft.get("purchase_link")
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
    return False


def _cue_tokens(constraint_ast: dict[str, Any] | None, draft: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    ast = constraint_ast if isinstance(constraint_ast, dict) else {}
    for key in ("fields", "states", "o2ms", "models", "menus", "must_do"):
        for row in ast.get(key) or []:
            if isinstance(row, str):
                tokens.add(row.lower())
            elif isinstance(row, dict):
                for k in ("name", "label", "id", "model", "string"):
                    if row.get(k):
                        tokens.add(str(row[k]).lower())
    und = draft.get("_understanding") if isinstance(draft.get("_understanding"), dict) else {}
    for row in und.get("must_do") or und.get("constraints") or []:
        if isinstance(row, str):
            tokens.add(row.lower())
        elif isinstance(row, dict) and row.get("label"):
            tokens.add(str(row["label"]).lower())
    prompt = str(draft.get("_user_prompt") or "")
    if prompt:
        tokens.add(prompt.lower())
    # Depend modules are legal stock-wire cues (hr / maintenance / project / stock).
    for dep in draft.get("depends") or []:
        d = str(dep).strip().lower()
        if d:
            tokens.add(d)
    return tokens


def build_ir(
    draft: dict[str, Any],
    *,
    constraint_ast: dict[str, Any] | None = None,
    approved_craft: dict[str, Any] | None = None,
) -> GenerateIR:
    """Seed GenerateIR from Must-do / constraint AST + current draft models (read-only copy)."""
    cues = _cue_tokens(constraint_ast, draft)
    craft = dict(approved_craft or draft.get("_approved_craft") or {})
    models: list[dict[str, Any]] = []
    fields_by_model: dict[str, list[dict[str, Any]]] = {}
    o2ms: list[dict[str, Any]] = []
    host: str | None = None
    for m in draft.get("models") or []:
        if not isinstance(m, dict) or not m.get("model"):
            continue
        mid = str(m["model"])
        row = {
            "model": mid,
            "description": m.get("description"),
            "mode": m.get("mode"),
            "source": m.get("source"),
            "is_workflow": m.get("is_workflow"),
        }
        models.append(row)
        flist: list[dict[str, Any]] = []
        for f in m.get("fields") or []:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            flist.append(dict(f))
            if str(f.get("ttype") or "") == "one2many":
                o2ms.append(
                    {
                        "name": f.get("name"),
                        "on_model": mid,
                        "relation": f.get("relation"),
                        "string": f.get("string"),
                    }
                )
        fields_by_model[mid] = flist
        if str(m.get("mode") or "") == "inherit" and not host:
            host = mid
        if not host and not mid.startswith("x_"):
            host = mid
    menus = [dict(x) for x in (draft.get("menus") or []) if isinstance(x, dict)]
    prior = draft.get("_generate_ir") if isinstance(draft.get("_generate_ir"), dict) else {}
    prior_admitted = [
        dict(row) for row in (prior.get("admitted") or []) if isinstance(row, dict)
    ]
    spray_names = {
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
    spray_rels = {
        "res.company",
        "purchase.order",
        "account.move",
        "res.partner",
        "res.currency",
    }
    if prior_admitted:
        seeded_admitted = prior_admitted
    else:
        # First stamp: admit non-spray seed + cue-allowed spray (Must-do Company→Contact).
        seeded_admitted = []
        admitted_names: set[str] = set()
        prompt = str(draft.get("_user_prompt") or "")
        craft = draft.get("_approved_craft") if isinstance(draft.get("_approved_craft"), dict) else {}
        for mid, flist in fields_by_model.items():
            for f in flist:
                fname = str(f.get("name") or "")
                if not fname:
                    continue
                rel = str(f.get("relation") or "")
                is_spray = fname in spray_names or rel in spray_rels
                if is_spray and not _seed_spray_allowed(
                    name=fname, rel=rel, prompt=prompt, craft=craft
                ):
                    continue
                admitted_names.add(fname)
                seeded_admitted.append(
                    {
                        "kind": "field",
                        "name": fname,
                        "payload": {
                            "model": mid,
                            **{k: v for k, v in f.items() if k != "name"},
                        },
                        "source_cue": "seed",
                        "admit_reason": "seed_snapshot",
                        "proposer": "build_ir",
                    }
                )
        for row in models:
            mid = str(row.get("model") or "")
            if mid:
                seeded_admitted.append(
                    {
                        "kind": "model",
                        "name": mid,
                        "payload": dict(row),
                        "source_cue": "seed",
                        "admit_reason": "seed_snapshot",
                        "proposer": "build_ir",
                    }
                )
    ir = GenerateIR(
        host_model=host,
        display_name=str(draft.get("display_name") or ""),
        technical_name=str(draft.get("technical_name") or ""),
        models=models,
        fields_by_model=fields_by_model,
        o2ms=o2ms,
        menus=menus,
        cues={"tokens": sorted(cues), "ast": constraint_ast or {}},
        approved_craft=craft,
        structural_defaults=sorted(STRUCTURAL_DEFAULT_ALLOWLIST),
        admitted=seeded_admitted,
    )
    draft["_generate_ir"] = ir.to_dict()
    return ir


def proposal_allowed(
    proposal: Proposal,
    *,
    ir: GenerateIR,
    schema_client: Any | None = None,
    draft: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Merge gate: cue / craft / structural / schema-verified stock reuse.

    (c) ``schema_verified_reuse`` never invents new ``x_*`` models by itself —
    it only confirms stock relations/fields the brief already cues.
    """
    name = (proposal.name or "").strip()
    if not name:
        return False, "empty_name"
    if name in STRUCTURAL_DEFAULT_ALLOWLIST or proposal.source_cue == "structural_default":
        return True, "structural_default"
    craft = ir.approved_craft or {}
    allow = craft.get("allow") if isinstance(craft.get("allow"), list) else []
    if name in {str(x) for x in allow}:
        return True, "approved_craft"
    toggle = str(proposal.payload.get("craft_key") or "").strip()
    if toggle and craft.get(toggle) is True:
        return True, f"approved_craft:{toggle}"
    try:
        from app.settings import settings

        if toggle and bool(getattr(settings, f"ai_craft_{toggle}", False)):
            return True, f"settings_craft:{toggle}"
    except Exception:  # noqa: BLE001
        pass

    # Must-do residual columns are the brief's closed constraints — always admit.
    if proposal.proposer in {
        "ai_document_shape.must_do",
        "must_do",
        "ai_document_shape",
    }:
        return True, "must_do_constraint"

    # Quality / apply scaffolds that repair already-present graph (not thin spray).
    if proposal.proposer in {
        "ai_model_quality.ensure_line_bill_link",
        "ai_apply_readiness.ensure_header_line_models",
        "ai_model_quality.deepen_thin_ops_children",
        "ai_model_quality.ensure_min_workflows",
    }:
        if draft is not None:
            try:
                from app.ai_generate_ir_enforce import _is_thin_residual

                if _is_thin_residual(draft) and _proposal_is_spray(proposal):
                    return False, "thin_spray_blocked"
            except Exception:  # noqa: BLE001
                pass
        if _proposal_is_spray(proposal):
            return False, "quality_spray_needs_cue"
        return True, "quality_scaffold"

    # Adopted pack floor may still supply cued line models / O2Ms.
    if (
        draft is not None
        and draft.get("domain_pack")
        and proposal.proposer
        in {"domain_pack", "ai_domain_packs", "ai_pipeline.pack_seed"}
    ):
        if _proposal_is_spray(proposal):
            return False, "pack_spray_needs_cue"
        return True, "pack_adopted"

    # Named Rate-Line class: maintenance/service lexical ≠ O2M cue.
    if _looks_like_generic_line_invent(proposal) and not _ast_has_o2m_or_line_cue(ir):
        return False, "uncued_line_invent"

    cue = (proposal.source_cue or "").strip().lower()
    tokens = set(ir.cues.get("tokens") or [])
    cue_hit = bool(
        cue and (cue in tokens or any(cue in t or t in cue for t in tokens))
    )
    bare = name.lower().removeprefix("x_")
    name_hit = bool(bare and any(bare in t or t in bare for t in tokens))

    if cue_hit or name_hit:
        if _stock_relation_reuse(proposal) and _schema_verifies_stock_m2o(
            proposal, schema_client
        ):
            return True, "schema_verified_reuse"
        return True, "cue_match" if cue_hit else "cue_name"

    # Comprehensive densifier role-fill (not thin residual): structural density.
    if proposal.proposer == "ai_domain_density" and draft is not None:
        try:
            from app.ai_generate_ir_enforce import _is_thin_residual

            if not _is_thin_residual(draft):
                return True, "density_role"
        except Exception:  # noqa: BLE001
            pass

    # (c) alone: reuse an *existing* stock field on a stock/inherit host — never new x_*.
    if (
        schema_client is not None
        and _existing_stock_field_reuse(proposal, schema_client)
        and _schema_verifies_stock_m2o(proposal, schema_client)
    ):
        return True, "schema_verified_reuse"

    return False, "no_cue_or_craft"


_PACK_SPRAY_NAMES = frozenset(
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
_PACK_SPRAY_RELS = frozenset(
    {
        "res.company",
        "purchase.order",
        "account.move",
        "res.partner",
        "res.currency",
    }
)


def _row_is_stock_spray(name: str, rel: str) -> bool:
    """True for Company/PO/Invoice/Partner/Currency invent onto stock models.

    Residual↔residual links (``relation`` starts with ``x_``) are not spray —
    e.g. ``x_bill_id`` → ``x_bill`` is a custom graph edge, not Accounting.
    """
    if rel.startswith("x_"):
        return False
    if rel in _PACK_SPRAY_RELS:
        return True
    if name in _PACK_SPRAY_NAMES:
        return True
    return False


def _proposal_is_spray(proposal: Proposal) -> bool:
    name = (proposal.name or "").strip()
    rel = str(proposal.payload.get("relation") or "")
    if _row_is_stock_spray(name, rel):
        return True
    for f in proposal.payload.get("fields") or []:
        if not isinstance(f, dict):
            continue
        if _row_is_stock_spray(str(f.get("name") or ""), str(f.get("relation") or "")):
            return True
    return False


_LINE_INVENT_NAME_RE = re.compile(
    r"(?i)(?:^x_)?(?:rate|service|price|billing)?_?lines?$|_line_ids$|rate_line|service_line"
)


def _looks_like_generic_line_invent(proposal: Proposal) -> bool:
    """Rate/service/generic ``*_line`` invent — not checklist/parts satellites."""
    name = (proposal.name or "").lower()
    if "checklist" in name or "parts" in name:
        return False
    line = proposal.payload.get("line_model")
    if isinstance(line, dict):
        lid = str(line.get("model") or "").lower()
        if "checklist" in lid or "parts" in lid:
            return False
        if lid.endswith("_line") or "rate_line" in lid:
            return True
    if proposal.kind == "model":
        mid = name
        if mid.endswith("_line") and "checklist" not in mid and "parts" not in mid:
            return True
    if proposal.kind == "o2m":
        rel = str(proposal.payload.get("relation") or "").lower()
        if "checklist" in rel or "parts" in rel:
            return False
        if _LINE_INVENT_NAME_RE.search(name) or rel.endswith("_line"):
            return True
    return False


def _ast_has_o2m_or_line_cue(ir: GenerateIR) -> bool:
    ast = ir.cues.get("ast") if isinstance(ir.cues.get("ast"), dict) else {}
    if ast.get("o2ms"):
        return True
    blob = " ".join(str(t) for t in (ir.cues.get("tokens") or []))
    return bool(
        re.search(
            r"(?i)\bchecklist\s+lines?\b|\bparts?\s+used\b|"
            r"\bo2m\b|\bone2many\b|"
            r"\b(?:line|lines|items|qty|quantity|hours)\b",
            blob,
        )
    )


def _stock_relation_reuse(proposal: Proposal) -> bool:
    if proposal.kind not in {"field", "m2o"}:
        return False
    if proposal.kind == "model" or proposal.payload.get("line_model"):
        return False
    rel = str(proposal.payload.get("relation") or "")
    if not rel or rel.startswith("x_"):
        return False
    mid = str(proposal.payload.get("model") or "")
    # New x_* model invent is never (c)-only; host may be x_* with stock M2O.
    return bool(mid)


def _existing_stock_field_reuse(proposal: Proposal, schema_client: Any) -> bool:
    """True when proposing an already-present stock field on a stock host."""
    if proposal.kind not in {"field", "m2o"}:
        return False
    mid = str(proposal.payload.get("model") or "")
    if not mid or mid.startswith("x_"):
        return False
    try:
        fg = schema_client.fields_get(mid) or {}
        return proposal.name in fg
    except Exception:  # noqa: BLE001
        return False


def _schema_verifies_stock_m2o(proposal: Proposal, schema_client: Any | None) -> bool:
    if schema_client is None:
        return False
    mid = str(proposal.payload.get("model") or "")
    rel = str(proposal.payload.get("relation") or "")
    if not mid or not rel or rel.startswith("x_"):
        return False
    try:
        if not schema_client.model_exists(rel):
            return False
        fg = schema_client.fields_get(mid) or {}
        if proposal.name in fg:
            # Reusing existing field — must be writable relational match.
            return bool(
                schema_client.relation_ok(mid, proposal.name, rel)
                and schema_client.field_is_writable(mid, proposal.name)
            )
        # New custom M2O onto stock relation — relation target must exist.
        return True
    except Exception:  # noqa: BLE001
        return False


def merge_proposals(
    ir: GenerateIR,
    proposals: list[Proposal],
    *,
    draft: dict[str, Any] | None = None,
    schema_client: Any | None = None,
) -> GenerateIR:
    """Admit proposals that pass the gate; record rejects for AI_IR_TRACE."""
    if schema_client is None and draft is not None:
        try:
            from app.ai_schema_client import schema_client_for_draft

            schema_client = schema_client_for_draft(draft)
        except Exception:  # noqa: BLE001
            schema_client = None
    for prop in proposals:
        ok, reason = proposal_allowed(
            prop, ir=ir, schema_client=schema_client, draft=draft
        )
        if not ok:
            ir.rejected_proposals.append({**prop.to_dict(), "reject_reason": reason})
            continue
        ir.admitted.append({**prop.to_dict(), "admit_reason": reason})
        if prop.kind in {"field", "m2o", "o2m"}:
            mid = str(prop.payload.get("model") or ir.host_model or "")
            if not mid:
                ir.rejected_proposals.append({**prop.to_dict(), "reject_reason": "no_model"})
                continue
            bucket = ir.fields_by_model.setdefault(mid, [])
            names = {str(f.get("name")) for f in bucket}
            fname = prop.name
            if fname not in names:
                row = {
                    "name": fname,
                    **{
                        k: v
                        for k, v in prop.payload.items()
                        if k not in {"model", "craft_key", "line_model"}
                    },
                }
                bucket.append(row)
                if prop.kind == "o2m" or str(row.get("ttype")) == "one2many":
                    ir.o2ms.append(
                        {
                            "name": fname,
                            "on_model": mid,
                            "relation": row.get("relation"),
                            "string": row.get("string"),
                        }
                    )
            line = prop.payload.get("line_model")
            if isinstance(line, dict) and line.get("model"):
                lid = str(line["model"])
                if not any(m.get("model") == lid for m in ir.models):
                    ir.models.append(
                        {
                            "model": lid,
                            "description": line.get("description") or lid,
                            "mode": line.get("mode") or "new",
                            "source": line.get("source")
                            or prop.proposer
                            or "proposal",
                        }
                    )
                    ir.fields_by_model[lid] = [
                        dict(f)
                        for f in (line.get("fields") or [])
                        if isinstance(f, dict) and f.get("name")
                    ]
        elif prop.kind == "model":
            if not any(m.get("model") == prop.name for m in ir.models):
                row = {
                    "model": prop.name,
                    "description": prop.payload.get("description") or prop.name,
                    "mode": prop.payload.get("mode") or "new",
                    "source": prop.payload.get("source")
                    or prop.proposer
                    or "proposal",
                    "is_workflow": prop.payload.get("is_workflow"),
                }
                if prop.payload.get("inherit"):
                    row["inherit"] = prop.payload.get("inherit")
                ir.models.append(row)
                ir.fields_by_model.setdefault(
                    prop.name,
                    [
                        dict(f)
                        for f in (prop.payload.get("fields") or [])
                        if isinstance(f, dict) and f.get("name")
                    ],
                )
        elif prop.kind == "menu":
            ir.menus.append({"name": prop.name, **prop.payload})
        elif prop.kind == "smart_button":
            if draft is not None:
                btns = draft.setdefault("smart_buttons", [])
                if isinstance(btns, list):
                    btns.append({"label": prop.name, **prop.payload})
    if draft is not None:
        draft["_generate_ir"] = ir.to_dict()
    return ir


def apply_ir_to_draft(ir: GenerateIR, draft: dict[str, Any]) -> list[str]:
    """Materialize admitted IR nodes onto the live draft (additive only)."""
    notes: list[str] = []
    by_id = {
        str(m.get("model")): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    for mid, fields in ir.fields_by_model.items():
        model = by_id.get(mid)
        if model is None:
            continue
        existing = {
            str(f.get("name"))
            for f in (model.get("fields") or [])
            if isinstance(f, dict) and f.get("name")
        }
        for f in fields:
            fname = str(f.get("name") or "")
            if not fname or fname in existing:
                continue
            model.setdefault("fields", []).append(dict(f))
            existing.add(fname)
            notes.append(f"generate_ir: admitted field {mid}.{fname}")
    for row in ir.models:
        mid = str(row.get("model") or "")
        if not mid or mid in by_id:
            continue
        fields = [dict(f) for f in ir.fields_by_model.get(mid) or []]
        new_model = {
            "model": mid,
            "description": row.get("description") or mid,
            "mode": row.get("mode") or "new",
            "source": row.get("source") or "generate_ir",
            "fields": fields,
        }
        if row.get("is_workflow") is not None:
            new_model["is_workflow"] = row.get("is_workflow")
        if row.get("inherit"):
            new_model["inherit"] = row.get("inherit")
        draft.setdefault("models", []).append(new_model)
        by_id[mid] = new_model
        notes.append(f"generate_ir: admitted model {mid}")
    # Wave 3: admitted menus materialize onto draft.
    if ir.menus:
        menus = list(draft.get("menus") or []) if isinstance(draft.get("menus"), list) else []
        existing_keys = {
            (
                str(m.get("xml_id") or m.get("technical_name") or ""),
                str(m.get("action_xml_id") or ""),
                str(m.get("name") or ""),
            )
            for m in menus
            if isinstance(m, dict)
        }
        for row in ir.menus:
            if not isinstance(row, dict):
                continue
            key = (
                str(row.get("xml_id") or row.get("technical_name") or ""),
                str(row.get("action_xml_id") or ""),
                str(row.get("name") or ""),
            )
            if key in existing_keys and any(key):
                continue
            menus.append(dict(row))
            existing_keys.add(key)
            notes.append(f"generate_ir: admitted menu {row.get('name') or row.get('technical_name')}")
        draft["menus"] = menus
    draft["_generate_ir"] = ir.to_dict()
    return notes


def o2ms_for_install(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Install-facing O2Ms — authoritative list from stamped GenerateIR."""
    ir = stamp_generate_ir(draft)
    return [dict(row) for row in ir.o2ms if isinstance(row, dict)]


def draft_o2ms_outside_ir(draft: dict[str, Any]) -> list[str]:
    """O2M field names on draft models missing from GenerateIR.o2ms."""
    ir_raw = draft.get("_generate_ir") if isinstance(draft.get("_generate_ir"), dict) else {}
    ir_names = {
        str(row.get("name"))
        for row in (ir_raw.get("o2ms") or [])
        if isinstance(row, dict) and row.get("name")
    }
    hits: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                continue
            if str(f.get("ttype") or "") != "one2many":
                continue
            name = str(f.get("name") or "")
            if name and name not in ir_names:
                hits.append(f"{mid}.{name}")
    return hits

def admit_and_apply(
    draft: dict[str, Any],
    proposals: list[Proposal],
    *,
    constraint_ast: dict[str, Any] | None = None,
    schema_client: Any | None = None,
) -> tuple[GenerateIR, list[str]]:
    """Single legal path: build IR → merge proposals → apply admitted nodes."""
    if not proposals:
        return stamp_generate_ir(draft, constraint_ast=constraint_ast), []
    ir = stamp_generate_ir(draft, constraint_ast=constraint_ast)
    merge_proposals(ir, proposals, draft=draft, schema_client=schema_client)
    notes = apply_ir_to_draft(ir, draft)
    rejected = len(ir.rejected_proposals)
    if rejected:
        notes.append(f"generate_ir: rejected {rejected} proposal(s)")
    try:
        from app.ai_ir_trace import trace_ir

        trace_ir(
            draft,
            stage="admit_and_apply",
            notes=notes[-20:]
            + [f"rejected:{r.get('name')}:{r.get('reject_reason')}" for r in ir.rejected_proposals[-10:]],
        )
    except Exception:  # noqa: BLE001
        pass
    return ir, notes


def stamp_generate_ir(
    draft: dict[str, Any], *, constraint_ast: dict[str, Any] | None = None
) -> GenerateIR:
    """Convenience: build + stamp on draft."""
    ast = constraint_ast
    if ast is None:
        und = draft.get("_understanding") if isinstance(draft.get("_understanding"), dict) else {}
        ast = und.get("constraint_ast") if isinstance(und.get("constraint_ast"), dict) else und
    return build_ir(draft, constraint_ast=ast if isinstance(ast, dict) else None)


def ir_closure_violations(draft: dict[str, Any]) -> list[str]:
    """Fields/M2Os that look like spray and are not cue/craft/proposal-admitted.

    Workspace / comprehensive graphs are out of scope — spray purge and this
    assert apply to thin residual Generate only (handoff §3).
    """
    try:
        from app.ai_generate_ir_enforce import _field_allowed, _is_thin_residual

        if not _is_thin_residual(draft):
            return []
    except Exception:  # noqa: BLE001
        return []
    ir_raw = draft.get("_generate_ir") if isinstance(draft.get("_generate_ir"), dict) else {}
    admitted_names: set[str] = set()
    for row in ir_raw.get("admitted") or []:
        if isinstance(row, dict) and row.get("name"):
            admitted_names.add(str(row["name"]))
    spray_names = {
        "x_company_id",
        "company_id",
        "x_purchase_order_id",
        "x_po_id",
        "x_invoice_id",
        "x_currency_id",
        "x_partner_id",
        "x_contact_id",
        "x_customer_id",
        "x_client_id",
    }
    spray_rels = {
        "res.company",
        "purchase.order",
        "res.partner",
        "res.currency",
    }
    hits: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                continue
            name = str(f.get("name") or "")
            rel = str(f.get("relation") or "")
            if name not in spray_names and rel not in spray_rels:
                continue
            if _field_allowed(name=name, rel=rel, draft=draft, admitted=admitted_names):
                continue
            hits.append(f"{mid}.{name}->{rel or name}")
    return hits


__all__ = [
    "STRUCTURAL_DEFAULT_ALLOWLIST",
    "GenerateIR",
    "Proposal",
    "admit_and_apply",
    "apply_ir_to_draft",
    "build_ir",
    "draft_o2ms_outside_ir",
    "ir_closure_violations",
    "merge_proposals",
    "o2ms_for_install",
    "proposal_allowed",
    "stamp_generate_ir",
]
