"""TRUST-5 chaos harness, mutation lock, apply resumability tests."""

from __future__ import annotations

import os
import threading
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.bulk_suite.transitions import PerRecordResult, _execute_transition_chunk  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.mutation_lock import (  # noqa: E402
    ConnectionMutationBusy,
    connection_mutation_lock,
    reset_mutation_locks_for_tests,
    try_acquire_connection_mutation_lock,
)
from app.project_apply import apply_project_spec  # noqa: E402
from app.rpc_resilience import (  # noqa: E402
    ChaosPolicy,
    ChaosRpcWrapper,
    execute_mutation_with_verify,
    is_transport_rpc_error,
)


@pytest.fixture(autouse=True)
def _reset_locks() -> None:
    reset_mutation_locks_for_tests()
    yield
    reset_mutation_locks_for_tests()


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def test_mutation_lock_refuses_second_holder() -> None:
    assert try_acquire_connection_mutation_lock("conn-a", "bulk.run") is True
    assert try_acquire_connection_mutation_lock("conn-a", "apply") is False
    with pytest.raises(ConnectionMutationBusy):
        with connection_mutation_lock("conn-a", "other"):
            pass


def test_mutation_lock_allows_different_connections() -> None:
    with connection_mutation_lock("conn-1"):
        with connection_mutation_lock("conn-2"):
            pass


def test_api_returns_409_when_mutation_in_progress(client: TestClient) -> None:
    init_db()
    create = client.post(
        "/api/connections",
        json={
            "name": "Lock test",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    assert create.status_code == 201, create.text
    conn_id = create.json()["id"]
    client.patch(
        f"/api/connections/{conn_id}/write-mode",
        json={"write_mode": "standard"},
    )

    with connection_mutation_lock(conn_id, "held-by-test"):
        resp = client.post(
            f"/api/connections/{conn_id}/bulk/transitions/run",
            json={
                "model": "sale.order",
                "method": "action_confirm",
                "dry_run": True,
                "cap": 10,
            },
        )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "mutation_in_progress"


def test_is_transport_rpc_error() -> None:
    assert is_transport_rpc_error(ConnectionError("reset")) is True
    assert is_transport_rpc_error(ValueError("bad domain")) is False


def test_execute_mutation_with_verify_treats_changed_fingerprint_as_success() -> None:
    reads = {"n": 0}

    class FakeClient:
        def execute_kw(self, model, method, args=None, kwargs=None):
            if method == "read":
                reads["n"] += 1
                wd = "2026-01-01" if reads["n"] == 1 else "2026-01-02"
                return [{"write_date": wd, "display_name": "A"}]
            raise ConnectionError("chaos: dropped mid-write")

    ok, err = execute_mutation_with_verify(
        FakeClient(),
        model="sale.order",
        method="action_confirm",
        record_id=1,
    )
    assert ok is True
    assert err is None
    assert reads["n"] >= 2


def test_chaos_wrapper_injects_transport_failure() -> None:
    inner = MagicMock()
    inner.execute_kw.return_value = True
    wrapped = ChaosRpcWrapper(inner, ChaosPolicy(fail_on_call=2))
    wrapped.execute_kw("res.partner", "read", [[1]])
    with pytest.raises(ConnectionError, match="chaos:"):
        wrapped.execute_kw("res.partner", "write", [[1], {"name": "x"}])


def test_transition_chunk_uses_resilient_per_record_fallback() -> None:
    client = MagicMock()

    def execute_kw(model, method, args=None, kwargs=None):
        if method == "read":
            return [{"id": args[0][0], "write_date": "t", "display_name": "n"}]
        if method == "action_confirm" and len(args[0]) > 1:
            raise RuntimeError("batch failed")
        return True

    client.execute_kw.side_effect = execute_kw
    results = _execute_transition_chunk(
        client,
        model="sale.order",
        method="action_confirm",
        record_ids=[1, 2],
        names={1: "One", 2: "Two"},
    )
    assert len(results) == 2
    assert all(r.ok for r in results)


def test_apply_project_spec_idempotent_on_rerun() -> None:
    client = MagicMock()
    existing_models: set[str] = set()
    existing_fields: set[tuple[str, str]] = set()

    def model_exists(name: str) -> bool:
        return name in existing_models

    def field_exists(model: str, name: str) -> bool:
        return (model, name) in existing_fields

    def create_model(req, **kwargs):
        existing_models.add(req.model)
        return MagicMock(model=req.model)

    def create_field(req):
        existing_fields.add((req.model, req.name))
        return MagicMock()

    client.model_exists.side_effect = model_exists
    client.field_exists.side_effect = field_exists
    client.create_model.side_effect = create_model
    client.create_field.side_effect = create_field

    spec = {
        "models": [
            {
                "model": "x_resume_test",
                "description": "Resume",
                "fields": [{"name": "x_name", "ttype": "char", "string": "Name"}],
            }
        ]
    }
    first = apply_project_spec(client, spec)
    second = apply_project_spec(client, spec)
    assert first.models_created == ["x_resume_test"]
    assert first.fields_created == 1
    assert second.models_created == []
    assert second.fields_created == 0
    assert client.create_model.call_count == 1
    assert client.create_field.call_count == 1


def test_concurrent_api_lock_via_thread(client: TestClient) -> None:
    init_db()
    create = client.post(
        "/api/connections",
        json={
            "name": "Thread lock",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    conn_id = create.json()["id"]
    client.patch(f"/api/connections/{conn_id}/write-mode", json={"write_mode": "standard"})

    results: list[int] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        barrier.wait(timeout=5)
        resp = client.post(
            f"/api/connections/{conn_id}/bulk/transitions/run",
            json={
                "model": "sale.order",
                "method": "action_confirm",
                "dry_run": True,
                "cap": 10,
            },
        )
        results.append(resp.status_code)

    with connection_mutation_lock(conn_id, "blocker"):
        t = threading.Thread(target=worker)
        t.start()
        barrier.wait(timeout=5)
        t.join(timeout=5)
    assert 409 in results