"""Wave 18 ELITE — developer-grade generation gates."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai_domain_pack_library import library_management_pack
from app.ai_domain_packs import match_domain_pack, merge_domain_pack
from app.ai_draft_scorecard import attach_scorecard, draft_scorecard
from app.ai_elite import (
    ELITE_DIMENSION_FLOORS,
    ELITE_SCORECARD_FLOOR,
    check_elite_scorecard_floors,
    elite_promote_gate,
    run_elite_artifacts_pass,
    run_elite_integration_pass,
    run_elite_passes,
    run_elite_python_pass,
    run_elite_quality_pass,
)
from app.ai_enrich import enrich_draft_module_spec
from app.ai_rules import validate_and_enrich_draft
from app.main import app
from app.module_spec_codec import draft_dict_to_module_spec, export_draft_module_zip
from app.settings import settings
from module_generator import render_module_files

FIXTURE6 = Path(__file__).parent / "fixtures" / "draft_supermarket6_2026-08-08.json"
LIBRARY_FIXTURE = Path(__file__).parent / "fixtures" / "draft_library_elite_2026-08-12.json"
LIBRARY_PROMPT = (
    "Build a sophisticated library management system with books, loans, "
    "reservations, fines, and overdue reminders for library members"
)


def _build_library_elite_draft() -> dict[str, Any]:
    pack = library_management_pack()
    draft: dict[str, Any] = {
        "technical_name": "library_management",
        "display_name": "Sophisticated Library Management",
        "depends": list(pack.get("depends") or ["base"]),
        "models": [],
        "domain_pack": "library_management",
        "_llm_status": {"mode": "llm_full", "completed_steps": ["elite-test"]},
        "ambition": "comprehensive",
    }
    merged, _warnings = merge_domain_pack(draft, pack)
    draft = merged
    validate_and_enrich_draft(draft)
    enrich_draft_module_spec(draft)
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    run_post_critique_pipeline(draft, user_prompt=LIBRARY_PROMPT)
    run_production_shape_pass(draft)
    run_elite_passes(draft, user_prompt=LIBRARY_PROMPT)
    attach_scorecard(draft, user_prompt=LIBRARY_PROMPT)
    draft["_meta"] = {
        **(draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}),
        "score_0_10": (draft.get("_scorecard") or {}).get("score_0_10"),
    }
    return draft


def _make_test_connection(db, cid: str, name: str) -> None:
    from app.db_models import OdooConnection

    db.add(
        OdooConnection(
            id=cid,
            name=name,
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted="dev-only-test",
            server_version="19.0",
        )
    )
    db.commit()


@pytest.fixture(scope="module")
def library_elite_draft() -> dict[str, Any]:
    return _build_library_elite_draft()


def test_reliability_staged_pipeline_default() -> None:
    assert settings.ai_pipeline_mode == "staged"


def test_library_pack_matches_prompt() -> None:
    matched = match_domain_pack(LIBRARY_PROMPT)
    assert matched is not None
    pack_id, pack = matched
    assert pack_id == "library_management"
    assert pack.get("domain_pack") == "library_management"
    assert len(pack.get("models") or []) >= 6


def test_library_pack_merge() -> None:
    base = {"technical_name": "lib", "display_name": "Lib", "depends": ["base"], "models": []}
    merged, _warnings = merge_domain_pack(base, library_management_pack())
    assert len(merged.get("models") or []) >= 6


def test_elite_python_adds_lint_clean_blocks(library_elite_draft: dict[str, Any]) -> None:
    blocks = library_elite_draft.get("custom_code_blocks") or []
    assert len(blocks) >= 2
    models_with_blocks = {b.get("model") for b in blocks if isinstance(b, dict)}
    assert "x_lib_loan" in models_with_blocks


def test_elite_artifacts_mail_cron_report(library_elite_draft: dict[str, Any]) -> None:
    assert any(
        isinstance(m, dict) and m.get("xml_id") == "mail_template_loan_overdue"
        for m in (library_elite_draft.get("mail_templates") or [])
    )
    assert any(
        isinstance(c, dict) and c.get("xml_id") == "ir_cron_library_overdue"
        for c in (library_elite_draft.get("cron_jobs") or [])
    )
    assert any(
        isinstance(r, dict) and r.get("model") == "x_lib_loan"
        for r in (library_elite_draft.get("reports") or [])
    )


def test_elite_integration_billing_prompt() -> None:
    draft = _build_library_elite_draft()
    draft["models"] = [
        {
            "model": "x_rental_contract",
            "description": "Rental Contract",
            "mode": "new",
            "is_workflow": True,
            "fields": [
                {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                {"name": "x_amount", "ttype": "monetary", "string": "Amount"},
            ],
        }
    ]
    notes = run_elite_integration_pass(
        draft,
        user_prompt="rental billing and invoice integration",
    )
    model = draft["models"][0]
    field_names = {f["name"] for f in model.get("fields") or []}
    assert "x_invoice_id" in field_names
    assert "account" in (draft.get("depends") or [])
    assert notes


def test_elite_quality_tests_and_i18n(library_elite_draft: dict[str, Any]) -> None:
    blocks = library_elite_draft.get("custom_code_blocks") or []
    paths = {str(b.get("source_file")) for b in blocks if isinstance(b, dict)}
    assert any(p.endswith("_smoke.py") for p in paths)
    assert any(p.endswith(".pot") for p in paths)


def test_elite_scorecard_floors_library(library_elite_draft: dict[str, Any]) -> None:
    sc = library_elite_draft.get("_scorecard") or {}
    overall = float(sc.get("score_0_10") or 0)
    assert overall >= ELITE_SCORECARD_FLOOR, sc
    dims = sc.get("dimensions") or {}
    for dim, floor in ELITE_DIMENSION_FLOORS.items():
        assert float(dims.get(dim) or 0) >= floor, f"{dim} below {floor}"
    ok, reasons = check_elite_scorecard_floors(sc)
    assert ok, reasons


def test_elite_promote_gate_passes_library(library_elite_draft: dict[str, Any]) -> None:
    passed, reasons = elite_promote_gate(library_elite_draft)
    assert passed, reasons


def test_elite_promote_gate_blocks_low_score() -> None:
    draft = {"models": [], "_scorecard": {"score_0_10": 5.0, "dimensions": {}, "validators": {}}}
    passed, reasons = elite_promote_gate(draft)
    assert not passed
    assert any("overall" in r for r in reasons)


def test_module_spec_codec_mail_cron(library_elite_draft: dict[str, Any]) -> None:
    spec = draft_dict_to_module_spec(library_elite_draft)
    assert len(spec.mail_templates) >= 1
    assert len(spec.cron_jobs) >= 1
    assert len(spec.reports) >= 1


def test_elite_zip_contains_artifacts(library_elite_draft: dict[str, Any]) -> None:
    files = render_module_files(draft_dict_to_module_spec(library_elite_draft))
    root = str(library_elite_draft.get("technical_name") or "library_management")
    assert f"{root}/data/mail_templates.xml" in files
    assert f"{root}/data/reminders.xml" in files or f"{root}/data/mail_templates.xml" in files
    assert any("test_" in k and k.endswith(".py") for k in files)
    zip_bytes = export_draft_module_zip(library_elite_draft, odoo_major=19)
    assert len(zip_bytes) > 500


def test_elite_passes_on_supermarket6_fixture() -> None:
    draft = json.loads(FIXTURE6.read_text())
    prompt = "mega supermarket branches"
    attach_scorecard(draft, user_prompt=prompt)
    before = float((draft.get("_scorecard") or {}).get("score_0_10") or 0)
    notes = run_elite_passes(draft, user_prompt=prompt)
    attach_scorecard(draft, user_prompt=prompt)
    assert notes
    after = float((draft.get("_scorecard") or {}).get("score_0_10") or 0)
    assert after >= before - 0.5


def test_elite_autopilot_route_gate_failure(client: TestClient) -> None:
    from app.db import SessionLocal, init_db
    import uuid

    init_db()
    db = SessionLocal()
    try:
        cid = str(uuid.uuid4())
        _make_test_connection(db, cid, "Elite Test")
    finally:
        db.close()

    bad = {"technical_name": "x", "models": [], "_scorecard": {"score_0_10": 4.0, "dimensions": {}, "validators": {}}}
    res = client.post(f"/api/connections/{cid}/module-spec/elite-autopilot", json={"spec": bad})
    assert res.status_code == 200
    body = res.json()
    assert body.get("ok") is False
    assert body.get("gate_passed") is False


def test_elite_autopilot_mock_sandbox(client: TestClient, library_elite_draft: dict[str, Any]) -> None:
    library_elite_draft["_meta"] = {**(library_elite_draft.get("_meta") or {}), "score_0_10": 9.5}
    sc = library_elite_draft.setdefault("_scorecard", {})
    if isinstance(sc, dict):
        sc.setdefault("validators", {})["all_green"] = True
    from app.db import SessionLocal, init_db
    import uuid

    init_db()
    db = SessionLocal()
    try:
        cid = str(uuid.uuid4())
        _make_test_connection(db, cid, "Elite Sandbox")
    finally:
        db.close()

    fake_result = MagicMock()
    fake_result.ok = True
    fake_result.module = "library_management"
    fake_result.message = "ok"
    fake_result.log_tail = ""

    fake_validation = MagicMock()
    fake_validation.id = "val-test-id"
    fake_validation.zip_sha256 = "abc"

    with (
        patch("app.ai_elite_promote.run_sandbox_install", return_value=fake_result),
        patch("app.ai_elite_promote.record_sandbox_validation", return_value=fake_validation),
    ):
        res = client.post(
            f"/api/connections/{cid}/module-spec/elite-autopilot",
            json={"spec": library_elite_draft},
        )
    assert res.status_code == 200
    body = res.json()
    assert body.get("ok") is True
    assert body.get("validation_id") == "val-test-id"
    assert body.get("gate_passed") is True


def test_elite_gate_route(client: TestClient, library_elite_draft: dict[str, Any]) -> None:
    from app.db import SessionLocal, init_db
    import uuid

    init_db()
    db = SessionLocal()
    try:
        cid = str(uuid.uuid4())
        _make_test_connection(db, cid, "Elite Gate")
    finally:
        db.close()

    res = client.post(
        f"/api/connections/{cid}/module-spec/elite-gate",
        json={"spec": library_elite_draft},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("gate_passed") is True


def test_write_library_elite_fixture(library_elite_draft: dict[str, Any]) -> None:
    """Persist regression fixture for Wave 18."""
    LIBRARY_FIXTURE.write_text(json.dumps(library_elite_draft, indent=2))
    loaded = json.loads(LIBRARY_FIXTURE.read_text())
    assert loaded.get("_elite", {}).get("passes_applied") is True
    assert len(loaded.get("models") or []) >= 6


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
