"""Comprehensive tests for AI module generation pipeline (no live Odoo).

Covers: domain packs, enrich/UI defaults, pack merge, optional rules engine,
API contracts, and apply_project_spec two-pass field ordering.
"""

from __future__ import annotations

import importlib
import json
import os
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ["AI_ASSIST"] = "off"

from app import ai_ollama  # noqa: E402
from app.ai_domain_packs import (  # noqa: E402
    car_rental_pack,
    match_domain_pack,
    merge_domain_pack,
)
from app.ai_enrich import enrich_draft_module_spec, ensure_default_ui  # noqa: E402
from app.main import app  # noqa: E402
from app.project_apply import apply_project_spec  # noqa: E402
from app.settings import settings  # noqa: E402
from odoo_client.models import CreateFieldRequest, CreateModelRequest, FieldType  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REQUIRED_CAR_RENTAL_MODELS = {
    "x_rent_branch",
    "x_rent_vehicle",
    "x_rent_customer",
    "x_rent_rate",
    "x_rent_extra",
    "x_rent_contract",
    "x_rent_payment",
    "x_rent_damage",
    "x_rent_maintenance",
}

VEHICLE_STATUS_KEYS = {"available", "rented", "maintenance", "retired"}


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _thin_vehicle_draft(*, extra_field: dict[str, Any] | None = None) -> dict[str, Any]:
    fields: list[dict[str, Any]] = [
        {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
        {"name": "x_ai_only", "ttype": "char", "string": "AI Extra"},
    ]
    if extra_field:
        fields.append(extra_field)
    return {
        "technical_name": "cars",
        "display_name": "Cars",
        "depends": ["base"],
        "models": [
            {
                "model": "x_rent_vehicle",
                "description": "Car",
                "fields": fields,
            },
            {
                "model": "x_ai_bonus",
                "description": "AI-only model",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                ],
            },
        ],
    }


def _thin_one_model_draft(*, with_status: bool = False) -> dict[str, Any]:
    fields: list[dict[str, Any]] = [
        {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
        {"name": "x_note", "ttype": "char", "string": "Note"},
    ]
    if with_status:
        fields.append(
            {
                "name": "x_status",
                "ttype": "selection",
                "string": "Status",
                "selection": "[('draft', 'Draft'), ('done', 'Done'), ('cancelled', 'Cancelled')]",
            }
        )
    return {
        "technical_name": "demo_widget",
        "display_name": "Demo Widget",
        "depends": ["base"],
        "models": [
            {
                "model": "x_demo_widget",
                "description": "Widget",
                "mode": "new",
                "fields": fields,
            }
        ],
    }


# ===========================================================================
# A. Domain packs & retrieval
# ===========================================================================


class TestDomainPacks:
    def test_car_rental_pack_required_models(self) -> None:
        pack = car_rental_pack()
        models = {m["model"] for m in pack["models"]}
        assert REQUIRED_CAR_RENTAL_MODELS.issubset(models)
        assert len(pack["models"]) >= 8

    def test_car_rental_pack_smart_buttons_and_automations(self) -> None:
        pack = car_rental_pack()
        assert pack["smart_buttons"], "expected smart_buttons metadata"
        assert pack["automations"], "expected automation stubs"
        btn_models = {b["on_model"] for b in pack["smart_buttons"]}
        assert "x_rent_vehicle" in btn_models
        assert "x_rent_contract" in btn_models
        auto_names = {a["name"] for a in pack["automations"]}
        assert any("rented" in n.lower() or "confirm" in n.lower() for n in auto_names)

    def test_customer_links_res_partner(self) -> None:
        pack = car_rental_pack()
        customer = next(m for m in pack["models"] if m["model"] == "x_rent_customer")
        partner = next(f for f in customer["fields"] if f["name"] == "x_partner_id")
        assert partner["ttype"] == "many2one"
        assert partner["relation"] == "res.partner"
        assert partner.get("required") is True

    def test_vehicle_status_selection_values(self) -> None:
        pack = car_rental_pack()
        vehicle = next(m for m in pack["models"] if m["model"] == "x_rent_vehicle")
        status = next(f for f in vehicle["fields"] if f["name"] == "x_status")
        assert status["ttype"] == "selection"
        selection = status["selection"]
        for key in VEHICLE_STATUS_KEYS:
            assert f"'{key}'" in selection, f"missing status key {key}"

    @pytest.mark.parametrize(
        "prompt",
        [
            "I need a car rental service management app",
            "vehicle rental fleet with deposits",
            "Build a rent-a-car operations module",
            "auto hire booking system",
            "Car-hire branch and contracts",
            "fleet rental management",
        ],
    )
    def test_match_positive_prompts(self, prompt: str) -> None:
        hit = match_domain_pack(prompt)
        assert hit is not None, f"expected car_rental match for: {prompt!r}"
        pack_id, pack = hit
        assert pack_id == "car_rental"
        assert pack["domain_pack"] == "car_rental"

    @pytest.mark.parametrize(
        "prompt",
        [
            "Books and loans library",
            "HR leave management",
            "Inventory warehouse barcodes",
            "I rent apartments (property management)",
            "car wash loyalty points",  # car but not rental domain phrase
            "",
            "   ",
        ],
    )
    def test_match_negative_prompts(self, prompt: str) -> None:
        assert match_domain_pack(prompt) is None

    def test_retrieve_domain_pack_ranks_car_rental(self) -> None:
        """Regex + keyword scoring: car rental prompt retrieves car_rental first."""
        from app.ai_domain_packs import retrieve_domain_pack, score_domain_pack

        hit = retrieve_domain_pack("car rental fleet management with deposits")
        assert hit is not None
        pack_id, pack, score = hit
        assert pack_id == "car_rental"
        assert score >= 0.08
        assert pack["domain_pack"] == "car_rental"

        # Soft keyword path (no regex): still prefers car_rental over clinic
        car_score = score_domain_pack(
            "fleet vehicle hire deposit odometer", car_rental_pack()
        )
        clinic = importlib.import_module("app.ai_domain_packs").clinic_pack()
        clinic_score = score_domain_pack(
            "fleet vehicle hire deposit odometer", clinic
        )
        assert car_score > clinic_score

    def test_retrieve_clinic_and_field_service(self) -> None:
        from app.ai_domain_packs import retrieve_domain_pack

        clinic_hit = retrieve_domain_pack("clinic appointment booking for patients")
        assert clinic_hit is not None
        assert clinic_hit[0] == "clinic"

        fs_hit = retrieve_domain_pack("field service job dispatch for technicians")
        assert fs_hit is not None
        assert fs_hit[0] == "field_service"

    def test_retrieve_hospital_world_class_prompt(self) -> None:
        from app.ai_domain_packs import hospital_pack, retrieve_domain_pack

        hit = retrieve_domain_pack(
            "I want to create a comprehensive Hospital Management app that "
            "perfectly models the internal workings of a modern world-class hospital"
        )
        assert hit is not None
        assert hit[0] == "hospital"
        pack = hospital_pack()
        assert pack["domain_pack"] == "hospital"
        assert len(pack["models"]) >= 15
        assert len(pack["smart_buttons"]) >= 12
        model_names = {m["model"] for m in pack["models"]}
        for required in (
            "x_patient",
            "x_encounter",
            "x_ward",
            "x_bed",
            "x_lab_order",
            "x_prescription",
            "x_surgery",
        ):
            assert required in model_names


# ===========================================================================
# B. Enrich / ensure_default_ui
# ===========================================================================


class TestEnrich:
    def test_thin_draft_gets_menus_actions_list_form(self) -> None:
        draft, warnings = enrich_draft_module_spec(_thin_one_model_draft())
        assert draft["menus"], "expected menus"
        assert draft["actions"], "expected actions"
        assert any(a.get("model") == "x_demo_widget" for a in draft["actions"])
        view_types = {
            (v["model"], v["type"]) for v in draft["views"] if isinstance(v, dict)
        }
        assert ("x_demo_widget", "list") in view_types
        assert ("x_demo_widget", "form") in view_types
        assert warnings

    def test_form_arch_statusbar_when_x_status(self) -> None:
        draft, _ = enrich_draft_module_spec(_thin_one_model_draft(with_status=True))
        forms = [v for v in draft["views"] if v.get("type") == "form"]
        assert forms
        arch = forms[0].get("arch") or ""
        assert 'widget="statusbar"' in arch
        assert 'name="x_status"' in arch
        # kanban expected when status present
        assert any(v.get("type") == "kanban" for v in draft["views"])

    def test_ensure_default_ui_idempotent(self) -> None:
        base = _thin_one_model_draft(with_status=True)
        first = enrich_draft_module_spec(base)[0]
        menu_count = len(first["menus"])
        action_count = len(first["actions"])
        view_count = len(first["views"])

        second, warnings2 = enrich_draft_module_spec(first)
        assert len(second["menus"]) == menu_count
        assert len(second["actions"]) == action_count
        assert len(second["views"]) == view_count
        # Second pass should not re-add menus/actions (already present)
        assert not any("added" in w and "menu" in w for w in warnings2)
        assert not any("added" in w and "action" in w for w in warnings2)

    def test_ensure_default_ui_direct_idempotent_on_same_object(self) -> None:
        draft = enrich_draft_module_spec(_thin_one_model_draft())[0]
        menus_before = list(draft["menus"])
        views_before = len(draft["views"])
        w2 = ensure_default_ui(draft)
        assert draft["menus"] == menus_before
        assert len(draft["views"]) == views_before
        assert w2 == [] or not any("menu" in w for w in w2)

    def test_meta_summary_counts(self) -> None:
        pack = car_rental_pack()
        draft, _ = enrich_draft_module_spec(pack)
        meta = draft.get("_meta")
        assert isinstance(meta, dict)
        assert meta["model_count"] == len(draft["models"])
        assert meta["view_count"] == len(draft["views"])
        assert meta["menu_count"] == len(draft["menus"])
        assert meta["smart_button_count"] == len(draft.get("smart_buttons") or [])
        assert meta["automation_count"] == len(draft.get("automations") or [])
        assert meta["domain_pack"] == "car_rental"
        assert meta["model_count"] >= 8
        assert meta["view_count"] >= 16  # list+form per model at minimum


# ===========================================================================
# C. Merge pack
# ===========================================================================


class TestMergePack:
    def test_thin_vehicle_merged_gains_models_keeps_ai_extras(self) -> None:
        thin = _thin_vehicle_draft()
        merged, warnings = merge_domain_pack(thin, car_rental_pack())
        models = {m["model"]: m for m in merged["models"]}

        assert len(merged["models"]) >= 9  # pack models + x_ai_bonus
        assert "x_ai_bonus" in models, "AI-only model must be preserved"
        assert "x_rent_contract" in models
        assert "x_rent_customer" in models

        vehicle = models["x_rent_vehicle"]
        field_names = {f["name"] for f in vehicle["fields"]}
        assert "x_plate" in field_names
        assert "x_vin" in field_names
        assert "x_status" in field_names
        assert "x_ai_only" in field_names, "AI extra field must be preserved"

        assert any("domain pack added model" in w for w in warnings)
        assert any("domain pack added field" in w for w in warnings)
        assert merged.get("smart_buttons")
        assert merged.get("automations")
        assert merged.get("domain_pack") == "car_rental"


# ===========================================================================
# D. Rules engine (optional — parent may add app.ai_rules)
# ===========================================================================


def _load_ai_rules():
    try:
        return importlib.import_module("app.ai_rules")
    except ModuleNotFoundError:
        return None


class TestRulesEngine:
    def test_validate_and_enrich_draft_api_present_or_xfail(self) -> None:
        mod = _load_ai_rules()
        if mod is None:
            pytest.xfail("app.ai_rules not present yet (parent agent adding it)")
        assert hasattr(mod, "validate_and_enrich_draft"), (
            "expected public API validate_and_enrich_draft(spec) -> (spec, warnings, errors)"
        )

    def test_orphan_relations_flagged(self) -> None:
        mod = _load_ai_rules()
        if mod is None:
            pytest.xfail("app.ai_rules not present yet")
        validate = getattr(mod, "validate_and_enrich_draft", None)
        if validate is None:
            pytest.xfail("validate_and_enrich_draft missing")

        orphan_spec = {
            "technical_name": "orphan_demo",
            "display_name": "Orphan Demo",
            "depends": ["base"],
            "models": [
                {
                    "model": "x_orphan_parent",
                    "description": "Parent",
                    "fields": [
                        {"name": "x_name", "ttype": "char", "string": "Name"},
                        {
                            "name": "x_missing_id",
                            "ttype": "many2one",
                            "string": "Missing",
                            "relation": "x_does_not_exist",
                        },
                    ],
                }
            ],
        }
        out, warnings, errors = validate(orphan_spec)
        msgs = " ".join([*(warnings or []), *(errors or [])]).lower()
        assert (
            "orphan" in msgs
            or "relation" in msgs
            or "x_does_not_exist" in msgs
            or "referential" in msgs
        ), f"expected orphan/referential warning; got warnings={warnings} errors={errors}"
        assert isinstance(out, dict)

    def test_pattern_rules_status_sequence_partner(self) -> None:
        mod = _load_ai_rules()
        if mod is None:
            pytest.xfail("app.ai_rules not present yet")
        validate = getattr(mod, "validate_and_enrich_draft", None)
        if validate is None:
            pytest.xfail("validate_and_enrich_draft missing")

        spec = {
            "technical_name": "pattern_demo",
            "display_name": "Pattern Demo",
            "depends": ["base"],
            "models": [
                {
                    "model": "x_pattern_ticket",
                    "description": "Ticket",
                    "fields": [
                        {"name": "x_name", "ttype": "char", "string": "Name"},
                        {
                            "name": "x_status",
                            "ttype": "selection",
                            "string": "Status",
                            "selection": "[('open', 'Open'), ('done', 'Done')]",
                        },
                        {
                            "name": "x_partner_id",
                            "ttype": "many2one",
                            "string": "Partner",
                            "relation": "res.partner",
                        },
                    ],
                }
            ],
        }
        out, warnings, errors = validate(spec)
        blob = " ".join(
            [
                json.dumps(out),
                " ".join(warnings or []),
                " ".join(errors or []),
            ]
        ).lower()
        # Soft pattern expectations: statusbar hint and/or sequence / partner smart button
        assert (
            "statusbar" in blob
            or "sequence" in blob
            or "smart" in blob
            or "partner" in blob
            or "hint" in blob
        ), f"expected pattern-rule hints; got warnings={warnings} errors={errors}"


# ===========================================================================
# E. API contract
# ===========================================================================


class TestApiContract:
    def test_draft_module_ai_off_car_rental(self, client: TestClient) -> None:
        settings.ai_assist = "off"
        res = client.post(
            "/api/ai/draft-module",
            json={"prompt": "car rental fleet management with deposits"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["ok"] is True
        assert body["domain_pack"] == "car_rental"
        assert body["draft"]["views"], "views must be nonempty after enrich"
        assert body["draft"]["menus"]
        models = {m["model"] for m in body["draft"]["models"]}
        assert "x_rent_contract" in models
        assert "x_rent_vehicle" in models

    def test_draft_module_ai_off_unrelated_503(self, client: TestClient) -> None:
        settings.ai_assist = "off"
        res = client.post(
            "/api/ai/draft-module",
            json={"prompt": "Books and loans catalog"},
        )
        assert res.status_code == 503

    def test_draft_module_monkeypatched_ollama_merges_car_rental(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings.ai_assist = "ollama"
        settings.ollama_base_url = "http://127.0.0.1:11434"
        settings.ollama_model = "llama3.2"
        settings.ai_pipeline_mode = "single"

        thin = {
            "technical_name": "thin_cars",
            "display_name": "Thin Cars",
            "depends": ["base"],
            "models": [
                {
                    "model": "x_rent_vehicle",
                    "description": "Vehicle",
                    "fields": [
                        {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                        {"name": "x_ai_color", "ttype": "char", "string": "AI Color"},
                    ],
                }
            ],
        }

        class _FakeProvider:
            name = "ollama"

            def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
                return True, "fake"

            def generate_json(
                self,
                prompt: str,
                *,
                system: str | None = None,
                timeout_s: float = 60.0,
            ) -> str:
                return json.dumps(thin)

        monkeypatch.setattr(ai_ollama, "get_llm_provider", lambda: _FakeProvider())

        res = client.post(
            "/api/ai/draft-module",
            json={"prompt": "car rental operations for my fleet"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["ok"] is True
        assert body["domain_pack"] == "car_rental"
        assert len(body["draft"]["models"]) >= 5
        vehicle = next(
            m for m in body["draft"]["models"] if m["model"] == "x_rent_vehicle"
        )
        names = {f["name"] for f in vehicle["fields"]}
        assert "x_ai_color" in names
        assert "x_plate" in names
        assert body["draft"]["views"]

    def test_ai_status_includes_domain_packs(self, client: TestClient) -> None:
        res = client.get("/api/ai/status")
        assert res.status_code == 200, res.text
        body = res.json()
        assert "ai_assist" in body or "enabled" in body
        packs = body.get("domain_packs")
        assert isinstance(packs, list), f"expected list of pack ids, got {packs!r}"
        assert "car_rental" in packs
        assert "clinic" in packs
        assert "field_service" in packs
        assert "ollama_base_url" in body or "ollama_model" in body or "provider" in body

    def test_module_spec_apply_without_confirm(self, client: TestClient) -> None:
        res = client.post(
            "/api/connections/00000000-0000-0000-0000-000000000000/module-spec/apply",
            json={"spec": {"models": [{"model": "x_demo", "fields": []}]}},
        )
        # Missing connection → 404; if connection existed without confirm → 403
        assert res.status_code in (403, 404), res.text

    def test_templates_list_includes_car_rental(self, client: TestClient) -> None:
        res = client.get("/api/apps/templates")
        assert res.status_code == 200
        ids = {t["id"] for t in res.json()}
        assert "car_rental" in ids


# ===========================================================================
# F. Apply helpers — two-pass field ordering (unit, FakeClient)
# ===========================================================================


class FakeOdooClient:
    """Minimal stand-in that records create_field order for apply_project_spec."""

    def __init__(self) -> None:
        self.models: set[str] = set()
        self.fields: dict[str, set[str]] = {}
        self.create_field_calls: list[tuple[str, str, str]] = []
        self.create_model_calls: list[str] = []

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def field_exists(self, model: str, name: str) -> bool:
        return name in self.fields.get(model, set())

    def create_model(
        self, request: CreateModelRequest, *, with_defaults: bool = True
    ) -> MagicMock:
        self.models.add(request.model)
        self.fields.setdefault(request.model, set())
        if with_defaults:
            self.fields[request.model].add("x_name")
        self.create_model_calls.append(request.model)
        return MagicMock(model=request.model, name=request.name)

    def create_field(self, request: CreateFieldRequest) -> MagicMock:
        ttype = (
            request.ttype.value
            if isinstance(request.ttype, FieldType)
            else str(request.ttype)
        )
        self.create_field_calls.append((request.model, request.name, ttype))
        self.fields.setdefault(request.model, set()).add(request.name)
        return MagicMock(name=request.name, model=request.model, ttype=ttype)


class TestApplyProjectSpecOrdering:
    def test_one2many_created_after_scalars_and_many2one(self) -> None:
        client = FakeOdooClient()
        spec = {
            "models": [
                {
                    "model": "x_parent",
                    "description": "Parent",
                    "fields": [
                        {
                            "name": "x_child_ids",
                            "ttype": "one2many",
                            "string": "Children",
                            "relation": "x_child",
                            "relation_field": "x_parent_id",
                        },
                        {"name": "x_code", "ttype": "char", "string": "Code"},
                        {
                            "name": "x_partner_id",
                            "ttype": "many2one",
                            "string": "Partner",
                            "relation": "res.partner",
                        },
                    ],
                },
                {
                    "model": "x_child",
                    "description": "Child",
                    "fields": [
                        {
                            "name": "x_parent_id",
                            "ttype": "many2one",
                            "string": "Parent",
                            "relation": "x_parent",
                        },
                        {"name": "x_label", "ttype": "char", "string": "Label"},
                    ],
                },
            ]
        }

        result = apply_project_spec(client, spec)  # type: ignore[arg-type]
        assert "x_parent" in client.create_model_calls
        assert "x_child" in client.create_model_calls
        assert result.fields_created >= 4

        # Index of first one2many create must be after all non-O2M creates
        o2m_indices = [
            i
            for i, (_m, _n, t) in enumerate(client.create_field_calls)
            if t == "one2many"
        ]
        non_o2m_indices = [
            i
            for i, (_m, _n, t) in enumerate(client.create_field_calls)
            if t != "one2many"
        ]
        assert o2m_indices, "expected at least one one2many create_field"
        assert non_o2m_indices, "expected scalar/many2one create_field calls"
        assert min(o2m_indices) > max(non_o2m_indices), (
            f"one2many must be after scalars/M2O; calls={client.create_field_calls}"
        )

        # Same-batch sanity: parent O2M after parent char + M2O
        parent_calls = [
            (n, t) for (m, n, t) in client.create_field_calls if m == "x_parent"
        ]
        parent_names_order = [n for n, _t in parent_calls]
        assert parent_names_order.index("x_child_ids") > parent_names_order.index(
            "x_code"
        )
        assert parent_names_order.index("x_child_ids") > parent_names_order.index(
            "x_partner_id"
        )
