"""Tests for protected_modules classification (PCM-1)."""

from __future__ import annotations

import pytest

from app.protected_modules import (
    PROTECTED_PATTERNS,
    TIER_1_KEYS,
    TIER_2_KEYS,
    build_manifest,
    classify,
    guardrail_prompt,
    protected_models_for,
)


@pytest.mark.parametrize(
    ("module", "expected_tier"),
    [
        ("account", "tier_1"),
        ("account_edi", "tier_1"),
        ("account_payment", "tier_1"),
        ("l10n_ng", "tier_2"),
        ("l10n_us", "tier_2"),
        ("stock_account", "tier_1"),
        ("stock_landed_costs", "tier_1"),
        ("mrp_account", "tier_1"),
        ("payment", "tier_1"),
        ("payment_flutterwave", "tier_1"),
        ("payment_stripe", "tier_1"),
        ("pos_account_tax_python", "tier_1"),
        ("pos_stripe", "tier_1"),
        ("pos_online_payment", "tier_1"),
        ("hr_payroll", "tier_1"),
        ("hr_payroll_account", "tier_1"),
        ("sign", "tier_1"),
        ("sale_subscription", "tier_1"),
        ("iap", "tier_1"),
        ("iap_mail", "tier_1"),
        ("base", "tier_2"),
        ("web", "tier_2"),
        ("auth_oauth", "tier_2"),
        ("mail", "tier_2"),
        ("crm", None),
        ("project", None),
        ("stock", None),
        ("sale", None),
        ("contacts", None),
        ("website", None),
    ],
)
def test_classify_modules(module: str, expected_tier: str | None) -> None:
    assert classify(module) == expected_tier


def test_protected_patterns_keys_match_card() -> None:
    expected = {
        "accounting_core",
        "fiscal_localization",
        "stock_valuation",
        "payment_processing",
        "pos_financial",
        "payroll",
        "esign",
        "subscriptions",
        "iap_billing",
        "framework_core",
        "auth_security",
        "messaging_audit",
    }
    assert set(PROTECTED_PATTERNS) == expected
    assert TIER_1_KEYS | TIER_2_KEYS == expected


def test_build_manifest_buckets() -> None:
    manifest = build_manifest(
        ["account", "crm", "l10n_ng", "payment_stripe", "mail"],
        "test",
    )
    assert manifest["source"] == "test"
    assert "account" in manifest["tier_1_never_generate_logic"]["accounting_core"]
    assert "payment_stripe" in manifest["tier_1_never_generate_logic"]["payment_processing"]
    assert "l10n_ng" in manifest["tier_2_extend_only"]["fiscal_localization"]
    assert "mail" in manifest["tier_2_extend_only"]["messaging_audit"]
    assert manifest["unclassified_count"] == 1
    assert "crm" in manifest["unclassified_sample"]


def test_protected_models_for_account_move() -> None:
    manifest = build_manifest(["account"], "test")
    assert protected_models_for(manifest, "account.move") == "tier_1"
    assert protected_models_for(manifest, "account.move.line") == "tier_1"
    assert protected_models_for(manifest, "account.tax") == "tier_1"
    assert protected_models_for(manifest, "account.payment") == "tier_1"


def test_protected_models_for_payment_and_payroll() -> None:
    manifest = build_manifest(["payment", "hr_payroll", "sign"], "test")
    assert protected_models_for(manifest, "payment.transaction") == "tier_1"
    assert protected_models_for(manifest, "hr.payslip") == "tier_1"
    assert protected_models_for(manifest, "sign.request") == "tier_1"


def test_protected_models_link_only_models_unclassified() -> None:
    manifest = build_manifest(["crm"], "test")
    assert protected_models_for(manifest, "res.partner") is None
    assert protected_models_for(manifest, "x_matter") is None


def test_guardrail_prompt_includes_categories_and_effect_clause() -> None:
    manifest = build_manifest(["account", "payment"], "test")
    text = guardrail_prompt(manifest)
    assert "accounting_core" in text
    assert "payment_processing" in text
    assert "EFFECT" in text
    assert "not the mechanism" in text

