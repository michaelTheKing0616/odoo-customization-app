"""Project / task tracker domain pack — projects, tasks, milestones, time entries."""

from __future__ import annotations

from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def project_tracker_pack() -> dict[str, Any]:
    project_status = _sel(
        ("draft", "Draft"),
        ("planning", "Planning"),
        ("active", "Active"),
        ("on_hold", "On hold"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    )
    task_status = _sel(
        ("draft", "Draft"),
        ("todo", "To do"),
        ("in_progress", "In progress"),
        ("blocked", "Blocked"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    )
    milestone_status = _sel(
        ("planned", "Planned"),
        ("in_progress", "In progress"),
        ("reached", "Reached"),
        ("missed", "Missed"),
    )
    priority = _sel(
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    )

    return {
        "technical_name": "project_tracker",
        "display_name": "Project Tracker",
        "depends": ["base", "contacts", "mail"],
        "domain_pack": "project_tracker",
        "tags": [
            "project",
            "task",
            "milestone",
            "time entry",
            "timesheet",
            "tracker",
            "pm",
            "project management",
            "deliverable",
            "sprint",
        ],
        "anti_patterns": [
            "Do NOT assign tasks directly to res.users — use x_team_member with x_user_id for login",
            "Do NOT spawn generic x_project filler trees unrelated to user request",
            "Milestones are not workflows — status selection only",
            "Billing/rates are optional floats — no invoicing engine",
        ],
        "models": [
            {
                "model": "x_team_member",
                "description": "Team Member",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_user_id",
                        "ttype": "many2one",
                        "string": "Login User",
                        "relation": "res.users",
                    },
                    {"name": "x_role", "ttype": "char", "string": "Role"},
                    {"name": "x_email", "ttype": "char", "string": "Email"},
                ],
            },
            {
                "model": "x_project",
                "description": "Project",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "state_field": {
                    "field": "x_status",
                    "transitions": [
                        ["draft", "planning"],
                        ["planning", "active"],
                        ["active", "on_hold"],
                        ["on_hold", "active"],
                        ["active", "done"],
                        ["draft", "cancelled"],
                    ],
                    "states": ["draft", "planning", "active", "on_hold", "done", "cancelled"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Project", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": project_status,
                        "required": True,
                    },
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Client",
                        "relation": "res.partner",
                    },
                    {
                        "name": "x_manager_id",
                        "ttype": "many2one",
                        "string": "Project Manager",
                        "relation": "x_team_member",
                    },
                    {"name": "x_start_date", "ttype": "date", "string": "Start"},
                    {"name": "x_end_date", "ttype": "date", "string": "End"},
                    {
                        "name": "x_task_ids",
                        "ttype": "one2many",
                        "string": "Tasks",
                        "relation": "x_task",
                        "relation_field": "x_project_id",
                    },
                    {
                        "name": "x_milestone_ids",
                        "ttype": "one2many",
                        "string": "Milestones",
                        "relation": "x_milestone",
                        "relation_field": "x_project_id",
                    },
                ],
            },
            {
                "model": "x_task",
                "description": "Task",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "state_field": {
                    "field": "x_status",
                    "transitions": [
                        ["draft", "todo"],
                        ["todo", "in_progress"],
                        ["in_progress", "blocked"],
                        ["blocked", "in_progress"],
                        ["in_progress", "done"],
                        ["todo", "cancelled"],
                    ],
                    "states": ["draft", "todo", "in_progress", "blocked", "done", "cancelled"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Task", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": task_status,
                        "required": True,
                    },
                    {
                        "name": "x_project_id",
                        "ttype": "many2one",
                        "string": "Project",
                        "relation": "x_project",
                        "required": True,
                    },
                    {
                        "name": "x_assignee_id",
                        "ttype": "many2one",
                        "string": "Assignee",
                        "relation": "x_team_member",
                    },
                    {
                        "name": "x_priority",
                        "ttype": "selection",
                        "string": "Priority",
                        "selection": priority,
                    },
                    {"name": "x_due_date", "ttype": "date", "string": "Due Date"},
                    {"name": "x_description", "ttype": "text", "string": "Description"},
                    {
                        "name": "x_time_entry_ids",
                        "ttype": "one2many",
                        "string": "Time Entries",
                        "relation": "x_time_entry",
                        "relation_field": "x_task_id",
                    },
                ],
            },
            {
                "model": "x_milestone",
                "description": "Milestone",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Milestone", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": milestone_status,
                        "required": True,
                    },
                    {
                        "name": "x_project_id",
                        "ttype": "many2one",
                        "string": "Project",
                        "relation": "x_project",
                        "required": True,
                    },
                    {"name": "x_target_date", "ttype": "date", "string": "Target Date"},
                ],
            },
            {
                "model": "x_time_entry",
                "description": "Time Entry",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Entry", "required": True},
                    {
                        "name": "x_task_id",
                        "ttype": "many2one",
                        "string": "Task",
                        "relation": "x_task",
                        "required": True,
                    },
                    {
                        "name": "x_member_id",
                        "ttype": "many2one",
                        "string": "Team Member",
                        "relation": "x_team_member",
                        "required": True,
                    },
                    {"name": "x_date", "ttype": "date", "string": "Date", "required": True},
                    {"name": "x_hours", "ttype": "float", "string": "Hours", "required": True},
                    {"name": "x_description", "ttype": "text", "string": "Description"},
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_project",
                "label": "Tasks",
                "related_model": "x_task",
                "relation_field": "x_project_id",
                "icon": "fa-tasks",
            },
            {
                "on_model": "x_task",
                "label": "Time",
                "related_model": "x_time_entry",
                "relation_field": "x_task_id",
                "icon": "fa-clock-o",
            },
        ],
        "automations": [
            {
                "name": "Activity on blocked task",
                "model": "x_task",
                "trigger": "on_write",
                "filter_domain": "[('x_status', '=', 'blocked')]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Unblock task"}
                ],
            },
            {
                "name": "Follow-up overdue tasks",
                "model": "x_task",
                "trigger": "on_time",
                "filter_domain": "[('x_status', 'in', ['todo', 'in_progress'])]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Review overdue task"}
                ],
            },
        ],
        "reuse_hints": [
            {"model": "res.partner", "reason": "Clients as Contacts on x_project"},
            {"model": "res.users", "reason": "Login mapping via x_team_member.x_user_id only"},
        ],
    }


__all__ = ["project_tracker_pack"]
