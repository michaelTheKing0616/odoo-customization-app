"""Field helper unit tests (fake RPC)."""

from __future__ import annotations

from typing import Any

from odoo_client import CreateFieldRequest, FieldType
from odoo_client.client import OdooClientError

from app.field_helpers import ensure_currency_field_for_monetary, list_related_paths


class _FakeClient:
    def __init__(self) -> None:
        self.fields: dict[tuple[str, str], dict[str, Any]] = {}
        self.models = {"x_test": True}
        self.created: list[CreateFieldRequest] = []

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def field_exists(self, model: str, name: str) -> bool:
        return (model, name) in self.fields

    def create_field(self, request: CreateFieldRequest) -> Any:
        self.created.append(request)
        self.fields[(request.model, request.name)] = {
            "name": request.name,
            "ttype": request.ttype.value,
        }

        class _Out:
            id = 1
            name = request.name

        return _Out()

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
        if model == "x_test" and method == "fields_get":
            return {
                "partner_id": {
                    "type": "many2one",
                    "relation": "res.partner",
                    "string": "Partner",
                }
            }
        if model == "res.partner" and method == "fields_get":
            return {
                "country_id": {
                    "type": "many2one",
                    "relation": "res.country",
                    "string": "Country",
                },
                "email": {"type": "char", "string": "Email"},
            }
        raise OdooClientError(f"unexpected {model}.{method}")


def test_list_related_paths_depth_two() -> None:
    client = _FakeClient()
    paths = list_related_paths(client, "x_test", depth=2)  # type: ignore[arg-type]
    labels = {p["path"] for p in paths}
    assert "partner_id" in labels
    assert "partner_id.country_id" in labels
    assert "partner_id.email" in labels


def test_ensure_currency_creates_once() -> None:
    client = _FakeClient()
    name, created = ensure_currency_field_for_monetary(client, "x_test")  # type: ignore[arg-type]
    assert created is True
    assert name == "x_currency_id"
    name2, created2 = ensure_currency_field_for_monetary(client, "x_test")  # type: ignore[arg-type]
    assert created2 is False
    assert name2 == "x_currency_id"
    assert len(client.created) == 1
    assert client.created[0].ttype == FieldType.MANY2ONE
