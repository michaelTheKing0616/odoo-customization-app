"""Tests for robust AI drafts + domain packs + enrich (no Odoo required)."""

from __future__ import annotations

import json
import os
from typing import Any
from typing import Any

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
from app.ai_domain_packs import car_rental_pack, match_domain_pack, merge_domain_pack  # noqa: E402
from app.ai_enrich import enrich_draft_module_spec  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_match_car_rental_pack() -> None:
    hit = match_domain_pack("I need a car rental service management app")
    assert hit is not None
    pack_id, pack = hit
    assert pack_id == "car_rental"
    models = {m["model"] for m in pack["models"]}
    assert "x_rent_vehicle" in models
    assert "x_rent_contract" in models
    assert "x_rent_customer" in models
    assert pack["smart_buttons"]
    assert pack["automations"]


def test_enrich_adds_views_menus() -> None:
    draft, warnings = enrich_draft_module_spec(car_rental_pack())
    assert draft["views"]
    assert draft["menus"]
    assert draft["actions"]
    assert any(v["type"] == "form" for v in draft["views"])
    assert any("statusbar" in (v.get("arch") or "") for v in draft["views"] if v["type"] == "form")
    assert warnings


def test_merge_fills_thin_ai_draft() -> None:
    thin = {
        "technical_name": "cars",
        "display_name": "Cars",
        "depends": ["base"],
        "models": [
            {
                "model": "x_rent_vehicle",
                "description": "Car",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                ],
            }
        ],
    }
    merged, warnings = merge_domain_pack(thin, car_rental_pack())
    assert len(merged["models"]) >= 8
    assert any("domain pack added model" in w for w in warnings)
    vehicle = next(m for m in merged["models"] if m["model"] == "x_rent_vehicle")
    field_names = {f["name"] for f in vehicle["fields"]}
    assert "x_plate" in field_names
    assert "x_vin" in field_names


def test_draft_module_offline_domain_pack(client: TestClient) -> None:
    settings.ai_assist = "off"
    res = client.post(
        "/api/ai/draft-module",
        json={"prompt": "car rental fleet management with deposits"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["domain_pack"] == "car_rental"
    models = {m["model"] for m in body["draft"]["models"]}
    assert "x_rent_contract" in models
    assert body["draft"]["views"]
    assert body["draft"]["smart_buttons"]


def test_draft_module_503_when_ai_off_and_no_pack(client: TestClient) -> None:
    settings.ai_assist = "off"
    res = client.post("/api/ai/draft-module", json={"prompt": "Books and loans"})
    assert res.status_code == 503


def test_draft_module_with_monkeypatched_ollama(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.ai_assist = "ollama"
    settings.ollama_base_url = "http://127.0.0.1:11434"
    settings.ollama_model = "llama3.2"

    fake = {
        "technical_name": "demo_books",
        "display_name": "Demo Books",
        "depends": ["base"],
        "models": [
            {
                "model": "x_book",
                "description": "Book",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Title", "required": True},
                    {"name": "x_barcode", "ttype": "char", "string": "Barcode"},
                ],
            }
        ],
    }

    class _FakeProvider:
        name = "ollama"

        def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
            return True, "fake"

        def generate_json(
            self, prompt: str, *, system: str | None = None, timeout_s: float = 60.0, **kwargs: Any
        ) -> str:
            return json.dumps(fake)

    monkeypatch.setattr(ai_ollama, "get_llm_provider", lambda: _FakeProvider())

    res = client.post(
        "/api/ai/draft-module",
        json={"prompt": "Books with barcode and loans"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["draft"]["technical_name"] == "demo_books"
    assert body["draft"]["models"][0]["model"] == "x_book"
    # enrich should add menus/views
    assert body["draft"]["menus"]
    assert body["draft"]["views"]


def test_validate_rejects_bad_model_name() -> None:
    with pytest.raises(ValueError, match="x_"):
        ai_ollama.validate_draft_module_spec(
            {
                "technical_name": "ok_mod",
                "display_name": "Ok",
                "models": [{"model": "book", "fields": [{"name": "x_name"}]}],
            }
        )


def test_car_rental_in_templates(client: TestClient) -> None:
    res = client.get("/api/apps/templates")
    assert res.status_code == 200
    ids = {t["id"] for t in res.json()}
    assert "car_rental" in ids


def test_module_spec_apply_requires_confirm(client: TestClient) -> None:
    res = client.post(
        "/api/connections/00000000-0000-0000-0000-000000000000/module-spec/apply",
        json={"spec": {"models": [{"model": "x_demo", "fields": []}]}},
    )
    assert res.status_code in (403, 404)


def test_library_export_includes_fines(client: TestClient) -> None:
    res = client.post(
        "/api/apps/templates/library/export",
        json={
            "technical_name": "library_mgmt",
            "display_name": "Library",
            "fines": True,
            "reminders": True,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["technical_name"] == "library_mgmt"
    assert body["content_base64"]
    assert "fines=on" in body["note"]
    assert "reminders=on" in body["note"]
