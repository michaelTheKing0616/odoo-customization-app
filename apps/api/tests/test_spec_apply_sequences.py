"""CMP-1 spec_apply ir.sequence parity (fake RPC)."""

from __future__ import annotations

from typing import Any

from odoo_client import OdooClient

from app.spec_apply_ui import apply_module_spec_ui


class _FakeClient(OdooClient):
    def __init__(self) -> None:
        self._models: set[str] = {"x_order"}
        self._fields: dict[str, set[str]] = {"x_order": {"x_name", "x_status"}}
        self.sequences: list[dict[str, Any]] = []

    def model_exists(self, model: str) -> bool:
        return model in self._models

    def field_exists(self, model: str, field: str) -> bool:
        return field in self._fields.get(model, set())

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        _ = kwargs
        if model == "ir.sequence" and method == "search":
            code = args[0][0][2] if args and args[0] else None
            for row in self.sequences:
                if row.get("code") == code:
                    return [row["id"]]
            return []
        if model == "ir.sequence" and method == "create":
            vals = args[0]
            row = {"id": len(self.sequences) + 1, **vals}
            self.sequences.append(row)
            return row["id"]
        if model == "ir.sequence" and method == "write":
            seq_id, vals = args[0][0], args[0][1]
            for row in self.sequences:
                if row["id"] == seq_id:
                    row.update(vals)
            return True
        if model == "ir.sequence" and method == "read":
            seq_id = args[0][0]
            return [r for r in self.sequences if r["id"] == seq_id]
        raise NotImplementedError(f"{model}.{method}")


def test_spec_apply_creates_workflow_sequence() -> None:
    client = _FakeClient()
    spec = {
        "technical_name": "orders",
        "display_name": "Orders",
        "models": [
            {
                "model": "x_order",
                "description": "Order",
                "mode": "new",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {"name": "x_code", "ttype": "char", "string": "Reference"},
                ],
            }
        ],
    }
    # Patch apply_project_spec path — models already exist on fake client
    from app import spec_apply_ui as mod

    original = mod.apply_project_spec

    def _noop_apply(_client: OdooClient, _spec: dict[str, Any]) -> Any:
        from app.project_apply import ApplyResult

        return ApplyResult()

    mod.apply_project_spec = _noop_apply
    try:
        result = apply_module_spec_ui(client, spec)
    finally:
        mod.apply_project_spec = original

    assert result.sequences_created == 1
    assert client.sequences
    assert client.sequences[0]["code"] == "x_order_ref"
    assert client.sequences[0]["prefix"] == "ORDER/"
