"""Prefer / inherit field_pack Generate IR — no understanding_json / clarifications leak."""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_component_builder import draft_component_from_prompt
from app.ai_conversation.clarify import apply_clarification_answer
from app.ai_conversation.intent_gate import merge_resolved_prompt
from app.ai_conversation.understand import (
    UNDERSTANDING_KEY,
    append_locked_diagnosis,
    build_understanding,
    dump_understanding,
)
from app.ai_field_ir import (
    _constraint_field_spec,
    extract_field_ir,
    is_junk_extension_field,
    typed_fields_from_constraints,
)


TOPE_SALES = (
    "Extend Sales Orders: add Customer PO reference and Required delivery window "
    "(start and end dates). Show a status hint when PO is set but delivery window "
    "is incomplete. Do not create a new app — inherit sale.order. Place under Other "
    "Info / Documents."
)


def _confirmed_prompt(brief: str) -> tuple[str, object]:
    u = build_understanding(brief)
    answers: dict[str, str] = {}
    dump_understanding(answers, u)
    merged, _ = apply_clarification_answer(
        brief,
        merge_key="diagnosis",
        answer_id="confirm",
        answer_text="Yes — build this",
        resolved_answers=answers,
        understanding=None,
    )
    return merged, u


def test_merge_resolved_prompt_strips_understanding_json() -> None:
    answers = {
        UNDERSTANDING_KEY: '{"grain":"field_pack","host_model":"sale.order","constraints":["Field: X"]}',
        "diagnosis": "confirm",
        "pack_choice": "on_existing_form",
    }
    merged = merge_resolved_prompt(TOPE_SALES, answers)
    assert "understanding_json" not in merged
    assert '"grain"' not in merged
    assert "pack_choice" in merged


def test_constraint_spec_rejects_json_and_status_hint() -> None:
    assert _constraint_field_spec(
        'understanding_json: {"grain":"field_pack","host_model":"sale.order"}'
    ) is None
    assert _constraint_field_spec(
        "Constraint: Status hint when PO is set but delivery window is incomplete"
    ) is None
    assert _constraint_field_spec(
        "Extend Sales Orders: add Customer PO reference and Required delivery window "
        "(start and end dates). Show a status hint"
    ) is None
    spec = _constraint_field_spec("Constraint: Field: Customer PO reference")
    assert spec and spec["string"] == "Customer PO reference"


def test_tope_sales_must_do_typed_fields_short_labels() -> None:
    u = build_understanding(TOPE_SALES)
    fields = typed_fields_from_constraints(u.constraints)
    by = {f["name"]: f for f in fields}
    assert "x_customer_po_reference" in by
    assert by["x_customer_po_reference"]["string"] == "Customer PO reference"
    assert "x_delivery_window_start_date" in by
    assert by["x_delivery_window_start_date"]["ttype"] == "date"
    assert "Required" not in by["x_delivery_window_start_date"]["string"]
    assert "x_delivery_window_end_date" in by
    assert not any("status hint" in str(f.get("string") or "").lower() for f in fields)


def test_tope_sales_generate_ir_clean_after_confirm() -> None:
    merged, u = _confirmed_prompt(TOPE_SALES)
    assert "understanding_json" not in merged
    assert u.title == "Customer PO + delivery window"

    draft, _hosts, _warns = draft_component_from_prompt(merged, grain="field_pack")
    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    assert inherit["model"] == "sale.order"
    fields = [f for f in (inherit.get("fields") or []) if isinstance(f, dict)]
    names = {str(f.get("name") or "") for f in fields}
    strings = [str(f.get("string") or "") for f in fields]

    assert names == {
        "x_customer_po_reference",
        "x_delivery_window_start_date",
        "x_delivery_window_end_date",
    }
    assert "Customer PO reference" in strings
    assert any("start date" in s.lower() for s in strings)
    assert any("end date" in s.lower() for s in strings)
    assert not any("{" in s or "understanding" in s.lower() or "field_pack" in s for s in strings)
    assert not any("status hint" in s.lower() for s in strings)
    assert not any(is_junk_extension_field(f) for f in fields)
    assert draft.get("menus") in (None, [], ())


@pytest.mark.parametrize(
    "brief,host,needle",
    [
        (
            "Extend Purchase Orders: add Vendor TIN and Required delivery window "
            "(start and end dates). Do not create a new app — inherit purchase.order.",
            "purchase.order",
            "Vendor TIN",
        ),
        (
            "Extend Contacts: add Loyalty tier and membership window "
            "(start and end dates). Show a status hint when tier is set. "
            "Do not create a new app — inherit res.partner.",
            "res.partner",
            "Loyalty",
        ),
        (
            "Extend Employees: add Badge code and review window "
            "(start and end dates). Do not create a new app — inherit hr.employee.",
            "hr.employee",
            "Badge",
        ),
    ],
)
def test_prefer_siblings_no_json_leak(brief: str, host: str, needle: str) -> None:
    merged, _u = _confirmed_prompt(brief)
    assert "understanding_json" not in merged
    draft, _hosts, _warns = draft_component_from_prompt(merged, grain="field_pack")
    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    assert inherit["model"] == host
    strings = [str(f.get("string") or "") for f in (inherit.get("fields") or [])]
    assert any(needle.lower() in s.lower() for s in strings)
    assert not any("{" in s or "understanding" in s.lower() for s in strings)
    assert not any("status hint" in s.lower() for s in strings)


def test_delivery_window_names_not_junk() -> None:
    assert not is_junk_extension_field(
        {
            "name": "x_delivery_window_start_date",
            "ttype": "date",
            "string": "Delivery window start date",
        }
    )
    assert is_junk_extension_field(
        {
            "name": "x_understanding_json_capability_residual",
            "ttype": "char",
            "string": 'understanding_json: {"grain":"field_pack"}',
        }
    )


def test_extract_field_ir_from_brief_without_locked_block() -> None:
    fields = extract_field_ir(
        "Extend Sales Orders: add Customer PO reference and Required delivery window "
        "(start and end dates). Do not create a new app — inherit sale.order."
    )
    names = {f["name"] for f in fields}
    assert "x_customer_po_reference" in names
    assert "x_delivery_window_start_date" in names
