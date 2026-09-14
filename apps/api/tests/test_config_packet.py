"""Config Packet A–C: fingerprint, diff, apply gates, recipes, icons, roster."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.app_icons import ICON_SIZE, render_app_icon_png
from app.config_packet.checklist import build_checklist
from app.config_packet.diff import diff_packet
from app.config_packet.fingerprint import fingerprint_instance
from app.config_packet.schema import (
    COA_THRESHOLD,
    ConfigAccounting,
    ConfigCompany,
    ConfigConnector,
    ConfigFiscalPosition,
    ConfigJournal,
    ConfigPacket,
    ConfigStock,
    ConfigTax,
    ConfigUser,
)
from app.config_packet.settings import sanitize_settings
from app.config_packet.users import parse_roster_csv
from app.job_autopilot.sandbox_gate import AutopilotRefused, assert_autopilot_run_allowed
from app.job_autopilot.stock_kits import infer_warehouse_flags
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired


class _FpFake:
    def __init__(self) -> None:
        self.modules = ["sale", "account", "base"]
        self.journals = [
            {"id": 1, "name": "Customer Invoices", "type": "sale", "code": "INV"},
            {"id": 2, "name": "Trust", "type": "general", "code": "trust"},
        ]

    def model_exists(self, model: str) -> bool:
        return model in {
            "ir.module.module",
            "ir.model.data",
            "account.journal",
            "account.tax",
            "account.account",
            "res.users",
            "res.company",
            "stock.warehouse",
            "ir.mail_server",
            "res.config.settings",
        }

    def field_exists(self, model: str, name: str) -> bool:
        return name in {
            "share",
            "delivery_steps",
            "group_ids",
            "paperformat_id",
            "report_header",
            "report_footer",
        }

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        if model == "ir.module.module" and method == "search_read":
            domain = args[0] if args else []
            if domain and domain[0] == ("name", "=", "base"):
                return [{"latest_version": "19.0.1.5"}]
            return [{"name": n} for n in self.modules]
        if model == "account.journal" and method == "search_read":
            return list(self.journals)
        if model == "account.tax" and method == "search":
            return [3]
        if model == "account.tax" and method == "search_read":
            return [{"id": 3, "name": "Sale", "amount": 5.0, "type_tax_use": "sale"}]
        if model == "ir.model.data" and method == "search_read":
            return [{"module": "l10n_us", "name": "tax_sale", "res_id": 3}]
        if model == "account.account" and method == "search_count":
            return 40
        if model == "res.users" and method == "search_read":
            return [{"login": "admin"}, {"login": "ada@studio.test"}]
        if model == "res.company" and method == "search_read":
            return [{"name": "Sandbox Co", "currency_id": [1, "USD"], "country_id": [1, "US"], "report_header": "Studio Co — Accra", "report_footer": "Thank you for your business"}]
        if model == "res.country" and method == "search_read":
            return [{"code": "US"}]
        if model == "stock.warehouse" and method == "search_read":
            return [{"code": "MAIN", "name": "Main", "delivery_steps": "ship_only"}]
        if model == "ir.mail_server" and method == "search":
            return []
        if model == "res.config.settings" and method == "default_get":
            return {"group_uom": True, "smtp_password": "nope"}
        return []


def test_settings_allowlist_drops_secrets() -> None:
    clean = sanitize_settings(
        {"group_uom": True, "smtp_password": "x", "payment_secret": "y", "unknown": 1}
    )
    assert clean == {"group_uom": True}


def test_roster_csv_skips_admin_and_parses_roles() -> None:
    users = parse_roster_csv(
        "login,name,groups\n"
        "admin,Admin,base.group_system\n"
        "ada@studio.test,Ada,sales\n"
    )
    assert len(users) == 1
    assert users[0].login == "ada@studio.test"
    assert "sales_team.group_sale_salesman" in users[0].group_xmlids
    assert "base.group_user" in users[0].group_xmlids


def test_warehouse_needles() -> None:
    flags = infer_warehouse_flags("one-step delivery, MTO, dropship, lot tracking")
    assert flags["delivery_steps"] == "ship_only"
    assert flags["mto"] is True
    assert flags["dropship"] is True
    assert flags["lot_tracking"] is True
    three = infer_warehouse_flags("three-step pick pack ship")
    assert three["delivery_steps"] == "pick_pack_ship"


def test_fingerprint_and_diff_skips_installed() -> None:
    fp = fingerprint_instance(_FpFake())
    assert fp.major == 19
    assert "sale" in fp.modules_installed
    assert fp.account_code_count == 40
    assert "smtp_password" not in fp.settings
    packet = ConfigPacket(
        modules=["sale", "purchase", "account"],
        company=ConfigCompany(name="Client Co", currency="USD"),
        accounting=ConfigAccounting(
            journals=[ConfigJournal(name="Trust", type="general", code="trust")],
            tax_xmlids=["l10n_us.tax_sale"],
            account_code_count=40,
        ),
        stock=ConfigStock(warehouse_code="MAIN", delivery_steps="ship_only"),
        users=[ConfigUser(login="ada@studio.test"), ConfigUser(login="new@studio.test")],
        connectors=[
            ConfigConnector(id="payments", title="Payment acquirer", needs_secret=True, brands=["paystack"])
        ],
    )
    delta = diff_packet(packet, fp)
    install = [o.target for o in delta.ops if o.op == "install_module"]
    assert "purchase" in install
    assert "sale" not in install
    assert any(o.op == "create_user" and o.target == "new@studio.test" for o in delta.ops)
    assert not any(o.op == "create_user" and o.target == "ada@studio.test" for o in delta.ops)
    assert any(o.op == "secret_handoff" for o in delta.ops)
    assert any("Trust" in s or "trust" in s.lower() for s in delta.skipped) or not any(
        o.op == "create_journal" and "Trust" in o.detail for o in delta.ops
    )


def test_checklist_marks_secrets() -> None:
    packet = ConfigPacket(
        modules=["sale"],
        connectors=[ConfigConnector(id="payments", title="Paystack", needs_secret=True, brands=["paystack"])],
    )
    items = build_checklist(packet, None)
    secret = next(i for i in items if i.id == "secret:payments")
    assert secret.status == "secret"
    assert "Odoo" in (secret.href_hint or "")


def test_apply_observer_refused() -> None:
    from app.config_packet.apply import apply_config_packet

    report = apply_config_packet(
        client=_FpFake(),
        connection=SimpleNamespace(id="c1", write_mode="observer", url="https://client.example"),
        packet=ConfigPacket(),
        confirm_advanced=True,
        confirm_phrase=CONFIRM_PHRASE,
    )
    assert report.refused is True
    assert report.ok is False


def test_apply_requires_confirm_phrase() -> None:
    from app.config_packet.apply import apply_config_packet

    with pytest.raises(ConfirmationRequired):
        apply_config_packet(
            client=_FpFake(),
            connection=SimpleNamespace(
                id="c1", write_mode="standard", url="https://staging.example"
            ),
            packet=ConfigPacket(modules=["purchase"]),
            confirm_advanced=False,
            confirm_phrase=None,
        )


def test_autopilot_still_refuses_production() -> None:
    with pytest.raises(AutopilotRefused):
        assert_autopilot_run_allowed(
            SimpleNamespace(write_mode="production", url="https://erp.client.com"),
            confirm_advanced=True,
            confirm_phrase=CONFIRM_PHRASE,
        )


def test_capture_emits_packet_with_checklist() -> None:
    from app.config_packet.capture import capture_config_packet
    from app.job_autopilot.packet import AutopilotResult, JobPacket, SmokeReport

    result = AutopilotResult(
        packet=JobPacket(
            prompt="sell with Paystack",
            stock_apps=["sale", "account"],
            connectors=["payments"],
            org_emails=["ada@studio.test"],
        ),
        connection_kind="sandbox",
        sandbox=True,
        smoke=SmokeReport(ok=True, named_process="quote_to_invoice", message="ok"),
    )
    packet = capture_config_packet(_FpFake(), result)
    assert packet.secrets_excluded is True
    assert "sale" in packet.modules
    assert packet.checklist
    assert packet.sha256
    assert any(c.needs_secret for c in packet.connectors)
    assert packet.documents.report_header == "Studio Co — Accra"
    assert packet.documents.report_footer == "Thank you for your business"
    assert packet.documents.option_a_qweb_needed is False
    assert any(i.id == "letterhead" for i in packet.checklist)


def test_app_icon_is_real_png_not_placeholder() -> None:
    from app.store_readiness import PLACEHOLDER_ICON_PNG

    png = render_app_icon_png("Helpdesk")
    assert png.startswith(b"\x89PNG")
    assert len(png) > len(PLACEHOLDER_ICON_PNG)
    other = render_app_icon_png("Visitor Log")
    assert png != other
    assert ICON_SIZE == 64


def test_classify_users_csv_is_user_roster() -> None:
    from app.ingest.classify import classify_structured

    result = classify_structured(
        filename="users.csv",
        headers=["login", "email", "groups", "name"],
    )
    assert result.doc_type == "user_roster"


def test_thin_coa_blocks_opening_tb() -> None:
    from app.ingest.opening_balance import validate_opening_tb_table
    from app.ingest.schema import IngestRow, IngestTable

    class Thin:
        def model_exists(self, model: str) -> bool:
            return model in {"account.move", "account.account", "account.journal"}

        def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
            if model == "account.journal" and method == "search_read":
                return [{"id": 1, "name": "Opening", "code": "OPEN", "type": "general"}]
            if model == "account.account" and method == "search_count":
                return 2
            if model == "account.account" and method == "search_read":
                return [{"id": 1, "code": "1000"}]
            return []

    table = IngestTable(
        id="tb",
        model="account.move",
        doc_type="opening_trial_balance",
        rows=[IngestRow(raw={"code": "1000", "debit": "1", "credit": "0"})],
    )
    gaps, _ = validate_opening_tb_table(Thin(), table)
    assert any(COA_THRESHOLD == 8 and "Chart of accounts" in g.message for g in gaps)


def test_users_csv_template_has_no_password_column() -> None:
    from app.config_packet.users import parse_roster_csv, users_csv_template

    csv = users_csv_template()
    assert "password" not in csv.lower()
    assert csv.splitlines()[0] == "login,name,email,groups"
    users = parse_roster_csv(csv)
    assert users
    assert all(u.login for u in users)


def test_fiscal_diff_creates_positions_never_taxes() -> None:
    fp = fingerprint_instance(_FpFake())
    packet = ConfigPacket(
        accounting=ConfigAccounting(
            tax_xmlids=["l10n_us.tax_sale"],
            taxes=[
                ConfigTax(
                    xmlid="l10n_us.tax_sale",
                    tax_exigibility="on_payment",
                    cash_basis_account_xmlid="l10n_us.account_cash_basis",
                )
            ],
            fiscal_positions=[ConfigFiscalPosition(name="Export", auto_apply=True)],
            reconcile_models=[],
        )
    )
    delta = diff_packet(packet, fp)
    assert any(o.op == "create_fiscal_position" and o.target == "Export" for o in delta.ops)
    assert any(o.op == "write_cash_basis" and o.target == "l10n_us.tax_sale" for o in delta.ops)
    assert not any(o.op == "create_tax" for o in delta.ops)
    assert all(o.op != "install_module" or "tax" not in o.target for o in delta.ops)


def test_fiscal_apply_never_creates_account_tax() -> None:
    from app.config_packet.fiscal import apply_fiscal_kit

    class FiscalFake(_FpFake):
        def __init__(self) -> None:
            super().__init__()
            self.creates: list[tuple[str, dict[str, Any]]] = []

        def model_exists(self, model: str) -> bool:
            return super().model_exists(model) or model in {
                "account.fiscal.position",
                "account.reconcile.model",
                "ir.model.data",
            }

        def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
            if method == "create":
                payload = args[0] if args else {}
                self.creates.append((model, payload if isinstance(payload, dict) else {}))
                return 99
            if model == "account.fiscal.position" and method == "search":
                return []
            if model == "ir.model.data" and method == "search_read":
                domain = args[0] if args else []
                blob = str(domain)
                if "tax_sale" in blob:
                    return [{"res_id": 3}]
                return super().execute_kw(model, method, args, kwargs)
            return super().execute_kw(model, method, args, kwargs)

    client = FiscalFake()
    applied = apply_fiscal_kit(
        client,
        ConfigAccounting(
            taxes=[ConfigTax(xmlid="l10n_us.tax_sale", tax_exigibility="on_payment")],
            fiscal_positions=[ConfigFiscalPosition(name="Intra-EU")],
        ),
    )
    assert any("fiscal_position:Intra-EU" in a for a in applied)
    assert not any(model == "account.tax" for model, _ in client.creates)


def test_lock_date_blocks_opening_tb() -> None:
    from app.ingest.opening_balance import validate_opening_tb_table
    from app.ingest.schema import IngestRow, IngestTable

    class Locked:
        def model_exists(self, model: str) -> bool:
            return model in {"account.move", "account.account", "account.journal", "res.company"}

        def field_exists(self, model: str, name: str) -> bool:
            return model == "res.company" and name in {
                "period_lock_date",
                "fiscalyear_lock_date",
                "tax_lock_date",
            }

        def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
            if model == "account.journal" and method == "search_read":
                return [{"id": 1, "name": "Opening", "code": "OPEN", "type": "general"}]
            if model == "account.account" and method == "search_count":
                return 40
            if model == "account.account" and method == "search_read":
                return [{"id": 1, "code": "1000"}]
            if model == "res.company" and method == "search_read":
                return [{"period_lock_date": "2026-12-31"}]
            return []

    table = IngestTable(
        id="tb",
        model="account.move",
        doc_type="opening_trial_balance",
        rows=[
            IngestRow(raw={"code": "1000", "debit": "1", "credit": "0", "date": "2026-01-01"}),
        ],
    )
    gaps, _ = validate_opening_tb_table(Locked(), table)
    assert any("lock" in g.message.lower() for g in gaps)


def test_apply_document_layout_writes_stock_letterhead() -> None:
    from app.config_packet.schema import ConfigDocuments
    from app.job_autopilot.stock_kits import apply_document_layout

    class LayoutFake:
        def __init__(self) -> None:
            self.writes: list[dict[str, Any]] = []

        def model_exists(self, model: str) -> bool:
            return model in {"res.company"}

        def field_exists(self, model: str, name: str) -> bool:
            return name in {"report_header", "report_footer", "primary_color"}

        def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
            if method == "search_read":
                return [{"id": 7}]
            if method == "write":
                self.writes.append(args[1])
                return True
            return []

    client = LayoutFake()
    msg = apply_document_layout(
        client,
        ConfigDocuments(report_header="Acme Ltd", report_footer="Accra · TIN 123"),
    )
    assert msg and "report_header" in msg
    assert client.writes
    assert client.writes[0]["report_header"] == "Acme Ltd"
    assert client.writes[0]["report_footer"] == "Accra · TIN 123"


def test_checklist_letterhead_vs_option_a_qweb() -> None:
    from app.config_packet.schema import ConfigDocuments

    stock = ConfigPacket(documents=ConfigDocuments(report_header="Hi", logo_upload_needed=True))
    items = build_checklist(stock, None)
    assert any(i.id == "letterhead" for i in items)
    brand = next(i for i in items if i.id == "brand")
    assert "logo" in brand.label.lower()
    assert "Option A" not in brand.label

    option_a = ConfigPacket(
        documents=ConfigDocuments(logo_upload_needed=True, option_a_qweb_needed=True)
    )
    labels = [i.label for i in build_checklist(option_a, None) if i.id == "brand"]
    assert labels and "Option A" in labels[0]
