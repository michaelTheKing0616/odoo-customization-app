import json

import pytest

from app.bridge.spec_import import SpecError, import_spec

OPENAPI = {
    "openapi": "3.0.0",
    "info": {"title": "Acme"},
    "servers": [{"url": "https://api.acme.com/v1"}],
    "components": {
        "securitySchemes": {"k": {"type": "apiKey"}, "o": {"type": "oauth2"}},
        "schemas": {
            "Order": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "total": {"type": "number"},
                    "placed": {"type": "string", "format": "date-time"},
                    "customer": {"$ref": "#/components/schemas/C"},
                },
            },
            "C": {},
        },
    },
    "paths": {
        "/v1/orders": {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Order"},
                                }
                            }
                        }
                    }
                }
            },
            "post": {},
        },
        "/v1/orders/{id}": {"patch": {}, "get": {}},
    },
}


def test_openapi():
    d = import_spec(json.dumps(OPENAPI))
    assert (
        d["name"] == "Acme"
        and d["base_url"] == "https://api.acme.com/v1"
        and d["auth"] == ["api_key", "oauth2"]
    )
    o = d["entities"]["orders"]
    assert o["read"] == "/v1/orders" and o["create"] and o["update"]
    assert o["fields"] == {
        "id": "integer",
        "total": "float",
        "placed": "datetime",
        "customer": "many2one",
    }


def test_postman_and_sample():
    pm = {
        "info": {"name": "Shop"},
        "auth": {"type": "bearer"},
        "item": [
            {
                "item": [
                    {
                        "request": {
                            "method": "GET",
                            "url": {
                                "raw": "https://x.io/api/products",
                                "path": ["api", "products"],
                            },
                        }
                    },
                    {
                        "request": {
                            "method": "POST",
                            "url": {
                                "raw": "https://x.io/api/products",
                                "path": ["api", "products"],
                            },
                            "body": {"raw": '{"sku": "A1", "price": 2.5}'},
                        }
                    },
                ]
            }
        ],
    }
    d = import_spec(json.dumps(pm))
    assert d["base_url"] == "https://x.io" and d["entities"]["products"]["fields"] == {
        "sku": "char",
        "price": "float",
    }
    s = import_spec(json.dumps({"invoices": [{"id": 1, "due": "2026-10-01", "paid": False}]}))
    assert s["entities"]["invoices"]["fields"] == {
        "id": "integer",
        "due": "date",
        "paid": "boolean",
    }


def test_checks_refuse_unsafe():
    bad = dict(OPENAPI, servers=[{"url": "http://api.acme.com"}])
    with pytest.raises(SpecError):
        import_spec(json.dumps(bad))
    with pytest.raises(SpecError):
        import_spec(json.dumps(dict(OPENAPI, servers=[{"url": "https://192.168.1.4"}])))
    with pytest.raises(SpecError):
        import_spec("just text")
