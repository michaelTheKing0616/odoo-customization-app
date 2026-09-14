"""Unit tests for live-apply ACL groups and Odoo 19 menu group_ids."""

from __future__ import annotations

from typing import Any

from app.spec_apply_ui import (
    UiApplyResult,
    _apply_access_rules,
    _apply_root_menu_groups,
    _ensure_apply_user_in_app_groups,
    _menu_group_m2m_field,
    _resolve_or_create_group_id,
)


class _GroupFakeClient:
    def __init__(self, *, menu_fields: set[str]) -> None:
        self.menu_fields = menu_fields
        self.groups_by_name: dict[str, int] = {}
        self.created_groups: list[dict[str, Any]] = []
        self.menu_writes: list[Any] = []
        self.access_created: list[Any] = []
        self.user_writes: list[Any] = []
        self._next_gid = 10
        self._uid = 2

    @property
    def uid(self) -> int:
        return self._uid

    def field_exists(self, model: str, name: str) -> bool:
        if model == "ir.ui.menu" and name in self.menu_fields:
            return True
        if model == "res.users" and name == "group_ids":
            return True
        return False

    def resolve_xml_id(self, xml_id: str) -> int:
        if xml_id == "base.group_user":
            return 1
        raise ValueError(f"Invalid xml_id {xml_id!r} — expected module.name")

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: Any = None):
        _ = kwargs
        if model == "res.groups" and method == "search":
            domain = args[0] if args else []
            name = None
            for term in domain:
                if isinstance(term, (list, tuple)) and term and term[0] == "name":
                    name = term[2]
            if name in self.groups_by_name:
                return [self.groups_by_name[name]]
            return []
        if model == "res.groups" and method == "create":
            vals = args[0]
            self._next_gid += 1
            gid = self._next_gid
            self.groups_by_name[str(vals.get("name"))] = gid
            self.created_groups.append(vals)
            return gid
        if model == "ir.ui.menu" and method == "write":
            self.menu_writes.append(args)
            return True
        if model == "ir.model.access" and method == "search":
            return []
        if model == "res.users" and method == "read":
            return [{"id": self._uid, "group_ids": [1], "groups_id": [1]}]
        if model == "res.users" and method == "write":
            self.user_writes.append(args)
            return True
        return []

    def model_exists(self, model: str) -> bool:
        return model.startswith("x_")

    def create_access_right(self, request: Any) -> Any:
        self.access_created.append(request)
        return request


_SPEC = {
    "technical_name": "music_production_recording_studios",
    "groups": [
        {
            "id": "group_music_production_recording_studios_user",
            "name": "Music Recording Studio Location user",
        }
    ],
    "menus": [
        {
            "name": "Music Production",
            "groups": ["group_music_production_recording_studios_user"],
        }
    ],
    "access_rules": [
        {
            "name": "Music Recording Studio Location user",
            "model": "x_studio",
            "group": "group_music_production_recording_studios_user",
            "perm_read": True,
            "perm_write": True,
            "perm_create": True,
            "perm_unlink": True,
        }
    ],
}


def test_menu_group_field_prefers_odoo19_group_ids() -> None:
    client = _GroupFakeClient(menu_fields={"group_ids"})
    assert _menu_group_m2m_field(client) == "group_ids"
    client18 = _GroupFakeClient(menu_fields={"groups_id"})
    assert _menu_group_m2m_field(client18) == "groups_id"


def test_root_menu_groups_write_group_ids_on_odoo19() -> None:
    client = _GroupFakeClient(menu_fields={"group_ids"})
    result = UiApplyResult()
    _apply_root_menu_groups(client, _SPEC, 99, result)
    assert client.menu_writes
    vals = client.menu_writes[0][1]
    assert "group_ids" in vals
    assert "groups_id" not in vals
    assert not any("group assignment failed" in w for w in result.warnings)


def test_resolve_bare_group_id_creates_res_groups() -> None:
    client = _GroupFakeClient(menu_fields={"group_ids"})
    gid = _resolve_or_create_group_id(
        client, _SPEC, "group_music_production_recording_studios_user"
    )
    assert gid is not None
    assert client.created_groups[0]["name"] == "Music Recording Studio Location user"


def test_access_rules_use_created_group_not_xml_id() -> None:
    client = _GroupFakeClient(menu_fields={"group_ids"})
    result = UiApplyResult()
    _apply_access_rules(client, _SPEC, result)
    assert result.access_rights_created == 1
    assert client.access_created[0].group_id is not None
    assert not any("unresolved" in w for w in result.warnings)
    assert not any("expected module.name" in w for w in result.warnings)


def test_apply_user_gets_app_group_membership() -> None:
    client = _GroupFakeClient(menu_fields={"group_ids"})
    result = UiApplyResult()
    _ensure_apply_user_in_app_groups(client, _SPEC, result)
    assert client.user_writes
    cmds = client.user_writes[0][1]["group_ids"]
    assert cmds and cmds[0][0] == 4
    assert any("Apply login added to app group" in w for w in result.warnings)
