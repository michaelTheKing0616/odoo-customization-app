"""CMP-9 bulk scan find tests."""

from __future__ import annotations

from typing import Any

from app.bulk_suite.scan import find_records_by_field


class _FakeClient:
    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        assert model == "x_item"
        assert method == "search_read"
        assert args[0] == [("x_barcode", "=", "ABC123")]
        return [{"id": 9, "x_barcode": "ABC123", "display_name": "Item 9"}]


def test_find_records_by_field() -> None:
    data = find_records_by_field(
        _FakeClient(),
        model="x_item",
        field="x_barcode",
        value="ABC123",
    )
    assert data["count"] == 1
    assert data["records"][0]["id"] == 9
