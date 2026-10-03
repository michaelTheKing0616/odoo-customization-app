"""Read plane, environment profile, and schema fingerprint."""

from __future__ import annotations

import pytest

from odoo_client.env_profile import EnvProfile
from odoo_client.read_plane import ReadPlane, ReadPlaneError
from odoo_client.schema_fingerprint import schema_fingerprint


def test_read_plane_rejects_writes_before_the_transport() -> None:
    seen: list[str] = []

    def transport(model: str, method: str, args: list, kwargs: dict) -> str:
        seen.append(method)
        return "ok"

    plane = ReadPlane(transport)
    assert plane.call("sale.order", "fields_get") == "ok"
    for method in ("create", "write", "unlink", "button_immediate_install", "action_post"):
        with pytest.raises(ReadPlaneError):
            plane.call("sale.order", method)
    assert seen == ["fields_get"]


def test_unknown_capability_is_not_allowed() -> None:
    profile = EnvProfile(major=19, capabilities={"inherit_views": "yes", "server_action_code": "unknown"})
    assert profile.allows("inherit_views") is True
    assert profile.allows("server_action_code") is False
    assert profile.allows("missing") is False
    for value in ("Yes", "YES", "true", " yes", "no"):
        assert EnvProfile(major=19, capabilities={"inherit_views": value}).allows("inherit_views") is False


def test_fingerprint_ignores_volatile_ids_and_changes_with_the_field() -> None:
    left = schema_fingerprint({"model": "sale.order", "fields": ["partner_id"], "id": 1, "write_date": "a", "create_date": "c1"})
    right = schema_fingerprint({"model": "sale.order", "fields": ["partner_id"], "id": 9, "write_date": "b", "create_date": "c2"})
    changed = schema_fingerprint({"model": "sale.order", "fields": ["partner_id", "x_po"], "id": 1, "write_date": "a", "create_date": "c1"})
    assert left == right
    assert left != changed
