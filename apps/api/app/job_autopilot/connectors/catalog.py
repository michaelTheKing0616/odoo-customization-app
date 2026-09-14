"""Domain-agnostic connector recipes. Order is the Autopilot furthermost path.

Any vertical can match: a law firm Paystack retainer, a clinic WhatsApp line,
a factory marketplace feed, a restaurant KDS — same five lanes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.text_negation import has_positive_match

CONNECTOR_ORDER: tuple[str, ...] = (
    "payments",
    "inbound_orders",
    "messaging",
    "hardware",
    "statutory_payroll",
)


@dataclass(frozen=True)
class ConnectorSpec:
    id: str
    title: str
    needles: tuple[re.Pattern[str], ...]
    requires_country_pack: bool = False


SPECS: tuple[ConnectorSpec, ...] = (
    ConnectorSpec(
        id="payments",
        title="Payment acquirer",
        needles=(
            re.compile(
                r"(?i)\b(paystack|flutterwave|stripe|paypal|adyen|razorpay|"
                r"moniepoint|coralpay|square|payment gateway|dynamic qr|"
                r"card terminal|pos payment)\b"
            ),
        ),
    ),
    ConnectorSpec(
        id="inbound_orders",
        title="Inbound channel orders",
        needles=(
            re.compile(
                r"(?i)\b(chowdeck|glovo|doordash|ubereats|uber eats|jumia|"
                r"just eat|grubhub|"
                r"third-?party (?:delivery|platform)|"
                r"(?:food|order|channel) marketplace|"
                r"marketplace orders?|"
                r"online orders? inject|channel orders?)\b"
            ),
        ),
    ),
    ConnectorSpec(
        id="messaging",
        title="Messaging channel",
        needles=(
            re.compile(
                r"(?i)\b(whatsapp|telegram bot|sms chatbot|chatbot|"
                r"messaging api|cloud api)\b"
            ),
        ),
    ),
    ConnectorSpec(
        id="hardware",
        title="Edge hardware",
        needles=(
            re.compile(
                r"(?i)\b(kds|kitchen display|iot box|pos printer|"
                r"preparation display|barcode scanner|biometric|"
                r"handheld (?:android )?tablet|card terminal hardware)\b"
            ),
        ),
    ),
    ConnectorSpec(
        id="statutory_payroll",
        title="Statutory payroll",
        needles=(
            re.compile(
                r"(?i)\b(payroll|payslip|paye|pension|nhf|"
                r"statutory deduction|withholding tax on (?:salary|wage))\b"
            ),
        ),
        requires_country_pack=True,
    ),
)

_SPEC_BY_ID = {s.id: s for s in SPECS}


def infer_connector_ids(text: str, country_code: str | None = None) -> list[str]:
    """Return matched connector ids in CONNECTOR_ORDER (never catalog order of verticals)."""
    blob = text or ""
    out: list[str] = []
    for spec in SPECS:
        if not any(has_positive_match(pat, blob) for pat in spec.needles):
            continue
        out.append(spec.id)
    return [cid for cid in CONNECTOR_ORDER if cid in out]


def spec_for(connector_id: str) -> ConnectorSpec | None:
    return _SPEC_BY_ID.get(connector_id)


def detected_brands(text: str, connector_id: str) -> list[str]:
    """Human labels for the UAT report — still domain-agnostic (brand ≠ vertical)."""
    blob = (text or "").lower()
    brands: dict[str, tuple[str, ...]] = {
        "payments": (
            "paystack",
            "flutterwave",
            "stripe",
            "paypal",
            "adyen",
            "razorpay",
            "moniepoint",
            "coralpay",
            "square",
        ),
        "inbound_orders": (
            "chowdeck",
            "glovo",
            "doordash",
            "ubereats",
            "uber eats",
            "jumia",
            "just eat",
            "grubhub",
        ),
        "messaging": ("whatsapp", "telegram", "sms"),
        "hardware": ("kds", "iot", "pos printer", "biometric"),
        "statutory_payroll": ("paye", "pension", "nhf", "payroll"),
    }
    found: list[str] = []
    for brand in brands.get(connector_id, ()):
        if brand in blob and brand not in found:
            found.append(brand)
    return found


__all__ = [
    "CONNECTOR_ORDER",
    "ConnectorSpec",
    "SPECS",
    "detected_brands",
    "infer_connector_ids",
    "spec_for",
]
