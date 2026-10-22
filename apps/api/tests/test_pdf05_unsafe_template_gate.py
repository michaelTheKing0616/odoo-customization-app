"""PDF-05 — Unsafe template gate (t-raw, script, XXE, bad t-call, RT-22, block QWeb)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.qweb_unsafe_gate import (
    QWEB_T_CALL_ALLOWLIST,
    arch_has_xxe,
    gate_report_arch,
    gate_report_design_spec,
    refuse_unsafe_block_text,
    refuse_unsafe_qweb_arch,
)
from app.report_design import compile_report_design, refuse_root_replace
from app.routers import reports as reports_router


SAFE_PRIMARY = {
    "report_key": "custom.report_safe",
    "use_external_layout": True,
    "blocks": [
        {"type": "heading", "text": "Invoice", "level": 1},
        {"type": "text", "text": "Thank you for your business."},
        {"type": "field", "field": "display_name"},
    ],
}


def test_allowlist_documents_stock_layouts() -> None:
    assert "web.external_layout" in QWEB_T_CALL_ALLOWLIST
    assert "web.html_container" in QWEB_T_CALL_ALLOWLIST
    assert "web.basic_layout" in QWEB_T_CALL_ALLOWLIST
    assert "web.minimal_layout" in QWEB_T_CALL_ALLOWLIST
    assert "web.internal_layout" in QWEB_T_CALL_ALLOWLIST


def test_pdf05_refuses_t_raw_before_save() -> None:
    arch = '<t t-name="x"><div t-raw="doc.note"/></t>'
    with pytest.raises(ValueError, match="t-raw"):
        refuse_unsafe_qweb_arch(arch)


def test_pdf05_refuses_t_out() -> None:
    arch = '<t t-name="x"><span t-out="doc.html"/></t>'
    with pytest.raises(ValueError, match="t-out"):
        refuse_unsafe_qweb_arch(arch)


def test_pdf05_refuses_script_any_case() -> None:
    with pytest.raises(ValueError, match="script"):
        refuse_unsafe_qweb_arch('<t t-name="x"><SCRIPT src="evil.js"></SCRIPT></t>')
    with pytest.raises(ValueError, match="script"):
        refuse_unsafe_qweb_arch('<t t-name="x"><script>alert(1)</script></t>')


def test_pdf05_refuses_doctype_and_entity_xxe() -> None:
    doctype = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        '<t t-name="x">&xxe;</t>'
    )
    assert arch_has_xxe(doctype) is True
    with pytest.raises(ValueError, match="external entities|DOCTYPE"):
        refuse_unsafe_qweb_arch(doctype)
    with pytest.raises(ValueError, match="external entities|DOCTYPE"):
        refuse_unsafe_qweb_arch('<!ENTITY foo "bar"><t t-name="x"/>')


def test_pdf05_refuses_non_allowlisted_t_call() -> None:
    arch = '<t t-name="x"><t t-call="evil.payload"/></t>'
    with pytest.raises(ValueError, match="not on the allowlist"):
        refuse_unsafe_qweb_arch(arch)
    # allowlisted targets pass
    refuse_unsafe_qweb_arch(
        '<t t-name="custom.report_x"><t t-call="web.external_layout">'
        '<div class="page"/></t></t>'
    )
    refuse_unsafe_qweb_arch(
        '<t t-name="custom.report_x"><t t-call="web.html_container">'
        '<div class="page"/></t></t>'
    )


def test_pdf05_rt22_root_replace_still_refused() -> None:
    """Negative: RT-22 root replace stays refused (PDF-03 intact)."""
    with pytest.raises(ValueError, match="root or a large subtree"):
        refuse_root_replace("/", "replace")
    with pytest.raises(ValueError, match="root or a large subtree"):
        compile_report_design(
            {
                "mode": "inherit",
                "inherit": {
                    "base_report_key": "account.report_invoice",
                    "xpath": "/",
                    "position": "replace",
                },
                "blocks": [{"type": "text", "text": "x"}],
            }
        )


def test_pdf05_block_text_qweb_injection_refused() -> None:
    """Negative: a block whose text would be interpreted as QWeb is refused."""
    with pytest.raises(ValueError, match="must not contain QWeb"):
        refuse_unsafe_block_text(
            {"blocks": [{"type": "heading", "text": '<t t-esc="doc.name"/>', "level": 1}]}
        )
    with pytest.raises(ValueError, match="must not contain QWeb"):
        refuse_unsafe_block_text(
            {"blocks": [{"type": "text", "text": "{{ doc.secret }}"}]}
        )
    with pytest.raises(ValueError, match="must not contain QWeb"):
        refuse_unsafe_block_text(
            {"blocks": [{"type": "text", "text": 'Hello t-raw="note"'}]}
        )
    with pytest.raises(ValueError, match="must not contain QWeb"):
        refuse_unsafe_block_text(
            {
                "blocks": [
                    {
                        "type": "label_field",
                        "label": '<t t-call="evil.x"/>',
                        "field": "name",
                    }
                ]
            }
        )
    # benign text OK
    refuse_unsafe_block_text(
        {"blocks": [{"type": "heading", "text": "Quarterly statement", "level": 2}]}
    )


def test_pdf05_compile_gates_block_text_and_emits_safe_arch() -> None:
    with pytest.raises(ValueError, match="must not contain QWeb"):
        compile_report_design(
            {
                "report_key": "custom.report_bad",
                "blocks": [{"type": "text", "text": "<t t-esc='x'/>"}],
            }
        )
    out = compile_report_design(SAFE_PRIMARY)
    assert 't-call="web.external_layout"' in out["arch"]
    assert "t-raw" not in out["arch"]
    gate_report_arch(out["arch"])  # idempotent


def test_pdf05_update_route_refuses_pasted_unsafe_arch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pasted arch is rejected before ir.ui.view write."""

    writes: list[Any] = []

    class _Client:
        def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict | None = None):
            if model == "ir.actions.report" and method == "read":
                return [
                    {
                        "name": "Partner",
                        "model": "res.partner",
                        "report_type": "qweb-pdf",
                        "report_name": "custom.report_partner",
                        "paperformat_id": False,
                    }
                ]
            if model == "ir.ui.view" and method == "search_read":
                return [{"id": 9, "arch": "<t t-name='custom.report_partner'/>", "key": "custom.report_partner"}]
            if model == "ir.ui.view" and method == "write":
                writes.append(args)
                return True
            raise AssertionError(f"unexpected {model}.{method}")

    monkeypatch.setattr(reports_router, "_client", lambda *_a, **_k: _Client())
    monkeypatch.setattr(
        "app.snapshots.snapshot_report",
        lambda *_a, **_k: None,
    )

    body = reports_router.UpdateReportBody(
        arch='<t t-name="custom.report_partner"><div t-raw="doc.x"/></t>'
    )
    with pytest.raises(HTTPException) as exc:
        reports_router.update_report("conn-1", 1, body, db=MagicMock())
    assert exc.value.status_code == 422
    assert "t-raw" in str(exc.value.detail)
    assert writes == []


def test_pdf05_update_route_refuses_bad_t_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Client:
        def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict | None = None):
            if model == "ir.actions.report" and method == "read":
                return [
                    {
                        "name": "Partner",
                        "model": "res.partner",
                        "report_type": "qweb-pdf",
                        "report_name": "custom.report_partner",
                        "paperformat_id": False,
                    }
                ]
            raise AssertionError(f"unexpected {model}.{method}")

    monkeypatch.setattr(reports_router, "_client", lambda *_a, **_k: _Client())
    monkeypatch.setattr("app.snapshots.snapshot_report", lambda *_a, **_k: None)

    body = reports_router.UpdateReportBody(
        arch='<t t-name="custom.report_partner"><t t-call="website.layout"/></t>'
    )
    with pytest.raises(HTTPException) as exc:
        reports_router.update_report("conn-1", 1, body, db=MagicMock())
    assert exc.value.status_code == 422
    assert "allowlist" in str(exc.value.detail)


def test_pdf05_create_route_gates_pasted_arch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Client:
        def model_exists(self, model: str) -> bool:
            return model == "res.partner"

        def execute_kw(self, *a, **k):
            raise AssertionError("must not reach Odoo when arch is unsafe")

    monkeypatch.setattr(reports_router, "_client", lambda *_a, **_k: _Client())
    body = reports_router.CreateReportBody(
        name="Bad",
        model="res.partner",
        report_key="custom.report_bad",
        arch='<!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://evil">]><t t-name="custom.report_bad"/>',
    )
    with pytest.raises(HTTPException) as exc:
        reports_router.create_report("conn-1", body, db=MagicMock())
    assert exc.value.status_code == 422
    assert "external entities" in str(exc.value.detail) or "DOCTYPE" in str(exc.value.detail)


def test_gate_report_design_spec_wrapper() -> None:
    with pytest.raises(ValueError, match="QWeb"):
        gate_report_design_spec({"blocks": [{"type": "text", "text": "t-call=evil"}]})
