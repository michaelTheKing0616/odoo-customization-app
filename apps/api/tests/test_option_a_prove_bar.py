"""PR-E: prove_status=proved only after install + run_tests=True; max 3 repair loop."""

from __future__ import annotations

from types import SimpleNamespace

from app.ai_option_a_quality import prove_option_a_in_sandbox, sandbox_verify_and_repair


def _authored_draft() -> dict:
    return {
        "technical_name": "ext_markup_test",
        "display_name": "Markup test",
        "depends": ["sale"],
        "grain": "full_app",
        "models": [{"model": "sale.order", "mode": "inherit", "fields": []}],
        "custom_code_blocks": [
            {
                "option_a": True,
                "source_file": "models/sale_order.py",
                "content": (
                    "from odoo import models\n\n"
                    "class SaleOrder(models.Model):\n"
                    "    _inherit = 'sale.order'\n"
                ),
            }
        ],
        "_generation_engine": {
            "capability": "option_a_authored",
            "artifact_kind": "option_a_module",
            "delivery_lane": "module_sh_or_self",
            "prove_status": "pending",
        },
        "_user_prompt": (
            "On Sales Orders add markup percent with Python compute. "
            "Option A module zip → sandbox → Promote."
        ),
    }


def _ok_result(*, tests_ran: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        module="ext_markup_test",
        message="installed",
        log_tail="ok",
        job_id=None,
        tests_ran=tests_ran,
        test_failures=[],
    )


def _fail_result(msg: str = "ParseError: bad xpath") -> SimpleNamespace:
    return SimpleNamespace(
        ok=False,
        module="ext_markup_test",
        message=msg,
        log_tail=f"FAIL: {msg}",
        job_id=None,
        tests_ran=False,
        test_failures=[f"FAIL: {msg}"] if "FAIL" in msg else [],
    )


def test_smoke_only_success_leaves_prove_pending(monkeypatch) -> None:
    draft = _authored_draft()
    monkeypatch.setattr(
        "app.module_spec_codec.export_draft_module_zip",
        lambda *_a, **_k: b"PK\x03\x04fake",
    )
    monkeypatch.setattr(
        "app.sandbox.run_sandbox_install",
        lambda *_a, **_k: _ok_result(tests_ran=False),
    )
    out = prove_option_a_in_sandbox(draft, odoo_major=19, run_tests=False)
    assert out["ok"] is True
    assert out["prove_status"] == "pending"
    assert out["promote_eligible"] is False
    assert draft.get("prove_status") == "pending"


def test_run_tests_true_stamps_proved(monkeypatch) -> None:
    draft = _authored_draft()
    monkeypatch.setattr(
        "app.module_spec_codec.export_draft_module_zip",
        lambda *_a, **_k: b"PK\x03\x04fake",
    )

    def fake_install(*_a, **kwargs):
        assert kwargs.get("run_tests") is True
        return _ok_result(tests_ran=True)

    monkeypatch.setattr("app.sandbox.run_sandbox_install", fake_install)
    out = prove_option_a_in_sandbox(draft, odoo_major=19, run_tests=True)
    assert out["ok"] is True
    assert out["prove_status"] == "proved"
    assert out["promote_eligible"] is True
    assert draft.get("prove_status") == "proved"
    assert (draft.get("_generation_engine") or {}).get("prove_status") == "proved"


def test_fail_repair_then_ok_with_tests_stamps_proved(monkeypatch) -> None:
    draft = _authored_draft()
    calls = {"n": 0}

    def fake_install(*_a, **kwargs):
        calls["n"] += 1
        assert kwargs.get("run_tests") is True
        if calls["n"] == 1:
            return _fail_result()
        return _ok_result(tests_ran=True)

    def fake_repair(draft_in, **_k):
        draft_in["_sandbox_repair_count"] = 1
        return {
            "applied": True,
            "gate_status": "pass",
            "repair": {"ok": True, "bucket": "sandbox", "repair_count": 1},
        }

    monkeypatch.setattr(
        "app.module_spec_codec.export_draft_module_zip",
        lambda *_a, **_k: b"PK\x03\x04fake",
    )
    monkeypatch.setattr("app.sandbox.run_sandbox_install", fake_install)
    monkeypatch.setattr(
        "app.ai_option_a_feedback.repair_option_a_from_feedback", fake_repair
    )
    out = prove_option_a_in_sandbox(
        draft, odoo_major=19, run_tests=True, auto_repair=True, max_attempts=3
    )
    assert out["ok"] is True
    assert calls["n"] == 2
    assert out["repairs_used"] >= 1
    assert out["prove_status"] == "proved"
    assert out["promote_eligible"] is True


def test_three_install_fails_stamps_failed(monkeypatch) -> None:
    draft = _authored_draft()
    calls = {"n": 0}

    def fake_install(*_a, **_k):
        calls["n"] += 1
        return _fail_result(f"boom attempt {calls['n']}")

    def fake_repair(draft_in, **_k):
        n = int(draft_in.get("_sandbox_repair_count") or 0) + 1
        draft_in["_sandbox_repair_count"] = n
        return {
            "applied": True,
            "gate_status": "pass",
            "repair": {"ok": True, "bucket": "sandbox", "repair_count": n},
        }

    monkeypatch.setattr(
        "app.module_spec_codec.export_draft_module_zip",
        lambda *_a, **_k: b"PK\x03\x04fake",
    )
    monkeypatch.setattr("app.sandbox.run_sandbox_install", fake_install)
    monkeypatch.setattr(
        "app.ai_option_a_feedback.repair_option_a_from_feedback", fake_repair
    )
    out = prove_option_a_in_sandbox(
        draft, odoo_major=19, run_tests=True, auto_repair=True, max_attempts=3
    )
    assert out["ok"] is False
    assert calls["n"] == 3
    assert out["prove_status"] == "failed"
    assert out["promote_eligible"] is False
    assert draft.get("prove_status") == "failed"


def test_sandbox_verify_and_repair_defaults_run_tests_true(monkeypatch) -> None:
    draft = _authored_draft()
    seen: dict = {}

    def fake_install(*_a, **kwargs):
        seen.update(kwargs)
        return _ok_result(tests_ran=True)

    monkeypatch.setattr(
        "app.module_spec_codec.export_draft_module_zip",
        lambda *_a, **_k: b"PK\x03\x04fake",
    )
    monkeypatch.setattr("app.sandbox.run_sandbox_install", fake_install)
    out = sandbox_verify_and_repair(draft, odoo_major=19)
    assert seen.get("run_tests") is True
    assert out["prove_status"] == "proved"
    assert out["promote_eligible"] is True
