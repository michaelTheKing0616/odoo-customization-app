"""Queued flush claims through claim_db. Promote stays human."""

from __future__ import annotations

import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import get_db
from app.db_models import IdempotencyKey
from app.dry_run_middleware import is_write_capable
from app.offline.flush import FlushBody, apply_queued_flush, recorded_flush_effects, reset_flush_effects
from app.routers.offline import router
from app.snapshots import CONFIRM_PHRASE

pytestmark = pytest.mark.no_app_db

PROMOTE_BODY = {
    "kind": "promote",
    "method": "POST",
    "path": "/api/connections/c1/modules/promote",
    "body": {"validation_id": "val-1"},
}

MUTATION_BODY = {
    "kind": "mutation",
    "method": "POST",
    "path": "/api/connections/c1/fields",
    "body": {"name": "x_note"},
}


def _app(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/offline_flush.db",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    IdempotencyKey.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app = FastAPI()
    app.include_router(router, prefix="/api")

    def _db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    return app, factory


@pytest.fixture
def client(tmp_path):
    reset_flush_effects()
    app, _factory = _app(tmp_path)
    with TestClient(app) as test_client:
        yield test_client
    reset_flush_effects()


def test_flush_is_not_an_odoo_write() -> None:
    assert is_write_capable("POST", "/api/offline/flush") is False


def test_dropped_ack_does_not_double_apply(client: TestClient) -> None:
    headers = {"Idempotency-Key": "01JOFFLINEACK000000000001"}
    first = client.post("/api/offline/flush", json=MUTATION_BODY, headers=headers)
    dropped = first.json()
    second = client.post("/api/offline/flush", json=MUTATION_BODY, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json() == dropped
    assert dropped["applied"] is True
    assert dropped["effect_seq"] == 1
    assert recorded_flush_effects() == [
        {"kind": "mutation", "method": "POST", "path": "/api/connections/c1/fields"}
    ]


def test_promote_without_confirm_is_refused_and_not_applied(client: TestClient) -> None:
    headers = {"Idempotency-Key": "01JOFFLINEPROM00000000001"}
    res = client.post("/api/offline/flush", json=PROMOTE_BODY, headers=headers)
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["requires_confirmation"] is True
    assert detail["confirm_phrase"] == CONFIRM_PHRASE
    assert recorded_flush_effects() == []

    confirmed = client.post(
        "/api/offline/flush",
        json={
            **PROMOTE_BODY,
            "confirm_advanced": True,
            "confirm_phrase": CONFIRM_PHRASE,
        },
        headers=headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["applied"] is True
    assert confirmed.json()["kind"] == "promote"
    assert len(recorded_flush_effects()) == 1


def test_two_tabs_flushing_the_same_item_produce_one_effect(tmp_path) -> None:
    reset_flush_effects()
    app, _factory = _app(tmp_path)
    key = "01JOFFLINETABS00000000001"
    results: list[dict] = []
    errors: list[BaseException] = []

    def _flush() -> None:
        try:
            with TestClient(app) as tab:
                res = tab.post(
                    "/api/offline/flush",
                    json=MUTATION_BODY,
                    headers={"Idempotency-Key": key},
                )
                results.append({"status": res.status_code, "body": res.json()})
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    first = threading.Thread(target=_flush)
    second = threading.Thread(target=_flush)
    first.start()
    second.start()
    first.join()
    second.join()
    assert errors == []
    assert [row["status"] for row in results] == [200, 200]
    assert results[0]["body"] == results[1]["body"]
    assert results[0]["body"]["effect_seq"] == 1
    assert recorded_flush_effects() == [
        {"kind": "mutation", "method": "POST", "path": "/api/connections/c1/fields"}
    ]
    reset_flush_effects()


def test_missing_idempotency_key_is_refused(client: TestClient) -> None:
    res = client.post("/api/offline/flush", json=MUTATION_BODY)
    assert res.status_code == 400
    assert recorded_flush_effects() == []


def test_apply_queued_flush_does_not_touch_odoo() -> None:
    reset_flush_effects()
    out = apply_queued_flush(FlushBody.model_validate(MUTATION_BODY))
    assert out["applied"] is True
    assert "odoo" not in out
    reset_flush_effects()
