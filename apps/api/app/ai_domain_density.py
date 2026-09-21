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
    }


def _m2o(name: str, relation: str, string: str) -> dict[str, Any]:
    return {
        "name": name,
        "ttype": "many2one",
        "relation": relation,
        "string": string,
    }


def _add_model(
    draft: dict[str, Any],
    *,
    mid: str,
    description: str,
    fields: list[dict[str, Any]],
    is_workflow: bool = False,
) -> None:
    known = set(_models_index(draft))
    if mid in known:
        return
    names = {str(f.get("name")) for f in fields if isinstance(f, dict)}
    if "x_company_id" not in names:
        fields = [*fields, _company_field()]
    row: dict[str, Any] = {
        "model": mid,
        "description": description,
        "mode": "new",
        "fields": fields,
        "source": "domain_density",
        "is_workflow": is_workflow,
    }
    if is_workflow:
        row["mixins"] = ["mail.thread", "mail.activity.mixin"]
    draft.setdefault("models", []).append(row)


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
    """Add missing residual roles. Never clone stock invoices/staff/tasks/events."""
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

    def _room() -> bool:
        return len(_non_line_ids(draft)) < target

    def _may_add(mid: str) -> bool:
        return mid not in blocked and _leaf(mid) not in STAFF_ROLE_LEAVES

    site = _find_by_tokens(draft, _SITE_TOKENS)
    party = _find_by_tokens(draft, _PARTY_TOKENS)
    engagement = _find_by_tokens(draft, _ENGAGEMENT_TOKENS)
    if not site:
        leaf = _prompt_token_hit(prompt, _SITE_TOKENS)
        if leaf and _may_add(f"x_{leaf}"):
            site = f"x_{leaf}"
            _add_model(
                draft,
                mid=site,
                description=_title(leaf),
                fields=[
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                ],
            )
            notes.append(f"density: site from prompt {site}")
    if not party:
        leaf = _prompt_token_hit(prompt, _PARTY_TOKENS)
        if leaf and _may_add(f"x_{leaf}"):
            party = f"x_{leaf}"
            _add_model(
                draft,
                mid=party,
                description=_title(leaf),
                fields=[
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Contact",
                    },
                ],
            )
            notes.append(f"density: party from prompt {party}")
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
                },
            ]
            if "hr.employee" in reused or "hr.employee" in ops:
                fields.append(_m2o("x_employee_id", "hr.employee", "Employee"))
            _add_model(
                draft,
                mid=engagement,
                description=_title(leaf),
                is_workflow=True,
                fields=fields,
            )
            notes.append(f"density: residual from prompt {engagement}")
    booking = _find_by_tokens(draft, _BOOKING_TOKENS)
    asset = _find_by_tokens(draft, _ASSET_TOKENS)
    rate = _find_by_tokens(draft, _RATE_TOKENS)
    agreement = _find_by_tokens(draft, _AGREEMENT_TOKENS)
    expense = _find_by_tokens(draft, _EXPENSE_TOKENS)

    prompt_has_booking = any(
        re.search(rf"\b{re.escape(tok)}s?\b", prompt, re.I) for tok in _BOOKING_TOKENS
    )
    if (
        not booking
        and engagement
        and _room()
        and prompt_has_booking
        and "calendar.event" not in reused
        and _may_add("x_booking")
    ):
        booking = "x_session" if "x_session" not in _models_index(draft) else "x_booking"
        if _may_add(booking):
            _add_model(
                draft,
                mid=booking,
                description="Booking",
                is_workflow=True,
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
            notes.append(f"density: booking document {booking}")

    deliverable_leaf = _deliverable_leaf(draft, prompt)
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
        _add_model(
            draft,
            mid=d_id,
            description=_title(deliverable_leaf),
            is_workflow=True,
            fields=fields,
        )
        notes.append(f"density: deliverable {d_id}")

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
        _add_model(
            draft,
            mid=asset,
            description="Equipment",
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
        notes.append(f"density: equipment roster on {site}")

    if (
        asset
        and _room()
        and _may_add("x_maintenance")
        and not _find_by_tokens(draft, ("maintenance", "repair"))
    ):
        _add_model(
            draft,
            mid="x_maintenance",
            description="Maintenance",
            is_workflow=True,
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
        notes.append(f"density: maintenance log on {asset}")

    if site and not rate and _room() and _may_add("x_rate"):
        rate = "x_rate"
        _add_model(
            draft,
            mid=rate,
            description="Rate",
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
                },
                {
                    "name": "x_uom",
                    "ttype": "selection",
                    "string": "Unit",
                    "selection": "[('hour','Hour'),('day','Day'),('session','Session')]",
                },
            ],
        )
        notes.append(f"density: rate card on {site}")

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
        _add_model(
            draft,
            mid=agreement,
            description="Agreement",
            is_workflow=True,
            fields=fields,
        )
        notes.append("density: agreement / license document")

    if (
        site
        and _room()
        and _may_add("x_unavailability")
        and not _find_by_tokens(draft, ("unavailability", "blackout", "closure"))
    ):
        _add_model(
            draft,
            mid="x_unavailability",
            description="Unavailability",
            fields=[
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                _m2o(f"x_{_leaf(site)}_id", site, _title(_leaf(site))),
                {"name": "x_start", "ttype": "datetime", "string": "Start", "required": True},
                {"name": "x_end", "ttype": "datetime", "string": "End", "required": True},
                {"name": "x_reason", "ttype": "char", "string": "Reason"},
            ],
        )
        notes.append(f"density: unavailability calendar on {site}")

    deliverable = _find_by_tokens(
        draft, tuple({deliverable_leaf} if deliverable_leaf else ()) or ("recording", "track", "output")
    )
    parent_for_rev = deliverable or booking
    if (
        parent_for_rev
        and _room()
        and _may_add("x_revision")
        and not _find_by_tokens(draft, ("revision", "take", "version"))
    ):
        _add_model(
            draft,
            mid="x_revision",
            description="Revision",
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
        notes.append(f"density: revision / take on {parent_for_rev}")

    stock_covers_expense = bool(ops & {"hr.expense", "account.move"})
    if not expense and (engagement or booking) and _room() and not stock_covers_expense and _may_add("x_expense"):
        parent = engagement or booking
        assert parent
        _add_model(
            draft,
            mid="x_expense",
            description="Expense",
            is_workflow=True,
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
        notes.append(f"density: job costing on {parent}")
    elif expense:
        emodel = _models_index(draft).get(expense) or {}
        names = {
            str(f.get("name"))
            for f in (emodel.get("fields") or [])
            if isinstance(f, dict)
        }
        parent = engagement or booking
        extra: list[dict[str, Any]] = []
        if "x_date" not in names:
            extra.append({"name": "x_date", "ttype": "date", "string": "Date"})
        if "x_amount" not in names:
            extra.append(
                {
                    "name": "x_amount",
                    "ttype": "monetary",
                    "string": "Amount",
                    "currency_field": "x_currency_id",
                }
            )
            extra.append(
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "relation": "res.currency",
                    "string": "Currency",
                }
            )
        if parent and f"x_{_leaf(parent)}_id" not in names:
            extra.append(_m2o(f"x_{_leaf(parent)}_id", parent, _title(_leaf(parent))))
        if extra:
            emodel.setdefault("fields", []).extend(extra)
            emodel["is_workflow"] = True
            notes.append(f"density: enriched job costing on {expense}")

    booking_now = _find_by_tokens(draft, _BOOKING_TOKENS)
    if booking_now:
        bmodel = _models_index(draft).get(booking_now) or {}
        names = {
            str(f.get("name"))
            for f in (bmodel.get("fields") or [])
            if isinstance(f, dict)
        }
        if "x_employee_id" not in names:
            bmodel.setdefault("fields", []).append(
                _m2o("x_employee_id", "hr.employee", "Crew")
            )
            depends = list(draft.get("depends") or [])
            if "hr" not in depends:
                depends.append("hr")
                draft["depends"] = depends
            notes.append(f"density: hr.employee crew on {booking_now}")

    if notes:
        notes.append(
            f"density: {len(_non_line_ids(draft))} domain models (target {target})"
        )
    return notes


__all__ = ["ensure_domain_density"]
