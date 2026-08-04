"""TRUST-6 error-path assertions for mutating services (unit-level)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.bulk_suite.storage import (  # noqa: E402
    load_bulk_run,
    mark_bulk_run_abort_requested,
    save_bulk_run,
)
from app.bulk_suite.transitions import BulkRunResult, PerRecordResult, run_bulk_transition  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection, SandboxValidation  # noqa: E402
from app.field_lifecycle import FieldLifecycleError, export_field_column_csv  # noqa: E402
from app.power_ops_recipes import run_recipe  # noqa: E402
from app.promote import get_valid_validation, record_sandbox_validation, sha256_bytes  # noqa: E402
from app.snapshots import save_snapshot  # noqa: E402
from odoo_client.client import OdooClientError  # noqa: E402
from app.rpc_resilience import is_transport_rpc_error  # noqa: E402


def test_bulk_transition_reports_per_record_failure_on_rpc_error() -> None:
    client = MagicMock()

    def execute_kw(model, method, args=None, kwargs=None):
        if method == "read":
            rid = args[0][0]
            return [{"id": rid, "write_date": "t", "display_name": str(rid)}]
        if method == "action_done":
            if len(args[0]) > 1:
                raise OdooClientError("batch failed")
            if args[0][0] == 2:
                raise OdooClientError("access denied")
        return True

    client.execute_kw.side_effect = execute_kw
    result = run_bulk_transition(
        client,
        model="sale.order",
        method="action_done",
        record_ids=[1, 2],
        dry_run=False,
    )
    assert result.failed >= 1
    assert any(not r.ok for r in result.per_record)


def test_field_export_error_path_refuses_without_partial_csv() -> None:
    client = MagicMock()
    client.list_fields.return_value = [MagicMock(name="x_note")]
    client.execute_kw.side_effect = OdooClientError("rpc down")
    with pytest.raises(FieldLifecycleError, match="export failed"):
        export_field_column_csv(client, model="x_test", field_name="x_note")


def test_power_ops_continue_on_error_logs_failed_step() -> None:
    from unittest.mock import patch

    client = MagicMock()
    client.execute_kw.return_value = [101]

    with patch("app.power_ops_recipes.probe_recipe", return_value=(True, "ok")):
        with patch("app.power_ops_recipes.get_recipe") as get_recipe:
            step = MagicMock(label="write", kind="write")
            recipe = MagicMock(
                id="test.recipe",
                name="Test",
                model="res.partner",
                steps=[step],
            )
            get_recipe.return_value = recipe
            with patch(
                "app.power_ops_recipes._exec_step",
                side_effect=OdooClientError("boom"),
            ):
                result = run_recipe(
                    client,
                    recipe_id="test.recipe",
                    model="res.partner",
                    ids=[101],
                    dry_run=False,
                    continue_on_error=True,
                )
    assert result.failed == 1
    assert any(not log.ok for log in result.logs)


def test_promote_validation_expired_error_path() -> None:
    init_db()
    db = SessionLocal()
    try:
        conn = OdooConnection(
            name="promote-err",
            url="http://127.0.0.1:8069",
            db_name="odoo",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        zip_bytes = b"zip-bytes"
        row = record_sandbox_validation(
            db,
            connection_id=conn.id,
            module_name="x_test",
            zip_bytes=zip_bytes,
        )
        row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.add(row)
        db.commit()
        with pytest.raises(ValueError, match="expired"):
            get_valid_validation(
                db,
                validation_id=row.id,
                connection_id=conn.id,
                zip_bytes=zip_bytes,
            )
    finally:
        db.close()


def test_bulk_run_storage_abort_flag_roundtrip() -> None:
    init_db()
    db = SessionLocal()
    try:
        conn = OdooConnection(
            id=str(uuid.uuid4()),
            name="bulk-store",
            url="http://127.0.0.1:8069",
            db_name="odoo",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
        )
        db.add(conn)
        db.commit()
        result = BulkRunResult(
            run_id=str(uuid.uuid4()),
            operation="bulk_transition",
            model="sale.order",
            total=2,
            succeeded=1,
            failed=0,
            per_record=[PerRecordResult(id=1, display_name="A", ok=True)],
            dry_run=False,
            status="sample_paused",
            pending_ids=[2],
        )
        save_bulk_run(db, connection_id=conn.id, result=result)
        payload = mark_bulk_run_abort_requested(db, result.run_id)
        assert payload["abort_requested"] is True
        loaded = load_bulk_run(db, result.run_id)
        assert loaded is not None
        assert loaded["abort_requested"] is True
        assert loaded["can_continue"] is True
    finally:
        db.close()


def test_snapshot_save_persists_payload() -> None:
    init_db()
    db = SessionLocal()
    try:
        conn = OdooConnection(
            id=str(uuid.uuid4()),
            name="snap",
            url="http://127.0.0.1:8069",
            db_name="odoo",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
        )
        db.add(conn)
        db.commit()
        row = save_snapshot(
            db,
            connection_id=conn.id,
            resource_type="view",
            resource_key="view:1",
            label="test",
            payload={"view": {"id": 1}},
        )
        assert json.loads(row.payload_json)["view"]["id"] == 1
    finally:
        db.close()


def test_promote_sha256_mismatch_error_path() -> None:
    init_db()
    db = SessionLocal()
    try:
        conn = OdooConnection(
            id=str(uuid.uuid4()),
            name="sha",
            url="http://127.0.0.1:8069",
            db_name="odoo",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
        )
        db.add(conn)
        db.commit()
        zip_bytes = b"original"
        row = record_sandbox_validation(
            db,
            connection_id=conn.id,
            module_name="x_test",
            zip_bytes=zip_bytes,
        )
        with pytest.raises(ValueError, match="sha256 mismatch"):
            get_valid_validation(
                db,
                validation_id=row.id,
                connection_id=conn.id,
                zip_bytes=b"tampered",
            )
        assert sha256_bytes(zip_bytes) != sha256_bytes(b"tampered")
    finally:
        db.close()


def test_rpc_resilience_transport_classifiers() -> None:
    assert is_transport_rpc_error(OSError("connection timed out")) is True
    assert is_transport_rpc_error(ValueError("validation")) is False


def test_bulk_executor_abort_path() -> None:
    from app.bulk_suite.executor import execute_in_batches

    results_holder: list[int] = []

    def should_abort() -> bool:
        return bool(results_holder)

    def track_chunk(chunk: list[int]) -> list[PerRecordResult]:
        results_holder.append(1)
        return [PerRecordResult(id=i, display_name=str(i), ok=True) for i in chunk]

    results, aborted, pending = execute_in_batches(
        [1, 2, 3, 4],
        track_chunk,
        batch_size=2,
        sleep_ms=0,
        should_abort=should_abort,
    )
    assert aborted is True
    assert pending
    assert len(results) == 2


def test_domain_util_rejects_invalid_domain() -> None:
    from app.bulk_suite.domain_util import DomainParseError, parse_domain

    with pytest.raises(DomainParseError):
        parse_domain("{not-a-domain")
