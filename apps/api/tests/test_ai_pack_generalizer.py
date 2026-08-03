"""Tests for AI-6 draft→pack generalizer."""

from __future__ import annotations

import ast
import os
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

from app.ai_domain_pack_law_firm import law_firm_pack  # noqa: E402
from app.ai_domain_packs import score_domain_pack  # noqa: E402
from app.ai_pack_generalizer import (  # noqa: E402
    generalize_spec_to_pack_candidate,
    parse_candidate_pack_source,
)
from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_generalize_law_firm_gold_parses_and_classifies() -> None:
    spec = law_firm_pack()
    result = generalize_spec_to_pack_candidate(spec, pack_slug="law_firm")
    ast.parse(result["source"])
    pack = parse_candidate_pack_source(result["source"])
    assert pack.get("domain_pack") == "law_firm"
    assert isinstance(pack.get("models"), list)
    assert len(pack["models"]) >= 8
    assert "x_matter" in {m.get("model") for m in pack["models"]}
    score = score_domain_pack(
        "law firm practice management with matters and retainers", pack
    )
    assert score >= 0.07
    assert result["filename"] == "ai_domain_pack_candidate_law_firm.py"
    assert "NOT registered" in result["note"]


def test_generalize_strips_views_and_keeps_automations() -> None:
    spec = law_firm_pack()
    spec["views"] = [{"name": "x_matter.form", "type": "form", "arch": "<form/>"}]
    result = generalize_spec_to_pack_candidate(spec, pack_slug="law_firm")
    assert any("omitted non-pack key" in w for w in result["warnings"])
    pack = parse_candidate_pack_source(result["source"])
    assert "views" not in pack
    assert isinstance(pack.get("automations"), list)


def test_generalize_endpoint_requires_consent(client: TestClient) -> None:
    spec = law_firm_pack()
    res = client.post(
        "/api/ai/generalize-pack",
        json={"spec_json": spec, "consent_share_template": False},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["requires_consent"] is True


def test_generalize_endpoint_spec_json(client: TestClient) -> None:
    spec = law_firm_pack()
    res = client.post(
        "/api/ai/generalize-pack",
        json={"spec_json": spec, "consent_share_template": True, "pack_slug": "law_firm"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["filename"].startswith("ai_domain_pack_candidate_")
    assert "def candidate_pack" in body["source"]
    assert body["model_count"] >= 8
    ast.parse(body["source"])


def test_generalize_llm_tags_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Fake:
        name = "fake"

        def generate_json(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return '{"tags":["legal","matter"],"anti_patterns":["Do NOT drop x_bill"]}'

    spec = law_firm_pack()
    out = generalize_spec_to_pack_candidate(spec, pack_slug="law_firm", provider=_Fake())  # type: ignore[arg-type]
    assert "legal" in out["suggested_tags"]
    assert any("x_bill" in a for a in out["anti_patterns"])


def test_generalize_never_writes_app_files(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.ai_pack_generalizer as gen

    def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("generalizer must not write files")

    monkeypatch.setattr(gen, "open", _boom, raising=False)
    spec = law_firm_pack()
    result = generalize_spec_to_pack_candidate(spec, pack_slug="law_firm")
    assert result["source"]
    assert "ai_domain_pack_candidate" in result["filename"]
