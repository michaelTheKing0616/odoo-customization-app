"""Approval Requests mini-app draft + module export (CMP-10)."""

from __future__ import annotations

from typing import Any

DEFAULT_CHAIN = [
    {
        "level": 1,
        "min_approvals": 2,
        "approver_user_ids": [2, 3],
        "approver_group_id": None,
    },
    {
        "level": 2,
        "min_approvals": 1,
        "approver_user_ids": [2],
        "approver_group_id": None,
    },
]


def approval_requests_draft(
    *,
    technical_name: str = "approval_requests",
    display_name: str = "Approval Requests",
    type_model: str = "x_approval_type",
    request_model: str = "x_approval_request",
) -> dict[str, Any]:
    state_sel = (
        "[('draft','Draft'),('submitted','Submitted'),"
        "('approved','Approved'),('refused','Refused')]"
    )
    return {
        "technical_name": technical_name,
        "display_name": display_name,
        "depends": ["base", "mail"],
        "models": [
            {
                "model": type_model,
                "description": "Approval Type",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_chain_json",
                        "ttype": "text",
                        "string": "Approval chain (JSON levels)",
                    },
                    {"name": "x_active", "ttype": "boolean", "string": "Active"},
                ],
            },
            {
                "model": request_model,
                "description": "Approval Request",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "state_field": {
                    "field": "x_state",
                    "transitions": [
                        ["draft", "submitted"],
                        ["submitted", "approved"],
                        ["submitted", "refused"],
                    ],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Reference"},
                    {
                        "name": "x_type_id",
                        "ttype": "many2one",
                        "relation": type_model,
                        "string": "Approval type",
                    },
                    {
                        "name": "x_requester_id",
                        "ttype": "many2one",
                        "relation": "res.users",
                        "string": "Requester",
                    },
                    {"name": "x_subject", "ttype": "char", "string": "Subject"},
                    {"name": "x_amount", "ttype": "float", "string": "Amount"},
                    {
                        "name": "x_state",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": state_sel,
                    },
                    {"name": "x_current_level", "ttype": "integer", "string": "Current level"},
                    {
                        "name": "x_level_approvals_json",
                        "ttype": "text",
                        "string": "Level approvals JSON",
                    },
                ],
            },
        ],
        "actions": [
            {
                "name": "Approval Requests",
                "model": request_model,
                "view_mode": "list,form",
                "technical_name": "action_x_approval_request",
            },
            {
                "name": "Approval Types",
                "model": type_model,
                "view_mode": "list,form",
                "technical_name": "action_x_approval_type",
            },
        ],
        "menus": [
            {
                "name": display_name,
                "technical_name": "menu_approval_requests_root",
                "sequence": 10,
            },
            {
                "name": "Requests",
                "action_xml_id": "action_x_approval_request",
                "parent_xml_id": "menu_approval_requests_root",
                "sequence": 10,
                "technical_name": "menu_approval_requests",
            },
            {
                "name": "Types",
                "action_xml_id": "action_x_approval_type",
                "parent_xml_id": "menu_approval_requests_root",
                "sequence": 20,
                "technical_name": "menu_approval_types",
            },
        ],
        "seed_types": [
            {
                "name": "Two-level demo",
                "chain": DEFAULT_CHAIN,
            }
        ],
    }
