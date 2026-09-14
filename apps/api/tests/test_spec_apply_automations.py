"""Unit tests for ModuleSpec safe automation apply (related_write mapping)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.spec_apply_ui import (
    UiApplyResult,
    _action_from_spec,
    _apply_safe_automations,
    _iter_safe_actions,
    _live_filter_domain_broken,
    _normalize_automation_trigger,
    _scrub_live_broken_automations,
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
        self.activity_types: list[dict[str, Any]] = []

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def create_automation(self, request: Any) -> Any:
        self.created.append(request)
        return SimpleNamespace(id=1)

    def resolve_xml_id(self, xml_id: str) -> int:
        raise ValueError(f"Invalid xml_id {xml_id!r}")

    def list_activity_types(self, *, limit: int = 50) -> list[dict[str, Any]]:
        _ = limit
        return list(self.activity_types)


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


def test_apply_on_time_infers_date_from_filter_domain() -> None:
    client = _AutoFakeClient()
    result = UiApplyResult()
    _apply_safe_automations(
        client,
        {
            "automations": [
                {
                    "name": "Follow up deadline Engagement",
                    "model": "x_appointment",
                    "trigger": "on_time",
                    "filter_domain": (
                        "[('x_date_end', '!=', False), ('x_date_end', '<', 'now')]"
                    ),
                    "safe_actions": [
                        {"kind": "update_field", "field": "x_status", "value": "expired"}
                    ],
                }
            ]
        },
        result,
    )
    assert result.automations_created == 1
    assert client.created[0].trg_date_field_name == "x_date_end"
    assert not any("needs trg_date_field_name" in w for w in result.warnings)


def test_apply_on_time_falls_back_to_create_date() -> None:
    client = _AutoFakeClient()
    result = UiApplyResult()
    _apply_safe_automations(
        client,
        {
            "automations": [
                {
                    "name": "Follow up deadline Engagement",
                    "model": "x_appointment",
                    "trigger": "on_time",
                    "filter_domain": "[('x_status', '=', 'in_progress')]",
                    "safe_actions": [
                        {"kind": "update_field", "field": "x_status", "value": "expired"}
                    ],
                }
            ]
        },
        result,
    )
    assert result.automations_created == 1
    assert client.created[0].trg_date_field_name == "create_date"


def test_apply_next_activity_skips_foreign_model_activity_type() -> None:
    client = _AutoFakeClient()
    client.activity_types = [
        {"id": 1, "name": "Call", "res_model": "crm.lead"},
        {"id": 4, "name": "To Do", "res_model": False},
    ]
    result = UiApplyResult()
    _apply_safe_automations(
        client,
        {
            "automations": [
                {
                    "name": "Notify on Project completed",
                    "model": "x_appointment",
                    "trigger": "on_write",
                    "safe_actions": [
                        {"kind": "next_activity", "summary": "Review completed"}
                    ],
                }
            ]
        },
        result,
    )
    assert result.automations_created == 1
    assert client.created[0].action.activity_type_id == 4


def test_apply_next_activity_defaults_todo_type() -> None:
    client = _AutoFakeClient()
    client.activity_types = [{"id": 4, "name": "To Do"}]
    result = UiApplyResult()
    _apply_safe_automations(
        client,
        {
            "automations": [
                {
                    "name": "Follow up deadline Engagement",
                    "model": "x_appointment",
                    "trigger": "on_write",
                    "safe_actions": [
                        {"kind": "next_activity", "summary": "deadline engagement"}
                    ],
                }
            ]
        },
        result,
    )
    assert result.automations_created == 1
    action = client.created[0].action
    assert action.kind == "create_activity"
    assert action.activity_type_id == 4
    assert action.summary == "deadline engagement"
    assert not any("unsupported/incomplete" in w for w in result.warnings)


def test_resolve_draft_model_name_strips_export_prefix() -> None:
    from app.spec_apply_ui import _resolve_draft_model_name

    class _M:
        def model_exists(self, m: str) -> bool:
            return m == "x_patient"

    assert _resolve_draft_model_name(_M(), "model_x_patient") == "x_patient"
    assert _resolve_draft_model_name(_M(), "x_patient") == "x_patient"


def test_broken_rate_unit_infix_domain_is_detected() -> None:
    assert _live_filter_domain_broken("['x_rate_unit in ('hour','day')']") is True
    assert _live_filter_domain_broken("[('x_status', '=', 'open')]") is False
    assert _live_filter_domain_broken("[]") is False


def test_apply_skips_invalid_filter_domain() -> None:
    client = _AutoFakeClient()
    result = UiApplyResult()
    _apply_safe_automations(
        client,
        {
            "automations": [
                {
                    "name": "Calculate Engagement Total Amount",
                    "model": "x_appointment",
                    "trigger": "on_write",
                    "filter_domain": "['x_rate_unit in ('hour','day')']",
                    "safe_actions": [
                        {"kind": "update_field", "field": "x_name", "value": "x"}
                    ],
                }
            ]
        },
        result,
    )
    assert client.created == []
    assert result.automations_created == 0
    assert any("invalid filter_domain" in w for w in result.warnings)


class _ScrubFake:
    def __init__(self) -> None:
        self.rows = [
            {
                "id": 11,
                "name": "Calculate Engagement Total Amount",
                "filter_domain": "['x_rate_unit in ('hour','day')']",
                "filter_pre_domain": False,
            },
            {
                "id": 12,
                "name": "Follow up deadline Engagement",
                "filter_domain": "[('x_end_date', '<', 'now')]",
                "filter_pre_domain": False,
            },
        ]
        self.unlinked: list[list[int]] = []

    def model_exists(self, model: str) -> bool:
        return model == "base.automation"

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        if method == "search_read":
            return list(self.rows)
        if method == "unlink":
            ids = list(args[0])
            self.unlinked.append(ids)
            self.rows = [r for r in self.rows if r["id"] not in ids]
            return True
        return []


def test_scrub_unlinks_leftover_broken_automations() -> None:
    client = _ScrubFake()
    result = UiApplyResult()
    _scrub_live_broken_automations(client, {"models": [{"model": "x_engagement"}]}, result)
    assert client.unlinked == [[11]]
    assert result.automations_scrubbed == 1
    assert any("Calculate Engagement Total Amount" in w for w in result.warnings)


class _RequiredFake:
    def __init__(self) -> None:
        self.rows = [
            {"id": 1, "name": "x_name", "required": True},
            {"id": 2, "name": "x_rate_hour", "required": True},
            {"id": 3, "name": "x_session_type", "required": True},
        ]
        self.writes: list[Any] = []

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        if method == "search_read":
            return list(self.rows)
        if method == "write":
            self.writes.append((args[0], args[1]))
            return True
        return []


def test_relax_leftover_required_fields_not_in_spec() -> None:
    from app.spec_apply_ui import _relax_leftover_required_fields

    client = _RequiredFake()
    result = UiApplyResult()
    spec = {
        "models": [
            {
                "model": "x_engagement",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ]
    }
    _relax_leftover_required_fields(client, spec, result)
    assert result.fields_relaxed == 2
    assert client.writes == [([2, 3], {"required": False})]
    assert any("x_rate_hour" in w for w in result.warnings)
