"""Regression — invent leaks go through admit (strict positive + negative paths).

No OR escape hatches. Each test asserts one contract.
"""

from __future__ import annotations

from app.ai_generate_ir_lint import invent_outside_admit_violations
from app.ai_model_quality import (
    deepen_thin_ops_children,
    deepen_thin_rate_models,
    ensure_line_bill_link,
)


def _admitted_names(draft: dict) -> set[str]:
    ir = draft.get("_generate_ir") if isinstance(draft.get("_generate_ir"), dict) else {}
    return {
        str(row["name"])
        for row in (ir.get("admitted") or [])
        if isinstance(row, dict) and row.get("name")
    }


def _rejected_by_name(draft: dict) -> dict[str, str]:
    ir = draft.get("_generate_ir") if isinstance(draft.get("_generate_ir"), dict) else {}
    out: dict[str, str] = {}
    for row in ir.get("rejected_proposals") or []:
        if isinstance(row, dict) and row.get("name"):
            out[str(row["name"])] = str(row.get("reject_reason") or "")
    return out


def test_line_bill_link_admits_fk_and_o2m_together() -> None:
    """Custom residual bill graph: both FK and inverse O2M must admit (not orphan O2M)."""
    draft = {
        "_user_prompt": "law firm matters with time lines and bills",
        "_ambition": "comprehensive",
        "domain_pack": "law_firm",
        "models": [
            {
                "model": "x_matter_line",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_bill",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
        ],
        "_generate_ir": {"admitted": []},
    }
    ensure_line_bill_link(draft)
    line = next(m for m in draft["models"] if m["model"] == "x_matter_line")
    bill = next(m for m in draft["models"] if m["model"] == "x_bill")
    line_names = {f.get("name") for f in line["fields"] if isinstance(f, dict)}
    bill_o2ms = [
        f
        for f in bill.get("fields") or []
        if isinstance(f, dict) and f.get("ttype") == "one2many"
    ]
    assert "x_bill_id" in line_names, "FK must admit onto the line"
    assert any(
        f.get("relation") == "x_matter_line" for f in bill_o2ms
    ), "inverse O2M must admit onto the bill"
    admitted = _admitted_names(draft)
    assert "x_bill_id" in admitted
    assert any("matter_line" in n for n in admitted)
    assert invent_outside_admit_violations(draft) == []


def test_line_bill_stock_account_move_still_spray_blocked() -> None:
    """x_bill_id → account.move remains stock spray without cue/craft."""
    from app.ai_generate_ir import Proposal, admit_and_apply

    draft = {
        "_user_prompt": "ticket with lines only",
        "_ambition": "thin",
        "models": [
            {"model": "x_ticket_line", "fields": [{"name": "x_name", "ttype": "char"}]},
        ],
        "_generate_ir": {"admitted": []},
    }
    prop = Proposal(
        kind="m2o",
        name="x_bill_id",
        payload={
            "model": "x_ticket_line",
            "ttype": "many2one",
            "relation": "account.move",
            "string": "Bill",
            "source": "quality_o2m",
        },
        source_cue="bill",
        proposer="ai_model_quality.ensure_line_bill_link",
        confidence=0.85,
    )
    admit_and_apply(draft, [prop])
    names = {f.get("name") for f in draft["models"][0]["fields"]}
    assert "x_bill_id" not in names
    rejected = _rejected_by_name(draft)
    assert "x_bill_id" in rejected
    assert "spray" in rejected["x_bill_id"] or "cue" in rejected["x_bill_id"]


def test_deepen_rate_rejects_currency_without_craft() -> None:
    draft = {
        "_user_prompt": "thin rate card name only",
        "_ambition": "thin",
        "_document_shape": "register",
        "models": [
            {
                "model": "x_rate",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "_generate_ir": {"admitted": [{"name": "x_name"}]},
    }
    deepen_thin_rate_models(draft)
    names = {f.get("name") for f in draft["models"][0]["fields"]}
    assert "x_currency_id" not in names
    assert "x_company_id" not in names
    rejected = _rejected_by_name(draft)
    assert "x_currency_id" in rejected
    assert invent_outside_admit_violations(draft) == []


def test_deepen_rate_admits_currency_with_money_slots_craft() -> None:
    draft = {
        "_user_prompt": "thin rate card name only",
        "_ambition": "thin",
        "_document_shape": "register",
        "_approved_craft": {"money_slots": True},
        "models": [
            {
                "model": "x_rate",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "_generate_ir": {"admitted": [{"name": "x_name"}]},
    }
    deepen_thin_rate_models(draft)
    names = {f.get("name") for f in draft["models"][0]["fields"]}
    assert "x_currency_id" in names
    # Company still needs company_scoping craft — must stay out.
    assert "x_company_id" not in names
    assert "x_currency_id" in _admitted_names(draft)
    assert invent_outside_admit_violations(draft) == []


def test_enrich_keeps_currency_when_draft_has_amount_fields() -> None:
    """Amount columns on the draft are a money cue — do not drop companion currency."""
    from app.ai_enrich import coerce_uncued_money_fields

    draft = {
        "_user_prompt": "a large supermarket with branches",
        "models": [
            {
                "model": "x_store_order",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_amount_total", "ttype": "float"},
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "relation": "res.currency",
                    },
                ],
            }
        ],
    }
    notes = coerce_uncued_money_fields(draft)
    names = {f.get("name") for f in draft["models"][0]["fields"]}
    assert "x_currency_id" in names
    assert not any("dropped uncued money" in n for n in notes)


def test_ops_child_status_goes_through_admit() -> None:
    draft = {
        "_user_prompt": "project tasks with deadlines",
        "_ambition": "standard",
        "models": [
            {
                "model": "x_task",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {"name": "x_date_deadline", "ttype": "date"},
                ],
            }
        ],
        "_generate_ir": {"admitted": []},
    }
    deepen_thin_ops_children(draft)
    names = {f.get("name") for f in draft["models"][0]["fields"]}
    assert "x_status" in names
    assert "x_status" in _admitted_names(draft)
    assert invent_outside_admit_violations(draft) == []
