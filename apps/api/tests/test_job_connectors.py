"""Domain-agnostic Autopilot connector recipes (any vertical, fixed lane order)."""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ["AI_ASSIST"] = "off"

from app.job_autopilot.connectors.catalog import CONNECTOR_ORDER, infer_connector_ids
from app.job_autopilot.connectors.runner import run_connectors
from app.job_autopilot.connectors.statutory import compute_ng
from app.job_autopilot.packet import (
    AutopilotResult,
    BootstrapReport,
    ConnectorReport,
    JobPacket,
    SmokeReport,
)
from app.job_autopilot.planner import build_job_packet
from app.job_autopilot.scorecard import score_job


def test_catalog_order_is_fixed() -> None:
    assert CONNECTOR_ORDER == (
        "payments",
        "inbound_orders",
        "messaging",
        "hardware",
        "statutory_payroll",
    )


def test_infer_restaurant_needles_are_lanes_not_vertical() -> None:
    brief = (
        "Restaurant POS, kitchen display, Chowdeck and Glovo, WhatsApp ordering, "
        "Paystack QR, biometric attendance."
    )
    assert infer_connector_ids(brief, "NG") == [
        "payments",
        "inbound_orders",
        "messaging",
        "hardware",
    ]


def test_infer_law_firm_paystack_whatsapp_only() -> None:
    ids = infer_connector_ids(
        "Law firm retainers billed on Paystack. WhatsApp for client intake.",
        "NG",
    )
    assert ids == ["payments", "messaging"]


def test_infer_legal_marketplace_is_not_inbound() -> None:
    ids = infer_connector_ids(
        "Law firm on a legal marketplace of counsel. Paystack retainers. WhatsApp intake.",
        "NG",
    )
    assert "inbound_orders" not in ids
    assert ids == ["payments", "messaging"]


def test_infer_negated_food_marketplace_is_not_inbound() -> None:
    ids = infer_connector_ids(
        "Law Firm / Legal Practice. No third-party food marketplace. "
        "No shop-floor or kitchen hardware. Paystack retainers. WhatsApp intake. "
        "PAYE, PENCOM pension, NHF payroll.",
        "NG",
    )
    assert "inbound_orders" not in ids
    assert "hardware" not in ids
    assert ids == ["payments", "messaging", "statutory_payroll"]


def test_infer_factory_marketplace_plus_payroll() -> None:
    ids = infer_connector_ids(
        "Factory sells on Jumia marketplace. PAYE and NHF payroll for the plant.",
        "NG",
    )
    assert ids == ["inbound_orders", "statutory_payroll"]


def test_compute_ng_golden_500k() -> None:
    result = compute_ng(500_000.0)
    assert result.country == "NG"
    assert result.employee_pension == 40_000.0
    assert result.employer_pension == 50_000.0
    assert result.nhf == 2_500.0
    assert result.paye == 11_025.0
    assert result.net == 446_475.0


def test_all_five_lanes_on_mixed_brief() -> None:
    packet = build_job_packet(
        "Clinic in Nigeria. Paystack checkout, Jumia marketplace orders, "
        "WhatsApp booking line, IoT box at reception, PAYE and NHF payroll.",
        use_llm=False,
    )
    assert packet.connectors == list(CONNECTOR_ORDER)
    models = {r.model for r in packet.custom_residuals}
    assert "x_kds" not in models
    assert "x_payslip" not in models
    assert "x_stay" not in models


class _ConnectorFake:
    def __init__(self) -> None:
        self.models = {
            "payment.provider",
            "sale.order",
            "sale.order.line",
            "product.product",
            "product.template",
            "res.partner",
            "pos.config",
        }
        self.created: list[tuple[str, dict[str, Any]]] = []
        self._n = 20
        self.providers: list[dict[str, Any]] = []

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def get_module_state(self, name: str) -> dict[str, Any] | None:
        if name == "point_of_sale":
            return {"name": name, "state": "installed"}
        return None

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        if method == "create":
            self._n += 1
            vals = args[0] if args else {}
            self.created.append((model, vals))
            if model == "payment.provider":
                self.providers.append({"id": self._n, **vals})
            return self._n
        if method == "search":
            domain = args[0] if args else []
            if model == "product.product":
                return [8]
            if model == "res.partner":
                return []
            return []
        if method == "search_read":
            if model == "payment.provider":
                domain = args[0] if args else []
                if domain and "Autopilot" in str(domain):
                    return [p for p in self.providers if "Autopilot" in str(p.get("name"))]
                return list(self.providers)
            return []
        return []


def test_runner_lands_on_stock_models() -> None:
    client = _ConnectorFake()
    packet = JobPacket(
        prompt="Paystack QR, Chowdeck, WhatsApp, kitchen display, PAYE NHF Nigeria",
        country_code="NG",
        connectors=list(CONNECTOR_ORDER),
        stock_apps=["sale", "account", "point_of_sale", "hr"],
    )
    report = run_connectors(client, packet, BootstrapReport())
    assert "payments" in report.ran
    assert "inbound_orders" in report.ran
    assert "messaging" in report.ran
    assert "hardware" in report.ran
    assert "statutory_payroll" in report.ran
    assert report.failed == []
    models_created = {m for m, _v in client.created}
    assert "payment.provider" in models_created
    assert "sale.order" in models_created
    assert "hr.payslip" not in models_created
    assert "payment.transaction" not in models_created
    provider_vals = next(v for m, v in client.created if m == "payment.provider")
    assert "key" not in provider_vals
    assert "secret" not in str(provider_vals).lower()
    assert provider_vals.get("state") == "disabled"


def test_runner_skips_statutory_without_pack() -> None:
    packet = JobPacket(
        prompt="PAYE payroll",
        country_code="US",
        connectors=["statutory_payroll"],
    )
    report = run_connectors(object(), packet, None)
    assert report.skipped_ids == ["statutory_payroll"]
    assert report.failed == []
    assert report.ok is True


def test_connector_gap_does_not_zero_process_smoke() -> None:
    packet = JobPacket(prompt="sell", stock_apps=["sale", "account"])
    result = AutopilotResult(
        packet=packet,
        sandbox=True,
        connection_kind="sandbox",
        smoke=SmokeReport(ok=True, named_process="quote_to_invoice", message="ok"),
        connectors=ConnectorReport(
            ok=False,
            ran=["payments"],
            failed=["inbound_orders"],
            message="gap",
        ),
        bootstrap=BootstrapReport(installed=["sale"], probes=[]),
    )
    card = score_job(result)
    assert card.process_smoke == 10.0
    assert any("inbound_orders" in f for f in card.findings)
    assert any("do not zero process smoke" in f.lower() for f in card.findings)


def test_connector_fixtures_are_called_out_on_scorecard() -> None:
    packet = JobPacket(prompt="sell", stock_apps=["sale", "account"])
    result = AutopilotResult(
        packet=packet,
        sandbox=True,
        connection_kind="sandbox",
        smoke=SmokeReport(ok=True, named_process="quote_to_invoice", message="ok"),
        connectors=ConnectorReport(ok=True, ran=["payments", "messaging"], failed=[]),
        bootstrap=BootstrapReport(already_installed=["sale"], probes=[]),
    )
    card = score_job(result)
    assert any("sandbox fixtures only" in f.lower() for f in card.findings)
