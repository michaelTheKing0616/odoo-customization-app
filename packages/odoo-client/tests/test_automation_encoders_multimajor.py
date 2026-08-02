"""Strict multi-major automation encoder tests (no live Odoo).

v16 hard-refuses update_path-era encoders with exact error type/message.
v17 / v18 / v19 still emit dotted ``update_path`` object_write vals.
"""

from __future__ import annotations

import pytest

from odoo_client.automation import RelatedWriteAction, UpdateFieldAction
from odoo_client.compat.adapters import (
    automation_v16,
    automation_v17,
    automation_v18,
    automation_v19,
)

_UPDATE_MAJORS = (
    ("v17", automation_v17),
    ("v18", automation_v18),
    ("v19", automation_v19),
)


@pytest.mark.parametrize(
    "relation,field,expected_msg_fragment",
    [
        ("x_vehicle_id", "x_status", "x_vehicle_id'.'x_status"),
        ("parent_id", "name", "parent_id'.'name"),
        ("a", "b", "a'.'b"),
    ],
)
def test_v16_related_write_update_path_hard_fail_exact(
    relation: str, field: str, expected_msg_fragment: str
) -> None:
    with pytest.raises(automation_v16.UnsupportedOnOdoo16Error) as exc:
        automation_v16.related_write_update_path(relation, field)
    assert isinstance(exc.value, ValueError)
    msg = str(exc.value)
    assert "not supported on Odoo 16" in msg
    assert "related_write" in msg
    assert "update_path" in msg
    assert expected_msg_fragment in msg or f"{relation!r}.{field!r}" in msg


@pytest.mark.parametrize(
    "field_name,action_name,model_id",
    [
        ("x_note", "Rule", 7),
        ("name", "n", 1),
        ("x_status", "Loan status", 42),
    ],
)
def test_v16_encode_update_field_hard_fail_exact(
    field_name: str, action_name: str, model_id: int
) -> None:
    with pytest.raises(automation_v16.UnsupportedOnOdoo16Error) as exc:
        automation_v16.encode_update_field_server_vals(
            name=action_name,
            model_id=model_id,
            action=UpdateFieldAction(field_name=field_name, value="x"),
        )
    msg = str(exc.value)
    assert "object_write update_path" in msg
    assert "not supported on Odoo 16" in msg
    assert repr(field_name) in msg
    assert repr(action_name) in msg
    assert f"model_id={model_id}" in msg
    # Must not leak an update_path-shaped payload via exception attrs
    assert not hasattr(exc.value, "update_path")


@pytest.mark.parametrize(
    "relation,field,action_name,model_id",
    [
        ("x_vehicle_id", "x_status", "n", 1),
        ("x_partner_id", "email", "Partner sync", 9),
    ],
)
def test_v16_encode_related_write_hard_fail_exact(
    relation: str, field: str, action_name: str, model_id: int
) -> None:
    with pytest.raises(automation_v16.UnsupportedOnOdoo16Error) as exc:
        automation_v16.encode_related_write_server_vals(
            name=action_name,
            model_id=model_id,
            action=RelatedWriteAction(
                relation_field=relation,
                field_name=field,
                value="x",
            ),
        )
    msg = str(exc.value)
    assert "related_write (dotted update_path)" in msg
    assert "not supported on Odoo 16" in msg
    assert repr(relation) in msg
    assert repr(field) in msg
    assert repr(action_name) in msg
    assert f"model_id={model_id}" in msg


@pytest.mark.parametrize("label,mod", _UPDATE_MAJORS)
def test_v17_plus_related_write_update_path_still_encodes(label: str, mod: object) -> None:
    path = mod.related_write_update_path("x_vehicle_id", "x_status")  # type: ignore[attr-defined]
    assert path == "x_vehicle_id.x_status", label


@pytest.mark.parametrize("label,mod", _UPDATE_MAJORS)
def test_v17_plus_encode_update_field_emits_update_path(label: str, mod: object) -> None:
    vals = mod.encode_update_field_server_vals(  # type: ignore[attr-defined]
        name="Rule",
        model_id=7,
        action=UpdateFieldAction(field_name="x_note", value="hi"),
    )
    assert vals["state"] == "object_write", label
    assert vals["update_path"] == "x_note", label
    assert vals["evaluation_type"] == "value", label
    assert vals["value"] == "hi", label
    assert vals["model_id"] == 7, label
    assert "code" not in vals


@pytest.mark.parametrize("label,mod", _UPDATE_MAJORS)
def test_v17_plus_encode_related_write_emits_dotted_update_path(
    label: str, mod: object
) -> None:
    vals = mod.encode_related_write_server_vals(  # type: ignore[attr-defined]
        name="Rule",
        model_id=7,
        action=RelatedWriteAction(
            relation_field="x_vehicle_id",
            field_name="x_status",
            value="rented",
        ),
    )
    assert vals["state"] == "object_write", label
    assert vals["update_path"] == "x_vehicle_id.x_status", label
    assert vals["value"] == "rented", label
    assert vals["name"].endswith("related x_vehicle_id.x_status"), label


def test_v16_and_v19_disagree_on_update_path_encoders() -> None:
    """Sanity: calling the same logical API must diverge by major adapter."""
    with pytest.raises(automation_v16.UnsupportedOnOdoo16Error):
        automation_v16.encode_update_field_server_vals(
            name="n",
            model_id=1,
            action=UpdateFieldAction(field_name="x_note", value="x"),
        )
    ok = automation_v19.encode_update_field_server_vals(
        name="n",
        model_id=1,
        action=UpdateFieldAction(field_name="x_note", value="x"),
    )
    assert ok["update_path"] == "x_note"
