"""CMP-7 property fields service (fake RPC)."""

from __future__ import annotations

from typing import Any

from app.property_fields_service import write_properties_definition


class _FakeClient:
    def __init__(self) -> None:
        self.fields = {("x_parent", "x_properties_definition"): True}
        self.writes: list[tuple[list[int], dict[str, Any]]] = []

    def field_exists(self, model: str, name: str) -> bool:
        return (model, name) in self.fields

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        if model == "x_parent" and method == "write":
            self.writes.append((args[0], args[1]))
            return True
        raise AssertionError(f"{model}.{method}")


def test_write_properties_definition() -> None:
    client = _FakeClient()
    result = write_properties_definition(
        client,
        parent_model="x_parent",
        parent_record_id=7,
        definition_field="x_properties_definition",
        entries=[{"name": "size", "type": "char", "string": "Size"}],
    )
    assert result["property_count"] == 1
    assert client.writes[0][1]["x_properties_definition"][0]["name"] == "size"
