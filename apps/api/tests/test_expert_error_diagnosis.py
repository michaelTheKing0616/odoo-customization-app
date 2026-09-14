"""Broad Expert software-bug diagnosis regression tests."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.expert.error_diagnosis import try_rule_based_error_diagnosis  # noqa: E402
from app.expert.grounding import GroundingBundle, looks_like_rpc_error  # noqa: E402
from app.expert.product_guidance import try_rule_based_product_guidance  # noqa: E402


def _diag(question: str, **kwargs):
    return try_rule_based_error_diagnosis(
        question,
        kwargs.pop("bundle", GroundingBundle()),
        connection_id=kwargs.pop("connection_id", "conn-1"),
        **kwargs,
    )


def test_looks_like_rpc_detects_request_failed_empty_field() -> None:
    q = (
        "Request failed\n\n"
        '<Fault 2: \'Error while validating view near:\\n\\n <field name=""/>\\n'
        "\\nField tag must have a \"name\" attribute defined'>"
    )
    assert looks_like_rpc_error(q)


def test_empty_field_name_preferred_over_product_guidance() -> None:
    q = (
        "Diagnose with Expert\n\nRequest failed\n\n"
        "<Fault 2: 'Error while validating view near:\\n\\n "
        '<field name=""/>\\n <field name=""/>\\n </group>\\n <notebook>\\n'
        "\\nField tag must have a \"name\" attribute defined'>"
    )
    assert try_rule_based_product_guidance(q, GroundingBundle(), connection_id="c1") is None
    result = _diag(q)
    assert result is not None
    md = result["answer_markdown"].lower()
    assert "empty" in md or 'name=""' in result["answer_markdown"]
    assert "estate.property" not in md
    assert "peppol" not in md
    assert "paymentprovider" not in md
    assert "empty_field_name_in_arch" in result["caution_flags"]
    assert any(t.get("id") == "designer" for t in (result.get("suggested_tools") or []))


def test_model_not_found_view_validation() -> None:
    result = _diag(
        "Diagnose this error\n\nError log:\n"
        "<Fault 2: 'Error while validating view near:\\n\\nModel not found: x_ticket'>"
    )
    assert result is not None
    assert "x_ticket" in result["answer_markdown"]
    assert "Models & Fields" in result["answer_markdown"]


def test_access_error_points_to_access_matrix() -> None:
    result = _diag(
        "AccessError: You are not allowed to modify 'account.move' (account.move) records"
    )
    assert result is not None
    assert "AccessError" in result["answer_markdown"]
    assert "access-matrix" in result["answer_markdown"]


def test_unknown_field_in_view() -> None:
    result = _diag(
        '<Fault 2: \'Error while validating view near:\\n<field name="x_missing"/>\\n'
        "Field \"x_missing\" does not exist'>"
    )
    assert result is not None
    assert "x_missing" in result["answer_markdown"]
    assert "field_not_found" in result["caution_flags"]


def test_xpath_miss() -> None:
    result = _diag(
        "Error while validating view near:\n"
        "Element '<xpath expr=\"//field[@name='phone']\">' cannot be located in parent view"
    )
    assert result is not None
    assert "xpath" in result["answer_markdown"].lower()
    assert "xpath_miss" in result["caution_flags"]


def test_sandbox_amount_tax_xpath_not_xmlrpc_model() -> None:
    q = (
        "<Fault 1: 'Traceback (most recent call last):\n"
        ' File "/usr/lib/python3/dist-packages/odoo/addons/rpc/controllers/xmlrpc.py", line 162\n'
        "odoo.tools.convert.ParseError: while parsing "
        "/mnt/extra-addons/custom_markup/views/sale_order_views.xml:2\n"
        "Error while parsing or validating view:\n\n"
        "Element '<xpath expr=\"//field[@name=&#39;amount_tax&#39;]\">' "
        "cannot be located in parent view\n"
        "'view.model': 'sale.order',\n"
        "'xmlid': 'view_order_form_with_markup'\n'>"
    )
    bundle = GroundingBundle(
        error_diagnostics=[
            {"model": "xmlrpc", "field": "py", "status": "model_missing"},
        ],
        instance_summary={"server_version": "19.0-20260723", "edition": "community"},
    )
    result = _diag(q, bundle=bundle)
    assert result is not None
    md = result["answer_markdown"]
    assert "xpath_miss" in result["caution_flags"]
    assert "live_model_missing" not in result["caution_flags"]
    assert "Install the module that provides `xmlrpc`" not in md
    assert "tax_totals" in md
    assert "amount_tax" in md
    assert "ParseError" in md
    assert "Promote" in md


def test_integrity_null_column() -> None:
    result = _diag(
        "IntegrityError: null value in column \"x_required\" violates not-null constraint"
    )
    assert result is not None
    assert "integrity" in result["answer_markdown"].lower() or "NOT NULL" in result["answer_markdown"]


def test_confirm_phrase_gate() -> None:
    result = _diag("Confirmation required: type I understand the risks to continue")
    assert result is not None
    assert "understand the risks" in result["answer_markdown"].lower()


def test_generic_fault_never_returns_none() -> None:
    result = _diag(
        "<Fault 2: 'Some obscure Odoo internal failure about widgets on account.move'>"
    )
    assert result is not None
    assert "generic_fault_fallback" in result["caution_flags"]
    assert "account.move" in result["answer_markdown"] or "Fault excerpt" in result["answer_markdown"]
    assert result["grounded"] is True


def test_live_model_missing_diagnostic() -> None:
    bundle = GroundingBundle(
        error_diagnostics=[
            {"model": "x_ticket", "field": None, "status": "model_missing"},
        ],
        instance_summary={"server_version": "19.0", "edition": "community"},
    )
    result = _diag("Model not found: x_ticket", bundle=bundle)
    assert result is not None
    assert "does not exist" in result["answer_markdown"]
    assert "19.0" in result["answer_markdown"]


def test_duplicate_chrome_diagnosis() -> None:
    result = _diag(
        "Bill form shows Send twice, Print twice, Pay twice, and Other Info Other Info"
    )
    assert result is not None
    assert "duplicate_view_chrome" in result["caution_flags"]
    assert "Fix duplicate chrome" in result["answer_markdown"]


def test_non_error_question_returns_none() -> None:
    assert _diag("How do I add a field?", connection_id=None) is None


def test_empty_diagnose_paste_is_not_odoo_rpc() -> None:
    from app.expert.grounding import looks_like_platform_error
    from app.expert.platform_guidance import try_rule_based_platform_guidance

    q = "Diagnose this error on my connection\n\nError log:\n"
    assert not looks_like_rpc_error(q)
    assert looks_like_platform_error(q)
    assert _diag(q) is None
    guided = try_rule_based_platform_guidance(q, GroundingBundle(), connection_id="c1")
    assert guided is not None
    md = guided["answer_markdown"].lower()
    assert "404" in md or "reverify" in md
    assert "uvicorn" in md
    assert "install this app" in md


def test_install_sales_api_404_is_platform_not_view_fault() -> None:
    from app.expert.grounding import looks_like_platform_error
    from app.expert.platform_guidance import try_rule_based_platform_guidance

    q = (
        "Diagnose this error on my connection\n\nError log:\n"
        "Not Found (POST /api/ai/option-a/reverify)"
    )
    assert looks_like_platform_error(q)
    assert not looks_like_rpc_error(q)
    assert _diag(q) is None
    guided = try_rule_based_platform_guidance(q, GroundingBundle(), connection_id="c1")
    assert guided is not None
    assert "reverify" in guided["answer_markdown"].lower()
    assert "designer" not in guided["answer_markdown"].lower() or "App Studio" in guided["answer_markdown"]

