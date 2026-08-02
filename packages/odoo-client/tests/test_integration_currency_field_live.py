"""Live currency_field inject proofs (W0 gap close).

Odoo 19+: monetary create with currency_field persisted.
Odoo 16: currency_field omitted (column absent) — no crash.
"""

from __future__ import annotations

import os
import uuid

import pytest

from odoo_client import ConnectionConfig, CreateFieldRequest, CreateModelRequest, FieldType, OdooClient
from odoo_client.client import OdooClientError


def _client(url: str, db: str, user_env: str, pass_env: str) -> OdooClient:
    c = OdooClient(
        ConnectionConfig(
            url=url,
            db=db,
            username=os.environ.get(user_env, "admin"),
            password=os.environ.get(pass_env, "admin"),
        )
    )
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo not reachable: {exc}")
    return c


@pytest.fixture(scope="module")
def client19() -> OdooClient:
    c = _client(
        os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
        os.environ.get("ODOO_DB", "odoo_dev"),
        "ODOO_USER",
        "ODOO_PASSWORD",
    )
    if c.capabilities.major != 19:
        pytest.skip(f"Expected major 19, got {c.capabilities.major}")
    return c


@pytest.fixture(scope="module")
def client16() -> OdooClient:
    c = _client(
        os.environ.get("ODOO16_URL", "http://127.0.0.1:8072"),
        os.environ.get("ODOO16_DB", "odoo16_dev"),
        "ODOO16_USER",
        "ODOO16_PASSWORD",
    )
    if c.capabilities.major != 16:
        pytest.skip(f"Expected major 16, got {c.capabilities.major}")
    return c


@pytest.mark.integration
def test_currency_field_persisted_on_monetary_odoo19(client19: OdooClient) -> None:
    suffix = uuid.uuid4().hex[:6]
    model = f"x_cur19_{suffix}"
    client19.create_model(CreateModelRequest(model=model, name=f"Cur19 {suffix}"))
    client19.create_field(
        CreateFieldRequest(
            model=model,
            name="x_currency_id",
            ttype=FieldType.MANY2ONE,
            field_description="Currency",
            relation="res.currency",
        )
    )
    info = client19.create_field(
        CreateFieldRequest(
            model=model,
            name="x_amount",
            ttype=FieldType.MONETARY,
            field_description="Amount",
            currency_field="x_currency_id",
        )
    )
    rows = client19.execute_kw(
        "ir.model.fields",
        "read",
        [[info.id]],
        {"fields": ["name", "ttype", "currency_field"]},
    )
    assert rows
    assert rows[0]["ttype"] == "monetary"
    assert rows[0].get("currency_field") == "x_currency_id"


@pytest.mark.integration
def test_currency_field_omitted_safely_on_odoo16(client16: OdooClient) -> None:
    """Odoo 16 has no ir.model.fields.currency_field — create must not raise."""
    suffix = uuid.uuid4().hex[:6]
    model = f"x_cur16_{suffix}"
    client16.create_model(CreateModelRequest(model=model, name=f"Cur16 {suffix}"))
    # Ensure currency m2o exists for monetary semantics where possible
    client16.create_field(
        CreateFieldRequest(
            model=model,
            name="x_currency_id",
            ttype=FieldType.MANY2ONE,
            field_description="Currency",
            relation="res.currency",
        )
    )
    info = client16.create_field(
        CreateFieldRequest(
            model=model,
            name="x_amount",
            ttype=FieldType.MONETARY,
            field_description="Amount",
            currency_field="x_currency_id",  # client must omit on 16
        )
    )
    cols = client16._ir_model_fields_columns(["currency_field"])  # noqa: SLF001
    assert "currency_field" not in cols
    rows = client16.execute_kw(
        "ir.model.fields",
        "read",
        [[info.id]],
        {"fields": ["name", "ttype"]},
    )
    assert rows and rows[0]["ttype"] == "monetary"
