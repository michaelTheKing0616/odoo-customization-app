"""Live apply parity: draft record_rules → ir.rule RPC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from odoo_client import OdooClient

from app.spec_apply_ui import UiApplyResult, _apply_draft_record_rules


@dataclass
class _FakeRule:
    id: int
    name: str
    model: str


class _FakeClient(OdooClient):
    def __init__(self) -> None:
        self._models: set[str] = {"x_branch"}
        self.rules: list[_FakeRule] = []
        self.created: list[Any] = []

    def model_exists(self, model: str) -> bool:
        return model in self._models

    def list_record_rules(self, *, model: str, limit: int = 50) -> list[_FakeRule]:
        _ = limit
        return [r for r in self.rules if r.model == model]

    def create_record_rule(self, request: Any) -> _FakeRule:
        self.created.append(request)
        row = _FakeRule(
            id=len(self.rules) + 1,
            name=str(request.name),
            model=str(request.model),
        )
        self.rules.append(row)
        return row


def test_apply_draft_record_rules_creates_ir_rule() -> None:
    client = _FakeClient()
    result = UiApplyResult()
    spec = {
        "record_rules": [
            {
                "name": "Multi-company (x_branch)",
                "model": "x_branch",
                "domain_force": (
                    "['|', ('x_company_id', '=', False), "
                    "('x_company_id', 'in', company_ids)]"
                ),
            }
        ]
    }
    _apply_draft_record_rules(client, spec, result)
    assert result.record_rules_created == 1
    assert len(client.created) == 1
    assert client.created[0].domain_force == spec["record_rules"][0]["domain_force"]


def test_apply_draft_record_rules_idempotent() -> None:
    client = _FakeClient()
    client.rules.append(_FakeRule(id=1, name="Multi-company (x_branch)", model="x_branch"))
    result = UiApplyResult()
    spec = {
        "record_rules": [
            {
                "name": "Multi-company (x_branch)",
                "model": "x_branch",
                "domain_force": "['|', ('x_company_id', '=', False), ('x_company_id', 'in', company_ids)]",
            }
        ]
    }
    _apply_draft_record_rules(client, spec, result)
    assert result.record_rules_created == 0
    assert result.skipped == ["record_rule:x_branch:Multi-company (x_branch)"]
