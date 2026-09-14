"""Option A quality bar — score caps, dedupe, done-bar, structural smoke."""

from __future__ import annotations

from app.ai_capability_gaps import stamp_capability_gaps
from app.ai_component_builder import draft_component_from_prompt
from app.ai_draft_scorecard import attach_scorecard
from app.ai_live_apply_contract import attach_live_apply_contract
from app.ai_option_a_quality import (
    OPTION_A_SCORE_CAP,
    dedupe_option_a_items,
    stamp_option_a_smoke,
    structural_option_a_smoke,
)


PDF_QR_PROMPT = (
    "Add dynamic QR codes or click-to-pay buttons directly on the PDF for Invoices"
)


def _pdf_draft() -> dict:
    draft, _hosts, _w = draft_component_from_prompt(
        PDF_QR_PROMPT,
        available_models=["account.move", "sale.order"],
    )
    attach_live_apply_contract(draft)
    attach_scorecard(draft, user_prompt=PDF_QR_PROMPT)
    return draft


def test_option_a_primary_caps_score_until_smoke() -> None:
    draft = _pdf_draft()
    assert draft.get("_capability_primary_option_a") is True
    assert "Option A document extras" in str(draft.get("grain_label") or "")
    sc = draft.get("_scorecard") or {}
    assert float(sc.get("score_0_10") or 0) <= OPTION_A_SCORE_CAP
    assert any(
        f.get("element") == "option_a_unproven" for f in (sc.get("findings") or [])
    )
    bar = draft.get("_done_bar") or {}
    assert bar.get("mode") == "option_a"
    assert draft.get("_go_live_ready") is not True


def test_elite_tests_and_i18n_are_not_option_a_runtime() -> None:
    from app.ai_option_a_quality import is_option_a_runtime_block

    assert not is_option_a_runtime_block(
        {
            "source_file": "tests/test_visitor_log_smoke.py",
            "kind": "test",
            "reason": "elite: generated smoke tests",
        }
    )
    assert not is_option_a_runtime_block(
        {
            "source_file": "i18n/visitor_log.pot",
            "kind": "i18n",
            "reason": "elite: translation template",
        }
    )
    assert is_option_a_runtime_block(
        {
            "source_file": "models/x_loan_fine_compute.py",
            "kind": "python",
            "reason": "elite: overdue fine compute",
        }
    )
    assert is_option_a_runtime_block(
        {
            "source_file": "report/invoice_pay_qr.xml",
            "kind": "qweb",
            "reason": "Pay now + QR",
        }
    )


def test_option_a_list_is_deduped() -> None:
    draft = _pdf_draft()
    items = (draft.get("_live_apply") or {}).get("option_a") or []
    paths = [str(x).split(" — ", 1)[0] for x in items]
    assert len(paths) == len(set(paths))
    assert len(items) <= 4


def test_dedupe_prefers_scaffold_reason() -> None:
    out = dedupe_option_a_items(
        [
            "report/a.xml — PDF / QWeb report: Document layout",
            "report/a.xml — QWeb inherit: Pay now + QR",
            "models/b.py — Fill x_payment_url",
        ]
    )
    assert len(out) == 2
    assert "Pay now" in out[0]


def test_structural_smoke_and_lift_on_fake_rpc_ok() -> None:
    draft = _pdf_draft()
    structural = structural_option_a_smoke(draft)
    assert structural.get("structural_ok") is True
    assert structural.get("ok") is False  # structural alone never proves

    # Simulate sandbox smoke pass → score can lift past cap.
    stamp_option_a_smoke(
        draft,
        {
            "ok": True,
            "structural_ok": True,
            "level": "sandbox_rpc",
            "checks": [{"id": "ir_ui_view_document_extras", "ok": True}],
            "message": "simulated",
        },
    )
    assert draft.get("_go_live_ready") is True
    sc = draft.get("_scorecard") or {}
    assert float(sc.get("score_0_10") or 0) > OPTION_A_SCORE_CAP
    assert not any(
        f.get("element") == "option_a_unproven" for f in (sc.get("findings") or [])
    )


def test_sla_field_pack_not_capped() -> None:
    draft, _h, _w = draft_component_from_prompt(
        "Add SLA due date on invoices",
        available_models=["account.move"],
    )
    attach_live_apply_contract(draft)
    attach_scorecard(draft, user_prompt="Add SLA due date on invoices")
    assert not draft.get("_capability_primary_option_a")
    assert float((draft.get("_scorecard") or {}).get("score_0_10") or 0) >= 9.0
    assert (draft.get("_done_bar") or {}).get("mode") == "live"


def test_residual_plus_paystack_is_mixed_not_option_a_primary() -> None:
    draft = {
        "models": [
            {
                "model": "x_matter",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {"model": "account.move", "mode": "inherit", "fields": []},
        ],
        "depends": ["account", "payment"],
    }
    notes = stamp_capability_gaps(
        draft,
        "Law firm matter file. Paystack: dynamic QR and card checkout on retainer invoices.",
    )
    assert draft.get("_capability_primary_option_a") is False
    assert any("mixed live+Option A" in n for n in notes)
    attach_scorecard(
        draft,
        user_prompt="Law firm matter file. Paystack QR on invoices.",
    )
    assert not any(
        f.get("element") == "option_a_unproven"
        for f in ((draft.get("_scorecard") or {}).get("findings") or [])
    )


def test_phase3_payment_provider_gap() -> None:
    from app.ai_capability_gaps import assess_capability_gaps

    a = assess_capability_gaps("Wire a Paystack payment provider for invoices")
    assert any(g.id == "payment_provider" for g in a.gaps)
    draft = {
        "models": [{"model": "account.move", "mode": "inherit", "fields": []}],
        "depends": ["account"],
    }
    stamp_capability_gaps(draft, "Wire a Paystack payment provider for invoices")
    paths = {
        str(b.get("source_file"))
        for b in (draft.get("custom_code_blocks") or [])
        if isinstance(b, dict)
    }
    assert "data/payment_provider_stub.xml" in paths
