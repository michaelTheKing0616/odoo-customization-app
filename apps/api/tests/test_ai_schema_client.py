"""PR-A schema_client contract — model_exists, relation_ok ±, writable, TTL."""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.no_app_db

from app.ai_schema_client import (  # noqa: E402
    SCHEMA_CATALOG_TTL_S,
    CatalogSchemaClient,
    DenySchemaClient,
    FakeSchemaClient,
    schema_client_for_draft,
)


def _partner_fake() -> FakeSchemaClient:
    return FakeSchemaClient(
        models={"res.partner", "res.users", "x_ticket"},
        fields={
            "x_ticket": {
                "x_partner_id": {
                    "type": "many2one",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "readonly": False,
                },
                "x_display": {
                    "type": "char",
                    "ttype": "char",
                    "readonly": True,
                    "related": "x_partner_id.name",
                },
                "x_bad_rel": {
                    "type": "many2one",
                    "ttype": "many2one",
                    "relation": "account.move",
                    "readonly": False,
                },
            },
            "res.partner": {
                "name": {"type": "char", "ttype": "char", "readonly": False},
            },
        },
    )


def test_model_exists_known_and_unknown() -> None:
    client = _partner_fake()
    assert client.model_exists("res.partner") is True
    assert client.model_exists("x_invent_nowhere") is False


def test_fields_get_known_and_unknown() -> None:
    client = _partner_fake()
    assert "x_partner_id" in client.fields_get("x_ticket")
    assert client.fields_get("x_invent_nowhere") == {}


def test_relation_ok_positive_and_negative() -> None:
    client = _partner_fake()
    assert client.relation_ok("x_ticket", "x_partner_id", "res.partner") is True
    assert client.relation_ok("x_ticket", "x_partner_id", "res.users") is False
    assert client.relation_ok("x_ticket", "missing", "res.partner") is False
    assert client.relation_ok("x_ticket", "x_bad_rel", "res.partner") is False


def test_field_is_writable_rejects_readonly_related() -> None:
    client = _partner_fake()
    assert client.field_is_writable("x_ticket", "x_partner_id") is True
    assert client.field_is_writable("x_ticket", "x_display") is False
    assert client.field_is_writable("x_ticket", "nope") is False


def test_view_has_field_is_stub_false() -> None:
    client = _partner_fake()
    assert client.view_has_field("x_ticket", "x_partner_id") is False


def test_factory_prefers_injected_fake() -> None:
    fake = _partner_fake()
    draft = {"_schema_client": fake}
    assert schema_client_for_draft(draft) is fake


def test_factory_ttl_denies_stale_catalog() -> None:
    now = time.time()
    draft = {
        "_connection_catalog": {
            "available_models": ["res.partner", "sale.order"],
            "stock": [{"model": "res.partner"}],
            "loaded_at": now - SCHEMA_CATALOG_TTL_S - 10,
        }
    }
    client = schema_client_for_draft(draft, now=now)
    assert isinstance(client, DenySchemaClient)
    assert client.reason == "stale_or_missing_catalog_ts"
    assert client.model_exists("res.partner") is False


def test_factory_fresh_catalog_allows_model_exists() -> None:
    now = time.time()
    draft = {
        "_connection_catalog": {
            "available_models": ["res.partner"],
            "stock": [],
            "loaded_at": now - 60,
        }
    }
    client = schema_client_for_draft(draft, now=now)
    assert isinstance(client, CatalogSchemaClient)
    assert client.model_exists("res.partner") is True
    # Without field map, relation_ok stays deny (no invent from model list alone)
    assert client.relation_ok("x_ticket", "x_partner_id", "res.partner") is False


def test_factory_missing_loaded_at_denies() -> None:
    draft = {
        "_connection_catalog": {
            "available_models": ["res.partner"],
            "stock": [],
        }
    }
    client = schema_client_for_draft(draft)
    assert isinstance(client, DenySchemaClient)


def test_catalog_relation_ok_with_field_map() -> None:
    now = time.time()
    client = CatalogSchemaClient(
        models={"x_ticket", "res.partner"},
        loaded_at=now,
        fields={
            "x_ticket": {
                "x_partner_id": {
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "readonly": False,
                }
            }
        },
    )
    assert client.relation_ok("x_ticket", "x_partner_id", "res.partner") is True
    assert client.field_is_writable("x_ticket", "x_partner_id") is True
