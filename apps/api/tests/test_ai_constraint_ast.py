"""Hybrid constraint AST — det floor + optional LLM fill + merge never shrinks."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.no_app_db

os.environ["AI_INTENT_LLM"] = "off"

from app.ai_constraint_ast import (  # noqa: E402
    ConstraintAST,
    ConstraintField,
    ast_to_must_do,
    merge_asts,
    merge_must_do,
    parse_det,
    parse_llm,
)
from app.ai_conversation.understand import build_understanding  # noqa: E402

TOPE_SALES = (
    "Extend Sales Orders: add Customer PO reference and Required delivery window "
    "(date range or start/end dates). On the form, show a status hint when the order "
    "is confirmed but no delivery document is attached in Documents. Prefer inherit/extend "
    "— do not invent a parallel Sales app."
)

VISITOR_LOG = (
    "Build a tiny Visitor Log app: model with Name, Company (link to Contact), "
    "Visit date, Purpose (selection: Meeting / Delivery / Other), and Host (Employee). "
    "Simple list + form, menu under Services. No workflow beyond create/read."
)


def test_parse_det_tope_sales_floor() -> None:
    ast = parse_det(TOPE_SALES, host="sale.order", inherit=True, grain="field_pack")
    assert ast.host == "sale.order"
    assert ast.grain == "field_pack"
    labels = " | ".join(f.label for f in ast.fields).lower()
    assert "customer po reference" in labels
    assert "delivery window" in labels and "start" in labels and "end" in labels
    assert any("status hint" in h.lower() for h in ast.hints)
    assert any("parallel" in n.lower() or "invent" in n.lower() for n in ast.non_goals)
    rows = ast_to_must_do(ast)
    joined = " | ".join(rows).lower()
    assert "customer po reference and" not in joined
    assert "sale.order" in joined


def test_parse_det_visitor_full_app() -> None:
    ast = parse_det(VISITOR_LOG, inherit=False, grain="full_app")
    assert ast.model_id and "visitor" in ast.model_id
    labels = " | ".join(f.label.lower() for f in ast.fields)
    assert "name" in labels
    assert any(f.ttype == "many2one" and f.relation and "contact" in f.relation.lower() for f in ast.fields)
    assert any(f.ttype == "selection" for f in ast.fields)
    assert any("services" in s.lower() for s in ast.structural)
    u = build_understanding(VISITOR_LOG)
    assert u.grain == "full_app"
    assert u.host_model is None


def test_parse_det_prefer_contacts_multi_field() -> None:
    prompt = (
        "Extend Contacts: add Loyalty tier and Preferred contact window "
        "(date range or start/end dates). On the form, show a status hint when the "
        "contact is archived but no ID document is attached in Documents. "
        "Prefer inherit — do not invent a parallel Contacts app."
    )
    u = build_understanding(prompt)
    assert u.host_model == "res.partner"
    joined = " | ".join(u.constraints).lower()
    assert "loyalty tier" in joined
    assert "contact window" in joined and "start" in joined and "end" in joined
    assert "status hint" in joined


def test_parse_det_prefer_purchase_date_range() -> None:
    prompt = (
        "Extend Purchase Orders: add Vendor contract reference and Required receipt "
        "window (date range or start/end dates). On the form, show a status hint when "
        "the order is confirmed but no receipt document is attached in Documents. "
        "Prefer inherit — do not invent a parallel Purchase app."
    )
    u = build_understanding(prompt)
    assert u.host_model == "purchase.order"
    joined = " | ".join(u.constraints).lower()
    assert "vendor contract" in joined
    assert "receipt window" in joined and "start" in joined
    assert "status hint" in joined


def test_residual_restaurant_does_not_steal_prefer_hosts() -> None:
    prompt = (
        "Dining Tables for our restaurant. Name, Capacity, Status (selection: Free / Seated / Reserved). "
        "Simple list + form, menu under Services."
    )
    u = build_understanding(prompt)
    assert u.grain == "full_app"
    assert u.host_model is None
    assert u.inherit_existing is False
    joined = " | ".join(u.constraints).lower()
    assert "sale.order" not in joined
    assert "res.partner" not in joined
    assert "purchase.order" not in joined


def test_merge_asts_never_shrinks_det_floor() -> None:
    det = parse_det(TOPE_SALES, host="sale.order", inherit=True, grain="field_pack")
    thin = ConstraintAST(
        grain="field_pack",
        host="sale.order",
        fields=[ConstraintField(label="Customer PO reference", ttype="char")],
        source="llm",
    )
    merged = merge_asts(det, thin)
    labels = " | ".join(f.label.lower() for f in merged.fields)
    assert "customer po" in labels
    assert "delivery window" in labels
    assert any("status hint" in h.lower() for h in merged.hints)
    bullets = ast_to_must_do(merged)
    bj = " | ".join(bullets).lower()
    assert "delivery window" in bj and "status hint" in bj


def test_merge_must_do_cap_keeps_det_over_llm_extras() -> None:
    """Over cap: det floor wins; LLM fluff is what gets trimmed."""
    det = [f"Field: Det {i}" for i in range(8)]
    llm = [f"Field: Llm {i}" for i in range(12)]
    out = merge_must_do(det, llm, cap=12)
    assert len(out) <= 12
    for row in det:
        assert row in out
    # Some LLM extras may fit; all det must remain
    assert sum(1 for r in out if r.startswith("Field: Det")) == 8


def test_parse_llm_structured_fill() -> None:
    payload = {
        "constraint_ast": {
            "grain": "field_pack",
            "host": "sale.order",
            "fields": [
                {"label": "Customer PO reference", "ttype": "char"},
                {"label": "Extra note from prose", "ttype": "text"},
            ],
            "hints": ["Status hint when confirmed"],
            "non_goals": ["Do not invent a parallel Sales app"],
        }
    }
    llm = parse_llm(payload)
    assert llm is not None
    assert llm.host == "sale.order"
    assert any(f.label == "Extra note from prose" for f in llm.fields)
    det = parse_det(TOPE_SALES, host="sale.order", inherit=True, grain="field_pack")
    merged = merge_asts(det, llm)
    labels = [f.label for f in merged.fields]
    assert any("Extra note" in x for x in labels)
    assert any("Customer PO" in x for x in labels)
