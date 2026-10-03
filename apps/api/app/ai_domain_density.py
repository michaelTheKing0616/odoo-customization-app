"""Domain-named vertical density — full Odoo apps, not 4-model stubs.

After generic-loop prune, fill missing operational *roles* using names taken
from the prompt and existing models (recording, equipment, rate, …). Public
ORM shapes only; no per-vertical pack.
"""

from __future__ import annotations

import re
from typing import Any

_SKIP_NOUNS = frozenset(
    {
        "company",
        "management",
        "system",
        "platform",
        "operations",
        "multiple",
        "music",
        "app",
        "application",
        "module",
        "business",
        "service",
        "user",
        "data",
        "record",
        "item",
        "order",
        "line",
    }
)
_SITE_TOKENS = (
    "studio",
    "facility",
    "branch",
    "site",
    "warehouse",
    "store",
    "room",
    "location",
    "clinic",
    "ward",
    "court",
    "yard",
)
_PARTY_TOKENS = (
    "artist",
    "artiste",
    "guest",
    "patient",
    "member",
    "tenant",
    "student",
    "resident",
)
_STAFF_TOKENS = (
    "attorney",
    "lawyer",
    "counsel",
    "doctor",
    "nurse",
    "teacher",
    "practitioner",
    "technician",
)
_ENGAGEMENT_TOKENS = (
    "project",
    "production",
    "matter",
    "case",
    "stay",
    "engagement",
    "job",
)
_BOOKING_TOKENS = (
    "session",
    "booking",
    "appointment",
    "reservation",
    "work_order",
)
_ASSET_TOKENS = ("equipment", "asset", "instrument", "gear", "vehicle", "tool")
_RATE_TOKENS = ("rate", "fee", "tariff", "pricelist")
_AGREEMENT_TOKENS = ("agreement", "license", "contract", "lease")
_EXPENSE_TOKENS = ("expense", "cost", "disbursement")
_OUTPUT_TOKENS = (
    "recording",
    "track",
    "mix",
    "master",
    "album",
    "pour",
    "melt",
    "casting",
    "batch",
    "harvest",
    "episode",
    "deliverable",
    "output",
)


def _models_index(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def _leaf(mid: str) -> str:
    return str(mid).replace("x_", "")


def _find_by_tokens(draft: dict[str, Any], tokens: tuple[str, ...]) -> str | None:
    for mid, model in _models_index(draft).items():
        if mid.endswith("_line"):
            continue
        hay = f"{_leaf(mid)} {model.get('description') or ''}".lower()
        if any(tok in hay for tok in tokens):
            return mid
    return None


def _non_line_ids(draft: dict[str, Any]) -> set[str]:
    return {
        mid
        for mid in _models_index(draft)
        if mid.startswith("x_") and not mid.endswith("_line")
    }


def _prompt_token_hit(prompt: str, tokens: tuple[str, ...]) -> str | None:
    # "Receipts stay stock POS" is Option-A deferral, not a hotel stay residual.
    cleaned = re.sub(
        r"(?i)\breceipts?\s+stay\s+stock(?:\s+pos)?\b",
        " ",
        prompt or "",
    )
    cleaned = re.sub(r"(?i)\bstay\s+(?:stock|as|with)\b", " ", cleaned)
    hay = f" {re.sub(r'[^a-z0-9]+', ' ', cleaned.lower())} "
    for tok in tokens:
        if re.search(rf"\b{re.escape(tok)}s?\b", hay):
            return "artist" if tok == "artiste" else tok
    return None


def _density_target(ambition: str, draft: dict[str, Any] | None = None) -> int:
    """Unpacked vertical size. Reuse-rich drafts stay residual, not a second ERP."""
    from app.ai_stock_first import is_reuse_rich

    if draft is not None and is_reuse_rich(draft):
        return 4 if ambition != "thin" else 3
    if ambition == "thin":
        return 4
    if ambition == "comprehensive":
        return 16
    return 12


def _company_field() -> dict[str, Any]:
    return {
        "name": "x_company_id",
        "ttype": "many2one",
        "relation": "res.company",
        "string": "Company",
        "on_delete": "restrict",
        "craft_key": "company_scoping",
        "source": "domain_density",
    }


def _m2o(name: str, relation: str, string: str) -> dict[str, Any]:
    return {
        "name": name,
        "ttype": "many2one",
        "relation": relation,
        "string": string,
        "source": "domain_density",
    }


def _model_proposal(
    *,
    mid: str,
    description: str,
    fields: list[dict[str, Any]],
    is_workflow: bool = False,
    source_cue: str | None = None,
    add_company: bool = False,
) -> Any:
    """Build a GenerateIR model Proposal (admit is the only writer)."""
    from app.ai_generate_ir import Proposal

    known_fields = [dict(f) for f in fields if isinstance(f, dict)]
    names = {str(f.get("name")) for f in known_fields}
    # Company only when multi-company is cued/craft — never silent spray.
    if add_company and "x_company_id" not in names:
        known_fields = [*known_fields, _company_field()]
    for f in known_fields:
        f.setdefault("source", "domain_density")
    cue = (source_cue or _leaf(mid) or mid).strip()
    return Proposal(
        kind="model",
        name=mid,
        payload={
            "description": description,
            "mode": "new",
            "source": "domain_density",
            "is_workflow": is_workflow,
            "fields": known_fields,
        },
        source_cue=cue,
        rationale=f"domain density role {mid}",
        proposer="ai_domain_density",
        confidence=0.75,
    )


def _field_proposal(
    *,
    model: str,
    field: dict[str, Any],
    source_cue: str | None = None,
) -> Any:
    from app.ai_generate_ir import Proposal

    name = str(field.get("name") or "")
    payload = {k: v for k, v in field.items() if k != "name"}
    payload["model"] = model
    payload.setdefault("source", "domain_density")
    kind = "o2m" if payload.get("ttype") == "one2many" else (
        "m2o" if payload.get("ttype") == "many2one" else "field"
    )
    return Proposal(
        kind=kind,  # type: ignore[arg-type]
        name=name,
        payload=payload,
        source_cue=source_cue or name.removeprefix("x_"),
        rationale=f"domain density field {model}.{name}",
        proposer="ai_domain_density",
        confidence=0.7,
    )


def _deliverable_leaf(draft: dict[str, Any], prompt: str) -> str | None:
    """Work-product model named from prompt output nouns (recording, melt, …)."""
    blob = " ".join(_non_line_ids(draft)).lower()
    prompt_l = (prompt or "").lower()
    if any(f"x_{token}" in blob for token in _OUTPUT_TOKENS):
        return None
    for token in _OUTPUT_TOKENS:
        if re.search(rf"\b{re.escape(token)}s?\b", prompt_l):
            return token
    if _find_by_tokens(draft, _ENGAGEMENT_TOKENS) or _find_by_tokens(draft, _BOOKING_TOKENS):
        return "deliverable"
    return None


def _title(leaf: str) -> str:
    return leaf.replace("_", " ").title()


def _blocked_ids(draft: dict[str, Any]) -> set[str]:
    from app.ai_stock_first import forbid_new_models_from_draft

    return forbid_new_models_from_draft(draft)


def ensure_domain_density(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    ambition: str = "",
) -> list[str]:
    """Propose missing residual roles; only admit_and_apply may write them."""
    from app.ai_generate_ir import admit_and_apply
    from app.ai_ir_trace import trace_ir

    notes: list[str] = []
    if draft.get("domain_pack"):
        return notes
    try:
        from app.ai_document_shape import additive_model_growth_blocked

        if additive_model_growth_blocked(draft, prompt=user_prompt):
            return notes
    except Exception:  # noqa: BLE001
        pass
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    from app.ai_domain_briefing import attach_domain_briefing
    from app.ai_stock_first import (
        STAFF_ROLE_LEAVES,
        attach_reuse_plan_to_draft,
        extract_explicit_residuals,
        reuse_models_from_draft,
        stock_ops_reused,
    )

    attach_domain_briefing(draft, user_prompt=prompt)
    notes.extend(attach_reuse_plan_to_draft(draft, user_prompt=prompt))
    amb = ambition or str(draft.get("_ambition") or "comprehensive")
    target = _density_target(amb, draft)
    blocked = _blocked_ids(draft)
    reused = reuse_models_from_draft(draft)
    ops = stock_ops_reused(draft)
    proposals: list[Any] = []
    pending: set[str] = set()

    def _index() -> dict[str, dict[str, Any]]:
        out = _models_index(draft)
        for mid in pending:
            out.setdefault(mid, {"model": mid, "fields": []})
        return out

    def _non_line() -> set[str]:
        return {
            mid
            for mid in _index()
            if mid.startswith("x_") and not mid.endswith("_line")
        }

    def _room() -> bool:
        return len(_non_line()) < target

    def _may_add(mid: str) -> bool:
        return mid not in blocked and _leaf(mid) not in STAFF_ROLE_LEAVES and mid not in _index()

    def _find(tokens: tuple[str, ...]) -> str | None:
        for mid, model in _index().items():
            if mid.endswith("_line"):
                continue
            hay = f"{_leaf(mid)} {model.get('description') or ''}".lower()
            if any(tok in hay for tok in tokens):
                return mid
        return None

    def _queue_model(
        *,
        mid: str,
        description: str,
        fields: list[dict[str, Any]],
        is_workflow: bool = False,
        source_cue: str | None = None,
    ) -> None:
        if not _may_add(mid):
            return
        proposals.append(
            _model_proposal(
                mid=mid,
                description=description,
                fields=fields,
                is_workflow=is_workflow,
                source_cue=source_cue or _leaf(mid),
            )
        )
        pending.add(mid)

    site = _find(_SITE_TOKENS)
    party = _find(_PARTY_TOKENS)
    engagement = _find(_ENGAGEMENT_TOKENS)
    if not site:
        leaf = _prompt_token_hit(prompt, _SITE_TOKENS)
        if leaf and _may_add(f"x_{leaf}"):
            site = f"x_{leaf}"
            _queue_model(
                mid=site,
                description=_title(leaf),
                fields=[
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                ],
                source_cue=leaf,
            )
            notes.append(f"density: propose site {site}")
    if not party:
        leaf = _prompt_token_hit(prompt, _PARTY_TOKENS)
        if leaf and _may_add(f"x_{leaf}"):
            party = f"x_{leaf}"
            _queue_model(
                mid=party,
                description=_title(leaf),
                fields=[
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Contact",
                        "craft_key": "partner_links",
                    },
                ],
                source_cue=leaf,
            )
            notes.append(f"density: propose party {party}")
    if not engagement:
        leaf = _prompt_token_hit(prompt, _ENGAGEMENT_TOKENS)
        if not leaf:
            explicit = extract_explicit_residuals(prompt)
            if explicit:
                leaf = explicit[0][0]
        if leaf and _may_add(f"x_{leaf}"):
            engagement = f"x_{leaf}"
            fields: list[dict[str, Any]] = [
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                {
                    "name": "x_partner_id",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "string": "Contact",
                    "craft_key": "partner_links",
                },
            ]
            if "hr.employee" in reused or "hr.employee" in ops:
                fields.append(_m2o("x_employee_id", "hr.employee", "Employee"))
            _queue_model(
                mid=engagement,
                description=_title(leaf),
                is_workflow=True,
                fields=fields,
                source_cue=leaf,
            )
            notes.append(f"density: propose residual {engagement}")
    booking = _find(_BOOKING_TOKENS)
    asset = _find(_ASSET_TOKENS)
    rate = _find(_RATE_TOKENS)
    agreement = _find(_AGREEMENT_TOKENS)
    expense = _find(_EXPENSE_TOKENS)

    prompt_has_booking = any(
        re.search(rf"\b{re.escape(tok)}s?\b", prompt, re.I) for tok in _BOOKING_TOKENS
    )
    if (
        not booking
        and engagement
        and _room()
        and prompt_has_booking
        and "calendar.event" not in reused
    ):
        booking = "x_session" if "x_session" not in _index() else "x_booking"
        if _may_add(booking):
            cue = "session" if booking.endswith("session") else "booking"
            _queue_model(
                mid=booking,
                description="Booking",
                is_workflow=True,
                source_cue=cue,
                fields=[
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    _m2o(
                        f"x_{_leaf(engagement)}_id",
                        engagement,
                        _title(_leaf(engagement)),
                    ),
                    *(
                        [
                            _m2o(
                                f"x_{_leaf(site)}_id",
                                site,
                                _title(_leaf(site)),
                            )
                        ]
                        if site
                        else []
                    ),
                    {"name": "x_start", "ttype": "datetime", "string": "Start"},
                    {"name": "x_end", "ttype": "datetime", "string": "End"},
                ],
            )
            notes.append(f"density: propose booking {booking}")

    deliverable_leaf = _deliverable_leaf(draft, prompt)
    # Also search pending+draft for output tokens
    if deliverable_leaf and _room() and _may_add(f"x_{deliverable_leaf}"):
        d_id = f"x_{deliverable_leaf}"
        fields = [
            {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
            {"name": "x_date", "ttype": "date", "string": "Date"},
            {
                "name": "x_status",
                "ttype": "selection",
                "string": "Status",
                "selection": "[('draft','Draft'),('in_progress','In Progress'),('done','Done')]",
            },
        ]
        if booking:
            fields.append(_m2o(f"x_{_leaf(booking)}_id", booking, _title(_leaf(booking))))
        if engagement:
            fields.append(
                _m2o(f"x_{_leaf(engagement)}_id", engagement, _title(_leaf(engagement)))
            )
        if party:
            fields.append(_m2o(f"x_{_leaf(party)}_id", party, _title(_leaf(party))))
        _queue_model(
            mid=d_id,
            description=_title(deliverable_leaf),
            is_workflow=True,
            fields=fields,
            source_cue=deliverable_leaf,
        )
        notes.append(f"density: propose deliverable {d_id}")

    if site and not asset and _room() and _may_add("x_equipment"):
        asset = "x_equipment"
        from app.ai_domain_briefing import briefing_from_dict
        from app.ai_selection import serialize_selection

        brief = briefing_from_dict(
            draft.get("_domain_briefing")
            if isinstance(draft.get("_domain_briefing"), dict)
            else None
        )
        type_sel = (
            serialize_selection(brief.equipment_types)
            if brief and brief.equipment_types
            else "[('standard','Standard'),('other','Other')]"
        )
        _queue_model(
            mid=asset,
            description="Equipment",
            source_cue="equipment",
            fields=[
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                _m2o(f"x_{_leaf(site)}_id", site, _title(_leaf(site))),
                {"name": "x_serial", "ttype": "char", "string": "Serial"},
                {
                    "name": "x_type",
                    "ttype": "selection",
                    "string": "Type",
                    "selection": type_sel,
                    "source": "domain_briefing",
                },
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Status",
                    "selection": "[('available','Available'),('in_use','In Use'),('maintenance','Maintenance')]",
                },
            ],
        )
        notes.append(f"density: propose equipment on {site}")

    # Re-read asset after potential queue (still pending until admit)
    if asset is None:
        asset = _find(_ASSET_TOKENS) or ("x_equipment" if "x_equipment" in pending else None)

    if (
        asset
        and _room()
        and _may_add("x_maintenance")
        and not _find(("maintenance", "repair"))
    ):
        _queue_model(
            mid="x_maintenance",
            description="Maintenance",
            is_workflow=True,
            source_cue="maintenance",
            fields=[
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                _m2o(f"x_{_leaf(asset)}_id", asset, _title(_leaf(asset))),
                {"name": "x_date", "ttype": "date", "string": "Date"},
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Status",
                    "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                },
                {"name": "x_notes", "ttype": "text", "string": "Notes"},
            ],
        )
        notes.append(f"density: propose maintenance on {asset}")

    if site and not rate and _room() and _may_add("x_rate"):
        rate = "x_rate"
        _queue_model(
            mid=rate,
            description="Rate",
            source_cue="rate",
            fields=[
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                _m2o(f"x_{_leaf(site)}_id", site, _title(_leaf(site))),
                {
                    "name": "x_amount",
                    "ttype": "monetary",
                    "string": "Rate",
                    "currency_field": "x_currency_id",
                },
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "relation": "res.currency",
                    "string": "Currency",
                    "craft_key": "money_slots",
                },
                {
                    "name": "x_uom",
                    "ttype": "selection",
                    "string": "Unit",
                    "selection": "[('hour','Hour'),('day','Day'),('session','Session')]",
                },
            ],
        )
        notes.append(f"density: propose rate on {site}")

    prompt_wants_agreement = any(
        re.search(rf"\b{re.escape(tok)}s?\b", prompt, re.I) for tok in _AGREEMENT_TOKENS
    )
    stock_covers_sale = "sale.order" in ops
    if (
        not agreement
        and (party or engagement)
        and _room()
        and _may_add("x_agreement")
        and (prompt_wants_agreement or not stock_covers_sale)
    ):
        agreement = "x_agreement"
        fields = [
            {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
            {"name": "x_date", "ttype": "date", "string": "Date", "required": True},
            {
                "name": "x_status",
                "ttype": "selection",
                "string": "Status",
                "selection": "[('draft','Draft'),('signed','Signed'),('expired','Expired')]",
            },
            {"name": "x_notes", "ttype": "text", "string": "Terms"},
        ]
        if party:
            fields.append(_m2o(f"x_{_leaf(party)}_id", party, _title(_leaf(party))))
        if engagement:
            fields.append(
                _m2o(f"x_{_leaf(engagement)}_id", engagement, _title(_leaf(engagement)))
            )
        _queue_model(
            mid=agreement,
            description="Agreement",
            is_workflow=True,
            fields=fields,
            source_cue="agreement" if prompt_wants_agreement else (party or engagement or "agreement"),
        )
        notes.append("density: propose agreement")

    if (
        site
        and _room()
        and _may_add("x_unavailability")
        and not _find(("unavailability", "blackout", "closure"))
    ):
        _queue_model(
            mid="x_unavailability",
            description="Unavailability",
            source_cue="unavailability",
            fields=[
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                _m2o(f"x_{_leaf(site)}_id", site, _title(_leaf(site))),
                {"name": "x_start", "ttype": "datetime", "string": "Start", "required": True},
                {"name": "x_end", "ttype": "datetime", "string": "End", "required": True},
                {"name": "x_reason", "ttype": "char", "string": "Reason"},
            ],
        )
        notes.append(f"density: propose unavailability on {site}")

    deliverable = _find(
        tuple({deliverable_leaf} if deliverable_leaf else ()) or ("recording", "track", "output")
    )
    parent_for_rev = deliverable or booking
    if (
        parent_for_rev
        and _room()
        and _may_add("x_revision")
        and not _find(("revision", "take", "version"))
    ):
        _queue_model(
            mid="x_revision",
            description="Revision",
            source_cue="revision",
            fields=[
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                _m2o(
                    f"x_{_leaf(parent_for_rev)}_id",
                    parent_for_rev,
                    _title(_leaf(parent_for_rev)),
                ),
                {"name": "x_date", "ttype": "date", "string": "Date"},
                {"name": "x_notes", "ttype": "text", "string": "Notes"},
            ],
        )
        notes.append(f"density: propose revision on {parent_for_rev}")

    stock_covers_expense = bool(ops & {"hr.expense", "account.move"})
    if not expense and (engagement or booking) and _room() and not stock_covers_expense and _may_add("x_expense"):
        parent = engagement or booking
        assert parent
        _queue_model(
            mid="x_expense",
            description="Expense",
            is_workflow=True,
            source_cue="expense",
            fields=[
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                {"name": "x_date", "ttype": "date", "string": "Date", "required": True},
                {
                    "name": "x_amount",
                    "ttype": "monetary",
                    "string": "Amount",
                    "currency_field": "x_currency_id",
                    "required": True,
                },
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "relation": "res.currency",
                    "string": "Currency",
                    "craft_key": "money_slots",
                },
                _m2o(f"x_{_leaf(parent)}_id", parent, _title(_leaf(parent))),
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Status",
                    "selection": "[('draft','Draft'),('open','Open'),('done','Done')]",
                },
            ],
        )
        notes.append(f"density: propose expense on {parent}")
    elif expense:
        emodel = _models_index(draft).get(expense) or {}
        names = {
            str(f.get("name"))
            for f in (emodel.get("fields") or [])
            if isinstance(f, dict)
        }
        parent = engagement or booking
        if "x_date" not in names:
            proposals.append(
                _field_proposal(
                    model=expense,
                    field={"name": "x_date", "ttype": "date", "string": "Date"},
                    source_cue="expense",
                )
            )
        if "x_amount" not in names:
            proposals.append(
                _field_proposal(
                    model=expense,
                    field={
                        "name": "x_amount",
                        "ttype": "monetary",
                        "string": "Amount",
                        "currency_field": "x_currency_id",
                        "craft_key": "money_slots",
                    },
                    source_cue="amount",
                )
            )
            proposals.append(
                _field_proposal(
                    model=expense,
                    field={
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "relation": "res.currency",
                        "string": "Currency",
                        "craft_key": "money_slots",
                    },
                    source_cue="currency",
                )
            )
        if parent and f"x_{_leaf(parent)}_id" not in names:
            proposals.append(
                _field_proposal(
                    model=expense,
                    field=_m2o(f"x_{_leaf(parent)}_id", parent, _title(_leaf(parent))),
                    source_cue=_leaf(parent),
                )
            )

    booking_now = _find(_BOOKING_TOKENS) or (
        "x_session" if "x_session" in pending else ("x_booking" if "x_booking" in pending else None)
    )
    if booking_now and booking_now in _models_index(draft):
        bmodel = _models_index(draft).get(booking_now) or {}
        names = {
            str(f.get("name"))
            for f in (bmodel.get("fields") or [])
            if isinstance(f, dict)
        }
        if "x_employee_id" not in names:
            proposals.append(
                _field_proposal(
                    model=booking_now,
                    field=_m2o("x_employee_id", "hr.employee", "Crew"),
                    source_cue="employee",
                )
            )
            depends = list(draft.get("depends") or [])
            if "hr" not in depends:
                depends.append("hr")
                draft["depends"] = depends
            notes.append(f"density: propose hr.employee crew on {booking_now}")

    if proposals:
        trace_ir(draft, stage="ensure_domain_density:before_admit")
        _, gate = admit_and_apply(draft, proposals)
        notes.extend(gate)
        trace_ir(draft, stage="ensure_domain_density:after_admit")
        notes.append(
            f"density: {len(_non_line_ids(draft))} domain models (target {target})"
        )
    return notes



__all__ = ["ensure_domain_density"]
