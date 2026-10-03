"""Slow sandbox suite — PR-D/E prove with real Docker (not fast CI).

Unit prove-bar coverage lives in ``test_option_a_prove_bar.py`` (mocked install).
This module is opted in with ``pytest -m sandbox`` when Docker is available.

Fast CI never requires Docker; nightly ``pytest -m sandbox`` does.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.sandbox import sandbox_docker_status


pytestmark = [pytest.mark.sandbox, pytest.mark.no_app_db]


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


def test_sandbox_docker_gate_documented() -> None:
    """Fast CI must not require Docker; sandbox mark is the opt-in."""
    ok, detail = sandbox_docker_status()
    if not ok:
        pytest.skip(f"Sandbox Docker unavailable: {detail}")
    assert ok is True


def test_failing_unittest_blocks_prove() -> None:
    """Failing unittest shape → ok=False, not promote_eligible (SandboxResult mock)."""
    from app.ai_option_a_quality import prove_option_a_in_sandbox

    draft = _authored_draft()
    fake_install = SimpleNamespace(
        ok=False,
        module=str(draft.get("technical_name") or "mod"),
        message="Unit tests failed",
        log_tail="FAIL: TestFail.test_always_fail\n",
        sandbox_url=None,
        odoo_major=19,
        test_failures=["TestFail.test_always_fail"],
        tests_ran=True,
        job_id=None,
    )
    with (
        patch(
            "app.module_spec_codec.export_draft_module_zip",
            return_value=b"PK\x03\x04fake",
        ),
        patch("app.sandbox.run_sandbox_install", return_value=fake_install),
    ):
        out = prove_option_a_in_sandbox(
            draft, odoo_major=19, run_tests=True, auto_repair=False
        )
    assert out.get("ok") is False
    assert out.get("promote_eligible") is not True
    install = draft.get("_sandbox_install") if isinstance(draft.get("_sandbox_install"), dict) else {}
    assert install.get("tests_ran") is True
    assert install.get("test_failures") == ["TestFail.test_always_fail"]
