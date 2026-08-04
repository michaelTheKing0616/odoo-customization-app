"""AI-9 — overlap / already-exists detection tests."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.ai_overlap import (  # noqa: E402
    SEMANTIC_CONFIDENCE_FLOOR,
    OverlapFinding,
    check_overlap,
    default_semantic_filter,
    record_overlap_choice,
)


def test_zero_hit_fast_path_no_semantic_pass() -> None:
    result = check_overlap(
        "build a completely unique x_zorbax inventory from scratch",
        installed_modules=["base"],
        projects=[],
    )
    assert result["findings"] == []
    assert result["semantic_pass_ran"] is False
    assert result["requires_review"] is False


def test_installed_module_source_b() -> None:
    result = check_overlap(
        "build me a project tracker to track tasks per client",
        grain="full_app",
        installed_modules=["base", "web", "project", "mail"],
        connection_id="conn-1",
    )
    ids = {f["id"] for f in result["findings"]}
    assert "installed-project" in ids
    hit = next(f for f in result["findings"] if f["id"] == "installed-project")
    assert "Project" in hit["title"]
    assert hit["source"] == "installed_module"
    assert "track" in hit["evidence"].lower() or "task" in hit["evidence"].lower()


def test_available_module_source_c() -> None:
    result = check_overlap(
        "I need a helpdesk ticket system",
        installed_modules=["base", "web"],
        available_odoo_modules=["helpdesk", "crm"],
        connection_id="conn-1",
    )
    assert any(f["source"] == "available_module" for f in result["findings"])


def test_workspace_project_source_d() -> None:
    result = check_overlap(
        "car rental fleet management",
        projects=[
            {
                "id": "p1",
                "name": "Car Rental extras",
                "updated_at": datetime(2026, 6, 12, tzinfo=timezone.utc),
                "spec_json": {"display_name": "Car Rental Fleet"},
            }
        ],
        connection_id="conn-1",
        semantic_fn=lambda _p, xs: xs,
    )
    assert any(f["source"] == "workspace_project" for f in result["findings"])
    hit = next(f for f in result["findings"] if f["source"] == "workspace_project")
    assert "Car Rental" in hit["evidence"]


def test_gallery_source_d() -> None:
    result = check_overlap(
        "add warranty tracker on sales orders",
        projects=[],
        connection_id="conn-1",
        semantic_fn=lambda _p, xs: xs,
    )
    assert any(f["source"] == "gallery" for f in result["findings"])


def test_instance_field_source_a() -> None:
    client = MagicMock()
    client.execute_kw.return_value = [
        {
            "name": "x_warranty_end",
            "field_description": "Warranty End Date",
            "model": "sale.order",
        }
    ]
    result = check_overlap(
        "add warranty end date on sale orders",
        host_model="sale.order",
        client=client,
        connection_id="conn-1",
        semantic_fn=lambda _p, xs: xs,
    )
    assert any(f["source"] == "instance" for f in result["findings"])
    hit = next(f for f in result["findings"] if f["source"] == "instance")
    assert "x_warranty_end" in hit["evidence"]


def test_precision_guard_drops_low_confidence() -> None:
    low = OverlapFinding(
        id="low-1",
        source="gallery",
        title="Maybe",
        evidence="weak",
        confidence=0.5,
        artifact_type="gallery",
    )
    kept = default_semantic_filter("unique prompt", [low])
    assert kept == []


def test_semantic_pass_only_when_shortlist() -> None:
    calls: list[int] = []

    def counter(_prompt: str, findings: list[OverlapFinding]) -> list[OverlapFinding]:
        calls.append(len(findings))
        return [f for f in findings if f.confidence >= SEMANTIC_CONFIDENCE_FLOOR]

    check_overlap("unique zorbax", semantic_fn=counter)
    assert calls == []

    check_overlap(
        "track tasks per client",
        installed_modules=["project"],
        semantic_fn=counter,
    )
    assert calls == [1]


def test_build_anyway_recorded_on_draft() -> None:
    draft = record_overlap_choice(
        {"technical_name": "x_test"},
        finding_id="installed-project",
        choice="build_anyway",
        findings=[{"id": "installed-project"}],
    )
    assert draft["overlap_audit"]["choice"] == "build_anyway"
    assert draft["overlap_audit"]["finding_id"] == "installed-project"


def test_findings_capped_at_five() -> None:
    many = [
        OverlapFinding(
            id=f"f{i}",
            source="gallery",
            title=f"G{i}",
            evidence="e",
            confidence=0.9 - i * 0.05,
            artifact_type="gallery",
        )
        for i in range(10)
    ]

    def passthrough(_p: str, xs: list[OverlapFinding]) -> list[OverlapFinding]:
        return xs

    result = check_overlap(
        "warranty inspection compliance tracker tasks sales",
        projects=[],
        semantic_fn=passthrough,
    )
    # deterministic may add gallery hits — force via direct rank test
    from app.ai_overlap import _rank_and_cap

    ranked = _rank_and_cap(many)
    assert len(ranked) == 5


def test_check_overlap_route() -> None:
    from fastapi.testclient import TestClient

    from app.db import init_db
    from app.main import app

    init_db()
    client = TestClient(app)
    res = client.post(
        "/api/ai/check-overlap",
        json={"prompt": "track tasks per client", "grain": "full_app"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "findings" in body
