"""Live RPC smoke — BLK-9 ID generator on Docker Odoo 19."""

from __future__ import annotations

import os
import uuid

import pytest

from odoo_client import ConnectionConfig, CreateFieldRequest, FieldType, OdooClient
from odoo_client.client import OdooClientError

from app.id_generator import IdGeneratorConfig, run_live_id_generator

MODEL = "x_blk_wf_item"
CODE_FIELD = "x_ref_code"
NAME_FIELD = "x_name"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@pytest.fixture(scope="module")
def client() -> OdooClient:
    config = ConnectionConfig(
        url=_env("ODOO_URL", "http://127.0.0.1:8069"),
        db=_env("ODOO_DB", "odoo_dev"),
        username=_env("ODOO_USER", "admin"),
        password=_env("ODOO_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 19 not reachable for BLK-9 smoke: {exc}")
    if not str(c.server_version().get("server_version", "")).startswith("19"):
        pytest.skip("Expected Odoo 19")
    return c


@pytest.fixture(scope="module")
def workflow_model(client: OdooClient) -> None:
    if not client.model_exists(MODEL):
        pytest.skip(f"{MODEL} not installed — promote blk_wf_smoke for BLK-9 live smoke")


@pytest.fixture(scope="module")
def ref_code_field(client: OdooClient, workflow_model: None) -> None:
    if not client.model_exists(MODEL):
        pytest.skip(f"{MODEL} not installed — run blk_wf_smoke fixture stack first")
    if CODE_FIELD not in client.execute_kw(MODEL, "fields_get", [[CODE_FIELD]]):
        client.create_field(
            CreateFieldRequest(
                model=MODEL,
                name=CODE_FIELD,
                field_description="Reference code",
                ttype=FieldType.CHAR,
            )
        )


@pytest.mark.integration
def test_live_id_generator_assigns_and_idempotent(
    client: OdooClient, ref_code_field: None
) -> None:
    record_ids = [
        int(
            client.execute_kw(
                MODEL,
                "create",
                [{"x_name": f"Inventory Item {uuid.uuid4().hex[:5]}", "x_status": "draft"}],
            )
        )
        for _ in range(3)
    ]
    cfg = IdGeneratorConfig(prefix="INV", separator="-", padding=4, initials_length=3)
    try:
        dry = run_live_id_generator(
            client,
            model=MODEL,
            name_field=NAME_FIELD,
            code_field=CODE_FIELD,
            config=cfg,
            record_ids=record_ids,
            dry_run=True,
        )
        assert dry.changed == 3
        codes = [a.new_code for a in dry.assignments if a.new_code]
        assert len(codes) == len(set(codes))

        live = run_live_id_generator(
            client,
            model=MODEL,
            name_field=NAME_FIELD,
            code_field=CODE_FIELD,
            config=cfg,
            record_ids=record_ids,
            dry_run=False,
        )
        assert live.succeeded == 3
        rows = client.execute_kw(
            MODEL,
            "read",
            [record_ids],
            {"fields": [CODE_FIELD, NAME_FIELD]},
        )
        assert all(r.get(CODE_FIELD) for r in rows)

        again = run_live_id_generator(
            client,
            model=MODEL,
            name_field=NAME_FIELD,
            code_field=CODE_FIELD,
            config=cfg,
            record_ids=record_ids,
            dry_run=True,
        )
        assert again.changed == 0
    finally:
        client.execute_kw(MODEL, "unlink", [record_ids])
