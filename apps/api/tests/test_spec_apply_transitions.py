"""Live apply binds workflow Confirm/Cancel to object_write actions."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.spec_apply_ui import (
    UiApplyResult,
    _bind_workflow_transition_buttons,
    rewrite_transition_buttons_to_actions,
)


def test_rewrite_object_transition_buttons_to_action_ids() -> None:
    arch = (
        '<form><header>'
        '<button string="Confirm" type="object" class="oe_highlight" '
        'invisible="x_status != \'draft\'" data-transition-to="open"/>'
        '<button string="Cancel" type="object" class="oe_highlight" '
        "invisible=\"x_status not in ('draft', 'open')\" data-transition-to=\"cancelled\"/>"
        "</header></form>"
    )
    out = rewrite_transition_buttons_to_actions(arch, {"open": 41, "cancelled": 42})
    assert 'type="object"' not in out
    assert 'data-transition-to' not in out
    assert 'name="41"' in out and 'type="action"' in out
    assert 'name="42"' in out
    assert "invisible=\"x_status != 'draft'\"" in out


class _TransitionFake:
    def __init__(self, arch: str) -> None:
        self.arch = arch
        self.view_id = 9
        self.actions: list[dict[str, Any]] = []
        self.updated: list[tuple[int, str]] = []
        self._nid = 100
        self.group_writes: list[tuple[int, dict[str, Any]]] = []
        self.groups = {"Purchase Requests Manager": 55}

    def field_exists(self, model: str, field: str) -> bool:
        return model == "ir.actions.server" and field == "groups_id"

    def model_exists(self, model: str) -> bool:
        return model == "x_engagement"

    def find_view(self, model: str, view_type: str, *, primary_only: bool = False):
        if model != "x_engagement" or view_type != "form":
            return None
        return SimpleNamespace(id=self.view_id, arch=self.arch, name="x_engagement.form")

    def update_view_arch(self, view_id: int, arch: str) -> None:
        self.arch = arch
        self.updated.append((view_id, arch))

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        if model == "ir.actions.server" and method == "search":
            domain = args[0] if args else []
            name = None
            for term in domain:
                if isinstance(term, (list, tuple)) and term[0] == "name":
                    name = term[2]
            return [a["id"] for a in self.actions if a["name"] == name][:1]
        if model == "ir.actions.server" and method == "write":
            ids, vals = args[0], args[1]
            self.group_writes.append((int(ids[0]), dict(vals)))
            return True
        if model == "res.groups" and method == "search":
            domain = args[0] if args else []
            name = None
            for term in domain:
                if isinstance(term, (list, tuple)) and term[0] == "name":
                    name = term[2]
            if name in self.groups:
                return [self.groups[name]]
            return []
        if model == "res.groups" and method == "create":
            self._nid += 1
            name = (args[0] or {}).get("name")
            self.groups[str(name)] = self._nid
            return self._nid
        return []

    def create_update_field_server_action(self, request: Any) -> Any:
        self._nid += 1
        rid = self._nid
        self.actions.append(
            {
                "id": rid,
                "name": request.name,
                "field": request.field_name,
                "value": request.value,
            }
        )
        return SimpleNamespace(id=rid)


_SPEC = {
    "models": [
        {
            "model": "x_engagement",
            "is_workflow": True,
            "state_field": {
                "field": "x_status",
                "transitions": [
                    ["draft", "open"],
                    ["open", "in_progress"],
                    ["draft", "cancelled"],
                    ["in_progress", "done"],
                ],
            },
        }
    ],
    "views": [
        {
            "model": "x_engagement",
            "type": "form",
            "arch": (
                '<form><header>'
                '<button string="Confirm" type="object" '
                'invisible="x_status != \'draft\'" data-transition-to="open"/>'
                '<button string="Cancel" type="object" '
                'invisible="x_status != \'draft\'" data-transition-to="cancelled"/>'
                "</header></form>"
            ),
        }
    ],
}


def test_bind_creates_object_write_and_rewrites_form() -> None:
    client = _TransitionFake(_SPEC["views"][0]["arch"])
    result = UiApplyResult()
    _bind_workflow_transition_buttons(client, _SPEC, result)
    assert result.workflow_buttons_bound >= 1
    assert client.updated
    arch = client.updated[0][1]
    assert 'type="object"' not in arch
    assert 'data-transition-to' not in arch
    assert 'type="action"' in arch
    values = {a["value"] for a in client.actions}
    assert {"open", "cancelled"} <= values
    assert all(a["field"] == "x_status" for a in client.actions)


def test_bind_reuses_existing_server_action() -> None:
    client = _TransitionFake(_SPEC["views"][0]["arch"])
    client.actions.append(
        {"id": 7, "name": "x_engagement: set x_status = open", "field": "x_status", "value": "open"}
    )
    result = UiApplyResult()
    _bind_workflow_transition_buttons(client, _SPEC, result)
    open_ids = [a["id"] for a in client.actions if a["value"] == "open"]
    assert open_ids == [7]
    assert 'name="7"' in client.updated[0][1]


def test_bind_restricts_approve_action_to_manager_group() -> None:
    arch = (
        '<form><header>'
        '<button string="Submit" type="object" invisible="x_status != \'draft\'" '
        'data-transition-to="submitted"/>'
        '<button string="Approve" type="object" data-approval-role="manager" '
        'invisible="x_status != \'submitted\'" data-transition-to="approved"/>'
        "</header></form>"
    )
    spec = {
        "technical_name": "purchase_requests",
        "display_name": "Purchase Requests",
        "groups": [
            {"id": "group_purchase_requests_user", "name": "Purchase Requests User"},
            {"id": "group_purchase_requests_manager", "name": "Purchase Requests Manager"},
        ],
        "_approval_flow": {
            "manager_dests": ["approved", "refused"],
            "manager_group": "group_purchase_requests_manager",
        },
        "models": [
            {
                "model": "x_engagement",
                "is_workflow": True,
                "state_field": {
                    "field": "x_status",
                    "transitions": [["draft", "submitted"], ["submitted", "approved"]],
                },
            }
        ],
        "views": [{"model": "x_engagement", "type": "form", "arch": arch}],
    }
    client = _TransitionFake(arch)
    result = UiApplyResult()
    _bind_workflow_transition_buttons(client, spec, result)
    assert result.workflow_buttons_bound >= 1
    assert "data-approval-role" not in client.updated[0][1]
    approve = next(a for a in client.actions if a["value"] == "approved")
    writes = [w for w in client.group_writes if w[0] == approve["id"]]
    assert writes
    assert writes[0][1]["groups_id"] == [(6, 0, [55])]
