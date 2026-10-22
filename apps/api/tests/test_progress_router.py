"""Progress poll endpoint returns stage events for a run."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.progress.store import get_stage_bus


def test_progress_events_poll() -> None:
    bus = get_stage_bus()
    bus.emit("run-test", "expert_retrieve", detail="docs")
    client = TestClient(app)
    res = client.get("/api/progress/runs/run-test/events")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    assert body["events"][-1]["stage"] == "expert_retrieve"
