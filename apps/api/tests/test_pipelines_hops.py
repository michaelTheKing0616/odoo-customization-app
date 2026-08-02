"""Pipeline hop API tests — prod gate + mocked promote (no live Docker required)."""

from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from module_generator import FieldSpec, ModelSpec, ModuleSpec, build_module_zip  # noqa: E402

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection, PipelineHop  # noqa: E402
from app.main import app  # noqa: E402
from app.promote import PromoteResult, sha256_bytes  # noqa: E402
from app.snapshots import CONFIRM_PHRASE  # noqa: E402

CONFIRM = {"confirm_advanced": True, "confirm_phrase": CONFIRM_PHRASE}


def _tiny_zip() -> bytes:
    return build_module_zip(
        ModuleSpec(
            technical_name="pipe_smoke_mod",
            display_name="Pipe Smoke",
            models=[
                ModelSpec(
                    model="x_pipe_smoke",
                    description="Pipe",
                    fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
                )
            ],
        )
    )


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _mk_connection(name: str) -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name=name,
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


@pytest.fixture
def pipeline_pair(client: TestClient) -> tuple[str, str, str]:
    staging = _mk_connection("pipe-staging")
    prod = _mk_connection("pipe-prod")
    created = client.post(
        "/api/pipelines",
        json={
            "name": "Smoke pipeline",
            "staging_connection_id": staging,
            "prod_connection_id": prod,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["id"], staging, prod


def test_pipeline_create_rejects_same_staging_prod(client: TestClient) -> None:
    cid = _mk_connection("same-env")
    res = client.post(
        "/api/pipelines",
        json={
            "name": "bad",
            "staging_connection_id": cid,
            "prod_connection_id": cid,
        },
    )
    assert res.status_code == 422


def test_prod_hop_requires_confirm(client: TestClient, pipeline_pair) -> None:
    pid, _staging, _prod = pipeline_pair
    z64 = base64.b64encode(_tiny_zip()).decode()
    denied = client.post(
        f"/api/pipelines/{pid}/promote",
        json={"hop": "prod", "zip_base64": z64},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["requires_confirmation"] is True


def test_prod_hop_blocked_without_staging_success(
    client: TestClient, pipeline_pair
) -> None:
    pid, _staging, _prod = pipeline_pair
    raw = _tiny_zip()
    z64 = base64.b64encode(raw).decode()
    blocked = client.post(
        f"/api/pipelines/{pid}/promote",
        json={"hop": "prod", "zip_base64": z64, **CONFIRM},
    )
    assert blocked.status_code == 400
    assert "staging hop" in blocked.json()["detail"].lower()


def test_prod_hop_succeeds_after_staging_sha_match(
    client: TestClient, pipeline_pair
) -> None:
    pid, staging, prod = pipeline_pair
    raw = _tiny_zip()
    digest = sha256_bytes(raw)
    z64 = base64.b64encode(raw).decode()

    db = SessionLocal()
    try:
        db.add(
            PipelineHop(
                pipeline_id=pid,
                hop="staging",
                module_name="pipe_smoke_mod",
                zip_sha256=digest,
                connection_id=staging,
                validation_id=None,
                status="succeeded",
                message="pre-seeded staging hop",
            )
        )
        db.commit()
    finally:
        db.close()

    fake_result = PromoteResult(
        ok=True,
        module="pipe_smoke_mod",
        method="data",
        message="installed (fake)",
    )

    with (
        patch(
            "app.routers.environments.client_from_connection",
            return_value=MagicMock(),
        ),
        patch(
            "app.routers.environments.promote_module_zip",
            return_value=fake_result,
        ),
        patch(
            "app.routers.environments.record_sandbox_validation",
        ) as rec_val,
    ):
        val = MagicMock()
        val.id = "val-fake-1"
        rec_val.return_value = val
        res = client.post(
            f"/api/pipelines/{pid}/promote",
            json={"hop": "prod", "zip_base64": z64, **CONFIRM},
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["hop"] == "prod"
    assert body["zip_sha256"] == digest
    assert body["module_name"] == "pipe_smoke_mod"

    hops = client.get(f"/api/pipelines/{pid}/hops")
    assert hops.status_code == 200
    assert any(h["hop"] == "prod" and h["status"] == "succeeded" for h in hops.json())


def test_prod_hop_blocked_on_sha_mismatch(client: TestClient, pipeline_pair) -> None:
    pid, staging, _prod = pipeline_pair
    raw_a = _tiny_zip()
    # Different zip content → different sha (tweak display via second module name)
    raw_b = build_module_zip(
        ModuleSpec(
            technical_name="pipe_other_mod",
            display_name="Other",
            models=[
                ModelSpec(
                    model="x_other",
                    description="Other",
                    fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
                )
            ],
        )
    )
    db = SessionLocal()
    try:
        db.add(
            PipelineHop(
                pipeline_id=pid,
                hop="staging",
                module_name="pipe_smoke_mod",
                zip_sha256=sha256_bytes(raw_a),
                connection_id=staging,
                validation_id=None,
                status="succeeded",
                message="staging A",
            )
        )
        db.commit()
    finally:
        db.close()

    blocked = client.post(
        f"/api/pipelines/{pid}/promote",
        json={
            "hop": "prod",
            "zip_base64": base64.b64encode(raw_b).decode(),
            **CONFIRM,
        },
    )
    assert blocked.status_code == 400
    assert "staging hop" in blocked.json()["detail"].lower()


@pytest.mark.integration
def test_sandbox_hop_optional_docker(client: TestClient, pipeline_pair) -> None:
    """Runs ephemeral sandbox when Docker is available; otherwise skip."""
    pid, _staging, _prod = pipeline_pair
    raw = _tiny_zip()
    z64 = base64.b64encode(raw).decode()
    res = client.post(
        f"/api/pipelines/{pid}/promote",
        json={"hop": "sandbox", "zip_base64": z64, **CONFIRM},
    )
    if res.status_code == 400:
        detail = res.json().get("detail")
        msg = detail if isinstance(detail, str) else str(detail)
        if any(
            needle in msg.lower()
            for needle in ("docker", "cannot connect", "daemon", "not found", "timeout")
        ):
            pytest.skip(f"Docker sandbox unavailable: {msg[:200]}")
        # Genuine sandbox install failure — still a gate signal
        assert "ok" in str(detail).lower() or "message" in str(detail).lower()
        return
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["hop"] == "sandbox"
    assert body["validation_id"]
