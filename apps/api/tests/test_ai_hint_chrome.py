"""Hint chrome — status/banner/alert/ribbon as form decoration (any grain)."""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_hint_chrome import (
    apply_hint_chrome,
    attach_preview_alerts,
    collect_status_hint_rows,
    hints_to_chrome,
)
from app.ai_component_builder import draft_component_from_prompt
from app.ai_constraint_ast import parse_det
from app.preview_views import build_form_preview


PREFER_SALES = (
    "Extend Sales Orders: add Customer PO reference and Required delivery window "
    "(start and end dates). Show a status hint when PO is set but delivery window "
    "is incomplete. Do not create a new app — inherit sale.order. Place under Other "
    "Info / Documents."
)

RESIDUAL_VISITOR = (
    "Build a Visitor Log app with Name, Company, Purpose, and Time In. "
    "Show a status hint when Time In is set but Purpose is empty. "
    "Menu under Operations. Simple create/read only."
)


def test_collect_status_hints_from_prefer_and_residual() -> None:
    rows = collect_status_hint_rows(prompt=PREFER_SALES)
    assert rows
    assert any("delivery window" in c.lower() for _, c in rows)

    rows2 = collect_status_hint_rows(prompt=RESIDUAL_VISITOR)
    assert rows2
    assert any("purpose" in c.lower() or "time in" in c.lower() for _, c in rows2)


def test_ast_hints_become_chrome_not_char_fields() -> None:
    ast = parse_det(PREFER_SALES, host="sale.order", inherit=True, grain="field_pack")
    assert any("status hint" in h.lower() for h in ast.hints)

    draft, _hosts, _warns = draft_component_from_prompt(PREFER_SALES, grain="field_pack")
    notes = apply_hint_chrome(draft, prompt=PREFER_SALES)
    assert any("hint_chrome" in n for n in notes)
    chrome = draft.get("_hint_chrome") or []
    assert chrome
    assert chrome[0]["message"]

    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    strings = [str(f.get("string") or "") for f in inherit.get("fields") or []]
    assert not any("status hint" in s.lower() for s in strings)

    arch = next(
        str(v.get("arch") or "")
        for v in draft.get("views") or []
        if isinstance(v, dict) and str(v.get("type") or "") == "form"
    )
    assert "alert" in arch.lower() or "web_ribbon" in arch.lower()


def test_preview_canvas_shows_alert_chrome() -> None:
    draft, _hosts, _warns = draft_component_from_prompt(PREFER_SALES, grain="field_pack")
    apply_hint_chrome(draft, prompt=PREFER_SALES)
    form = build_form_preview(draft)
    assert form is not None
    alerts = form.get("alerts") or []
    assert alerts
    assert alerts[0].get("message")
    # Single banner line — no redundant When: echo of the same condition.
    assert not alerts[0].get("when")
    msg = str(alerts[0]["message"]).lower()
    assert "when:" not in msg


def test_prefer_sales_field_preview_no_double_label() -> None:
    """Structural preview: one Customer PO field; sample must not equal label."""
    draft, _hosts, _warns = draft_component_from_prompt(PREFER_SALES, grain="field_pack")
    apply_hint_chrome(draft, prompt=PREFER_SALES)
    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    strings = [
        str(f.get("string") or "").strip().lower()
        for f in (inherit.get("fields") or [])
        if isinstance(f, dict)
    ]
    assert strings.count("customer po reference") == 1
    form = build_form_preview(draft)
    assert form is not None
    po_rows = []
    for group in form.get("groups") or []:
        for field in group.get("fields") or []:
            if "po" in str(field.get("string") or "").lower():
                po_rows.append(field)
    for notebook in form.get("notebooks") or []:
        for page in notebook.get("pages") or []:
            for field in page.get("fields") or []:
                if "po" in str(field.get("string") or "").lower():
                    po_rows.append(field)
    assert len(po_rows) == 1
    # PreviewField has no sample stamped as the label (frontend owns sample).
    assert po_rows[0].get("string") == "Customer PO reference"


def test_residual_hint_chrome_any_grain() -> None:
    chrome = hints_to_chrome(prompt=RESIDUAL_VISITOR)
    assert chrome
    assert chrome[0].kind in {"alert", "ribbon"}


def test_attach_preview_alerts_empty_safe() -> None:
    out = attach_preview_alerts({"type": "form", "model": "x.demo"}, {})
    assert out is not None
    assert out.get("alerts") == []
