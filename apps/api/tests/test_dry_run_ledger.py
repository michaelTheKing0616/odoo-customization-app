"""Dry-run hash is required before the matching live write."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.dry_run_ledger import DryRunRequired, enforce_dry_run
from app.dry_run_middleware import DryRunHashMiddleware


def test_live_write_without_preview_is_refused() -> None:
    args = {"recipe_id": "mass_archive", "ids": [1]}
    with pytest.raises(DryRunRequired):
        enforce_dry_run("tool", args, dry_run=False)


def test_preview_then_live_write_matches() -> None:
    args = {"recipe_id": "mass_archive", "ids": [1], "confirm_phrase": "I understand the risks"}
    enforce_dry_run("tool", args, dry_run=True)
    enforce_dry_run(
        "tool",
        {**args, "receipt_token": "abc", "confirm_advanced": True},
        dry_run=False,
    )


def test_middleware_refuses_then_allows_the_same_body() -> None:
    app = FastAPI()
    app.add_middleware(DryRunHashMiddleware)

    @app.post("/write")
    async def write(request: Request) -> dict:
        await request.json()
        return {"ok": True}

    client = TestClient(app)
    blocked = client.post("/write", json={"model": "res.partner", "dry_run": False})
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error"] == "dry_run_receipt_required"
    preview = client.post("/write", json={"model": "res.partner", "dry_run": True})
    assert preview.status_code == 200
    live = client.post(
        "/write",
        json={
            "model": "res.partner",
            "dry_run": False,
            "confirm_phrase": "I understand the risks",
        },
    )
    assert live.status_code == 200
