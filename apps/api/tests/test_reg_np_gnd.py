"""REG-NP-GND oracle. Pins only worked-example inputs and outputs."""

from __future__ import annotations

import atexit
import json
import os
import tempfile
import time
import uuid
from types import SimpleNamespace
from typing import Any

_SQLITE_FD, _SQLITE_PATH = tempfile.mkstemp(prefix="reg_np_gnd_", suffix=".sqlite")
os.close(_SQLITE_FD)
_SQLITE_URL = "sqlite:///" + _SQLITE_PATH
os.environ["DATABASE_URL"] = _SQLITE_URL
os.environ["AUTH_MODE"] = "off"
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"
os.environ.setdefault("FERNET_KEY", "dev-only-test")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.settings import settings

settings.database_url = _SQLITE_URL
settings.auth_mode = "off"
settings.rate_limit_per_minute = 0

import app.db as app_db  # noqa: E402

_ENGINE = create_engine(
    _SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
app_db.engine = _ENGINE
app_db.SessionLocal = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False)

pytestmark = pytest.mark.no_app_db

_FORM_ARCH = (
    "<form><sheet><group>"
    '<field name="partner_id"/>'
    '<field name="partner_invoice_id"/>'
    '<field name="date_order"/>'
    "</group></sheet></form>"
)
_LIST_ARCH = '<list><field name="name"/><field name="partner_id"/></list>'
_SEARCH_ARCH = '<search><field name="name"/><field name="partner_id"/></search>'
_QUOTATION_PROMPT = "Add a field after the customer on quotations"
_AC6_PROMPT = "add a PO reference on quotations"
_INVENTED = "commercial_partner_phone"
_X_KEEP = "x_studio_tier"
_MAP_HEADERS = ["Kunde Name", "Mail Adresse", "Telefon Nr"]
_MAP_ROWS = [
    {"Kunde Name": "Ada", "Mail Adresse": "ada@example.com", "Telefon Nr": "123"}
]


def _cleanup_sqlite() -> None:
    _ENGINE.dispose()
    for suffix in ("", "-journal", "-wal", "-shm"):
        try:
            os.unlink(_SQLITE_PATH + suffix)
        except OSError:
            pass


atexit.register(_cleanup_sqlite)


class _SaleViewTables:
    def __call__(self, model: str, method: str, args: list, kwargs: dict):
        if method != "get_view" or model != "sale.order":
            raise AssertionError((model, method))
        view_type = str(kwargs.get("view_type") or "form")
        arches = {"form": _FORM_ARCH, "list": _LIST_ARCH, "search": _SEARCH_ARCH}
        return {"arch": arches.get(view_type, "<form/>")}


def _sale_client():
    from app.ai_schema_client import FakeSchemaClient

    return FakeSchemaClient(
        models={"sale.order", "res.partner"},
        fields={
            "sale.order": {
                "partner_id": {
                    "type": "many2one",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "required": True,
                },
                "partner_invoice_id": {
                    "type": "many2one",
                    "ttype": "many2one",
                    "relation": "res.partner",
                },
                "date_order": {"type": "datetime", "ttype": "datetime"},
                "name": {"type": "char", "ttype": "char"},
            }
        },
        methods={"sale.order": {"action_confirm", "formatted_read_group"}},
    )


def _connection(*, major: int = 19) -> SimpleNamespace:
    return SimpleNamespace(
        id="fixture-sale",
        server_version=f"{major}.0",
        odoo_major=major,
        odoo_version=f"{major}.0",
        installed_modules=[{"name": "sale", "state": "installed"}],
    )


def _graph():
    from odoo_client.read_plane import ReadPlane
    from odoo_client.schema_graph import SchemaGraph

    return SchemaGraph(ReadPlane(_SaleViewTables()))


def _sale_packet(*, major: int = 19):
    from app.live_schema_context import build_schema_packet

    return build_schema_packet(
        _connection(major=major),
        models=["sale.order"],
        schema_client=_sale_client(),
        schema_graph=_graph(),
    )


def _partner_packet():
    from app.ai_schema_client import FakeSchemaClient
    from app.live_schema_context import build_schema_packet

    client = FakeSchemaClient(
        models={"res.partner"},
        fields={
            "res.partner": {
                "name": {"type": "char", "ttype": "char"},
                "email": {"type": "char", "ttype": "char"},
                "phone": {"type": "char", "ttype": "char"},
            }
        },
    )
    return build_schema_packet(
        SimpleNamespace(id="fixture", server_version="19.0", odoo_major=19),
        models=["res.partner"],
        schema_client=client,
    )


def _host_absent_from_packet(packet) -> str:
    """The pin names the condition, not a model string."""
    from app.ai_grain import HOST_ALIASES

    for model in dict.fromkeys(HOST_ALIASES.values()):
        if model not in packet.models:
            return model
    raise AssertionError("packet contains every known host")


class _JsonProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.prompts: list[str] = []
        self.json_calls = 0
        self.text_calls = 0

    @property
    def name(self) -> str:
        return "reg-np-gnd-fake"

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        return True, "ok"

    def generate_json(self, prompt: str, **_kwargs: Any) -> str:
        self.json_calls += 1
        self.prompts.append(prompt)
        return json.dumps(self.payload)

    def generate_text(self, prompt: str, **_kwargs: Any) -> str:
        self.text_calls += 1
        self.prompts.append(prompt)
        return ""


def _field_names(models: list[Any], model: str) -> set[str]:
    for row in models:
        if isinstance(row, dict) and row.get("model") == model:
            return {
                str(field.get("name"))
                for field in (row.get("fields") or [])
                if isinstance(field, dict) and field.get("name")
            }
    return set()


def _missing_field_names(rows: list[Any], model: str) -> set[str]:
    return {
        str(row.get("name"))
        for row in rows
        if isinstance(row, dict) and row.get("model") == model and row.get("name")
    }


def _invented_on_partner_and_x_keep() -> list[dict[str, Any]]:
    return [
        {"model": "res.partner", "name": _INVENTED, "ttype": "char", "string": "Invented"},
        {"model": "res.partner", "name": _X_KEEP, "ttype": "char", "string": "Custom tier"},
    ]


def _thin_draft() -> dict[str, Any]:
    return {
        "technical_name": "studio_book",
        "display_name": "Studio Book",
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [{"name": "x_existing", "ttype": "char", "string": "Existing"}],
            }
        ],
    }


def _fake_budget(payload: dict[str, Any], prompts: list[str]):
    def _call(_provider: Any, _step: str, prompt: str, **_kwargs: Any) -> tuple[str, None]:
        prompts.append(prompt)
        return json.dumps(payload), None

    return _call


def test_ac1_sale_order_packet() -> None:
    from app.ai_schema_client import SCHEMA_CATALOG_TTL_S
    from app.live_schema_context import build_schema_packet

    packet = _sale_packet()
    sale = packet.models["sale.order"]
    assert sale.views["form"] == ("partner_id", "partner_invoice_id", "date_order")
    assert sale.fields["partner_id"].relation == "res.partner"
    assert "x_not_on_sale" not in sale.fields

    major_17 = _sale_packet(major=17)
    methods = major_17.models["sale.order"].methods
    assert "formatted_read_group" not in methods
    assert "action_confirm" in methods

    now = time.time()
    stale = build_schema_packet(
        _connection(),
        models=["sale.order"],
        draft={
            "_connection_catalog": {
                "available_models": ["sale.order"],
                "stock": [{"model": "sale.order"}],
                "installed_modules": ["sale"],
                "loaded_at": now - SCHEMA_CATALOG_TTL_S - 10,
            },
            "_schema_fields": {
                "sale.order": {
                    "partner_id": {"type": "many2one", "relation": "res.partner"},
                }
            },
            "_schema_client": _sale_client(),
        },
        schema_client=_sale_client(),
        schema_graph=_graph(),
        now=now,
    )
    assert stale.is_empty() is True


def test_ac1_no_connection_raises() -> None:
    from app.live_schema_context import ConnectionRequiredError, build_schema_packet

    with pytest.raises(ConnectionRequiredError):
        build_schema_packet(None, models=["sale.order"])
    with pytest.raises(ConnectionRequiredError):
        build_schema_packet("", models=["sale.order"])


def test_ac2_ground_studio_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.llm_provider import MockLLMProvider
    from app.routers.ai_studio import ground_studio_generate

    packet = _sale_packet()
    invented = json.dumps(
        {
            "title": "PO ref on quotations",
            "summary": "Add x_po_ref on sale.order after partner_id",
            "host_model": "sale.order",
            "inherit_existing": True,
            "needs_module": False,
            "constraints": ["On Sales (sale.order)", "Add x_po_ref", "Place after the customer"],
            "out_of_scope": ["new home-screen app"],
            "confidence": "high",
        }
    )

    class _Provider(MockLLMProvider):
        def __init__(self) -> None:
            super().__init__(json_response=invented)

        def generate_json(self, prompt: str, **kwargs: Any) -> str:
            return super().generate_json(prompt, **kwargs)

    previous = settings.ai_intent_llm
    settings.ai_intent_llm = "on"
    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": _Provider(),
    )
    try:
        grounded = ground_studio_generate(_QUOTATION_PROMPT, schema_packet=packet)
    finally:
        settings.ai_intent_llm = previous

    assert "LIVE SCHEMA PACKET" in grounded["user_message"]
    assert "partner_id" in grounded["user_message"]
    assert grounded["placement_anchor"] == "partner_id"
    assert "x_po_ref" not in json.dumps(grounded)


def test_ac2_absent_host_discarded_not_new_app(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_conversation.intent_gate import IntentAssessment
    from app.ai_conversation.intent_llm import maybe_llm_refine_assessment

    packet = _sale_packet()
    absent = _host_absent_from_packet(packet)
    assert absent not in packet.models
    provider = _JsonProvider(
        {
            "clear": True,
            "confidence": "high",
            "host_model": absent,
            "inherit_existing": True,
            "needs_module": False,
            "residual": "absent from the packet",
            "rationale": "host is absent from the packet",
        }
    )
    previous = settings.ai_intent_llm
    settings.ai_intent_llm = "on"
    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier",
        lambda tier="fast": provider,
    )
    try:
        refined = maybe_llm_refine_assessment(
            _QUOTATION_PROMPT,
            IntentAssessment(
                clear=False,
                triggers=["low_ir_confidence"],
                ir_confidence="low",
                capability_path="residual_app",
            ),
            ranked=[],
            schema_packet=packet,
        )
    finally:
        settings.ai_intent_llm = previous

    assert refined.clear is False
    assert "host_model" not in (refined.llm_resolved or {})
    assert any(
        "discarded" in note and "not repaired into a new app" in note for note in refined.notes
    )


def test_ac3_expert_cites_live_schema_packet(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.expert.ask import ask_expert
    from app.expert.grounding import GroundingBundle

    client = _sale_client()
    conn = _connection()
    monkeypatch.setattr("app.odoo_service.get_connection_or_404", lambda _db, _cid: conn)
    monkeypatch.setattr("app.expert.ask.manifest_for_connection", lambda _row: {"version": "19.0"})
    monkeypatch.setattr(
        "app.expert.ask.assemble_context",
        lambda *_args, **_kwargs: GroundingBundle(retrieval_version="19.0"),
    )
    result = ask_expert(
        SimpleNamespace(),
        question="What type is partner_id on sale.order on this instance?",
        connection_id="fixture-sale",
        schema_client=client,
        schema_graph=_graph(),
        provider=_JsonProvider({}),
    )
    assert result.grounded is True
    assert result.declined is False
    assert "partner_id" in result.answer_markdown
    assert "LIVE SCHEMA PACKET" in result.answer_markdown


def test_ac4_quotations_community_major_20() -> None:
    from app.live_demo_copilot.stage2_answer import STOCK_COMMUNITY, generate_live_answer

    model = _JsonProvider(
        {
            "verdict": "stock_community",
            "app": "Sales",
            "text": (
                "Stock Community — Sales. "
                "Quotations are a standard Sales feature on Odoo Community 20."
            ),
            "claimed_names": [],
            "hosting_depends": False,
        }
    )
    answer = generate_live_answer(
        None,
        question="Can Odoo do quotations?",
        connection_id=None,
        major=20,
        edition="Community",
        provider=model,
    )
    surface = " ".join(
        [
            answer.verdict,
            answer.answer_markdown or "",
            " ".join(answer.bullets),
            answer.confidence_flag or "",
            answer.app_name or "",
        ]
    )
    assert answer.verdict == STOCK_COMMUNITY
    assert answer.app_name == "Sales"
    assert "database" not in surface.lower()
    assert model.json_calls == 1
    assert model.text_calls == 0


def test_ac5_job_packet_keeps_only_live_models() -> None:
    from app.job_autopilot.planner import build_job_packet

    sale_packet = _sale_packet()
    job = build_job_packet(
        "Quotations and invoices for a trading company.",
        use_llm=False,
        schema_packet=sale_packet,
        planned_models=["sale.order", "project.task"],
    )
    assert job.operator_brief["schema_models"] == ["sale.order"]
    assert "project.task" not in {residual.model for residual in job.custom_residuals}


class _BaseOnlyOdoo:
    def __init__(self) -> None:
        self.models = {"res.partner", "res.users", "ir.model"}
        self.state = {"base": "installed", "sale": "uninstalled"}
        self.calls: list[tuple[str, str, list]] = []

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None):
        self.calls.append((model, method, args))
        if model == "ir.model" and method == "search_count":
            name = args[0][0][2]
            return 1 if name in self.models else 0
        if model == "ir.module.module" and method == "search_read":
            field, _op, value = args[0][0]
            if field == "name":
                if value not in self.state:
                    return []
                module_id = 1 if value == "base" else 41
                return [{"id": module_id, "state": self.state[value]}]
            if field == "state":
                return [{"name": name} for name, state in self.state.items() if state == value]
        return []

    def methods_called(self) -> list[str]:
        return [method for _model, method, _args in self.calls]


def test_ac6_decline_stops_stock_app_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from app.crypto import encrypt_secret
    from app.db_models import OdooConnection
    from app.main import app

    app_db.init_db()
    db = app_db.SessionLocal()
    try:
        row = OdooConnection(
            name="reg-np-gnd-base-only",
            url="http://127.0.0.1:9",
            db_name=f"regnpgnd-{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        connection_id = row.id
    finally:
        db.close()

    port = _BaseOnlyOdoo()
    monkeypatch.setattr("app.routers.ai_studio._open_stock_app_port", lambda _conn: port)
    monkeypatch.setattr("app.odoo_snapshot.snapshot_for_connection", lambda *_a, **_k: None)
    monkeypatch.setattr("app.routers.ai_studio.snapshot_for_connection", lambda *_a, **_k: None)
    monkeypatch.setattr("app.llm_provider.get_llm_provider", lambda *_a, **_k: None)
    monkeypatch.setattr("app.llm_provider.get_llm_provider_for_tier", lambda *_a, **_k: None)
    monkeypatch.setattr("app.routers.ai_studio.get_llm_provider", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "app.routers.ai_studio.get_llm_provider_for_tier", lambda *_a, **_k: None
    )
    previous = settings.ai_intent_llm
    settings.ai_intent_llm = "off"
    try:
        with TestClient(app) as api:
            created = api.post(
                "/api/ai/sessions",
                json={"prompt": _AC6_PROMPT, "connection_id": connection_id},
            )
            assert created.status_code == 200, created.text
            body = created.json()
            clarification = body["clarification"]
            assert body["status"] == "clarifying"
            assert clarification["kind"] == "stock_app_install"
            assert clarification["stock_app"]["module"] == "sale"
            assert "Sales is not installed" in clarification["help"]
            assert [option["label"] for option in clarification["options"]] == [
                "Install Sales and continue",
                "Not now",
            ]
            assert "button_immediate_install" not in port.methods_called()

            declined = api.post(
                f"/api/ai/sessions/{body['id']}/stock-app",
                json={"decision": "decline"},
            )
    finally:
        settings.ai_intent_llm = previous

    assert declined.status_code == 200, declined.text
    out = declined.json()
    assert out["stopped"] is True
    assert out["status"] == "stopped"
    assert out["message"] == (
        "Stopped. Sales was not installed, so this request was not built."
    )
    assert "Traceback" not in declined.text
    assert "button_immediate_install" not in port.methods_called()


def test_ac7_pipeline_calls_drop_invented_stock_field(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    from app import ai_ollama
    from app.ai_critique import llm_critique
    from app.ai_depth import llm_expand_depth
    from app.ai_domain_briefing import DomainBriefing, _enrich_briefing_with_llm
    from app.ai_model_quality import llm_deepen_model_fields, llm_emit_missing_scaffold_models
    from app.ai_pipeline import _llm_json

    packet = _partner_packet()
    prompts: list[str] = []
    pipeline_payload = {
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [
                    {"name": _INVENTED, "ttype": "char", "string": "Bad"},
                    {"name": _X_KEEP, "ttype": "char", "string": "Good"},
                ],
            }
        ]
    }
    monkeypatch.setattr(
        "app.ai_llm_budget.llm_json_with_budget",
        _fake_budget(pipeline_payload, prompts),
    )
    data = _llm_json(MagicMock(), system="sys", prompt="Build a studio app", schema_packet=packet)
    names = _field_names(data.get("models") or [], "res.partner")
    assert _INVENTED not in names
    assert _X_KEEP in names
    assert "LIVE SCHEMA PACKET" in prompts[0]

    prompts.clear()
    monkeypatch.setattr(
        "app.ai_llm_budget.llm_json_with_budget",
        _fake_budget(
            {
                "missing_fields": _invented_on_partner_and_x_keep(),
                "missing_models": [],
                "missing_automations": [],
                "notes": ["deepen"],
            },
            prompts,
        ),
    )
    expanded, _notes = llm_expand_depth(
        MagicMock(),
        _thin_draft(),
        user_prompt="music studio booking",
        ambition="standard",
        gaps=["depth_fields"],
        schema_packet=packet,
    )
    expanded_names = _field_names(expanded.get("models") or [], "res.partner")
    assert _INVENTED not in expanded_names
    assert _X_KEEP in expanded_names
    assert "LIVE SCHEMA PACKET" in prompts[0]

    prompts.clear()
    monkeypatch.setattr(
        "app.ai_llm_budget.llm_json_with_budget",
        _fake_budget(
            {
                "ready": False,
                "checklist": [],
                "missing_fields": _invented_on_partner_and_x_keep(),
                "missing_models": [],
                "missing_automations": [],
                "notes": [],
            },
            prompts,
        ),
    )
    critique = llm_critique(
        MagicMock(),
        _thin_draft(),
        user_prompt="music studio",
        schema_packet=packet,
    )
    critique_names = _missing_field_names(critique.get("missing_fields") or [], "res.partner")
    assert _INVENTED not in critique_names
    assert _X_KEEP in critique_names
    assert "LIVE SCHEMA PACKET" in prompts[0]

    prompts.clear()
    monkeypatch.setattr(
        "app.ai_llm_budget.llm_json_with_budget",
        _fake_budget(
            {
                "missing_fields": _invented_on_partner_and_x_keep(),
                "missing_models": [],
                "notes": ["deepen"],
            },
            prompts,
        ),
    )
    deepened, _deep_notes = llm_deepen_model_fields(
        MagicMock(),
        _thin_draft(),
        user_prompt="music studio booking rooms",
        ambition="standard",
        min_fields=6,
        schema_packet=packet,
    )
    deepened_names = _field_names(deepened.get("models") or [], "res.partner")
    assert _INVENTED not in deepened_names
    assert _X_KEEP in deepened_names
    assert "LIVE SCHEMA PACKET" in prompts[0]

    prompts.clear()
    monkeypatch.setattr(
        "app.ai_llm_budget.llm_json_with_budget",
        _fake_budget(
            {
                "models": [
                    {
                        "model": "res.partner",
                        "fields": [
                            {"name": _INVENTED, "ttype": "char"},
                            {"name": _X_KEEP, "ttype": "char"},
                        ],
                    }
                ]
            },
            prompts,
        ),
    )
    emitted, emit_notes = llm_emit_missing_scaffold_models(
        MagicMock(),
        {"models": [{"model": "x_session", "fields": [{"name": "x_name", "ttype": "char"}]}]},
        {"models": [{"model": "x_session_line", "fields": [{"name": "x_name", "ttype": "char"}]}]},
        user_prompt="music studio",
        schema_packet=packet,
    )
    assert _INVENTED not in _field_names(emitted.get("models") or [], "res.partner")
    assert any(_INVENTED in note for note in emit_notes)
    assert "LIVE SCHEMA PACKET" in prompts[0]

    prompts.clear()
    monkeypatch.setattr(
        "app.ai_llm_budget.llm_json_with_budget",
        _fake_budget(
            {
                "industry": "music studio",
                "not_industries": [],
                "equipment_types": [],
                "rate_uoms": [],
                "banned_selection_keys": [],
                "models": [
                    {
                        "model": "res.partner",
                        "fields": [
                            {"name": _INVENTED, "ttype": "char"},
                            {"name": _X_KEEP, "ttype": "char"},
                        ],
                    }
                ],
            },
            prompts,
        ),
    )
    briefing = _enrich_briefing_with_llm(
        DomainBriefing(industry="prompt-derived", source="default", notes=[]),
        "independent music recording studio",
        MagicMock(),
        schema_packet=packet,
    )
    assert any(_INVENTED in note for note in briefing.notes)
    assert "LIVE SCHEMA PACKET" in prompts[0]

    prompts.clear()
    draft_payload = {
        "technical_name": "studio_book",
        "display_name": "Studio Book",
        "depends": ["base"],
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [
                    {"name": _INVENTED, "ttype": "char", "string": "Bad"},
                    {"name": _X_KEEP, "ttype": "char", "string": "Tier"},
                ],
            }
        ],
    }

    class _Prov:
        name = "fake"

        def generate_json(self, prompt: str, **_kwargs: Any) -> str:
            prompts.append(prompt)
            return json.dumps(draft_payload)

    monkeypatch.setattr(ai_ollama, "get_llm_provider", lambda: _Prov())
    monkeypatch.setattr("app.ollama_warm.warm_ollama_models", lambda: None)
    monkeypatch.setattr("app.ai_generation_engine.maybe_seed_from_capability", lambda _p: None)
    monkeypatch.setattr("app.ai_domain_packs.match_domain_pack", lambda *_a, **_k: None)
    monkeypatch.setattr("app.ai_domain_packs.retrieve_domain_pack", lambda *_a, **_k: None)
    monkeypatch.setattr("app.ai_ollama.retrieve_domain_pack", lambda *_a, **_k: None)
    draft, _raw, _warnings, _refusals = ai_ollama.draft_module_from_prompt(
        "Build a full custom music studio booking app with sessions and rooms",
        expand=False,
        pipeline="single",
        grain_override="full_app",
        schema_packet=packet,
    )
    draft_names = _field_names(draft.get("models") or [], "res.partner")
    assert _INVENTED not in draft_names
    assert _X_KEEP in draft_names
    assert any("LIVE SCHEMA PACKET" in prompt for prompt in prompts)

    prompts.clear()
    raw = ai_ollama.call_ollama_generate("studio booking ModuleSpec", schema_packet=packet)
    ollama_names = _field_names(json.loads(raw).get("models") or [], "res.partner")
    assert _INVENTED not in ollama_names
    assert _X_KEEP in ollama_names
    assert "LIVE SCHEMA PACKET" in prompts[0]


def test_ac8_mapping_keeps_live_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ingest import map_columns
    from app.ingest.map_columns import enhance_mapping_with_llm

    llm = _JsonProvider(
        {"mapping": {"Kunde Name": "name", "Mail Adresse": "email", "Telefon Nr": "x_phone_invented"}}
    )
    monkeypatch.setattr(map_columns, "get_llm_provider", lambda: llm)
    mapping, warnings = enhance_mapping_with_llm(
        None,
        model="res.partner",
        headers=_MAP_HEADERS,
        rows=_MAP_ROWS,
        mapping={},
        schema_packet=_partner_packet(),
    )
    assert mapping == {"Kunde Name": "name", "Mail Adresse": "email"}
    assert "Telefon Nr" not in mapping
    assert any("x_phone_invented" in warning and "left unmapped" in warning for warning in warnings)


def test_ac8_no_client_or_empty_fields_skips_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ingest import map_columns
    from app.ingest.map_columns import enhance_mapping_with_llm

    no_client = _JsonProvider({"mapping": {"Kunde Name": "name"}})
    monkeypatch.setattr(map_columns, "get_llm_provider", lambda: no_client)
    mapping, _warnings = enhance_mapping_with_llm(
        None,
        model="res.partner",
        headers=_MAP_HEADERS,
        rows=_MAP_ROWS,
        mapping={},
    )
    assert mapping == {}
    assert no_client.prompts == []

    empty = _JsonProvider({"mapping": {"Kunde Name": "name"}})
    monkeypatch.setattr(map_columns, "get_llm_provider", lambda: empty)
    client = SimpleNamespace(model_exists=lambda _model: True, list_fields=lambda _model: [])
    mapping, _warnings = enhance_mapping_with_llm(
        client,
        model="res.partner",
        headers=_MAP_HEADERS,
        rows=_MAP_ROWS,
        mapping={},
    )
    assert mapping == {}
    assert empty.prompts == []


def test_ac9_narrative_unknown_name_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.expert import narrative
    from app.expert.draft_review import DraftReviewFinding
    from app.expert.retrieval import RetrievedChunk

    def _finding(priority: int) -> DraftReviewFinding:
        return DraftReviewFinding(
            priority=priority,
            element="x_rental",
            summary="Missing list view",
            detail="Model x_rental has no list view.",
            deterministic=True,
        )

    llm = _JsonProvider(
        {
            "narratives": [
                {
                    "priority": 1,
                    "paragraph": "Add x_rental to a list view showing x_po_ref from sale.order [1].",
                    "citation_ids": [1],
                },
                {
                    "priority": 2,
                    "paragraph": "A list view on x_rental near partner_id helps operators [1].",
                    "citation_ids": [1],
                },
            ]
        }
    )
    monkeypatch.setattr(narrative, "expert_assist_enabled", lambda: True)
    monkeypatch.setattr(
        narrative,
        "retrieve_expert_chunks",
        lambda *_args, **_kwargs: [
            RetrievedChunk(
                chunk_id="c1",
                source="odoo-docs",
                version="19.0",
                breadcrumb="Views",
                text="Every model needs a list view.",
                score=0.9,
                method="fixture",
            )
        ],
    )
    monkeypatch.setattr(narrative, "get_llm_provider", lambda: llm)
    findings = [_finding(1), _finding(2)]
    out = narrative.generate_finding_narratives(
        object(),
        findings,
        schema_packet=_sale_packet(),
    )
    by_priority = {row.priority: row for row in out}
    assert by_priority[1].paragraph == narrative._fallback_paragraph(findings[0])
    assert "partner_id" in by_priority[2].paragraph
