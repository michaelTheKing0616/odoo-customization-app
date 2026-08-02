"""Unit tests for ModuleSpec smart-button inject (no live Odoo)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from odoo_client.view_arch import ButtonNode

from app.spec_apply_ui import (
    UiApplyResult,
    _apply_smart_buttons,
    _ensure_m2o_on_target_for_smart_button,
    _inject_button_box,
    _normalize_smart_button,
)


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.models: set[str] = set()
        self.fields: set[tuple[str, str]] = set()
        self.created_fields: list[Any] = []
        self.bundles: list[Any] = []

    def inject_smart_buttons_into_form(self, model: str, nodes: list[Any], **kwargs: Any):
        self.calls.append((model, nodes, kwargs))
        return SimpleNamespace(name=f"{model}.studio.smart_buttons", id=7)

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def field_exists(self, model: str, name: str) -> bool:
        return (model, name) in self.fields

    def create_field(self, request: Any) -> Any:
        self.created_fields.append(request)
        self.fields.add((request.model, request.name))
        return SimpleNamespace(id=len(self.created_fields), name=request.name)

    def create_smart_button_bundle(self, request: Any) -> Any:
        self.bundles.append(request)
        return SimpleNamespace(
            window_action=SimpleNamespace(id=100 + len(self.bundles)),
            count_field=f"{request.one2many_field}_count"
            if request.one2many_field
            else None,
        )


def test_inject_button_box_uses_inherit_not_primary_write() -> None:
    client = _FakeClient()
    result = UiApplyResult()
    nodes = [
        ButtonNode(
            string="Contracts",
            name="55",
            type="action",
            class_name="oe_stat_button",
            icon="fa-list",
        )
    ]
    _inject_button_box(client, "res.partner", nodes, result)
    assert len(client.calls) == 1
    assert client.calls[0][0] == "res.partner"
    assert result.views_updated == 1
    assert any("inherit" in w.lower() for w in result.warnings)
    assert any("res.partner" in w for w in result.warnings)


def test_inject_button_box_custom_model_no_stock_warning() -> None:
    client = _FakeClient()
    result = UiApplyResult()
    nodes = [
        ButtonNode(
            string="Payments",
            name="56",
            type="action",
            class_name="oe_stat_button",
        )
    ]
    _inject_button_box(client, "x_rent_contract", nodes, result)
    assert result.views_updated == 1
    assert not any("primary" in w.lower() for w in result.warnings)


def test_normalize_smart_button_accepts_api_aliases() -> None:
    norm = _normalize_smart_button(
        {
            "source_model": "x_patient",
            "target_model": "x_appointment",
            "field": "x_patient_id",
            "label": "Appointments",
        }
    )
    assert norm["on_model"] == "x_patient"
    assert norm["related_model"] == "x_appointment"
    assert norm["relation_field"] == "x_patient_id"


def test_ensure_m2o_creates_missing_field_on_target() -> None:
    client = _FakeClient()
    client.models |= {"x_patient", "x_appointment"}
    result = UiApplyResult()
    rel = _ensure_m2o_on_target_for_smart_button(
        client,
        {
            "on_model": "x_patient",
            "related_model": "x_appointment",
            "relation_field": "x_patient_id",
            "label": "Patient",
        },
        result,
    )
    assert rel == "x_patient_id"
    assert ("x_appointment", "x_patient_id") in client.fields
    assert result.fields_created == 1


def test_ensure_m2o_creates_inverse_when_fk_on_source() -> None:
    """Hospital AI mistake: x_doctor_id on patient, button patient→doctor."""
    client = _FakeClient()
    client.models |= {"x_patient", "x_doctor"}
    client.fields.add(("x_patient", "x_doctor_id"))
    result = UiApplyResult()
    rel = _ensure_m2o_on_target_for_smart_button(
        client,
        {
            "on_model": "x_patient",
            "related_model": "x_doctor",
            "relation_field": "x_doctor_id",
            "label": "Doctors",
        },
        result,
    )
    assert rel == "x_patient_id"
    assert ("x_doctor", "x_patient_id") in client.fields


def test_apply_smart_buttons_uses_aliases_and_creates_m2o() -> None:
    client = _FakeClient()
    client.models |= {"x_patient", "x_appointment"}
    result = UiApplyResult()
    _apply_smart_buttons(
        client,
        {
            "smart_buttons": [
                {
                    "source_model": "x_patient",
                    "target_model": "x_appointment",
                    "relation_field": "x_patient_id",
                    "label": "Appointments",
                }
            ]
        },
        result,
    )
    assert result.smart_buttons == 1
    assert len(client.bundles) == 1
    assert client.bundles[0].relation_field == "x_patient_id"
    assert ("x_appointment", "x_patient_id") in client.fields
    assert any(c[0] == "x_patient" for c in client.calls)
