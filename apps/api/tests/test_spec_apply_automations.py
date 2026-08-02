"""Unit tests for ModuleSpec safe automation apply (related_write mapping)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.spec_apply_ui import (
    UiApplyResult,
    _action_from_spec,
    _apply_safe_automations,
    _iter_safe_actions,
    _normalize_automation_trigger,
)


def test_normalize_trigger_aliases() -> None:
    assert _normalize_automation_trigger("create") == "on_create"
    assert _normalize_automation_trigger("write") == "on_write"
    assert _normalize_automation_trigger("Update") == "on_write"
    assert _normalize_automation_trigger("create_or_write") == "on_create_or_write"
    assert _normalize_automation_trigger("on_create") == "on_create"
    assert _normalize_automation_trigger("delete") == "on_unlink"
    assert _normalize_automation_trigger("bogus_trigger") is None


def test_action_without_kind_defaults_to_update_field() -> None:
    typed = _action_from_spec({"field": "x_status", "value": "done"})
    assert typed is not None
    assert typed.kind == "update_field"
    assert typed.field_name == "x_status"


def test_iter_safe_actions_from_domain_pack_shape() -> None:
    auto = {
        "name": "Mark vehicle rented",
        "model": "x_rent_contract",
        "safe_actions": [
            {
                "kind": "related_write",
                "relation_field": "x_vehicle_id",
                "field": "x_status",
                "value": "rented",
            }
        ],
    }
    actions = _iter_safe_actions(auto)
    assert len(actions) == 1
    typed = _action_from_spec(actions[0])
    assert typed is not None
    assert typed.kind == "related_write"
    assert typed.relation_field == "x_vehicle_id"
    assert typed.field_name == "x_status"
    assert typed.value == "rented"


def test_dotted_object_write_maps_to_related_write() -> None:
    typed = _action_from_spec(
        {"kind": "object_write", "field": "x_vehicle_id.x_status", "value": "available"}
    )
    assert typed is not None
    assert typed.kind == "related_write"
    assert typed.relation_field == "x_vehicle_id"
    assert typed.field_name == "x_status"


def test_unsupported_code_action_returns_none() -> None:
    assert _action_from_spec({"kind": "code", "code": "pass"}) is None


class _AutoFakeClient:
    def __init__(self) -> None:
        self.models = {"x_appointment"}
        self.created: list[Any] = []

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def create_automation(self, request: Any) -> Any:
        self.created.append(request)
        return SimpleNamespace(id=1)


def test_apply_safe_automations_accepts_create_trigger_alias() -> None:
    client = _AutoFakeClient()
    result = UiApplyResult()
    _apply_safe_automations(
        client,
        {
            "automations": [
                {
                    "name": "On appointment create",
                    "model": "x_appointment",
                    "trigger": "create",
                    "safe_actions": [
                        {"kind": "update_field", "field": "x_status", "value": "scheduled"}
                    ],
                }
            ]
        },
        result,
    )
    assert result.automations_created == 1
    assert client.created[0].trigger.value == "on_create"


def test_resolve_draft_model_name_strips_export_prefix() -> None:
    from app.spec_apply_ui import _resolve_draft_model_name

    class _M:
        def model_exists(self, m: str) -> bool:
            return m == "x_patient"

    assert _resolve_draft_model_name(_M(), "model_x_patient") == "x_patient"
    assert _resolve_draft_model_name(_M(), "x_patient") == "x_patient"
    assert _resolve_draft_model_name(_M(), "model_x_unknown") is None
