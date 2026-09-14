"""Job Autopilot: packet, sandbox gate, bootstrap, custom residual, smoke."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ["AI_ASSIST"] = "off"

from app.job_autopilot.bootstrap import bootstrap_stock  # noqa: E402
from app.job_autopilot.custom import apply_custom_residual  # noqa: E402
from app.job_autopilot.executor import run_autopilot_job  # noqa: E402
from app.job_autopilot.packet import JobPacket  # noqa: E402
from app.job_autopilot.planner import build_job_packet  # noqa: E402
from app.job_autopilot.sandbox_gate import (  # noqa: E402
    AutopilotRefused,
    assert_autopilot_run_allowed,
    classify_connection,
)
from app.job_autopilot.smoke import run_process_smoke  # noqa: E402
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired  # noqa: E402


def test_stock_first_named_residual_is_in_packet() -> None:
    packet = build_job_packet(
        "# Operator brief\n## Goal\nPOS plus a loyalty punch card.\n"
        "## Stock reuse (named)\n- point_of_sale\n- sale\n- account\n"
        "## Custom residual\nloyalty punch card\n"
        "## Capability path\nstock_first\n",
        use_llm=False,
    )
    models = {r.model for r in packet.custom_residuals}
    assert any("loyalty" in m for m in models)
    assert "x_invoice" not in models
    assert "point_of_sale" in packet.stock_apps
    assert str(packet.operator_brief.get("custom_residual") or "").lower().startswith(
        "loyalty"
    )


def test_stock_first_pos_brief_packet_skips_website_sale() -> None:
    from test_ai_generation_engine import POS_STOCK_FIRST

    packet = build_job_packet(POS_STOCK_FIRST, use_llm=False)
    assert packet.custom_residuals == []
    assert "point_of_sale" in packet.stock_apps
    assert "sale" in packet.stock_apps
    assert "account" in packet.stock_apps
    assert "website_sale" not in packet.stock_apps
    assert packet.domain_label == "Point of Sale"
    assert packet.company_name is None
    assert packet.operator_brief.get("capability_path") == "stock_first"
    assert not str(packet.operator_brief.get("goal") or "").lower().startswith("# operator brief")
    assert not any("POS receipt designer is Option A" in d for d in packet.decision_record)


def test_stock_first_sales_invoice_has_no_custom_residual() -> None:
    packet = build_job_packet(
        "We sell widgets, send quotations, and invoice customers in the United States.",
        use_llm=False,
    )
    assert "sale" in packet.stock_apps
    assert "account" in packet.stock_apps
    assert packet.custom_residuals == []
    assert packet.country_code == "US"
    assert packet.l10n_module == "l10n_us"
    assert "completeness" in packet.scorecard_note.lower()


def test_booking_residual_not_parallel_invoice() -> None:
    packet = build_job_packet(
        "Recording studio in Lagos Nigeria. Clients book studio sessions. We invoice in naira.",
        file_excerpts=[("customers.csv", "name,email\nAda,ada@example.com\n")],
        use_llm=False,
    )
    models = {r.model for r in packet.custom_residuals}
    assert "x_booking" in models
    assert "x_invoice" not in models
    assert "x_client" not in models
    assert packet.country_code == "NG"
    assert any(f.doc_type == "customer_list" for f in packet.data_files)


def test_infer_odoo_stack_for_job_without_setup_phrasing() -> None:
    from app.expert.stack_inference import infer_odoo_stack, infer_odoo_stack_for_job

    brief = "Recording studio with bookings and invoicing"
    assert infer_odoo_stack(brief) is None
    stack = infer_odoo_stack_for_job(brief)
    assert stack is not None
    packet = build_job_packet(brief, use_llm=False)
    assert "sale" in packet.stock_apps
    assert "account" in packet.stock_apps


_RESTAURANT_BRIEF = """
## Business Requirements & Odoo ERP Integration Brief
Client Name: Sample Nigerian Restaurant & Lounge
Location: Abuja / Lagos, Nigeria
The restaurant requires POS, kitchen display, and recipe BoMs.
When a customer orders a plate of Jollof Rice, Odoo must deduct raw materials.
Point of Sale is the primary interface. Biometric pin-code check-in at the POS for Attendance.
Lagos State Hotel Occupancy and Restaurant Consumption Tax at 5%.
Integrate Chowdeck and Glovo. WhatsApp ordering. Paystack QR.
Bills of Materials via Odoo Manufacturing (mrp).
"""


def test_nigerian_restaurant_brief_is_not_hotel_stay() -> None:
    packet = build_job_packet(_RESTAURANT_BRIEF, use_llm=False)
    assert "Hotel" not in packet.domain_label
    assert "Restaurant" in packet.domain_label or "Food" in packet.domain_label
    assert packet.custom_residuals == []
    assert "x_stay" not in {r.model for r in packet.custom_residuals}
    assert "point_of_sale" in packet.stock_apps
    assert "mrp" in packet.stock_apps
    assert packet.country_code == "NG"
    assert packet.currency == "NGN"
    assert packet.company_name and "Restaurant" in packet.company_name
    assert packet.connectors == [
        "payments",
        "inbound_orders",
        "messaging",
        "hardware",
    ]
    assert any("domain-agnostic" in w for w in packet.warnings)


def test_hotel_pms_brief_still_gets_stay_residual() -> None:
    packet = build_job_packet(
        "Hotel PMS front desk check-in with housekeeping, guest folio, and room reservations.",
        use_llm=False,
    )
    assert any(r.model == "x_stay" for r in packet.custom_residuals)
    assert "Hotel" in packet.domain_label


def test_production_connection_refused() -> None:
    row = SimpleNamespace(write_mode="production", url="https://erp.example.com")
    kind, unattended = classify_connection(row)
    assert kind == "production"
    assert unattended is False
    with pytest.raises(AutopilotRefused, match="production"):
        assert_autopilot_run_allowed(row)


def test_observer_refused() -> None:
    row = SimpleNamespace(write_mode="observer", url="http://127.0.0.1:8069")
    with pytest.raises(AutopilotRefused, match="Observer"):
        assert_autopilot_run_allowed(row)


def test_staging_requires_confirm() -> None:
    row = SimpleNamespace(write_mode="standard", url="https://staging.example.com:443")
    with pytest.raises(ConfirmationRequired):
        assert_autopilot_run_allowed(row)
    kind = assert_autopilot_run_allowed(
        row, confirm_advanced=True, confirm_phrase=CONFIRM_PHRASE
    )
    assert kind == "staging"


def test_local_sandbox_unattended() -> None:
    row = SimpleNamespace(write_mode="standard", url="http://127.0.0.1:8069")
    kind, unattended = classify_connection(row)
    assert kind == "sandbox" and unattended
    assert assert_autopilot_run_allowed(row) == "sandbox"


class _BootstrapFake:
    def __init__(self) -> None:
        self.modules = {
            "mail": "installed",
            "contacts": "installed",
            "sale": "uninstalled",
            "account": "uninstalled",
            "l10n_us": "uninstalled",
            "l10n_ng": "uninstalled",
            "l10n_generic_coa": "uninstalled",
            "stock": "uninstalled",
        }
        self.installed: list[str] = []
        self.warehouse_rows: list[dict[str, Any]] = []
        self.company = {"id": 1, "name": "My Company"}
        self.writes: list[Any] = []
        self.busy_until: dict[str, int] = {}

    def update_module_list(self) -> None:
        return

    def get_module_state(self, name: str) -> dict[str, Any] | None:
        state = self.modules.get(name)
        if name not in self.modules:
            return None
        return {"name": name, "state": state}

    def ensure_module_installed(self, name: str) -> None:
        if name not in self.modules:
            raise RuntimeError(f"missing {name}")
        left = self.busy_until.get(name, 0)
        if left > 0:
            self.busy_until[name] = left - 1
            raise RuntimeError(
                "Odoo is currently processing a scheduled action.\n"
                "Module operations are not possible at this time, please try again later"
            )
        self.modules[name] = "installed"
        self.installed.append(name)
        if name == "sale" and self.modules.get("contacts") == "uninstalled":
            self.modules["contacts"] = "installed"
        if name in {"sale", "point_of_sale", "l10n_generic_coa", "l10n_us", "l10n_ng"}:
            if self.modules.get("account") == "uninstalled":
                self.modules["account"] = "installed"

    def model_exists(self, model: str) -> bool:
        return model in {"stock.warehouse", "res.company", "account.account", "account.move"}

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        if model == "res.company" and method == "search_read":
            return [self.company]
        if model == "res.company" and method == "write":
            self.writes.append(("company", args))
            return True
        if model == "res.currency" and method == "search":
            return [10]
        if model == "res.currency" and method == "write":
            self.writes.append(("currency", args))
            return True
        if model == "product.pricelist" and method == "search_read":
            return []
        if model == "product.pricelist" and method == "create":
            return 1
        if model == "product.pricelist" and method == "write":
            return True
        if model == "res.country" and method == "search":
            return [233]
        if model == "stock.warehouse" and method == "search_read":
            return list(self.warehouse_rows)
        if model == "stock.warehouse" and method == "create":
            wid = 5
            self.warehouse_rows.append({"id": wid, **args[0]})
            return wid
        if model == "account.account" and method == "search":
            return [1]
        return []


def test_bootstrap_installs_and_creates_warehouse() -> None:
    client = _BootstrapFake()
    packet = JobPacket(
        prompt="sell and stock",
        stock_apps=["mail", "contacts", "sale", "account", "stock", "l10n_us"],
        l10n_module="l10n_us",
        country_code="US",
        company_name="Acme",
        currency="USD",
        warehouse_needed=True,
    )
    with patch("app.job_autopilot.bootstrap.detect_l10n", return_value={"ok": True, "message": "ok"}):
        report = bootstrap_stock(client, packet)
    assert "sale" in report.installed
    assert "mail" in report.already_installed
    warehouse = next(p for p in report.probes if p.name == "warehouse")
    assert warehouse.ok
    assert "created" in warehouse.detail
    company = next(p for p in report.probes if p.name == "company")
    assert company.ok
    currency = next(p for p in report.probes if p.name == "currency")
    assert currency.ok
    assert any(w[0] == "currency" for w in client.writes)


def test_bootstrap_fresh_db_does_not_warn_account_missing_after_sale() -> None:
    """SKIP_GATE_MODULES=1: detect_l10n before install must not stick as a coverage warning."""
    from types import SimpleNamespace

    client = _BootstrapFake()
    client.modules["mail"] = "uninstalled"
    client.modules["contacts"] = "uninstalled"
    client.modules["point_of_sale"] = "uninstalled"
    client.modules["hr"] = "uninstalled"

    def _model_exists(model: str) -> bool:
        if model in {"account.move", "account.account"}:
            return client.modules.get("account") == "installed"
        return model in {"stock.warehouse", "res.company"}

    client.model_exists = _model_exists  # type: ignore[method-assign]

    def _list_installed(*, name_prefix: str | None = None, limit: int = 200):
        prefix = name_prefix or ""
        out = []
        for name, state in client.modules.items():
            if state == "installed" and name.startswith(prefix):
                out.append(SimpleNamespace(name=name))
        return out[:limit]

    client.list_installed_modules = _list_installed  # type: ignore[method-assign]

    packet = JobPacket(
        prompt="Community POS stock-first residual none",
        stock_apps=["mail", "contacts", "point_of_sale", "sale", "account", "hr"],
    )
    report = bootstrap_stock(client, packet)
    assert "account" in report.installed or "account" in report.already_installed
    assert "l10n_generic_coa" not in report.installed
    assert not any(
        "Accounting (account) module is not installed" in str(w) for w in report.warnings
    )
    l10n = next(p for p in report.probes if p.name == "l10n")
    assert l10n.ok, l10n.detail


def test_nigeria_brief_defaults_ngn_without_saying_naira() -> None:
    packet = build_job_packet(
        "Quotations and invoices for a trading company in Nigeria.",
        use_llm=False,
    )
    assert packet.country_code == "NG"
    assert packet.currency == "NGN"
    assert packet.l10n_module == "l10n_ng"


def test_bootstrap_writes_country_before_account_and_installs_l10n_ng() -> None:
    client = _BootstrapFake()
    timeline: list[Any] = []
    orig_ensure = client.ensure_module_installed
    orig_exec = client.execute_kw

    def ensure(name: str) -> None:
        timeline.append(("install", name))
        orig_ensure(name)

    def execute_kw(
        model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        if model == "res.company" and method == "write":
            vals = args[1] if len(args) > 1 else {}
            timeline.append(("company_write", vals))
        return orig_exec(model, method, args, kwargs)

    client.ensure_module_installed = ensure  # type: ignore[method-assign]
    client.execute_kw = execute_kw  # type: ignore[method-assign]
    packet = JobPacket(
        prompt="nigeria",
        stock_apps=["mail", "contacts", "sale", "account"],
        l10n_module="l10n_ng",
        country_code="NG",
        currency="NGN",
    )
    with patch("app.job_autopilot.bootstrap.detect_l10n", return_value={"ok": True, "message": "ok"}):
        report = bootstrap_stock(client, packet)
    country_at = next(
        i for i, e in enumerate(timeline) if e[0] == "company_write" and "country_id" in e[1]
    )
    currency_at = next(
        i for i, e in enumerate(timeline) if e[0] == "company_write" and "currency_id" in e[1]
    )
    fiscal_at = next(
        i
        for i, e in enumerate(timeline)
        if e == ("install", "account") or e == ("install", "l10n_ng")
    )
    assert country_at < fiscal_at
    assert currency_at < fiscal_at
    assert client.modules["account"] == "installed"
    assert "account" in report.installed or "account" in report.already_installed
    assert "l10n_ng" in report.installed
    assert "l10n_generic_coa" not in report.skipped


def test_bootstrap_retries_contacts_when_odoo_cron_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.job_autopilot.bootstrap.time.sleep", lambda _s: None)
    client = _BootstrapFake()
    client.modules["contacts"] = "uninstalled"
    client.busy_until["contacts"] = 2
    packet = JobPacket(
        prompt="nigeria",
        stock_apps=["mail", "contacts", "sale", "account"],
        l10n_module="l10n_ng",
        country_code="NG",
        currency="NGN",
    )
    with patch("app.job_autopilot.bootstrap.detect_l10n", return_value={"ok": True, "message": "ok"}):
        report = bootstrap_stock(client, packet)
    assert "contacts" not in report.skipped
    assert "contacts" in report.installed or "contacts" in report.already_installed


def test_bootstrap_reconciles_contacts_pulled_in_by_sale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.job_autopilot.bootstrap.time.sleep", lambda _s: None)
    client = _BootstrapFake()
    client.modules["contacts"] = "uninstalled"
    client.busy_until["contacts"] = 99
    packet = JobPacket(
        prompt="nigeria",
        stock_apps=["mail", "contacts", "sale", "account"],
        l10n_module="l10n_ng",
        country_code="NG",
        currency="NGN",
    )
    with patch("app.job_autopilot.bootstrap.detect_l10n", return_value={"ok": True, "message": "ok"}):
        report = bootstrap_stock(client, packet)
    assert "contacts" not in report.skipped
    assert "contacts" in report.already_installed
    assert not any("Could not install contacts" in w for w in report.warnings)


def test_bootstrap_activates_inactive_country_currency() -> None:
    client = _BootstrapFake()
    client.inactive_currency = "NGN"

    def execute_kw(
        model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        if model == "res.currency" and method == "search":
            ctx = (kwargs or {}).get("context") or {}
            domain = args[0] if args else []
            names = [t[2] for t in domain if isinstance(t, (list, tuple)) and t[0] == "name"]
            code = names[0] if names else ""
            if code == "NGN":
                if ctx.get("active_test") is False:
                    return [15]
                return []
            return [10]
        if model == "res.currency" and method == "write":
            client.writes.append(("currency", args))
            return True
        return _BootstrapFake.execute_kw(client, model, method, args, kwargs)

    client.execute_kw = execute_kw  # type: ignore[method-assign]
    packet = JobPacket(
        prompt="nigeria",
        stock_apps=["mail", "contacts", "sale", "account"],
        l10n_module="l10n_generic_coa",
        country_code="NG",
        currency="NGN",
    )
    with patch("app.job_autopilot.bootstrap.detect_l10n", return_value={"ok": True, "message": "ok"}):
        report = bootstrap_stock(client, packet)
    assert report.currency_id == 15
    assert any(w[0] == "currency" and w[1][1].get("active") is True for w in client.writes)
    company_writes = [w for w in client.writes if w[0] == "company"]
    assert any("currency_id" in (w[1][1] if len(w[1]) > 1 else {}) for w in company_writes)
    currency = next(p for p in report.probes if p.name == "currency")
    assert currency.ok


def test_custom_skips_without_residual() -> None:
    packet = build_job_packet("Quotations and invoices for a trading company.", use_llm=False)
    report = apply_custom_residual(object(), packet)
    assert report.skipped is True


def test_custom_applies_provided_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    packet = build_job_packet(
        "Studio session bookings and invoicing",
        use_llm=False,
    )
    assert packet.has_custom_residual
    applied = SimpleNamespace(
        message="applied",
        models_created=["x_booking"],
        fields_created=3,
        fields_relaxed=1,
        root_menu_id=9,
        open_action_id=8,
        warnings=[],
    )
    monkeypatch.setattr("app.job_autopilot.custom.attach_live_apply_contract", lambda *_a, **_k: [])
    monkeypatch.setattr("app.job_autopilot.custom.apply_module_spec_ui", lambda *_a, **_k: applied)

    def _review(draft, **_k):
        return SimpleNamespace(
            draft=draft, score_before=7.0, score_after=10.0, repairs=["closer"], findings=[]
        )

    monkeypatch.setattr("app.expert.draft_review.review_draft", _review)
    monkeypatch.setattr(
        "app.module_spec_codec.export_draft_module_zip", lambda *_a, **_k: b"PK fake zip"
    )
    spec = {"models": [{"model": "x_booking", "fields": [{"name": "x_name", "ttype": "char"}]}]}
    report = apply_custom_residual(object(), packet, spec=spec)
    assert report.skipped is False
    assert report.models_created == ["x_booking"]
    assert report.fields_relaxed == 1
    assert report.expert_score_after == 10.0
    assert report.zip_base64


def test_seed_residual_spec_filters_pack_to_packet_models() -> None:
    from app.job_autopilot.custom import seed_residual_spec

    packet = JobPacket(
        prompt="Law firm practice management with matters and retainers in Lagos Nigeria",
        domain_label="Law Firm / Legal Practice",
        custom_residuals=[{"key": "matter", "model": "x_matter", "reason": "case file"}],
    )
    spec = seed_residual_spec(packet)
    models = {m["model"] for m in spec["models"]}
    assert "x_matter" in models
    assert "x_matter_party" in models
    assert "x_matter_line" in models
    assert "x_conflict_check" in models
    assert "x_matter_document" in models
    assert "sale.order" in models
    assert "hr.employee" in models
    assert "x_invoice" not in models
    assert "x_client" not in models
    assert "x_bill" not in models
    assert spec.get("_autopilot_seed") is True


def test_clip_spec_to_residuals_drops_pack_siblings() -> None:
    from app.job_autopilot.custom import clip_spec_to_residuals

    packet = JobPacket(
        prompt="matters",
        custom_residuals=[{"key": "matter", "model": "x_matter", "reason": "case file"}],
    )
    spec = {
        "models": [
            {"model": "x_matter", "fields": []},
            {"model": "x_matter_line", "fields": []},
            {"model": "x_matter_party", "fields": []},
            {"model": "x_session", "fields": []},
            {"model": "x_equipment", "fields": []},
        ]
    }
    clipped = clip_spec_to_residuals(spec, packet)
    models = {m["model"] for m in clipped["models"]}
    assert models == {"x_matter", "x_matter_line", "x_matter_party"}
    assert "x_session" in clipped["_autopilot_clipped"]


def test_clip_spec_keeps_pack_floor_and_stock_inherit() -> None:
    from app.ai_domain_pack_law_firm import law_firm_pack
    from app.job_autopilot.custom import clip_spec_to_residuals

    pack = law_firm_pack()
    spec = {
        **pack,
        "models": list(pack["models"]) + [{"model": "x_session", "fields": []}],
    }
    packet = JobPacket(
        prompt="law firm matters",
        custom_residuals=[{"key": "matter", "model": "x_matter", "reason": "case file"}],
    )
    clipped = clip_spec_to_residuals(spec, packet)
    models = {m["model"] for m in clipped["models"]}
    assert "x_matter" in models
    assert "x_conflict_check" in models
    assert "x_matter_document" in models
    assert "sale.order" in models
    assert "hr.employee" in models
    assert "x_session" not in models
    assert "x_bill" not in models


def test_apply_custom_clips_expert_pack_siblings(monkeypatch: pytest.MonkeyPatch) -> None:
    packet = JobPacket(
        prompt="law firm matters",
        custom_residuals=[{"key": "matter", "model": "x_matter", "reason": "case file"}],
    )
    bloated = {
        "technical_name": "law_firm_management",
        "display_name": "Law",
        "depends": ["mail"],
        "models": [
            {"model": "x_matter", "fields": [{"name": "x_name", "ttype": "char"}]},
            {"model": "x_session", "fields": []},
        ],
    }
    captured: dict[str, Any] = {}

    def _apply(_client: Any, spec: dict[str, Any]) -> Any:
        captured["models"] = [m["model"] for m in spec.get("models") or []]
        return SimpleNamespace(
            message="applied",
            models_created=["x_matter"],
            fields_created=1,
            fields_relaxed=0,
            root_menu_id=1,
            open_action_id=2,
            warnings=[],
        )

    monkeypatch.setattr("app.job_autopilot.custom.attach_live_apply_contract", lambda *_a, **_k: [])
    monkeypatch.setattr("app.job_autopilot.custom.apply_module_spec_ui", _apply)
    monkeypatch.setattr(
        "app.expert.draft_review.review_draft",
        lambda draft, **_k: SimpleNamespace(
            draft=bloated, score_before=6.5, score_after=8.4, repairs=[], findings=[]
        ),
    )
    monkeypatch.setattr(
        "app.module_spec_codec.export_draft_module_zip",
        lambda *_a, **_k: b"PK fake",
    )
    report = apply_custom_residual(object(), packet, spec={"models": [{"model": "x_matter"}]})
    assert report.skipped is False
    assert captured["models"] == ["x_matter"]
    assert any("x_session" in w for w in report.warnings)


def test_custom_without_spec_does_not_call_full_app_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    packet = build_job_packet(
        "Recording studio in Lagos Nigeria. Clients book studio sessions. We invoice in naira.",
        use_llm=False,
    )
    applied = SimpleNamespace(
        message="applied",
        models_created=[packet.custom_residuals[0].model],
        fields_created=3,
        fields_relaxed=0,
        root_menu_id=9,
        open_action_id=8,
        warnings=[],
    )
    monkeypatch.setattr("app.job_autopilot.custom.attach_live_apply_contract", lambda *_a, **_k: [])
    monkeypatch.setattr("app.job_autopilot.custom.apply_module_spec_ui", lambda *_a, **_k: applied)
    monkeypatch.setattr(
        "app.expert.draft_review.review_draft",
        lambda draft, **_k: SimpleNamespace(
            draft=draft, score_before=8.0, score_after=9.0, repairs=[], findings=[]
        ),
    )
    monkeypatch.setattr(
        "app.module_spec_codec.export_draft_module_zip", lambda *_a, **_k: b"PK fake zip"
    )

    def _boom(*_a, **_k):
        raise AssertionError("draft_module_from_prompt must not run on Autopilot residual")

    monkeypatch.setattr("app.ai_ollama.draft_module_from_prompt", _boom)
    report = apply_custom_residual(object(), packet)
    assert report.skipped is False
    assert report.models_created
    assert report.spec and report.spec.get("_autopilot_seed") is True


class _SmokeFake:
    def __init__(self) -> None:
        self.models = {
            "res.partner",
            "product.template",
            "product.product",
            "sale.order",
            "sale.order.line",
            "account.move",
            "sale.advance.payment.inv",
            "x_booking",
            "ir.model",
            "ir.actions.server",
        }
        self.fields = {("x_booking", "x_name"), ("x_booking", "x_status")}
        self.required: set[tuple[str, str]] = set()
        self.relations: dict[tuple[str, str], str] = {}
        self._n = 10
        self.writes: list[Any] = []
        self.calls: list[tuple[str, str]] = []
        self.creates: list[tuple[str, dict[str, Any]]] = []
        self.confirm_fails_left = 0

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def field_exists(self, model: str, name: str) -> bool:
        return (model, name) in self.fields

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        self.calls.append((model, method))
        if method == "create":
            payload = args[0] if args else {}
            if isinstance(payload, dict):
                self.creates.append((model, payload))
            self._n += 1
            return self._n
        if method == "write":
            self.writes.append((model, args[0], args[1]))
            return True
        if method == "action_confirm":
            if self.confirm_fails_left > 0:
                self.confirm_fails_left -= 1
                raise RuntimeError("confirm blocked")
            return True
        if method == "create_invoices":
            return [99]
        if method == "_create_invoices":
            return [99]
        if method == "run":
            return True
        if method == "fields_get":
            names = args[0] if args and isinstance(args[0], list) and args[0] else None
            out: dict[str, Any] = {}
            for m, fname in self.fields:
                if m != model:
                    continue
                if names and fname not in names:
                    continue
                ttype = "char"
                relation: str | None = None
                if fname.endswith("_id"):
                    ttype = "many2one"
                    relation = self.relations.get((m, fname), "res.partner")
                elif fname == "x_status":
                    ttype = "selection"
                row: dict[str, Any] = {
                    "type": ttype,
                    "required": (m, fname) in self.required,
                    "readonly": False,
                }
                if relation:
                    row["relation"] = relation
                if ttype == "selection":
                    row["selection"] = [("draft", "Draft"), ("done", "Done")]
                out[fname] = row
            return out
        if method == "search":
            if model == "ir.actions.server":
                return [7]
            if model == "product.product":
                return [22]
            if model == "pos.config":
                return [4]
            return [1]
        if method in {
            "button_confirm",
            "button_validate",
            "action_set_quantities_to_reservation",
            "action_pos_session_open",
            "action_pos_session_closing_control",
            "action_pos_session_close",
            "close_session_from_ui",
        }:
            return True
        if method in {"search_read", "read"}:
            return [{"id": 1, "name": "SO001", "picking_ids": []}]
        return []


def test_process_smoke_extra_apps_are_gated() -> None:
    client = _SmokeFake()
    client.models.update(
        {"purchase.order", "pos.config", "pos.session", "crm.lead", "stock.picking", "crm.stage"}
    )
    client.fields.add(("crm.lead", "probability"))
    packet = JobPacket(
        prompt="buy and sell",
        stock_apps=["sale", "account", "purchase", "point_of_sale", "crm"],
    )
    report = run_process_smoke(client, packet)
    names = {s.name for s in report.steps}
    assert "purchase.order" in names
    assert "purchase.order.receipt" in names
    assert "pos.config" in names
    assert "pos.session" in names
    assert "crm.lead" in names
    assert "crm.lead.won" in names
    pos_step = next(s for s in report.steps if s.name == "pos.session")
    assert pos_step.ok
    assert "closed" in (pos_step.detail or "").lower() or "close" in (pos_step.detail or "").lower()


def test_process_smoke_stock_and_custom() -> None:
    packet = JobPacket(
        prompt="bookings",
        stock_apps=["sale", "account"],
        custom_residuals=[{"key": "booking", "model": "x_booking", "reason": "session"}],
    )
    report = run_process_smoke(_SmokeFake(), packet)
    assert report.ok
    names = [s.name for s in report.steps]
    assert "partner" in names
    assert "sale.order" in names
    assert "sale.order.action_confirm" in names
    assert "sale.advance.payment.inv.create_invoices" in names
    assert "x_booking.create" in names
    assert "x_booking.confirm_action" in names
    assert "x_booking.x_status" not in names
    assert report.named_process == "quote_to_invoice"
    assert report.invoice_id == 99
    assert report.open_model == "account.move"
    assert report.open_id == 99


def test_custom_smoke_fills_required_m2o_by_relation() -> None:
    client = _SmokeFake()
    client.models.add("x_visit")
    client.fields.update(
        {
            ("x_visit", "x_name"),
            ("x_visit", "x_patient_id"),
            ("x_visit", "x_sku_id"),
            ("x_visit", "x_optional_id"),
            ("x_visit", "x_status"),
        }
    )
    client.required.update({("x_visit", "x_patient_id"), ("x_visit", "x_sku_id")})
    client.relations[("x_visit", "x_patient_id")] = "res.partner"
    client.relations[("x_visit", "x_sku_id")] = "product.product"
    client.relations[("x_visit", "x_optional_id")] = "res.partner"
    packet = JobPacket(
        prompt="clinic visits",
        stock_apps=["sale", "account"],
        custom_residuals=[{"key": "visit", "model": "x_visit", "reason": "encounter"}],
    )
    report = run_process_smoke(client, packet)
    assert any(s.name == "x_visit.create" and s.ok for s in report.steps)
    visit_vals = [vals for model, vals in client.creates if model == "x_visit"]
    assert visit_vals
    assert visit_vals[0].get("x_patient_id") == report.partner_id
    assert visit_vals[0].get("x_sku_id") == 22
    assert "x_optional_id" not in visit_vals[0]


def test_custom_smoke_line_parent_by_header_relation() -> None:
    from app.job_autopilot.smoke import _line_parent_field

    client = _SmokeFake()
    client.models.add("x_visit_line")
    client.fields.add(("x_visit_line", "x_encounter_id"))
    client.relations[("x_visit_line", "x_encounter_id")] = "x_visit"
    assert _line_parent_field(client, "x_visit", "x_visit_line") == "x_encounter_id"


def test_executor_refuses_production() -> None:
    conn = SimpleNamespace(id="c1", write_mode="production", url="https://erp.example.com")
    result = run_autopilot_job(client=object(), connection=conn, prompt="sell widgets")
    assert result.refused is True
    assert result.ok is False
    assert result.promote_ready is False


def test_executor_sandbox_stock_only_smoke() -> None:
    conn = SimpleNamespace(id="c1", write_mode="standard", url="http://127.0.0.1:8069")
    client = _SmokeFake()
    packet = JobPacket(prompt="invoices", stock_apps=["sale", "account"])
    with patch("app.job_autopilot.executor.bootstrap_stock") as boot:
        boot.return_value = SimpleNamespace(message="ok")
        result = run_autopilot_job(
            client=client,
            connection=conn,
            prompt="invoices",
            packet=packet,
        )
    assert result.refused is False
    assert result.sandbox is True
    assert result.custom and result.custom.skipped
    assert result.smoke and result.smoke.ok
    assert result.promote_ready is True
    assert "smoke" in result.stages
    assert result.config_packet
    assert result.config_packet.get("secrets_excluded") is True


def test_packet_endpoint_json() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    fake = SimpleNamespace(write_mode="standard", url="http://127.0.0.1:8069")
    with patch("app.routers.job_autopilot.get_connection_or_404", return_value=fake):
        with TestClient(app) as c:
            res = c.post(
                "/api/connections/c1/job-autopilot/packet",
                json={
                    "prompt": "Sell products and invoice in Germany. Customers book studio sessions.",
                    "use_llm": False,
                },
            )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sandbox"] is True
    models = [r["model"] for r in body["packet"]["custom_residuals"]]
    assert "x_booking" in models
    assert body["packet"]["country_code"] == "DE"


def test_run_endpoint_refuses_production() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    fake = SimpleNamespace(
        id="c1", write_mode="production", url="https://erp.example.com"
    )
    with patch("app.routers.job_autopilot.get_connection_or_404", return_value=fake):
        with TestClient(app) as c:
            res = c.post(
                "/api/connections/c1/job-autopilot/run",
                json={
                    "prompt": "invoice customers",
                    "confirm_advanced": True,
                    "confirm_phrase": CONFIRM_PHRASE,
                },
            )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["refused"] is True
    assert body["ok"] is False


def test_run_endpoint_queues_sandbox() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    fake = SimpleNamespace(id="c1", write_mode="standard", url="http://127.0.0.1:8069")
    with patch("app.routers.job_autopilot.get_connection_or_404", return_value=fake):
        with patch("app.routers.job_autopilot.find_in_flight_job", return_value=None):
            with patch(
                "app.routers.job_autopilot.create_job",
                return_value=SimpleNamespace(id="job-ap-1"),
            ):
                with patch("app.routers.job_autopilot.enqueue") as enqueued:
                    with TestClient(app) as c:
                        res = c.post(
                            "/api/connections/c1/job-autopilot/run",
                            json={"prompt": "invoice customers", "use_llm": False},
                        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["queued"] is True
    assert body["job_id"] == "job-ap-1"
    enqueued.assert_called_once()


def test_run_endpoint_attaches_in_flight_job() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    fake = SimpleNamespace(id="c1", write_mode="standard", url="http://127.0.0.1:8069")
    running = SimpleNamespace(id="job-already", status="running")
    with patch("app.routers.job_autopilot.get_connection_or_404", return_value=fake):
        with patch("app.routers.job_autopilot.find_in_flight_job", return_value=running):
            with patch("app.routers.job_autopilot.create_job") as created:
                with patch("app.routers.job_autopilot.enqueue") as enqueued:
                    with TestClient(app) as c:
                        res = c.post(
                            "/api/connections/c1/job-autopilot/run",
                            json={"prompt": "invoice customers", "use_llm": False},
                        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["job_id"] == "job-already"
    assert body["queued"] is True
    created.assert_not_called()
    enqueued.assert_not_called()


def test_persist_autopilot_job_payload_strips_zip(tmp_path, monkeypatch) -> None:
    from app.job_autopilot.artifacts import (
        load_autopilot_zip_artifact,
        persist_autopilot_job_payload,
        strip_zip_fields,
    )

    monkeypatch.setattr("app.job_autopilot.artifacts._cache_dir", lambda: tmp_path)
    slim = persist_autopilot_job_payload(
        "job-z",
        {
            "ok": True,
            "custom": {"zip_base64": "UEsDBAQAAAAA", "elite": {"zip_base64": "ZWxpdGU="}},
        },
    )
    assert slim["custom"].get("zip_base64") is None
    assert slim["custom"]["zip_omitted"] is True
    art = load_autopilot_zip_artifact("job-z")
    assert art["zip_base64"] == "UEsDBAQAAAAA"
    assert art["elite_zip_base64"] == "ZWxpdGU="
    stripped = strip_zip_fields({"custom": {"zip_base64": "A" * 100}})
    assert "zip_base64" not in stripped["custom"]
    assert stripped["custom"]["zip_omitted"] is True


def test_ingest_auto_commits_on_sandbox() -> None:
    from app.job_autopilot.ingest_bridge import ingest_job_files

    packet = JobPacket(
        prompt="customers",
        data_files=[{"filename": "customers.csv", "doc_type": "customer_list", "confidence": 0.9}],
    )
    files = [("customers.csv", b"name,email\nAda,a@x.com\n", "text/csv")]
    table = SimpleNamespace(
        model="res.partner",
        rows=[SimpleNamespace(flags=[]), SimpleNamespace(flags=[])],
    )
    batch = SimpleNamespace(
        files=[SimpleNamespace(needs_user_confirm=False)],
        plan=None,
        gaps=[],
        status="dry_run",
        tables=[table],
        refs=[],
    )
    committed = SimpleNamespace(
        files=batch.files,
        plan=None,
        gaps=[],
        status="committed",
        tables=[table],
        refs=[],
        commit_log=SimpleNamespace(created=2, updated=0),
    )
    job_row = SimpleNamespace(id="ing-1")

    with (
        patch("app.job_autopilot.ingest_bridge.create_job", return_value=(job_row, {})),
        patch("app.job_autopilot.ingest_bridge.run_pipeline", side_effect=[batch, committed]) as pipe,
    ):
        report = ingest_job_files(
            object(),  # type: ignore[arg-type]
            object(),
            packet,
            files,
            connection_id="c1",
            allow_commit=True,
        )
    assert report.committed is True
    assert report.ingest_job_id == "ing-1"
    assert report.source_rows == 2
    assert report.loaded_rows == 2
    assert pipe.call_count == 2
    assert pipe.call_args_list[0].kwargs["through"] == "dry_run"
    assert pipe.call_args_list[1].kwargs["through"] == "commit"


def test_ingest_skips_commit_without_allow() -> None:
    from app.job_autopilot.ingest_bridge import ingest_job_files

    packet = JobPacket(prompt="customers")
    batch = SimpleNamespace(files=[SimpleNamespace(needs_user_confirm=False)], plan=None, gaps=[], status="dry_run")
    with (
        patch("app.job_autopilot.ingest_bridge.create_job", return_value=(SimpleNamespace(id="ing-2"), {})),
        patch("app.job_autopilot.ingest_bridge.run_pipeline", return_value=batch) as pipe,
    ):
        report = ingest_job_files(
            object(),  # type: ignore[arg-type]
            object(),
            packet,
            [("customers.csv", b"name\nAda\n", "text/csv")],
            connection_id="c1",
            allow_commit=False,
        )
    assert report.committed is False
    assert report.dry_run_only is True
    assert pipe.call_count == 1


def test_ingest_blocks_on_gaps() -> None:
    from app.job_autopilot.ingest_bridge import ingest_job_files

    packet = JobPacket(prompt="coa")
    batch = SimpleNamespace(
        files=[SimpleNamespace(needs_user_confirm=False)],
        plan=SimpleNamespace(gaps=["CoA codes unmatched"]),
        gaps=[],
        status="dry_run",
    )
    with (
        patch("app.job_autopilot.ingest_bridge.create_job", return_value=(SimpleNamespace(id="ing-3"), {})),
        patch("app.job_autopilot.ingest_bridge.run_pipeline", return_value=batch) as pipe,
    ):
        report = ingest_job_files(
            object(),  # type: ignore[arg-type]
            object(),
            packet,
            [("coa.csv", b"code,name\n1000,Cash\n", "text/csv")],
            connection_id="c1",
            allow_commit=True,
        )
    assert report.committed is False
    assert "unmatched" in " ".join(report.gaps).lower() or "gap" in report.message.lower()
    assert pipe.call_count == 1
    assert any("unmatched" in m.lower() for m in report.unmatched_m2o)


def test_org_emails_from_excerpts() -> None:
    packet = build_job_packet(
        "We invoice customers.",
        file_excerpts=[("org.csv", "name,email\nAda,ada@studio.ng\nBola,bola@studio.ng\n")],
        use_llm=False,
    )
    assert "ada@studio.ng" in packet.org_emails
    assert "bola@studio.ng" in packet.org_emails


def test_client_doc_index_jaccard_not_pack_rag(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.job_autopilot import client_index

    monkeypatch.setattr(client_index, "_cache_dir", lambda: tmp_path)
    n = client_index.upsert_client_docs(
        "conn-idx",
        [("sop.md", "Studio session booking SOP. Clients book rooms. Invoice after the session.")],
    )
    assert n >= 1
    hits = client_index.retrieve_grounding("conn-idx", "booking session invoice")
    assert hits
    assert "sop.md" in hits[0]


def test_job_scorecard_smoke_fail_is_not_golive() -> None:
    from app.job_autopilot.packet import AutopilotResult, SmokeReport
    from app.job_autopilot.scorecard import score_job

    packet = JobPacket(prompt="sell", stock_apps=["sale", "account"])
    result = AutopilotResult(
        packet=packet,
        smoke=SmokeReport(ok=False, message="failed"),
        sandbox=True,
        connection_kind="sandbox",
    )
    card = score_job(result)
    assert card.process_smoke == 0.0
    assert card.overall == 0.0
    assert any("not go-live" in f.lower() or "failed" in f.lower() for f in card.findings)


def test_scorecard_no_client_files_is_not_ten() -> None:
    from app.job_autopilot.packet import AutopilotResult, BootstrapReport, SmokeReport
    from app.job_autopilot.scorecard import score_job

    packet = JobPacket(prompt="sell", stock_apps=["sale", "account"])
    result = AutopilotResult(
        packet=packet,
        sandbox=True,
        smoke=SmokeReport(ok=True, named_process="quote_to_invoice", message="ok"),
        bootstrap=BootstrapReport(already_installed=["sale"], probes=[]),
    )
    card = score_job(result)
    assert card.data_load == 7.0
    assert any("scored 7" in f for f in card.findings)


def test_law_firm_packet_omits_inventory_stock() -> None:
    packet = build_job_packet(
        "Adeyemi, Okonkwo & Partners law firm in Lagos. Matters and retainers on "
        "Paystack. WhatsApp for client intake. PAYE payroll for associates.",
        use_llm=False,
    )
    assert "stock" not in packet.stock_apps
    assert "inbound_orders" not in packet.connectors
    assert any(r.model == "x_matter" for r in packet.custom_residuals)


def test_law_firm_brief_negates_marketplace_and_inventory() -> None:
    packet = build_job_packet(
        "Adeyemi law firm. Stock apps cover CRM, Project, Sales, Accounting. "
        "Quotations, sales orders, and customer invoices are stock Odoo documents. "
        "No third-party food marketplace. No shop-floor or kitchen hardware. "
        "Paystack, WhatsApp, PAYE payroll. Custom residual is the matter file only.",
        use_llm=False,
    )
    assert "stock" not in packet.stock_apps
    assert "inbound_orders" not in packet.connectors
    assert "hardware" not in packet.connectors
    assert packet.connectors == ["payments", "messaging", "statutory_payroll"]


def test_parse_brief_master_data_extracts_aop_clients() -> None:
    from app.job_autopilot.demo_seed import parse_brief_master_data

    parsed = parse_brief_master_data(
        "Clients: Northern Harvest Ltd; Rivers Marine Services; Adaeze Nwosu.\n"
        "Matters: “NH-LIT-014 share dispute”; “RMS-COR-003 shareholders’ agreement”.\n"
        "Products / fee types: Retainer (service), Hourly advisory (service), Disbursement (service).\n"
    )
    assert "Northern Harvest Ltd" in parsed["clients"]
    assert "Rivers Marine Services" in parsed["clients"]
    assert any("share dispute" in m for m in parsed["matters"])
    assert any("Retainer" in p for p in parsed["products"])


def test_probe_leftover_stock_form_fields_names_invoice_x_star() -> None:
    from app.job_autopilot.demo_seed import probe_leftover_stock_form_fields

    class Fake:
        def execute_kw(self, model, method, args, kwargs=None):
            assert model == "ir.model.fields"
            assert method == "search_read"
            return [
                {"name": "x_payment_url", "model": "account.move"},
                {"name": "x_qr_payload", "model": "account.move"},
                {"name": "x_demo_note", "model": "account.move"},
            ]

    probes = probe_leftover_stock_form_fields(Fake())
    assert len(probes) == 1
    assert probes[0].name == "sandbox_form"
    assert "x_payment_url" in probes[0].detail
    assert "x_demo_note" in probes[0].detail
    assert "not stock Community" in probes[0].detail
    assert "or Pay" in probes[0].detail


def test_probe_leftover_stock_form_fields_clean() -> None:
    from app.job_autopilot.demo_seed import probe_leftover_stock_form_fields

    class Fake:
        def execute_kw(self, model, method, args, kwargs=None):
            return []

    probes = probe_leftover_stock_form_fields(Fake())
    assert probes[0].detail.startswith("Stock invoice/quotation forms have no leftover")


def test_report_pdf_is_real_pdf() -> None:
    from app.job_autopilot.packet import AutopilotResult
    from app.job_autopilot.report import render_markdown, render_pdf_bytes

    result = AutopilotResult(
        packet=JobPacket(prompt="sell widgets", stock_apps=["sale"]),
        sandbox=True,
        connection_kind="sandbox",
        message="ok",
    )
    pdf = render_pdf_bytes(render_markdown(result))
    assert pdf.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf


def test_promote_to_refuses_same_connection_and_missing_zip() -> None:
    from app.job_autopilot.promote_target import promote_to_connection

    db = object()
    same = promote_to_connection(
        db,  # type: ignore[arg-type]
        source_connection_id="c1",
        target_connection_id="c1",
        zip_base64="UEs=",
    )
    assert same.refused is True
    missing = promote_to_connection(
        db,  # type: ignore[arg-type]
        source_connection_id="c1",
        target_connection_id="c2",
        zip_base64=None,
    )
    assert missing.refused is True
    assert "zip" in (missing.refuse_reason or "").lower()


def test_promote_to_endpoint_requires_confirm() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    fake = SimpleNamespace(id="c1", write_mode="standard", url="http://127.0.0.1:8069")
    with (
        patch("app.routers.job_autopilot.get_connection_or_404", return_value=fake),
        patch("app.job_autopilot.promote_target.get_connection_or_404", return_value=fake),
    ):
        with TestClient(app) as c:
            res = c.post(
                "/api/connections/c1/job-autopilot/promote-to",
                json={"target_connection_id": "c2", "zip_base64": "UEs="},
            )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body["detail"]["requires_confirmation"] is True


def test_find_confirm_prefers_open_over_billed() -> None:
    from app.job_autopilot.smoke import _find_confirm_action

    class Fake:
        def execute_kw(self, model, method, args, kwargs=None):
            if model == "ir.model" and method == "search":
                return [3]
            if model == "ir.actions.server" and method == "search":
                domain = args[0] if args else []
                flat = str(domain)
                if "Confirm" in flat or "= open" in flat or "open" in flat.lower():
                    return [11, 22]
                if "set" in flat.lower():
                    return [22, 11]
                return []
            if model == "ir.actions.server" and method == "read":
                return [
                    {"id": 22, "name": "x_matter: set x_status = billed"},
                    {"id": 11, "name": "x_matter: set x_status = open"},
                ]
            return []

    assert _find_confirm_action(Fake(), "x_matter") == 11


def test_find_confirm_refuses_billed_only() -> None:
    from app.job_autopilot.smoke import _find_confirm_action

    class Fake:
        def execute_kw(self, model, method, args, kwargs=None):
            if model == "ir.model" and method == "search":
                return [3]
            if model == "ir.actions.server" and method == "search":
                domain = args[0] if args else []
                flat = str(domain).lower()
                # Exact / open lookups find nothing — only a billed write exists
                if "open" in flat or "confirm" in flat or "confirmed" in flat:
                    return []
                return [22]
            if model == "ir.actions.server" and method == "read":
                return [{"id": 22, "name": "x_matter: set x_status = billed"}]
            return []

    assert _find_confirm_action(Fake(), "x_matter") is None


def test_executor_retries_then_passes() -> None:
    conn = SimpleNamespace(id="c1", write_mode="standard", url="http://127.0.0.1:8069")
    client = _SmokeFake()
    client.confirm_fails_left = 2
    packet = JobPacket(prompt="invoices", stock_apps=["sale", "account"])
    with patch("app.job_autopilot.executor.bootstrap_stock") as boot:
        boot.return_value = SimpleNamespace(
            message="ok",
            probes=[],
            installed=["sale"],
            already_installed=[],
            skipped=[],
            warnings=[],
            recipe_version=1,
        )
        result = run_autopilot_job(
            client=client,
            connection=conn,
            prompt="invoices",
            packet=packet,
        )
    assert result.smoke and result.smoke.ok
    assert result.retry_count == 2
    assert result.job_scorecard is not None
    assert result.job_scorecard.process_smoke == 10.0
    assert result.report_markdown
    assert result.walkthrough_seeded is False


def test_smoke_retry_reapplies_without_expert() -> None:
    from app.job_autopilot.packet import CustomApplyReport

    conn = SimpleNamespace(id="c1", write_mode="standard", url="http://127.0.0.1:8069")
    client = _SmokeFake()
    client.confirm_fails_left = 1
    spec = {"models": [{"name": "x_booking"}]}
    packet = JobPacket(
        prompt="bookings",
        stock_apps=["sale", "account"],
        custom_residuals=[{"key": "booking", "model": "x_booking", "reason": "session"}],
    )
    report = CustomApplyReport(spec=spec, skipped=False)
    with (
        patch("app.job_autopilot.executor.bootstrap_stock") as boot,
        patch("app.job_autopilot.executor.run_connectors") as conn_run,
        patch("app.job_autopilot.executor.apply_custom_residual", return_value=report) as apply,
    ):
        boot.return_value = SimpleNamespace(
            message="ok",
            probes=[],
            installed=["sale"],
            already_installed=[],
            skipped=[],
            warnings=[],
            recipe_version=1,
        )
        conn_run.return_value = SimpleNamespace(
            ok=True,
            skipped=True,
            ran=[],
            failed=[],
            skipped_ids=[],
            steps=[],
            warnings=[],
            message="skip",
        )
        result = run_autopilot_job(
            client=client,
            connection=conn,
            prompt="bookings",
            packet=packet,
            spec=spec,
        )
    assert result.smoke and result.smoke.ok
    assert apply.call_count == 2
    assert apply.call_args_list[0].kwargs.get("skip_expert", False) is False
    assert apply.call_args_list[1].kwargs.get("skip_expert") is True


def test_live_odoo19_quote_to_invoice_smoke() -> None:
    if os.environ.get("ODOO_LIVE_AUTOPILOT", "1") == "0":
        pytest.skip("ODOO_LIVE_AUTOPILOT=0")
    from odoo_client import ConnectionConfig, OdooClient
    from odoo_client.client import OdooClientError

    config = ConnectionConfig(
        url=os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
        db=os.environ.get("ODOO_DB", "odoo_dev"),
        username=os.environ.get("ODOO_USER", "admin"),
        password=os.environ.get("ODOO_PASSWORD", "admin"),
    )
    client = OdooClient(config)
    try:
        client.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 19 not reachable: {exc}")
    if not str(client.server_version().get("server_version", "")).startswith("19"):
        pytest.skip("Expected Odoo 19")
    if not client.model_exists("sale.order"):
        pytest.skip("sale.order not installed — live Autopilot smoke needs Sales")
    packet = JobPacket(
        prompt="quotations and invoices",
        stock_apps=["sale", "account"],
        processes=["quote_to_invoice"],
    )
    report = run_process_smoke(client, packet)
    assert report.ok, f"{report.message} steps={[(s.name, s.ok, s.detail) for s in report.steps]}"
    names = [s.name for s in report.steps]
    assert "sale.order.action_confirm" in names
    assert "sale.advance.payment.inv.create_invoices" in names

