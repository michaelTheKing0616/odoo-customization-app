"""GND-MOD: offer the stock app, install through module.install, continue.

Fake Odoo ports and fixture schema clients only. No live Odoo, no live model.
The fixture database starts with only ``base`` installed.
"""

from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.ai_schema_client import FakeSchemaClient  # noqa: E402
from app.live_schema_context import build_schema_packet, empty_schema_packet  # noqa: E402
from app.stock_app_install import (  # noqa: E402
    STOCK_APPS,
    InstallFacts,
    install_stock_app,
    match_stock_app,
    proposal_for,
    propose_stock_app_install,
    stock_app_clarification,
    stock_app_for_model,
)

PROMPT = "Add a PO reference field on quotations"
SALES_QUESTION = (
    "Your request edits quotations, which come from the Sales app. Install Sales to continue?"
)

_MODULE_IDS = {
    "base": 1,
    "sale": 41,
    "purchase": 42,
    "account": 43,
    "stock": 44,
    "crm": 45,
    "project": 46,
    "hr": 47,
    "mrp": 48,
    "point_of_sale": 49,
    "calendar": 50,
}
_PROVIDES = {
    "sale": ("sale.order",),
    "purchase": ("purchase.order",),
    "account": ("account.move",),
    "stock": ("stock.picking",),
    "crm": ("crm.lead",),
    "project": ("project.task", "project.project"),
    "hr": ("hr.employee",),
    "mrp": ("mrp.production",),
    "point_of_sale": ("pos.order",),
    "calendar": ("calendar.event",),
}


class BaseOnlyOdoo:
    """Fake port for a fresh database with only ``base`` installed."""

    def __init__(self, *, fail_install: str | None = None) -> None:
        self.models = {"res.partner", "res.users", "ir.model"}
        self.state = {name: "uninstalled" for name in _MODULE_IDS}
        self.state["base"] = "installed"
        self.calls: list[tuple[str, str, list]] = []
        self.fail_install = fail_install

    def create(self, model: str, values: dict) -> int:  # pragma: no cover - never used
        raise AssertionError(("create", model, values))

    def write(self, model: str, ids: list[int], values: dict) -> None:  # pragma: no cover
        raise AssertionError(("write", model, ids, values))

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None):
        self.calls.append((model, method, args))
        if model == "ir.model" and method == "search_count":
            name = args[0][0][2]
            return 1 if name in self.models else 0
        if model == "ir.module.module" and method == "search_read":
            field, _, value = args[0][0]
            if field == "name":
                if value not in self.state:
                    return []
                return [{"id": _MODULE_IDS[value], "state": self.state[value]}]
            if field == "state":
                return [{"name": n} for n, s in sorted(self.state.items()) if s == value]
        if model == "ir.module.module" and method == "button_immediate_install":
            if self.fail_install:
                raise RuntimeError(self.fail_install)
            module_id = args[0][0]
            name = next(n for n, i in _MODULE_IDS.items() if i == module_id)
            self.state[name] = "installed"
            self.models.update(_PROVIDES.get(name, ()))
            return {"type": "ir.actions.client", "tag": "reload"}
        raise AssertionError((model, method, args))

    def methods_called(self) -> list[str]:
        return [method for _, method, _ in self.calls]


# --- map ----------------------------------------------------------------------


@pytest.mark.no_app_db
@pytest.mark.parametrize(
    ("model", "module"),
    [
        ("sale.order", "sale"),
        ("purchase.order", "purchase"),
        ("account.move", "account"),
        ("stock.picking", "stock"),
        ("crm.lead", "crm"),
        ("project.task", "project"),
        ("hr.employee", "hr"),
        ("mrp.production", "mrp"),
        ("pos.order", "point_of_sale"),
    ],
)
def test_map_missing_model_to_community_module(model: str, module: str) -> None:
    app = stock_app_for_model(model)
    assert app is not None and app.module == module and app.edition == "community"


@pytest.mark.no_app_db
@pytest.mark.parametrize(
    ("prompt", "module", "model", "noun"),
    [
        (PROMPT, "sale", "sale.order", "quotations"),
        (
            "Add a vendor reference on purchase orders",
            "purchase",
            "purchase.order",
            "purchase orders",
        ),
        ("Show a project code on invoices", "account", "account.move", "invoices"),
        ("Add a dock number on delivery orders", "stock", "stock.picking", "delivery orders"),
        ("Track a referral source on leads", "crm", "crm.lead", "leads"),
        ("Add a budget code on tasks", "project", "project.task", "tasks"),
        ("Add a badge colour on employees", "hr", "hr.employee", "employees"),
        (
            "Add a batch number on manufacturing orders",
            "mrp",
            "mrp.production",
            "manufacturing orders",
        ),
        ("Add a table number on POS orders", "point_of_sale", "pos.order", "pos orders"),
    ],
)
def test_map_user_words_to_app_without_asking(
    prompt: str, module: str, model: str, noun: str
) -> None:
    match = match_stock_app(prompt)
    assert match is not None
    assert (match.app.module, match.model, match.noun) == (module, model, noun)


@pytest.mark.no_app_db
def test_locked_host_wins_over_words() -> None:
    match = match_stock_app("Add a PO link on quotations", host_model="purchase.order")
    assert match is not None and match.app.module == "purchase"


@pytest.mark.no_app_db
def test_present_model_or_installed_module_needs_no_proposal() -> None:
    match = match_stock_app(PROMPT)
    assert match is not None
    assert proposal_for(match, InstallFacts(model_present=True, module_state="installed")) is None
    assert proposal_for(match, InstallFacts(model_present=False, module_state="installed")) is None


@pytest.mark.no_app_db
def test_enterprise_only_app_is_explained_not_offered_on_community() -> None:
    match = match_stock_app("Add an SLA tier on helpdesk tickets")
    assert match is not None and match.app.module == "helpdesk"
    proposal = proposal_for(match, InstallFacts(model_present=False, module_state=None, edition="community"))
    assert proposal is not None
    assert proposal.installable is False
    assert "Enterprise" in proposal.question
    clar = stock_app_clarification(proposal)
    assert [opt["id"] for opt in clar["options"]] == ["decline"]
    port = BaseOnlyOdoo()
    outcome = install_stock_app(port, proposal)
    assert outcome.ok is False
    assert port.calls == []


@pytest.mark.no_app_db
def test_module_the_server_cannot_install_is_not_offered() -> None:
    match = match_stock_app(PROMPT)
    assert match is not None
    for state in (None, "uninstallable"):
        proposal = proposal_for(match, InstallFacts(model_present=False, module_state=state))
        assert proposal is not None and proposal.installable is False


@pytest.mark.no_app_db
def test_map_never_offers_uninstall_or_a_generated_zip() -> None:
    assert all(app.module.isidentifier() for app in STOCK_APPS)
    port = BaseOnlyOdoo()
    proposal = propose_stock_app_install(PROMPT, port)
    assert proposal is not None
    install_stock_app(port, proposal)
    methods = port.methods_called()
    assert "button_immediate_uninstall" not in methods
    assert not any("zip" in str(call).lower() for call in port.calls)


@pytest.mark.no_app_db
def test_install_runs_module_install_op_and_errors_are_one_sentence() -> None:
    port = BaseOnlyOdoo()
    proposal = propose_stock_app_install(PROMPT, port)
    assert proposal is not None
    outcome = install_stock_app(port, proposal)
    assert outcome.ok and outcome.module == "sale" and outcome.module_id == 41
    assert any("uninstall" in w for w in outcome.warnings)
    assert ("ir.module.module", "button_immediate_install", [[41]]) in port.calls

    broken = BaseOnlyOdoo(
        fail_install="Traceback (most recent call last):\n  File odoo/...\nKeyError"
    )
    outcome = install_stock_app(broken, proposal)
    assert outcome.ok is False
    assert "Traceback" not in outcome.message and "\n" not in outcome.message
    assert outcome.message.startswith("Sales")


@pytest.mark.no_app_db
def test_install_refuses_a_module_outside_the_map_before_any_port_call() -> None:
    port = BaseOnlyOdoo()
    outcome = install_stock_app(
        port, {"module": "my_generated_zip", "app_label": "Mine", "installable": True}
    )
    assert outcome.ok is False and port.calls == []


@pytest.mark.no_app_db
def test_read_failure_degrades_to_no_proposal() -> None:
    class Down:
        def execute_kw(self, *args, **kwargs):
            raise ConnectionError("refused")

    assert propose_stock_app_install(PROMPT, Down()) is None
    assert propose_stock_app_install(PROMPT, None) is None


@pytest.mark.no_app_db
def test_expert_uses_the_same_map_and_copy() -> None:
    from app.expert.live_schema_ask import _stock_app_install_hint

    packet = empty_schema_packet(server_version="19.0", major=19)
    hint = _stock_app_install_hint("Is there a PO reference on quotations?", packet, "sale.order")
    assert hint is not None
    module, text = hint
    assert module == "sale"
    assert "Sales is not installed" in text and "App Studio can install Sales" in text


# --- App Studio routes ----------------------------------------------------------


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch):
    from app.db import init_db
    from app.main import app
    from app.settings import settings

    monkeypatch.setattr(settings, "ai_intent_llm", "off", raising=False)
    monkeypatch.setattr("app.llm_provider.get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr("app.llm_provider.get_llm_provider_for_tier", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.ai_studio.get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.ai_studio.get_llm_provider_for_tier", lambda *a, **k: None)
    init_db()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def connection_id() -> str:
    from app.crypto import encrypt_secret
    from app.db import SessionLocal
    from app.db_models import OdooConnection

    db = SessionLocal()
    try:
        row = OdooConnection(
            name="gnd-mod-base-only",
            url="http://127.0.0.1:9",
            db_name=f"gndmod-{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


@pytest.fixture
def fake_odoo(monkeypatch: pytest.MonkeyPatch) -> BaseOnlyOdoo:
    port = BaseOnlyOdoo()
    monkeypatch.setattr("app.routers.ai_studio._open_stock_app_port", lambda conn: port)
    return port


@pytest.fixture
def rereads(monkeypatch: pytest.MonkeyPatch, fake_odoo: BaseOnlyOdoo) -> list[dict]:
    """Record schema packet builds; build them from the fake database's live models."""
    seen: list[dict] = []

    def _packet(connection, *, prompt, host=None, available=None, **_kw):
        if connection is None:
            return None
        seen.append(
            {
                "host": host,
                "installed": list(getattr(connection, "installed_modules", None) or []),
                "models": sorted(fake_odoo.models),
            }
        )
        client = FakeSchemaClient(
            models=set(fake_odoo.models),
            fields={
                "sale.order": {
                    "partner_id": {"type": "many2one", "relation": "res.partner"},
                    "name": {"type": "char"},
                }
            },
        )
        return build_schema_packet(
            SimpleNamespace(id="fake", server_version="19.0", odoo_major=19),
            models=[host or "sale.order"],
            schema_client=client,
        )

    monkeypatch.setattr("app.routers.ai_studio._studio_schema_packet", _packet)
    return seen


def _create(api: TestClient, connection_id: str) -> dict:
    res = api.post("/api/ai/sessions", json={"prompt": PROMPT, "connection_id": connection_id})
    assert res.status_code == 200, res.text
    return res.json()


def test_quotation_field_on_base_only_db_proposes_sales_with_reason(
    api: TestClient, connection_id: str, fake_odoo: BaseOnlyOdoo, rereads: list
) -> None:
    out = _create(api, connection_id)
    clar = out["clarification"]
    assert out["status"] == "clarifying"
    assert clar["kind"] == "stock_app_install"
    assert clar["question"] == SALES_QUESTION
    assert "Sales is not installed" in clar["help"]
    assert clar["stock_app"]["module"] == "sale"
    assert [o["label"] for o in clar["options"]] == ["Install Sales and continue", "Not now"]
    assert "button_immediate_install" not in fake_odoo.methods_called()


def test_user_is_never_asked_to_name_the_app(
    api: TestClient, connection_id: str, fake_odoo: BaseOnlyOdoo, rereads: list
) -> None:
    out = _create(api, connection_id)
    clar = out["clarification"]
    assert "host_choices" not in clar
    assert {o["id"] for o in clar["options"]} <= {"install", "decline"}
    assert "which app" not in clar["question"].lower()
    res = api.post(
        f"/api/ai/sessions/{out['id']}/stock-app",
        json={"decision": "install", "module": "crm"},
    )
    assert res.status_code == 200, res.text
    assert fake_odoo.state["sale"] == "installed"
    assert fake_odoo.state["crm"] == "uninstalled"


def test_approve_installs_sale_rereads_schema_and_continues_same_session(
    api: TestClient, connection_id: str, fake_odoo: BaseOnlyOdoo, rereads: list
) -> None:
    created = _create(api, connection_id)
    res = api.post(f"/api/ai/sessions/{created['id']}/stock-app", json={"decision": "install"})
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["id"] == created["id"]
    assert out["prompt_original"] == PROMPT
    assert ("ir.module.module", "button_immediate_install", [[41]]) in fake_odoo.calls
    assert out["installed"]["module"] == "sale"
    assert rereads and rereads[-1]["host"] == "sale.order"
    assert "sale" in rereads[-1]["installed"]
    assert "sale.order" in out["schema_reread"]["models"]
    assert out["status"] == "clarifying"
    pending = out.get("pending_clarification") or {}
    assert pending.get("kind") == "diagnosis"
    assert (pending.get("understanding") or {}).get("host_model") == "sale.order"
    kinds = [turn["kind"] for turn in out["conversation"]]
    assert kinds.index("stock_app_install") < kinds.index("stock_app_installed")


def test_decline_stops_request_without_traceback(
    api: TestClient, connection_id: str, fake_odoo: BaseOnlyOdoo, rereads: list
) -> None:
    created = _create(api, connection_id)
    res = api.post(f"/api/ai/sessions/{created['id']}/stock-app", json={"decision": "decline"})
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["stopped"] is True
    assert out["status"] == "stopped"
    assert out["pending_clarification"] is None
    assert out["message"] == "Stopped. Sales was not installed, so this request was not built."
    assert "Traceback" not in res.text
    assert "button_immediate_install" not in fake_odoo.methods_called()
    again = api.post(f"/api/ai/sessions/{created['id']}/stock-app", json={"decision": "install"})
    assert again.status_code == 409
    assert again.json()["detail"]["message"] == "No app install is waiting on this request."


def test_failed_install_is_one_sentence_and_keeps_the_offer(
    api: TestClient, connection_id: str, fake_odoo: BaseOnlyOdoo, rereads: list
) -> None:
    created = _create(api, connection_id)
    fake_odoo.fail_install = "Traceback (most recent call last):\n psycopg2.errors.LockNotAvailable"
    res = api.post(f"/api/ai/sessions/{created['id']}/stock-app", json={"decision": "install"})
    assert res.status_code == 502
    message = res.json()["detail"]["message"]
    assert message == "Sales could not be installed. Odoo did not finish the install."
    assert "Traceback" not in res.text
    row = api.get(f"/api/ai/sessions/{created['id']}").json()
    assert row["pending_clarification"]["kind"] == "stock_app_install"


def test_installed_db_skips_the_confirm_step(
    api: TestClient, connection_id: str, fake_odoo: BaseOnlyOdoo, rereads: list
) -> None:
    fake_odoo.state["sale"] = "installed"
    fake_odoo.models.add("sale.order")
    out = _create(api, connection_id)
    assert (out.get("clarification") or {}).get("kind") != "stock_app_install"


@pytest.mark.no_app_db
def test_generate_gate_uses_the_same_confirm_step_for_a_locked_host() -> None:
    from app.routers.ai_studio import _stock_app_gate

    port = BaseOnlyOdoo()
    proposal = _stock_app_gate(object(), PROMPT, host_model="purchase.order", port=port)
    assert proposal is not None and proposal.module == "purchase" and proposal.installable
